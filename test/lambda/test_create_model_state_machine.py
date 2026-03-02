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

"""Unit tests for create_model state machine functions."""

import json
import os
import sys
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.config import Config
from moto import mock_aws

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["MODEL_TABLE_NAME"] = "model-table"
os.environ["GUARDRAILS_TABLE_NAME"] = "guardrails-table"
os.environ["ECR_REPOSITORY_NAME"] = "test-ecr-repo"
os.environ["ECR_REPOSITORY_ARN"] = "arn:aws:ecr:us-east-1:123456789012:repository/test-ecr-repo"
os.environ["DOCKER_IMAGE_BUILDER_FN_ARN"] = "arn:aws:lambda:us-east-1:123456789012:function:docker-image-builder"
os.environ["ECS_MODEL_DEPLOYER_FN_ARN"] = "arn:aws:lambda:us-east-1:123456789012:function:ecs-model-deployer"
os.environ["MANAGEMENT_KEY_NAME"] = "test-management-key"
os.environ["LITELLM_CONFIG_OBJ"] = '{"litellm_settings": {"drop_params": true}}'

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")

# Create mock modules
mock_common = MagicMock()
mock_common.get_cert_path.return_value = None
mock_common.get_rest_api_container_endpoint.return_value = "https://test-api.example.com"
mock_common.retry_config = retry_config

# Create mock LiteLLMClient
mock_litellm_client = MagicMock()
mock_litellm_client.add_model.return_value = {"model_info": {"id": "test-litellm-id"}}
mock_litellm_client.create_guardrail.return_value = {"guardrail_id": "test-guardrail-id"}
mock_litellm_client.delete_guardrail.return_value = {"status": "deleted"}

# First, patch sys.modules
patch.dict(
    "sys.modules",
    {
        "create_env_variables": MagicMock(),
    },
).start()

# Then patch the specific functions
patch("utilities.common_functions.get_cert_path", mock_common.get_cert_path).start()
patch("utilities.common_functions.get_rest_api_container_endpoint", mock_common.get_rest_api_container_endpoint).start()
patch("utilities.common_functions.retry_config", retry_config).start()
patch("models.clients.litellm_client.LiteLLMClient", return_value=mock_litellm_client).start()

# Mock boto3 clients
mock_lambda = MagicMock()
mock_ecr = MagicMock()
mock_ec2 = MagicMock()
mock_cfn = MagicMock()
mock_iam = MagicMock()
mock_secrets = MagicMock()

IMAGE_TAG = "test-tag"


# Create mock exception classes for ECR
class MockECRExceptions:
    class ImageNotFoundException(Exception):
        pass


mock_ecr.exceptions = MockECRExceptions()

mock_lambda.invoke.return_value = {
    "Payload": MagicMock(
        read=lambda: json.dumps({"image_tag": "test-tag", "instance_id": "i-1234567890abcdef0"}).encode()
    )
}
mock_ecr.describe_images.return_value = {"imageDetails": [{"imageTags": ["test-tag"]}]}
mock_cfn.describe_stacks.return_value = {
    "Stacks": [
        {
            "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id",
            "StackStatus": "CREATE_COMPLETE",
            "Outputs": [
                {"OutputKey": "modelEndpointUrl", "OutputValue": "https://test-model.example.com"},
                {"OutputKey": "autoScalingGroup", "OutputValue": "test-asg"},
            ],
        }
    ]
}
mock_secrets.get_secret_value.return_value = {"SecretString": "test-secret"}


# Create comprehensive mock for boto3.client to handle all possible service requests
def mock_boto3_client(*args, **kwargs):
    # Support both (service_name, region_name, config) and (service_name)
    service = args[0] if args else kwargs.get("service_name", kwargs.get("service"))
    if service == "lambda":
        return mock_lambda
    elif service == "ecr":
        return mock_ecr
    elif service == "ec2":
        return mock_ec2
    elif service == "cloudformation":
        return mock_cfn
    elif service == "iam":
        return mock_iam
    elif service == "secretsmanager":
        return mock_secrets
    elif service == "ssm":
        # Return a basic mock for SSM
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "mock-value"}}
        return mock_ssm
    elif service == "s3":
        # Return a basic mock for S3
        mock_s3 = MagicMock()
        return mock_s3
    else:
        # Return a generic mock for any other services
        return MagicMock()


# Note: This module needs global boto3.client patch for import-time dependencies
patch("boto3.client", side_effect=mock_boto3_client).start()

# Patch the specific clients in the state machine module
patch("models.state_machine.create_model.ecrClient", mock_ecr).start()
patch("models.state_machine.create_model.ec2Client", mock_ec2).start()
patch("models.state_machine.create_model.cfnClient", mock_cfn).start()
patch("models.state_machine.create_model.lambdaClient", mock_lambda).start()

from models.domain_objects import InferenceContainer, ModelStatus

# Now import the state machine functions
from models.state_machine.create_model import (
    get_container_path,
    handle_add_guardrails_to_litellm,
    handle_add_model_to_litellm,
    handle_failure,
    handle_poll_create_stack,
    handle_poll_docker_image_available,
    handle_set_model_to_creating,
    handle_start_copy_docker_image,
    handle_start_create_stack,
)


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def model_table(dynamodb):
    """Create a mock DynamoDB table for models."""
    table = dynamodb.create_table(
        TableName="model-table",
        KeySchema=[{"AttributeName": "model_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "model_id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture(scope="function")
def guardrails_table(dynamodb):
    """Create a mock DynamoDB table for guardrails."""
    table = dynamodb.create_table(
        TableName="guardrails-table",
        KeySchema=[
            {"AttributeName": "guardrailId", "KeyType": "HASH"},
            {"AttributeName": "modelId", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "guardrailId", "AttributeType": "S"},
            {"AttributeName": "modelId", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture
def sample_event():
    """Sample event for state machine functions."""
    return {
        "modelId": "test-model",
        "modelName": "test-model-name",
        "modelType": "textgen",
        "streaming": True,
        "autoScalingConfig": {
            "minCapacity": 1,
            "maxCapacity": 3,
            "cooldown": 60,
            "defaultInstanceWarmup": 300,
            "metricConfig": {
                "estimatedInstanceWarmup": 300,
                "targetValue": 60,
                "albMetricName": "RequestCountPerTarget",
                "duration": 60,
            },
        },
        "containerConfig": {
            "image": {"baseImage": "test-image:test-tag", "type": "ecr"},
            "environment": {"TEST_VAR": "test_value"},
            "sharedMemorySize": 2048,
            "healthCheckConfig": {
                "command": "curl -f http://localhost:8080/health || exit 1",
                "interval": 30,
                "startPeriod": 30,
                "timeout": 5,
                "retries": 3,
            },
        },
        "inferenceContainer": "vllm",
        "instanceType": "t3.medium",
        "loadBalancerConfig": {
            "healthCheckConfig": {
                "healthyThresholdCount": 2,
                "unhealthyThresholdCount": 2,
                "path": "/health",
                "timeout": 5,
                "interval": 10,
            }
        },
    }


def test_get_container_path():
    """Test container path mapping for different inference containers."""
    assert get_container_path(InferenceContainer.TEI) == "embedding/tei"
    assert get_container_path(InferenceContainer.TGI) == "textgen/tgi"
    assert get_container_path(InferenceContainer.VLLM) == "vllm"


def test_handle_set_model_to_creating_lisa_managed(model_table, sample_event, lambda_context):
    """Test setting model to creating status for LISA-managed model."""
    with patch("models.state_machine.create_model.model_table", model_table):
        result = handle_set_model_to_creating(sample_event, lambda_context)

        assert result["create_infra"] is True
        assert result["modelId"] == "test-model"

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.CREATING
        assert item["model_config"] == sample_event


def test_handle_set_model_to_creating_not_lisa_managed(model_table, lambda_context):
    """Test setting model to creating status for non-LISA-managed model."""
    event = {
        "modelId": "test-model",
        "modelName": "test-model-name",
        "modelType": "textgen",
        "streaming": True,
    }

    with patch("models.state_machine.create_model.model_table", model_table):
        result = handle_set_model_to_creating(event, lambda_context)

        assert result["create_infra"] is False
        assert result["modelId"] == "test-model"


def test_handle_start_copy_docker_image(sample_event, lambda_context):
    """Test starting Docker image copy process."""
    # Mock ECR image found to trigger ECR verification path
    mock_ecr.describe_images.return_value = {"imageDetails": [{"imageTags": [IMAGE_TAG]}]}

    result = handle_start_copy_docker_image(sample_event, lambda_context)

    assert result["containerConfig"]["image"]["path"] == "vllm"
    assert "image_info" in result
    assert result["image_info"]["image_tag"] == IMAGE_TAG
    assert result["image_info"]["image_type"] == "ecr"
    assert result["image_info"]["remaining_polls"] == 0
    assert result["image_info"]["image_status"] == "prebuilt"

    # Verify ECR describe_images was called for verification
    mock_ecr.describe_images.assert_called_once()
    call_args = mock_ecr.describe_images.call_args
    assert call_args[1]["repositoryName"] == "test-image"
    assert call_args[1]["imageIds"] == [{"imageTag": IMAGE_TAG}]


def test_handle_poll_docker_image_available_success(sample_event, lambda_context):
    """Test polling Docker image when image is available."""
    event = deepcopy(sample_event)
    event["image_info"] = {"image_tag": "test-tag", "instance_id": "i-1234567890abcdef0", "remaining_polls": 10}

    # Mock image found
    mock_ecr.describe_images.return_value = {"imageDetails": [{"imageTags": ["test-tag"]}]}

    result = handle_poll_docker_image_available(event, lambda_context)

    assert result["continue_polling_docker"] is False
    mock_ec2.terminate_instances.assert_called_with(InstanceIds=["i-1234567890abcdef0"])


def test_handle_poll_docker_image_available_not_ready(sample_event, lambda_context):
    """Test polling Docker image when image is not yet available."""
    event = deepcopy(sample_event)
    event["image_info"] = {"image_tag": "test-tag", "instance_id": "i-1234567890abcdef0", "remaining_polls": 10}

    # Mock image not found
    mock_ecr.describe_images.side_effect = mock_ecr.exceptions.ImageNotFoundException()

    result = handle_poll_docker_image_available(event, lambda_context)

    assert result["continue_polling_docker"] is True
    assert result["image_info"]["remaining_polls"] == 9


def test_handle_poll_docker_image_available_max_polls_exceeded(sample_event, lambda_context):
    """Test polling Docker image when max polls exceeded."""
    event = deepcopy(sample_event)
    event["image_info"] = {"image_tag": "test-tag", "instance_id": "i-1234567890abcdef0", "remaining_polls": 1}

    # Mock image not found
    mock_ecr.describe_images.side_effect = mock_ecr.exceptions.ImageNotFoundException()

    from models.exception import MaxPollsExceededException

    with pytest.raises(MaxPollsExceededException):
        handle_poll_docker_image_available(event, lambda_context)

    mock_ec2.terminate_instances.assert_called_with(InstanceIds=["i-1234567890abcdef0"])


def test_handle_start_create_stack(model_table, sample_event, lambda_context):
    """Test starting CloudFormation stack creation."""
    event = deepcopy(sample_event)
    event["image_info"] = {"image_tag": "test-tag"}

    # Mock ECS model deployer response
    mock_lambda.invoke.return_value = {
        "Payload": MagicMock(read=lambda: json.dumps({"stackName": "test-stack"}).encode())
    }

    with patch("models.state_machine.create_model.model_table", model_table):
        result = handle_start_create_stack(event, lambda_context)

        assert result["stack_name"] == "test-stack"
        assert result["stack_arn"] == "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id"
        assert result["remaining_polls_stack"] == 30

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["cloudformation_stack_name"] == "test-stack"


def test_handle_start_create_stack_no_stack_name(sample_event, lambda_context):
    """Test starting CloudFormation stack creation when no stack name returned."""
    event = deepcopy(sample_event)
    event["image_info"] = {"image_tag": "test-tag"}

    # Mock ECS model deployer response without stack name
    mock_lambda.invoke.return_value = {"Payload": MagicMock(read=lambda: json.dumps({}).encode())}

    from models.exception import StackFailedToCreateException

    with pytest.raises(StackFailedToCreateException):
        handle_start_create_stack(event, lambda_context)


def test_handle_poll_create_stack_complete(sample_event, lambda_context):
    """Test polling CloudFormation stack when creation is complete."""
    event = deepcopy(sample_event)
    event["stack_name"] = "test-stack"
    event["remaining_polls_stack"] = 10

    result = handle_poll_create_stack(event, lambda_context)

    assert result["continue_polling_stack"] is False
    assert result["modelUrl"] == "https://test-model.example.com"
    assert result["autoScalingGroup"] == "test-asg"


def test_handle_poll_create_stack_in_progress(sample_event, lambda_context):
    """Test polling CloudFormation stack when creation is in progress."""
    event = deepcopy(sample_event)
    event["stack_name"] = "test-stack"
    event["remaining_polls_stack"] = 10

    # Mock stack in progress
    mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]}

    result = handle_poll_create_stack(event, lambda_context)

    assert result["continue_polling_stack"] is True
    assert result["remaining_polls_stack"] == 9


def test_handle_poll_create_stack_max_polls_exceeded(sample_event, lambda_context):
    """Test polling CloudFormation stack when max polls exceeded."""
    event = deepcopy(sample_event)
    event["stack_name"] = "test-stack"
    event["remaining_polls_stack"] = 1

    # Mock stack in progress
    mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]}

    from models.exception import MaxPollsExceededException

    with pytest.raises(MaxPollsExceededException):
        handle_poll_create_stack(event, lambda_context)


def test_handle_poll_create_stack_unexpected_state(sample_event, lambda_context):
    """Test polling CloudFormation stack with unexpected state."""
    event = deepcopy(sample_event)
    event["stack_name"] = "test-stack"

    # Mock unexpected stack state
    mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "DELETE_COMPLETE"}]}

    from models.exception import UnexpectedCloudFormationStateException

    with pytest.raises(UnexpectedCloudFormationStateException):
        handle_poll_create_stack(event, lambda_context)


def test_handle_add_model_to_litellm_lisa_managed(model_table, sample_event, lambda_context):
    """Test adding LISA-managed model to LiteLLM."""
    event = deepcopy(sample_event)
    event["create_infra"] = True
    event["modelUrl"] = "https://test-model.example.com"
    event["autoScalingGroup"] = "test-asg"

    with patch("models.state_machine.create_model.model_table", model_table):
        result = handle_add_model_to_litellm(event, lambda_context)

        assert result["litellm_id"] == "test-litellm-id"

        # Verify LiteLLM client call
        mock_litellm_client.add_model.assert_called_once()
        call_args = mock_litellm_client.add_model.call_args
        assert call_args[1]["model_name"] == "test-model"
        assert "hosted_vllm/test-model-name" in call_args[1]["litellm_params"]["model"]

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.IN_SERVICE
        assert item["litellm_id"] == "test-litellm-id"


def test_handle_add_model_to_litellm_lisa_managed_non_vllm(model_table, sample_event, lambda_context):
    """Test adding a tgi LISA-managed model to LiteLLM."""
    event = deepcopy(sample_event)
    event["inferenceContainer"] = "tgi"
    event["create_infra"] = True
    event["modelUrl"] = "https://test-model.example.com"
    event["autoScalingGroup"] = "test-asg"
    mock_litellm_client.reset_mock()

    with patch("models.state_machine.create_model.model_table", model_table):
        result = handle_add_model_to_litellm(event, lambda_context)

        assert result["litellm_id"] == "test-litellm-id"

        # Verify LiteLLM client call
        mock_litellm_client.add_model.assert_called_once()
        call_args = mock_litellm_client.add_model.call_args
        assert call_args[1]["model_name"] == "test-model"
        assert "openai/test-model-name" in call_args[1]["litellm_params"]["model"]

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.IN_SERVICE
        assert item["litellm_id"] == "test-litellm-id"


def test_handle_add_model_to_litellm_not_lisa_managed(model_table, sample_event, lambda_context):
    """Test adding non-LISA-managed model to LiteLLM."""
    event = deepcopy(sample_event)
    event["create_infra"] = False

    with patch("models.state_machine.create_model.model_table", model_table):
        result = handle_add_model_to_litellm(event, lambda_context)

        assert result["litellm_id"] == "test-litellm-id"

        # Verify LiteLLM client call
        call_args = mock_litellm_client.add_model.call_args
        assert call_args[1]["litellm_params"]["model"] == "test-model-name"


def test_handle_failure_with_instance(model_table, sample_event, lambda_context):
    """Test handling failure with EC2 instance to terminate."""
    event = {
        "Cause": json.dumps(
            {
                "errorMessage": json.dumps(
                    {
                        "error": "Test error",
                        "event": {"modelId": "test-model", "image_info": {"instance_id": "i-1234567890abcdef0"}},
                    }
                )
            }
        )
    }

    with patch("models.state_machine.create_model.model_table", model_table):
        result = handle_failure(event, lambda_context)

        assert result == event

        # Verify EC2 instance termination
        mock_ec2.terminate_instances.assert_called_with(InstanceIds=["i-1234567890abcdef0"])

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.FAILED
        assert item["failure_reason"] == "Test error"


def test_handle_failure_without_instance(model_table, lambda_context):
    """Test handling failure without EC2 instance."""
    event = {
        "Cause": json.dumps({"errorMessage": json.dumps({"error": "Test error", "event": {"modelId": "test-model"}})})
    }

    with patch("models.state_machine.create_model.model_table", model_table):
        result = handle_failure(event, lambda_context)

        assert result == event

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.FAILED
        assert item["failure_reason"] == "Test error"


def test_handle_start_copy_docker_image_tei(lambda_context):
    """Test Docker image copy for TEI container."""
    event = {
        "modelId": "test-model",
        "modelName": "test-model-name",
        "modelType": "embedding",
        "inferenceContainer": "tei",
        "instanceType": "t3.medium",
        "autoScalingConfig": {
            "minCapacity": 1,
            "maxCapacity": 3,
            "cooldown": 60,
            "defaultInstanceWarmup": 300,
            "metricConfig": {
                "estimatedInstanceWarmup": 300,
                "targetValue": 60,
                "albMetricName": "RequestCountPerTarget",
                "duration": 60,
            },
        },
        "containerConfig": {
            "image": {"baseImage": "test-image:test-tag", "type": "ecr"},
            "sharedMemorySize": 2048,
            "healthCheckConfig": {
                "command": "curl -f http://localhost:8080/health || exit 1",
                "interval": 30,
                "startPeriod": 30,
                "timeout": 5,
                "retries": 3,
            },
        },
        "loadBalancerConfig": {
            "healthCheckConfig": {
                "healthyThresholdCount": 2,
                "unhealthyThresholdCount": 2,
                "path": "/health",
                "timeout": 5,
                "interval": 10,
            }
        },
    }

    # Reset mock and set return value for ECR image found
    mock_ecr.describe_images.side_effect = None
    mock_ecr.describe_images.return_value = {"imageDetails": [{"imageTags": [IMAGE_TAG]}]}

    result = handle_start_copy_docker_image(event, lambda_context)

    assert result["containerConfig"]["image"]["path"] == "embedding/tei"
    assert result["image_info"]["image_tag"] == IMAGE_TAG
    assert result["image_info"]["image_type"] == "ecr"
    assert result["image_info"]["image_status"] == "prebuilt"


def test_handle_start_copy_docker_image_tgi(lambda_context):
    """Test Docker image copy for TGI container."""
    event = {
        "modelId": "test-model",
        "modelName": "test-model-name",
        "modelType": "textgen",
        "inferenceContainer": "tgi",
        "instanceType": "t3.medium",
        "autoScalingConfig": {
            "minCapacity": 1,
            "maxCapacity": 3,
            "cooldown": 60,
            "defaultInstanceWarmup": 300,
            "metricConfig": {
                "estimatedInstanceWarmup": 300,
                "targetValue": 60,
                "albMetricName": "RequestCountPerTarget",
                "duration": 60,
            },
        },
        "containerConfig": {
            "image": {"baseImage": "test-image:test-tag", "type": "ecr"},
            "sharedMemorySize": 2048,
            "healthCheckConfig": {
                "command": "curl -f http://localhost:8080/health || exit 1",
                "interval": 30,
                "startPeriod": 30,
                "timeout": 5,
                "retries": 3,
            },
        },
        "loadBalancerConfig": {
            "healthCheckConfig": {
                "healthyThresholdCount": 2,
                "unhealthyThresholdCount": 2,
                "path": "/health",
                "timeout": 5,
                "interval": 10,
            }
        },
    }

    # Reset mock and set return value for ECR image found
    mock_ecr.describe_images.side_effect = None
    mock_ecr.describe_images.return_value = {"imageDetails": [{"imageTags": [IMAGE_TAG]}]}

    result = handle_start_copy_docker_image(event, lambda_context)

    assert result["containerConfig"]["image"]["path"] == "textgen/tgi"
    assert result["image_info"]["image_tag"] == IMAGE_TAG
    assert result["image_info"]["image_type"] == "ecr"
    assert result["image_info"]["image_status"] == "prebuilt"


def test_handle_add_model_to_litellm_json_decode_error(model_table, sample_event, lambda_context):
    """Test adding model to LiteLLM with invalid JSON config."""
    event = deepcopy(sample_event)
    event["create_infra"] = True
    event["modelUrl"] = "https://test-model.example.com"

    with patch("os.environ.get") as mock_env:
        mock_env.return_value = "invalid-json"

        with patch("models.state_machine.create_model.model_table", model_table):
            result = handle_add_model_to_litellm(event, lambda_context)

            assert result["litellm_id"] == "test-litellm-id"

            # Should fallback to empty dict when JSON parsing fails
            call_args = mock_litellm_client.add_model.call_args
            assert call_args[1]["litellm_params"]["drop_params"] is True


def test_handle_start_create_stack_camelize_function(sample_event, lambda_context):
    """Test the internal camelize function in handle_start_create_stack."""
    event = deepcopy(sample_event)
    event["image_info"] = {"image_tag": "test-tag"}
    event["TestKey"] = {"NestedKey": "value"}

    # Reset mock_cfn for this test to include StackId
    mock_cfn.describe_stacks.return_value = {
        "Stacks": [
            {
                "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id",
                "StackStatus": "CREATE_COMPLETE",
            }
        ]
    }

    mock_lambda.invoke.return_value = {
        "Payload": MagicMock(read=lambda: json.dumps({"stackName": "test-stack"}).encode())
    }

    with patch("models.state_machine.create_model.model_table"):
        handle_start_create_stack(event, lambda_context)

    # Verify lambda was called with camelized payload
    call_args = mock_lambda.invoke.call_args
    payload = json.loads(call_args[1]["Payload"])

    # Check that keys are camelized
    assert "testKey" in payload["modelConfig"]
    assert "nestedKey" in payload["modelConfig"]["testKey"]

    # Check that certain keys are preserved
    assert payload["modelConfig"]["containerConfig"]["environment"] == {"TEST_VAR": "test_value"}
    assert payload["modelConfig"]["containerConfig"]["image"]["type"] == "ecr"


def test_handle_add_guardrails_to_litellm_with_guardrails(model_table, guardrails_table, lambda_context):
    """Test adding guardrails to LiteLLM."""
    event = {
        "modelId": "test-model",
        "guardrailsConfig": {
            "guardrail1": {
                "guardrailName": "test-guardrail",
                "guardrailIdentifier": "test-identifier",
                "guardrailVersion": "1",
                "mode": "pre_call",
                "description": "Test guardrail",
                "allowedGroups": ["group1"],
            }
        },
    }

    with patch("models.state_machine.create_model.model_table", model_table), patch(
        "models.state_machine.create_model.guardrails_table", guardrails_table
    ):
        result = handle_add_guardrails_to_litellm(event, lambda_context)

        assert len(result["guardrail_ids"]) == 1
        assert result["guardrail_ids"][0] == "test-guardrail-id"
        assert len(result["created_guardrails"]) == 1

        # Verify guardrail was stored in DynamoDB
        item = guardrails_table.get_item(Key={"guardrailId": "test-guardrail-id", "modelId": "test-model"})["Item"]
        assert item["guardrailName"] == "test-guardrail"


def test_handle_add_guardrails_to_litellm_no_guardrails(lambda_context):
    """Test adding guardrails when none are configured."""
    event = {"modelId": "test-model"}

    result = handle_add_guardrails_to_litellm(event, lambda_context)

    assert result["guardrail_ids"] == []
