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
from typing import Any, Dict

import boto3
from models.clients.litellm_client import LiteLLMClient
from models.domain_objects import ModelStatus
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config

ddbResource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
model_table = ddbResource.Table(os.environ["MODEL_TABLE_NAME"])
autoscaling_client = boto3.client("autoscaling", region_name=os.environ["AWS_REGION"], config=retry_config)
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

    # metadata updates
    payload_model_type = event["update_payload"].get("modelType", None)
    is_payload_streaming_update = (payload_streaming := event["update_payload"].get("streaming", None)) is not None
    if payload_model_type or is_payload_streaming_update or is_autoscaling_update:
        if payload_model_type:
            logger.info(f"Setting type '{payload_model_type}' for model '{model_id}'")
            model_config["modelType"] = payload_model_type
        if is_payload_streaming_update:
            logger.info(f"Setting streaming to '{payload_streaming}' for model '{model_id}'")
            model_config["streaming"] = payload_streaming

        ddb_update_expression += ", model_config = :mc"
        ddb_update_values[":mc"] = model_config

    logger.info(f"Model '{model_id}' update expression: {ddb_update_expression}")
    logger.info(f"Model '{model_id}' update values: {ddb_update_values}")

    model_table.update_item(
        Key=model_key,
        UpdateExpression=ddb_update_expression,
        ExpressionAttributeValues=ddb_update_values,
    )

    # We only need to poll for activation so that we know when to add the model back to LiteLLM
    output_dict["has_capacity_update"] = is_enable
    output_dict["is_disable"] = is_disable
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
    litellm_params["api_key"] = "ignored"  # pragma: allowlist-secret not a real key, but needed for LiteLLM to be happy

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
