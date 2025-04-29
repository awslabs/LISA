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
import * as cdk from 'aws-cdk-lib';
import { BaseProps } from '../../schema';
import { ILayerVersion } from 'aws-cdk-lib/aws-lambda';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Vpc } from '../../networking/vpc';
import { EventField, EventPattern, Rule, RuleTargetInput, Schedule } from 'aws-cdk-lib/aws-events';
import { LambdaFunction } from 'aws-cdk-lib/aws-events-targets';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { PipelineConfig, RagRepositoryType, RdsConfig } from '../../schema';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import * as lambda from 'aws-cdk-lib/aws-lambda';

type IngestPipelineStateMachineProps = BaseProps & {
    vpc?: Vpc;
    pipelineConfig: PipelineConfig;
    rdsConfig?: RdsConfig;
    repositoryId: string;
    type: RagRepositoryType;
    layers?: ILayerVersion[];
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

        // Add EventBridge Rules based on pipeline configuration
        if (pipelineConfig.trigger === 'daily') {
            const ingestionLambdaArn = StringParameter.fromStringParameterName(this, 'IngestionScheduleLambdaStringParameter', `${config.deploymentPrefix}/ingestion/ingest/schedule`);
            const ingestionLambda = lambda.Function.fromFunctionArn(this, 'IngestionScheduleLambda', ingestionLambdaArn.stringValue);

            // Create daily cron trigger with input template
            new Rule(this, 'DailyIngestRule', {
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
        } else if (pipelineConfig.trigger === 'event') {
            const ingestionLambdaArn = StringParameter.fromStringParameterName(this, 'IngestionChangeEventLambdaStringParameter', `${config.deploymentPrefix}/ingestion/ingest/event`);
            const ingestionLambda = lambda.Function.fromFunctionArn(this, 'IngestionIngestEventLambda', ingestionLambdaArn.stringValue);

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

            new Rule(this, 'S3EventIngestRule', {
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
        }
    }
}
