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

"""Lambda functions for managing user metrics."""
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
metrics_table = dynamodb.Table(os.environ["USER_METRICS_TABLE_NAME"])


@api_wrapper
def get_user_metrics(event: dict, context: dict) -> dict:
    """Get metrics for a specific user."""
    user_id = event.get("pathParameters", {}).get("userId")

    if not user_id:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing userId parameter"})}

    try:
        response = metrics_table.get_item(Key={"userId": user_id})

        metrics = {
            user_id: {
                "totalPrompts": response.get("Item", {}).get("totalPrompts", 0),
                "ragUsageCount": response.get("Item", {}).get("ragUsageCount", 0),
                "userGroups": list(response.get("Item", {}).get("userGroups", [])),
            }
        }
        return {"statusCode": 200, "body": metrics}
    except ClientError as e:
        logger.error(f"Error retrieving user metrics: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to retrieve metrics"})}


@api_wrapper
def get_global_metrics(event: dict, context: dict) -> dict:
    """Get aggregated metrics across all users."""
    try:
        # Scan entire metrics table
        response = metrics_table.scan()
        items = response.get("Items", [])

        # Calculate aggregated metrics
        total_prompts = sum(item.get("totalPrompts", 0) for item in items)
        total_rag_usage = sum(item.get("ragUsageCount", 0) for item in items)

        # Collect all unique user groups
        all_user_groups: Dict[str, int] = {}
        for item in items:
            if item.get("userGroups"):
                for group in item["userGroups"]:
                    all_user_groups[group] = all_user_groups.get(group, 0) + 1

        metrics = {
            "totalUniqueUsers": len(items),
            "totalPrompts": total_prompts,
            "totalRagUsage": total_rag_usage,
            "ragUsagePercentage": (total_rag_usage / total_prompts * 100) if total_prompts > 0 else 0,
            "userGroups": all_user_groups,
        }

        return {"statusCode": 200, "body": metrics}
    except ClientError as e:
        logger.error(f"Error retrieving global metrics: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to retrieve global metrics"})}


def count_unique_users_and_publish_metric() -> Any:
    """Count unique users in metrics table and publish to CloudWatch."""
    try:
        # Scan the table to get all users
        response = metrics_table.scan(Select="COUNT")
        unique_user_count = response["Count"]

        # Publish metric to CloudWatch
        cloudwatch.put_metric_data(
            Namespace="LISA/UserMetrics",
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
        response = metrics_table.scan(ProjectionExpression="userGroups")

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
            cloudwatch.put_metric_data(Namespace="LISA/UserMetrics", MetricData=metric_data)

        logger.info(f"Published user counts by group: {group_counts}")
        return group_counts

    except Exception as e:
        logger.error(f"Error publishing user counts by group: {e}")
        raise


def daily_metrics_handler(event: dict, context: dict) -> tuple:
    """Lambda handler function for scheduled (Daily) unique user metrics.

    This function is triggered by a daily EventBridge event and publishes metrics for:
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
        (unique_user_count, group_counts) containing the published metrics
    """
    return count_unique_users_and_publish_metric(), count_users_by_group_and_publish_metric()


def process_metrics_sqs_event(event: dict, context: dict) -> None:
    """Process SQS events and update user metrics.

    This function is triggered by SQS events containing session data.
    It extracts the necessary information and calls update_user_metrics.

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
            user_groups = message.get("userGroups", [])
            messages = message.get("messages", [])

            logger.info(f"Processing metrics for user: {user_id}, message contains {len(messages)} messages")

            # Check for RAG usage in messages
            has_rag_usage = check_rag_usage(messages)

            if user_id:
                logger.info(f"Updating metrics for user {user_id} from SQS event")
                update_user_metrics(user_id, has_rag_usage, user_groups)
            else:
                logger.error("SQS message missing required 'userId' field")
        except Exception as e:
            logger.error(f"Error processing SQS message: {str(e)}")


def check_rag_usage(messages: List[Dict[str, Any]]) -> bool:
    """Check if last human message in message history used RAG.

    Parameters:
    -----------
    messages : List[Dict[str, Any]]
        List of message objects to check

    Returns:
    --------
    bool
        True if RAG was used in last human message, False otherwise
    """
    if not messages:
        return False

    # Find the last human message
    for i in range(len(messages) - 1, -1, -1):
        message = messages[i]
        if isinstance(message, dict) and message.get("type") == "human":
            metadata = message.get("metadata", {})
            if metadata and (metadata.get("ragContext") or metadata.get("ragDocuments")):
                return True
            break  # Exit after checking the last human message
    return False


def update_user_metrics(user_id: str, has_rag_usage: bool, user_groups: List[str]) -> None:
    """Update metrics for a given user

    Parameters:
    -----------
    user_id : str
        The user ID to update metrics for
    has_rag_usage : bool, optional
        Whether this prompt used RAG functionality
    user_groups : List[str]
        The groups that the user is apart of
    """
    table_name = os.environ.get("USER_METRICS_TABLE_NAME")

    if not table_name:
        return

    try:
        response = metrics_table.get_item(Key={"userId": user_id})
        user_exists = "Item" in response

        # Initialize user data if new user
        if not user_exists:
            metrics_table.put_item(
                Item={
                    "userId": user_id,
                    "totalPrompts": 1,
                    "ragUsageCount": 1 if has_rag_usage else 0,
                    "firstSeen": datetime.now().isoformat(),
                    "lastSeen": datetime.now().isoformat(),
                    "userGroups": set(user_groups) if user_groups else None,
                }
            )
        else:
            update_expression = "SET lastSeen = :now, totalPrompts = totalPrompts + :inc"
            expression_values = {":now": datetime.now().isoformat(), ":inc": 1}

            if has_rag_usage:
                update_expression += ", ragUsageCount = if_not_exists(ragUsageCount, :zero) + :inc"
                expression_values[":zero"] = 0

            if user_groups:
                update_expression += ", userGroups = :groups"
                expression_values[":groups"] = set(user_groups)

            metrics_table.update_item(
                Key={"userId": user_id}, UpdateExpression=update_expression, ExpressionAttributeValues=expression_values
            )
    except ClientError as e:
        logger.error(f"Failed to update metrics for user {user_id}: {e}")

    # Publish CloudWatch metrics
    try:
        metric_data = [
            {"MetricName": "TotalPromptCount", "Value": 1, "Unit": "Count", "Timestamp": datetime.now()},
            {
                "MetricName": "UserPromptCount",
                "Dimensions": [{"Name": "UserId", "Value": user_id}],
                "Value": 1,
                "Unit": "Count",
                "Timestamp": datetime.now(),
            },
        ]
        if has_rag_usage:
            metric_data.append(
                {"MetricName": "RAGUsageCount", "Value": 1, "Unit": "Count", "Timestamp": datetime.now()}
            )
            metric_data.append(
                {
                    "MetricName": "UserRAGUsageCount",
                    "Dimensions": [{"Name": "UserId", "Value": user_id}],
                    "Value": 1,
                    "Unit": "Count",
                    "Timestamp": datetime.now(),
                }
            )

        cloudwatch.put_metric_data(Namespace="LISA/UserMetrics", MetricData=metric_data)
    except Exception as e:
        logger.error(f"Failed to publish CloudWatch metrics: {e}")
