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
from datetime import datetime, UTC
from typing import Any, Dict

import boto3
from botocore.config import Config
from models.clients.litellm_client import LiteLLMClient
from models.domain_objects import CreateModelRequest, InferenceContainer, ModelStatus
from models.exception import (
    MaxPollsExceededException,
    StackFailedToCreateException,
    UnexpectedCloudFormationStateException,
)
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambdaConfig = Config(connect_timeout=60, read_timeout=600, retries={"max_attempts": 1})
lambdaClient = boto3.client("lambda", region_name=os.environ["AWS_REGION"], config=lambdaConfig)
ecrClient = boto3.client("ecr", region_name=os.environ["AWS_REGION"], config=retry_config)
ec2Client = boto3.client("ec2", region_name=os.environ["AWS_REGION"], config=retry_config)
ddbResource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
model_table = ddbResource.Table(os.environ["MODEL_TABLE_NAME"])
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

    model_table.update_item(
        Key={"model_id": request.modelId},
        UpdateExpression=(
            "SET model_status = :model_status, model_config = :model_config, "
            "model_description = :model_description, last_modified_date = :lm"
        ),
        ExpressionAttributeValues={
            ":model_status": ModelStatus.CREATING,
            ":model_config": event,
            ":model_description": request.modelDescription,
            ":lm": int(datetime.now(UTC).timestamp()),
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
                repository_name = repository_name.split("/")[-1]

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

    # Handle ECR images differently - use the existing ECR image instead of the built one
    if event["image_info"].get("image_type") == "ecr":
        # For pre-existing ECR images, construct the ARN using the image repository
        account_id = os.environ.get("AWS_ACCOUNT_ID", "")
        if not account_id:
            # Try to get account ID from the existing ECR repository ARN
            ecr_repo_arn = os.environ.get("ECR_REPOSITORY_ARN", "")
            if ecr_repo_arn:
                account_id = ecr_repo_arn.split(":")[4]

        repository_arn = (
            f"arn:aws:ecr:{os.environ['AWS_REGION']}:{account_id}:repository/{event['image_info']['image_uri']}"
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

    response = lambdaClient.invoke(
        FunctionName=os.environ["ECS_MODEL_DEPLOYER_FN_ARN"],
        Payload=json.dumps({"modelConfig": prepared_event}),
    )

    payload = response["Payload"].read()
    payload = json.loads(payload)
    stack_name = payload.get("stackName", None)

    if not stack_name:
        raise StackFailedToCreateException(
            json.dumps(
                {
                    "error": "Failed to create Model CloudFormation Stack. Please validate model parameters are valid.",
                    "event": event,
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
            ":lm": int(datetime.now(UTC).timestamp()),
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

    litellm_id = litellm_response["model_info"]["id"]
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
            ":lm": int(datetime.now(UTC).timestamp()),
            ":mu": litellm_params.get("api_base", ""),
            ":asg": event.get("autoScalingGroup", ""),
        },
    )

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
    error_dict = json.loads(  # error from SFN is json payload on top of json payload we add to the exception
        json.loads(event["Cause"])["errorMessage"]
    )
    error_reason = error_dict["error"]
    original_event = error_dict["event"]
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
            ":lm": int(datetime.now(UTC).timestamp()),
            ":fr": error_reason,
        },
    )
    return event
