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

"""Lambda functions for managing Chat Assistant Stacks in DynamoDB."""
from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from typing import Any, cast

import boto3
from botocore.exceptions import ClientError
from utilities.auth import admin_only, get_groups, is_admin, user_has_group_access
from utilities.common_functions import api_wrapper, retry_config
from utilities.exceptions import NotFoundException
from utilities.time import iso_string

from .models import ChatAssistantStackModel

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["CHAT_ASSISTANT_STACKS_TABLE_NAME"])


def _get_stack_id(event: dict) -> str:
    """Extract stackId from path parameters."""
    params = event.get("pathParameters") or {}
    stack_id = params.get("stackId")
    if not stack_id:
        raise ValueError("stackId is required")
    return str(stack_id)


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Convert DynamoDB item for JSON response (e.g. Decimal)."""
    return cast(dict[str, Any], json.loads(json.dumps(item, default=str)))


@api_wrapper
def list_stacks(event: dict, context: dict) -> dict:
    """List stacks: admins get all; non-admins get active stacks (allowedGroups empty or user in group)."""
    try:
        response = table.scan()
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        if is_admin(event):
            return {"Items": [_serialize_item(assistant_stack) for assistant_stack in items]}
        user_groups = get_groups(event)
        filtered = [
            assistant_stack
            for assistant_stack in items
            if assistant_stack.get("isActive", True)
            and (
                not assistant_stack.get("allowedGroups")
                or user_has_group_access(user_groups, assistant_stack.get("allowedGroups", []))
            )
        ]
        return {"Items": [_serialize_item(assistant_stack) for assistant_stack in filtered]}
    except ClientError:
        logger.exception("Error listing stacks")
        raise


@api_wrapper
@admin_only
def get_stack(event: dict, context: dict) -> dict:
    """Get a single Chat Assistant Stack by stackId. Admin only."""
    stack_id = _get_stack_id(event)
    try:
        response = table.get_item(Key={"stackId": stack_id})
        item = response.get("Item")
        if not item:
            raise NotFoundException(f"Chat Assistant Stack {stack_id} not found.")
        return _serialize_item(item)
    except ClientError:
        logger.exception("Error getting stack %s", stack_id)
        raise


@api_wrapper
@admin_only
def create(event: dict, context: dict) -> dict:
    """Create a new Chat Assistant Stack. Admin only."""
    body = json.loads(event["body"], parse_float=Decimal)
    model = ChatAssistantStackModel(**body)
    item = model.model_dump(exclude_none=True)
    try:
        table.put_item(Item=item)
        return _serialize_item(item)
    except ClientError:
        logger.exception("Error creating stack")
        raise


@api_wrapper
@admin_only
def update(event: dict, context: dict) -> dict:
    """Update an existing Chat Assistant Stack. Admin only."""
    stack_id = _get_stack_id(event)
    body = json.loads(event["body"], parse_float=Decimal)
    body["stackId"] = stack_id
    model = ChatAssistantStackModel(**body)
    try:
        response = table.get_item(Key={"stackId": stack_id})
        if not response.get("Item"):
            raise NotFoundException(f"Chat Assistant Stack {stack_id} not found.")
        existing = response["Item"]
        item = model.model_dump(exclude_none=True)
        item["created"] = existing.get("created", item.get("created"))
        table.put_item(Item=item)
        return _serialize_item(item)
    except ClientError:
        logger.exception("Error updating stack %s", stack_id)
        raise


@api_wrapper
@admin_only
def delete(event: dict, context: dict) -> dict:
    """Delete a Chat Assistant Stack. Admin only."""
    stack_id = _get_stack_id(event)
    try:
        response = table.delete_item(Key={"stackId": stack_id}, ReturnValues="ALL_OLD")
        if not response.get("Attributes"):
            raise NotFoundException(f"Chat Assistant Stack {stack_id} not found.")
        return {"status": "ok"}
    except ClientError:
        logger.exception("Error deleting stack %s", stack_id)
        raise


@api_wrapper
@admin_only
def update_status(event: dict, context: dict) -> dict:
    """Update isActive (activate/deactivate) for a stack. Admin only."""
    stack_id = _get_stack_id(event)
    body = json.loads(event.get("body") or "{}", parse_float=Decimal)
    is_active = body.get("isActive")
    if is_active is None:
        raise ValueError("isActive is required in body")
    try:
        response = table.get_item(Key={"stackId": stack_id})
        item = response.get("Item")
        if not item:
            raise NotFoundException(f"Chat Assistant Stack {stack_id} not found.")
        item["isActive"] = bool(is_active)
        item["updated"] = iso_string()
        table.put_item(Item=item)
        return _serialize_item(item)
    except ClientError:
        logger.exception("Error updating status for stack %s", stack_id)
        raise
