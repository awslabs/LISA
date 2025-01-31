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
import { DefinitionBody, Fail, StateMachine, Succeed } from 'aws-cdk-lib/aws-stepfunctions';
import { Construct } from 'constructs';
import { BaseProps, RagRepositoryType } from '../../schema';
import { Vpc } from '../../networking/vpc';
import { Table } from 'aws-cdk-lib/aws-dynamodb';
import { getDefaultRuntime } from '../../api-base/utils';
import { LAMBDA_MEMORY, LAMBDA_TIMEOUT } from './constants';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import * as cdk from 'aws-cdk-lib';

import { EventField, EventPattern, Rule, RuleTargetInput } from 'aws-cdk-lib/aws-events';
import { SfnStateMachine } from 'aws-cdk-lib/aws-events-targets';
import { LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Key } from 'aws-cdk-lib/aws-kms';

type DeletePipelineStateMachineProps = BaseProps & {
    baseEnvironment:  Record<string, string>,
    vpc?: Vpc;
    repositoryId: string;
    type: RagRepositoryType;
    layers: ILayerVersion[];
    ragDocumentTable: Table;
    ragSubDocumentTable: Table;
    embeddingModel: string;
    s3Bucket: string;
    s3Prefix: string;
};

export class DeletePipelineStateMachine extends Construct {
    constructor (scope: Construct, id: string, props: DeletePipelineStateMachineProps) {
        super(scope, id);

        const {config, vpc, type, s3Bucket, baseEnvironment, embeddingModel, s3Prefix, repositoryId, layers, ragDocumentTable, ragSubDocumentTable} = props;

        const environment = {
            ...baseEnvironment,
            EMBEDDING_MODEL: embeddingModel,
            S3_BUCKET: s3Bucket,
            S3_PREFIX: s3Prefix,
            REPOSITORY_TYPE: type,
            REPOSITORY_ID: repositoryId
        };

        // Create KMS key for environment variable encryption
        const kmsKey = new Key(this, 'EnvironmentEncryptionKey', {
            enableKeyRotation: true,
            description: 'Key for encrypting Lambda environment variables'
        });

        const policyStatements = this.createPolicy(s3Bucket, ragDocumentTable, ragSubDocumentTable, config.restApiConfig.sslCertIamArn, config.deploymentPrefix);

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
            initialPolicy: policyStatements
        });

        // Create a Step Function task to invoke the Lambda
        const invokeTask = new LambdaInvoke(this, 'InvokeDeleteDocumentLambda', {
            lambdaFunction: deleteDocumentsFunction,
            outputPath: '$.Payload',
        });

        // Create the state machine
        const stateMachine = new StateMachine(this, 'DeleteProcessingStateMachine', {
            definitionBody: DefinitionBody.fromChainable(
                invokeTask
                    .addCatch(new Fail(this, 'FailState', {
                        cause: 'Lambda function failed to process delete event',
                        error: 'DeleteProcessingError',
                    }))
                    .next(
                        new Succeed(this, 'SuccessState', {
                            comment: 'Delete processing completed successfully',
                        }),
                    ),
            ),
            tracingEnabled: true
        });

        // Create EventBridge rule for S3 delete events
        const eventPattern: EventPattern = {
            source: ['aws.s3'],
            detailType: ['Object Deleted'],
            detail: this.getBucketDetails(s3Bucket, s3Prefix)
        };

        // Create the rule to trigger the state machine
        new Rule(this, 'S3DeleteDocumentRule', {
            eventPattern,
            targets: [new SfnStateMachine(stateMachine, {
                input: RuleTargetInput.fromObject({
                    'detail-type': EventField.detailType,
                    source: EventField.source,
                    time: EventField.time,
                    bucket: s3Bucket,
                    prefix: s3Prefix,
                    key: EventField.fromPath('$.detail.object.key')
                }),
            })],
        });
    }

    getBucketDetails (s3Bucket:string, s3Prefix: string): [key: string] {
        // Create S3 event trigger with complete event pattern and transform input
        const detail: any = {
            bucket: {
                name: [s3Bucket]
            }
        };
        // Add prefix filter if specified and not root
        if (s3Prefix && s3Prefix !== '/') {
            detail.object = {
                key: [{
                    prefix: s3Prefix
                }]
            };
        }

        return detail;
    }

    createPolicy (s3Bucket:string, ragDocumentTable: any, ragSubDocumentTable: any, sslCertIamArn: string | null, deploymentPrefix?: string){
        // Create S3 policy statement
        const s3PolicyStatement = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['s3:GetObject', 's3:ListBucket', 's3:DeleteObject'],
            resources: [
                `arn:${cdk.Aws.PARTITION}:s3:::${s3Bucket}`,
                `arn:${cdk.Aws.PARTITION}:s3:::${s3Bucket}/*`
            ]
        });
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

        const policies = [s3PolicyStatement, dynamoPolicyStatement, ssmPolicy, secretsManagerPolicy];
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
