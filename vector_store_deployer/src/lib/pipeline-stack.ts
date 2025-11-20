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
import { Stack } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { PipelineConfig, RagRepositoryConfig, PartialConfig } from '../../../lib/schema';
import { EventField, EventPattern, Rule, RuleTargetInput, Schedule } from 'aws-cdk-lib/aws-events';
import { LambdaFunction } from 'aws-cdk-lib/aws-events-targets';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Effect, PolicyStatement, Role } from 'aws-cdk-lib/aws-iam';
import { Roles } from '../../../lib/core/iam/roles';
import { createCdkId } from '../../../lib/core/utils';
import { IFunction } from 'aws-cdk-lib/aws-lambda';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as crypto from 'crypto';

/**
 * Abstract base class for pipeline infrastructure stacks
 * Provides common functionality for setting up event-driven and scheduled pipelines
 */
export abstract class PipelineStack extends Stack {
    constructor (scope: Construct, id: string, props: any) {
        super(scope, id, props);
    }

    /**
     * Creates EventBridge rules for pipeline triggers based on configuration
     * Supports both event-based (S3 events) and scheduled (daily) triggers
     */
    createPipelineRules (config: PartialConfig, ragConfig: RagRepositoryConfig) {
        // Get the Lambda execution role from SSM parameter
        const lambdaExecutionRole = Role.fromRoleArn(
            this,
            Roles.RAG_LAMBDA_EXECUTION_ROLE,
            StringParameter.valueForStringParameter(
                this,
                `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );

        // setup EventBridge Rules for any pipelines
        // Process each pipeline configuration
        ragConfig.pipelines?.forEach((pipelineConfig, index) => {
            const bucketActions = ['s3:GetObject'];
            const hash = crypto.randomBytes(6).toString('hex');

            // Add EventBridge Rules based on trigger type specified in the pipeline configuration
            // Create rules based on trigger type
            switch (pipelineConfig.trigger) {
                case 'daily': {
                    const paramName = `${config.deploymentPrefix}/ingestion/ingest/schedule`;
                    const ingestionLambdaArn = StringParameter.valueForStringParameter(this, paramName);
                    const ingestionLambda = lambda.Function.fromFunctionArn(this, `IngestionScheduleLambda-${index}`, ingestionLambdaArn);
                    this.createDailyLambdaRule(config, ingestionLambda, ragConfig, pipelineConfig, hash);
                    break;
                }
                case 'event': {
                    const paramName = `${config.deploymentPrefix}/ingestion/ingest/event`;
                    const ingestionLambdaArn = StringParameter.valueForStringParameter(this, paramName);
                    const ingestionLambda = lambda.Function.fromFunctionArn(this, `IngestionIngestEventLambda-${index}`, ingestionLambdaArn);
                    this.createEventLambdaRule(config, ingestionLambda, ragConfig.repositoryId, pipelineConfig, ['Object Created', 'Object Modified'], 'Ingest', hash);
                    break;
                }
                default:
                    // Log warning for unrecognized triggers
                    console.warn(`Unrecognized trigger ${pipelineConfig.trigger}`);
            }

            // Add EventBridge Rule for when objects are removed from S3
            // Setup auto-removal of objects if enabled
            if (pipelineConfig.autoRemove) {
                const paramName = `${config.deploymentPrefix}/ingestion/delete/event`;
                const deletionLambdaArn = StringParameter.valueForStringParameter(this, paramName);
                const deletionLambda = lambda.Function.fromFunctionArn(this, `IngestionDeleteEventLambda-${index}`, deletionLambdaArn);
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

                this.createEventLambdaRule(config, deletionLambda, ragConfig.repositoryId, pipelineConfig, ['Object Deleted'], 'Delete', hash);
            }

            // Grant the execution role permissions to access specified S3 bucket/prefix
            lambdaExecutionRole.addToPrincipalPolicy(new PolicyStatement({
                effect: Effect.ALLOW,
                actions: bucketActions,
                resources: [
                    `arn:${config.partition}:s3:::${pipelineConfig.s3Bucket}/${pipelineConfig.s3Prefix}*`
                ]
            }));
        });
    }

    /**
     * Creates an EventBridge rule for S3 event-based triggers
     */
    private createEventLambdaRule (config: PartialConfig, ingestionLambda: IFunction, repositoryId: string, pipelineConfig: PipelineConfig, eventTypes: string[], eventName: string, disambiguator: string): Rule {
        const detail: any = {
            bucket: {
                name: [pipelineConfig.s3Bucket]
            }
        };

        // Add prefix filter if specified and not root
        // Add object key prefix filter if specified in the configuration
        // Add prefix filter if not root
        if (pipelineConfig.s3Prefix !== '') {
            detail.object = {
                key: [
                    {
                        prefix: pipelineConfig.s3Prefix
                    },
                    {
                        // Exclude metadata files from triggering events
                        'anything-but': {
                            suffix: '.metadata.json'
                        }
                    }
                ]
            };
        } else {
            // No prefix, but still exclude metadata files
            detail.object = {
                key: [
                    {
                        'anything-but': {
                            suffix: '.metadata.json'
                        }
                    }
                ]
            };
        }

        // Define event pattern for S3 Object Created and Modified events
        const eventPattern: EventPattern = {
            source: ['aws.s3'],
            detailType: eventTypes,
            detail
        };

        const collectionName = `${repositoryId}-${pipelineConfig.collectionId ?? pipelineConfig.embeddingModel}`;
        // Create a new EventBridge rule for the S3 event pattern
        return new Rule(this, `${repositoryId}-S3Event${eventName}Rule-${disambiguator}`, {
            ruleName: `${config.deploymentName}-${config.deploymentStage}-${config.appName}-${collectionName}-S3${eventName}Rule-${disambiguator}`.substring(0,127),
            eventPattern,
            // Define the state machine target with input transformation
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
    }

    /**
     * Creates an EventBridge rule for daily scheduled triggers
     */
    private createDailyLambdaRule (config: PartialConfig, ingestionLambda: IFunction, ragConfig: RagRepositoryConfig, pipelineConfig: PipelineConfig, disambiguator: string): Rule {
        return new Rule(this, `${ragConfig.repositoryId}-S3DailyIngestRule-${disambiguator}`, {
            ruleName: `${config.deploymentName}-${config.deploymentStage}-DailyIngestRule-${disambiguator}`,
            // Schedule the rule to run daily at midnight
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
                        repositoryId: ragConfig.repositoryId,
                        bucket: pipelineConfig.s3Bucket,
                        prefix: pipelineConfig.s3Prefix,
                        trigger: 'daily',
                        pipelineConfig
                    }
                })
            })]
        });
    }
}
