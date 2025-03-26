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
from decimal import Decimal
from functools import reduce
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key
from utilities.common_functions import api_wrapper, get_groups, get_username, is_admin, retry_config

from .models import PromptTemplateModel

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["PROMPT_TEMPLATES_TABLE_NAME"])


def _get_prompt_templates(
    user_id: Optional[str] = None,
    groups: Optional[List] = None,
    cursor: Optional[str] = None,
    latest: Optional[bool] = None,
) -> Dict[str, Any]:
    filter_expression = None

    if latest:
        condition = Attr("latest").eq(True)
        filter_expression = condition if filter_expression is None else filter_expression & condition

    if user_id:
        condition = Attr("owner").eq(user_id)
        filter_expression = condition if filter_expression is None else filter_expression & condition

    if groups:
        if len(groups) == 0:
            condition = Attr("groups").size().eq(0)
            filter_expression = condition if filter_expression is None else filter_expression & condition
        else:
            conditions = [Attr("groups").contains(group) for group in groups]
            condition = reduce(lambda a, b: a | b, conditions)
            filter_expression = condition if filter_expression is None else filter_expression & condition

    scan_arguments = {
        "TableName": os.environ["PROMPT_TEMPLATES_TABLE_NAME"],
        "IndexName": os.environ["PROMPT_TEMPLATES_BY_LATEST_INDEX_NAME"],
    }

    if filter_expression:
        scan_arguments["FilterExpression"] = filter_expression

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
def get(event: dict, context: dict) -> Dict[str, Any]:
    """Get session from DynamoDB."""
    user_id = get_username(event)
    prompt_template_id = get_prompt_template_id(event)

    # find latest prompt template revision
    response = table.query(KeyConditionExpression=Key("id").eq(prompt_template_id), Limit=1, ScanIndexForward=False)
    items = response.get("Items", [])
    item = items[0] if items else None

    if item is None:
        raise ValueError(f"Prompt template {prompt_template_id} not found.")

    is_owner = item["owner"] == user_id
    is_group_member = set(get_groups(event)) & set(item["groups"])
    if not is_admin(event) and not is_owner and not is_group_member:
        raise ValueError(f"Not authorized to get {prompt_template_id}.")

    return item


@api_wrapper
def list(event: dict, context: dict) -> Dict[str, Any]:
    """List sessions by user ID from DynamoDB."""

    query_params = event.get("queryStringParameters", {})
    cursor = query_params.get("cursor", None)
    user_id = get_username(event)

    if query_params.get("public") == "true":
        if is_admin(event):
            logger.info(f"Listing all templates for user {user_id} (is_admin)")
            return _get_prompt_templates(cursor=cursor, latest=True)
        else:
            groups = get_groups(event)
            logger.info(f"Listing public templates for user {user_id} with groups {groups}")
            return _get_prompt_templates(groups=groups, cursor=cursor, latest=True)
    else:
        logger.info(f"Listing private templates for user {user_id}")
        return _get_prompt_templates(user_id=user_id, cursor=cursor, latest=True)


@api_wrapper
def create(event: dict, context: dict) -> Any:
    """Get session from DynamoDB."""
    user_id = get_username(event)
    # from https://stackoverflow.com/a/71446846
    body = json.loads(event["body"], parse_float=Decimal)
    # enforce owner
    body["owner"] = user_id
    model = PromptTemplateModel(**body)

    table.put_item(Item=model.model_dump(exclude_none=True))
    return model.model_dump()


@api_wrapper
def update(event: dict, context: dict) -> Any:
    """Get session from DynamoDB."""
    user_id = get_username(event)
    prompt_template_id = get_prompt_template_id(event)
    # from https://stackoverflow.com/a/71446846
    body = json.loads(event["body"], parse_float=Decimal)
    model = PromptTemplateModel(**body)

    if prompt_template_id != model.id:
        raise ValueError(f"URL id {prompt_template_id} doesn't match body id {model.id}")

    # find latest prompt template revision
    response = table.query(KeyConditionExpression=Key("id").eq(prompt_template_id), Limit=1, ScanIndexForward=False)
    items = response.get("Items", [])
    item = items[0] if items else None

    if item is None:
        raise ValueError(f"Prompt template {model} not found.")

    if is_admin(event) or item["owner"] == user_id:
        logger.info(f"Removing latest attribute from prompt_template with ID {prompt_template_id} for user {user_id}")
        table.update_item(
            Key={
                "id": item["id"],
                "created": item["created"],
            },
            UpdateExpression="REMOVE latest",
        )

        # overwrite non-editable fields to make sure nothing is being updated unexpectedly
        model = model.new_revision(update={"id": item["id"], "owner": item["owner"]})
        logger.info(f"new model: {model.model_dump(exclude_none=True)}")
        response = table.put_item(Item=model.model_dump(exclude_none=True))
        return model.model_dump()

    raise ValueError(f"Not authorized to update {prompt_template_id}.")


@api_wrapper
def delete(event: dict, context: dict) -> Dict[str, str]:
    """Delete prompt template from DynamoDB."""
    user_id = get_username(event)
    prompt_template_id = get_prompt_template_id(event)

    # find latest prompt template revision
    response = table.query(KeyConditionExpression=Key("id").eq(prompt_template_id), Limit=1, ScanIndexForward=False)
    items = response.get("Items", [])
    item = items[0] if items else None

    if item is None:
        raise ValueError(f"Prompt template {prompt_template_id} not found.")

    if is_admin(event) or item["owner"] == user_id:
        logger.info(f"Removing latest attribute from prompt_template with ID {prompt_template_id} for user {user_id}")

        # logical delete by just removing the latest attribute
        table.update_item(
            Key={"id": item["id"], "created": item["created"]},
            UpdateExpression="REMOVE latest",
        )

        return {"status": "ok"}

    raise ValueError(f"Not authorized to delete {prompt_template_id}.")


def get_prompt_template_id(event: dict) -> str:
    """Get session_id from event."""
    return str(event["pathParameters"]["promptTemplateId"])
