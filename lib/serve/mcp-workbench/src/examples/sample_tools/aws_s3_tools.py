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

from __future__ import annotations

from typing import Any

import boto3
from mcpworkbench.aws import shared_session_service as _session_service
from mcpworkbench.aws.identity import CallerIdentityError, get_caller_identity
from mcpworkbench.aws.session_models import AwsSessionRecord
from mcpworkbench.aws.session_service import AwsSessionMissingError
from mcpworkbench.core.annotations import mcp_tool


def _build_s3_client(record: AwsSessionRecord) -> Any:
    return boto3.client(
        "s3",
        aws_access_key_id=record.aws_access_key_id,
        aws_secret_access_key=record.aws_secret_access_key,
        aws_session_token=record.aws_session_token,
        region_name=record.aws_region,
    )


@mcp_tool(
    name="aws_list_s3_buckets",
    description=(
        "List S3 buckets using the connected AWS session credentials. "
        "No parameters are required — the caller's identity is determined "
        "automatically from the authenticated session."
    ),
)
def aws_list_s3_buckets() -> dict[str, list[str]]:
    """List S3 buckets for the current AWS session.

    Identity (user_id, session_id) is extracted automatically from the
    HTTP request headers — the LLM does not need to supply them.
    """
    try:
        identity = get_caller_identity()
    except CallerIdentityError as exc:
        raise RuntimeError(
            "Could not determine caller identity from the request. "
            "Ensure the MCP connection sends Authorization and X-Session-Id headers."
        ) from exc

    try:
        record = _session_service.get_aws_session_for_user(identity.user_id, identity.session_id)
    except AwsSessionMissingError as exc:
        raise RuntimeError("AWS session not connected or expired.") from exc

    s3 = _build_s3_client(record)
    response = s3.list_buckets()
    buckets = [b["Name"] for b in response.get("Buckets", [])]
    return {"buckets": buckets}
