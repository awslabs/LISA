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

import boto3
import create_env_variables  # noqa: F401
from botocore.exceptions import ClientError
from utilities.common_functions import api_wrapper, retry_config

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
metrics_table = dynamodb.Table(os.environ["USER_METRICS_TABLE_NAME"])

@api_wrapper
def get_user_metrics(event: dict, context: dict) -> dict:
    """Get metrics for a specific user."""
    user_id = event.get("pathParameters", {}).get("userId")
    if not user_id:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing userId parameter"})}
    
    try:
        response = metrics_table.get_item(Key={"userId": user_id})
        return response.get("Item", {})
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
        metrics = {
            "totalUniqueUsers": len(items),
            "totalPrompts": sum(item.get("totalPrompts", 0) for item in items),
        }
        return metrics
    except ClientError as e:
        logger.error(f"Error retrieving global metrics: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to retrieve global metrics"})}
