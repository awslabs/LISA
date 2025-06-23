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

"""Lambda functions for managing MCP Servers in AWS DynamoDB."""
import json
import logging
import os
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key
from utilities.common_functions import api_wrapper, get_username, is_admin, retry_config

from .models import McpServerModel

logger = logging.getLogger(__name__)

# Initialize the DynamoDB resource and the table using environment variables
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["MCP_SERVERS_TABLE_NAME"])


def _get_mcp_servers(
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper function to retrieve mcp servers from DynamoDB."""
    filter_expression = None

    # Filter by user_id if provided
    if user_id:
        condition = Attr("owner").eq(user_id) | Attr("owner").eq("lisa:public")
        filter_expression = condition if filter_expression is None else filter_expression & condition

    scan_arguments = {
        "TableName": os.environ["MCP_SERVERS_TABLE_NAME"],
        "IndexName": os.environ["MCP_SERVERS_BY_OWNER_INDEX_NAME"],
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
    """Retrieve a specific mcp server from DynamoDB."""
    user_id = get_username(event)
    mcp_server_id = get_mcp_server_id(event)

    # Query for the mcp server
    response = table.query(KeyConditionExpression=Key("id").eq(mcp_server_id), Limit=1, ScanIndexForward=False)
    items = response.get("Items", [])
    item = items[0] if items else None

    if item is None:
        raise ValueError(f"MCP Server {mcp_server_id} not found.")

    # Check if the user is authorized to get the mcp server
    is_owner = item["owner"] == user_id or item["owner"] == "lisa:public"
    if is_owner or is_admin(event):
        # add extra attribute so the frontend doesn't have to determine this
        if is_owner:
            item["isOwner"] = True
        return item

    raise ValueError(f"Not authorized to get {mcp_server_id}.")


@api_wrapper
def list(event: dict, context: dict) -> Dict[str, Any]:
    """List mcp servers for a user from DynamoDB."""
    user_id = get_username(event)

    if is_admin(event):
        logger.info(f"Listing all mcp servers for user {user_id} (is_admin)")
        return _get_mcp_servers()
    else:
        logger.info(f"Listing mcp servers for user {user_id}")
    return _get_mcp_servers(user_id=user_id)


@api_wrapper
def create(event: dict, context: dict) -> Any:
    """Create a new mcp server in DynamoDB."""
    user_id = get_username(event)
    body = json.loads(event["body"], parse_float=Decimal)
    body["owner"] = user_id if body.get("owner", None) is None else body["owner"]  # Set the owner of the mcp server
    mcp_server_model = McpServerModel(**body)

    # Insert the new mcp server item into the DynamoDB table
    table.put_item(Item=mcp_server_model.model_dump(exclude_none=True))
    return mcp_server_model.model_dump()


@api_wrapper
def update(event: dict, context: dict) -> Any:
    """Update an existing mcp server in DynamoDB."""
    user_id = get_username(event)
    mcp_server_id = get_mcp_server_id(event)
    body = json.loads(event["body"], parse_float=Decimal)
    mcp_server_model = McpServerModel(**body)

    if mcp_server_id != mcp_server_model.id:
        raise ValueError(f"URL id {mcp_server_id} doesn't match body id {mcp_server_model.id}")

    # Query for the latest mcp server revision
    response = table.query(KeyConditionExpression=Key("id").eq(mcp_server_id), Limit=1, ScanIndexForward=False)
    items = response.get("Items", [])
    item = items[0] if items else None

    if item is None:
        raise ValueError(f"MCP Server {mcp_server_model} not found.")

    # Check if the user is authorized to update the mcp server
    if is_admin(event) or item["owner"] == user_id:
        # Update the mcp server
        logger.info(f"new model: {mcp_server_model.model_dump(exclude_none=True)}")
        table.put_item(Item=mcp_server_model.model_dump(exclude_none=True))
        return mcp_server_model.model_dump()

    raise ValueError(f"Not authorized to update {mcp_server_id}.")


@api_wrapper
def delete(event: dict, context: dict) -> Dict[str, str]:
    """Logically delete a mcp server from DynamoDB."""
    user_id = get_username(event)
    mcp_server_id = get_mcp_server_id(event)

    # Query for the mcp server
    response = table.query(KeyConditionExpression=Key("id").eq(mcp_server_id), Limit=1, ScanIndexForward=False)
    items = response.get("Items", [])
    item = items[0] if items else None

    if item is None:
        raise ValueError(f"MCP Server {mcp_server_id} not found.")

    # Check if the user is authorized to delete the mcp server
    if is_admin(event) or item["owner"] == user_id:
        logger.info(f"Deleting mcp server {mcp_server_id} for user {user_id}")
        table.delete_item(Key={"id": mcp_server_id, "owner": item.get("owner")})
        return {"status": "ok"}

    raise ValueError(f"Not authorized to delete {mcp_server_id}.")


def get_mcp_server_id(event: dict) -> str:
    """Extract the mcp server id from the event's path parameters."""
    return str(event["pathParameters"]["serverId"])
