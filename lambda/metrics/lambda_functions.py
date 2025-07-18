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

"""Lambda functions for managing usage metrics."""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import boto3
import create_env_variables  # noqa: F401
from botocore.exceptions import ClientError
from utilities.common_functions import api_wrapper, retry_config

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
cloudwatch = boto3.client("cloudwatch", region_name=os.environ["AWS_REGION"])
usage_metrics_table = dynamodb.Table(os.environ["USAGE_METRICS_TABLE_NAME"])


@api_wrapper
def get_user_metrics(event: dict, context: dict) -> dict:
    """Get usage metrics for a specific user."""
    user_id = event.get("pathParameters", {}).get("userId")

    if not user_id:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing userId parameter"})}

    try:
        response = usage_metrics_table.get_item(Key={"userId": user_id})
        item = response.get("Item", {})

        metrics = {
            user_id: {
                "totalPrompts": item.get("totalPrompts", 0),
                "ragUsageCount": item.get("ragUsageCount", 0),
                "mcpToolCallsCount": item.get("mcpToolCallsCount", 0),
                "mcpToolUsage": item.get("mcpToolUsage", {}),
                "userGroups": list(item.get("userGroups", [])),
                "sessionMetrics": item.get("sessionMetrics", {}),
                "firstSeen": item.get("firstSeen"),
                "lastSeen": item.get("lastSeen"),
            }
        }
        return {"statusCode": 200, "body": metrics}
    except ClientError as e:
        logger.error(f"Error retrieving user metrics: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to retrieve metrics"})}


@api_wrapper
def get_user_metrics_all(event: dict, context: dict) -> dict:
    """Get aggregated usage metrics across all users."""
    try:
        # Scan entire usage metrics table
        response = usage_metrics_table.scan()
        items = response.get("Items", [])

        # Calculate aggregated metrics
        total_prompts = sum(item.get("totalPrompts", 0) for item in items)
        total_rag_usage = sum(item.get("ragUsageCount", 0) for item in items)
        total_mcp_tool_calls = sum(item.get("mcpToolCallsCount", 0) for item in items)

        # Collect all unique user groups
        all_user_groups: Dict[str, int] = {}
        for item in items:
            if item.get("userGroups"):
                for group in item["userGroups"]:
                    all_user_groups[group] = all_user_groups.get(group, 0) + 1

        # Collect all MCP tool usage across users
        all_mcp_tool_usage: Dict[str, int] = {}
        for item in items:
            if item.get("mcpToolUsage"):
                for tool_name, count in item["mcpToolUsage"].items():
                    all_mcp_tool_usage[tool_name] = all_mcp_tool_usage.get(tool_name, 0) + count

        metrics = {
            "totalUniqueUsers": len(items),
            "totalPrompts": total_prompts,
            "totalRagUsage": total_rag_usage,
            "ragUsagePercentage": (total_rag_usage / total_prompts * 100) if total_prompts > 0 else 0,
            "totalMCPToolCalls": total_mcp_tool_calls,
            "mcpToolCallsPercentage": (total_mcp_tool_calls / total_prompts * 100) if total_prompts > 0 else 0,
            "mcpToolUsage": all_mcp_tool_usage,
            "userGroups": all_user_groups,
        }

        return {"statusCode": 200, "body": metrics}
    except ClientError as e:
        logger.error(f"Error retrieving user metrics: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to retrieve user metrics"})}


def count_unique_users_and_publish_metric() -> Any:
    """Count unique users in usage metrics table and publish to CloudWatch."""
    try:
        # Scan the table to get all users
        response = usage_metrics_table.scan(Select="COUNT")
        unique_user_count = response["Count"]

        # Publish metric to CloudWatch
        cloudwatch.put_metric_data(
            Namespace="LISA/UsageMetrics",
            MetricData=[
                {"MetricName": "UniqueUsers", "Value": unique_user_count, "Unit": "Count", "Timestamp": datetime.now()}
            ],
        )
        logger.info(f"Published unique users metric: {unique_user_count}")
        return unique_user_count
    except Exception as e:
        logger.error(f"Error publishing unique users metric: {e}")
        raise


def count_users_by_group_and_publish_metric() -> Dict[str, int]:
    """Count users in each group and publish metrics to CloudWatch."""
    try:
        # Scan the table to get users with groups
        response = usage_metrics_table.scan(ProjectionExpression="userGroups")

        # Count users in each group
        group_counts: Dict[str, int] = {}
        for item in response.get("Items", []):
            if "userGroups" in item:
                for group in item["userGroups"]:
                    group_counts[group] = group_counts.get(group, 0) + 1

        # Publish metrics to CloudWatch
        timestamp = datetime.now()
        metric_data = []

        for group, count in group_counts.items():
            metric_data.append(
                {
                    "MetricName": "UsersPerGroup",
                    "Dimensions": [{"Name": "GroupName", "Value": group}],
                    "Value": count,
                    "Unit": "Count",
                    "Timestamp": timestamp,
                }
            )

        if metric_data:
            cloudwatch.put_metric_data(Namespace="LISA/UsageMetrics", MetricData=metric_data)

        logger.info(f"Published user counts by group: {group_counts}")
        return group_counts

    except Exception as e:
        logger.error(f"Error publishing user counts by group: {e}")
        raise


def daily_metrics_handler(event: dict, context: dict) -> tuple:
    """Lambda handler function for scheduled (Daily) unique user usage metrics.

    This function is triggered by a daily EventBridge event and publishes usage metrics for:
    1. Count of unique users in the system
    2. Counts of users by group membership

    Parameters:
    -----------
    event : dict
        The EventBridge event
    context : dict
        Lambda execution context

    Returns:
    --------
    tuple
        (unique_user_count, group_counts) containing the published usage metrics
    """
    return count_unique_users_and_publish_metric(), count_users_by_group_and_publish_metric()


def process_metrics_sqs_event(event: dict, context: dict) -> None:
    """Process SQS events and update usage metrics.

    This function is triggered by SQS events containing session data.
    It extracts the necessary information and calls update_user_metrics_by_session.

    Parameters:
    -----------
    event : Dict[str, Any]
        The SQS event containing records to process
    context : Dict[str, Any]
        Lambda execution context
    """
    logger.info(f"Processing SQS event with {len(event.get('Records', []))} records")

    for record in event.get("Records", []):
        try:
            # Parse the message body
            message = json.loads(record["body"])

            user_id = message.get("userId")
            session_id = message.get("sessionId")
            user_groups = message.get("userGroups", [])
            messages = message.get("messages", [])

            logger.info(f"Processing metrics for user: {user_id}, session: {session_id}.")

            if not user_id:
                logger.error("SQS message missing required 'userId' field")
                continue

            if not session_id:
                logger.error("SQS message missing required 'sessionId' field")
                continue

            # Calculate metrics for a given session
            session_metrics = calculate_session_metrics(messages)

            logger.info(f"Calculated session metrics: {session_metrics}")

            # Update usage metrics for given session
            update_user_metrics_by_session(user_id, session_id, session_metrics, user_groups)

        except Exception as e:
            logger.error(f"Error processing SQS message: {str(e)}")


def count_rag_usage(messages: List[Dict[str, Any]]) -> int:
    """Count occurrences of 'File context:' in all human messages to determine RAG usage.

    Parameters:
    -----------
    messages : List[Dict[str, Any]]
        List of message objects to check

    Returns:
    --------
    int
        Count of 'File context:' occurrences across all human messages
    """
    if not messages:
        return 0

    file_context_count = 0

    for message in messages:
        if not isinstance(message, dict):
            continue

        # Check if this is a human message
        is_human = False
        if isinstance(message.get("type"), dict) and message["type"].get("S") == "human":
            is_human = True
        elif message.get("type") == "human":
            is_human = True

        if not is_human:
            continue

        # Extract content and search for "File context:"
        content = message.get("content")

        if isinstance(content, dict) and content.get("L"):
            # DynamoDB format - content is {"L": [{"M": {"text": {"S": "..."}}}]}
            for content_item in content["L"]:
                if isinstance(content_item, dict) and content_item.get("M"):
                    text_obj = content_item["M"].get("text", {})
                    if isinstance(text_obj, dict) and text_obj.get("S"):
                        text_content = text_obj["S"]
                        file_context_count += text_content.lower().count("file context:")
        elif isinstance(content, list):
            # Direct format - content is a list of content objects
            for content_item in content:
                if isinstance(content_item, dict) and content_item.get("text"):
                    text_content = content_item["text"]
                    file_context_count += text_content.lower().count("file context:")
        elif isinstance(content, str):
            # Simple string content
            file_context_count += content.lower().count("file context:")

    return file_context_count


def calculate_session_metrics(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate metrics for a complete session.

    Parameters:
    -----------
    messages : List[Dict[str, Any]]
        List of message objects to analyze

    Returns:
    --------
    Dict[str, Any]
        Dictionary containing session metrics
    """
    if not messages:
        return {"totalPrompts": 0, "ragUsage": 0, "mcpToolCallsCount": 0, "mcpToolUsage": {}}

    total_prompts = 0
    mcp_tool_usage: Dict[str, int] = {}

    # Count human messages for total prompts
    for message in messages:
        if isinstance(message, dict):
            # Check for human messages (DynamoDB format)
            if isinstance(message.get("type"), dict) and message["type"].get("S") == "human":
                total_prompts += 1
            # Check for direct type field
            elif message.get("type") == "human":
                total_prompts += 1

            # Check for MCP tool calls in toolCalls array
            tool_calls = message.get("toolCalls", [])

            if isinstance(tool_calls, dict) and tool_calls.get("L"):
                # DynamoDB format - toolCalls is {"L": [...]}
                for tool_call_item in tool_calls["L"]:
                    tool_call = tool_call_item.get("M", {})
                    if isinstance(tool_call.get("type"), dict) and tool_call["type"].get("S") == "tool_call":
                        # Extract tool name
                        name_obj = tool_call.get("name", {})
                        if isinstance(name_obj, dict) and name_obj.get("S"):
                            tool_name = name_obj["S"]
                            mcp_tool_usage[tool_name] = mcp_tool_usage.get(tool_name, 0) + 1
            elif isinstance(tool_calls, list):
                # Direct format - toolCalls is a list
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict) and tool_call.get("type") == "tool_call":
                        tool_name = tool_call.get("name")
                        if tool_name:
                            mcp_tool_usage[tool_name] = mcp_tool_usage.get(tool_name, 0) + 1

    # Calculate RAG usage by counting "File context:" occurrences
    rag_usage_count = count_rag_usage(messages)

    return {
        "totalPrompts": total_prompts,
        "ragUsage": rag_usage_count,
        "mcpToolCallsCount": sum(mcp_tool_usage.values()),
        "mcpToolUsage": mcp_tool_usage,
    }


def publish_metric_deltas(
    user_id: str,
    delta_prompts: int,
    delta_rag: int,
    delta_mcp_calls: int,
    delta_mcp_usage: Dict[str, int],
    user_groups: List[str],
) -> None:
    """Publish only metric deltas to CloudWatch to prevent double counting.

    Parameters:
    -----------
    user_id : str
        The user ID
    delta_prompts : int
        Change in prompt count
    delta_rag : int
        Change in RAG usage
    delta_mcp_calls : int
        Change in MCP tool calls
    delta_mcp_usage : Dict[str, int]
        Changes in individual MCP tool usage
    user_groups : List[str], optional
        The groups that the user belongs to
    """
    try:
        timestamp = datetime.now()
        metric_data = []

        # Only publish metrics that actually changed
        if delta_prompts != 0:
            metric_data.extend(
                [
                    {"MetricName": "TotalPromptCount", "Value": delta_prompts, "Unit": "Count", "Timestamp": timestamp},
                    {
                        "MetricName": "UserPromptCount",
                        "Dimensions": [{"Name": "UserId", "Value": user_id}],
                        "Value": delta_prompts,
                        "Unit": "Count",
                        "Timestamp": timestamp,
                    },
                ]
            )

        if delta_rag != 0:
            metric_data.extend(
                [
                    {"MetricName": "RAGUsageCount", "Value": delta_rag, "Unit": "Count", "Timestamp": timestamp},
                    {
                        "MetricName": "UserRAGUsageCount",
                        "Dimensions": [{"Name": "UserId", "Value": user_id}],
                        "Value": delta_rag,
                        "Unit": "Count",
                        "Timestamp": timestamp,
                    },
                ]
            )

        if delta_mcp_calls != 0:
            metric_data.extend(
                [
                    {
                        "MetricName": "TotalMCPToolCalls",
                        "Value": delta_mcp_calls,
                        "Unit": "Count",
                        "Timestamp": timestamp,
                    },
                    {
                        "MetricName": "UserMCPToolCalls",
                        "Dimensions": [{"Name": "UserId", "Value": user_id}],
                        "Value": delta_mcp_calls,
                        "Unit": "Count",
                        "Timestamp": timestamp,
                    },
                ]
            )

        # Individual tool metrics
        for tool_name, delta_count in delta_mcp_usage.items():
            if delta_count != 0:
                metric_data.append(
                    {
                        "MetricName": "MCPToolCallsByTool",
                        "Dimensions": [{"Name": "ToolName", "Value": tool_name}],
                        "Value": delta_count,
                        "Unit": "Count",
                        "Timestamp": timestamp,
                    }
                )

        # Group-level metrics
        if user_groups:
            for group in user_groups:
                if delta_prompts != 0:
                    metric_data.append(
                        {
                            "MetricName": "GroupPromptCount",
                            "Dimensions": [{"Name": "GroupName", "Value": group}],
                            "Value": delta_prompts,
                            "Unit": "Count",
                            "Timestamp": timestamp,
                        }
                    )

                if delta_rag != 0:
                    metric_data.append(
                        {
                            "MetricName": "GroupRAGUsageCount",
                            "Dimensions": [{"Name": "GroupName", "Value": group}],
                            "Value": delta_rag,
                            "Unit": "Count",
                            "Timestamp": timestamp,
                        }
                    )

                if delta_mcp_calls != 0:
                    metric_data.append(
                        {
                            "MetricName": "GroupMCPToolCalls",
                            "Dimensions": [{"Name": "GroupName", "Value": group}],
                            "Value": delta_mcp_calls,
                            "Unit": "Count",
                            "Timestamp": timestamp,
                        }
                    )

        if metric_data:
            cloudwatch.put_metric_data(Namespace="LISA/UsageMetrics", MetricData=metric_data)
            logger.info(f"Published {len(metric_data)} metric deltas for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to publish metric deltas: {e}")


def update_user_metrics_by_session(
    user_id: str, session_id: str, session_metrics: Dict[str, Any], user_groups: List[str]
) -> None:
    """Update usage metrics for a given user based on session-level metrics.

    Parameters:
    -----------
    user_id : str
        The user ID to update usage metrics for
    session_id : str
        The session ID being updated
    session_metrics : Dict[str, Any]
        Calculated metrics for this session
    user_groups : List[str]
        The groups that the user is apart of
    """
    table_name = os.environ.get("USAGE_METRICS_TABLE_NAME")

    if not table_name:
        return

    try:
        # Get existing user data
        response = usage_metrics_table.get_item(Key={"userId": user_id})
        existing_item = response.get("Item", {})
        user_exists = "Item" in response

        # Get existing session metrics for this specific session
        existing_session_metrics = existing_item.get("sessionMetrics", {}).get(
            session_id, {"totalPrompts": 0, "ragUsage": 0, "mcpToolCallsCount": 0, "mcpToolUsage": {}}
        )

        # Calculate deltas
        delta_prompts = session_metrics["totalPrompts"] - existing_session_metrics.get("totalPrompts", 0)
        delta_rag = session_metrics["ragUsage"] - existing_session_metrics.get("ragUsage", 0)
        delta_mcp_calls = session_metrics["mcpToolCallsCount"] - existing_session_metrics.get("mcpToolCallsCount", 0)

        # Calculate MCP tool usage deltas
        existing_mcp_usage = existing_session_metrics.get("mcpToolUsage", {})
        new_mcp_usage = session_metrics["mcpToolUsage"]
        delta_mcp_usage = {}
        for tool_name, count in new_mcp_usage.items():
            old_count = existing_mcp_usage.get(tool_name, 0)
            delta = count - old_count
            if delta != 0:
                delta_mcp_usage[tool_name] = delta

        # Publish only deltas to CloudWatch (prevents double counting)
        if delta_prompts != 0 or delta_rag != 0 or delta_mcp_calls != 0 or delta_mcp_usage:
            publish_metric_deltas(user_id, delta_prompts, delta_rag, delta_mcp_calls, delta_mcp_usage, user_groups)

        # Update DynamoDB with session-based metrics
        if not user_exists:
            # Create new user with session metrics
            item = {
                "userId": user_id,
                "totalPrompts": session_metrics["totalPrompts"],
                "ragUsageCount": session_metrics["ragUsage"],
                "mcpToolCallsCount": session_metrics["mcpToolCallsCount"],
                "mcpToolUsage": session_metrics["mcpToolUsage"],
                "sessionMetrics": {session_id: session_metrics},
                "firstSeen": datetime.now().isoformat(),
                "lastSeen": datetime.now().isoformat(),
                "userGroups": set(user_groups) if user_groups else None,
            }
            usage_metrics_table.put_item(Item=item)
        else:
            # Update existing user
            all_session_metrics = existing_item.get("sessionMetrics", {})
            all_session_metrics[session_id] = session_metrics

            # Recalculate aggregate totals from all sessions
            total_prompts = sum(sm.get("totalPrompts", 0) for sm in all_session_metrics.values())
            total_rag = sum(sm.get("ragUsage", 0) for sm in all_session_metrics.values())
            total_mcp_calls = sum(sm.get("mcpToolCallsCount", 0) for sm in all_session_metrics.values())

            # Aggregate MCP tool usage across all sessions
            aggregate_mcp_usage: Dict[str, int] = {}
            for sm in all_session_metrics.values():
                for tool_name, count in sm.get("mcpToolUsage", {}).items():
                    aggregate_mcp_usage[tool_name] = aggregate_mcp_usage.get(tool_name, 0) + count

            # Update the user record
            usage_metrics_table.update_item(
                Key={"userId": user_id},
                UpdateExpression="SET lastSeen = :now, totalPrompts = :total_prompts, ragUsageCount = :total_rag, "
                "mcpToolCallsCount = :total_mcp, mcpToolUsage = :mcp_usage, "
                "sessionMetrics = :session_metrics, userGroups = :groups",
                ExpressionAttributeValues={
                    ":now": datetime.now().isoformat(),
                    ":total_prompts": total_prompts,
                    ":total_rag": total_rag,
                    ":total_mcp": total_mcp_calls,
                    ":mcp_usage": aggregate_mcp_usage,
                    ":session_metrics": all_session_metrics,
                    ":groups": set(user_groups) if user_groups else existing_item.get("userGroups", set()),
                },
            )
    except ClientError as e:
        logger.error(f"Failed to update session metrics for user {user_id}: {e}")
