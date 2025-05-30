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
/**
 * IngestionJobConstruct creates AWS infrastructure for document ingestion pipeline
 * This includes:
 * - DynamoDB table for tracking ingestion jobs
 * - AWS Batch compute environment and job queue for processing documents
 * - Lambda functions for handling scheduled ingestion and S3 events
 */
import { Duration, Size, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { BaseProps } from '../../schema';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as batch from 'aws-cdk-lib/aws-batch';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { DockerImageAsset } from 'aws-cdk-lib/aws-ecr-assets';
import { Vpc } from '../../networking/vpc';
import path from 'path';
import { ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { getDefaultRuntime } from '../../api-base/utils';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import * as fs from 'fs';
import * as crypto from 'crypto';

// Props interface for the IngestionJobConstruct
export type IngestionJobConstructProps = StackProps & BaseProps & {
    vpc: Vpc,
    lambdaRole: iam.IRole,
    baseEnvironment: Record<string, string>,
    layers?: ILayerVersion[];
};

export class IngestionJobConstruct extends Construct {
    constructor (scope: Construct, id: string, props: IngestionJobConstructProps) {
        super(scope, id);

        const { config, vpc, lambdaRole, layers, baseEnvironment } = props;
        const hash = crypto.randomBytes(6).toString('hex');

        // DynamoDB table for tracking ingestion jobs
        // Uses id as partition key with additional GSIs for querying by created date, s3 path and document id
        const ingestionJobTable = new dynamodb.Table(this, 'IngestionJobTable', {
            tableName: `${config.deploymentName}-${config.deploymentStage}-ingestion-job`,
            partitionKey: {
                name: 'id',
                type: dynamodb.AttributeType.STRING
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            removalPolicy: config.removalPolicy
        });
        ingestionJobTable.grantReadWriteData(props.lambdaRole);
        baseEnvironment['LISA_INGESTION_JOB_TABLE_NAME'] = ingestionJobTable.tableName;

        // GSI for querying by document ID
        ingestionJobTable.addGlobalSecondaryIndex({
            indexName: 'documentId',
            partitionKey: {
                name: 'document_id',
                type: dynamodb.AttributeType.STRING
            },
            projectionType: dynamodb.ProjectionType.ALL
        });

        // CloudWatch log group for batch job container logs
        const logGroup = new logs.LogGroup(this, 'IngestionJobLogGroup', {
            retention: logs.RetentionDays.ONE_WEEK,
            removalPolicy: config.removalPolicy
        });

        // AWS Batch Fargate compute environment for running ingestion jobs
        const computeEnv = new batch.FargateComputeEnvironment(this, 'IngestionJobFargateEnv', {
            computeEnvironmentName: `${config.deploymentName}-${config.deploymentStage}-ingestion-job-${hash}`,
            vpc: vpc.vpc,

        });

        // AWS Batch job queue that uses the Fargate compute environment
        const jobQueue = new batch.JobQueue(this, 'IngestionJobQueue', {
            jobQueueName: `${config.deploymentName}-${config.deploymentStage}-ingestion-job-${hash}`,
            computeEnvironments: [
                {
                    computeEnvironment: computeEnv,
                    order: 1,
                },
            ],
        });
        baseEnvironment['LISA_INGESTION_JOB_QUEUE_NAME'] = jobQueue.jobQueueName;

        // Set up build directory for Docker image
        const ingestionImageRoot = path.join(__dirname, 'ingestion-image');
        const buildDirName = 'build';
        const buildDir = path.join(ingestionImageRoot, buildDirName);

        fs.mkdirSync(buildDir, {recursive: true});

        const copyOptions = {
            recursive: true,
            force: true,
            filter: (srcPath: string) => !srcPath.includes('__pycache__')
        };

        // Skip actual copying during tests to avoid file not found errors
        if (process.env.NODE_ENV !== 'test') {
            fs.cpSync(path.join(__dirname, '../../../lambda'), buildDir, copyOptions);
            fs.cpSync(path.join(__dirname, '../../../lisa-sdk/lisapy'), path.join(buildDir, 'lisapy'), copyOptions);
        } else {
            // For tests, we just ensure the directories exist but don't copy files
            const directories = ['repository', 'prompt_templates', 'lisapy'];
            directories.forEach((dir) => {
                const dirPath = path.join(buildDir, dir);
                fs.mkdirSync(dirPath, { recursive: true });

                // Create empty placeholder files to satisfy file existence checks
                if (dir === 'repository') {
                    fs.writeFileSync(path.join(dirPath, 'rag_document_repo.py'), '# Test placeholder');
                }
                if (dir === 'prompt_templates') {
                    fs.writeFileSync(path.join(dirPath, 'models.py'), '# Test placeholder');
                }
            });
        }

        // Build Docker image for batch jobs
        const dockerImageAsset = new DockerImageAsset(this, 'IngestionJobImage', {
            directory: ingestionImageRoot,
            buildArgs: {
                'BUILD_DIR': buildDirName
            },
        });

        // AWS Batch job definition specifying container configuration
        const jobDefinition = new batch.EcsJobDefinition(this, 'IngestionJobDefinition', {
            jobDefinitionName: `${config.deploymentName}-${config.deploymentStage}-ingestion-job-${hash}`,
            container: new batch.EcsFargateContainerDefinition(this, 'IngestionJobContainer', {
                environment: baseEnvironment,
                image: ecs.ContainerImage.fromDockerImageAsset(dockerImageAsset),
                memory: Size.mebibytes(4096),
                cpu: 2,
                command: ['-m', 'repository.pipeline_ingestion', 'Ref::ACTION', 'Ref::DOCUMENT_ID'],
                jobRole: lambdaRole,
                logging: new ecs.AwsLogDriver({
                    streamPrefix: 'batch-job',
                    logGroup: logGroup
                })
            }),
            retryAttempts: 1,
            timeout: Duration.hours(4),
        });
        baseEnvironment['LISA_INGESTION_JOB_DEFINITION_NAME'] = jobDefinition.jobDefinitionName;

        // Grant permissions for submitting batch jobs
        jobDefinition.grantSubmitJob(lambdaRole, jobQueue);
        lambdaRole.addToPrincipalPolicy(new iam.PolicyStatement({
            actions: ['batch:SubmitJob'],
            effect: iam.Effect.ALLOW,
            resources: ['*']
        }));

        // Lambda function for handling scheduled document ingestion
        const handlePipelineIngestScheduleLambda = new lambda.Function(this, 'handlePipelineIngestSchedule', {
            functionName: `${config.deploymentName}-${config.deploymentStage}-ingestion-ingest-schedule-${hash}`,
            runtime: getDefaultRuntime(),
            handler: 'repository.pipeline_ingest_documents.handle_pipline_ingest_schedule',
            code: lambda.Code.fromAsset('./lambda'),
            timeout: Duration.seconds(60),
            memorySize: 256,
            vpc: vpc!.vpc,
            environment: baseEnvironment,
            layers: layers,
            role: lambdaRole
        });
        new StringParameter(this, 'IngestionJobScheduleLambdaArn', {
            parameterName: `${config.deploymentPrefix}/ingestion/ingest/schedule`,
            stringValue: handlePipelineIngestScheduleLambda.functionArn
        });
        handlePipelineIngestScheduleLambda.addPermission('AllowEventBridgeInvoke', {
            principal: new iam.ServicePrincipal('events.amazonaws.com'),
            action: 'lambda:InvokeFunction'
        });

        // Lambda function for handling S3 event-based document ingestion
        const handlePipelineIngestEvent = new lambda.Function(this, 'handlePipelineIngestEvent', {
            functionName: `${config.deploymentName}-${config.deploymentStage}-ingestion-ingest-event-${hash}`,
            runtime: getDefaultRuntime(),
            handler: 'repository.pipeline_ingest_documents.handle_pipeline_ingest_event',
            code: lambda.Code.fromAsset('./lambda'),
            timeout: Duration.seconds(60),
            memorySize: 256,
            vpc: vpc!.vpc,
            environment: baseEnvironment,
            layers: layers,
            role: lambdaRole
        });
        new StringParameter(this, 'IngestionJobEventLambdaArn', {
            parameterName: `${config.deploymentPrefix}/ingestion/ingest/event`,
            stringValue: handlePipelineIngestEvent.functionArn
        });
        handlePipelineIngestEvent.addPermission('AllowEventBridgeInvoke', {
            principal: new iam.ServicePrincipal('events.amazonaws.com'),
            action: 'lambda:InvokeFunction'
        });

        // Lambda function for handling document deletion events
        const handlePipelineDeleteEvent = new lambda.Function(this, 'handlePipelineDeleteEvent', {
            functionName: `${config.deploymentName}-${config.deploymentStage}-ingestion-delete-event-${hash}`,
            runtime: getDefaultRuntime(),
            handler: 'repository.pipeline_delete_documents.handle_pipeline_delete_event',
            code: lambda.Code.fromAsset('./lambda'),
            timeout: Duration.seconds(60),
            memorySize: 256,
            vpc: vpc!.vpc,
            environment: baseEnvironment,
            layers: layers,
            role: lambdaRole
        });
        new StringParameter(this, 'DeletionJobEventLambdaArn', {
            parameterName: `${config.deploymentPrefix}/ingestion/delete/event`,
            stringValue: handlePipelineDeleteEvent.functionArn
        });

        handlePipelineDeleteEvent.addPermission('AllowEventBridgeInvoke', {
            principal: new iam.ServicePrincipal('events.amazonaws.com'),
            action: 'lambda:InvokeFunction'
        });
    }
}
