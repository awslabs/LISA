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
        // (e.g. "prod-gptoss20b"). CloudWatch SEARCH tokenizes on hyphens, so
        // "prod-gptoss20b" becomes tokens ["prod", "gptoss20b"]. Using a partial match
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
                markdown: '# **LISA Self-Hosted Model Health Dashboard**',
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
            // Use Maximum so counts display as whole numbers instead of fractional averages.
            new cloudwatch.GraphWidget({
                title: 'Running vs Desired Tasks (by Cluster)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="RunningTaskCount" ClusterName=${dp}', 'Maximum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="DesiredTaskCount" ClusterName=${dp}', 'Maximum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Pending tasks — waiting for placement (capacity issues)
            // Use Maximum instead of Average so the count shows as whole numbers
            // (Average over 5 min produces tiny fractions like 0.03).
            new cloudwatch.GraphWidget({
                title: 'Pending Tasks (by Cluster)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="PendingTaskCount" ClusterName=${dp}', 'Maximum', 300)`,
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
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="TaskSetCount" ClusterName=${dp}', 'Maximum', 300)`,
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
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="DeploymentCount" ClusterName=${dp}', 'Maximum', 300)`,
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
        // ALB metrics are published with specific dimension combos. Target-level
        // metrics (HealthyHostCount, HTTP codes, etc.) use {TargetGroup, LoadBalancer}.
        // Connection-level metrics (ActiveConnectionCount, etc.) use {LoadBalancer} only.
        // The deployment name token (e.g. "prod") scopes results to this deployment's
        // ALBs and target groups.
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
                        expression: `SEARCH('{AWS/ApplicationELB,TargetGroup,LoadBalancer} MetricName="HealthyHostCount" ${dp}', 'Average', 300)`,
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
                        expression: `SEARCH('{AWS/ApplicationELB,TargetGroup,LoadBalancer} MetricName="UnHealthyHostCount" ${dp}', 'Average', 300)`,
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
                        expression: `SEARCH('{AWS/ApplicationELB,TargetGroup,LoadBalancer} MetricName="HTTPCode_Target_5XX_Count" ${dp}', 'Sum', 300)`,
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
                        expression: `SEARCH('{AWS/ApplicationELB,TargetGroup,LoadBalancer} MetricName="HTTPCode_Target_4XX_Count" ${dp}', 'Sum', 300)`,
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
                        expression: `SEARCH('{AWS/ApplicationELB,LoadBalancer} MetricName="HTTPCode_ELB_5XX_Count" ${dp}', 'Sum', 300)`,
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
            // ALB publishes TargetResponseTime in seconds; multiply by 1000 for milliseconds.
            // Exclude the REST API target group (contains "RestA") — it's the API router, not a model.
            // SEARCH auto-labels include the full ALB/TG ARN path which is hard to read;
            // unfortunately CloudWatch SEARCH doesn't support label customization.
            // For clean per-model latency, see the Inference Engine Metrics section below
            // (E2E Request Latency, TTFT, Inter-Token Latency) which use the ModelName dimension.
            new cloudwatch.GraphWidget({
                title: 'Target Response Time p50 (by Model)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB,TargetGroup,LoadBalancer} MetricName="TargetResponseTime" ${dp} NOT RestA NOT rest NOT MCP', 'p50', 300) * 1000`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                leftYAxis: { label: 'ms' },
                width: 12,
                height: 6,
            }),

            new cloudwatch.GraphWidget({
                title: 'Target Response Time p99 (by Model)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB,TargetGroup,LoadBalancer} MetricName="TargetResponseTime" ${dp} NOT RestA NOT rest NOT MCP', 'p99', 300) * 1000`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                leftYAxis: { label: 'ms' },
                width: 12,
                height: 6,
            }),

            // Request count per model (throughput / load) — excludes REST API target group
            new cloudwatch.GraphWidget({
                title: 'Request Count (by Model)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/ApplicationELB,TargetGroup,LoadBalancer} MetricName="RequestCount" ${dp} NOT RestA NOT rest NOT MCP', 'Sum', 300)`,
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
                        expression: `SEARCH('{AWS/ApplicationELB,LoadBalancer} MetricName="ActiveConnectionCount" ${dp}', 'Sum', 300)`,
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
                        expression: `SEARCH('{AWS/ApplicationELB,LoadBalancer} MetricName="NewConnectionCount" ${dp}', 'Sum', 300)`,
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
            // The raw metric is a 0–1 decimal; multiply by 100 for display as a percentage.
            new cloudwatch.GraphWidget({
                title: 'GPU Cache Usage % (vLLM)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{LISA/InferenceMetrics,ModelName} MetricName="GpuCacheUsagePercent"\', \'Average\', 300) * 100',
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                leftYAxis: { min: 0, max: 100, label: '%' },
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
                        expression: 'SEARCH(\'{LISA/InferenceMetrics,ModelName} MetricName="RequestsRunning"\', \'Average\', 300)',
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: 'SEARCH(\'{LISA/InferenceMetrics,ModelName} MetricName="RequestsWaiting"\', \'Average\', 300)',
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

            // Storage I/O — read and write bytes
            new cloudwatch.GraphWidget({
                title: 'Storage Read / Write Bytes (by Cluster)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="StorageReadBytes" ClusterName=${dp}', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName} MetricName="StorageWriteBytes" ClusterName=${dp}', 'Average', 300)`,
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

            // vLLM: Token throughput — derived from cumulative token counters.
            // AvgPrompt/GenerationThroughputToksPerSec gauges were removed in newer vLLM versions,
            // so we use DIFF on the cumulative totals divided by the period (300s) to get toks/sec.
            new cloudwatch.GraphWidget({
                title: 'Token Throughput (vLLM)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `DIFF(SEARCH('{${metricsNs},ModelName} MetricName="PromptTokensTotal"', 'Maximum', 300)) / 300`,
                        label: 'Prompt toks/s',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `DIFF(SEARCH('{${metricsNs},ModelName} MetricName="GenerationTokensTotal"', 'Maximum', 300)) / 300`,
                        label: 'Generation toks/s',
                        period: Duration.minutes(5),
                    }),
                ],
                leftYAxis: { label: 'toks/s' },
                rightYAxis: { label: 'toks/s' },
                width: 12,
                height: 6,
            }),

            // vLLM: E2E request latency and TTFT
            new cloudwatch.GraphWidget({
                title: 'E2E Request Latency / TTFT (vLLM)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="E2ERequestLatencySeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="TimeToFirstTokenSeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // vLLM: Inter-token latency (TPOT) — key SLO metric for streaming
            new cloudwatch.GraphWidget({
                title: 'Inter-Token Latency / TPOT (vLLM)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="InterTokenLatencySeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // vLLM: Queue time — how long requests wait before processing
            new cloudwatch.GraphWidget({
                title: 'Request Queue Time (vLLM)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="RequestQueueTimeSeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // vLLM: Prefill and decode time breakdown
            new cloudwatch.GraphWidget({
                title: 'Prefill / Decode Time (vLLM)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="RequestPrefillTimeSeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="RequestDecodeTimeSeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // vLLM: Completed requests and prefix cache effectiveness
            new cloudwatch.GraphWidget({
                title: 'Completed Requests (vLLM)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="RequestSuccessTotal"', 'Sum', 300)`,
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
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="QueueSize"', 'Average', 300)`,
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
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="BatchCurrentSize"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // TGI: Request success / failure counts
            new cloudwatch.GraphWidget({
                title: 'TGI Request Success / Failure',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="RequestSuccess"', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="RequestFailure"', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // TGI: Latency breakdown — queue, inference, per-token
            new cloudwatch.GraphWidget({
                title: 'TGI Latency Breakdown (Queue / Inference / Per-Token)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="QueueDurationSeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="InferenceDurationSeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="MeanTimePerTokenSeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // TGI: Input / output token sizes per request
            new cloudwatch.GraphWidget({
                title: 'TGI Avg Input / Generated Tokens per Request',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="InputLengthPerRequest"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                right: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="GeneratedTokensPerRequest"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // TEI: Request duration breakdown — tokenization, queue, inference
            new cloudwatch.GraphWidget({
                title: 'TEI Request Duration Breakdown',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="RequestDurationSeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // TEI: Tokenization / Queue / Inference time breakdown
            new cloudwatch.GraphWidget({
                title: 'TEI Tokenization / Queue / Inference Time',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="TokenizationDurationSeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="QueueDurationSeconds"', 'Average', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="InferenceDurationSeconds"', 'Average', 300)`,
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
                        expression: `SEARCH('{${metricsNs},ModelName} MetricName="MetricsPublisherHeartbeat"', 'Average', 300)`,
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
        // AWS Batch does not publish job-level metrics to CloudWatch natively.
        // Job failures are captured via EventBridge → Lambda → custom CloudWatch
        // metric (LISA/BatchIngestion namespace). Lambda invocation metrics track
        // job submissions. Function names follow:
        //   {deploymentName}-{deploymentStage}-ingestion-{ingest-schedule|ingest-event|delete-event}
        dashboard.addWidgets(
            new cloudwatch.TextWidget({
                markdown: '## **Batch Ingestion**\nDocument ingestion pipeline metrics (Lambda submissions + custom failure metric)',
                width: 24,
                height: 1,
                background: cloudwatch.TextWidgetBackground.TRANSPARENT,
            }),

            // Ingestion Lambda invocations — tracks job submissions
            new cloudwatch.GraphWidget({
                title: 'Ingestion Lambda Invocations (Job Submissions)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/Lambda,FunctionName} MetricName="Invocations" ${dp}-${config.deploymentStage}-ingestion', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Ingestion Lambda errors — failures in the submission Lambdas themselves
            new cloudwatch.GraphWidget({
                title: 'Ingestion Lambda Errors',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/Lambda,FunctionName} MetricName="Errors" ${dp}-${config.deploymentStage}-ingestion', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Batch job failures — from custom metric published by EventBridge → Lambda
            new cloudwatch.GraphWidget({
                title: 'Batch Job Failures',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{LISA/BatchIngestion,DeploymentName,DeploymentStage,JobQueue} MetricName="JobsFailed" DeploymentName="${dp}"', 'Sum', 300)`,
                        label: '',
                        period: Duration.minutes(5),
                    }),
                ],
                width: 12,
                height: 6,
            }),

            // Ingestion Lambda duration — how long submissions take
            new cloudwatch.GraphWidget({
                title: 'Ingestion Lambda Duration (ms)',
                left: [
                    new cloudwatch.MathExpression({
                        expression: `SEARCH('{AWS/Lambda,FunctionName} MetricName="Duration" ${dp}-${config.deploymentStage}-ingestion', 'Average', 300)`,
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
        // NOTE: ALB alarms (unhealthy hosts, 5xx errors, connection errors,
        // latency, rejected connections) were removed because:
        //   1. Model ALB dimensions (TargetGroup/LoadBalancer) are dynamic and
        //      unknown at deploy time — dimensionless metrics return no data.
        //   2. CloudWatch does not support SEARCH expressions in Metric Alarms.
        // ALB health is monitored via the SEARCH-based dashboard widgets above.
        const alarmPrefix = `${dp}-${config.deploymentStage}-LISA`;

        // Batch ingestion job failures — from custom metric published by
        // EventBridge → Lambda when Batch jobs enter FAILED state.
        const batchJobFailuresAlarm = new cloudwatch.Alarm(this, 'BatchJobFailuresAlarm', {
            alarmName: `${alarmPrefix}-BatchJobFailures`,
            alarmDescription: 'One or more batch ingestion jobs have failed. Check AWS Batch console and CloudWatch Logs for the failed job details.',
            metric: new cloudwatch.Metric({
                namespace: 'LISA/BatchIngestion',
                metricName: 'JobsFailed',
                dimensionsMap: {
                    DeploymentName: dp,
                    DeploymentStage: config.deploymentStage,
                },
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
                    batchJobFailuresAlarm,
                ],
                width: 24,
                height: 4,
            }),
        );
    }
}
