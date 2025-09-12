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

"""Lambda functions for managing sessions."""
import json
import logging
import os
import time
from decimal import Decimal
from typing import Any, Dict

import boto3
import create_env_variables  # noqa: F401
from botocore.exceptions import ClientError
from utilities.common_functions import api_wrapper, retry_config

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["CONFIG_TABLE_NAME"])


@api_wrapper
def get_configuration(event: dict, context: dict) -> Dict[str, Any]:
    """List configuration entries by configScope from DynamoDB."""
    config_scope = event["queryStringParameters"]["configScope"]

    response = {}
    try:
        response = table.query(
            KeyConditionExpression="#s = :configScope",
            ExpressionAttributeNames={"#s": "configScope"},
            ExpressionAttributeValues={":configScope": config_scope},
            ScanIndexForward=False,
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No record found with session id: {config_scope}")
        else:
            logger.exception("Error fetching session")
    return response.get("Items", {})  # type: ignore [no-any-return]


def _convert_floats_to_decimals(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {key: _convert_floats_to_decimals(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimals(item) for item in obj]
    else:
        return obj


def _invalidate_session_encryption_cache() -> None:
    """Invalidate session encryption cache across Lambda functions.

    This function sends a signal to clear the session encryption cache
    in both session and encryption Lambda functions when global configuration
    is updated.
    """
    try:
        # Use SQS or SNS to notify other Lambda functions to clear their cache
        # For now, we'll use a simple approach with SSM Parameter Store
        import boto3

        ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"])

        # Update a parameter that indicates cache should be invalidated
        # Lambda functions can check this timestamp against their cache timestamp
        current_time = str(int(time.time()))

        try:
            ssm_client.put_parameter(
                Name="/lisa/cache/session-encryption-invalidation",
                Value=current_time,
                Type="String",
                Overwrite=True,
                Description="Timestamp when session encryption cache should be invalidated",
            )
            logger.info("Updated session encryption cache invalidation timestamp")
        except ClientError as e:
            logger.warning(f"Failed to update cache invalidation parameter: {e}")

    except Exception as e:
        logger.error(f"Error invalidating session encryption cache: {e}")


@api_wrapper
def update_configuration(event: dict, context: dict) -> None:
    """Update configuration in DynamoDB."""
    # Parse JSON with float/int types for proper type preservation
    body = json.loads(event["body"], parse_float=float, parse_int=int)

    # Convert floats to Decimals for DynamoDB compatibility
    body = _convert_floats_to_decimals(body)

    body["created_at"] = str(Decimal(time.time()))

    try:
        table.put_item(Item=body)

        # If this is a global configuration update that might affect session encryption,
        # invalidate the cache
        if (
            body.get("configScope") == "global"
            and "configuration" in body
            and "enabledComponents" in body.get("configuration", {})
            and "encryptSession" in body.get("configuration", {}).get("enabledComponents", {})
        ):
            logger.info("Global configuration with session encryption setting updated, invalidating cache")
            _invalidate_session_encryption_cache()

    except ClientError:
        logger.exception("Error updating session in DynamoDB")
