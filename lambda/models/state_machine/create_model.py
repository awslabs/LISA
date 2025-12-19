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

"""Lambda handlers for CreateModel state machine."""

import json
import logging
import os
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

import boto3
from botocore.config import Config
from models.clients.litellm_client import LiteLLMClient
from models.domain_objects import CreateModelRequest, GuardrailsTableEntry, InferenceContainer, ModelStatus
from models.exception import (
    MaxPollsExceededException,
    StackFailedToCreateException,
    UnexpectedCloudFormationStateException,
)
from models.scheduling import schedule_monitoring
from utilities.common_functions import (
    get_account_and_partition,
    get_cert_path,
    get_rest_api_container_endpoint,
    retry_config,
)
from utilities.time import now

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambdaConfig = Config(connect_timeout=60, read_timeout=600, retries={"max_attempts": 1})
lambdaClient = boto3.client("lambda", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
ecrClient = boto3.client("ecr", region_name=os.environ["AWS_REGION"], config=retry_config)
ec2Client = boto3.client("ec2", region_name=os.environ["AWS_REGION"], config=retry_config)
ddbResource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
model_table = ddbResource.Table(os.environ["MODEL_TABLE_NAME"])
guardrails_table = ddbResource.Table(os.environ["GUARDRAILS_TABLE_NAME"])
cfnClient = boto3.client("cloudformation", region_name=os.environ["AWS_REGION"], config=retry_config)
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


def get_container_path(inference_container_type: InferenceContainer) -> str:
    """
    Get the LISA repository path for referencing container build scripts.

    Paths are relative to <LISA Repository root>/lib/serve/ecs-model/
    """
    path_mapping = {
        InferenceContainer.TEI: "embedding/tei",
        InferenceContainer.TGI: "textgen/tgi",
        InferenceContainer.VLLM: "vllm",
    }
    # API validation before state machine guarantees the value exists.
    return path_mapping[inference_container_type]


def adjust_initial_capacity_for_schedule(prepared_event: Dict[str, Any]) -> None:
    """Adjust Auto Scaling Group initial capacity based on schedule configuration"""
    try:
        # Check if scheduling is configured
        auto_scaling_config = prepared_event.get("autoScalingConfig", {})
        scheduling_config = auto_scaling_config.get("scheduling")

        if (
            not scheduling_config
            or not isinstance(scheduling_config, dict)
            or not scheduling_config.get("scheduleEnabled")
        ):
            logger.info("No scheduling configured - using original capacity settings")
            return

        schedule_type = scheduling_config.get("scheduleType")
        timezone_name = scheduling_config.get("timezone")

        try:
            now = datetime.now(ZoneInfo(timezone_name))
            current_time = now.time()
            current_day = now.strftime("%A").lower()
            is_within_schedule = False

            if schedule_type == "RECURRING" and scheduling_config.get("recurringSchedule"):
                # Daily recurring schedule
                recurring_schedule = scheduling_config["recurringSchedule"]
                start_time_str = recurring_schedule.get("startTime")
                stop_time_str = recurring_schedule.get("stopTime")

                if start_time_str and stop_time_str:
                    # Parse times
                    start_hour, start_minute = map(int, start_time_str.split(":"))
                    stop_hour, stop_minute = map(int, stop_time_str.split(":"))

                    start_time_obj = datetime.min.time().replace(hour=start_hour, minute=start_minute)
                    stop_time_obj = datetime.min.time().replace(hour=stop_hour, minute=stop_minute)

                    # Check if current time is within the schedule
                    if start_time_obj <= stop_time_obj:
                        # Normal schedule within same day
                        is_within_schedule = start_time_obj <= current_time <= stop_time_obj
                    else:
                        # Schedule crosses midnight
                        is_within_schedule = current_time >= start_time_obj or current_time <= stop_time_obj

            elif schedule_type == "DAILY" and scheduling_config.get("dailySchedule"):
                # Daily schedule
                daily_schedule = scheduling_config["dailySchedule"]
                today_schedule = daily_schedule.get(current_day)

                if today_schedule and today_schedule.get("startTime") and today_schedule.get("stopTime"):
                    start_time_str = today_schedule["startTime"]
                    stop_time_str = today_schedule["stopTime"]

                    # Parse times
                    start_hour, start_minute = map(int, start_time_str.split(":"))
                    stop_hour, stop_minute = map(int, stop_time_str.split(":"))

                    start_time_obj = datetime.min.time().replace(hour=start_hour, minute=start_minute)
                    stop_time_obj = datetime.min.time().replace(hour=stop_hour, minute=stop_minute)

                    # Check if current time is within the schedule
                    if start_time_obj <= stop_time_obj:
                        # Normal schedule within same day
                        is_within_schedule = start_time_obj <= current_time <= stop_time_obj
                    else:
                        # Schedule crosses midnight
                        is_within_schedule = current_time >= start_time_obj or current_time <= stop_time_obj

            # Adjust capacity based on schedule
            if is_within_schedule:
                logger.info(f"Current time {current_time} ({timezone_name}) is within scheduled hours")
                # Keep original capacity settings
            else:
                logger.info(f"Current time {current_time} ({timezone_name}) is outside scheduled hours")
                # Set desired capacity to 0 for deployment outside scheduled hours
                auto_scaling_config["minCapacity"] = 0
                auto_scaling_config["desiredCapacity"] = 0

        except Exception as time_error:
            logger.error(f"Error processing schedule time logic: {time_error}", exc_info=True)
            # If we can't determine the schedule, use default capacity to be safe
            logger.info("Using original capacity settings due to schedule processing error")

    except Exception as e:
        logger.error(f"Error adjusting initial capacity for schedule: {e}", exc_info=True)
        # If scheduling logic fails, proceed with original capacity settings
        logger.info("Using original capacity settings due to scheduling error")


def handle_set_model_to_creating(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set DDB entry to CREATING status."""
    logger.info(f"Setting model to CREATING status: {event.get('modelId')}")
    output_dict = deepcopy(event)
    request = CreateModelRequest.model_validate(event)

    is_lisa_managed = all(
        (
            bool(request_param)
            for request_param in (
                request.autoScalingConfig,
                request.containerConfig,
                request.inferenceContainer,
                request.instanceType,
                request.loadBalancerConfig,
            )
        )
    )

    # Create a copy of event without guardrailsConfig
    # Guardrails are stored separately in the guardrails table
    model_config_data = deepcopy(event)
    model_config_data.pop("guardrailsConfig", None)

    model_table.update_item(
        Key={"model_id": request.modelId},
        UpdateExpression=(
            "SET model_status = :model_status, model_config = :model_config, "
            "model_description = :model_description, last_modified_date = :lm"
        ),
        ExpressionAttributeValues={
            ":model_status": ModelStatus.CREATING,
            ":model_config": model_config_data,
            ":model_description": request.modelDescription,
            ":lm": now(),
        },
    )
    output_dict["create_infra"] = is_lisa_managed
    return output_dict


def handle_start_copy_docker_image(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Start process for copying Docker image into local AWS account."""
    logger.info(f"Starting Docker image copy for model: {event.get('modelId')}")
    output_dict = deepcopy(event)
    request = CreateModelRequest.model_validate(event)

    image_path = get_container_path(request.inferenceContainer)
    output_dict["containerConfig"]["image"]["path"] = image_path

    # Check if image type is ECR - skip building docker image if it already exists
    if request.containerConfig and request.containerConfig.image.type == "ecr":
        logger.info(f"ECR image detected for model {event.get('modelId')}, verifying image accessibility")
        # Verify the ECR image is accessible
        try:
            # Extract repository name and tag from the base image
            base_image = request.containerConfig.image.baseImage
            if ":" in base_image:
                repository_name, image_tag = base_image.rsplit(":", 1)
            else:
                repository_name = base_image
                image_tag = "latest"

            # Remove registry URL if present to get just the repository name
            if "/" in repository_name:
                repository_name = repository_name.split("/", 1)[1]

            # Verify image exists in ECR
            ecrClient.describe_images(repositoryName=repository_name, imageIds=[{"imageTag": image_tag}])

            logger.info(f"ECR image {base_image} verified successfully")
            output_dict["image_info"] = {
                "image_tag": image_tag,
                "image_uri": repository_name,
                "image_type": "ecr",
                "remaining_polls": 0,
                "image_status": "prebuilt",
            }
            return output_dict

        except ecrClient.exceptions.ImageNotFoundException:
            error_msg = f"ECR image {base_image} not found. Please ensure the image exists and is accessible."
            logger.error(error_msg)
            raise Exception(error_msg)
        except ecrClient.exceptions.RepositoryNotFoundException:
            error_msg = (
                f"ECR repository {repository_name} not found. Please ensure the repository exists and is accessible."
            )
            logger.error(error_msg)
            raise Exception(error_msg)

    # For non-ECR images, proceed with the normal docker image building process
    logger.info(f"Invoking image build for model {event.get('modelId')}")
    response = lambdaClient.invoke(
        FunctionName=os.environ["DOCKER_IMAGE_BUILDER_FN_ARN"],
        Payload=json.dumps(
            {
                "base_image": request.containerConfig.image.baseImage,
                "layer_to_add": image_path,
            }
        ),
    )

    payload = response["Payload"].read()
    output_dict["image_info"] = json.loads(payload)
    output_dict["image_info"]["remaining_polls"] = 30
    output_dict["image_info"]["image_status"] = "building"
    return output_dict


def handle_poll_docker_image_available(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check that Docker image is available in account or not."""
    output_dict = deepcopy(event)

    try:
        # Use the appropriate repository name based on image type
        repository_name = (
            event["image_info"]["image_uri"]
            if event["image_info"].get("image_type") == "ecr"
            else os.environ["ECR_REPOSITORY_NAME"]
        )
        ecrClient.describe_images(
            repositoryName=repository_name, imageIds=[{"imageTag": event["image_info"]["image_tag"]}]
        )
    except ecrClient.exceptions.ImageNotFoundException:
        output_dict["continue_polling_docker"] = True
        output_dict["image_info"]["remaining_polls"] -= 1
        if output_dict["image_info"]["remaining_polls"] <= 0:
            # Only terminate EC2 instance if one exists (not for pre-existing ECR images)
            if "instance_id" in event["image_info"]:
                ec2Client.terminate_instances(InstanceIds=[event["image_info"]["instance_id"]])
            raise MaxPollsExceededException(
                json.dumps(
                    {
                        "error": "Max number of ECR polls reached. Docker Image was not replicated successfully.",
                        "event": event,
                    }
                )
            )
        return output_dict

    output_dict["continue_polling_docker"] = False
    # Only terminate EC2 instance if one exists (not for pre-existing ECR images)
    if "instance_id" in event["image_info"]:
        ec2Client.terminate_instances(InstanceIds=[event["image_info"]["instance_id"]])
    return output_dict


def handle_start_create_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Start model infrastructure creation."""
    output_dict = deepcopy(event)
    request = CreateModelRequest.model_validate(event)

    def camelize_object(o):  # type: ignore[no-untyped-def]
        o2 = {}
        for k in o:
            fixed_k = k[:1].lower() + k[1:]
            if isinstance(o[k], dict):
                o2[fixed_k] = camelize_object(o[k])
            else:
                o2[fixed_k] = o[k]
        return o2

    prepared_event = camelize_object(event)
    prepared_event["containerConfig"]["environment"] = event["containerConfig"]["environment"]

    # Adjust initial capacity based on schedule if scheduling is configured
    adjust_initial_capacity_for_schedule(prepared_event)

    # Handle ECR images differently - use the existing ECR image instead of the built one
    if event["image_info"].get("image_type") == "ecr":
        # For pre-existing ECR images, construct the ARN using the image repository
        account_id, partition = get_account_and_partition()

        repository_arn = (
            f"arn:{partition}:ecr:{os.environ['AWS_REGION']}:{account_id}:repository/{event['image_info']['image_uri']}"
        )
        prepared_event["containerConfig"]["image"] = {
            "repositoryArn": repository_arn,
            "tag": event["image_info"]["image_tag"],
            "type": "ecr",
        }
    else:
        # For built images, use the default ECR repository
        prepared_event["containerConfig"]["image"] = {
            "repositoryArn": os.environ["ECR_REPOSITORY_ARN"],
            "tag": event["image_info"]["image_tag"],
            "type": "ecr",
        }

    # Remove scheduling configuration from autoScalingConfig before sending to ECS deployer
    if "autoScalingConfig" in prepared_event and "scheduling" in prepared_event["autoScalingConfig"]:
        del prepared_event["autoScalingConfig"]["scheduling"]

    # Log the complete payload being sent (excluding large environment variables)
    debug_payload = deepcopy(prepared_event)
    if "containerConfig" in debug_payload and "environment" in debug_payload["containerConfig"]:
        debug_payload["containerConfig"][
            "environment"
        ] = f"<{len(debug_payload['containerConfig']['environment'])} env vars>"

    try:
        response = lambdaClient.invoke(
            FunctionName=os.environ["ECS_MODEL_DEPLOYER_FN_ARN"],
            Payload=json.dumps({"modelConfig": prepared_event}),
        )

    except Exception as invoke_error:
        raise StackFailedToCreateException(
            json.dumps(
                {
                    "error": f"Failed to invoke ECS Model Deployer Lambda: {str(invoke_error)}",
                    "event": event,
                    "invoke_error": str(invoke_error),
                }
            )
        )

    try:
        payload = response["Payload"].read()
        payload = json.loads(payload)
    except Exception as parse_error:
        raise StackFailedToCreateException(
            json.dumps(
                {
                    "error": f"Failed to parse ECS Model Deployer response: {str(parse_error)}",
                    "event": event,
                    "raw_response": str(response["Payload"].read()),
                    "parse_error": str(parse_error),
                }
            )
        )

    stack_name = payload.get("stackName", None)

    if not stack_name:
        error_message = payload.get("errorMessage")
        error_type = payload.get("errorType")
        trace = payload.get("trace", [])
        raise StackFailedToCreateException(
            json.dumps(
                {
                    "error": f"Failed to create Model CloudFormation Stack. {error_type}: {error_message}",
                    "event": event,
                    "deployer_response": payload,
                    "debug_info": {
                        "error_type": error_type,
                        "error_message": error_message,
                        "stack_trace": trace,
                        "full_response": payload,
                    },
                }
            )
        )

    response = cfnClient.describe_stacks(StackName=stack_name)
    stack_arn = response["Stacks"][0]["StackId"]
    output_dict["stack_name"] = stack_name
    output_dict["stack_arn"] = stack_arn

    model_table.update_item(
        Key={"model_id": request.modelId},
        UpdateExpression="SET #csn = :stack_name, #csa = :stack_arn, last_modified_date = :lm",
        ExpressionAttributeNames={"#csn": "cloudformation_stack_name", "#csa": "cloudformation_stack_arn"},
        ExpressionAttributeValues={
            ":stack_name": stack_name,
            ":stack_arn": stack_arn,
            ":lm": now(),
        },
    )

    output_dict["remaining_polls_stack"] = 30

    return output_dict


def handle_poll_create_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check that model infrastructure creation has completed or not."""
    output_dict = deepcopy(event)
    stack = cfnClient.describe_stacks(StackName=event["stack_name"])["Stacks"][0]
    stackStatus = stack["StackStatus"]
    if stackStatus in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]:
        outputs = stack["Outputs"]
        for output in outputs:
            if output["OutputKey"] == "modelEndpointUrl":
                output_dict["modelUrl"] = output["OutputValue"]
            elif output["OutputKey"] == "autoScalingGroup":
                output_dict["autoScalingGroup"] = output["OutputValue"]
        output_dict["continue_polling_stack"] = False
        return output_dict
    elif stackStatus in ["CREATE_IN_PROGRESS", "UPDATE_IN_PROGRESS"]:
        output_dict["continue_polling_stack"] = True
        output_dict["remaining_polls_stack"] -= 1
        if output_dict["remaining_polls_stack"] <= 0:
            raise MaxPollsExceededException(
                json.dumps(
                    {
                        "error": "Max number of CloudFormation polls reached.",
                        "event": event,
                    }
                )
            )
        return output_dict
    else:
        raise UnexpectedCloudFormationStateException(
            json.dumps(
                {
                    "error": f"Stack entered unexpected state: {stackStatus}",
                    "event": event,
                }
            )
        )


def handle_add_model_to_litellm(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Add model to LiteLLM once it is created."""
    output_dict = deepcopy(event)
    is_lisa_managed = event["create_infra"]

    # Parse the JSON string from environment variable
    litellm_config_str = os.environ.get("LITELLM_CONFIG_OBJ", json.dumps({}))
    try:
        litellm_params = json.loads(litellm_config_str)
        litellm_params = litellm_params.get("litellm_settings", {})
    except json.JSONDecodeError:
        # Fallback to default if JSON parsing fails
        litellm_params = {}

    # Only set api_key if it's present in the event
    if "apiKey" in event:
        litellm_params["api_key"] = event["apiKey"]  # pragma: allowlist-secret
    litellm_params["drop_params"] = True  # drop unrecognized param instead of failing the request on it

    if is_lisa_managed:
        # get load balancer from cloudformation stack
        litellm_params["model"] = f'openai/{event["modelName"]}'
        litellm_params["api_base"] = f"{event['modelUrl']}/v1"  # model's OpenAI-compliant route
    else:
        litellm_params["model"] = event["modelName"]

    litellm_response = litellm_client.add_model(
        model_name=event["modelId"],
        litellm_params=litellm_params,
    )

    # Handle different LiteLLM API response structures
    if "model_info" in litellm_response and "id" in litellm_response["model_info"]:
        litellm_id = litellm_response["model_info"]["id"]
    elif "id" in litellm_response:
        litellm_id = litellm_response["id"]
    elif "model_id" in litellm_response:
        litellm_id = litellm_response["model_id"]
    else:
        # Log the actual response structure for debugging
        logger.error(f"Unexpected LiteLLM response structure: {litellm_response}")
        raise KeyError(f"Could not find model ID in LiteLLM response: {litellm_response}")

    output_dict["litellm_id"] = litellm_id

    model_table.update_item(
        Key={"model_id": event["modelId"]},
        UpdateExpression=(
            "SET model_status = :ms, litellm_id = :lid, last_modified_date = :lm, model_url = :mu, "
            "auto_scaling_group = :asg"
        ),
        ExpressionAttributeValues={
            ":ms": ModelStatus.IN_SERVICE,
            ":lid": litellm_id,
            ":lm": now(),
            ":mu": litellm_params.get("api_base", ""),
            ":asg": event.get("autoScalingGroup", ""),
        },
    )

    # If scheduling is configured, sync model status to ensure it reflects actual ASG state
    scheduling_config = event.get("autoScalingConfig", {}).get("scheduling")
    auto_scaling_group = event.get("autoScalingGroup")

    if scheduling_config and auto_scaling_group:
        try:
            schedule_monitoring.sync_model_status(
                {"operation": "sync_status", "modelId": event["modelId"], "autoScalingGroup": auto_scaling_group}
            )
            logger.info(f"Synced model status after creation for {event['modelId']}")
        except Exception as sync_error:
            logger.error(f"Failed to sync status after model creation: {sync_error}")

    return output_dict


def handle_add_guardrails_to_litellm(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Add guardrails to LiteLLM and store them in DynamoDB."""
    logger.info(f"Adding guardrails to LiteLLM for model: {event.get('modelId')}")
    output_dict = deepcopy(event)

    # Check if guardrails config exists
    if not event.get("guardrailsConfig") or not event["guardrailsConfig"]:
        logger.info("No guardrails configuration found, skipping guardrail creation")
        output_dict["guardrail_ids"] = []
        return output_dict

    guardrail_ids = []
    created_guardrails = []

    try:
        # Process each guardrail in the configuration
        for guardrail_key, guardrail_config in event["guardrailsConfig"].items():
            logger.info(f"Processing guardrail: {guardrail_key}")

            model_id = event["modelId"]

            # Transform guardrail config to LiteLLM format
            litellm_guardrail_config = {
                "guardrail": {
                    "guardrail_name": f'{guardrail_config["guardrailName"]}-{model_id}',
                    "litellm_params": {
                        "guardrail": "bedrock",
                        "mode": str(guardrail_config.get("mode", "pre_call")),
                        "guardrailIdentifier": guardrail_config["guardrailIdentifier"],
                        "guardrailVersion": guardrail_config.get("guardrailVersion", "DRAFT"),
                        "default_on": False,
                    },
                    "guardrail_info": {"description": guardrail_config.get("description", "")},
                }
            }

            # Create guardrail in LiteLLM
            logger.info(f"Creating guardrail in LiteLLM: {guardrail_config['guardrailName']}")
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
                guardrailId=litellm_guardrail_id,
                modelId=model_id,
                guardrailName=guardrail_config["guardrailName"],
                guardrailIdentifier=guardrail_config["guardrailIdentifier"],
                guardrailVersion=guardrail_config.get("guardrailVersion", "DRAFT"),
                mode=guardrail_config.get("mode", "pre_call"),
                description=guardrail_config.get("description"),
                allowedGroups=guardrail_config.get("allowedGroups", []),
            )

            # Store in DynamoDB
            logger.info(f"Storing guardrail in DynamoDB: {litellm_guardrail_id}")
            guardrails_table.put_item(Item=guardrail_entry.model_dump())

            guardrail_ids.append(litellm_guardrail_id)
            created_guardrails.append(
                {
                    "guardrail_id": litellm_guardrail_id,
                    "guardrail_name": guardrail_config["guardrailName"],
                }
            )

            logger.info(
                f"Successfully created guardrail: {guardrail_config['guardrailName']} with ID: {litellm_guardrail_id}"
            )

    except Exception as e:
        logger.error(f"Error creating guardrails: {str(e)}")

        # Clean up any created guardrails on failure
        for created_guardrail in created_guardrails:
            try:
                logger.info(f"Cleaning up guardrail: {created_guardrail['guardrail_id']}")
                # Delete from DynamoDB
                guardrails_table.delete_item(
                    Key={"guardrail_id": created_guardrail["guardrail_id"], "model_id": event["modelId"]}
                )
                # Delete from LiteLLM
                litellm_client.delete_guardrail(created_guardrail["litellm_guardrail_id"])
            except Exception as cleanup_error:
                logger.error(f"Error during guardrail cleanup: {str(cleanup_error)}")

        # Re-raise the original exception
        raise e

    output_dict["guardrail_ids"] = guardrail_ids
    output_dict["created_guardrails"] = created_guardrails

    logger.info(f"Successfully created {len(guardrail_ids)} guardrails for model: {event['modelId']}")
    return output_dict


def handle_failure(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle failures from state machine.

    Possible causes of failures would be:
    1. Docker Image failed to replicate into ECR in expected amount of time
    2. CloudFormation Stack creation failed from parameter validation.
    3. CloudFormation Stack creation failed from taking too long to stand up.

    Expectation of this function is to terminate the EC2 instance if it is still running, and to set the model status
    to Failed. Cleaning up the CloudFormation stack, if it still exists, will happen in the DeleteModel API.
    """
    logger.error(f"Handling state machine failure: {event}")

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

    logger.error(f"Failure reason: {error_reason}, Model ID: {original_event.get('modelId', 'unknown')}")

    # terminate EC2 instance if we have one recorded
    if "image_info" in original_event and "instance_id" in original_event["image_info"]:
        logger.info(f"Terminating EC2 instance: {original_event['image_info']['instance_id']}")
        ec2Client.terminate_instances(InstanceIds=[original_event["image_info"]["instance_id"]])

    # set model as Failed in DDB, so it shows as such in the UI. adds error reason as well.
    model_table.update_item(
        Key={"model_id": original_event["modelId"]},
        UpdateExpression="SET model_status = :ms, last_modified_date = :lm, failure_reason = :fr",
        ExpressionAttributeValues={
            ":ms": ModelStatus.FAILED,
            ":lm": now(),
            ":fr": error_reason,
        },
    )
    return event
