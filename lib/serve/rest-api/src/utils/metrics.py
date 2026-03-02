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

import json
import logging
import os
import uuid
from datetime import datetime

import boto3
from auth import get_user_context
from fastapi import Request

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


def publish_metrics_event(request: Request, params: dict, response_status: int) -> None:
    """
    Publish metrics event to SQS queue for API users

    Args:
        request: The FastAPI request object
        params: The request parameters
        response_status: HTTP response status code
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
        messages = extract_messages_for_metrics(params)

        # Generate a synthetic session ID for API users
        session_id = f"api-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:8]}"

        # Create metrics event in the same format as session lambda
        metrics_event = {
            "userId": username,
            "sessionId": session_id,
            "messages": messages,
            "userGroups": groups,
            "timestamp": datetime.now().isoformat(),
        }

        # Publish to SQS
        sqs_client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(metrics_event))

        logger.info(f"Published metrics event for API user: {username}")

    except Exception as e:
        # Don't fail the request if metrics publishing fails
        logger.error(f"Failed to publish metrics event: {e}")
