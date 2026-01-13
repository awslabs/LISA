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

"""Lambda handlers for UpdateMcpServer state machine."""

import logging
import os
import re
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.config import Config
from mcp_server.models import HostedMcpServerStatus, McpServerStatus
from utilities.time import now

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

lambdaConfig = Config(connect_timeout=60, read_timeout=600, retries={"max_attempts": 1})
ddbResource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
mcp_servers_table = ddbResource.Table(os.environ["MCP_SERVERS_TABLE_NAME"])
ecs_client = boto3.client("ecs", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
cfn_client = boto3.client("cloudformation", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
application_autoscaling_client = boto3.client(
    "application-autoscaling", region_name=os.environ["AWS_REGION"], config=lambdaConfig
)

MAX_POLLS = 30


def _get_mcp_connections_table_name(deployment_prefix: str) -> Optional[str]:
    """Get MCP connections table name from SSM parameter if chat is deployed."""
    try:
        response = ssm_client.get_parameter(Name=f"{deployment_prefix}/table/mcpServersTable")
        return response["Parameter"]["Value"]  # type: ignore[no-any-return]
    except ssm_client.exceptions.ParameterNotFound:
        logger.info("MCP connections table SSM parameter not found, chat may not be deployed")
        return None
    except Exception as e:
        logger.warning(f"Error getting MCP connections table name: {str(e)}")
        return None


def _normalize_server_identifier(server_id: str) -> str:
    """Normalize server identifier to match CDK resource naming (alphanumeric only)."""
    return re.sub(r"[^a-zA-Z0-9]", "", server_id)


def _update_simple_field(server_config: Dict[str, Any], field_name: str, value: Any, server_id: str) -> None:
    """Update a simple field in server_config."""
    logger.info(f"Setting {field_name} to '{value}' for server '{server_id}'")
    server_config[field_name] = value


def _update_container_config(
    server_config: Dict[str, Any], container_config: Dict[str, Any], server_id: str
) -> Dict[str, Any]:
    """Handle container config update.

    Returns:
        Dict containing any container config metadata needed for ECS updates
    """
    logger.info(f"Updating container configuration for server '{server_id}'")

    container_metadata = {}

    if container_config.get("environment") is not None:
        env_vars = container_config["environment"]
        env_vars_to_delete = []

        # Handle environment variable deletion markers
        for key, value in env_vars.items():
            if value == "LISA_MARKED_FOR_DELETION":
                env_vars_to_delete.append(key)

        for key in env_vars_to_delete:
            del env_vars[key]

        server_config["environment"] = env_vars

        # Store deletion info for ECS update
        if env_vars_to_delete:
            container_metadata["env_vars_to_delete"] = env_vars_to_delete
            logger.info(f"Deleted environment variables for server '{server_id}': {env_vars_to_delete}")
        logger.info(f"Updated environment variables for server '{server_id}': {env_vars}")

    # Update CPU
    if container_config.get("cpu") is not None:
        server_config["cpu"] = int(container_config["cpu"])
        logger.info(f"Updated CPU for server '{server_id}': {container_config['cpu']}")

    # Update memory
    if container_config.get("memoryLimitMiB") is not None:
        server_config["memoryLimitMiB"] = int(container_config["memoryLimitMiB"])
        logger.info(f"Updated memory for server '{server_id}': {container_config['memoryLimitMiB']}")

    # Update container health check configuration
    health_check_updates = {}
    if container_config.get("containerHealthCheckConfig") is not None:
        health_check_config = container_config["containerHealthCheckConfig"]
        if health_check_config.get("command") is not None:
            health_check_updates["command"] = health_check_config["command"]
        if health_check_config.get("interval") is not None:
            health_check_updates["interval"] = health_check_config["interval"]
        if health_check_config.get("timeout") is not None:
            health_check_updates["timeout"] = health_check_config["timeout"]
        if health_check_config.get("startPeriod") is not None:
            health_check_updates["startPeriod"] = health_check_config["startPeriod"]
        if health_check_config.get("retries") is not None:
            health_check_updates["retries"] = health_check_config["retries"]

        if health_check_updates:
            server_config["containerHealthCheckConfig"] = health_check_updates
            logger.info(
                f"Updated container health check configuration for server '{server_id}': {health_check_updates}"
            )

    # Update load balancer health check configuration
    if container_config.get("loadBalancerConfig") is not None:
        server_config["loadBalancerConfig"] = container_config["loadBalancerConfig"]
        logger.info(f"Updated load balancer configuration for server '{server_id}'")

    return container_metadata


def _get_metadata_update_handlers(server_config: Dict[str, Any], server_id: str) -> Dict[str, Callable[..., Any]]:
    """Return a dictionary mapping field names to their update handlers."""
    return {
        "description": lambda value: _update_simple_field(server_config, "description", value, server_id),
        "groups": lambda value: _update_simple_field(server_config, "groups", value, server_id),
        "environment": lambda value: _update_container_config(server_config, {"environment": value}, server_id),
        "cpu": lambda value: _update_container_config(server_config, {"cpu": value}, server_id),
        "memoryLimitMiB": lambda value: _update_container_config(server_config, {"memoryLimitMiB": value}, server_id),
        "containerHealthCheckConfig": lambda value: _update_container_config(
            server_config, {"containerHealthCheckConfig": value}, server_id
        ),
        "loadBalancerConfig": lambda value: _update_container_config(
            server_config, {"loadBalancerConfig": value}, server_id
        ),
    }


def _process_metadata_updates(
    server_config: Dict[str, Any], update_payload: Dict[str, Any], server_id: str
) -> tuple[bool, Dict[str, Any]]:
    """
    Process metadata updates.

    Args:
        server_config: The server configuration dictionary to update
        update_payload: The payload containing updates
        server_id: The server ID for logging purposes

    Returns:
        tuple: (has_updates: bool, metadata: Dict containing update metadata)
    """
    update_handlers = _get_metadata_update_handlers(server_config, server_id)
    has_updates = False
    update_metadata = {}

    # Handle container config fields specially
    container_config_fields = [
        "environment",
        "cpu",
        "memoryLimitMiB",
        "containerHealthCheckConfig",
        "loadBalancerConfig",
    ]
    container_config_updates = {}

    for field_name in container_config_fields:
        if field_name in update_payload and update_payload[field_name] is not None:
            container_config_updates[field_name] = update_payload[field_name]
            has_updates = True

    if container_config_updates:
        container_metadata = _update_container_config(server_config, container_config_updates, server_id)
        if container_metadata:
            update_metadata["container"] = container_metadata

    # Handle simple fields
    simple_fields = ["description", "groups"]
    for field_name in simple_fields:
        if field_name in update_payload and update_payload[field_name] is not None:
            update_handlers[field_name](update_payload[field_name])
            has_updates = True

    return has_updates, update_metadata


def _update_mcp_connections_table_status(server_id: str, status: str) -> None:
    """Update MCP Connections table status for a server."""
    deployment_prefix = os.environ.get("DEPLOYMENT_PREFIX", "")
    if not deployment_prefix:
        logger.info("No deployment prefix found, skipping MCP Connections table update")
        return

    mcp_connections_table_name = _get_mcp_connections_table_name(deployment_prefix)
    if not mcp_connections_table_name:
        logger.info("MCP connections table not found, skipping status update")
        return

    try:
        mcp_connections_table = ddbResource.Table(mcp_connections_table_name)
        # Scan for the connection entry with this server ID
        response = mcp_connections_table.scan(FilterExpression=Attr("id").eq(server_id))

        # Update the matching item(s)
        for item in response.get("Items", []):
            mcp_connections_table.update_item(
                Key={"id": item["id"], "owner": item["owner"]},
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": status},
            )
            logger.info(f"Updated MCP connection status for server {server_id} (owner: {item['owner']}) to {status}")
    except Exception as e:
        logger.warning(f"Error updating MCP Connections table status: {str(e)}")
        # Don't fail the update if connection table update fails


def _update_mcp_connections_table_metadata(
    server_id: str, description: Optional[str] = None, groups: Optional[List[str]] = None
) -> None:
    """Update MCP Connections table metadata (description, groups) for a server."""
    deployment_prefix = os.environ.get("DEPLOYMENT_PREFIX", "")
    if not deployment_prefix:
        logger.info("No deployment prefix found, skipping MCP Connections metadata update")
        return

    mcp_connections_table_name = _get_mcp_connections_table_name(deployment_prefix)
    if not mcp_connections_table_name:
        logger.info("MCP connections table not found, skipping metadata update")
        return

    # Nothing to update
    if description is None and groups is None:
        return

    # Format groups with "group:" prefix if not already present
    formatted_groups: Optional[List[str]] = None
    if groups is not None:
        formatted_groups = []
        for group in groups:
            if group.startswith("group:"):
                formatted_groups.append(group)
            else:
                formatted_groups.append(f"group:{group}")

    try:
        mcp_connections_table = ddbResource.Table(mcp_connections_table_name)
        # Scan for the connection entry with this server ID
        response = mcp_connections_table.scan(FilterExpression=Attr("id").eq(server_id))

        for item in response.get("Items", []):
            update_expression_parts = []
            expr_attr_names: Dict[str, str] = {}
            expr_attr_values: Dict[str, Any] = {}

            if description is not None:
                update_expression_parts.append("#d = :desc")
                expr_attr_names["#d"] = "description"
                expr_attr_values[":desc"] = description

            if formatted_groups is not None:
                update_expression_parts.append("#g = :groups")
                expr_attr_names["#g"] = "groups"
                expr_attr_values[":groups"] = formatted_groups

            if update_expression_parts:
                update_expression = "SET " + ", ".join(update_expression_parts)
                mcp_connections_table.update_item(
                    Key={"id": item["id"], "owner": item["owner"]},
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames=expr_attr_names if expr_attr_names else None,
                    ExpressionAttributeValues=expr_attr_values if expr_attr_values else None,
                )
                logger.info(
                    f"Updated MCP connection metadata for server {server_id} (owner: {item['owner']}): "
                    f"{'description ' if description is not None else ''}"
                    f"{'groups ' if groups is not None else ''}".strip()
                )
    except Exception as e:
        logger.warning(f"Error updating MCP Connections table metadata: {str(e)}")
        # Don't fail the update if connection table update fails


def handle_job_intake(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle initial UpdateMcpServer job submission.

    This handler will perform the following actions:
    1. Determine if any metadata (description, groups, environment, etc.) changes are required
    2. Determine if any AutoScaling changes are required
    3. Determine if enable/disable operation is required
    4. Commit changes to the database
    """
    output_dict = deepcopy(event)

    server_id = event["server_id"]
    logger.info(f"Processing UpdateMcpServer request for '{server_id}' with payload: {event}")
    server_key = {"id": server_id}
    ddb_item = mcp_servers_table.get_item(
        Key=server_key,
        ConsistentRead=True,
    ).get("Item", None)
    if not ddb_item:
        raise RuntimeError(f"Requested server '{server_id}' was not found in DynamoDB table.")

    server_status = ddb_item.get("status")
    stack_name = ddb_item.get("stack_name", None)

    if not stack_name:
        raise RuntimeError("Cannot update server that does not have a CloudFormation stack.")

    output_dict["stack_name"] = stack_name

    # Two checks for enabling: check that value was not omitted, then check that it was actually True.
    is_activation_request = event["update_payload"].get("enabled", None) is not None
    is_enable = event["update_payload"].get("enabled", False)
    is_disable = is_activation_request and not is_enable

    is_autoscaling_update = event["update_payload"].get("autoScalingConfig", None) is not None

    if is_activation_request and is_autoscaling_update:
        raise RuntimeError(
            "Cannot request AutoScaling updates at the same time as an enable or disable operation. "
            "Please perform those as two separate actions."
        )

    # set up DDB update expression to accumulate info as more options are processed
    ddb_update_expression = "SET #status = :ms, last_modified = :lm"
    ddb_update_values = {
        ":ms": HostedMcpServerStatus.UPDATING,
        ":lm": now(),
    }
    ExpressionAttributeNames = {"#status": "status"}

    # Process metadata updates (description, groups, environment, CPU, memory, health checks)
    server_config = {}
    # Copy existing server config fields that can be updated
    for field in [
        "description",
        "groups",
        "environment",
        "cpu",
        "memoryLimitMiB",
        "containerHealthCheckConfig",
        "loadBalancerConfig",
        "autoScalingConfig",
    ]:
        if field in ddb_item:
            server_config[field] = ddb_item[field]

    # Ensure autoScalingConfig exists if we're going to update it
    if is_autoscaling_update and "autoScalingConfig" not in server_config:
        raise RuntimeError("Cannot update auto-scaling config for server that does not have auto-scaling configured.")

    has_metadata_update, update_metadata = _process_metadata_updates(server_config, event["update_payload"], server_id)

    if is_activation_request:
        logger.info(f"Detected enable or disable activity for '{server_id}'")
        if is_enable:
            if server_status != HostedMcpServerStatus.STOPPED:
                raise RuntimeError(
                    f"Server cannot be enabled when it is not in the '{HostedMcpServerStatus.STOPPED}' state."
                )

            # Set status to Starting instead of Updating to signify that it can't be accessed by a user yet
            ddb_update_values[":ms"] = HostedMcpServerStatus.STARTING

            # Get current auto-scaling config to determine min capacity
            if "autoScalingConfig" not in server_config:
                raise RuntimeError("Cannot enable server that does not have auto-scaling configured.")
            min_capacity = server_config["autoScalingConfig"].get("minCapacity", 1)
            logger.info(f"Starting server '{server_id}' with min capacity of {min_capacity}.")

            # Store min capacity for later use in handle_finish_update
            output_dict["min_capacity"] = min_capacity

            # Scale ECS service to min capacity now (will be polled in handle_poll_capacity)
            try:
                service_arn, cluster_arn, _ = get_ecs_resources_from_stack(stack_name)
                ecs_client.update_service(cluster=cluster_arn, service=service_arn, desiredCount=int(min_capacity))
                logger.info(f"Scaled ECS service to {min_capacity} for server '{server_id}'")
            except Exception as e:
                logger.error(f"Error scaling ECS service to {min_capacity}: {str(e)}")
                raise RuntimeError(f"Failed to scale ECS service to {min_capacity}: {str(e)}")
        else:
            # Only if we are deactivating a server, we update MCP Connections table
            logger.info(f"Updating MCP Connections table for server '{server_id}' because of 'disable' activity.")
            _update_mcp_connections_table_status(server_id, McpServerStatus.INACTIVE)

            # set status to Stopping instead of Updating to signify why it was removed
            ddb_update_values[":ms"] = HostedMcpServerStatus.STOPPING

            # Scale ECS service to 0 (will be handled immediately)
            output_dict["desired_capacity"] = 0

            # Update ECS service immediately for disable
            try:
                # Get ECS resources from stack
                service_arn, cluster_arn, _ = get_ecs_resources_from_stack(stack_name)

                # Also set Application Auto Scaling target min/max to 0 to prevent immediate scale-up by policies
                try:
                    service_name = service_arn.split("/")[-1]
                    cluster_name = cluster_arn.split("/")[-1]
                    scalable_target_id = f"service/{cluster_name}/{service_name}"
                    application_autoscaling_client.register_scalable_target(
                        ServiceNamespace="ecs",
                        ResourceId=scalable_target_id,
                        ScalableDimension="ecs:service:DesiredCount",
                        MinCapacity=0,
                        MaxCapacity=0,
                    )
                    logger.info(
                        "Updated scalable target to MinCapacity=0, MaxCapacity=0 for server "
                        + f"'{server_id}' ({scalable_target_id})"
                    )
                except Exception as e:
                    logger.warning(f"Could not update scalable target to 0 for server '{server_id}': {str(e)}")

                # Update service to 0 desired count
                ecs_client.update_service(cluster=cluster_arn, service=service_arn, desiredCount=0)
                logger.info(f"Scaled ECS service to 0 for server '{server_id}'")
            except Exception as e:
                logger.error(f"Error scaling ECS service to 0: {str(e)}")
                raise RuntimeError(f"Failed to scale ECS service to 0: {str(e)}")

    if is_autoscaling_update:
        asg_config = event["update_payload"]["autoScalingConfig"]
        # Stage metadata updates regardless of immediate capacity changes or not
        # Merge updates with existing config (autoScalingConfig already exists, validated above)
        updated_min_capacity = None
        updated_max_capacity = None
        if minCapacity := asg_config.get("minCapacity"):
            server_config["autoScalingConfig"]["minCapacity"] = int(minCapacity)
            updated_min_capacity = int(minCapacity)
        if maxCapacity := asg_config.get("maxCapacity"):
            server_config["autoScalingConfig"]["maxCapacity"] = int(maxCapacity)
            updated_max_capacity = int(maxCapacity)
        if cooldown := asg_config.get("cooldown"):
            server_config["autoScalingConfig"]["cooldown"] = int(cooldown)
        if targetValue := asg_config.get("targetValue"):
            server_config["autoScalingConfig"]["targetValue"] = int(targetValue)
        if metricName := asg_config.get("metricName"):
            server_config["autoScalingConfig"]["metricName"] = metricName
        if duration := asg_config.get("duration"):
            server_config["autoScalingConfig"]["duration"] = int(duration)

        # If server is running, apply update immediately via Application Auto Scaling
        if server_status == HostedMcpServerStatus.IN_SERVICE:
            try:
                # Get ECS resources from stack
                service_arn, cluster_arn, _ = get_ecs_resources_from_stack(stack_name)

                # Get service name from ARN
                service_name = service_arn.split("/")[-1]
                cluster_name = cluster_arn.split("/")[-1]

                # Update scalable target
                scalable_target_id = f"service/{cluster_name}/{service_name}"

                update_params = {
                    "ServiceNamespace": "ecs",
                    "ResourceId": scalable_target_id,
                    "ScalableDimension": "ecs:service:DesiredCount",
                }

                # Use updated values if provided, otherwise use current values from server_config
                if updated_min_capacity is not None:
                    update_params["MinCapacity"] = updated_min_capacity
                else:
                    update_params["MinCapacity"] = server_config["autoScalingConfig"].get("minCapacity", 1)

                if updated_max_capacity is not None:
                    update_params["MaxCapacity"] = updated_max_capacity
                else:
                    update_params["MaxCapacity"] = server_config["autoScalingConfig"].get("maxCapacity", 1)

                application_autoscaling_client.register_scalable_target(**update_params)
                logger.info(f"Updated auto-scaling configuration for server '{server_id}': {update_params}")

                # Note: Scaling policies would need to be updated separately if they changed
                # For now, we only update min/max capacity
            except Exception as e:
                logger.error(f"Error updating auto-scaling configuration: {str(e)}")
                raise RuntimeError(f"Failed to update auto-scaling configuration: {str(e)}")

        has_metadata_update = True

    if has_metadata_update:
        # Update server config in DynamoDB - only include fields that were actually updated
        update_payload = event["update_payload"]

        if "description" in update_payload and update_payload["description"] is not None:
            ddb_update_expression += ", description = :desc"
            ddb_update_values[":desc"] = server_config.get("description")

        if "groups" in update_payload and update_payload["groups"] is not None:
            ddb_update_expression += ", groups = :groups"
            ddb_update_values[":groups"] = server_config.get("groups", [])

        # Update container config fields if they were in the update payload
        if "environment" in update_payload and update_payload["environment"] is not None:
            ddb_update_expression += ", environment = :env"
            ddb_update_values[":env"] = server_config.get("environment", {})
        if "cpu" in update_payload and update_payload["cpu"] is not None:
            ddb_update_expression += ", cpu = :cpu"
            ddb_update_values[":cpu"] = server_config.get("cpu")
        if "memoryLimitMiB" in update_payload and update_payload["memoryLimitMiB"] is not None:
            ddb_update_expression += ", memoryLimitMiB = :memory"
            ddb_update_values[":memory"] = server_config.get("memoryLimitMiB")
        if "containerHealthCheckConfig" in update_payload and update_payload["containerHealthCheckConfig"] is not None:
            ddb_update_expression += ", containerHealthCheckConfig = :health"
            ddb_update_values[":health"] = server_config.get("containerHealthCheckConfig")
        if "loadBalancerConfig" in update_payload and update_payload["loadBalancerConfig"] is not None:
            ddb_update_expression += ", loadBalancerConfig = :lb"
            ddb_update_values[":lb"] = server_config.get("loadBalancerConfig")
        if "autoScalingConfig" in update_payload and update_payload["autoScalingConfig"] is not None:
            ddb_update_expression += ", autoScalingConfig = :asg"
            ddb_update_values[":asg"] = server_config.get("autoScalingConfig")

    # Pass through container metadata for ECS updates
    if update_metadata.get("container"):
        output_dict["container_metadata"] = update_metadata["container"]

    logger.info(f"Server '{server_id}' update expression: {ddb_update_expression}")
    logger.info(f"Server '{server_id}' update values: {list(ddb_update_values.keys())}")

    mcp_servers_table.update_item(
        Key=server_key,
        UpdateExpression=ddb_update_expression,
        ExpressionAttributeValues=ddb_update_values,
        ExpressionAttributeNames=ExpressionAttributeNames,
    )

    # If metadata changed, reflect updates in MCP Connections table
    try:
        update_payload = event["update_payload"]
        should_update_description = "description" in update_payload and update_payload["description"] is not None
        should_update_groups = "groups" in update_payload and update_payload["groups"] is not None
        if should_update_description or should_update_groups:
            _update_mcp_connections_table_metadata(
                server_id=server_id,
                description=server_config.get("description") if should_update_description else None,
                groups=server_config.get("groups") if should_update_groups else None,
            )
    except Exception as e:
        # Don't fail the update flow for connection metadata update errors
        logger.warning(f"Non-fatal error updating MCP Connections metadata: {str(e)}")

    # Determine if ECS update is needed (container config changes for running servers)
    needs_ecs_update = (
        event["update_payload"].get("environment") is not None
        or event["update_payload"].get("cpu") is not None
        or event["update_payload"].get("memoryLimitMiB") is not None
        or event["update_payload"].get("containerHealthCheckConfig") is not None
    ) and server_status == HostedMcpServerStatus.IN_SERVICE

    # We only need to poll for activation so that we know when to update the MCP Connections table
    # For Hosted MCP servers, also poll on disable to wait for tasks to deprovision fully
    output_dict["has_capacity_update"] = is_enable or is_disable
    output_dict["is_disable"] = is_disable
    output_dict["needs_ecs_update"] = needs_ecs_update
    output_dict["initial_server_status"] = server_status  # needed for simple metadata updates
    output_dict["current_server_status"] = ddb_update_values[":ms"]  # for state machine debugging / visibility

    return output_dict


def get_ecs_resources_from_stack(stack_name: str) -> tuple[str, str, str]:
    """Extract ECS service name, cluster name, and current task definition ARN from CloudFormation."""
    try:
        resources = cfn_client.describe_stack_resources(StackName=stack_name)["StackResources"]

        service_arn = None
        cluster_arn = None

        for resource in resources:
            if resource["ResourceType"] == "AWS::ECS::Service":
                service_arn = resource["PhysicalResourceId"]
            elif resource["ResourceType"] == "AWS::ECS::Cluster":
                cluster_arn = resource["PhysicalResourceId"]

        if not service_arn or not cluster_arn:
            raise RuntimeError(f"Could not find ECS service or cluster in stack {stack_name}")

        # Get current task definition from service
        service_info = ecs_client.describe_services(cluster=cluster_arn, services=[service_arn])["services"][0]

        current_task_def_arn = service_info["taskDefinition"]

        return service_arn, cluster_arn, current_task_def_arn

    except Exception as e:
        logger.error(f"Error getting ECS resources from stack {stack_name}: {str(e)}")
        raise RuntimeError(f"Failed to get ECS resources from CloudFormation stack: {str(e)}")


def create_updated_task_definition(
    task_definition_arn: str,
    updated_env_vars: Optional[Dict[str, str]] = None,
    env_vars_to_delete: Optional[List[str]] = None,
    updated_cpu: Optional[int] = None,
    updated_memory: Optional[int] = None,
    updated_health_check: Optional[Dict[str, Any]] = None,
) -> str:
    """Create new task definition revision with updated configuration.

    Args:
        task_definition_arn: ARN of the current task definition
        updated_env_vars: Environment variables to add/update
        env_vars_to_delete: List of environment variable names to delete
        updated_cpu: Updated CPU units
        updated_memory: Updated memory limit in MiB
        updated_health_check: Updated container health check configuration
    """
    try:
        if env_vars_to_delete is None:
            env_vars_to_delete = []
        if updated_env_vars is None:
            updated_env_vars = {}

        # Get current task definition
        task_def_response = ecs_client.describe_task_definition(taskDefinition=task_definition_arn)
        task_def = task_def_response["taskDefinition"]

        # Create new task definition with updated configuration
        new_task_def = {
            "family": task_def["family"],
            "volumes": task_def.get("volumes", []),
            "containerDefinitions": [],
        }

        # Add optional fields only if they have valid values
        if task_def.get("taskRoleArn"):
            new_task_def["taskRoleArn"] = task_def["taskRoleArn"]
        if task_def.get("executionRoleArn"):
            new_task_def["executionRoleArn"] = task_def["executionRoleArn"]
        if task_def.get("networkMode"):
            new_task_def["networkMode"] = task_def["networkMode"]
        if task_def.get("requiresCompatibilities"):
            new_task_def["requiresCompatibilities"] = task_def["requiresCompatibilities"]

        # Update CPU and memory if provided
        if updated_cpu is not None:
            new_task_def["cpu"] = str(updated_cpu)
        elif task_def.get("cpu") is not None:
            new_task_def["cpu"] = str(task_def["cpu"])

        if updated_memory is not None:
            new_task_def["memory"] = str(updated_memory)
        elif task_def.get("memory") is not None:
            new_task_def["memory"] = str(task_def["memory"])

        # Update container definitions
        for container in task_def["containerDefinitions"]:
            new_container = container.copy()

            # Start with existing environment variables from the task definition
            existing_env = {env["name"]: env["value"] for env in container.get("environment", [])}
            logger.info(f"Existing environment variables: {list(existing_env.keys())}")

            # Apply updates/additions
            existing_env.update(updated_env_vars)
            logger.info(f"Environment variables after update: {list(existing_env.keys())}")

            # Remove deleted variables
            for var_name in env_vars_to_delete:
                if var_name in existing_env:
                    del existing_env[var_name]
                    logger.info(f"Deleted environment variable: {var_name}")

            logger.info(f"Final environment variables: {list(existing_env.keys())}")

            # Set the new environment variables
            new_container["environment"] = [{"name": key, "value": value} for key, value in existing_env.items()]

            # Update health check configuration if provided
            if updated_health_check:
                current_health_check = new_container.get("healthCheck", {})

                # Update individual health check fields
                if updated_health_check.get("command") is not None:
                    current_health_check["command"] = updated_health_check["command"]
                if updated_health_check.get("interval") is not None:
                    current_health_check["interval"] = int(updated_health_check["interval"])
                if updated_health_check.get("timeout") is not None:
                    current_health_check["timeout"] = int(updated_health_check["timeout"])
                if updated_health_check.get("startPeriod") is not None:
                    current_health_check["startPeriod"] = int(updated_health_check["startPeriod"])
                if updated_health_check.get("retries") is not None:
                    current_health_check["retries"] = int(updated_health_check["retries"])

                new_container["healthCheck"] = current_health_check
                logger.info(f"Updated container health check: {current_health_check}")

            new_task_def["containerDefinitions"].append(new_container)

        # Register new task definition
        response = ecs_client.register_task_definition(**new_task_def)
        new_task_def_arn = str(response["taskDefinition"]["taskDefinitionArn"])

        logger.info(f"Created new task definition: {new_task_def_arn}")
        return new_task_def_arn

    except Exception as e:
        logger.error(f"Error creating updated task definition: {str(e)}")
        raise RuntimeError(f"Failed to create updated task definition: {str(e)}")


def update_ecs_service(cluster_arn: str, service_arn: str, task_definition_arn: str) -> None:
    """Update ECS service to use new task definition."""
    try:
        ecs_client.update_service(
            cluster=cluster_arn,
            service=service_arn,
            taskDefinition=task_definition_arn,
            forceNewDeployment=True,
        )
        logger.info(f"Updated ECS service {service_arn} to use task definition {task_definition_arn}")

    except Exception as e:
        logger.error(f"Error updating ECS service: {str(e)}")
        raise RuntimeError(f"Failed to update ECS service: {str(e)}")


def handle_ecs_update(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Update ECS task definition with new environment variables and update service.

    This handler will:
    1. Retrieve current task definition from ECS
    2. Create new task definition revision with updated configuration
    3. Update ECS service to use new task definition
    4. Set up for deployment monitoring
    """
    output_dict = deepcopy(event)
    server_id = event["server_id"]

    logger.info(f"Starting ECS update for server '{server_id}'")

    try:
        # Get current server info from DDB (consistent read to ensure we see the latest env/cpu/memory)
        ddb_item = mcp_servers_table.get_item(Key={"id": server_id}, ConsistentRead=True)["Item"]
        stack_name = ddb_item.get("stack_name")

        if not stack_name:
            raise RuntimeError(f"No CloudFormation stack found for server '{server_id}'")

        # Get ECS service and task definition from CloudFormation stack
        service_arn, cluster_arn, task_definition_arn = get_ecs_resources_from_stack(stack_name)

        # Get updated environment variables from server config
        updated_env_vars = ddb_item.get("environment", {})

        # Get environment variables to delete from container metadata (if available)
        env_vars_to_delete = []
        if container_metadata := event.get("container_metadata"):
            env_vars_to_delete = container_metadata.get("env_vars_to_delete", [])

        logger.info(f"Environment variables to delete: {env_vars_to_delete}")

        # Get updated CPU and memory
        updated_cpu = ddb_item.get("cpu")
        updated_memory = ddb_item.get("memoryLimitMiB")

        # Get updated health check config
        updated_health_check = ddb_item.get("containerHealthCheckConfig")

        # Create new task definition with updated configuration
        new_task_def_arn = create_updated_task_definition(
            task_definition_arn, updated_env_vars, env_vars_to_delete, updated_cpu, updated_memory, updated_health_check
        )

        # Update ECS service to use new task definition
        update_ecs_service(cluster_arn, service_arn, new_task_def_arn)

        # Set up tracking for deployment monitoring
        output_dict["new_task_definition_arn"] = new_task_def_arn
        output_dict["ecs_service_arn"] = service_arn
        output_dict["ecs_cluster_arn"] = cluster_arn
        output_dict["remaining_ecs_polls"] = MAX_POLLS

        logger.info(f"Successfully initiated ECS update for server '{server_id}'")

    except Exception as e:
        logger.error(f"ECS update failed for server '{server_id}': {str(e)}")
        output_dict["ecs_update_error"] = str(e)

    return output_dict


def handle_poll_ecs_deployment(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Monitor ECS service deployment progress.

    This handler will:
    1. Check if ECS service deployment is complete
    2. Return boolean for continued polling if needed
    3. Handle deployment failures
    """
    output_dict = deepcopy(event)
    server_id = event["server_id"]

    # Check if there was an error in the ECS update step
    if event.get("ecs_update_error"):
        logger.error(f"ECS update error for server '{server_id}': {event['ecs_update_error']}")
        output_dict["should_continue_ecs_polling"] = False
        return output_dict

    cluster_name = event["ecs_cluster_arn"]
    service_name = event["ecs_service_arn"]
    new_task_def_arn = event["new_task_definition_arn"]

    try:
        # Get service deployment status
        services = ecs_client.describe_services(cluster=cluster_name, services=[service_name])["services"]

        if not services:
            raise RuntimeError(f"ECS service {service_name} not found")

        service = services[0]
        deployments = service["deployments"]

        # Check if deployment is stable
        is_deployment_stable = True
        primary_deployment = None

        # Look for our deployment
        for deployment in deployments:
            task_def = deployment["taskDefinition"]
            # Handle both full ARN and family:revision format
            if task_def == new_task_def_arn or (
                new_task_def_arn.endswith(task_def.split(":")[-1])
                and task_def.startswith(new_task_def_arn.split(":")[0])
            ):
                primary_deployment = deployment
                logger.info(
                    f"Found matching deployment: status={deployment['status']}, "
                    f"rolloutState={deployment.get('rolloutState', 'N/A')}"
                )
                if deployment["status"] != "PRIMARY" or deployment.get("rolloutState") != "COMPLETED":
                    is_deployment_stable = False
                    logger.info(
                        f"Deployment not yet stable: status={deployment['status']}, "
                        f"rolloutState={deployment.get('rolloutState', 'N/A')}"
                    )
                else:
                    logger.info("Deployment is stable and completed")
                break

        if not primary_deployment:
            logger.warning(f"Could not find deployment for task definition {new_task_def_arn}")
            logger.warning(f"Available task definitions: {[d['taskDefinition'] for d in deployments]}")
            is_deployment_stable = False

        # Check polling limits
        remaining_polls = event.get("remaining_ecs_polls", MAX_POLLS) - 1
        if remaining_polls <= 0 and not is_deployment_stable:
            logger.error(f"ECS deployment polling timeout for server '{server_id}'")
            output_dict["ecs_polling_error"] = (
                f"ECS deployment did not complete within expected time for server '{server_id}'"
            )
            output_dict["should_continue_ecs_polling"] = False
            return output_dict

        should_continue_polling = not is_deployment_stable and remaining_polls > 0

        output_dict["should_continue_ecs_polling"] = should_continue_polling
        output_dict["remaining_ecs_polls"] = remaining_polls

        if is_deployment_stable:
            logger.info(f"ECS deployment completed successfully for server '{server_id}'")
        else:
            logger.info(
                f"ECS deployment still in progress for server '{server_id}', remaining polls: {remaining_polls}"
            )

    except Exception as e:
        logger.error(f"Error polling ECS deployment for server '{server_id}': {str(e)}")
        output_dict["ecs_polling_error"] = f"Error polling ECS deployment: {str(e)}"
        output_dict["should_continue_ecs_polling"] = False

    return output_dict


def handle_poll_capacity(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Poll ECS service to confirm if the capacity is done updating.

    This handler will:
    1. Get the ECS service's current status. If it is still updating, then exit with a
       boolean to indicate for more polling
    2. If the service status has completed, validate that it has the desired number of
       running tasks
    3. If both match, then discontinue polling
    """
    output_dict = deepcopy(event)
    server_id = event["server_id"]
    stack_name = event["stack_name"]
    logger.info(f"Polling capacity for server {server_id}, Stack: {stack_name}")

    try:
        service_arn, cluster_arn, _ = get_ecs_resources_from_stack(stack_name)
        service_info = ecs_client.describe_services(cluster=cluster_arn, services=[service_arn])["services"][0]

        desired_count = service_info["desiredCount"]
        running_count = service_info["runningCount"]

        remaining_polls = event.get("remaining_capacity_polls", MAX_POLLS) - 1
        if remaining_polls <= 0:
            output_dict["polling_error"] = (
                f"Server '{server_id}' did not start healthy tasks in expected amount of time."
            )

        should_continue_polling = desired_count != running_count and remaining_polls > 0

        output_dict["should_continue_capacity_polling"] = should_continue_polling
        output_dict["remaining_capacity_polls"] = remaining_polls

        logger.info(
            f"Server '{server_id}' capacity: desired={desired_count}, running={running_count}, "
            f"continue_polling={should_continue_polling}"
        )

    except Exception as e:
        logger.error(f"Error polling capacity for server '{server_id}': {str(e)}")
        output_dict["polling_error"] = f"Error polling capacity: {str(e)}"
        output_dict["should_continue_capacity_polling"] = False

    return output_dict


def handle_finish_update(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Finalize update in DDB.

    1. If the server was enabled from the Stopped state, update MCP Connections table to ACTIVE,
       set status to InService in DDB
    2. If the server was disabled from the InService state, set status to Stopped
    3. Commit changes to DDB
    """
    output_dict = deepcopy(event)

    server_id = event["server_id"]
    server_key = {"id": server_id}
    stack_name = event["stack_name"]

    ddb_update_expression = "SET #status = :ms, last_modified = :lm"
    ddb_update_values: Dict[str, Any] = {
        ":lm": now(),
    }
    ExpressionAttributeNames = {"#status": "status"}

    if polling_error := event.get("polling_error", None):
        logger.error(f"{polling_error} Setting ECS service back to 0 tasks.")
        try:
            service_arn, cluster_arn, _ = get_ecs_resources_from_stack(stack_name)
            ecs_client.update_service(cluster=cluster_arn, service=service_arn, desiredCount=0)
        except Exception as e:
            logger.error(f"Error scaling service to 0: {str(e)}")
        ddb_update_values[":ms"] = HostedMcpServerStatus.STOPPED
    elif event["is_disable"]:
        ddb_update_values[":ms"] = HostedMcpServerStatus.STOPPED
    elif event["has_capacity_update"]:
        ddb_update_values[":ms"] = HostedMcpServerStatus.IN_SERVICE

        # Update MCP Connections table to ACTIVE (service was already scaled in handle_job_intake)
        _update_mcp_connections_table_status(server_id, McpServerStatus.ACTIVE)
        logger.info(f"Updated MCP Connections table to ACTIVE for server '{server_id}'")
    else:  # No polling error, not disabled, and no capacity update means this was a metadata update, keep initial state
        ddb_update_values[":ms"] = event["initial_server_status"]

    mcp_servers_table.update_item(
        Key=server_key,
        UpdateExpression=ddb_update_expression,
        ExpressionAttributeValues=ddb_update_values,
        ExpressionAttributeNames=ExpressionAttributeNames,
    )

    output_dict["current_server_status"] = ddb_update_values[":ms"]

    return output_dict
