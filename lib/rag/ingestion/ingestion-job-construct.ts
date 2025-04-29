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

export type IngestionJobConstructProps = StackProps & BaseProps & {
    vpc: Vpc,
    lambdaRole: iam.IRole,
    baseEnvironment:  Record<string, string>,
    layers?: ILayerVersion[];
    ragDocumentTable: dynamodb.ITable;
    ragSubDocumentTable: dynamodb.ITable;
};

export class IngestionJobConstruct extends Construct {
    constructor (scope: Construct, id: string, props: IngestionJobConstructProps) {
        super(scope, id);

        const {config, vpc, lambdaRole, layers, baseEnvironment} = props;
        // Create DynamoDB table with uuid hash key and date sort key
        const ingestionJobTable = new dynamodb.Table(this, 'IngestionJobTable', {
            partitionKey: {
                name: 'id',
                type: dynamodb.AttributeType.STRING
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            removalPolicy: config.removalPolicy
        });
        ingestionJobTable.grantReadWriteData(props.lambdaRole);
        baseEnvironment['LISA_INGESTION_JOB_TABLE_NAME'] = ingestionJobTable.tableName;

        ingestionJobTable.addGlobalSecondaryIndex({
            indexName: 'createdAt',
            partitionKey: {
                name: 'id',
                type: dynamodb.AttributeType.STRING
            },
            sortKey: {
                name: 'created_date',
                type: dynamodb.AttributeType.STRING
            },
            projectionType: dynamodb.ProjectionType.ALL
        });

        ingestionJobTable.addGlobalSecondaryIndex({
            indexName: 's3Path',
            partitionKey: {
                name: 's3_path',
                type: dynamodb.AttributeType.STRING
            },
            projectionType: dynamodb.ProjectionType.ALL
        });

        ingestionJobTable.addGlobalSecondaryIndex({
            indexName: 'documentId',
            partitionKey: {
                name: 'document_id',
                type: dynamodb.AttributeType.STRING
            },
            projectionType: dynamodb.ProjectionType.ALL
        });

        // Log group for container logs
        const logGroup = new logs.LogGroup(this, 'IngestionJobLogGroup', {
            retention: logs.RetentionDays.ONE_WEEK,
        });

        // Compute environment (Fargate)
        const computeEnv = new batch.FargateComputeEnvironment(this, 'IngestionJobFargateEnv', {
            computeEnvironmentName: 'IngestionJobMyFargateEnv',
            vpc: vpc.vpc,

        });

        // Job queue
        const jobQueue = new batch.JobQueue(this, 'IngestionJobQueue', {
            computeEnvironments: [
                {
                    computeEnvironment: computeEnv,
                    order: 1,
                },
            ],
        });
        baseEnvironment['LISA_INGESTION_JOB_QUEUE_NAME'] = jobQueue.jobQueueName;

        // fs.rmdirSync(path.join(__dirname, 'ingestion-image/build'), {recursive: true});
        fs.mkdirSync(path.join(__dirname, 'ingestion-image/build'));
        fs.cpSync(path.join(__dirname, '../../../lambda'), path.join(__dirname, 'ingestion-image/build'), {recursive: true, force: true});
        fs.cpSync(path.join(__dirname, '../../../lisa-sdk/lisapy'), path.join(__dirname, 'ingestion-image/build/lisapy'), {recursive: true, force: true});

        // ✅ Build Docker image from local directory
        const dockerImageAsset = new DockerImageAsset(this, 'IngestionJobImage', {
            directory: path.join(__dirname, 'ingestion-image'),
        });

        fs.rmdirSync(path.join(__dirname, 'ingestion-image/build'), {recursive: true});

        // Create a container job definition
        const jobDefinition = new batch.EcsJobDefinition(this, 'IngestionJobDefinition', {
            container: new batch.EcsFargateContainerDefinition(this, 'IngestionJobContainer', {
                environment: baseEnvironment,
                // environment: {...baseEnvironment, 'PYTHONPATH': '/workdir/lambda;/workdir/lisa-sdk'},
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
        jobDefinition.grantSubmitJob(lambdaRole, jobQueue);
        lambdaRole.addToPrincipalPolicy(new iam.PolicyStatement({
            actions: ['batch:SubmitJob'],
            effect: iam.Effect.ALLOW,
            resources: ['*']
        }));

        // function to ingest documents on a schedule
        const handlePipelineIngestScheduleLambda = new lambda.Function(this, 'handlePipelineIngestSchedule', {
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

        // function to ingest documents on s3 events
        const handlePipelineIngestEvent = new lambda.Function(this, 'handlePipelineIngestEvent', {
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

        // function to ingest documents on s3 events
        const handlePipelineDeleteScheduleEvent = new lambda.Function(this, 'handlePipelineDeleteEvent', {
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
            stringValue: handlePipelineDeleteScheduleEvent.functionArn
        });
    }
}
