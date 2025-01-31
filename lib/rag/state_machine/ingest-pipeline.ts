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
    Choice,
    Condition,
    DefinitionBody,
    Fail,
    StateMachine,
    Succeed,
    Map,
    Pass,
    Chain,
} from 'aws-cdk-lib/aws-stepfunctions';
import { Construct } from 'constructs';
import { Duration } from 'aws-cdk-lib';
import { BaseProps, PipelineConfig } from '../../schema';
import { Code, Function, ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { LAMBDA_MEMORY, LAMBDA_TIMEOUT, OUTPUT_PATH } from './constants';
import { Vpc } from '../../networking/vpc';
import { LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Rule, Schedule, EventPattern, RuleTargetInput, EventField } from 'aws-cdk-lib/aws-events';
import { SfnStateMachine } from 'aws-cdk-lib/aws-events-targets';
import { RagRepositoryType } from '../../schema';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as cdk from 'aws-cdk-lib';
import { getDefaultRuntime } from '../../api-base/utils';
import { Table } from 'aws-cdk-lib/aws-dynamodb';

type RdsConfig = {
    username: string;
    dbHost?: string;
    dbName: string;
    dbPort: number;
    passwordSecretId?: string;
};

type IngestPipelineStateMachineProps = BaseProps & {
    vpc?: Vpc;
    baseEnvironment:  Record<string, string>,
    pipelineConfig: PipelineConfig;
    rdsConfig?: RdsConfig;
    repositoryId: string;
    type: RagRepositoryType;
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

        const {config, vpc, type, pipelineConfig, baseEnvironment, rdsConfig, repositoryId, layers, ragDocumentTable, ragSubDocumentTable} = props;

        // Create KMS key for environment variable encryption
        const kmsKey = new kms.Key(this, 'EnvironmentEncryptionKey', {
            enableKeyRotation: true,
            description: 'Key for encrypting Lambda environment variables'
        });

        const environment = {
            ...baseEnvironment,
            CHUNK_OVERLAP: pipelineConfig.chunkOverlap.toString(),
            CHUNK_SIZE: pipelineConfig.chunkSize.toString(),
            EMBEDDING_MODEL: pipelineConfig.embeddingModel,
            S3_BUCKET: pipelineConfig.s3Bucket,
            S3_PREFIX: pipelineConfig.s3Prefix,
            REPOSITORY_ID: repositoryId,
            REPOSITORY_TYPE: type,
            ...(rdsConfig && {
                RDS_USERNAME: rdsConfig.username,
                RDS_HOST: rdsConfig.dbHost || '',
                RDS_DATABASE: rdsConfig.dbName,
                RDS_PORT: rdsConfig.dbPort.toString(),
                RDS_PASSWORD_SECRET_ID: rdsConfig.passwordSecretId || ''
            })
        };

        // Create S3 policy statement for both functions
        const s3PolicyStatement = new PolicyStatement({
            effect: Effect.ALLOW,
            actions: ['s3:GetObject', 's3:ListBucket'],
            resources: [
                `arn:${cdk.Aws.PARTITION}:s3:::${pipelineConfig.s3Bucket}`,
                `arn:${cdk.Aws.PARTITION}:s3:::${pipelineConfig.s3Bucket}/*`
            ]
        });
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

        // Create array of policy statements
        const policyStatements = [s3PolicyStatement, dynamoPolicyStatement];

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

        // Function to list objects modified in last 24 hours
        const listModifiedObjectsFunction = new Function(this, 'listModifiedObjectsFunc', {
            runtime: getDefaultRuntime(),
            handler: 'repository.state_machine.list_modified_objects.handle_list_modified_objects',
            code: Code.fromAsset('./lambda'),
            timeout: LAMBDA_TIMEOUT,
            memorySize: LAMBDA_MEMORY,
            vpc: vpc!.vpc,
            environment: environment,
            environmentEncryption: kmsKey,
            layers: layers,
            initialPolicy: policyStatements
        });

        const listModifiedObjects = new LambdaInvoke(this, 'listModifiedObjects', {
            lambdaFunction: listModifiedObjectsFunction,
            outputPath: OUTPUT_PATH,
        });

        // Create a Pass state to normalize event structure for single file processing
        const prepareSingleFile = new Pass(this, 'PrepareSingleFile', {
            parameters: {
                'files': [{
                    'bucket': pipelineConfig.s3Bucket,
                    'key.$': '$.detail.object.key'
                }]
            }
        });

        // Create the ingest documents function with S3 permissions
        const pipelineIngestDocumentsFunction = new Function(this, 'pipelineIngestDocumentsMapFunc', {
            runtime: getDefaultRuntime(),
            handler: 'repository.pipeline_ingest_documents.handle_pipeline_ingest_documents',
            code: Code.fromAsset('./lambda'),
            timeout: LAMBDA_TIMEOUT,
            memorySize: LAMBDA_MEMORY,
            vpc: vpc!.vpc,
            environment: environment,
            environmentEncryption: kmsKey,
            layers: layers,
            initialPolicy: [
                ...policyStatements, // Include all base policies including certificate policy
                new PolicyStatement({
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
                }),
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: ['secretsmanager:GetSecretValue'],
                    resources: ['*']
                })
            ]
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

        // Add EventBridge Rules based on pipeline configuration
        if (pipelineConfig.trigger === 'daily') {
            // Create daily cron trigger with input template
            new Rule(this, 'DailyIngestRule', {
                schedule: Schedule.cron({
                    minute: '0',
                    hour: '0'
                }),
                targets: [new SfnStateMachine(stateMachine, {
                    input: RuleTargetInput.fromObject({
                        version: '0',
                        id: EventField.eventId,
                        'detail-type': 'Scheduled Event',
                        source: 'aws.events',
                        time: EventField.time,
                        region: EventField.region,
                        detail: {
                            bucket: pipelineConfig.s3Bucket,
                            prefix: pipelineConfig.s3Prefix,
                            trigger: 'daily'
                        }
                    })
                })]
            });
        } else if (pipelineConfig.trigger === 'event') {
            // Create S3 event trigger with complete event pattern and transform input
            const detail: any = {
                bucket: {
                    name: [pipelineConfig.s3Bucket]
                }
            };

            // Add prefix filter if specified and not root
            if (pipelineConfig.s3Prefix && pipelineConfig.s3Prefix !== '/') {
                detail.object = {
                    key: [{
                        prefix: pipelineConfig.s3Prefix
                    }]
                };
            }

            const eventPattern: EventPattern = {
                source: ['aws.s3'],
                detailType: ['Object Created', 'Object Modified'],
                detail
            };

            new Rule(this, 'S3EventIngestRule', {
                eventPattern,
                targets: [new SfnStateMachine(stateMachine, {
                    input: RuleTargetInput.fromObject({
                        'detail-type': EventField.detailType,
                        source: EventField.source,
                        time: EventField.time,
                        region: EventField.region,
                        detail: {
                            bucket: pipelineConfig.s3Bucket,
                            prefix: pipelineConfig.s3Prefix,
                            object: {
                                key: EventField.fromPath('$.detail.object.key')
                            },
                            trigger: 'event'
                        }
                    })
                })]
            });
        }

        this.stateMachineArn = stateMachine.stateMachineArn;
    }
}
