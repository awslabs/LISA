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

"""Lambda functions for managing User Preferences in AWS DynamoDB."""
import json
import logging
import os
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from utilities.auth import get_username
from utilities.common_functions import api_wrapper, get_item, retry_config

from .models import UserPreferencesModel

logger = logging.getLogger(__name__)

# Initialize the DynamoDB resource and the table using environment variables
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["USER_PREFERENCES_TABLE_NAME"])


@api_wrapper
def get(event: dict, context: dict) -> Any:
    """Retrieve a user's user preferences from DynamoDB."""
    user_id = get_username(event)

    # Query for the user preferences
    response = table.query(KeyConditionExpression=Key("user").eq(user_id), Limit=1, ScanIndexForward=False)
    item = get_item(response)

    if item is None:
        return None

    if item["user"] == user_id:
        return item

    raise ValueError(f"Not authorized to get {user_id}'s preferences.")


@api_wrapper
def update(event: dict, context: dict) -> Any:
    """Update an existing user preferences in DynamoDB."""
    user_id = get_username(event)
    body = json.loads(event["body"], parse_float=Decimal)
    user_preferences_model = UserPreferencesModel(**body)

    # Query for the latest user preferences revision
    response = table.query(KeyConditionExpression=Key("user").eq(user_id), Limit=1, ScanIndexForward=False)
    item = get_item(response)

    if item is None:
        user_preferences_model = UserPreferencesModel(**body)
        # Insert the new user preferences item into the DynamoDB table
        logger.info(f"Creating User Preferences: {user_preferences_model.model_dump(exclude_none=True)}")
        table.put_item(Item=user_preferences_model.model_dump(exclude_none=True))
        return user_preferences_model.model_dump()

    # Check if the user is authorized to update the user preferences
    if item["user"] == user_id:
        # Update the user preferences
        logger.info(f"Updating User Preferences: {user_preferences_model.model_dump(exclude_none=True)}")
        table.put_item(Item=user_preferences_model.model_dump(exclude_none=True))
        return user_preferences_model.model_dump()

    raise ValueError(f"Not authorized to update {user_id}'s preferences.")
