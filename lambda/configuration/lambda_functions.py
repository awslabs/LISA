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
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No record found with session id: {config_scope}")
        else:
            logger.exception("Error fetching session")
    return response.get("Item", {})  # type: ignore [no-any-return]


@api_wrapper
def update_configuration(event: dict, context: dict) -> None:
    """Update configuration in DynamoDB."""
    # from https://stackoverflow.com/a/71446846
    body = json.loads(event["body"], parse_float=Decimal)
    body["created_at"]=time.time()

    try:
        table.put_item(Item=body)
    except ClientError:
        logger.exception("Error updating session in DynamoDB")
