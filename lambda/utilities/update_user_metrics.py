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

"""Utility for updating user metrics."""
import logging
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Union

import boto3
from botocore.exceptions import ClientError
from utilities.common_functions import retry_config, get_groups

logger = logging.getLogger(__name__)

cloudwatch = boto3.client('cloudwatch', region_name=os.environ["AWS_REGION"])

def process_sqs_event(event: Dict[str, Any], context: Dict[str, Any]) -> None:
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
    
    for record in event.get('Records', []):
        try:
            # Parse the message body
            message = json.loads(record['body'])
            
            # Extract userId and userGroups
            user_id = message.get('userId')
            user_groups = message.get('userGroups', [])
            messages = message.get('messages', [])
            
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
    """Check if any human messages in the list used RAG.
    
    Parameters:
    -----------
    messages : List[Dict[str, Any]]
        List of message objects to check
    
    Returns:
    --------
    bool
        True if RAG was used in any human message, False otherwise
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

def update_user_metrics(user_id: str, has_rag_usage: bool = False, user_groups: List[str] = []) -> None:
    """Update user metrics for prompt usage.
    
    Parameters:
    -----------
    user_id : str
        The user ID to update metrics for
    has_rag_usage : bool, optional
        Whether this prompt used RAG functionality, by default False
    """
    table_name = os.environ.get("USER_METRICS_TABLE_NAME")
    if not table_name:
        return
    try:
        dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
        metrics_table = dynamodb.Table(table_name)
        now = datetime.now().isoformat()
        
        response = metrics_table.get_item(Key={"userId": user_id})
        user_exists = "Item" in response

        # user group handling
        
        if not user_exists:
            metrics_table.put_item(
                Item={
                    "userId": user_id, 
                    "totalPrompts": 1, 
                    "ragUsageCount": 1 if has_rag_usage else 0, 
                    "firstSeen": now, 
                    "lastSeen": now,
                    "userGroups": set(user_groups) if user_groups else None
                }
            )
        else:
            update_expression = "SET lastSeen = :now, totalPrompts = totalPrompts + :inc"
            expression_values = {":now": now, ":inc": 1}
            
            if has_rag_usage:
                update_expression += ", ragUsageCount = if_not_exists(ragUsageCount, :zero) + :inc"
                expression_values[":zero"] = 0

            if user_groups:
                update_expression += ", userGroups = :groups"
                expression_values[":groups"] = set(user_groups)
            
            metrics_table.update_item(
                Key={"userId": user_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
    except ClientError as e:
        logger.error(f"Failed to update metrics for user {user_id}: {e}")
    
    # Publish CloudWatch metrics
    try:
        metric_data = [
            {
                'MetricName': 'TotalPromptCount',
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now()
            },
            {
                'MetricName': 'UserPromptCount',
                'Dimensions': [
                    {
                        'Name': 'UserId',
                        'Value': user_id
                    }
                ],
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now()
            }
        ]
        
        if has_rag_usage:
            metric_data.append({
                'MetricName': 'RAGUsageCount',
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now()
            })
            
            metric_data.append({
                'MetricName': 'UserRAGUsageCount',
                'Dimensions': [
                    {
                        'Name': 'UserId',
                        'Value': user_id
                    }
                ],
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now()
            })
            
        cloudwatch.put_metric_data(
            Namespace='LISA/UserMetrics',
            MetricData=metric_data
        )
    except Exception as e:
        logger.error(f"Failed to publish CloudWatch metrics: {e}")
