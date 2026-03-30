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

"""Generic AWS API access via boto3 using the MCP workbench AWS session.

This sample exposes one tool that can call any boto3 client method (service +
operation + parameters). That matches IAM permissions of the connected
credentials. For production, consider restricting allowed services or operations.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import boto3
from botocore.response import StreamingBody
from mcpworkbench.aws import shared_session_service as _session_service
from mcpworkbench.aws.identity import CallerIdentityError, get_caller_identity
from mcpworkbench.aws.session_models import AwsSessionRecord
from mcpworkbench.aws.session_service import AwsSessionMissingError
from mcpworkbench.core.annotations import mcp_tool

_SERVICE_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_OPERATION_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_STREAMING_BODY_READ_LIMIT = 65_536


def _session_record() -> AwsSessionRecord:
    try:
        identity = get_caller_identity()
    except CallerIdentityError as exc:
        raise RuntimeError(
            "Could not determine caller identity from the request. "
            "Ensure the MCP connection sends Authorization and X-Session-Id headers."
        ) from exc

    try:
        return _session_service.get_aws_session_for_user(identity.user_id, identity.session_id)
    except AwsSessionMissingError as exc:
        raise RuntimeError("AWS session not connected or expired.") from exc


def _build_client(record: AwsSessionRecord, service_name: str, region_name: str | None) -> Any:
    return boto3.client(
        service_name,
        aws_access_key_id=record.aws_access_key_id,
        aws_secret_access_key=record.aws_secret_access_key,
        aws_session_token=record.aws_session_token,
        region_name=region_name or record.aws_region,
    )


def _to_serializable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(v) for v in obj]
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, StreamingBody):
        try:
            chunk = obj.read(_STREAMING_BODY_READ_LIMIT)
            truncated = len(chunk) >= _STREAMING_BODY_READ_LIMIT
            try:
                text = chunk.decode("utf-8")
            except UnicodeDecodeError:
                text = chunk.hex()
                truncated = True
            return {
                "_streaming_body": True,
                "content_preview": text,
                "truncated": truncated,
                "note": "S3 and similar APIs return a stream; only a prefix is returned here.",
            }
        finally:
            try:
                obj.close()
            except Exception:
                # Best-effort cleanup; ignore close errors to avoid changing caller behavior.
                pass
    return str(obj)


@mcp_tool(
    name="aws_api_call",
    description=(
        "Call any AWS API exposed as a boto3 client method using the connected AWS session. "
        "Arguments: service (e.g. s3, ec2, dynamodb), operation (snake_case method name such as "
        "list_buckets or describe_instances), optional parameters object for boto3 keyword "
        "arguments, optional region to override the session default. "
        "Respects the caller's IAM permissions; destructive or broad calls are possible—use "
        "with care. Paginator workflows use multiple calls or the AWS CLI from your environment."
    ),
)
def aws_api_call(
    service: str,
    operation: str,
    parameters: dict[str, Any] | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    if not _SERVICE_RE.match(service):
        raise ValueError(f"Invalid service name {service!r}; expected a boto3 service id (letters, digits, hyphen).")
    if not _OPERATION_RE.match(operation):
        raise ValueError(f"Invalid operation {operation!r}; expected a snake_case boto3 client method name.")

    record = _session_record()
    client = _build_client(record, service, region)
    method = getattr(client, operation, None)
    if method is None or not callable(method):
        raise ValueError(
            f"No such client method {operation!r} on service {service!r}. "
            "Use boto3's snake_case names (see AWS service API docs / boto3 reference)."
        )

    params = parameters or {}
    try:
        response = method(**params)
    except TypeError as exc:
        raise ValueError(
            f"Bad parameters for {service}.{operation}: {exc}. " "Check required arguments in the AWS API / boto3 docs."
        ) from exc

    return {"response": _to_serializable(response)}
