#!/usr/bin/env python3
#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
LISA Inference Metrics Publisher

Background daemon that scrapes Prometheus metrics from inference engine
endpoints (vLLM, TGI, TEI) and publishes them to CloudWatch.

Environment variables:
    METRICS_PUBLISH_INTERVAL  - Seconds between scrape/publish cycles (default: 60)
    METRICS_ENDPOINT          - Prometheus metrics URL (default: http://localhost:8080/metrics)
    INFERENCE_ENGINE          - Explicit engine type override: vllm, tgi, or tei (default: auto-detect)
    CLUSTER_NAME              - ECS cluster name (CloudWatch dimension)
    SERVICE_NAME              - ECS service name (CloudWatch dimension)
    MODEL_NAME                - Model identifier (CloudWatch dimension)
    AWS_REGION                - AWS region for CloudWatch API calls
    METRICS_NAMESPACE         - CloudWatch namespace (default: LISA/InferenceMetrics)
"""

import json
import logging
import os
import re
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

log_level = logging.DEBUG if os.environ.get("DEBUG", "").lower() in ("true", "1", "yes") else logging.INFO
logging.basicConfig(
    level=log_level,
    format="[metrics_publisher] %(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("metrics_publisher")

try:
    import boto3
    from botocore.config import Config as BotoConfig
except ImportError:
    log.error("boto3 not available — metrics publisher disabled")
    sys.exit(0)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PUBLISH_INTERVAL = int(os.environ.get("METRICS_PUBLISH_INTERVAL", "60"))
METRICS_ENDPOINT = os.environ.get("METRICS_ENDPOINT", "http://localhost:8080/metrics")
CLUSTER_NAME = os.environ.get("CLUSTER_NAME", "")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "")
NAMESPACE = os.environ.get("METRICS_NAMESPACE", "LISA/InferenceMetrics")

# Engine type is required — set by each container's entrypoint.sh
INFERENCE_ENGINE = os.environ.get("INFERENCE_ENGINE", "").lower().strip()
if INFERENCE_ENGINE not in ("vllm", "tgi", "tei"):
    log.error(
        "INFERENCE_ENGINE environment variable must be set to one of: vllm, tgi, tei (got: %r)",
        INFERENCE_ENGINE or "<unset>",
    )
    sys.exit(1)

# Metrics we care about, keyed by engine type.
# Each entry maps a Prometheus metric name to a CloudWatch metric name.
VLLM_METRICS = {
    "vllm:gpu_cache_usage_perc": "GpuCacheUsagePercent",
    "vllm:kv_cache_usage_perc": "KvCacheUsagePercent",  # distinct metric for KV cache usage
    "vllm:num_requests_running": "RequestsRunning",
    "vllm:num_requests_waiting": "RequestsWaiting",
    "vllm:num_requests_swapped": "RequestsSwapped",
    "vllm:avg_prompt_throughput_toks_per_s": "AvgPromptThroughputToksPerSec",
    "vllm:avg_generation_throughput_toks_per_s": "AvgGenerationThroughputToksPerSec",
    "vllm:prompt_tokens_total": "PromptTokensTotal",
    "vllm:generation_tokens_total": "GenerationTokensTotal",
    "vllm:request_success_total": "RequestSuccessTotal",
    "vllm:prefix_cache_queries": "PrefixCacheQueries",
    "vllm:prefix_cache_hits": "PrefixCacheHits",
}

# Histogram metrics — we extract the _sum and _count to compute averages
VLLM_HISTOGRAM_METRICS = {
    "vllm:e2e_request_latency_seconds": "E2ERequestLatencySeconds",
    "vllm:time_to_first_token_seconds": "TimeToFirstTokenSeconds",
    "vllm:inter_token_latency_seconds": "InterTokenLatencySeconds",
    "vllm:request_queue_time_seconds": "RequestQueueTimeSeconds",
    "vllm:request_prefill_time_seconds": "RequestPrefillTimeSeconds",
    "vllm:request_decode_time_seconds": "RequestDecodeTimeSeconds",
}

TGI_METRICS = {
    "tgi_queue_size": "QueueSize",
    "tgi_batch_current_size": "BatchCurrentSize",
    "tgi_batch_current_max_tokens": "BatchCurrentMaxTokens",
    "tgi_request_count": "RequestCount",
    "tgi_request_success": "RequestSuccess",
    "tgi_request_failure": "RequestFailure",
}

TGI_HISTOGRAM_METRICS = {
    "tgi_request_duration": "RequestDurationSeconds",
    "tgi_request_queue_duration": "QueueDurationSeconds",
    "tgi_request_inference_duration": "InferenceDurationSeconds",
    "tgi_request_mean_time_per_token_duration": "MeanTimePerTokenSeconds",
    "tgi_request_generated_tokens": "GeneratedTokensPerRequest",
    "tgi_request_input_length": "InputLengthPerRequest",
    "tgi_batch_inference_duration": "BatchInferenceDurationSeconds",
}

TEI_METRICS = {
    "te_queue_size": "QueueSize",
    "te_batch_current_size": "BatchCurrentSize",
}

TEI_HISTOGRAM_METRICS = {
    "te_request_duration": "RequestDurationSeconds",
    "te_request_tokenization_duration": "TokenizationDurationSeconds",
    "te_request_queue_duration": "QueueDurationSeconds",
    "te_request_inference_duration": "InferenceDurationSeconds",
}

# ---------------------------------------------------------------------------
# Prometheus text format parser (minimal, no external deps)
# ---------------------------------------------------------------------------
PROM_LINE_RE = re.compile(r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)" r"(?:\{[^}]*\})?\s+" r"(?P<value>[^\s]+)")


def parse_prometheus(text: str) -> dict[str, float]:
    """Parse Prometheus exposition format into {metric_name: value}."""
    metrics: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = PROM_LINE_RE.match(line)
        if m:
            try:
                val = float(m.group("value"))
                name = m.group("name")
                # Accumulate (some metrics appear multiple times with different labels)
                # For gauges we want the latest; for counters we sum across labels.
                # Since we pick specific metrics, simple last-write-wins is fine for gauges,
                # and for _total counters we sum.
                if name.endswith("_total") or name.endswith("_count") or name.endswith("_sum"):
                    metrics[name] = metrics.get(name, 0.0) + val
                else:
                    metrics[name] = val
            except ValueError:
                continue
    return metrics


def build_metric_data(
    metrics: dict[str, float],
    engine: str,
    dimensions: list[dict],
) -> list[dict]:
    """Build CloudWatch MetricData entries from scraped Prometheus metrics."""
    data: list[dict] = []

    if engine == "vllm":
        gauge_map = VLLM_METRICS
        hist_map = VLLM_HISTOGRAM_METRICS
    elif engine == "tgi":
        gauge_map = TGI_METRICS
        hist_map = TGI_HISTOGRAM_METRICS
    elif engine == "tei":
        gauge_map = TEI_METRICS
        hist_map = TEI_HISTOGRAM_METRICS
    else:
        return data

    # Gauge / counter metrics
    for prom_name, cw_name in gauge_map.items():
        val = metrics.get(prom_name)
        if val is not None:
            data.append(
                {
                    "MetricName": cw_name,
                    "Dimensions": dimensions,
                    "Value": val,
                    "Unit": "None",
                }
            )

    # Histogram metrics — publish average from _sum/_count
    for prom_name, cw_name in hist_map.items():
        total = metrics.get(f"{prom_name}_sum")
        count = metrics.get(f"{prom_name}_count")
        if total is not None and count is not None and count > 0:
            # Determine unit: token/length metrics are counts, everything else is seconds
            unit = "None" if cw_name.endswith("PerRequest") else "Seconds"
            data.append(
                {
                    "MetricName": cw_name,
                    "Dimensions": dimensions,
                    "Value": total / count,
                    "Unit": unit,
                }
            )

    # Always publish engine type as a tag via a simple metric
    data.append(
        {
            "MetricName": "MetricsPublisherHeartbeat",
            "Dimensions": dimensions,
            "Value": 1.0,
            "Unit": "None",
        }
    )

    return data


def publish_loop() -> None:
    """Main loop: scrape → parse → publish, repeat."""
    dimensions = []
    if CLUSTER_NAME:
        dimensions.append({"Name": "ClusterName", "Value": CLUSTER_NAME})
    if SERVICE_NAME:
        dimensions.append({"Name": "ServiceName", "Value": SERVICE_NAME})
    if MODEL_NAME:
        dimensions.append({"Name": "ModelName", "Value": MODEL_NAME})

    if not dimensions:
        log.warning("No dimensions configured (CLUSTER_NAME, SERVICE_NAME, MODEL_NAME). Metrics will be dimensionless.")

    boto_config = BotoConfig(retries={"max_attempts": 2, "mode": "standard"})
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    cw = boto3.client("cloudwatch", config=boto_config, region_name=region)

    consecutive_failures = 0
    max_failures_before_backoff = 5

    log.info(
        "Starting metrics publisher: endpoint=%s interval=%ds namespace=%s engine=%s dimensions=%s",
        METRICS_ENDPOINT,
        PUBLISH_INTERVAL,
        NAMESPACE,
        INFERENCE_ENGINE,
        json.dumps(dimensions),
    )

    # Wait for the inference server to start
    log.info("Waiting for inference server at %s ...", METRICS_ENDPOINT)
    while True:
        try:
            urlopen(METRICS_ENDPOINT, timeout=5)  # nosec B310
            log.info("Inference server is up.")
            break
        except (URLError, OSError):
            time.sleep(10)

    while True:
        try:
            resp = urlopen(METRICS_ENDPOINT, timeout=10)  # nosec B310
            text = resp.read().decode("utf-8", errors="replace")
            metrics = parse_prometheus(text)

            metric_data = build_metric_data(metrics, INFERENCE_ENGINE, dimensions)

            if metric_data:
                # CloudWatch accepts max 20 metrics per call; batch in chunks of 20
                for i in range(0, len(metric_data), 20):
                    cw.put_metric_data(Namespace=NAMESPACE, MetricData=metric_data[i : i + 20])
                log.debug("Published %d metrics to %s", len(metric_data), NAMESPACE)

            consecutive_failures = 0

        except (URLError, OSError) as e:
            consecutive_failures += 1
            log.warning("Failed to scrape metrics (attempt %d): %s", consecutive_failures, e)
        except Exception as e:
            consecutive_failures += 1
            log.error("Error in publish cycle (attempt %d): %s", consecutive_failures, e, exc_info=True)

        # Back off if we keep failing
        sleep_time = PUBLISH_INTERVAL
        if consecutive_failures > max_failures_before_backoff:
            sleep_time = min(PUBLISH_INTERVAL * 4, 300)

        time.sleep(sleep_time)


if __name__ == "__main__":
    try:
        publish_loop()
    except KeyboardInterrupt:
        log.info("Shutting down metrics publisher.")
    except Exception as e:
        # Never crash the container — just log and exit quietly
        log.error("Fatal error in metrics publisher: %s", e, exc_info=True)
