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

"""Lambda handlers for UpdateModel state machine."""

import json
import logging
import os
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict

import boto3
from models.clients.litellm_client import LiteLLMClient
from models.domain_objects import ModelStatus
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config

ddbResource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
model_table = ddbResource.Table(os.environ["MODEL_TABLE_NAME"])
autoscaling_client = boto3.client("autoscaling", region_name=os.environ["AWS_REGION"], config=retry_config)
ecs_client = boto3.client("ecs", region_name=os.environ["AWS_REGION"], config=retry_config)
cfn_client = boto3.client("cloudformation", region_name=os.environ["AWS_REGION"], config=retry_config)
iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)
secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)

litellm_client = LiteLLMClient(
    base_uri=get_rest_api_container_endpoint(),
    verify=get_cert_path(iam_client),
    headers={
        "Authorization": secrets_manager.get_secret_value(
            SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), VersionStage="AWSCURRENT"
        )["SecretString"],
        "Content-Type": "application/json",
    },
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def handle_job_intake(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle initial UpdateModel job submission.

    This handler will perform the following actions:
    1. Determine if any metadata (streaming, or modelType) changes are required
        1. If so, accumulate changes for a ddb update expression
    2. Determine if any AutoScaling changes are required
        1. If so, accumulate changes for a ddb update expression, set status to Updating
        2. If disabling or setting desired capacity to 0, then remove model entry from LiteLLM
            1. accumulate update expression to set the previous LiteLLM ID to null/None
    3. If any desired capacity changes are required, set a boolean value for a poll/wait loop on capacity changes
    4. Commit changes to the database
    """
    output_dict = deepcopy(event)

    model_id = event["model_id"]
    logger.info(f"Processing UpdateModel request for '{model_id}' with payload: {event}")
    model_key = {"model_id": model_id}
    ddb_item = model_table.get_item(
        Key=model_key,
        ConsistentRead=True,
    ).get("Item", None)
    if not ddb_item:
        raise RuntimeError(f"Requested model '{model_id}' was not found in DynamoDB table.")

    model_config = ddb_item["model_config"]  # all model creation params
    model_status = ddb_item["model_status"]
    model_asg = ddb_item.get("auto_scaling_group", None)  # ASG name for LISA-hosted models. None if LiteLLM-only model.

    output_dict["asg_name"] = model_asg  # add to event dict for convenience in later functions

    # keep track of model wait time for model startup later. autoscaling marks instances as healthy even though the
    # models have not fully stood up yet, so this is another protection to make sure that the model is actually
    # running before users can run inference against it. Will not be defined for LiteLLM-only models.
    if model_asg:
        output_dict["model_warmup_seconds"] = model_config["autoScalingConfig"]["metricConfig"][
            "estimatedInstanceWarmup"
        ]

    # Two checks for enabling: check that value was not omitted, then check that it was actually True.
    is_activation_request = event["update_payload"].get("enabled", None) is not None
    is_enable = event["update_payload"].get("enabled", False)
    is_disable = is_activation_request and not is_enable

    is_autoscaling_update = event["update_payload"].get("autoScalingInstanceConfig", None) is not None

    if not model_asg and (is_activation_request or is_autoscaling_update):
        raise RuntimeError("Cannot request AutoScaling updates to models that are not hosted by LISA.")

    if is_activation_request and is_autoscaling_update:
        raise RuntimeError(
            "Cannot request AutoScaling updates at the same time as an enable or disable operation. "
            "Please perform those as two separate actions."
        )

    # set up DDB update expression to accumulate info as more options are processed
    ddb_update_expression = "SET model_status = :ms, last_modified_date = :lm"
    ddb_update_values = {
        ":ms": ModelStatus.UPDATING,
        ":lm": int(datetime.utcnow().timestamp()),
    }

    if is_activation_request:
        logger.info(f"Detected enable or disable activity for '{model_id}'")
        if is_enable:
            previous_min = int(model_config["autoScalingConfig"]["minCapacity"])
            previous_max = int(model_config["autoScalingConfig"]["maxCapacity"])
            logger.info(f"Starting model '{model_id}' with min/max capacity of {previous_min}/{previous_max}.")

            # Set status to Starting instead of Updating to signify that it can't be accessed by a user yet
            ddb_update_values[":ms"] = ModelStatus.STARTING

            # Start ASG update with all 0/0/0 = min/max/desired to scale the model down to 0 instances
            autoscaling_client.update_auto_scaling_group(
                AutoScalingGroupName=model_asg,
                MinSize=previous_min,
                MaxSize=previous_max,
            )
        else:
            # Only if we are deactivating a model, we remove from LiteLLM. It is already removed otherwise.
            logger.info(f"Removing model '{model_id}' from LiteLLM because of 'disable' activity.")
            # remove model from LiteLLM so users can't select a deactivating model
            litellm_id = ddb_item["litellm_id"]
            litellm_client.delete_model(identifier=litellm_id)
            # remove ID from DDB as LiteLLM will no longer have this reference
            ddb_update_expression += ", litellm_id = :li"
            ddb_update_values[":li"] = None
            # set status to Stopping instead of Updating to signify why it was removed from OpenAI endpoint
            ddb_update_values[":ms"] = ModelStatus.STOPPING

            # Start ASG update with all 0/0/0 = min/max/desired to scale the model down to 0 instances
            autoscaling_client.update_auto_scaling_group(
                AutoScalingGroupName=model_asg,
                MinSize=0,
                MaxSize=0,
                DesiredCapacity=0,
            )

    if is_autoscaling_update:
        asg_config = event["update_payload"]["autoScalingInstanceConfig"]
        # Stage metadata updates regardless of immediate capacity changes or not
        if minCapacity := asg_config.get("minCapacity", False):
            model_config["autoScalingConfig"]["minCapacity"] = int(minCapacity)
        if maxCapacity := asg_config.get("maxCapacity", False):
            model_config["autoScalingConfig"]["maxCapacity"] = int(maxCapacity)
        # If model is running, apply update immediately, else set metadata but don't apply until an 'enable' operation
        if model_status == ModelStatus.IN_SERVICE:
            asg_update_payload = {
                "AutoScalingGroupName": model_asg,
            }
            if minCapacity:
                asg_update_payload["MinSize"] = int(minCapacity)
            if maxCapacity:
                asg_update_payload["MaxSize"] = int(maxCapacity)
            if desiredCapacity := asg_config.get("desiredCapacity", False):
                asg_update_payload["DesiredCapacity"] = int(desiredCapacity)

            # Start ASG update with known parameters. Because of model validations, at least one arg is guaranteed.
            autoscaling_client.update_auto_scaling_group(**asg_update_payload)

    # TODO: Clean up how metadata updates are handled
    # metadata updates
    payload_model_type = event["update_payload"].get("modelType", None)
    is_payload_streaming_update = (payload_streaming := event["update_payload"].get("streaming", None)) is not None
    payload_model_description = event["update_payload"].get("modelDescription", None)
    payload_allowed_groups = event["update_payload"].get("allowedGroups", None)
    payload_features = event["update_payload"].get("features", None)
    payload_container_config = event["update_payload"].get("containerConfig", None)
    
    has_metadata_update = (payload_model_type or is_payload_streaming_update or 
                          payload_model_description is not None or payload_allowed_groups is not None or 
                          payload_features is not None or payload_container_config is not None or is_autoscaling_update)

    if has_metadata_update:
        if payload_model_type:
            logger.info(f"Setting type '{payload_model_type}' for model '{model_id}'")
            model_config["modelType"] = payload_model_type
        if is_payload_streaming_update:
            logger.info(f"Setting streaming to '{payload_streaming}' for model '{model_id}'")
            model_config["streaming"] = payload_streaming
        if payload_model_description is not None:
            logger.info(f"Setting model description for model '{model_id}'")
            model_config["modelDescription"] = payload_model_description
        if payload_allowed_groups is not None:
            logger.info(f"Setting allowed groups for model '{model_id}'")
            model_config["allowedGroups"] = payload_allowed_groups
        if payload_features is not None:
            logger.info(f"Setting features for model '{model_id}'")
            model_config["features"] = payload_features
        if payload_container_config is not None:
            logger.info(f"Updating container configuration for model '{model_id}'")
            
            if payload_container_config.get("environment") is not None:

                env_vars = payload_container_config["environment"]
                env_vars_to_delete = []
                
                for key, value in env_vars.items():
                    if value == "DELETE":
                        env_vars_to_delete.append(key)
                    
                for key in env_vars_to_delete:
                    del env_vars[key]

                model_config["containerConfig"]["environment"] = env_vars

                if env_vars_to_delete:
                    logger.info(f"Deleted environment variables for model '{model_id}': {env_vars_to_delete}")
                logger.info(f"Updated environment variables for model '{model_id}': {env_vars}")

            # Update other container config fields if provided
            if payload_container_config.get("sharedMemorySize") is not None:
                model_config["containerConfig"]["sharedMemorySize"] = payload_container_config["sharedMemorySize"]
                logger.info(f"Updated shared memory size for model '{model_id}': {payload_container_config['sharedMemorySize']}")

        ddb_update_expression += ", model_config = :mc"
        ddb_update_values[":mc"] = model_config

    logger.info(f"Model '{model_id}' update expression: {ddb_update_expression}")
    logger.info(f"Model '{model_id}' update values: {ddb_update_values}")

    model_table.update_item(
        Key=model_key,
        UpdateExpression=ddb_update_expression,
        ExpressionAttributeValues=ddb_update_values,
    )

    # Determine if ECS update is needed (container config changes for LISA-hosted models)
    needs_ecs_update = (payload_container_config is not None and model_asg is not None and 
                       model_status == ModelStatus.IN_SERVICE)
    
    # We only need to poll for activation so that we know when to add the model back to LiteLLM
    output_dict["has_capacity_update"] = is_enable
    output_dict["is_disable"] = is_disable
    output_dict["needs_ecs_update"] = needs_ecs_update
    output_dict["initial_model_status"] = model_status  # needed for simple metadata updates
    output_dict["current_model_status"] = ddb_update_values[":ms"]  # for state machine debugging / visibility
    return output_dict


def handle_poll_capacity(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Poll autoscaling and target group to confirm if the capacity is done updating.

    This handler will:
    1. Get the ASG's current status. If it is still updating, then exit with a boolean to indicate for more polling
    2. If the ASG status has completed, validate with the load balancer's target group that it also has the same
        number of healthy instances
    3. If both the ASG and target group healthy instances match, then discontinue polling
    """
    output_dict = deepcopy(event)
    model_id = event["model_id"]
    asg_name = event["asg_name"]
    asg_info = autoscaling_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])["AutoScalingGroups"][0]

    desired_capacity = asg_info["DesiredCapacity"]
    num_healthy_instances = sum([instance["HealthStatus"] == "Healthy" for instance in asg_info["Instances"]])

    remaining_polls = event.get("remaining_capacity_polls", 30) - 1
    if remaining_polls <= 0:
        output_dict["polling_error"] = f"Model '{model_id}' did not start healthy instances in expected amount of time."

    should_continue_polling = desired_capacity != num_healthy_instances and remaining_polls > 0

    output_dict["should_continue_capacity_polling"] = should_continue_polling
    output_dict["remaining_capacity_polls"] = remaining_polls

    return output_dict


def handle_finish_update(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Finalize update in DDB.

    1. If the model was enabled from the Stopped state, add the model back to LiteLLM, set status to InService in DDB
    2. If the model was disabled from the InService state, set status to Stopped
    3. Commit changes to DDB
    """
    output_dict = deepcopy(event)

    model_id = event["model_id"]
    model_key = {"model_id": model_id}
    asg_name = event["asg_name"]
    ddb_item = model_table.get_item(
        Key=model_key,
        ConsistentRead=True,
    )["Item"]
    model_url = ddb_item["model_url"]

    # Parse the JSON string from environment variable
    litellm_config_str = os.environ.get("LITELLM_CONFIG_OBJ", json.dumps({}))
    try:
        litellm_params = json.loads(litellm_config_str)
        litellm_params = litellm_params.get("litellm_settings", {})
    except json.JSONDecodeError:
        # Fallback to default if JSON parsing fails
        litellm_params = {}

    litellm_params["model"] = f"openai/{ddb_item['model_config']['modelName']}"
    litellm_params["api_base"] = model_url
    litellm_params["api_key"] = "ignored"  # pragma: allowlist-secret not a real key, but needed for LiteLLM to be happy

    ddb_update_expression = "SET model_status = :ms, last_modified_date = :lm"
    ddb_update_values: Dict[str, Any] = {
        ":lm": int(datetime.utcnow().timestamp()),
    }

    if polling_error := event.get("polling_error", None):
        logger.error(f"{polling_error} Setting ASG back to 0 instances.")
        autoscaling_client.update_auto_scaling_group(
            AutoScalingGroupName=asg_name,
            MinSize=0,
            MaxSize=0,
            DesiredCapacity=0,
        )
        ddb_update_values[":ms"] = ModelStatus.STOPPED
    elif event["is_disable"]:
        ddb_update_values[":ms"] = ModelStatus.STOPPED
    elif event["has_capacity_update"]:
        ddb_update_values[":ms"] = ModelStatus.IN_SERVICE
        litellm_response = litellm_client.add_model(
            model_name=model_id,
            litellm_params=litellm_params,
        )

        litellm_id = litellm_response["model_info"]["id"]
        output_dict["litellm_id"] = litellm_id

        ddb_update_expression += ", litellm_id = :lid"
        ddb_update_values[":lid"] = litellm_id
    else:  # No polling error, not disabled, and no capacity update means this was a metadata update, keep initial state
        ddb_update_values[":ms"] = event["initial_model_status"]
    model_table.update_item(
        Key=model_key,
        UpdateExpression=ddb_update_expression,
        ExpressionAttributeValues=ddb_update_values,
    )

    output_dict["current_model_status"] = ddb_update_values[":ms"]

    return output_dict


def get_ecs_resources_from_stack(stack_name: str) -> tuple[str, str, str]:
    """Extract ECS service name, cluster name, and current task definition ARN from CloudFormation."""
    try:
        resources = cfn_client.describe_stack_resources(StackName=stack_name)["StackResources"]
        
        service_name = None
        cluster_name = None

        for resource in resources:
            if resource["ResourceType"] == "AWS::ECS::Service":
                service_name = resource["PhysicalResourceId"]
            elif resource["ResourceType"] == "AWS::ECS::Cluster":
                cluster_name = resource["PhysicalResourceId"]

        if not service_name or not cluster_name:
            raise RuntimeError(f"Could not find ECS service or cluster in stack {stack_name}")
        
        # TODO: Might be failing to get the correct information here or failing to unpack in creation of new task def
        # Get current task definition from service
        service_info = ecs_client.describe_services(
            cluster=cluster_name,
            services=[service_name]
        )["services"][0]
        
        current_task_def_arn = service_info["taskDefinition"]
        
        return service_name, cluster_name, current_task_def_arn
        
    except Exception as e:
        logger.error(f"Error getting ECS resources from stack {stack_name}: {str(e)}")
        raise RuntimeError(f"Failed to get ECS resources from CloudFormation stack: {str(e)}")


def create_updated_task_definition(task_definition_arn: str, new_env_vars: Dict[str, str]) -> str:
    """Create new task definition revision with updated environment variables."""
    try:
        # Get current task definition
        task_def_response = ecs_client.describe_task_definition(taskDefinition=task_definition_arn)
        task_def = task_def_response["taskDefinition"]
        
        # Create new task definition with updated environment variables
        new_task_def = {
            "family": task_def["family"],
            "volumes": task_def.get("volumes", []),
            "containerDefinitions": []
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
        
        # Only include cpu and memory if they have valid non-None values
        if task_def.get("cpu") is not None:
            new_task_def["cpu"] = str(task_def["cpu"])
        if task_def.get("memory") is not None:
            new_task_def["memory"] = str(task_def["memory"])
        
        # Update container definitions with new environment variables
        for container in task_def["containerDefinitions"]:
            new_container = container.copy()
            
            # Update environment variables
            existing_env = {env["name"]: env["value"] for env in container.get("environment", [])}
            existing_env.update(new_env_vars)
            
            new_container["environment"] = [
                {"name": key, "value": value} for key, value in existing_env.items()
            ]
            
            new_task_def["containerDefinitions"].append(new_container)
        
        # Register new task definition
        response = ecs_client.register_task_definition(**new_task_def)
        new_task_def_arn = response["taskDefinition"]["taskDefinitionArn"]
        
        logger.info(f"Created new task definition: {new_task_def_arn}")
        return new_task_def_arn
        
    except Exception as e:
        logger.error(f"Error creating updated task definition: {str(e)}")
        raise RuntimeError(f"Failed to create updated task definition: {str(e)}")


def update_ecs_service(cluster_name: str, service_name: str, task_definition_arn: str) -> None:
    """Update ECS service to use new task definition."""
    try:
        ecs_client.update_service(
            cluster=cluster_name,
            service=service_name,
            taskDefinition=task_definition_arn
        )
        logger.info(f"Updated ECS service {service_name} to use task definition {task_definition_arn}")
        
    except Exception as e:
        logger.error(f"Error updating ECS service: {str(e)}")
        raise RuntimeError(f"Failed to update ECS service: {str(e)}")


def handle_ecs_update(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Update ECS task definition with new environment variables and update service.
    
    This handler will:
    1. Retrieve current task definition from ECS
    2. Create new task definition revision with updated environment variables  
    3. Update ECS service to use new task definition
    4. Set up for deployment monitoring
    """
    output_dict = deepcopy(event)
    model_id = event["model_id"]
    
    logger.info(f"Starting ECS update for model '{model_id}'")
    
    try:
        # Get current model info from DDB
        ddb_item = model_table.get_item(Key={"model_id": model_id})["Item"]
        cloudformation_stack_name = ddb_item.get("cloudformation_stack_name")
        
        if not cloudformation_stack_name:
            raise RuntimeError(f"No CloudFormation stack found for model '{model_id}'")
        
        # Get ECS service and task definition from CloudFormation stack
        service_name, cluster_name, task_definition_arn = get_ecs_resources_from_stack(cloudformation_stack_name)
        
        # Get updated environment variables from model config
        updated_env_vars = ddb_item["model_config"]["containerConfig"]["environment"]
        
        # Create new task definition with updated environment variables
        new_task_def_arn = create_updated_task_definition(task_definition_arn, updated_env_vars)
        
        # Update ECS service to use new task definition
        update_ecs_service(cluster_name, service_name, new_task_def_arn)
        
        # Set up tracking for deployment monitoring
        output_dict["new_task_definition_arn"] = new_task_def_arn
        output_dict["ecs_service_name"] = service_name
        output_dict["ecs_cluster_name"] = cluster_name
        output_dict["remaining_ecs_polls"] = 30  # Set initial polling limit
        
        logger.info(f"Successfully initiated ECS update for model '{model_id}'")
        
    except Exception as e:
        logger.error(f"ECS update failed for model '{model_id}': {str(e)}")
        # Set error for state machine handling
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
    model_id = event["model_id"]
    
    # Check if there was an error in the ECS update step
    if event.get("ecs_update_error"):
        logger.error(f"ECS update error for model '{model_id}': {event['ecs_update_error']}")
        output_dict["should_continue_ecs_polling"] = False
        return output_dict
    
    cluster_name = event["ecs_cluster_name"]
    service_name = event["ecs_service_name"]
    new_task_def_arn = event["new_task_definition_arn"]
    
    try:
        # Get service deployment status
        services = ecs_client.describe_services(
            cluster=cluster_name,
            services=[service_name]
        )["services"]
        
        if not services:
            raise RuntimeError(f"ECS service {service_name} not found")
        
        service = services[0]
        deployments = service["deployments"]
        
        # Check if deployment is stable
        is_deployment_stable = True
        primary_deployment = None
        
        for deployment in deployments:
            if deployment["taskDefinition"] == new_task_def_arn:
                primary_deployment = deployment
                if deployment["status"] != "PRIMARY" or deployment["rolloutState"] != "COMPLETED":
                    is_deployment_stable = False
                break
        
        if not primary_deployment:
            logger.warning(f"Could not find deployment for task definition {new_task_def_arn}")
            is_deployment_stable = False
        
        # Check polling limits
        remaining_polls = event.get("remaining_ecs_polls", 30) - 1
        if remaining_polls <= 0 and not is_deployment_stable:
            logger.error(f"ECS deployment polling timeout for model '{model_id}'")
            output_dict["ecs_polling_error"] = f"ECS deployment did not complete within expected time for model '{model_id}'"
            output_dict["should_continue_ecs_polling"] = False
            return output_dict
        
        should_continue_polling = not is_deployment_stable and remaining_polls > 0
        
        output_dict["should_continue_ecs_polling"] = should_continue_polling
        output_dict["remaining_ecs_polls"] = remaining_polls
        
        if is_deployment_stable:
            logger.info(f"ECS deployment completed successfully for model '{model_id}'")
        else:
            logger.info(f"ECS deployment still in progress for model '{model_id}', remaining polls: {remaining_polls}")
            
    except Exception as e:
        logger.error(f"Error polling ECS deployment for model '{model_id}': {str(e)}")
        output_dict["ecs_polling_error"] = f"Error polling ECS deployment: {str(e)}"
        output_dict["should_continue_ecs_polling"] = False
    
    return output_dict
