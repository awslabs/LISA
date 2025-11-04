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

"""Lambda handlers for DeleteMcpServer state machine."""

import logging
import os
from copy import deepcopy
from datetime import datetime, UTC
from typing import Any, Dict, Optional
from uuid import uuid4

import boto3
from botocore.config import Config
from boto3.dynamodb.conditions import Attr, Key

from mcp_server.models import HostedMcpServerStatus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambdaConfig = Config(connect_timeout=60, read_timeout=600, retries={"max_attempts": 1})
cfnClient = boto3.client("cloudformation", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
ddbResource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
ssmClient = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
mcp_servers_table = ddbResource.Table(os.environ["MCP_SERVERS_TABLE_NAME"])

# DDB and Payload fields
STACK_NAME = "stack_name"


def _get_mcp_connections_table_name(deployment_prefix: str) -> Optional[str]:
    """Get MCP connections table name from SSM parameter if chat is deployed."""
    try:
        response = ssmClient.get_parameter(Name=f"{deployment_prefix}/table/mcpServersTable")
        return response["Parameter"]["Value"]
    except ssmClient.exceptions.ParameterNotFound:
        logger.info("MCP connections table SSM parameter not found, chat may not be deployed")
        return None
    except Exception as e:
        logger.warning(f"Error getting MCP connections table name: {str(e)}")
        return None


def handle_set_server_to_deleting(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Start deletion workflow based on user-specified server input."""
    output_dict = deepcopy(event)
    server_id = event["id"]
    logger.info(f"Starting deletion workflow for MCP server: {server_id}")
    server_key = {"id": server_id}
    item = mcp_servers_table.get_item(
        Key=server_key,
        ConsistentRead=True,
        ReturnConsumedCapacity="NONE",
    ).get("Item", None)
    if not item:
        raise RuntimeError(f"Requested MCP server '{server_id}' was not found in DynamoDB table.")
    stack_name = item.get(STACK_NAME, None)
    # Convert stack name to ARN if stack_name exists
    if stack_name:
        # CloudFormation stack ARN format: arn:aws:cloudformation:region:account:stack/stack-name/id
        # For simplicity, we'll use the stack name directly and let CloudFormation handle it
        output_dict[STACK_NAME] = stack_name
        output_dict["cloudformation_stack_arn"] = stack_name  # Use stack name as ARN
    else:
        output_dict["cloudformation_stack_arn"] = None

    mcp_servers_table.update_item(
        Key=server_key,
        UpdateExpression="SET last_modified = :lm, #status = :ms",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":lm": int(datetime.now(UTC).timestamp()),
            ":ms": HostedMcpServerStatus.DELETING,
        },
    )
    return output_dict


def handle_delete_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Initialize stack deletion."""
    stack_name = event.get(STACK_NAME) or event.get("cloudformation_stack_arn")
    if not stack_name:
        raise ValueError("Stack name not found in event")
    logger.info(f"Deleting CloudFormation stack: {stack_name}")
    client_request_token = str(uuid4())
    cfnClient.delete_stack(
        StackName=stack_name,
        ClientRequestToken=client_request_token,
    )
    return event  # no payload mutations needed between this and next state


def handle_monitor_delete_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get stack status while it is being deleted and evaluate if state machine should continue polling."""
    output_dict = deepcopy(event)
    stack_name = event.get(STACK_NAME) or event.get("cloudformation_stack_arn")
    if not stack_name:
        raise ValueError("Stack name not found in event")
    stack_metadata = cfnClient.describe_stacks(StackName=stack_name)["Stacks"][0]
    stack_status = stack_metadata["StackStatus"]
    continue_polling = True  # stack not done yet, so continue monitoring
    if stack_status == "DELETE_COMPLETE":
        continue_polling = False  # stack finished, allow state machine to stop polling
    elif stack_status.endswith("COMPLETE") or stack_status.endswith("FAILED"):
        # Didn't expect anything else, so raise error to fail state machine
        raise RuntimeError(f"Stack entered unexpected terminal state '{stack_status}'.")
    output_dict["continue_polling"] = continue_polling

    return output_dict


def handle_delete_from_ddb(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete item from DDB after successful deletion workflow and remove from connections table."""
    server_id = event["id"]
    server_key = {"id": server_id}
    
    # Delete from MCP Connections table if chat is deployed
    deployment_prefix = os.environ.get("DEPLOYMENT_PREFIX", "")
    if deployment_prefix:
        mcp_connections_table_name = _get_mcp_connections_table_name(deployment_prefix)
        if mcp_connections_table_name:
            try:
                mcp_connections_table = ddbResource.Table(mcp_connections_table_name)
                # The connections table uses (id, owner) as composite key
                # We need to query/scan to find the entry with this server ID
                # Since we don't know the owner, we'll scan for the id
                response = mcp_connections_table.scan(
                    FilterExpression=Attr("id").eq(server_id)
                )
                
                # Delete the matching item (there should only be one)
                for item in response.get("Items", []):
                    mcp_connections_table.delete_item(
                        Key={
                            "id": item["id"],
                            "owner": item["owner"]
                        }
                    )
                    logger.info(f"Deleted MCP connection entry for server {server_id} (owner: {item['owner']}) from connections table")
            except Exception as e:
                logger.warning(f"Error deleting from MCP connections table: {str(e)}")
                # Continue with deletion from main table even if connections table deletion fails
    
    # Delete from main MCP servers table
    mcp_servers_table.delete_item(Key=server_key)
    logger.info(f"Deleted MCP server {server_id} from DynamoDB table")
    
    return event

