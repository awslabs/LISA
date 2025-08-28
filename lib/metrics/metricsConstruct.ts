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

import { IAuthorizer, RestApi } from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import { IRole, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { ISecurityGroup } from 'aws-cdk-lib/aws-ec2';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { LayerVersion } from 'aws-cdk-lib/aws-lambda';
import { SqsEventSource } from 'aws-cdk-lib/aws-lambda-event-sources';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { StringParameter } from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import * as path from 'path';

import { getDefaultRuntime, PythonLambdaFunction, registerAPIEndpoint } from '../api-base/utils';
import { BaseProps } from '../schema';
import { createLambdaRole } from '../core/utils';
import { Vpc } from '../networking/vpc';
import { LAMBDA_PATH } from '../util';
import { Duration } from 'aws-cdk-lib';

/**
 * Properties for MetricsApi Construct.
 */
type MetricsApiProps = {
    authorizer: IAuthorizer;
    restApiId: string;
    rootResourceId: string;
    securityGroups: ISecurityGroup[];
    vpc: Vpc;
} & BaseProps;

/**
 * API which manages usage metrics in DynamoDB
 */
export class MetricsConstruct extends Construct {

    constructor (scope: Construct, id: string, props: MetricsApiProps) {
        super(scope, id);

        const { authorizer, config, restApiId, rootResourceId, securityGroups, vpc } = props;

        // Get common layer based on arn from SSM due to issues with cross stack references
        const commonLambdaLayer = LayerVersion.fromLayerVersionArn(
            this,
            'metrics-common-lambda-layer',
            StringParameter.valueForStringParameter(this, `${config.deploymentPrefix}/layerVersion/common`),
        );

        // Create Usage Metrics table
        const usageMetricsTable = new dynamodb.Table(this, 'UsageMetricsTable', {
            partitionKey: {
                name: 'userId',
                type: dynamodb.AttributeType.STRING,
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
        });

        // Store table name in SSM for cross-stack access
        new StringParameter(this, 'UsageMetricsTableNameParameter', {
            parameterName: `${config.deploymentPrefix}/table/usage-metrics`,
            stringValue: usageMetricsTable.tableName,
        });

        // Create SQS Queue for metrics processing
        const usageMetricsQueue = new sqs.Queue(this, 'UsageMetricsQueue', {
            visibilityTimeout: Duration.minutes(2),
            retentionPeriod: Duration.days(14),
        });

        // Store queue name in SSM for cross-stack access
        new StringParameter(this, 'UsageMetricsQueueName', {
            parameterName: `${config.deploymentPrefix}/queue-name/usage-metrics`,
            stringValue: usageMetricsQueue.queueName,
        });

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        // Create CloudWatch Dashboard for usage metrics
        const dashboard = new cloudwatch.Dashboard(this, 'UsageMetricsDashboard', {
            dashboardName: 'LISA-Metrics',
            start: '-P7D',
        });

        dashboard.addWidgets(
            // Dashboard Title
            new cloudwatch.TextWidget({
                markdown: '# LISA Metrics Dashboard',
                width: 24,
                height: 1,
            }),
            // Total Prompts Widget
            new cloudwatch.GraphWidget({
                title: 'Total Prompts',
                left: [
                    new cloudwatch.Metric({
                        namespace: 'LISA/UsageMetrics',
                        metricName: 'TotalPromptCount',
                        statistic: 'Sum',
                        period: Duration.hours(1),
                    }),
                ],
                width: 12,
                height: 6,
            }),
            // Total RAG Usage Widget
            new cloudwatch.GraphWidget({
                title: 'Total RAG Usage',
                left: [
                    new cloudwatch.Metric({
                        namespace: 'LISA/UsageMetrics',
                        metricName: 'RAGUsageCount',
                        statistic: 'Sum',
                        period: Duration.hours(1),
                    }),
                ],
                width: 12,
                height: 6,
            }),
            // Total MCP Tool Calls Widget
            new cloudwatch.GraphWidget({
                title: 'Total MCP Tool Calls',
                left: [
                    new cloudwatch.Metric({
                        namespace: 'LISA/UsageMetrics',
                        metricName: 'TotalMCPToolCalls',
                        statistic: 'Sum',
                        period: Duration.hours(1),
                    }),
                ],
                width: 12,
                height: 6,
            }),
            // Prompts by User Widget
            new cloudwatch.GraphWidget({
                title: 'Prompts by User',
                left: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{LISA/UsageMetrics,UserId} MetricName="UserPromptCount"\', \'Sum\', 3600)',
                        label: '',
                        period: Duration.hours(1),
                    }),
                ],
                width: 12,
                height: 6,
            }),
            // RAG Usage by User Widget
            new cloudwatch.GraphWidget({
                title: 'RAG Usage by User',
                left: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{LISA/UsageMetrics,UserId} MetricName="UserRAGUsageCount"\', \'Sum\', 3600)',
                        label: '',
                        period: Duration.hours(1),
                    }),
                ],
                width: 12,
                height: 6,
            }),
            // MCP Tool Calls by User Widget
            new cloudwatch.GraphWidget({
                title: 'MCP Tool Calls by User',
                left: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{LISA/UsageMetrics,UserId} MetricName="UserMCPToolCalls"\', \'Sum\', 3600)',
                        label: '',
                        period: Duration.hours(1),
                    }),
                ],
                width: 12,
                height: 6,
            }),
            // MCP Tool Calls by Tool Widget
            new cloudwatch.GraphWidget({
                title: 'MCP Tool Calls by Tool',
                left: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{LISA/UsageMetrics,ToolName} MetricName="MCPToolCallsByTool"\', \'Sum\', 3600)',
                        label: '',
                        period: Duration.hours(1),
                    }),
                ],
                width: 12,
                height: 6,
            }),
            // Unique Users Widget
            new cloudwatch.SingleValueWidget({
                title: 'Total User Count',
                metrics: [
                    new cloudwatch.Metric({
                        namespace: 'LISA/UsageMetrics',
                        metricName: 'UniqueUsers',
                        statistic: 'Maximum',
                        period: Duration.days(1),
                    }),
                ],
                width: 12,
                height: 6,
            }),
            // Users by Group Widget
            new cloudwatch.GraphWidget({
                title: 'Groups by Membership Count',
                left: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{LISA/UsageMetrics,GroupName} MetricName="UsersPerGroup"\', \'Maximum\', 86400)',
                        label: '',
                        period: Duration.days(1),
                    }),
                ],
                view: cloudwatch.GraphWidgetView.PIE,
                width: 12,
                height: 6,
            }),
            // Group Prompt Counts Widget
            new cloudwatch.GraphWidget({
                title: 'Group Prompt Counts',
                left: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{LISA/UsageMetrics,GroupName} MetricName="GroupPromptCount"\', \'Sum\', 3600)',
                        label: '',
                        period: Duration.hours(1),
                    }),
                ],
                width: 12,
                height: 6,
            }),
            // Group RAG Usage Widget
            new cloudwatch.GraphWidget({
                title: 'Group RAG Usage',
                left: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{LISA/UsageMetrics,GroupName} MetricName="GroupRAGUsageCount"\', \'Sum\', 3600)',
                        label: '',
                        period: Duration.hours(1),
                    }),
                ],
                width: 12,
                height: 6,
            }),
            // Group MCP Usage Widget
            new cloudwatch.GraphWidget({
                title: 'Group MCP Usage',
                left: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{LISA/UsageMetrics,GroupName} MetricName="GroupMCPToolCalls"\', \'Sum\', 3600)',
                        label: '',
                        period: Duration.hours(1),
                    }),
                ],
                width: 12,
                height: 6,
            }),
        );

        const env = {
            USAGE_METRICS_TABLE_NAME: usageMetricsTable.tableName
        };

        // Create metrics API endpoints
        const metricsApis: PythonLambdaFunction[] = [
            {
                name: 'get_user_metrics',
                resource: 'metrics',
                description: 'Gets metrics for a specific user',
                path: 'metrics/users/{userId}',
                method: 'GET',
                environment: env,
            },
            {
                name: 'get_user_metrics_all',
                resource: 'metrics',
                description: 'Gets aggregated metrics across all users',
                path: 'metrics/users/all',
                method: 'GET',
                environment: env,
            },
        ];

        const lambdaRole: IRole = createLambdaRole(this, config.deploymentName, 'LisaMetricsApiLambdaExecutionRole', usageMetricsTable.tableArn, config.roles?.LambdaExecutionRole);

        lambdaRole.addToPrincipalPolicy(new PolicyStatement({
            actions: ['cloudwatch:PutMetricData'],
            resources: ['*']
        }));

        const lambdaPath = config.lambdaPath || LAMBDA_PATH;
        metricsApis.forEach((f) => {
            registerAPIEndpoint(
                this,
                restApi,
                lambdaPath,
                [commonLambdaLayer],
                f,
                getDefaultRuntime(),
                vpc,
                securityGroups,
                authorizer,
                lambdaRole,
            );
        });

        // Scheduled metrics Lambda to count unique users and group membership daily
        const scheduledMetricsLambda = new lambda.Function(this, 'DailyMetricsLambda', {
            runtime: getDefaultRuntime(),
            code: lambda.Code.fromAsset(path.join(lambdaPath)),
            handler: 'metrics/lambda_functions.daily_metrics_handler',
            environment: env,
            vpc: vpc.vpc,
            securityGroups: securityGroups,
            timeout: Duration.minutes(2),
            role: lambdaRole,
            layers: [commonLambdaLayer],
        });

        // EventBridge rule to trigger the UniqueUsersMetric lambda daily
        new events.Rule(this, 'DailyMetricsLambdaEventRule', {
            schedule: events.Schedule.rate(Duration.days(1)),
            targets: [new targets.LambdaFunction(scheduledMetricsLambda)],
        });

        // Create Lambda function for processing SQS events
        const metricsProcessorLambda = new lambda.Function(this, 'UsageMetricsProcessor', {
            runtime: getDefaultRuntime(),
            code: lambda.Code.fromAsset(path.join(lambdaPath)),
            handler: 'metrics.lambda_functions.process_metrics_sqs_event',
            environment: env,
            vpc: vpc.vpc,
            securityGroups: securityGroups,
            timeout: Duration.minutes(2),
            role: lambdaRole,
            layers: [commonLambdaLayer],
        });

        // Add SQS event source to the Lambda function
        metricsProcessorLambda.addEventSource(new SqsEventSource(usageMetricsQueue, {
            batchSize: 10,
        }));

        // Grant SQS permissions to the Lambda role
        usageMetricsQueue.grantConsumeMessages(metricsProcessorLambda);
    }
}
