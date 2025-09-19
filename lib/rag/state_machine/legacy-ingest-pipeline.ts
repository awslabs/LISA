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

import { Construct } from 'constructs';
import { BaseProps } from '../../schema';
import { ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { Effect, PolicyStatement, Role } from 'aws-cdk-lib/aws-iam';
import { Vpc } from '../../networking/vpc';
import { EventField, EventPattern, Rule, RuleTargetInput, Schedule } from 'aws-cdk-lib/aws-events';
import { LambdaFunction } from 'aws-cdk-lib/aws-events-targets';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { PipelineConfig, RagRepositoryType, RdsConfig } from '../../schema';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Roles } from '../../core/iam/roles';
import { createCdkId } from '../../core/utils';
import * as crypto from 'crypto';

type IngestPipelineStateMachineProps = BaseProps & {
    vpc?: Vpc;
    pipelineConfig: PipelineConfig;
    rdsConfig?: RdsConfig;
    repositoryId: string;
    type: RagRepositoryType;
    registeredRepositoriesParamName: string;
    ragDocumentTable: ITable;
    ragSubDocumentTable: ITable;
};

/**
 * State Machine for creating models.
 */
export class LegacyIngestPipelineStateMachine extends Construct {
    readonly stateMachineArn: string;

    constructor (scope: Construct, id: string, props: IngestPipelineStateMachineProps) {
        super(scope, id);

        const { config, pipelineConfig, repositoryId, ragDocumentTable, ragSubDocumentTable } = props;

        const hash = crypto.randomBytes(6).toString('hex');

        const bucketActions = ['s3:GetObject'];

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
        const policyStatements = [dynamoPolicyStatement];

        // Get the Lambda execution role from SSM parameter
        const lambdaExecutionRole = Role.fromRoleArn(
            this,
            createCdkId([Roles.RAG_LAMBDA_EXECUTION_ROLE, hash]),
            StringParameter.valueForStringParameter(
                this,
                `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        // Create IAM certificate policy if certificate ARN is provided
        if (config.restApiConfig.sslCertIamArn) {
            policyStatements.push(new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['iam:GetServerCertificate'],
                resources: [config.restApiConfig.sslCertIamArn]
            }));
        }

        // Add EventBridge Rules based on pipeline configuration
        if (pipelineConfig.trigger === 'daily') {
            const ingestionLambdaArn = StringParameter.fromStringParameterName(this, createCdkId(['IngestionScheduleLambdaStringParameter', hash]), `${config.deploymentPrefix}/ingestion/ingest/schedule`);
            const ingestionLambda = lambda.Function.fromFunctionArn(this, createCdkId(['IngestionScheduleLambda', hash]), ingestionLambdaArn.stringValue);

            // Create daily cron trigger with input template
            const dailyRule = new Rule(this, createCdkId(['DailyIngestRule', hash]), {
                ruleName: `${config.deploymentName}-${config.deploymentStage}-LegacyDailyIngestRule-${hash}`,
                schedule: Schedule.cron({
                    minute: '0',
                    hour: '0'
                }),
                targets: [new LambdaFunction(ingestionLambda, {
                    event: RuleTargetInput.fromObject({
                        version: '0',
                        id: EventField.eventId,
                        'detail-type': 'Scheduled Event',
                        source: 'aws.events',
                        time: EventField.time,
                        region: EventField.region,
                        detail: {
                            repositoryId,
                            bucket: pipelineConfig.s3Bucket,
                            prefix: pipelineConfig.s3Prefix,
                            trigger: 'daily',
                            pipelineConfig
                        }
                    })
                })]
            });

            // Ensure rule is created after Lambda function parameter is available
            dailyRule.node.addDependency(ingestionLambdaArn);
        } else if (pipelineConfig.trigger === 'event') {
            const ingestionLambdaArn = StringParameter.fromStringParameterName(this, createCdkId(['IngestionChangeEventLambdaStringParameter', hash]), `${config.deploymentPrefix}/ingestion/ingest/event`);

            const ingestionLambda = lambda.Function.fromFunctionArn(this, createCdkId(['IngestionIngestEventLambda', hash]), ingestionLambdaArn.stringValue);

            // Create S3 event trigger with complete event pattern and transform input
            const detail: any = {
                bucket: {
                    name: [pipelineConfig.s3Bucket]
                }
            };

            // Add prefix filter if specified and not root
            if (pipelineConfig.s3Prefix !== '') {
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

            const s3EventRule = new Rule(this, createCdkId(['S3EventIngestRule', hash]), {
                ruleName: `${config.deploymentName}-${config.deploymentStage}-LegacyS3EventIngestRule-${hash}}`,
                eventPattern,
                targets: [new LambdaFunction(ingestionLambda, {
                    event: RuleTargetInput.fromObject({
                        version: '0',
                        id: EventField.eventId,
                        'detail-type': EventField.detailType,
                        source: EventField.source,
                        time: EventField.time,
                        region: EventField.region,
                        detail: {
                            repositoryId,
                            bucket: pipelineConfig.s3Bucket,
                            prefix: pipelineConfig.s3Prefix,
                            key: EventField.fromPath('$.detail.object.key'),
                            trigger: 'event',
                            pipelineConfig,
                        }
                    })
                })]
            });

            // Ensure rule is created after Lambda function parameter is available
            s3EventRule.node.addDependency(ingestionLambdaArn);
        }

        if (pipelineConfig.autoRemove) {
            const deletionLambdaArn = StringParameter.fromStringParameterName(this, createCdkId(['IngestionDeleteEventLambdaStringParameter', hash]), `${config.deploymentPrefix}/ingestion/delete/event`);

            const deletionLambda = lambda.Function.fromFunctionArn(this, createCdkId(['IngestionDeleteEventLambda', hash]), deletionLambdaArn.stringValue);
            console.log('Creating autodelete rule...');

            bucketActions.push('s3:DeleteObject');

            // Grant the execution role permissions to list contents of the S3 bucket
            lambdaExecutionRole.addToPrincipalPolicy(new PolicyStatement({
                effect: Effect.ALLOW,
                actions: ['s3:ListBucket'],
                resources: [
                    `arn:${config.partition}:s3:::${pipelineConfig.s3Bucket}`,
                ]
            }));

            // Create S3 event trigger with complete event pattern and transform input
            const detail: any = {
                bucket: {
                    name: [pipelineConfig.s3Bucket]
                }
            };

            // Add prefix filter if specified and not root
            if (pipelineConfig.s3Prefix !== '') {
                detail.object = {
                    key: [{
                        prefix: pipelineConfig.s3Prefix
                    }]
                };
            }

            const eventPattern: EventPattern = {
                source: ['aws.s3'],
                detailType: ['Object Deleted'],
                detail
            };

            const s3DeleteRule = new Rule(this, createCdkId(['S3EventDeleteRule', hash]), {
                ruleName: `${config.deploymentName}-${config.deploymentStage}-LegacyS3EventDeleteRule-${hash}`,
                eventPattern,
                targets: [new LambdaFunction(deletionLambda, {
                    event: RuleTargetInput.fromObject({
                        version: '0',
                        id: EventField.eventId,
                        'detail-type': EventField.detailType,
                        source: EventField.source,
                        time: EventField.time,
                        region: EventField.region,
                        detail: {
                            repositoryId,
                            bucket: pipelineConfig.s3Bucket,
                            prefix: pipelineConfig.s3Prefix,
                            key: EventField.fromPath('$.detail.object.key'),
                            trigger: 'event',
                            pipelineConfig,
                        }
                    })
                })]
            });

            // Ensure rule is created after Lambda function parameter is available
            s3DeleteRule.node.addDependency(deletionLambdaArn);
        }

        // Grant the execution role permissions to access specified S3 bucket/prefix
        lambdaExecutionRole.addToPrincipalPolicy(new PolicyStatement({
            effect: Effect.ALLOW,
            actions: bucketActions,
            resources: [
                `arn:${config.partition}:s3:::${pipelineConfig.s3Bucket}/${pipelineConfig.s3Prefix}*`
            ]
        }));
    }
}
