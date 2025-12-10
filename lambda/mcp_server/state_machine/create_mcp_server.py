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

"""Lambda handlers for CreateMcpServer state machine."""

import json
import logging
import os
import re
from copy import deepcopy
from datetime import datetime, UTC
from typing import Any, Dict, Optional

import boto3
from botocore.config import Config
from mcp_server.models import HostedMcpServerModel, HostedMcpServerStatus, McpServerStatus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambdaConfig = Config(connect_timeout=60, read_timeout=600, retries={"max_attempts": 1})
lambdaClient = boto3.client("lambda", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
cfnClient = boto3.client("cloudformation", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
ssmClient = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
ddbResource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
mcp_servers_table = ddbResource.Table(os.environ["MCP_SERVERS_TABLE_NAME"])

MAX_POLLS = 60


def handle_set_server_to_creating(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set DDB entry to CREATING status."""
    logger.info(f"Setting MCP server to CREATING status: {event.get('id')}")
    output_dict = deepcopy(event)

    server_id = event.get("id")

    if not server_id:
        raise ValueError("Missing required field: id")

    mcp_servers_table.update_item(
        Key={"id": server_id},
        UpdateExpression="SET #status = :status, last_modified = :lm",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": HostedMcpServerStatus.CREATING,
            ":lm": int(datetime.now(UTC).timestamp()),
        },
    )

    output_dict["server_status"] = HostedMcpServerStatus.CREATING
    return output_dict


def handle_deploy_server(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Invoke MCP server deployer to create infrastructure."""
    logger.info(f"Deploying MCP server: {event.get('id')}")
    output_dict = deepcopy(event)

    try:
        # Validate and build server config using Pydantic model
        # Exclude fields that the deployer doesn't need (owner, description, created, status)
        server_config_model = HostedMcpServerModel.model_validate(event)
        server_config = server_config_model.model_dump(
            exclude_none=True, exclude={"owner", "description", "created", "status"}
        )

        logger.info(f"Sending server config to deployer: {json.dumps(server_config)}")

        # Invoke the MCP server deployer
        response = lambdaClient.invoke(
            FunctionName=os.environ["MCP_SERVER_DEPLOYER_FN_ARN"],
            Payload=json.dumps({"mcpServerConfig": server_config}),
        )

        payload = response["Payload"].read()
        payload = json.loads(payload)
        stack_name = payload.get("stackName", None)

        if not stack_name:
            logger.error(f"MCP Server Deployer response: {payload}")
            raise ValueError(f"Failed to create MCP server stack: {payload}")

        response = cfnClient.describe_stacks(StackName=stack_name)
        stack_arn = response["Stacks"][0]["StackId"]

        mcp_servers_table.update_item(
            Key={"id": event.get("id")},
            UpdateExpression="SET #status = :status, stack_name = :stack_name, cloudformation_stack_arn = :stack_arn,"
            + " last_modified = :lm",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": HostedMcpServerStatus.CREATING,
                ":stack_name": stack_name,
                ":stack_arn": stack_arn,
                ":lm": int(datetime.now(UTC).timestamp()),
            },
        )
    except Exception as e:
        logger.error(f"Error deploying MCP server: {str(e)}")
        raise Exception(
            json.dumps(
                {
                    "error": f"Error deploying MCP server: {str(e)}",
                    "event": event,
                }
            )
        )

    output_dict["stack_name"] = stack_name
    output_dict["stack_arn"] = stack_arn
    output_dict["poll_count"] = 0
    output_dict["continue_polling"] = True
    return output_dict


def handle_poll_deployment(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Poll CloudFormation stack status."""
    logger.info(f"Polling deployment status for stack: {event.get('stack_name')}")
    output_dict = deepcopy(event)

    stack_name = event.get("stack_name")
    stack_arn = event.get("stack_arn")
    poll_count = event.get("poll_count", 0)

    if poll_count > MAX_POLLS:
        raise Exception(f"Max polls exceeded for stack {stack_name}")

    try:
        response = cfnClient.describe_stacks(StackName=stack_arn)
        stack_status = response["Stacks"][0]["StackStatus"]

        logger.info(f"Stack {stack_name} status: {stack_status}")

        # Check if stack creation is complete
        if stack_status in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]:
            output_dict["continue_polling"] = False
            output_dict["stack_status"] = stack_status
        elif stack_status.endswith("_FAILED") or stack_status.endswith("ROLLBACK_COMPLETE"):
            raise Exception(
                json.dumps(
                    {
                        "error": f"Stack {stack_name} failed with status: {stack_status}",
                        "event": event,
                    }
                )
            )
        else:
            # Still in progress
            output_dict["poll_count"] = poll_count + 1
            output_dict["continue_polling"] = True
    except Exception as e:
        logger.error(f"Error polling stack status: {str(e)}")
        raise Exception(
            json.dumps(
                {
                    "error": f"Error polling stack status: {str(e)}",
                    "event": event,
                }
            )
        )

    return output_dict


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


def _get_api_gateway_url(deployment_prefix: str) -> Optional[str]:
    """Get API Gateway base URL from SSM parameter."""
    try:
        response = ssmClient.get_parameter(Name=f"{deployment_prefix}/LisaApiUrl")
        return response["Parameter"]["Value"]
    except Exception as e:
        logger.warning(f"Error getting API Gateway URL: {str(e)}")
        return None


def _normalize_server_identifier(server_id: str) -> str:
    """Normalize server identifier to match CDK resource naming (alphanumeric only)."""
    return re.sub(r"[^a-zA-Z0-9]", "", server_id)


def handle_add_server_to_active(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set server status to IN_SERVICE after successful deployment."""
    logger.info(f"Setting MCP server to IN_SERVICE: {event.get('id')}")
    output_dict = deepcopy(event)

    server_id = event.get("id")
    stack_name = event.get("stack_name")
    name = event.get("name")
    description = event.get("description")
    idp_groups = event.get("groups", [])
    owner = event.get("owner", "lisa:public") if idp_groups != [] else "lisa:public"

    # Update server status to IN_SERVICE
    mcp_servers_table.update_item(
        Key={"id": server_id},
        UpdateExpression="SET #status = :status, stack_name = :stack_name, last_modified = :lm",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": HostedMcpServerStatus.IN_SERVICE,
            ":stack_name": stack_name,
            ":lm": int(datetime.now(UTC).timestamp()),
        },
    )

    # Create connection entry in MCP Connections table if chat is deployed
    deployment_prefix = os.environ.get("DEPLOYMENT_PREFIX", "")
    if deployment_prefix:
        mcp_connections_table_name = _get_mcp_connections_table_name(deployment_prefix)
        if mcp_connections_table_name:
            try:
                api_gateway_url = _get_api_gateway_url(deployment_prefix)
                if api_gateway_url:
                    # Normalize server ID to match what CDK uses for resource naming
                    normalized_id = _normalize_server_identifier(name)
                    # Construct API Gateway URL for the hosted server
                    server_url = f"{api_gateway_url}/mcp/{normalized_id}/mcp"

                    # Format groups with "group:" prefix if not already present
                    formatted_groups = []
                    for group in idp_groups:
                        if group.startswith("group:"):
                            formatted_groups.append(group)
                        else:
                            formatted_groups.append(f"group:{group}")

                    # Create connection entry
                    mcp_connections_table = ddbResource.Table(mcp_connections_table_name)
                    connection_entry = {
                        "id": server_id,
                        "owner": owner,
                        "url": server_url,
                        "name": name,
                        "created": datetime.now().isoformat(),
                        "customHeaders": {"Authorization": "Bearer {LISA_BEARER_TOKEN}"},
                        "status": McpServerStatus.ACTIVE,
                    }

                    if description:
                        connection_entry["description"] = description

                    if formatted_groups:
                        connection_entry["groups"] = formatted_groups

                    mcp_connections_table.put_item(Item=connection_entry)
                    logger.info(f"Created MCP connection entry for server {server_id} in connections table")
                else:
                    logger.warning("Could not get API Gateway URL, skipping connection entry creation")
            except Exception as e:
                logger.error(f"Error creating MCP connection entry: {str(e)}")
                # Don't fail the state machine if connection entry creation fails
        else:
            logger.info(
                "MCP connections table not found, skipping connection entry creation (chat may not be deployed)"
            )

    output_dict["server_status"] = "InService"
    return output_dict


def handle_failure(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle failure in the state machine."""
    logger.error(f"Handling MCP server creation failure: {event}")

    # Update server status to failed
    try:
        # Parse the error from Step Functions
        cause_data = json.loads(event["Cause"])
        error_message = cause_data["errorMessage"]

        # Try to parse the error message as JSON (for our custom exceptions)
        try:
            error_dict = json.loads(error_message)
            if isinstance(error_dict, dict) and "error" in error_dict:
                error_reason = error_dict["error"]
                original_event = error_dict.get("event", event)
            else:
                # If it's not our expected format, use the raw error message
                error_reason = str(error_dict) if error_dict else "Unknown error"
                original_event = event
        except (json.JSONDecodeError, TypeError):
            # If error_message is not JSON, use it directly
            error_reason = error_message
            original_event = event

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"Error parsing failure event: {str(e)}")
        error_reason = f"Failed to parse error details: {str(e)}"
        original_event = event

    logger.error(f"Failure reason: {error_reason}, ServerId: {original_event.get('id', 'unknown')}")

    mcp_servers_table.update_item(
        Key={"id": original_event.get("id", "unknown")},
        UpdateExpression="SET #status = :status, error_message = :error, last_modified = :lm",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": HostedMcpServerStatus.FAILED,
            ":error": event.get("error", "Unknown error"),
            ":lm": int(datetime.now(UTC).timestamp()),
        },
    )

    return event
