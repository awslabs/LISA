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
import os
from copy import deepcopy
from typing import Any, Dict

import boto3
from models.domain_objects import CreateModelRequest

lambdaClient = boto3.client("lambda")
ecrClient = boto3.client("ecr")
ec2Client = boto3.client("ec2")
ddbResource = boto3.resource("dynamodb")
model_table = ddbResource.Table(os.environ["MODEL_TABLE_NAME"])


def handle_set_model_to_creating(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set DDB entry to CREATING status."""
    output_dict = deepcopy(event)
    request = CreateModelRequest.validate(event)

    if (
        request.AutoScalingConfig  # noqa: W503
        and request.ContainerConfig  # noqa: W503
        and request.InferenceContainer  # noqa: W503
        and request.InstanceType  # noqa: W503
        and request.LoadBalancerConfig  # noqa: W503
    ):
        model_table.update_item(
            Key={"model_id": request.ModelId}, AttributeUpdates={"Status": {"Value": "CREATING", "Action": "PUT"}}
        )
        output_dict["create_infra"] = True
    else:
        output_dict["create_infra"] = False
    return output_dict


def handle_start_copy_docker_image(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Start process for copying Docker image into local AWS account."""
    output_dict = deepcopy(event)
    request = CreateModelRequest.validate(event)

    response = lambdaClient.invoke(
        FunctionName=os.environ["DOCKER_IMAGE_BUILDER_FN_ARN"],
        Payload=json.dumps(
            {
                "base_image": request.ContainerConfig.BaseImage.BaseImage,
                "layer_to_add": request.ContainerConfig.BaseImage.Path,
            }
        ),
    )

    payload = response["Payload"].read()
    output_dict["image_info"] = json.loads(payload)
    output_dict["image_info"]["remaining_polls"] = 30
    return output_dict


def handle_poll_docker_image_available(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check that Docker image is available in account or not."""
    output_dict = deepcopy(event)

    try:
        ecrClient.describe_images(
            repositoryName=os.environ["ECR_REPOSITORY_NAME"], imageIds=[{"imageTag": event["image_info"]["image_tag"]}]
        )
    except ecrClient.exceptions.ImageNotFoundException:
        output_dict["continue_polling_docker"] = True
        output_dict["image_info"]["remaining_polls"] -= 1
        if output_dict["image_info"]["remaining_polls"] <= 0:
            ec2Client.terminate_instances(InstanceIds=[event["image_info"]["instance_id"]])
            raise Exception(
                "Maximum number of ECR poll attempts reached. Something went wrong building the docker image."
            )
        return output_dict

    output_dict["continue_polling_docker"] = False
    ec2Client.terminate_instances(InstanceIds=[event["image_info"]["instance_id"]])
    return output_dict


def handle_start_create_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Start model infrastructure creation."""
    output_dict = deepcopy(event)
    return output_dict


def handle_poll_create_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Check that model infrastructure creation has completed or not."""
    output_dict = deepcopy(event)
    output_dict["continue_polling_stack"] = False
    return output_dict


def handle_add_model_to_litellm(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Add model to LiteLLM once it is created."""
    output_dict = deepcopy(event)
    return output_dict
