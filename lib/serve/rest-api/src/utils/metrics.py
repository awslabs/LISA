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

"""Metrics utilities for publishing usage data."""

import logging
import os
import uuid
from datetime import datetime

import boto3
from auth import get_user_context, is_api_user
from fastapi import Request
from utils.metrics_models import MetricsEvent

logger = logging.getLogger(__name__)

sqs_client = boto3.client("sqs", region_name=os.environ["AWS_REGION"])


def extract_messages_for_metrics(params: dict) -> list[dict]:
    """
    Extract messages from chat completion request parameters.

    Args:
        params: The request parameters containing messages

    Returns:
        List of message dictionaries suitable for metrics calculation
    """
    messages = params.get("messages", [])

    # Convert to a format that matches what session lambda sends
    formatted_messages = []
    for msg in messages:
        role = msg.get("role", "user")

        # Map OpenAI roles to LISA message types
        if role == "user":
            msg_type = "human"
        elif role == "assistant":
            msg_type = "ai"
        elif role == "system":
            msg_type = "system"
        else:
            msg_type = role

        # Extract content - handle both string and array formats
        content = msg.get("content", "")
        content_text = ""

        if isinstance(content, str):
            # Simple string content (from direct API calls)
            content_text = content
        elif isinstance(content, list):
            # Array of content objects (from UI)
            # Extract text from all text-type content items
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    content_text += item.get("text", "") + " "
            content_text = content_text.strip()

        formatted_msg = {
            "type": msg_type,
            "content": content,  # Keep original format for session compatibility
            "metadata": {},
        }

        # Check if this message has RAG context in the extracted text
        # RAG context is typically indicated by "File context:" in the message
        if content_text and "file context:" in content_text.lower():
            # Mark this message as using RAG
            formatted_msg["metadata"]["ragContext"] = True

        # Handle tool calls if present (for MCP metrics)
        if "tool_calls" in msg:
            formatted_msg["toolCalls"] = msg["tool_calls"]

        formatted_messages.append(formatted_msg)

    return formatted_messages


def extract_token_usage(response_body: dict | None) -> tuple[int | None, int | None]:
    """
    Extract token usage from a LLM response body (non-streaming or SSE chunk).

    The usage structure is identical in both cases — LiteLLM normalises it:
        {"usage": {"prompt_tokens": N, "completion_tokens": N, ...}, ...}

    Args:
        response_body: The parsed JSON response or SSE chunk from LiteLLM

    Returns:
        Tuple of (prompt_tokens, completion_tokens), each int or None.
    """
    if not response_body:
        return None, None

    usage = response_body.get("usage")
    if not usage:
        return None, None

    return usage.get("prompt_tokens"), usage.get("completion_tokens")


def publish_metrics_event(
    request: Request,
    params: dict,
    response_status: int,
    response_body: dict | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> None:
    """
    Publish metrics event to SQS queue for API users.

    Includes both message-level metrics (for prompt/RAG/MCP counting) and
    token-level metrics (prompt_tokens, completion_tokens) if available.

    Args:
        request: The FastAPI request object
        params: The request parameters (contains messages and model)
        response_status: HTTP response status code
        response_body: Optional parsed response JSON (used to extract tokens for non-streaming)
        prompt_tokens: Optional prompt token count (provided directly for streaming)
        completion_tokens: Optional completion token count (provided directly for streaming)
    """
    # Only publish metrics for successful completions
    if response_status != 200:
        return

    # Only publish if metrics queue is configured
    queue_url = os.environ.get("USAGE_METRICS_QUEUE_URL")
    if not queue_url:
        logger.debug("Metrics queue URL not configured, skipping metrics")
        return

    try:
        username, groups = get_user_context(request)
        model_id = params.get("model")

        # If token counts were not passed directly, try to extract from response_body
        if prompt_tokens is None and response_body is not None:
            prompt_tokens, completion_tokens = extract_token_usage(response_body)

        is_jwt_user = not is_api_user(request)

        if is_jwt_user:
            # JWT/UI user: the session lambda already publishes prompt/RAG/MCP metrics with the
            # real sessionId. The passthrough only supplies the token counts that the session
            # lambda cannot see (they come from the LLM response, not the session history).
            # Skip entirely if there are no token counts to add.
            if prompt_tokens is None and completion_tokens is None:
                logger.debug("No token data for JWT user, skipping passthrough metrics publish")
                return
            messages = []  # Prevent double-counting prompts — session lambda owns this
            session_id = f"ui-tokens-{uuid.uuid4().hex}"
            event_type = "token_only"
        else:
            # API token user: publish full messages + tokens.
            # The session lambda does not run for API users, so the passthrough owns all metrics.
            messages = extract_messages_for_metrics(params)
            session_id = f"api-{uuid.uuid4().hex}"
            event_type = "full"

        # Build and validate the event through the Pydantic model before publishing
        metrics_event = MetricsEvent(
            userId=username,
            sessionId=session_id,
            messages=messages,
            userGroups=groups,
            timestamp=datetime.now().isoformat(),
            eventType=event_type,
            modelId=model_id,
            promptTokens=prompt_tokens,
            completionTokens=completion_tokens,
        )

        # Publish to SQS — exclude None fields to keep the message lean
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=metrics_event.model_dump_json(exclude_none=True),
        )

        logger.info(
            f"Published metrics event for user: {username} "
            f"tokens: prompt={prompt_tokens} completion={completion_tokens}"
        )

    except Exception as e:
        # Don't fail the request if metrics publishing fails
        logger.error(f"Failed to publish metrics event: {e}")
