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
import * as z from 'zod';
import { Construct } from 'constructs';
import { PartialConfigSchema } from '../../../lib/schema';
import { RagRepositoryConfigSchema, RagRepositoryPipeline } from '../../../lib/configSchema';
import { EventField, EventPattern, Rule, RuleTargetInput, Schedule } from 'aws-cdk-lib/aws-events';
import { SfnStateMachine } from 'aws-cdk-lib/aws-events-targets';
import { IStateMachine, StateMachine } from 'aws-cdk-lib/aws-stepfunctions';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Effect, PolicyStatement, Role } from 'aws-cdk-lib/aws-iam';
import { Roles } from '../../../lib/core/iam/roles';
import { createCdkId } from '../../../lib/core/utils';

// Abstract class representing a general pipeline stack
export abstract class PipelineStack extends Stack {
    constructor (scope: Construct, id: string, props: any) {
        super(scope, id, props);
    }

    // Method to create EventBridge rules for triggering state machine executions based on configuration
    createPipelineRules (config: z.infer<typeof PartialConfigSchema>, ragConfig: z.infer<typeof RagRepositoryConfigSchema>) {

        // Retrieve State Machine and IAM Role ARNs from SSM Parameter Store
        const { stateMachine, stateMachineRole } = this.getStateMachine(config, 'Ingest');
        const { stateMachine: deleteStateMachine } = this.getStateMachine(config, 'Delete');
        const lambdaExecutionRole = Role.fromRoleArn(
            this,
            Roles.RAG_LAMBDA_EXECUTION_ROLE,
            StringParameter.valueForStringParameter(
                this,
                `${config.deploymentPrefix}/roles/${createCdkId([config.deploymentName, Roles.RAG_LAMBDA_EXECUTION_ROLE])}`,
            ),
        );
        // Check if pipelines configuration exists
        if (ragConfig.pipelines) {
            ragConfig.pipelines.forEach((pipelineConfig) => {
                // Create S3 policy statement for both functions
                // Grant the state machine role permissions to access specified S3 bucket
                stateMachineRole.addToPrincipalPolicy(new PolicyStatement({
                    effect: Effect.ALLOW,
                    actions: ['s3:GetObject', 's3:ListBucket'],
                    resources: [
                        `arn:${config.partition}:s3:::${pipelineConfig.s3Bucket}`,
                        `arn:${config.partition}:s3:::${pipelineConfig.s3Bucket}/*`
                    ]
                }));

                // Add EventBridge Rules based on pipeline configuration
                // Add EventBridge Rules based on trigger type specified in the pipeline configuration
                switch (pipelineConfig.trigger) {
                    case 'daily': {
                        // Create daily cron trigger with input template
                        // Create a daily scheduled rule
                        this.createDailyRule(ragConfig, stateMachine, pipelineConfig);
                        break;
                    }
                    case 'event': {
                        // Create S3 event trigger with complete event pattern and transform input
                        // Create an event rule triggered by S3 object creation or modification
                        this.createEventRule(ragConfig.repositoryId, stateMachine, pipelineConfig, ['Object Created', 'Object Modified'], 'Ingest');
                        break;
                    }
                    default:
                        // Log warning for unrecognized triggers
                        console.warn(`Unrecognized trigger ${pipelineConfig.trigger}`);
                }

                if (pipelineConfig.autoRemove) {
                    console.log('Creating autodelete rule...');
                    lambdaExecutionRole.addToPrincipalPolicy(new PolicyStatement({
                        effect: Effect.ALLOW,
                        actions: ['s3:GetObject', 's3:ListBucket', 's3:DeleteObject'],
                        resources: [
                            `arn:${config.partition}:s3:::${pipelineConfig.s3Bucket}`,
                            `arn:${config.partition}:s3:::${pipelineConfig.s3Bucket}/*`
                        ]
                    }));
                    this.createEventRule(ragConfig.repositoryId, deleteStateMachine, pipelineConfig, ['Object Deleted'], 'Delete');
                }
            });
        }
    }

    // Method to create an EventBridge rule triggered by S3 events
    private createEventRule (repositoryId:string, stateMachine: IStateMachine, pipelineConfig: z.infer<typeof RagRepositoryPipeline>, eventTypes: string[], eventName: string): Rule {
        const detail: any = {
            bucket: {
                name: [pipelineConfig.s3Bucket]
            }
        };

        // Add prefix filter if specified and not root
        // Add object key prefix filter if specified in the configuration
        if (pipelineConfig.s3Prefix && pipelineConfig.s3Prefix !== '/') {
            detail.object = {
                key: [{
                    prefix: pipelineConfig.s3Prefix
                }]
            };
        }

        // Define event pattern for S3 Object Created and Modified events
        const eventPattern: EventPattern = {
            source: ['aws.s3'],
            detailType: eventTypes,
            detail
        };

        // Create a new EventBridge rule for the S3 event pattern
        const ruleName = `${repositoryId}-S3Event${eventName}Rule`;
        return new Rule(this, ruleName, {
            eventPattern,
            // Define the state machine target with input transformation
            targets: [new SfnStateMachine(stateMachine, {
                input: RuleTargetInput.fromObject({
                    'detail-type': EventField.detailType,
                    source: EventField.source,
                    time: EventField.time,
                    region: EventField.region,
                    detail: {
                        repositoryId,
                        bucket: pipelineConfig.s3Bucket,
                        prefix: pipelineConfig.s3Prefix,
                        object: {
                            key: EventField.fromPath('$.detail.object.key')
                        },
                        trigger: 'event',
                        pipelineConfig
                    }
                })
            })]
        });
    }

    // Method to create a daily scheduled EventBridge rule
    private createDailyRule (ragConfig: z.infer<typeof RagRepositoryConfigSchema>, stateMachine: IStateMachine, pipelineConfig: z.infer<typeof RagRepositoryPipeline>): Rule {
        return new Rule(this, 'DailyIngestRule', {
            // Schedule the rule to run daily at midnight
            schedule: Schedule.cron({
                minute: '0',
                hour: '0'
            }),
            // Define the state machine target with a specific input configuration
            targets: [new SfnStateMachine(stateMachine, {
                input: RuleTargetInput.fromObject({
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

    private getStateMachine (config: z.infer<typeof PartialConfigSchema>, resource: string){
        // Retrieve State Machine and IAM Role ARNs from SSM Parameter Store
        console.log(`looking for ${config.deploymentPrefix}/${resource}PipelineStateMachineArn`);
        const stateMachine = StateMachine.fromStateMachineArn(this, `${resource}PipelineStateMachine`, StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/${resource}PipelineStateMachineArn`));
        const stateMachineRole = Role.fromRoleArn(this, `${resource}PipelineRoleArn`, StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/${resource}PipelineRoleArn`));
        return {stateMachine, stateMachineRole};
    }
}
