/**
 Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

 Licensed under the Apache License, Version 2.0 (the "License").
 You may not use this file except in compliance with the License.
 You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 */

import { Code, Function, ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { DefinitionBody, Fail, Pass, StateMachine, Succeed } from 'aws-cdk-lib/aws-stepfunctions';
import { Construct } from 'constructs';
import { BaseProps } from '../../schema';
import { Vpc } from '../../networking/vpc';
import { Table } from 'aws-cdk-lib/aws-dynamodb';
import { getDefaultRuntime } from '../../api-base/utils';
import { LAMBDA_MEMORY, LAMBDA_TIMEOUT } from './constants';
import { Effect, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import * as cdk from 'aws-cdk-lib';

import { LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Key } from 'aws-cdk-lib/aws-kms';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';

type DeletePipelineStateMachineProps = BaseProps & {
    baseEnvironment:  Record<string, string>,
    vpc?: Vpc;
    ragDocumentTable: Table;
    ragSubDocumentTable: Table;
    layers: ILayerVersion[];
};

export class DeletePipelineStateMachine extends Construct {
    readonly stateMachineArn: string;

    constructor (scope: Construct, id: string, props: DeletePipelineStateMachineProps) {
        super(scope, id);

        const {config, vpc,  baseEnvironment, layers, ragDocumentTable, ragSubDocumentTable} = props;

        const environment = {
            ...baseEnvironment,
        };

        // Create KMS key for environment variable encryption
        const kmsKey = new Key(this, 'EnvironmentEncryptionKey', {
            enableKeyRotation: true,
            description: 'Key for encrypting Lambda environment variables'
        });
        const deletePipelineRole = new Role(this, 'DeletePipelineRole', {
            roleName: `${config.deploymentName}-DeletePipelineRole`,
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
        });
        new StringParameter(this, 'DeletePipelineRoleArnParameter', {
            parameterName: `${config.deploymentPrefix}/DeletePipelineRoleArn`,
            stringValue: deletePipelineRole.roleArn,
        });

        const policyStatements = this.createPolicy(ragDocumentTable, ragSubDocumentTable, config.restApiConfig.sslCertIamArn, config.deploymentPrefix);
        policyStatements.map((policyStatement) => deletePipelineRole.addToPolicy(policyStatement));

        const normalizeInput = new Pass(this, 'FormatInput', {
            parameters: {
                'bucket.$': '$.detail.bucket',
                'key.$': '$.detail.object.key',
                'prefix.$': '$.detail.prefix',
                'repositoryId.$': '$.detail.repositoryId',
                'pipelineConfig.$': '$.detail.pipelineConfig'
            },
        });

        // Create the ingest documents function with S3 permissions
        const deleteDocumentsFunction = new Function(this, 'pipelineDeleteDocumentFunc', {
            runtime: getDefaultRuntime(),
            handler: 'repository.pipeline_delete_document.lambda_handler',
            code: Code.fromAsset('./lambda'),
            timeout: LAMBDA_TIMEOUT,
            memorySize: LAMBDA_MEMORY,
            vpc: vpc!.vpc,
            environment: environment,
            environmentEncryption: kmsKey,
            layers: layers,
            role: deletePipelineRole
        });

        // Create a Step Function task to invoke the Lambda
        const invokeTask = new LambdaInvoke(this, 'InvokeDeleteDocumentLambda', {
            lambdaFunction: deleteDocumentsFunction,
            outputPath: '$.Payload',
        });

        // Create the state machine
        const stateMachine = new StateMachine(this, 'DeleteProcessingStateMachine', {
            definitionBody: DefinitionBody.fromChainable(
                normalizeInput
                    .next(
                        invokeTask
                            .addCatch(new Fail(this, 'FailState', {
                                cause: 'Lambda function failed to process delete event',
                                error: 'DeleteProcessingError',
                            })))
                    .next(
                        new Succeed(this, 'SuccessState', {
                            comment: 'Delete processing completed successfully',
                        }),
                    ),
            ),
            tracingEnabled: true
        });
        new StringParameter(this, 'DeletePipelineStateMachineArnParameter', {
            parameterName: `${config.deploymentPrefix}/DeletePipelineStateMachineArn`,
            stringValue: stateMachine.stateMachineArn,
        });

        this.stateMachineArn = stateMachine.stateMachineArn;

    }

    createPolicy (ragDocumentTable: any, ragSubDocumentTable: any, sslCertIamArn: string | null, deploymentPrefix?: string){
        // Allow DynamoDB Read/Delete RAG Document Table
        const dynamoPolicyStatement = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'dynamodb:BatchGetItem',
                'dynamodb:GetItem',
                'dynamodb:BatchWriteItem',
                'dynamodb:Query',
                'dynamodb:Scan',
                'dynamodb:DeleteItem',
            ],
            resources: [
                ragDocumentTable.tableArn,
                `${ragDocumentTable.tableArn}/index/*`,
                ragSubDocumentTable.tableArn,
                `${ragSubDocumentTable.tableArn}/index/*`
            ]
        });
        // Allow fetching SSM parameters
        const ssmPolicy = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['ssm:GetParameter'],
            resources: [
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/LisaServeRagPGVectorConnectionInfo`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/lisaServeRagRepositoryEndpoint`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/lisaServeRestApiUri`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/managementKeySecretName`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/registeredRepositories`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${deploymentPrefix}/LisaServeRagConnectionInfo/*`,
            ],
        });
        const secretsManagerPolicy = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['secretsmanager:GetSecretValue'],
            resources: ['*']
        });
        const ec2Policy = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'ec2:DescribeNetworkInterfaces',
                'ec2:CreateNetworkInterface',
                'ec2:DeleteNetworkInterface'
            ],
            resources: ['*']
        });

        const policies = [dynamoPolicyStatement, ssmPolicy, secretsManagerPolicy, ec2Policy];
        // Create IAM certificate policy if certificate ARN is provided
        if (sslCertIamArn) {
            const certPolicyStatement = new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['iam:GetServerCertificate'],
                resources: [sslCertIamArn]
            });
            policies.push(certPolicyStatement);
        }

        return policies;
    }
}
