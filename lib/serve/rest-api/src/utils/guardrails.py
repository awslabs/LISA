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

"""Utilities for managing and applying LiteLLM guardrails."""

import json
import os
import re
from collections.abc import Iterator
from typing import Any, Dict, List, Optional

import boto3
from fastapi.responses import JSONResponse
from loguru import logger


async def get_model_guardrails(model_id: str) -> List[Dict[str, Any]]:
    """
    Query the guardrails DynamoDB table for guardrails associated with a model.

    Parameters
    ----------
    model_id : str
        The model ID to query guardrails for.

    Returns
    -------
    List[Dict[str, Any]]
        List of guardrail configurations for the model. Returns empty list if no guardrails found.
    """
    try:
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
        guardrails_table = dynamodb.Table(os.environ["GUARDRAILS_TABLE_NAME"])

        # Query using the ModelIdIndex GSI
        response = guardrails_table.query(
            IndexName="ModelIdIndex",
            KeyConditionExpression="modelId = :modelId",
            ExpressionAttributeValues={":modelId": model_id},
        )

        guardrails = response.get("Items", [])
        logger.debug(f"Found {len(guardrails)} guardrails for model {model_id}")
        return guardrails  # type: ignore[no-any-return]

    except Exception as e:
        logger.error(f"Error fetching guardrails for model {model_id}: {e}")
        return []


def get_applicable_guardrails(user_groups: List[str], guardrails: List[Dict[str, Any]], model_id: str) -> List[str]:
    """
    Determine which guardrails apply to a user based on group membership.

    A guardrail applies if:
    - It has no allowed_groups (public guardrail, applies to everyone)
    - The user is a member of at least one of the guardrail's allowed_groups

    Parameters
    ----------
    user_groups : List[str]
        List of groups the user belongs to.

    guardrails : List[Dict[str, Any]]
        List of guardrail configurations from DynamoDB.

    model_id : str
        The model ID being invoked. Used to construct the full LiteLLM guardrail name.

    Returns
    -------
    List[str]
        List of LiteLLM guardrail names (format: {guardrail_name}-{model_id}) that should be applied to the request.
    """
    applicable_guardrails = []

    for guardrail in guardrails:
        # Skip guardrails marked for deletion
        if guardrail.get("markedForDeletion", False):
            continue

        allowed_groups = guardrail.get("allowedGroups", [])
        guardrail_name = guardrail.get("guardrailName")

        if not guardrail_name:
            logger.warning(f"Guardrail missing guardrailName field: {guardrail}")
            continue

        # Construct the full LiteLLM guardrail name (matches format used in create_model.py)
        litellm_guardrail_name = f"{guardrail_name}-{model_id}"

        # If no groups specified, guardrail is public (applies to everyone)
        if not allowed_groups:
            applicable_guardrails.append(litellm_guardrail_name)
            logger.debug(f"Applying public guardrail: {litellm_guardrail_name}")
            continue

        # Check if user has any matching group
        if any(group in allowed_groups for group in user_groups):
            applicable_guardrails.append(litellm_guardrail_name)
            logger.debug(f"Applying guardrail {litellm_guardrail_name} based on group membership")

    return applicable_guardrails


def is_guardrail_violation(error_msg: str) -> bool:
    """
    Check if an error message indicates a guardrail policy violation.

    Parameters
    ----------
    error_msg : str
        The error message to check.

    Returns
    -------
    bool
        True if the error message indicates a guardrail violation, False otherwise.
    """
    return "Violated guardrail policy" in error_msg


def extract_guardrail_response(error_msg: str) -> Optional[str]:
    """
    Extract the bedrock_guardrail_response from an error message.

    Parameters
    ----------
    error_msg : str
        The error message containing the guardrail response.

    Returns
    -------
    Optional[str]
        The extracted guardrail response text, or None if not found.
    """
    match = re.search(r"'bedrock_guardrail_response':\s*'([^']*)'", error_msg)
    return match.group(1) if match else None


def create_guardrail_streaming_response(guardrail_response: str, model_id: str, created: int = 0) -> Iterator[str]:
    """
    Generate streaming response chunks for a guardrail violation.

    Parameters
    ----------
    guardrail_response : str
        The guardrail response text to stream.
    model_id : str
        The model ID associated with the request.
    created : int, optional
        The creation timestamp, by default 0.

    Yields
    ------
    str
        Properly formatted SSE chunks for the guardrail response.
    """
    # First chunk with content
    response_chunk = {
        "id": "guardrail-response",
        "object": "chat.completion.chunk",
        "created": created,
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": guardrail_response},
                "finish_reason": None,
            }
        ],
        "lisa_guardrail_triggered": True,
    }
    yield f"data: {json.dumps(response_chunk)}\n\n"

    # Final chunk with finish_reason
    final_chunk = {
        "id": "guardrail-response",
        "object": "chat.completion.chunk",
        "created": created,
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
        "lisa_guardrail_triggered": True,
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"


def create_guardrail_json_response(guardrail_response: str, model_id: str, created: int = 0) -> JSONResponse:
    """
    Create a JSON response for a guardrail violation.

    Parameters
    ----------
    guardrail_response : str
        The guardrail response text.
    model_id : str
        The model ID associated with the request.
    created : int, optional
        The creation timestamp, by default 0.

    Returns
    -------
    JSONResponse
        A properly formatted JSON response for the guardrail violation.
    """
    response_data = {
        "id": "guardrail-response",
        "object": "chat.completion",
        "created": created,
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": guardrail_response},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "lisa_guardrail_triggered": True,
    }
    return JSONResponse(response_data, status_code=200)
