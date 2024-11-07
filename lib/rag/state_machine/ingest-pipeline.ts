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
import { BaseProps } from '../../schema';
import { Code, Function, ILayerVersion, Runtime } from 'aws-cdk-lib/aws-lambda';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { LAMBDA_MEMORY, LAMBDA_TIMEOUT, OUTPUT_PATH } from './constants';
import { Vpc } from '../../networking/vpc';
import { LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Rule, Schedule, EventPattern, RuleTargetInput, EventField } from 'aws-cdk-lib/aws-events';
import { SfnStateMachine } from 'aws-cdk-lib/aws-events-targets';
import { RagRepositoryType } from '../../schema';
import * as kms from 'aws-cdk-lib/aws-kms';

type PipelineConfig = {
    chunkOverlap: number;
    chunkSize: number;
    embeddingModel: string;
    s3Bucket: string;
    s3Prefix: string;
    trigger: string;
    collectionName: string;
};

type RdsConfig = {
    username: string;
    dbHost?: string;
    dbName: string;
    dbPort: number;
    passwordSecretId?: string;
};

type IngestPipelineStateMachineProps = BaseProps & {
    vpc?: Vpc;
    pipelineConfig: PipelineConfig;
    rdsConfig?: RdsConfig;
    repositoryId: string;
    type: RagRepositoryType;
    layers?: ILayerVersion[];
};

/**
 * State Machine for creating models.
 */
export class IngestPipelineStateMachine extends Construct {
    readonly stateMachineArn: string;

    constructor (scope: Construct, id: string, props: IngestPipelineStateMachineProps) {
        super(scope, id);

        const {config, vpc, pipelineConfig, rdsConfig, repositoryId, type, layers} = props;

        // Create KMS key for environment variable encryption
        const kmsKey = new kms.Key(this, 'EnvironmentEncryptionKey', {
            enableKeyRotation: true,
            description: 'Key for encrypting Lambda environment variables'
        });

        const environment = {
            CHUNK_OVERLAP: pipelineConfig.chunkOverlap.toString(),
            CHUNK_SIZE: pipelineConfig.chunkSize.toString(),
            EMBEDDING_MODEL: pipelineConfig.embeddingModel,
            S3_BUCKET: pipelineConfig.s3Bucket,
            S3_PREFIX: pipelineConfig.s3Prefix,
            REPOSITORY_ID: repositoryId,
            REPOSITORY_TYPE: type,
            REST_API_VERSION: 'v2',
            MANAGEMENT_KEY_SECRET_NAME_PS: `${config.deploymentPrefix}/managementKeySecretName`,
            RDS_CONNECTION_INFO_PS_NAME: `${config.deploymentPrefix}/LisaServeRagPGVectorConnectionInfo`,
            OPENSEARCH_ENDPOINT_PS_NAME: `${config.deploymentPrefix}/lisaServeRagRepositoryEndpoint`,
            LISA_API_URL_PS_NAME: `${config.deploymentPrefix}/lisaServeRestApiUri`,
            LOG_LEVEL: config.logLevel,
            RESTAPI_SSL_CERT_ARN: config.restApiConfig.sslCertIamArn || '',
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
                `arn:aws:s3:::${pipelineConfig.s3Bucket}`,
                `arn:aws:s3:::${pipelineConfig.s3Bucket}/*`
            ]
        });

        // Create array of policy statements
        const policyStatements = [s3PolicyStatement];

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
            runtime: Runtime.PYTHON_3_10,
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
            runtime: Runtime.PYTHON_3_10,
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
                        `arn:aws:ssm:${process.env.CDK_DEFAULT_REGION}:${process.env.CDK_DEFAULT_ACCOUNT}:parameter${config.deploymentPrefix}/LisaServeRagPGVectorConnectionInfo`,
                        `arn:aws:ssm:${process.env.CDK_DEFAULT_REGION}:${process.env.CDK_DEFAULT_ACCOUNT}:parameter${config.deploymentPrefix}/lisaServeRagRepositoryEndpoint`,
                        `arn:aws:ssm:${process.env.CDK_DEFAULT_REGION}:${process.env.CDK_DEFAULT_ACCOUNT}:parameter${config.deploymentPrefix}/lisaServeRestApiUri`,
                        `arn:aws:ssm:${process.env.CDK_DEFAULT_REGION}:${process.env.CDK_DEFAULT_ACCOUNT}:parameter${config.deploymentPrefix}/managementKeySecretName`
                    ]
                }),
                new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: ['secretsmanager:GetSecretValue'],
                    resources: [
                        `arn:aws:secretsmanager:${process.env.CDK_DEFAULT_REGION}:${process.env.CDK_DEFAULT_ACCOUNT}:secret:${config.deploymentName}-lisa-management-key*`,
                        `arn:aws:secretsmanager:${process.env.CDK_DEFAULT_REGION}:${process.env.CDK_DEFAULT_ACCOUNT}:secret:${config.deploymentName}LisaRAGPGVectorDBSecret*`
                    ]
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
