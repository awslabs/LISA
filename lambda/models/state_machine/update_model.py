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
from datetime import datetime, UTC
from typing import Any, Callable, Dict, List, Optional

import boto3
from models.clients.litellm_client import LiteLLMClient
from models.domain_objects import GuardrailsTableEntry, ModelStatus
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config

ddbResource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
model_table = ddbResource.Table(os.environ["MODEL_TABLE_NAME"])
guardrails_table = ddbResource.Table(os.environ["GUARDRAILS_TABLE_NAME"])
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


def _update_simple_field(model_config: Dict[str, Any], field_name: str, value: Any, model_id: str) -> None:
    """Update a simple field in model_config."""
    logger.info(f"Setting {field_name} to '{value}' for model '{model_id}'")
    model_config[field_name] = value


def _update_container_config(
    model_config: Dict[str, Any], container_config: Dict[str, Any], model_id: str
) -> Dict[str, Any]:
    """Handle container config update.

    Returns:
        Dict containing any container config metadata needed for ECS updates
    """
    logger.info(f"Updating container configuration for model '{model_id}'")

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

        model_config["containerConfig"]["environment"] = env_vars

        # Store deletion info for ECS update
        if env_vars_to_delete:
            container_metadata["env_vars_to_delete"] = env_vars_to_delete
            logger.info(f"Deleted environment variables for model '{model_id}': {env_vars_to_delete}")
        logger.info(f"Updated environment variables for model '{model_id}': {env_vars}")

    # Update sharedMemorySize
    if container_config.get("sharedMemorySize") is not None:
        model_config["containerConfig"]["sharedMemorySize"] = container_config["sharedMemorySize"]
        logger.info(f"Updated shared memory size for model '{model_id}': {container_config['sharedMemorySize']}")

    # Update health check configuration
    health_check_updates = {}
    if container_config.get("healthCheckCommand") is not None:
        health_check_updates["command"] = container_config["healthCheckCommand"]
    if container_config.get("healthCheckInterval") is not None:
        health_check_updates["interval"] = container_config["healthCheckInterval"]
    if container_config.get("healthCheckTimeout") is not None:
        health_check_updates["timeout"] = container_config["healthCheckTimeout"]
    if container_config.get("healthCheckStartPeriod") is not None:
        health_check_updates["startPeriod"] = container_config["healthCheckStartPeriod"]
    if container_config.get("healthCheckRetries") is not None:
        health_check_updates["retries"] = container_config["healthCheckRetries"]

    if health_check_updates:
        # Update the health check config in model_config
        if "healthCheckConfig" not in model_config["containerConfig"]:
            model_config["containerConfig"]["healthCheckConfig"] = {}

        for field, value in health_check_updates.items():
            model_config["containerConfig"]["healthCheckConfig"][field] = value

        logger.info(f"Updated health check configuration for model '{model_id}': {health_check_updates}")

    return container_metadata


def _get_metadata_update_handlers(model_config: Dict[str, Any], model_id: str) -> Dict[str, Callable[..., Any]]:
    """Return a dictionary mapping field names to their update handlers."""
    return {
        "modelType": lambda value: _update_simple_field(model_config, "modelType", value, model_id),
        "streaming": lambda value: _update_simple_field(model_config, "streaming", value, model_id),
        "modelDescription": lambda value: _update_simple_field(model_config, "modelDescription", value, model_id),
        "allowedGroups": lambda value: _update_simple_field(model_config, "allowedGroups", value, model_id),
        "features": lambda value: _update_simple_field(model_config, "features", value, model_id),
        "containerConfig": lambda value: _update_container_config(model_config, value, model_id),
    }


def _process_metadata_updates(
    model_config: Dict[str, Any], update_payload: Dict[str, Any], model_id: str
) -> tuple[bool, Dict[str, Any]]:
    """
    Process metadata updates.

    Args:
        model_config: The model configuration dictionary to update
        update_payload: The payload containing updates
        model_id: The model ID for logging purposes

    Returns:
        tuple: (has_updates: bool, metadata: Dict containing update metadata)
    """
    update_handlers = _get_metadata_update_handlers(model_config, model_id)
    has_updates = False
    update_metadata = {}

    for field_name, handler in update_handlers.items():
        if field_name in update_payload and update_payload[field_name] is not None:
            # Handle containerConfig specially since it returns metadata
            if field_name == "containerConfig":
                container_metadata = handler(update_payload[field_name])
                if container_metadata:
                    update_metadata["container"] = container_metadata
            else:
                handler(update_payload[field_name])
            has_updates = True

    return has_updates, update_metadata


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
        ":lm": int(datetime.now(UTC).timestamp()),
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
        if cooldown := asg_config.get("cooldown", False):
            model_config["autoScalingConfig"]["cooldown"] = int(cooldown)
        if defaultInstanceWarmup := asg_config.get("defaultInstanceWarmup", False):
            model_config["autoScalingConfig"]["defaultInstanceWarmup"] = int(defaultInstanceWarmup)

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
            if cooldown:
                asg_update_payload["DefaultCooldown"] = int(cooldown)
            if defaultInstanceWarmup:
                asg_update_payload["DefaultInstanceWarmup"] = int(defaultInstanceWarmup)

            # Start ASG update with known parameters. Because of model validations, at least one arg is guaranteed.
            autoscaling_client.update_auto_scaling_group(**asg_update_payload)

    # Process metadata updates
    has_metadata_update, update_metadata = _process_metadata_updates(model_config, event["update_payload"], model_id)
    has_metadata_update = has_metadata_update or is_autoscaling_update

    if has_metadata_update:
        ddb_update_expression += ", model_config = :mc"
        ddb_update_values[":mc"] = model_config

    # Pass through container metadata for ECS updates
    if update_metadata.get("container"):
        output_dict["container_metadata"] = update_metadata["container"]

    logger.info(f"Model '{model_id}' update expression: {ddb_update_expression}")
    logger.info(f"Model '{model_id}' update values: {ddb_update_values}")

    model_table.update_item(
        Key=model_key,
        UpdateExpression=ddb_update_expression,
        ExpressionAttributeValues=ddb_update_values,
    )

    # Determine if ECS update is needed (container config changes for LISA-hosted models)
    needs_ecs_update = (
        event["update_payload"].get("containerConfig") is not None
        and model_asg is not None
        and model_status == ModelStatus.IN_SERVICE
    )

    # Determine if guardrails update is needed
    needs_guardrails_update = event["update_payload"].get("guardrailsConfig") is not None

    # We only need to poll for activation so that we know when to add the model back to LiteLLM
    output_dict["has_capacity_update"] = is_enable
    output_dict["is_disable"] = is_disable
    output_dict["needs_ecs_update"] = needs_ecs_update
    output_dict["needs_guardrails_update"] = needs_guardrails_update
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
    logger.info(f"Polling capacity for model {model_id}, ASG: {asg_name}")
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

    ddb_update_expression = "SET model_status = :ms, last_modified_date = :lm"
    ddb_update_values: Dict[str, Any] = {
        ":lm": int(datetime.now(UTC).timestamp()),
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


def handle_update_guardrails(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Update guardrails for a model in LiteLLM and DynamoDB.

    This handler will:
    1. Process guardrails configuration updates from the event
    2. Update existing guardrails in LiteLLM
    3. Update guardrail entries in DynamoDB
    4. Handle creation of new guardrails and deletion of removed ones
    """
    logger.info(f"Updating guardrails for model: {event.get('model_id')}")
    output_dict = deepcopy(event)

    model_id = event["model_id"]
    guardrails_config = event["update_payload"].get("guardrailsConfig")

    # Check if guardrails config exists
    if not guardrails_config or not guardrails_config.get("guardrails"):
        logger.info("No guardrails configuration found, skipping guardrail updates")
        output_dict["guardrail_update_ids"] = []
        return output_dict

    updated_guardrails = created_guardrails = deleted_guardrails = []

    try:
        # Get existing guardrails for this model from DynamoDB
        existing_guardrails = {}
        response = guardrails_table.query(
            IndexName="ModelIdIndex",
            KeyConditionExpression="model_id = :model_id",
            ExpressionAttributeValues={":model_id": model_id},
        )

        for item in response.get("Items", []):
            existing_guardrails[item["guardrail_name"]] = item

        # Process each guardrail in the new configuration
        processed_guardrail_names = set()

        for guardrail_key, guardrail_config in guardrails_config["guardrails"].items():
            guardrail_name = guardrail_config["guardrail_name"]

            logger.info(f"Processing guardrail update: {guardrail_name}")

            # Check if this guardrail is marked for deletion using deletion flag
            if guardrail_config.get("marked_for_deletion", False):
                logger.info(f"Found guardrail marked for deletion: {guardrail_key} (name: {guardrail_name})")

                # Find the existing guardrail to delete by name
                guardrail_to_delete = existing_guardrails.get(guardrail_name)

                if guardrail_to_delete:
                    try:
                        logger.info(
                            f"Deleting guardrail: {guardrail_to_delete['guardrail_name']} "
                            f"(ID: {guardrail_to_delete['guardrail_id']})"
                        )

                        # Delete from LiteLLM
                        litellm_client.delete_guardrail(guardrail_to_delete["guardrail_id"])

                        # Delete from DynamoDB
                        guardrails_table.delete_item(
                            Key={"guardrail_id": guardrail_to_delete["guardrail_id"], "model_id": model_id}
                        )

                        deleted_guardrails.append(
                            {
                                "guardrail_id": guardrail_to_delete["guardrail_id"],
                                "guardrail_name": guardrail_to_delete["guardrail_name"],
                                "action": "deleted",
                            }
                        )

                        logger.info(f"Successfully deleted guardrail: {guardrail_to_delete['guardrail_name']}")

                    except Exception as delete_error:
                        logger.error(f"Error deleting guardrail marked for deletion: {str(delete_error)}")
                        # Continue with other operations even if one deletion fails
                else:
                    logger.warning(f"No matching guardrail found for deletion: {guardrail_name}")

                # Skip normal processing for deletion markers
                continue

            processed_guardrail_names.add(guardrail_name)

            # Check if this is an existing guardrail or a new one
            if guardrail_name in existing_guardrails:
                # Update existing guardrail
                existing_guardrail = existing_guardrails[guardrail_name]
                litellm_guardrail_id = existing_guardrail["guardrail_id"]

                # Transform guardrail config to LiteLLM format for update
                litellm_guardrail_config = {
                    "guardrail": {
                        "guardrail_name": f'{guardrail_config["guardrail_name"]}-{model_id}',
                        "litellm_params": {
                            "guardrail": "bedrock",
                            "mode": str(guardrail_config.get("mode", "pre_call")),
                            "guardrailIdentifier": guardrail_config["guardrail_identifier"],
                            "guardrailVersion": guardrail_config.get("guardrail_version", "DRAFT"),
                            "default_on": False,
                        },
                        "guardrail_info": {"description": guardrail_config.get("description", "")},
                    }
                }

                # Update guardrail in LiteLLM
                logger.info(f"Updating guardrail in LiteLLM: {guardrail_name}")
                litellm_client.update_guardrail(litellm_guardrail_id, litellm_guardrail_config)

                # Update guardrail entry in DynamoDB
                update_expression = (
                    "SET guardrail_identifier = :gi, guardrail_version = :gv, #mode = :m, "
                    "description = :d, allowed_groups = :ag, last_modified_date = :lm"
                )
                guardrails_table.update_item(
                    Key={"guardrail_id": existing_guardrail["guardrail_id"], "model_id": model_id},
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames={"#mode": "mode"},  # mode is a reserved keyword in DynamoDB
                    ExpressionAttributeValues={
                        ":gi": guardrail_config["guardrail_identifier"],
                        ":gv": guardrail_config.get("guardrail_version", "DRAFT"),
                        ":m": str(guardrail_config.get("mode", "pre_call")),
                        ":d": guardrail_config.get("description"),
                        ":ag": guardrail_config.get("allowed_groups", []),
                        ":lm": int(datetime.now(UTC).timestamp() * 1000),
                    },
                )

                updated_guardrails.append(
                    {
                        "guardrail_id": existing_guardrail["guardrail_id"],
                        "guardrail_name": guardrail_name,
                        "action": "updated",
                    }
                )

                logger.info(f"Successfully updated guardrail: {guardrail_name}")

            else:

                # Transform guardrail config to LiteLLM format
                litellm_guardrail_config = {
                    "guardrail": {
                        "guardrail_name": f'{guardrail_config["guardrail_name"]}-{model_id}',
                        "litellm_params": {
                            "guardrail": "bedrock",
                            "mode": str(guardrail_config.get("mode", "pre_call")),
                            "guardrailIdentifier": guardrail_config["guardrail_identifier"],
                            "guardrailVersion": guardrail_config.get("guardrail_version", "DRAFT"),
                            "default_on": False,
                        },
                        "guardrail_info": {"description": guardrail_config.get("description", "")},
                    }
                }

                # Create guardrail in LiteLLM
                logger.info(f"Creating new guardrail in LiteLLM: {guardrail_name}")
                litellm_response = litellm_client.create_guardrail(litellm_guardrail_config)

                # Extract LiteLLM guardrail ID from response
                litellm_guardrail_id = None
                if "guardrail_id" in litellm_response:
                    litellm_guardrail_id = litellm_response["guardrail_id"]
                else:
                    logger.error(f"Unexpected LiteLLM guardrail response structure: {litellm_response}")
                    raise KeyError(f"Could not find guardrail ID in LiteLLM response: {litellm_response}")

                # Create guardrail entry for DynamoDB
                guardrail_entry = GuardrailsTableEntry(
                    guardrail_id=litellm_guardrail_id,
                    model_id=model_id,
                    guardrail_name=guardrail_config["guardrail_name"],
                    guardrail_identifier=guardrail_config["guardrail_identifier"],
                    guardrail_version=guardrail_config.get("guardrail_version", "DRAFT"),
                    mode=str(guardrail_config.get("mode", "pre_call")),
                    description=guardrail_config.get("description"),
                    allowed_groups=guardrail_config.get("allowed_groups", []),
                )

                # Store in DynamoDB
                logger.info(f"Storing new guardrail in DynamoDB: {litellm_guardrail_id}")
                guardrails_table.put_item(Item=guardrail_entry.model_dump())

                created_guardrails.append(
                    {"guardrail_id": litellm_guardrail_id, "guardrail_name": guardrail_name, "action": "created"}
                )

                logger.info(f"Successfully created new guardrail: {guardrail_name}")

        # Delete guardrails that are no longer in the configuration
        for guardrail_name, existing_guardrail in existing_guardrails.items():
            if guardrail_name not in processed_guardrail_names:
                logger.info(f"Deleting removed guardrail: {guardrail_name}")

                try:
                    # Delete from LiteLLM
                    litellm_client.delete_guardrail(existing_guardrail["guardrail_id"])

                    # Delete from DynamoDB
                    guardrails_table.delete_item(
                        Key={"guardrail_id": existing_guardrail["guardrail_id"], "model_id": model_id}
                    )

                    deleted_guardrails.append(
                        {
                            "guardrail_id": existing_guardrail["guardrail_id"],
                            "guardrail_name": guardrail_name,
                            "action": "deleted",
                        }
                    )

                    logger.info(f"Successfully deleted guardrail: {guardrail_name}")

                except Exception as delete_error:
                    logger.error(f"Error deleting guardrail {guardrail_name}: {str(delete_error)}")
                    # Continue with other operations even if one deletion fails

        # Combine all operations for output
        all_guardrail_operations = updated_guardrails + created_guardrails + deleted_guardrails

    except Exception as e:
        logger.error(f"Error updating guardrails: {str(e)}")

        # Clean up any newly created guardrails on failure
        for created_guardrail in created_guardrails:
            try:
                logger.info(f"Cleaning up created guardrail: {created_guardrail['guardrail_id']}")
                # Delete from DynamoDB
                guardrails_table.delete_item(
                    Key={"guardrail_id": created_guardrail["guardrail_id"], "model_id": model_id}
                )
                # Delete from LiteLLM
                litellm_client.delete_guardrail(created_guardrail["guardrail_id"])
            except Exception as cleanup_error:
                logger.error(f"Error during guardrail cleanup: {str(cleanup_error)}")

        # Re-raise the original exception
        raise e

    output_dict["guardrail_updates"] = all_guardrail_operations
    output_dict["guardrail_update_summary"] = {
        "updated": len(updated_guardrails),
        "created": len(created_guardrails),
        "deleted": len(deleted_guardrails),
    }

    logger.info(
        f"Successfully processed guardrail updates for model: {model_id}. "
        f"Updated: {len(updated_guardrails)}, Created: {len(created_guardrails)}, "
        f"Deleted: {len(deleted_guardrails)}"
    )
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
    updated_env_vars: Dict[str, str],
    env_vars_to_delete: Optional[List[str]] = None,
    updated_container_config: Optional[Dict[str, Any]] = None,
) -> str:
    """Create new task definition revision with updated environment variables and container config.

    Args:
        task_definition_arn: ARN of the current task definition
        updated_env_vars: Environment variables to add/update from DynamoDB config
        env_vars_to_delete: List of environment variable names to delete
        updated_container_config: Updated container configuration from DynamoDB
    """
    try:
        if env_vars_to_delete is None:
            env_vars_to_delete = []

        # Get current task definition
        task_def_response = ecs_client.describe_task_definition(taskDefinition=task_definition_arn)
        task_def = task_def_response["taskDefinition"]

        # Create new task definition with updated environment variables
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

        # Only include cpu and memory if they have valid non-None values
        if task_def.get("cpu") is not None:
            new_task_def["cpu"] = str(task_def["cpu"])
        if task_def.get("memory") is not None:
            new_task_def["memory"] = str(task_def["memory"])

        # Update container definitions with new environment variables
        for container in task_def["containerDefinitions"]:
            new_container = container.copy()

            # Start with existing environment variables from the task definition
            existing_env = {env["name"]: env["value"] for env in container.get("environment", [])}
            logger.info(f"Existing environment variables: {list(existing_env.keys())}")

            # Apply updates/additions from DynamoDB config
            existing_env.update(updated_env_vars)
            logger.info(f"Environment variables after model_config merge: {list(existing_env.keys())}")

            # Remove deleted variables
            for var_name in env_vars_to_delete:
                if var_name in existing_env:
                    del existing_env[var_name]
                    logger.info(f"Deleted environment variable: {var_name}")

            logger.info(f"Final environment variables: {list(existing_env.keys())}")

            # Set the new environment variables
            new_container["environment"] = [{"name": key, "value": value} for key, value in existing_env.items()]

            # Update container configuration if provided
            if updated_container_config:
                # Update shared memory size
                if updated_container_config.get("sharedMemorySize") is not None:
                    # Ensure linuxParameters exists
                    if "linuxParameters" not in new_container:
                        new_container["linuxParameters"] = {}

                    new_container["linuxParameters"]["sharedMemorySize"] = int(
                        updated_container_config["sharedMemorySize"]
                    )
                    logger.info(
                        f"Updated container shared memory size: {updated_container_config['sharedMemorySize']} MiB"
                    )

                # Update health check configuration
                health_check_config = updated_container_config.get("healthCheckConfig")
                if health_check_config:
                    # Start with existing health check if it exists
                    current_health_check = new_container.get("healthCheck", {})

                    # Update individual health check fields, converting Decimal to int
                    if health_check_config.get("command") is not None:
                        current_health_check["command"] = health_check_config["command"]
                    if health_check_config.get("interval") is not None:
                        current_health_check["interval"] = int(health_check_config["interval"])
                    if health_check_config.get("timeout") is not None:
                        current_health_check["timeout"] = int(health_check_config["timeout"])
                    if health_check_config.get("startPeriod") is not None:
                        current_health_check["startPeriod"] = int(health_check_config["startPeriod"])
                    if health_check_config.get("retries") is not None:
                        current_health_check["retries"] = int(health_check_config["retries"])

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
        ecs_client.update_service(cluster=cluster_arn, service=service_arn, taskDefinition=task_definition_arn)
        logger.info(f"Updated ECS service {service_arn} to use task definition {task_definition_arn}")

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
        service_arn, cluster_arn, task_definition_arn = get_ecs_resources_from_stack(cloudformation_stack_name)

        # Get updated environment variables from model config
        updated_env_vars = ddb_item["model_config"]["containerConfig"]["environment"]

        # Get environment variables to delete from container metadata (if available)
        env_vars_to_delete = []
        if container_metadata := event.get("container_metadata"):
            env_vars_to_delete = container_metadata.get("env_vars_to_delete", [])

        logger.info(f"Environment variables to delete: {env_vars_to_delete}")

        # Get updated container config from model config
        updated_container_config = ddb_item["model_config"]["containerConfig"]

        # Create new task definition with updated environment variables and container config
        new_task_def_arn = create_updated_task_definition(
            task_definition_arn, updated_env_vars, env_vars_to_delete, updated_container_config
        )

        # Update ECS service to use new task definition
        update_ecs_service(cluster_arn, service_arn, new_task_def_arn)

        # Set up tracking for deployment monitoring
        output_dict["new_task_definition_arn"] = new_task_def_arn
        output_dict["ecs_service_arn"] = service_arn
        output_dict["ecs_cluster_arn"] = cluster_arn
        output_dict["remaining_ecs_polls"] = 30

        logger.info(f"Successfully initiated ECS update for model '{model_id}'")

    except Exception as e:
        logger.error(f"ECS update failed for model '{model_id}': {str(e)}")
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

        # Look for our deployment - check both exact match and just the revision number
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
        remaining_polls = event.get("remaining_ecs_polls", 30) - 1
        if remaining_polls <= 0 and not is_deployment_stable:
            logger.error(f"ECS deployment polling timeout for model '{model_id}'")
            output_dict["ecs_polling_error"] = (
                f"ECS deployment did not complete within expected time for model '{model_id}'"
            )
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
