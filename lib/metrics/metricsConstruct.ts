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
 * API which manages user metrics in DynamoDB
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

        // Create User Metrics table
        const userMetricsTable = new dynamodb.Table(this, 'UserMetricsTable', {
            partitionKey: {
                name: 'userId',
                type: dynamodb.AttributeType.STRING,
            },
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption: dynamodb.TableEncryption.AWS_MANAGED,
            removalPolicy: config.removalPolicy,
        });

        // Store table name in SSM for cross-stack access
        new StringParameter(this, 'UserMetricsTableNameParameter', {
            parameterName: `${config.deploymentPrefix}/table/user-metrics`,
            stringValue: userMetricsTable.tableName,
        });

        // Create SQS Queue for metrics processing
        const metricsQueue = new sqs.Queue(this, 'UserMetricsQueue', {
            visibilityTimeout: Duration.minutes(2),
            retentionPeriod: Duration.days(14),
        });

        // Store queue name and in SSM for cross-stack access
        new StringParameter(this, 'UserMetricsQueueName', {
            parameterName: `${config.deploymentPrefix}/queue-name/user-metrics`,
            stringValue: metricsQueue.queueName,
        });

        const restApi = RestApi.fromRestApiAttributes(this, 'RestApi', {
            restApiId: restApiId,
            rootResourceId: rootResourceId,
        });

        // Create CloudWatch Dashboard for user metrics
        const dashboard = new cloudwatch.Dashboard(this, 'UserMetricsDashboard', {
            dashboardName: 'LISA-User-Metrics',
            start: '-P7D',
        });

        dashboard.addWidgets(
            // Dashboard Title
            new cloudwatch.TextWidget({
                markdown: '# LISA User Metrics Dashboard',
                width: 24,
                height: 1,
            }),
            // Total Prompts Widget
            new cloudwatch.GraphWidget({
                title: 'Total Prompts',
                left: [
                    new cloudwatch.Metric({
                        namespace: 'LISA/UserMetrics',
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
                        namespace: 'LISA/UserMetrics',
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
                        namespace: 'LISA/UserMetrics',
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
                        expression: 'SEARCH(\'{LISA/UserMetrics,UserId} MetricName="UserPromptCount"\', \'Sum\', 3600)',
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
                        expression: 'SEARCH(\'{LISA/UserMetrics,UserId} MetricName="UserRAGUsageCount"\', \'Sum\', 3600)',
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
                        expression: 'SEARCH(\'{LISA/UserMetrics,UserId} MetricName="UserMCPToolCalls"\', \'Sum\', 3600)',
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
                        expression: 'SEARCH(\'{LISA/UserMetrics,ToolName} MetricName="MCPToolCallsByTool"\', \'Sum\', 3600)',
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
                        namespace: 'LISA/UserMetrics',
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
                        expression: 'SEARCH(\'{LISA/UserMetrics,GroupName} MetricName="UsersPerGroup"\', \'Maximum\', 86400)',
                        label: '',
                        period: Duration.days(1),
                    }),
                ],
                view: cloudwatch.GraphWidgetView.PIE,
                width: 12,
                height: 6,
            }),
        );

        const env = {
            USER_METRICS_TABLE_NAME: userMetricsTable.tableName
        };

        // Create metrics API endpoints
        const metricsApis: PythonLambdaFunction[] = [
            {
                name: 'get_user_metrics',
                resource: 'metrics',
                description: 'Gets metrics for a specific user',
                path: 'metrics/user/{userId}',
                method: 'GET',
                environment: env,
            },
            {
                name: 'get_global_metrics',
                resource: 'metrics',
                description: 'Gets aggregated metrics across all users',
                path: 'metrics/global',
                method: 'GET',
                environment: env,
            },
            {
                name: 'update_user_metrics',
                resource: 'metrics',
                description: 'Updates metrics for a specific user',
                path: 'metrics/user/{userId}',
                method: 'PUT',
                environment: env,
            },
        ];

        const lambdaRole: IRole = createLambdaRole(this, config.deploymentName, 'LisaMetricsApiLambdaExecutionRole', userMetricsTable.tableArn, config.roles?.LambdaExecutionRole);

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
        const metricsProcessorLambda = new lambda.Function(this, 'UserMetricsProcessor', {
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
        metricsProcessorLambda.addEventSource(new SqsEventSource(metricsQueue, {
            batchSize: 10,
        }));

        // Grant SQS permissions to the Lambda role
        metricsQueue.grantConsumeMessages(metricsProcessorLambda);
    }
}
