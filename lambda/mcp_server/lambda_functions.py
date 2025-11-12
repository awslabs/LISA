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
import re
import uuid
from decimal import Decimal
from functools import reduce
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key
from utilities.auth import get_username, is_admin
from utilities.common_functions import api_wrapper, get_bearer_token, get_groups, get_item, retry_config

from .models import (
    HostedMcpServerModel,
    HostedMcpServerStatus,
    McpServerModel,
    McpServerStatus,
    UpdateHostedMcpServerRequest,
)

logger = logging.getLogger(__name__)

# Initialize the DynamoDB resource and the table using environment variables
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["MCP_SERVERS_TABLE_NAME"])
stepfunctions = boto3.client("stepfunctions", region_name=os.environ["AWS_REGION"], config=retry_config)


def _normalize_server_name(name: str) -> str:
    """Normalize server name to match CDK resource naming (alphanumeric only)."""
    return re.sub(r"[^a-zA-Z0-9]", "", name)


def replace_bearer_token_header(mcp_server: dict, replacement: str):
    """Replace {LISA_BEARER_TOKEN} placeholder with actual bearer token in custom headers."""
    custom_headers = mcp_server.get("customHeaders", {})
    for key, value in custom_headers.items():
        if key.lower() == "authorization" and "{LISA_BEARER_TOKEN}" in value:
            custom_headers[key] = value.replace("{LISA_BEARER_TOKEN}", replacement)


def _build_groups_condition(groups: List[str]) -> Any:
    """Build DynamoDB condition for groups filtering."""
    # Servers with no groups (groups attribute doesn't exist, is null, or is empty array) should be included
    no_groups_condition = Attr("groups").not_exists() | Attr("groups").eq(None) | Attr("groups").eq([])

    # Servers with at least one matching group
    group_conditions = [Attr("groups").contains(f"group:{group}") for group in groups]
    has_matching_group_condition = reduce(lambda a, b: a | b, group_conditions)

    # Combine: no groups OR has matching group
    return no_groups_condition | has_matching_group_condition


def _get_mcp_servers(
    user_id: Optional[str] = None,
    active: Optional[bool] = None,
    replace_bearer_token: Optional[str] = None,
    groups: Optional[List] = None,
) -> Dict[str, Any]:
    """Helper function to retrieve mcp servers from DynamoDB."""
    filter_expression = None
    condition = None

    # Filter by user_id if provided
    if user_id:
        if groups is not None and len(groups) > 0:
            # Complex logic when groups are provided:
            # 1. User owns server (regardless of groups) OR
            # 2. Public server AND (no groups OR has matching groups) OR
            # 3. Any server with matching groups (regardless of owner)

            # User owns server (no group restrictions)
            user_owns = Attr("owner").eq(user_id)

            # Public server with groups filtering
            # Public servers should be included if they have no groups OR matching groups
            public_no_groups = Attr("owner").eq("lisa:public") & (
                Attr("groups").not_exists() | Attr("groups").eq(None) | Attr("groups").eq([])
            )
            public_matching_groups = Attr("owner").eq("lisa:public") & reduce(
                lambda a, b: a | b, [Attr("groups").contains(f"group:{group}") for group in groups]
            )
            public_with_groups_ok = public_no_groups | public_matching_groups

            # Any server with matching groups (regardless of owner)
            # Only include servers that actually have groups and match
            group_conditions = [Attr("groups").contains(f"group:{group}") for group in groups]
            any_matching_groups = reduce(lambda a, b: a | b, group_conditions)

            # Combine: user owns OR (public with groups ok) OR (any matching groups)
            condition = user_owns | public_with_groups_ok | any_matching_groups
        else:
            # Simple logic when no groups: user owns OR public
            condition = Attr("owner").eq(user_id) | Attr("owner").eq("lisa:public")

        filter_expression = condition if filter_expression is None else filter_expression & condition

    # Filter by active status if provided
    if active:
        condition = Attr("status").eq(McpServerStatus.ACTIVE)
        filter_expression = condition if filter_expression is None else filter_expression & condition

    # Filter by user groups if provided (only if not already handled in user_id filter)
    if groups is not None and len(groups) > 0 and not user_id:
        condition = _build_groups_condition(groups)
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
        batch_items = response.get("Items", [])
        items.extend(batch_items)

        if "LastEvaluatedKey" in response:
            scan_arguments["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        else:
            break

    # Look through the headers, and replace {LISA_BEARER_TOKEN} with the users
    if replace_bearer_token:
        for mcp_server in items:
            replace_bearer_token_header(mcp_server, replace_bearer_token)

    return {"Items": items}


@api_wrapper
def get(event: dict, context: dict) -> Any:
    """Retrieve a specific mcp server from DynamoDB."""
    user_id = get_username(event)
    mcp_server_id = get_mcp_server_id(event)

    # Check if showPlaceholder query parameter is present
    query_params = event.get("queryStringParameters") or {}
    show_placeholder = query_params.get("showPlaceholder") == "1"

    # Query for the mcp server
    response = table.query(KeyConditionExpression=Key("id").eq(mcp_server_id), Limit=1, ScanIndexForward=False)
    item = get_item(response)

    if item is None:
        raise ValueError(f"MCP Server {mcp_server_id} not found.")

    # Check if the user is authorized to get the mcp server
    is_owner = item["owner"] == user_id or item["owner"] == "lisa:public"
    groups = item.get("groups", [])
    if is_owner or is_admin(event) or _is_member(get_groups(event), groups):
        # add extra attribute so the frontend doesn't have to determine this
        if is_owner:
            item["isOwner"] = True

        # Replace bearer token placeholder unless showPlaceholder is true
        if not show_placeholder:
            bearer_token = get_bearer_token(event)
            if bearer_token:
                replace_bearer_token_header(item, bearer_token)

        return item

    raise ValueError(f"Not authorized to get {mcp_server_id}.")


def _is_member(user_groups: List[str], prompt_groups: List[str]) -> bool:
    return bool(set(user_groups) & set(prompt_groups))


def _set_can_use(
    connections: Dict[str, Any], user_id: Optional[str] = None, groups: Optional[List[str]] = None
) -> Dict[str, Any]:
    if groups is None:
        groups = []
    items = connections.get("Items", [])
    formatted_groups = [f"group:{group}" for group in groups]
    for item in items:
        item["canUse"] = (
            _is_member(formatted_groups, item.get("groups", []))
            or item["owner"] == user_id
            or item["owner"] == "lisa:public"
        )
    connections["Items"] = items
    return connections


@api_wrapper
def list(event: dict, context: dict) -> Dict[str, Any]:
    """List mcp servers for a user from DynamoDB."""
    user_id = get_username(event)

    bearer_token = get_bearer_token(event)
    groups = get_groups(event)

    if is_admin(event):
        logger.info(f"Listing all mcp servers for user {user_id} (is_admin)")
        return _set_can_use(_get_mcp_servers(replace_bearer_token=bearer_token), user_id, groups)

    return _set_can_use(
        _get_mcp_servers(user_id=user_id, active=True, groups=groups, replace_bearer_token=bearer_token),
        user_id,
        groups,
    )


@api_wrapper
def create(event: dict, context: dict) -> Any:
    """Create a new mcp server in DynamoDB."""
    user_id = get_username(event)
    body = json.loads(event["body"], parse_float=Decimal)
    body["owner"] = (
        user_id if body.get("owner", None) != "lisa:public" else body["owner"]
    )  # Set the owner of the mcp server
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
    body["owner"] = user_id if body.get("owner", None) != "lisa:public" else body["owner"]
    mcp_server_model = McpServerModel(**body)

    if mcp_server_id != mcp_server_model.id:
        raise ValueError(f"URL id {mcp_server_id} doesn't match body id {mcp_server_model.id}")

    # Query for the latest mcp server revision
    response = table.query(KeyConditionExpression=Key("id").eq(mcp_server_id), Limit=1, ScanIndexForward=False)
    item = get_item(response)

    if item is None:
        raise ValueError(f"MCP Server {mcp_server_model} not found.")

    # Check if the user is authorized to update the mcp server
    if is_admin(event) or item["owner"] == user_id:
        # Check if switching to global
        if item["owner"] != mcp_server_model.owner:
            table.delete_item(Key={"id": mcp_server_id, "owner": item["owner"]})
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
    item = get_item(response)

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


@api_wrapper
def create_hosted_mcp_server(event: dict, context: dict) -> Any:
    """Trigger the state machine to create a LISA Hosted MCP server."""
    user_id = get_username(event)
    body = json.loads(event["body"], parse_float=Decimal)
    body["owner"] = user_id if body.get("owner", None) != "lisa:public" else body["owner"]
    body["id"] = str(uuid.uuid4())

    # Check if the user is authorized to create Hosted MCP server
    if is_admin(event):
        # Validate and parse the hosted server configuration
        hosted_server_model = HostedMcpServerModel(**body)

        # Check if normalized name is unique
        normalized_name = _normalize_server_name(hosted_server_model.name)
        if not normalized_name:
            raise ValueError("Server name must contain at least one alphanumeric character.")

        # Scan all items to check for duplicate normalized names
        items = []
        scan_arguments = {}
        while True:
            response = table.scan(**scan_arguments)
            items.extend(response.get("Items", []))

            if "LastEvaluatedKey" in response:
                scan_arguments["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            else:
                break

        # Check if any existing server has the same normalized name
        for item in items:
            existing_name = item.get("name", "")
            existing_normalized = _normalize_server_name(existing_name)
            if existing_normalized == normalized_name and item.get("id") != body["id"]:
                raise ValueError(
                    f"Server name '{hosted_server_model.name}' conflicts with existing server '{existing_name}'. "
                    f"Normalized names must be unique (alphanumeric characters only)."
                )

        # persist initial record
        table.put_item(Item=hosted_server_model.model_dump(exclude_none=True))

        # kick off state machine
        sfn_arn = os.environ.get("CREATE_MCP_SERVER_SFN_ARN")
        if not sfn_arn:
            raise ValueError("CREATE_MCP_SERVER_SFN_ARN not configured")
        stepfunctions.start_execution(
            stateMachineArn=sfn_arn,
            input=json.dumps(hosted_server_model.model_dump(exclude_none=True)),
        )

        result = hosted_server_model.model_dump(exclude_none=True)
        result["status"] = HostedMcpServerStatus.CREATING
        return result
    raise ValueError(f"Not authorized to create hosted MCP server. User {user_id} is not an admin.")


@api_wrapper
def list_hosted_mcp_servers(event: dict, context: dict) -> Dict[str, Any]:
    """List all hosted MCP servers from DynamoDB."""
    user_id = get_username(event)

    # Check if the user is authorized to list hosted MCP servers
    if is_admin(event):
        logger.info(f"Listing all hosted MCP servers for user {user_id} (is_admin)")
        # Get all items from the table
        items = []
        scan_arguments = {}
        while True:
            response = table.scan(**scan_arguments)
            items.extend(response.get("Items", []))

            if "LastEvaluatedKey" in response:
                scan_arguments["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            else:
                break

        return {"Items": items}

    raise ValueError(f"Not authorized to list hosted MCP servers. User {user_id} is not an admin.")


@api_wrapper
def get_hosted_mcp_server(event: dict, context: dict) -> Any:
    """Retrieve a specific hosted MCP server from DynamoDB."""
    user_id = get_username(event)
    mcp_server_id = get_mcp_server_id(event)

    # Query for the mcp server
    response = table.query(KeyConditionExpression=Key("id").eq(mcp_server_id), Limit=1, ScanIndexForward=False)
    item = get_item(response)

    if item is None:
        raise ValueError(f"Hosted MCP Server {mcp_server_id} not found.")

    # Check if the user is authorized to get the hosted mcp server
    if is_admin(event):
        return item

    raise ValueError(f"Not authorized to get hosted MCP server {mcp_server_id}. User {user_id} is not an admin.")


@api_wrapper
def delete_hosted_mcp_server(event: dict, context: dict) -> Any:
    """Trigger the state machine to delete a LISA Hosted MCP server."""
    user_id = get_username(event)
    mcp_server_id = get_mcp_server_id(event)

    # Check if the user is authorized to delete Hosted MCP server
    if is_admin(event):
        # Check if server exists
        response = table.query(KeyConditionExpression=Key("id").eq(mcp_server_id), Limit=1, ScanIndexForward=False)
        item = get_item(response)

        if item is None:
            raise ValueError(f"Hosted MCP Server {mcp_server_id} not found.")

        # Validate server status - only allow deletion if in specific states
        server_status = item.get("status", "")
        allowed_statuses = [
            HostedMcpServerStatus.IN_SERVICE,
            HostedMcpServerStatus.STOPPED,
            HostedMcpServerStatus.FAILED,
        ]
        if server_status not in allowed_statuses:
            raise ValueError(
                f"Cannot delete server {mcp_server_id} with status '{server_status}'. "
                f"Only servers with status '{HostedMcpServerStatus.IN_SERVICE}', "
                f"'{HostedMcpServerStatus.STOPPED}', or '{HostedMcpServerStatus.FAILED}' can be deleted."
            )

        # Kick off state machine
        sfn_arn = os.environ.get("DELETE_MCP_SERVER_SFN_ARN")
        if not sfn_arn:
            raise ValueError("DELETE_MCP_SERVER_SFN_ARN not configured")

        stepfunctions.start_execution(
            stateMachineArn=sfn_arn,
            input=json.dumps({"id": mcp_server_id}),
        )

        return {"message": f"Deletion initiated for hosted MCP server {mcp_server_id}"}

    raise ValueError(f"Not authorized to delete hosted MCP server. User {user_id} is not an admin.")


@api_wrapper
def update_hosted_mcp_server(event: dict, context: dict) -> Any:
    """Trigger the state machine to update a LISA Hosted MCP server."""
    user_id = get_username(event)
    mcp_server_id = get_mcp_server_id(event)

    # Check if the user is authorized to update Hosted MCP server
    if is_admin(event):
        # Check if server exists
        response = table.query(KeyConditionExpression=Key("id").eq(mcp_server_id), Limit=1, ScanIndexForward=False)
        item = get_item(response)

        if item is None:
            raise ValueError(f"Hosted MCP Server {mcp_server_id} not found.")

        server_status = item.get("status", "")

        # Validate server is not actively mutating or failed before starting
        if server_status not in (HostedMcpServerStatus.IN_SERVICE, HostedMcpServerStatus.STOPPED):
            raise ValueError(
                f"Server cannot be updated when it is not in the '{HostedMcpServerStatus.IN_SERVICE}' or "
                f"'{HostedMcpServerStatus.STOPPED}' states"
            )

        # Parse and validate update request
        body = json.loads(event["body"], parse_float=Decimal)
        update_request = UpdateHostedMcpServerRequest(**body)

        # Validate enable/disable state transitions
        if update_request.enabled is not None:
            # Force capacity changes and enable/disable operations to happen in separate requests
            if update_request.autoScalingConfig is not None:
                raise ValueError("Start or Stop operations and AutoScaling changes must happen in separate requests.")
            # Server cannot be enabled if it isn't already stopped
            if update_request.enabled and server_status != HostedMcpServerStatus.STOPPED:
                raise ValueError(
                    f"Server cannot be enabled when it is not in the '{HostedMcpServerStatus.STOPPED}' state."
                )
            # Server cannot be stopped if it isn't already in service
            elif not update_request.enabled and server_status != HostedMcpServerStatus.IN_SERVICE:
                raise ValueError(
                    f"Server cannot be stopped when it is not in the '{HostedMcpServerStatus.IN_SERVICE}' state."
                )

        # Validate auto-scaling config
        if update_request.autoScalingConfig is not None:
            stack_name = item.get("stack_name")
            if not stack_name:
                raise ValueError(
                    "Cannot update AutoScaling Config for server that does not have a CloudFormation stack."
                )

            asg_config = update_request.autoScalingConfig.model_dump(exclude_none=True)
            current_asg_config = item.get("autoScalingConfig", {})

            # Validate min <= max
            min_capacity = asg_config.get("minCapacity", current_asg_config.get("minCapacity", 1))
            max_capacity = asg_config.get("maxCapacity", current_asg_config.get("maxCapacity", 1))

            if min_capacity > max_capacity:
                raise ValueError(f"Min capacity ({min_capacity}) cannot be greater than max capacity ({max_capacity}).")

            # Validate min and max are positive
            if min_capacity < 1:
                raise ValueError("Min capacity must be at least 1.")
            if max_capacity < 1:
                raise ValueError("Max capacity must be at least 1.")

        # Validate container config updates
        if (
            update_request.environment is not None
            or update_request.cpu is not None
            or update_request.memoryLimitMiB is not None
            or update_request.containerHealthCheckConfig is not None
        ):
            stack_name = item.get("stack_name")
            if not stack_name:
                raise ValueError("Cannot update container config for server that does not have a CloudFormation stack.")

        # Kick off state machine
        sfn_arn = os.environ.get("UPDATE_MCP_SERVER_SFN_ARN")
        if not sfn_arn:
            raise ValueError("UPDATE_MCP_SERVER_SFN_ARN not configured")

        # Package server ID and request payload into single payload for step functions
        state_machine_payload = {"server_id": mcp_server_id, "update_payload": update_request.model_dump()}
        stepfunctions.start_execution(
            stateMachineArn=sfn_arn,
            input=json.dumps(state_machine_payload),
        )

        # Return current server config (status will be updated by state machine)
        return item

    raise ValueError(f"Not authorized to update hosted MCP server. User {user_id} is not an admin.")
