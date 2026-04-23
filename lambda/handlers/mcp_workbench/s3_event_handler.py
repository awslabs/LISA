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

"""Lambda to handle S3 events: refresh MCP Workbench tools via HTTP rescan (in-VPC)."""

import json
import logging
import os
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, cast
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Do not import utilities.common_functions here: it pulls in aws_helpers → amazoncerts,
# which is only present on the shared Common layer. This function uses the bare Lambda.zip asset.
_boto_retry = Config(retries={"max_attempts": 3, "mode": "standard"})

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

secrets_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=_boto_retry)


def _management_bearer_token() -> str | None:
    secret_id = os.environ.get("MANAGEMENT_KEY_NAME")
    if not secret_id:
        return None
    try:
        raw = secrets_client.get_secret_value(SecretId=secret_id, VersionStage="AWSCURRENT")["SecretString"]
        return cast(str, raw)
    except ClientError as e:
        logger.error("Failed to read management key for rescan auth: %s", e)
        raise


def trigger_workbench_rescan() -> dict[str, Any]:
    """
    GET the workbench rescan route (same app management key as OIDC middleware when auth is on).

    Waits briefly so rclone --poll-interval can surface new S3 keys in the tools mount.
    """
    base = (os.environ.get("MCP_WORKBENCH_ENDPOINT") or "").rstrip("/")
    if not base:
        return {"skipped": True, "reason": "MCP_WORKBENCH_ENDPOINT unset"}

    parsed_base = urlparse(base)
    if parsed_base.scheme not in ("http", "https") or not parsed_base.netloc:
        return {"skipped": True, "reason": "MCP_WORKBENCH_ENDPOINT must be http(s) with a host"}

    delay_s = int(os.environ.get("WORKBENCH_RESCAN_DELAY_SECONDS", "5"))
    if delay_s > 0:
        logger.info("Waiting %s s before rescan so rclone can poll S3", delay_s)
        time.sleep(delay_s)

    path = (os.environ.get("MCP_WORKBENCH_RESCAN_PATH") or "v2/mcp/rescan").strip("/")
    url = f"{base}/{path}"

    headers: dict[str, str] = {}
    token = _management_bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    open_kw: dict[str, Any] = {"timeout": 120}
    # In-VPC rescan only; workbench ALB may use private/self-signed certs not in the Lambda trust store.
    if parsed_base.scheme == "https":
        open_kw["context"] = ssl._create_unverified_context()  # nosec B323

    try:
        with urllib.request.urlopen(req, **open_kw) as resp:  # nosec B310
            body = resp.read().decode()
            logger.info("Rescan HTTP %s: %s", resp.status, body[:500])
            return {"rescan_status_code": resp.status, "rescan_body": body}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else str(e)
        logger.error("Rescan HTTP error %s: %s", e.code, err_body)
        return {"rescan_error": True, "rescan_status_code": e.code, "rescan_body": err_body}
    except urllib.error.URLError as e:
        logger.error("Rescan request failed: %s", e)
        return {"rescan_error": True, "rescan_reason": str(e.reason)}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Handle S3 events from EventBridge: call MCP Workbench HTTP rescan (in-VPC).

    Reloads tools from the rclone-mounted bucket without restarting ECS tasks.
    """
    logger.info(f"Received S3 event: {json.dumps(event, default=str)}")

    try:
        # Extract event details
        detail = event.get("detail", {})
        bucket_name = detail.get("bucket", {}).get("name")
        event_name = detail.get("eventName", "")

        if not bucket_name:
            logger.error("Missing bucket name in event details")
            return {"statusCode": 400, "body": json.dumps("Missing bucket name")}

        logger.info(f"Processing S3 event '{event_name}' for bucket: {bucket_name}")

        rescan_result = trigger_workbench_rescan()

        payload = {
            "message": "MCP Workbench tools refresh triggered",
            "bucket": bucket_name,
            "event": event_name,
            "rescan": rescan_result,
        }

        if rescan_result.get("rescan_error"):
            return {"statusCode": 502, "body": json.dumps(payload)}

        return {"statusCode": 200, "body": json.dumps(payload)}

    except Exception as e:
        logger.error(f"Error processing S3 event: {str(e)}")
        return {"statusCode": 500, "body": json.dumps(f"Error: {str(e)}")}


def validate_s3_event(event: dict[str, Any]) -> bool:
    """
    Validate that the event is a proper S3 event from EventBridge.
    """
    try:
        source = event.get("source")
        detail_type = event.get("detail-type")
        detail = event.get("detail", {})

        # Check if it's an S3 event
        if source not in ["aws.s3", "debug"]:
            return False

        # Check if it's an object event
        if detail_type not in ["Object Created", "Object Deleted"]:
            return False

        # Check if bucket information is present
        if not detail.get("bucket", {}).get("name"):
            return False

        return True

    except Exception as e:
        logger.error(f"Error validating S3 event: {e}")
        return False
