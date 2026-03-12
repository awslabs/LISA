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

import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import { Construct } from 'constructs';
import { Duration } from 'aws-cdk-lib';
import { BaseProps } from '../schema';

/**
 * CloudWatch dashboard for ECS model hosting operational health.
 *
 * Uses Container Insights v2 metrics (ECS/ContainerInsights namespace)
 * and ALB metrics. SEARCH expressions auto-discover all model clusters
 * so new model deployments appear without dashboard changes.
 */
export class ModelHealthDashboard extends Construct {

    constructor (scope: Construct, id: string, props: BaseProps) {
        super(scope, id);

        const { config } = props;
        // Deployment prefix used in SEARCH expressions to scope to this deployment's clusters.
        // Cluster names are built via createCdkId and always start with deploymentName
        // (e.g. "bear-gptoss20b"). CloudWatch SEARCH tokenizes on hyphens, so
        // "bear-gptoss20b" becomes tokens ["bear", "gptoss20b"]. Using a partial match
        // (no double quotes) like ClusterName=${dp} matches any ClusterName containing
        // the deployment name token. Double-quoted values do exact match only — no wildcards.
        const dp = config.deploymentName;

        const dashboard = new cloudwatch.Dashboard(this, 'ModelHealthDashboard', {
            dashboardName: `${dp}-${config.deploymentStage}-LISA-Model-Health`,
            start: '-P7D',
        });

        // =====================================================================
        // Task & Container Health
        // =====================================================================
        dashboard.addWidgets(
            new cloudwatch.TextWidget({
                markdown: '# **LISA Model Health Dashboard**',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),

            new cloudwatch.TextWidget({
                markdown: '## **Task & Container Health**',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),

            // Running vs Desired Task Count per cluster/service
            new cloudwatch.GraphWidget({
                title: 'Running vs Desired Tasks (by Cluster)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="RunningTaskCount" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="DesiredTaskCount" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Pending tasks — waiting for placement (capacity issues)
            new cloudwatch.GraphWidget({
                title: 'Pending Tasks (by Cluster)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="PendingTaskCount" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Task set count — tracks deployment rollouts and circuit breaker activity
            new cloudwatch.GraphWidget({
                title: 'Task Sets (Deployment Rollouts)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="TaskSetCount" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Service deployment count — spikes indicate restarts or circuit breaker trips
            new cloudwatch.GraphWidget({
                title: 'Deployment Count (by Service)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="DeploymentCount" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),
        );

        // =====================================================================
        // ALB Target Health
        // =====================================================================
        // ALB metrics are published with varying dimension combos (e.g.
        // TargetGroup+AZ+LoadBalancer, AZ+LoadBalancer, etc.). Using just
        // {AWS/ApplicationELB} with no dimension names in the schema matches
        // all combos. The deployment name token (e.g. "bear") scopes results
        // to this deployment's ALBs and target groups.
        dashboard.addWidgets(
            new cloudwatch.TextWidget({
                markdown: '## **ALB Target Health**',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),

            // Healthy host count per target group
            new cloudwatch.GraphWidget({
                title: 'Healthy Host Count (by Target Group)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="HealthyHostCount" ${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Unhealthy host count per target group
            new cloudwatch.GraphWidget({
                title: 'Unhealthy Host Count (by Target Group)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="UnHealthyHostCount" ${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),
        );

        // =====================================================================
        // Error Rates
        // =====================================================================
        dashboard.addWidgets(
            new cloudwatch.TextWidget({
                markdown: '## **Error Rates**',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),

            // Target 5xx — failed model invocations (500s from the container)
            new cloudwatch.GraphWidget({
                title: 'Target 5xx Errors (Failed Invocations)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="HTTPCode_Target_5XX_Count" ${dp}', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),

            // Target 4xx — client errors / bad requests to models
            new cloudwatch.GraphWidget({
                title: 'Target 4xx Errors (by Model)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="HTTPCode_Target_4XX_Count" ${dp}', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),

            // ELB 5xx — load balancer level errors (no healthy targets, timeouts)
            new cloudwatch.GraphWidget({
                title: 'ELB 5xx Errors (by Load Balancer)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="HTTPCode_ELB_5XX_Count" ${dp}', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),

            // Target connection errors — ALB couldn't connect to container (crash/OOM)
            new cloudwatch.GraphWidget({
                title: 'Target Connection Errors',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="TargetConnectionErrorCount" ${dp}', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),

            // Rejected connection count — model hit max concurrent connections
            new cloudwatch.GraphWidget({
                title: 'Rejected Connections (by Load Balancer)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="RejectedConnectionCount" ${dp}', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),

            // Target TLS negotiation errors
            new cloudwatch.GraphWidget({
                title: 'Target TLS Errors',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="TargetTLSNegotiationErrorCount" ${dp}', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),
        );

        // =====================================================================
        // Latency & Throughput
        // =====================================================================
        dashboard.addWidgets(
            new cloudwatch.TextWidget({
                markdown: '## **Latency & Throughput**',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),

            // Target response time p50/p99 per model
            new cloudwatch.GraphWidget({
                title: 'Target Response Time p50 / p99 (by Model)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="TargetResponseTime" ${dp}', 'p50', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="TargetResponseTime" ${dp}', 'p99', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Request count per model (throughput / load)
            new cloudwatch.GraphWidget({
                title: 'Request Count (by Model)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="RequestCount" ${dp}', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Active connection count — concurrent load per ALB
            new cloudwatch.GraphWidget({
                title: 'Active Connections (by Load Balancer)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="ActiveConnectionCount" ${dp}', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // New connection count — rate of new connections
            new cloudwatch.GraphWidget({
                title: 'New Connections (by Load Balancer)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB} MetricName="NewConnectionCount" ${dp}', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),
        );

        // =====================================================================
        // Resource Utilization
        // =====================================================================
        dashboard.addWidgets(
            new cloudwatch.TextWidget({
                markdown: '## **Resource Utilization**',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),

            // CPU utilization per cluster/service
            new cloudwatch.GraphWidget({
                title: 'CPU Utilized (by Cluster)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="CpuUtilized" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),

            // Memory utilization per cluster/service
            new cloudwatch.GraphWidget({
                title: 'Memory Utilized (by Cluster)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="MemoryUtilized" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),

            // GPU Cache Usage (vLLM) — from custom metrics publisher
            new cloudwatch.GraphWidget({
                title: 'GPU Cache Usage % (vLLM)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{LISA/InferenceMetrics,ClusterName,ServiceName,ModelName} MetricName="GpuCacheUsagePercent"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),

            // CPU reserved vs utilized — shows headroom
            new cloudwatch.GraphWidget({
                title: 'CPU Reserved (by Cluster)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="CpuReserved" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),

            // Memory reserved vs utilized — shows headroom
            new cloudwatch.GraphWidget({
                title: 'Memory Reserved (by Cluster)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="MemoryReserved" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),

            // Inference Requests Running/Waiting (vLLM) — from custom metrics publisher
            new cloudwatch.GraphWidget({
                title: 'Requests Running / Waiting (vLLM)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{LISA/InferenceMetrics,ClusterName,ServiceName,ModelName} MetricName="RequestsRunning"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{LISA/InferenceMetrics,ClusterName,ServiceName,ModelName} MetricName="RequestsWaiting"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 8,
                height: 6,
            }),
        );

        // =====================================================================
        // Network & Storage
        // =====================================================================
        dashboard.addWidgets(
            new cloudwatch.TextWidget({
                markdown: '## **Network & Storage**',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),

            // Network throughput RX/TX
            new cloudwatch.GraphWidget({
                title: 'Network RX / TX Bytes (by Cluster)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="NetworkRxBytes" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="NetworkTxBytes" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Ephemeral storage utilization
            new cloudwatch.GraphWidget({
                title: 'Ephemeral Storage Utilized (by Cluster)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="EphemeralStorageUtilized" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),
        );

        // =====================================================================
        // Inference Engine Metrics (from metrics_publisher.py)
        // =====================================================================
        // These metrics are scraped from the Prometheus /metrics endpoint of each
        // inference engine (vLLM, TGI, TEI) and published to the LISA/InferenceMetrics
        // CloudWatch namespace by a background script running in each container.
        const metricsNs = 'LISA/InferenceMetrics';
        dashboard.addWidgets(
            new cloudwatch.TextWidget({
                markdown: '## **Inference Engine Metrics**\nScraped from Prometheus `/metrics` endpoints via `metrics_publisher.py`',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),

            // vLLM: Token throughput
            new cloudwatch.GraphWidget({
                title: 'Token Throughput (vLLM)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ClusterName,ServiceName,ModelName} MetricName="AvgPromptThroughputToksPerSec"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ClusterName,ServiceName,ModelName} MetricName="AvgGenerationThroughputToksPerSec"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // vLLM: E2E request latency
            new cloudwatch.GraphWidget({
                title: 'E2E Request Latency (vLLM)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ClusterName,ServiceName,ModelName} MetricName="E2ERequestLatencySeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ClusterName,ServiceName,ModelName} MetricName="TimeToFirstTokenSeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // TGI/TEI: Queue size and batch size
            new cloudwatch.GraphWidget({
                title: 'Queue Size (TGI / TEI)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ClusterName,ServiceName,ModelName} MetricName="QueueSize"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // TGI/TEI: Batch current size
            new cloudwatch.GraphWidget({
                title: 'Batch Current Size (TGI / TEI)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ClusterName,ServiceName,ModelName} MetricName="BatchCurrentSize"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Metrics publisher heartbeat — confirms which models are reporting
            new cloudwatch.GraphWidget({
                title: 'Metrics Publisher Heartbeat (by Model)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ClusterName,ServiceName,ModelName} MetricName="MetricsPublisherHeartbeat"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),
        );

        // =====================================================================
        // Batch Ingestion Metrics
        // =====================================================================
        // AWS Batch metrics for the document ingestion pipeline.
        // Job queue name follows: {deploymentName}-{deploymentStage}-ingestion-job-{hash}
        const batchPrefix = `${dp}-${config.deploymentStage}-ingestion`;
        dashboard.addWidgets(
            new cloudwatch.TextWidget({
                markdown: '## **Batch Ingestion**\nAWS Batch document ingestion pipeline metrics',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),

            // Jobs submitted, pending, running — pipeline throughput
            new cloudwatch.GraphWidget({
                title: 'Ingestion Jobs: Submitted / Pending / Runnable',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/Batch,JobQueue} MetricName="JobsSubmittedCount" JobQueue="${batchPrefix}"', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/Batch,JobQueue} MetricName="PendingJobsCount" JobQueue="${batchPrefix}"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/Batch,JobQueue} MetricName="RunnableJobsCount" JobQueue="${batchPrefix}"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Jobs running and succeeded — active processing
            new cloudwatch.GraphWidget({
                title: 'Ingestion Jobs: Running / Succeeded',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/Batch,JobQueue} MetricName="RunningJobsCount" JobQueue="${batchPrefix}"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/Batch,JobQueue} MetricName="JobsSucceededCount" JobQueue="${batchPrefix}"', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Job failures — critical for alerting on broken ingestion
            new cloudwatch.GraphWidget({
                title: 'Ingestion Job Failures',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/Batch,JobQueue} MetricName="JobsFailedCount" JobQueue="${batchPrefix}"', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Ingestion Lambda invocations and errors
            new cloudwatch.GraphWidget({
                title: 'Ingestion Lambda Invocations',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/Lambda,FunctionName} MetricName="Invocations" FunctionName="${dp}-${config.deploymentStage}-ingestion"', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/Lambda,FunctionName} MetricName="Errors" FunctionName="${dp}-${config.deploymentStage}-ingestion"', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),
        );

        // =====================================================================
        // Auto Scaling
        // =====================================================================
        dashboard.addWidgets(
            new cloudwatch.TextWidget({
                markdown: '## **Auto Scaling**',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),

            // ASG group size — instances backing the ECS clusters
            new cloudwatch.GraphWidget({
                title: 'ASG Instance Count (by Group)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{AWS/AutoScaling,AutoScalingGroupName} MetricName="GroupInServiceInstances"\', \'Average\', 300)',
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // ASG desired vs in-service
            new cloudwatch.GraphWidget({
                title: 'ASG Desired Capacity (by Group)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{AWS/AutoScaling,AutoScalingGroupName} MetricName="GroupDesiredCapacity"\', \'Average\', 300)',
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),
        );

        // =====================================================================
        // Alarms
        // =====================================================================
        // These use account-level ALB metrics (no dimensions) to aggregate
        // across all load balancers in the account. This catches issues with
        // any model without needing to know model names at deploy time.
        const alarmPrefix = `${dp}-${config.deploymentStage}-LISA`;

        // 1. Unhealthy hosts — any model container failing health checks
        //    Uses account-level metric (no TargetGroup/LoadBalancer dimensions)
        //    to aggregate across all ALBs.
        const unhealthyHostsAlarm = new cloudwatch.Alarm(this, 'UnhealthyHostsAlarm', {
            alarmName: `${alarmPrefix}-UnhealthyHosts`,
            alarmDescription: 'One or more ECS model containers are failing ALB health checks. Check the Model Health dashboard for details on which target group is affected.',
            metric: new cloudwatch.Metric({
                namespace: 'AWS/ApplicationELB',
                metricName: 'UnHealthyHostCount',
                statistic: 'Maximum',
                period: Duration.minutes(5),
            }),
            threshold: 0,
            comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluationPeriods: 2,
            treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
        });

        // 2. Target 5xx errors sustained — model invocations are failing
        const target5xxAlarm = new cloudwatch.Alarm(this, 'Target5xxAlarm', {
            alarmName: `${alarmPrefix}-Target5xxErrors`,
            alarmDescription: 'Sustained HTTP 5xx errors from model containers indicating failed inference requests. Investigate container logs for the affected model.',
            metric: new cloudwatch.Metric({
                namespace: 'AWS/ApplicationELB',
                metricName: 'HTTPCode_Target_5XX_Count',
                statistic: 'Sum',
                period: Duration.minutes(5),
            }),
            threshold: 10,
            comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluationPeriods: 2,
            treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
        });

        // 3. Target connection errors — ALB can't reach container (crash/OOM)
        const connectionErrorAlarm = new cloudwatch.Alarm(this, 'TargetConnectionErrorAlarm', {
            alarmName: `${alarmPrefix}-TargetConnectionErrors`,
            alarmDescription: 'ALB cannot establish connections to model containers. This typically indicates container crashes, OOM kills, or process failures.',
            metric: new cloudwatch.Metric({
                namespace: 'AWS/ApplicationELB',
                metricName: 'TargetConnectionErrorCount',
                statistic: 'Sum',
                period: Duration.minutes(5),
            }),
            threshold: 5,
            comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluationPeriods: 2,
            treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
        });

        // 4. ELB 5xx errors — load balancer has no healthy targets
        const elb5xxAlarm = new cloudwatch.Alarm(this, 'ELB5xxAlarm', {
            alarmName: `${alarmPrefix}-ELB5xxErrors`,
            alarmDescription: 'ALB is returning 5xx errors, typically meaning no healthy targets are available for one or more models. This is a critical availability issue.',
            metric: new cloudwatch.Metric({
                namespace: 'AWS/ApplicationELB',
                metricName: 'HTTPCode_ELB_5XX_Count',
                statistic: 'Sum',
                period: Duration.minutes(5),
            }),
            threshold: 5,
            comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluationPeriods: 2,
            treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
        });

        // 5. High p99 latency — model response times degrading
        const highLatencyAlarm = new cloudwatch.Alarm(this, 'HighLatencyAlarm', {
            alarmName: `${alarmPrefix}-HighP99Latency`,
            alarmDescription: 'P99 response time across model endpoints exceeds 120 seconds. Models may be overloaded or experiencing resource contention.',
            metric: new cloudwatch.Metric({
                namespace: 'AWS/ApplicationELB',
                metricName: 'TargetResponseTime',
                statistic: 'p99',
                period: Duration.minutes(5),
            }),
            threshold: 120,
            comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluationPeriods: 3,
            treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
        });

        // 6. Rejected connections — models at capacity
        const rejectedConnectionsAlarm = new cloudwatch.Alarm(this, 'RejectedConnectionsAlarm', {
            alarmName: `${alarmPrefix}-RejectedConnections`,
            alarmDescription: 'ALB is rejecting connections, indicating model endpoints are at maximum capacity. Consider scaling up or adding more instances.',
            metric: new cloudwatch.Metric({
                namespace: 'AWS/ApplicationELB',
                metricName: 'RejectedConnectionCount',
                statistic: 'Sum',
                period: Duration.minutes(5),
            }),
            threshold: 0,
            comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluationPeriods: 2,
            treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
        });

        // 7. Batch ingestion job failures — broken document ingestion pipeline
        //    Uses account-level metric (no JobQueue dimension) to aggregate across
        //    all Batch job queues since the ingestion queue name includes a random hash.
        const batchJobFailuresAlarm = new cloudwatch.Alarm(this, 'BatchJobFailuresAlarm', {
            alarmName: `${alarmPrefix}-BatchJobFailures`,
            alarmDescription: 'One or more batch ingestion jobs have failed. Check AWS Batch console and CloudWatch Logs for the failed job details.',
            metric: new cloudwatch.Metric({
                namespace: 'AWS/Batch',
                metricName: 'JobsFailedCount',
                statistic: 'Sum',
                period: Duration.minutes(5),
            }),
            threshold: 0,
            comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluationPeriods: 1,
            treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
        });

        // Add alarm status widgets to the dashboard
        dashboard.addWidgets(
            new cloudwatch.TextWidget({
                markdown: '## **Alarm Status**',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),
            new cloudwatch.AlarmStatusWidget({
                title: 'Model Health Alarms',
                alarms: [
                    unhealthyHostsAlarm,
                    target5xxAlarm,
                    connectionErrorAlarm,
                    elb5xxAlarm,
                    highLatencyAlarm,
                    rejectedConnectionsAlarm,
                    batchJobFailuresAlarm,
                ],
                width: 24,
                height: 4,
            }),
        );
    }
}
