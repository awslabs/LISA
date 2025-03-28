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

"""Lambda functions for managing prompt templates in AWS DynamoDB."""
import json
import logging
import os
from decimal import Decimal
from functools import reduce
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key
from utilities.common_functions import api_wrapper, get_groups, get_username, is_admin, retry_config

from .models import PromptTemplateModel

logger = logging.getLogger(__name__)

# Initialize the DynamoDB resource and the table using environment variables
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["PROMPT_TEMPLATES_TABLE_NAME"])


def _get_prompt_templates(
    user_id: Optional[str] = None,
    groups: Optional[List] = None,
    latest: Optional[bool] = None,
) -> Dict[str, Any]:
    """Helper function to retrieve prompt templates from DynamoDB."""
    filter_expression = None

    # Optionally filter for latest prompt templates
    if latest:
        condition = Attr("latest").eq(True)
        filter_expression = condition if filter_expression is None else filter_expression & condition

    # Filter by user_id if provided
    if user_id:
        condition = Attr("owner").eq(user_id)
        filter_expression = condition if filter_expression is None else filter_expression & condition

    # Filter by user groups if provided
    if groups is not None:
        condition = Attr("groups").contains("lisa:public")
        if len(groups) > 0:
            conditions = [Attr("groups").contains(f"group:{group}") for group in groups]
            condition = reduce(lambda a, b: a | b, conditions, condition)
        filter_expression = condition if filter_expression is None else filter_expression & condition

    scan_arguments = {
        "TableName": os.environ["PROMPT_TEMPLATES_TABLE_NAME"],
        "IndexName": os.environ["PROMPT_TEMPLATES_BY_LATEST_INDEX_NAME"],
    }

    # Set FilterExpression if applicable
    if filter_expression:
        scan_arguments["FilterExpression"] = filter_expression

    # Scan the DynamoDB table to retrieve items
    items = []
    while True:
        response = table.scan(**scan_arguments)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" in response:
            scan_arguments["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        else:
            break

    return {"Items": items}


@api_wrapper
def get(event: dict, context: dict) -> Any:
    """Retrieve a specific prompt template from DynamoDB."""
    user_id = get_username(event)
    prompt_template_id = get_prompt_template_id(event)

    # Query for the latest prompt template revision
    response = table.query(KeyConditionExpression=Key("id").eq(prompt_template_id), Limit=1, ScanIndexForward=False)
    items = response.get("Items", [])
    item = items[0] if items else None

    if item is None:
        raise ValueError(f"Prompt template {prompt_template_id} not found.")

    # Check if the user is authorized to get the prompt template
    is_owner = item["owner"] == user_id
    if is_owner or is_admin(event) or is_member(get_groups(event), item["groups"]):
        # add extra attribute so the frontend doesn't have to determine this
        if is_owner:
            item["isOwner"] = True
        return item

    raise ValueError(f"Not authorized to get {prompt_template_id}.")


def is_member(user_groups: List[str], prompt_groups: List[str]) -> bool:
    if "lisa:public" in prompt_groups:
        return True

    return bool(set(user_groups) & set(prompt_groups))


@api_wrapper
def list(event: dict, context: dict) -> Dict[str, Any]:
    """List prompt templates for a user from DynamoDB."""
    query_params = event.get("queryStringParameters", {})
    user_id = get_username(event)

    # Check whether to list public or private templates
    if query_params.get("public") == "true":
        if is_admin(event):
            logger.info(f"Listing all templates for user {user_id} (is_admin)")
            return _get_prompt_templates(latest=True)
        else:
            groups = get_groups(event)
            logger.info(f"Listing public templates for user {user_id} with groups {groups}")
            return _get_prompt_templates(groups=groups, latest=True)
    else:
        logger.info(f"Listing private templates for user {user_id}")
        return _get_prompt_templates(user_id=user_id, latest=True)


@api_wrapper
def create(event: dict, context: dict) -> Any:
    """Create a new prompt template in DynamoDB."""
    user_id = get_username(event)
    body = json.loads(event["body"], parse_float=Decimal)
    body["owner"] = user_id  # Set the owner of the prompt template
    prompt_template_model = PromptTemplateModel(**body)

    # Insert the new prompt template item into the DynamoDB table
    table.put_item(Item=prompt_template_model.model_dump(exclude_none=True))
    return prompt_template_model.model_dump()


@api_wrapper
def update(event: dict, context: dict) -> Any:
    """Update an existing prompt template in DynamoDB."""
    user_id = get_username(event)
    prompt_template_id = get_prompt_template_id(event)
    body = json.loads(event["body"], parse_float=Decimal)
    prompt_template_model = PromptTemplateModel(**body)

    if prompt_template_id != prompt_template_model.id:
        raise ValueError(f"URL id {prompt_template_id} doesn't match body id {prompt_template_model.id}")

    # Query for the latest prompt template revision
    response = table.query(KeyConditionExpression=Key("id").eq(prompt_template_id), Limit=1, ScanIndexForward=False)
    items = response.get("Items", [])
    item = items[0] if items else None

    if item is None:
        raise ValueError(f"Prompt template {prompt_template_model} not found.")

    # Check if the user is authorized to update the prompt template
    if is_admin(event) or item["owner"] == user_id:
        logger.info(f"Removing latest attribute from prompt_template with ID {prompt_template_id} for user {user_id}")

        # Remove latest attribute indicating no longer the latest version
        table.update_item(
            Key={
                "id": item["id"],
                "created": item["created"],
            },
            UpdateExpression="REMOVE latest",
        )

        # Update the prompt template with a new revision
        prompt_template_model = prompt_template_model.new_revision(update={"id": item["id"], "owner": item["owner"]})
        logger.info(f"new model: {prompt_template_model.model_dump(exclude_none=True)}")
        response = table.put_item(Item=prompt_template_model.model_dump(exclude_none=True))
        return prompt_template_model.model_dump()

    raise ValueError(f"Not authorized to update {prompt_template_id}.")


@api_wrapper
def delete(event: dict, context: dict) -> Dict[str, str]:
    """Logically delete a prompt template from DynamoDB."""
    user_id = get_username(event)
    prompt_template_id = get_prompt_template_id(event)

    # Query for the latest prompt template revision
    response = table.query(KeyConditionExpression=Key("id").eq(prompt_template_id), Limit=1, ScanIndexForward=False)
    items = response.get("Items", [])
    item = items[0] if items else None

    if item is None:
        raise ValueError(f"Prompt template {prompt_template_id} not found.")

    # Check if the user is authorized to delete the prompt template
    if is_admin(event) or item["owner"] == user_id:
        logger.info(f"Removing latest attribute from prompt_template with ID {prompt_template_id} for user {user_id}")

        # Logical delete by removing the latest attribute
        table.update_item(
            Key={"id": item["id"], "created": item["created"]},
            UpdateExpression="REMOVE latest",
        )

        return {"status": "ok"}

    raise ValueError(f"Not authorized to delete {prompt_template_id}.")


def get_prompt_template_id(event: dict) -> str:
    """Extract the prompt_template_id from the event's path parameters."""
    return str(event["pathParameters"]["promptTemplateId"])
