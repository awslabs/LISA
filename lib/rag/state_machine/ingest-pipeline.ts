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

import {
    Chain,
    Choice,
    Condition,
    DefinitionBody,
    Fail,
    Map,
    Pass,
    StateMachine,
    Succeed,
} from 'aws-cdk-lib/aws-stepfunctions';
import { Construct } from 'constructs';
import * as cdk from 'aws-cdk-lib';
import { Duration } from 'aws-cdk-lib';
import { BaseProps } from '../../schema';
import { Code, Function, ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { Effect, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { LAMBDA_MEMORY, LAMBDA_TIMEOUT, OUTPUT_PATH } from './constants';
import { Vpc } from '../../networking/vpc';
import { LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as kms from 'aws-cdk-lib/aws-kms';
import { getDefaultRuntime } from '../../api-base/utils';
import { Table } from 'aws-cdk-lib/aws-dynamodb';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { LAMBDA_PATH } from '../../util';

type IngestPipelineStateMachineProps = BaseProps & {
    baseEnvironment:  Record<string, string>,
    vpc?: Vpc;
    layers?: ILayerVersion[];
    ragDocumentTable: Table;
    ragSubDocumentTable: Table;
};

/**
 * State Machine for creating models.
 */
export class IngestPipelineStateMachine extends Construct {
    readonly stateMachineArn: string;

    constructor (scope: Construct, id: string, props: IngestPipelineStateMachineProps) {
        super(scope, id);

        const {config, vpc, layers, baseEnvironment, ragDocumentTable, ragSubDocumentTable} = props;

        // Create KMS key for environment variable encryption
        const kmsKey = new kms.Key(this, 'EnvironmentEncryptionKey', {
            enableKeyRotation: true,
            description: 'Key for encrypting Lambda environment variables'
        });

        const environment = {
            ...baseEnvironment,
        };

        // Allow DynamoDB Read/Write to RAG Document Table
        const dynamoPolicyStatement = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'dynamodb:BatchGetItem',
                'dynamodb:GetItem',
                'dynamodb:Query',
                'dynamodb:Scan',
                'dynamodb:BatchWriteItem',
                'dynamodb:PutItem',
                'dynamodb:UpdateItem',
            ],
            resources: [
                ragDocumentTable.tableArn,
                `${ragDocumentTable.tableArn}/index/*`,
                ragSubDocumentTable.tableArn,
                `${ragSubDocumentTable.tableArn}/index/*`
            ]
        });
        // Create log group
        const cloudWatchLogsPolicy = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents'
            ],
            resources: [
                `arn:${cdk.Aws.PARTITION}:logs:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:log-group:/aws/lambda/*`
            ]
        });

        // Create array of policy statements
        const policyStatements = [dynamoPolicyStatement, cloudWatchLogsPolicy];

        // Create IAM certificate policy if certificate ARN is provided
        let certPolicyStatement;
        if (config.restApiConfig.sslCertIamArn) {
            certPolicyStatement = new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['iam:GetServerCertificate'],
                resources: [config.restApiConfig.sslCertIamArn]
            });
            policyStatements.push(certPolicyStatement);
        }

        const ingestPipelineRole = new Role(this, 'IngestPipelineRole', {
            roleName: `${config.deploymentName}-IngestPipelineRole`,
            assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
        });
        new StringParameter(this, 'IngestPipelineRoleArnParameter', {
            parameterName: `${config.deploymentPrefix}/IngestPipelineRoleArn`,
            stringValue: ingestPipelineRole.roleArn,
        });

        policyStatements.push(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['ssm:GetParameter'],
            resources: [
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${config.deploymentPrefix}/LisaServeRagPGVectorConnectionInfo`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${config.deploymentPrefix}/lisaServeRagRepositoryEndpoint`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${config.deploymentPrefix}/lisaServeRestApiUri`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${config.deploymentPrefix}/managementKeySecretName`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${config.deploymentPrefix}/registeredRepositories`,
                `arn:${cdk.Aws.PARTITION}:ssm:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:parameter${config.deploymentPrefix}/LisaServeRagConnectionInfo/*`
            ]
        }));

        policyStatements.push(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['secretsmanager:GetSecretValue'],
            resources: ['*']
        }));

        policyStatements.push(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
                'ec2:DescribeNetworkInterfaces',
                'ec2:CreateNetworkInterface',
                'ec2:DeleteNetworkInterface'
            ],
            resources: ['*']
        }));

        policyStatements.map((policyStatement) => ingestPipelineRole.addToPolicy(policyStatement));
        const lambdaPath = config.lambdaPath || LAMBDA_PATH;

        // Function to list objects modified in last 24 hours
        const listModifiedObjectsFunction = new Function(this, 'listModifiedObjectsFunc', {
            runtime: getDefaultRuntime(),
            handler: 'repository.state_machine.list_modified_objects.handle_list_modified_objects',
            code: Code.fromAsset(lambdaPath),
            timeout: LAMBDA_TIMEOUT,
            memorySize: LAMBDA_MEMORY,
            vpc: vpc!.vpc,
            environment: environment,
            environmentEncryption: kmsKey,
            layers: layers,
            role: ingestPipelineRole
        });

        const listModifiedObjects = new LambdaInvoke(this, 'listModifiedObjects', {
            lambdaFunction: listModifiedObjectsFunction,
            outputPath: OUTPUT_PATH,
        });

        // Create a Pass state to normalize event structure for single file processing
        const prepareSingleFile = new Pass(this, 'PrepareSingleFile', {
            parameters: {
                'files': [{
                    'bucket.$': '$.detail.bucket',
                    'key.$': '$.detail.object.key',
                    'repositoryId.$': '$.detail.repositoryId',
                    'pipelineConfig.$': '$.detail.pipelineConfig'
                }]
            }
        });

        // Create the ingest documents function with S3 permissions
        const pipelineIngestDocumentsFunction = new Function(this, 'pipelineIngestDocumentsMapFunc', {
            runtime: getDefaultRuntime(),
            handler: 'repository.pipeline_ingest_documents.handle_pipeline_ingest_documents',
            code: Code.fromAsset(lambdaPath),
            timeout: LAMBDA_TIMEOUT,
            memorySize: LAMBDA_MEMORY,
            vpc: vpc!.vpc,
            environment: environment,
            environmentEncryption: kmsKey,
            layers: layers,
            role: ingestPipelineRole
        });

        const pipelineIngestDocumentsMap = new LambdaInvoke(this, 'pipelineIngestDocumentsMap', {
            lambdaFunction: pipelineIngestDocumentsFunction,
            retryOnServiceExceptions: true, // Enable retries for service exceptions
            resultPath: '$.taskResult' // Store the entire result
        });

        const failState = new Fail(this, 'CreateFailed', {
            cause: 'Pipeline execution failed',
            error: 'States.TaskFailed'
        });

        const successState = new Succeed(this, 'CreateSuccess');

        // Map state for distributed processing with rate limiting
        const processFiles = new Map(this, 'ProcessFiles', {
            maxConcurrency: 5,
            itemsPath: '$.files',
            resultPath: '$.mapResults' // Store map results in mapResults field
        });

        // Configure the iterator without error handling (will be handled at Map level)
        processFiles.iterator(pipelineIngestDocumentsMap);

        // Add error handling at Map level
        processFiles.addCatch(failState, {
            errors: ['States.ALL'],
            resultPath: '$.error'
        });

        // Choice state to determine trigger type
        const triggerChoice = new Choice(this, 'DetermineTriggerType')
            .when(Condition.stringEquals('$.detail.trigger', 'daily'), listModifiedObjects)
            .otherwise(prepareSingleFile);

        // Build the chain
        const definition = Chain
            .start(triggerChoice);

        listModifiedObjects.next(processFiles);
        prepareSingleFile.next(processFiles);
        processFiles.next(successState);

        const stateMachine = new StateMachine(this, 'IngestPipeline', {
            definitionBody: DefinitionBody.fromChainable(definition),
            timeout: Duration.hours(2),
        });
        new StringParameter(this, 'IngestPipelineStateMachineArnParameter', {
            parameterName: `${config.deploymentPrefix}/IngestPipelineStateMachineArn`,
            stringValue: stateMachine.stateMachineArn,
        });

        this.stateMachineArn = stateMachine.stateMachineArn;
    }
}
