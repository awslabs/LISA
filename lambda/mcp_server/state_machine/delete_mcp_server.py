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
from typing import Any, Dict, Optional
from uuid import uuid4

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.config import Config
from botocore.exceptions import ClientError
from mcp_server.models import HostedMcpServerStatus
from utilities.time import now

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambdaConfig = Config(connect_timeout=60, read_timeout=600, retries={"max_attempts": 1})
cfnClient = boto3.client("cloudformation", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
ddbResource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
ssmClient = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
mcp_servers_table = ddbResource.Table(os.environ["MCP_SERVERS_TABLE_NAME"])

# DDB and Payload fields
STACK_NAME = "stack_name"
STACK_ARN = "cloudformation_stack_arn"


def _get_mcp_connections_table_name(deployment_prefix: str) -> Optional[str]:
    """Get MCP connections table name from SSM parameter if chat is deployed."""
    try:
        response = ssmClient.get_parameter(Name=f"{deployment_prefix}/table/mcpServersTable")
        return response["Parameter"]["Value"]  # type: ignore[no-any-return]
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
    stack_arn = item.get(STACK_ARN, None)
    # Convert stack name to ARN if stack_name exists
    if stack_name:
        output_dict[STACK_NAME] = stack_name
        output_dict[STACK_ARN] = stack_arn  # Use stack name as ARN
    else:
        output_dict[STACK_ARN] = None

    mcp_servers_table.update_item(
        Key=server_key,
        UpdateExpression="SET last_modified = :lm, #status = :ms",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":lm": now(),
            ":ms": HostedMcpServerStatus.DELETING,
        },
    )
    return output_dict


def handle_delete_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Initialize stack deletion."""
    output_dict = deepcopy(event)
    stack_arn = event.get(STACK_ARN)
    if not stack_arn:
        raise ValueError("Stack arn not found in event")

    # Get the actual stack ARN before deleting

    logger.info(f"Deleting CloudFormation stack: {stack_arn}")
    client_request_token = str(uuid4())
    cfnClient.delete_stack(
        StackName=stack_arn,
        ClientRequestToken=client_request_token,
    )
    return output_dict


def handle_monitor_delete_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get stack status while it is being deleted and evaluate if state machine should continue polling."""
    output_dict = deepcopy(event)
    # Prefer ARN if available, fall back to stack name
    stack_identifier = event.get(STACK_ARN) or event.get(STACK_NAME)
    if not stack_identifier:
        raise ValueError("Stack ARN or name not found in event")

    try:
        stack_metadata = cfnClient.describe_stacks(StackName=stack_identifier)["Stacks"][0]
        stack_status = stack_metadata["StackStatus"]
        continue_polling = True  # stack not done yet, so continue monitoring
        if stack_status == "DELETE_COMPLETE":
            continue_polling = False  # stack finished, allow state machine to stop polling
        elif stack_status.endswith("COMPLETE") or stack_status.endswith("FAILED"):
            # Didn't expect anything else, so raise error to fail state machine
            raise RuntimeError(f"Stack entered unexpected terminal state '{stack_status}'.")
    except ClientError as e:
        # Check if the error is because the stack doesn't exist (ValidationError)
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ValidationError":
            # Stack doesn't exist - this means it was successfully deleted
            # CloudFormation removes stacks completely after DELETE_COMPLETE, so ValidationError is expected
            logger.info(f"Stack {stack_identifier} no longer exists (successfully deleted)")
            continue_polling = False  # Stack is gone, deletion is complete
        else:
            # Re-raise unexpected ClientErrors
            logger.error(f"Error monitoring stack deletion: {str(e)}")
            raise
    except Exception as e:
        # Re-raise unexpected errors
        logger.error(f"Error monitoring stack deletion: {str(e)}")
        raise

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
                response = mcp_connections_table.scan(FilterExpression=Attr("id").eq(server_id))

                # Delete the matching item (there should only be one)
                for item in response.get("Items", []):
                    mcp_connections_table.delete_item(Key={"id": item["id"], "owner": item["owner"]})
                    logger.info(
                        f"Deleted MCP connection entry for server {server_id} (owner: {item['owner']}) "
                        + "from connections table"
                    )
            except Exception as e:
                logger.warning(f"Error deleting from MCP connections table: {str(e)}")
                # Continue with deletion from main table even if connections table deletion fails

    # Delete from main MCP servers table
    mcp_servers_table.delete_item(Key=server_key)
    logger.info(f"Deleted MCP server {server_id} from DynamoDB table")

    return event
