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
from datetime import datetime
from typing import Any, Dict

import boto3
from botocore.config import Config
from models.clients.litellm_client import LiteLLMClient
from models.domain_objects import CreateModelRequest, ModelStatus
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config

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


def handle_set_model_to_creating(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Set DDB entry to CREATING status."""
    output_dict = deepcopy(event)
    request = CreateModelRequest.validate(event)

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
        UpdateExpression="SET model_status = :model_status, model_config = :model_config, last_modified_date = :lm",
        ExpressionAttributeValues={
            ":model_status": ModelStatus.CREATING,
            ":model_config": event,
            ":lm": int(datetime.utcnow().timestamp()),
        },
    )
    output_dict["create_infra"] = is_lisa_managed
    return output_dict


def handle_start_copy_docker_image(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Start process for copying Docker image into local AWS account."""
    output_dict = deepcopy(event)
    request = CreateModelRequest.validate(event)

    response = lambdaClient.invoke(
        FunctionName=os.environ["DOCKER_IMAGE_BUILDER_FN_ARN"],
        Payload=json.dumps(
            {
                "base_image": request.containerConfig.baseImage.baseImage,
                "layer_to_add": request.containerConfig.baseImage.path,
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
    request = CreateModelRequest.validate(event)

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
    stack_name = payload.get("stackName")

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
            ":lm": int(datetime.utcnow().timestamp()),
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
        output_dict["continue_polling_stack"] = False
        return output_dict
    elif stackStatus in ["CREATE_IN_PROGRESS", "UPDATE_IN_PROGRESS"]:
        output_dict["continue_polling_stack"] = True
        output_dict["remaining_polls_stack"] -= 1
        if output_dict["remaining_polls_stack"] <= 0:
            raise Exception("Maximum number of CloudFormation polls reached")
        return output_dict
    else:
        raise Exception(f"Stack in unexpected state: {stackStatus}")


def handle_add_model_to_litellm(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Add model to LiteLLM once it is created."""
    output_dict = deepcopy(event)
    is_lisa_managed = event["create_infra"]

    litellm_params = {
        "api_key": "ignored"  # pragma: allowlist-secret not a real key, but needed for LiteLLM to be happy
    }

    if is_lisa_managed:
        # get load balancer from cloudformation stack
        litellm_params["model"] = f'openai/{event["modelName"]}'
        litellm_params["api_base"] = f"http://{event['modelUrl']}/v1"  # model's OpenAI-compliant route
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
        UpdateExpression="SET model_status = :ms, litellm_id = :lid, last_modified_date = :lm, model_url = :mu",
        ExpressionAttributeValues={
            ":ms": ModelStatus.IN_SERVICE,
            ":lid": litellm_id,
            ":lm": int(datetime.utcnow().timestamp()),
            ":mu": litellm_params.get("api_base", ""),
        },
    )

    return output_dict
