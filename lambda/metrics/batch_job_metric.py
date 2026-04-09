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

"""Lambda handler for publishing CloudWatch metrics on Batch job state changes.

Captures SUBMITTED, RUNNING, SUCCEEDED, and FAILED state transitions from
EventBridge and publishes corresponding metrics to the LISA/BatchIngestion
namespace. This provides queue-level visibility regardless of how the
ingestion job was triggered (S3 event, scheduled, or manual upload).
"""

import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

cloudwatch = boto3.client("cloudwatch")

# Map Batch job states to CloudWatch metric names
STATE_METRIC_MAP = {
    "SUBMITTED": "JobsSubmitted",
    "RUNNING": "JobsStarted",
    "SUCCEEDED": "JobsSucceeded",
    "FAILED": "JobsFailed",
}


def handler(event: dict, context: dict) -> None:
    """Publish a CloudWatch metric when an AWS Batch ingestion job changes state.

    Triggered by an EventBridge rule that captures Batch Job State Change
    events for the ingestion job queue.

    Parameters
    ----------
    event : dict
        EventBridge event with Batch job state change details.
    context : dict
        Lambda execution context.
    """
    namespace = os.environ["METRICS_NAMESPACE"]
    deployment = os.environ["DEPLOYMENT_NAME"]
    stage = os.environ["DEPLOYMENT_STAGE"]

    detail = event.get("detail", {})
    job_queue = detail.get("jobQueue", "unknown")
    job_name = detail.get("jobName", "unknown")
    status = detail.get("status", "UNKNOWN")

    metric_name = STATE_METRIC_MAP.get(status)
    if not metric_name:
        logger.warning(json.dumps({"message": "Unhandled job status", "status": status}))
        return

    cloudwatch.put_metric_data(
        Namespace=namespace,
        MetricData=[
            {
                "MetricName": metric_name,
                "Dimensions": [
                    {"Name": "DeploymentName", "Value": deployment},
                    {"Name": "DeploymentStage", "Value": stage},
                    {"Name": "JobQueue", "Value": os.environ.get("JOB_QUEUE_LABEL", job_queue.split("/")[-1])},
                ],
                "Value": 1,
                "Unit": "Count",
            },
        ],
    )
    logger.info(json.dumps({"status": status, "metric": metric_name, "jobName": job_name, "jobQueue": job_queue}))
