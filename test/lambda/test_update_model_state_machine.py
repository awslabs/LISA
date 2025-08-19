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

"""Unit tests for update_model state machine functions."""

import os
import sys
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
mock_litellm_client.delete_model.return_value = {"status": "deleted"}

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
mock_autoscaling = MagicMock()
mock_iam = MagicMock()
mock_secrets = MagicMock()
mock_ecs = MagicMock()
mock_cfn = MagicMock()

mock_autoscaling.update_auto_scaling_group.return_value = {}
mock_autoscaling.describe_auto_scaling_groups.return_value = {
    "AutoScalingGroups": [
        {"DesiredCapacity": 2, "Instances": [{"HealthStatus": "Healthy"}, {"HealthStatus": "Healthy"}]}
    ]
}
mock_secrets.get_secret_value.return_value = {"SecretString": "test-secret"}

# Mock ECS client responses
mock_ecs.describe_services.return_value = {
    "services": [
        {
            "taskDefinition": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:1",
            "deployments": [
                {
                    "status": "PRIMARY",
                    "rolloutState": "COMPLETED",
                    "taskDefinition": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2",
                }
            ],
        }
    ]
}
mock_ecs.describe_task_definition.return_value = {
    "taskDefinition": {
        "family": "test-task-def",
        "taskRoleArn": "arn:aws:iam::123456789012:role/test-role",
        "executionRoleArn": "arn:aws:iam::123456789012:role/test-execution-role",
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["FARGATE"],
        "cpu": "256",
        "memory": "512",
        "containerDefinitions": [
            {
                "name": "test-container",
                "environment": [
                    {"name": "EXISTING_VAR", "value": "existing_value"},
                    {"name": "TO_UPDATE", "value": "old_value"},
                ],
            }
        ],
    }
}
mock_ecs.register_task_definition.return_value = {
    "taskDefinition": {"taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2"}
}
mock_ecs.update_service.return_value = {}

# Mock CloudFormation client responses
mock_cfn.describe_stack_resources.return_value = {
    "StackResources": [
        {
            "ResourceType": "AWS::ECS::Service",
            "PhysicalResourceId": "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service",
        },
        {
            "ResourceType": "AWS::ECS::Cluster",
            "PhysicalResourceId": "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster",
        },
    ]
}


# Create comprehensive mock for boto3.client to handle all possible service requests
def mock_boto3_client(service, **kwargs):
    if service == "autoscaling":
        return mock_autoscaling
    elif service == "iam":
        return mock_iam
    elif service == "secretsmanager":
        return mock_secrets
    elif service == "ecs":
        return mock_ecs
    elif service == "cloudformation":
        return mock_cfn
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


patch("boto3.client", side_effect=mock_boto3_client).start()

from models.domain_objects import ModelStatus

# Now import the state machine functions
from models.state_machine.update_model import (
    _process_metadata_updates,
    _update_container_config,
    _update_simple_field,
    handle_ecs_update,
    handle_finish_update,
    handle_job_intake,
    handle_poll_capacity,
    handle_poll_ecs_deployment,
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


@pytest.fixture
def sample_model(model_table):
    """Sample model in DynamoDB for testing."""
    item = {
        "model_id": "test-model",
        "model_status": ModelStatus.IN_SERVICE,
        "auto_scaling_group": "test-asg",
        "litellm_id": "test-litellm-id",
        "model_url": "https://test-model.example.com/v1",
        "cloudformation_stack_name": "test-stack",
        "model_config": {
            "modelId": "test-model",
            "modelName": "test-model-name",
            "modelType": "textgen",
            "streaming": True,
            "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 3, "metricConfig": {"estimatedInstanceWarmup": 300}},
            "containerConfig": {
                "environment": {"EXISTING_VAR": "existing_value", "TO_UPDATE": "old_value"},
            },
        },
    }
    model_table.put_item(Item=item)
    return item


@pytest.fixture
def stopped_model(model_table):
    """Sample stopped model in DynamoDB for testing."""
    item = {
        "model_id": "stopped-model",
        "model_status": ModelStatus.STOPPED,
        "auto_scaling_group": "test-asg",
        "model_url": "https://test-model.example.com/v1",
        "model_config": {
            "modelId": "stopped-model",
            "modelName": "stopped-model-name",
            "modelType": "textgen",
            "streaming": True,
            "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 3, "metricConfig": {"estimatedInstanceWarmup": 300}},
        },
    }
    model_table.put_item(Item=item)
    return item


@pytest.fixture
def litellm_only_model(model_table):
    """Sample LiteLLM-only model in DynamoDB for testing."""
    item = {
        "model_id": "litellm-model",
        "model_status": ModelStatus.IN_SERVICE,
        "litellm_id": "test-litellm-id",
        "model_config": {
            "modelId": "litellm-model",
            "modelName": "litellm-model-name",
            "modelType": "textgen",
            "streaming": True,
        },
    }
    model_table.put_item(Item=item)
    return item


def test_handle_job_intake_enable_model(model_table, stopped_model, lambda_context):
    """Test enabling a stopped model."""
    event = {"model_id": "stopped-model", "update_payload": {"enabled": True}}

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_job_intake(event, lambda_context)

        assert result["has_capacity_update"] is True
        assert result["is_disable"] is False
        assert result["asg_name"] == "test-asg"
        assert result["model_warmup_seconds"] == 300
        assert result["current_model_status"] == ModelStatus.STARTING

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "stopped-model"})["Item"]
        assert item["model_status"] == ModelStatus.STARTING

        # Verify ASG update call
        mock_autoscaling.update_auto_scaling_group.assert_called_once()
        call_args = mock_autoscaling.update_auto_scaling_group.call_args
        assert call_args[1]["AutoScalingGroupName"] == "test-asg"
        assert call_args[1]["MinSize"] == 1
        assert call_args[1]["MaxSize"] == 3


def test_handle_job_intake_disable_model(model_table, sample_model, lambda_context):
    """Test disabling a running model."""
    # Reset mocks for this test
    mock_autoscaling.reset_mock()
    mock_litellm_client.reset_mock()

    event = {"model_id": "test-model", "update_payload": {"enabled": False}}

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_job_intake(event, lambda_context)

        assert result["has_capacity_update"] is False
        assert result["is_disable"] is True
        assert result["asg_name"] == "test-asg"
        assert result["current_model_status"] == ModelStatus.STOPPING

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.STOPPING
        assert item["litellm_id"] is None

        # Verify LiteLLM deletion call
        mock_litellm_client.delete_model.assert_called_once_with(identifier="test-litellm-id")

        # Verify ASG update call
        mock_autoscaling.update_auto_scaling_group.assert_called_once()
        call_args = mock_autoscaling.update_auto_scaling_group.call_args
        assert call_args[1]["AutoScalingGroupName"] == "test-asg"
        assert call_args[1]["MinSize"] == 0
        assert call_args[1]["MaxSize"] == 0
        assert call_args[1]["DesiredCapacity"] == 0


def test_handle_job_intake_autoscaling_update_running_model(model_table, sample_model, lambda_context):
    """Test updating autoscaling configuration for a running model."""
    # Reset mocks for this test
    mock_autoscaling.reset_mock()

    event = {
        "model_id": "test-model",
        "update_payload": {"autoScalingInstanceConfig": {"minCapacity": 2, "maxCapacity": 5, "desiredCapacity": 3}},
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_job_intake(event, lambda_context)

        assert result["has_capacity_update"] is False
        assert result["is_disable"] is False
        assert result["current_model_status"] == ModelStatus.UPDATING

        # Verify model config update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_config"]["autoScalingConfig"]["minCapacity"] == 2
        assert item["model_config"]["autoScalingConfig"]["maxCapacity"] == 5

        # Verify ASG update call
        mock_autoscaling.update_auto_scaling_group.assert_called_once()
        call_args = mock_autoscaling.update_auto_scaling_group.call_args
        assert call_args[1]["MinSize"] == 2
        assert call_args[1]["MaxSize"] == 5
        assert call_args[1]["DesiredCapacity"] == 3


def test_handle_job_intake_autoscaling_update_stopped_model(model_table, stopped_model, lambda_context):
    """Test updating autoscaling configuration for a stopped model."""
    # Reset mocks for this test
    mock_autoscaling.reset_mock()

    event = {
        "model_id": "stopped-model",
        "update_payload": {"autoScalingInstanceConfig": {"minCapacity": 2, "maxCapacity": 5}},
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_job_intake(event, lambda_context)

        assert result["has_capacity_update"] is False
        assert result["is_disable"] is False
        assert result["current_model_status"] == ModelStatus.UPDATING

        # Verify model config update
        item = model_table.get_item(Key={"model_id": "stopped-model"})["Item"]
        assert item["model_config"]["autoScalingConfig"]["minCapacity"] == 2
        assert item["model_config"]["autoScalingConfig"]["maxCapacity"] == 5

        # ASG should not be updated for stopped model
        mock_autoscaling.update_auto_scaling_group.assert_not_called()


def test_handle_job_intake_metadata_update(model_table, sample_model, lambda_context):
    """Test updating model metadata only."""
    event = {"model_id": "test-model", "update_payload": {"streaming": False, "modelType": "embedding"}}

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_job_intake(event, lambda_context)

        assert result["has_capacity_update"] is False
        assert result["is_disable"] is False
        assert result["current_model_status"] == ModelStatus.UPDATING
        assert result["initial_model_status"] == ModelStatus.IN_SERVICE

        # Verify model config update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_config"]["streaming"] is False
        assert item["model_config"]["modelType"] == "embedding"


def test_handle_job_intake_model_not_found(model_table, lambda_context):
    """Test handling when model is not found."""
    event = {"model_id": "nonexistent-model", "update_payload": {"enabled": True}}

    with patch("models.state_machine.update_model.model_table", model_table):
        with pytest.raises(RuntimeError, match="Requested model 'nonexistent-model' was not found"):
            handle_job_intake(event, lambda_context)


def test_handle_job_intake_litellm_only_model_activation_error(model_table, litellm_only_model, lambda_context):
    """Test error when trying to activate/deactivate LiteLLM-only model."""
    event = {"model_id": "litellm-model", "update_payload": {"enabled": False}}

    with patch("models.state_machine.update_model.model_table", model_table):
        with pytest.raises(
            RuntimeError, match="Cannot request AutoScaling updates to models that are not hosted by LISA"
        ):
            handle_job_intake(event, lambda_context)


def test_handle_job_intake_concurrent_activation_and_autoscaling_error(model_table, sample_model, lambda_context):
    """Test error when trying to do activation and autoscaling updates simultaneously."""
    event = {
        "model_id": "test-model",
        "update_payload": {"enabled": False, "autoScalingInstanceConfig": {"minCapacity": 2}},
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        with pytest.raises(
            RuntimeError, match="Cannot request AutoScaling updates at the same time as an enable or disable operation"
        ):
            handle_job_intake(event, lambda_context)


def test_handle_poll_capacity_healthy_instances(lambda_context):
    """Test polling capacity when instances are healthy."""
    event = {"model_id": "test-model", "asg_name": "test-asg", "remaining_capacity_polls": 20}

    result = handle_poll_capacity(event, lambda_context)

    assert result["should_continue_capacity_polling"] is False
    assert result["remaining_capacity_polls"] == 19
    assert "polling_error" not in result


def test_handle_poll_capacity_unhealthy_instances(lambda_context):
    """Test polling capacity when instances are not yet healthy."""
    event = {"model_id": "test-model", "asg_name": "test-asg", "remaining_capacity_polls": 20}

    # Mock unhealthy instances
    mock_autoscaling.describe_auto_scaling_groups.return_value = {
        "AutoScalingGroups": [
            {"DesiredCapacity": 2, "Instances": [{"HealthStatus": "Healthy"}, {"HealthStatus": "Unhealthy"}]}
        ]
    }

    result = handle_poll_capacity(event, lambda_context)

    assert result["should_continue_capacity_polling"] is True
    assert result["remaining_capacity_polls"] == 19
    assert "polling_error" not in result


def test_handle_poll_capacity_max_polls_exceeded(lambda_context):
    """Test polling capacity when max polls exceeded."""
    event = {"model_id": "test-model", "asg_name": "test-asg", "remaining_capacity_polls": 1}

    # Mock unhealthy instances
    mock_autoscaling.describe_auto_scaling_groups.return_value = {
        "AutoScalingGroups": [
            {"DesiredCapacity": 2, "Instances": [{"HealthStatus": "Healthy"}, {"HealthStatus": "Unhealthy"}]}
        ]
    }

    result = handle_poll_capacity(event, lambda_context)

    assert result["should_continue_capacity_polling"] is False
    assert result["remaining_capacity_polls"] == 0
    assert "polling_error" in result
    assert "did not start healthy instances" in result["polling_error"]


def test_handle_finish_update_enable_success(model_table, lambda_context):
    """Test finishing update for successful model enable."""
    # Create model without litellm_id (enabled model should get one)
    item = {
        "model_id": "test-model",
        "model_status": ModelStatus.STARTING,
        "auto_scaling_group": "test-asg",
        "model_url": "https://test-model.example.com/v1",
        "model_config": {"modelName": "test-model-name"},
    }
    model_table.put_item(Item=item)

    event = {
        "model_id": "test-model",
        "asg_name": "test-asg",
        "has_capacity_update": True,
        "is_disable": False,
        "initial_model_status": ModelStatus.STOPPED,
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_finish_update(event, lambda_context)

        assert result["litellm_id"] == "test-litellm-id"
        assert result["current_model_status"] == ModelStatus.IN_SERVICE

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.IN_SERVICE
        assert item["litellm_id"] == "test-litellm-id"

        # Verify LiteLLM add call
        mock_litellm_client.add_model.assert_called_once()
        call_args = mock_litellm_client.add_model.call_args
        assert call_args[1]["model_name"] == "test-model"


def test_handle_finish_update_disable_success(model_table, lambda_context):
    """Test finishing update for successful model disable."""
    item = {
        "model_id": "test-model",
        "model_status": ModelStatus.STOPPING,
        "auto_scaling_group": "test-asg",
        "model_url": "https://test-model.example.com/v1",
        "model_config": {"modelName": "test-model-name"},
    }
    model_table.put_item(Item=item)

    event = {
        "model_id": "test-model",
        "asg_name": "test-asg",
        "has_capacity_update": False,
        "is_disable": True,
        "initial_model_status": ModelStatus.IN_SERVICE,
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_finish_update(event, lambda_context)

        assert result["current_model_status"] == ModelStatus.STOPPED

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.STOPPED


def test_handle_finish_update_metadata_only(model_table, lambda_context):
    """Test finishing update for metadata-only update."""
    item = {
        "model_id": "test-model",
        "model_status": ModelStatus.UPDATING,
        "auto_scaling_group": "test-asg",
        "model_url": "https://test-model.example.com/v1",
        "model_config": {"modelName": "test-model-name"},
    }
    model_table.put_item(Item=item)

    event = {
        "model_id": "test-model",
        "asg_name": "test-asg",
        "has_capacity_update": False,
        "is_disable": False,
        "initial_model_status": ModelStatus.IN_SERVICE,
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_finish_update(event, lambda_context)

        assert result["current_model_status"] == ModelStatus.IN_SERVICE

        # Verify DDB update - should restore initial status
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.IN_SERVICE


def test_handle_finish_update_polling_error(model_table, lambda_context):
    """Test finishing update when there was a polling error."""
    # Reset mocks for this test
    mock_autoscaling.reset_mock()

    item = {
        "model_id": "test-model",
        "model_status": ModelStatus.STARTING,
        "auto_scaling_group": "test-asg",
        "model_url": "https://test-model.example.com/v1",
        "model_config": {"modelName": "test-model-name"},
    }
    model_table.put_item(Item=item)

    event = {
        "model_id": "test-model",
        "asg_name": "test-asg",
        "has_capacity_update": True,
        "is_disable": False,
        "polling_error": "Model did not start in time",
        "initial_model_status": ModelStatus.STOPPED,
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_finish_update(event, lambda_context)

        assert result["current_model_status"] == ModelStatus.STOPPED

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.STOPPED

        # Verify ASG is scaled down due to error
        mock_autoscaling.update_auto_scaling_group.assert_called_once()
        call_args = mock_autoscaling.update_auto_scaling_group.call_args
        assert call_args[1]["MinSize"] == 0
        assert call_args[1]["MaxSize"] == 0
        assert call_args[1]["DesiredCapacity"] == 0


def test_handle_finish_update_json_decode_error(model_table, lambda_context):
    """Test finishing update with invalid LiteLLM config JSON."""
    item = {
        "model_id": "test-model",
        "model_status": ModelStatus.STARTING,
        "auto_scaling_group": "test-asg",
        "model_url": "https://test-model.example.com/v1",
        "model_config": {"modelName": "test-model-name"},
    }
    model_table.put_item(Item=item)

    event = {
        "model_id": "test-model",
        "asg_name": "test-asg",
        "has_capacity_update": True,
        "is_disable": False,
        "initial_model_status": ModelStatus.STOPPED,
    }

    with patch("os.environ.get") as mock_env:
        mock_env.return_value = "invalid-json"

        with patch("models.state_machine.update_model.model_table", model_table):
            result = handle_finish_update(event, lambda_context)

            assert result["litellm_id"] == "test-litellm-id"

            # Should fallback to empty dict when JSON parsing fails
            call_args = mock_litellm_client.add_model.call_args
            assert call_args[1]["litellm_params"]["api_key"] == "ignored"


def test_end_to_end_enable_workflow(model_table, stopped_model, lambda_context):
    """Test complete enable workflow end-to-end."""
    # Reset mocks for this test
    mock_autoscaling.reset_mock()
    mock_litellm_client.reset_mock()

    # Ensure the autoscaling mock returns the expected values for this test
    mock_autoscaling.describe_auto_scaling_groups.return_value = {
        "AutoScalingGroups": [
            {"DesiredCapacity": 2, "Instances": [{"HealthStatus": "Healthy"}, {"HealthStatus": "Healthy"}]}
        ]
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        # Step 1: Job intake for enable
        event1 = {"model_id": "stopped-model", "update_payload": {"enabled": True}}
        result1 = handle_job_intake(event1, lambda_context)
        assert result1["has_capacity_update"] is True
        assert result1["current_model_status"] == ModelStatus.STARTING

        # Step 2: Poll capacity (healthy)
        event2 = {"model_id": "stopped-model", "asg_name": "test-asg", "remaining_capacity_polls": 20}
        result2 = handle_poll_capacity(event2, lambda_context)
        assert result2["should_continue_capacity_polling"] is False

        # Step 3: Finish update
        event3 = {
            "model_id": "stopped-model",
            "asg_name": "test-asg",
            "has_capacity_update": True,
            "is_disable": False,
            "initial_model_status": ModelStatus.STOPPED,
        }
        result3 = handle_finish_update(event3, lambda_context)
        assert result3["current_model_status"] == ModelStatus.IN_SERVICE

        # Verify final state
        item = model_table.get_item(Key={"model_id": "stopped-model"})["Item"]
        assert item["model_status"] == ModelStatus.IN_SERVICE


def test_end_to_end_disable_workflow(model_table, sample_model, lambda_context):
    """Test complete disable workflow end-to-end."""
    with patch("models.state_machine.update_model.model_table", model_table):
        # Step 1: Job intake for disable
        event1 = {"model_id": "test-model", "update_payload": {"enabled": False}}
        result1 = handle_job_intake(event1, lambda_context)
        assert result1["is_disable"] is True
        assert result1["current_model_status"] == ModelStatus.STOPPING

        # Step 2: Finish update (no polling needed for disable)
        event2 = {
            "model_id": "test-model",
            "asg_name": "test-asg",
            "has_capacity_update": False,
            "is_disable": True,
            "initial_model_status": ModelStatus.IN_SERVICE,
        }
        result2 = handle_finish_update(event2, lambda_context)
        assert result2["current_model_status"] == ModelStatus.STOPPED

        # Verify final state
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.STOPPED


def test_handle_job_intake_partial_autoscaling_config(model_table, sample_model, lambda_context):
    """Test updating only some autoscaling parameters."""
    # Reset mocks for this test
    mock_autoscaling.reset_mock()

    event = {
        "model_id": "test-model",
        "update_payload": {"autoScalingInstanceConfig": {"maxCapacity": 5}},  # Only update max capacity
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        handle_job_intake(event, lambda_context)

        # Verify model config update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_config"]["autoScalingConfig"]["minCapacity"] == 1  # Unchanged
        assert item["model_config"]["autoScalingConfig"]["maxCapacity"] == 5  # Updated

        # Verify ASG update call only includes maxCapacity
        mock_autoscaling.update_auto_scaling_group.assert_called_once()
        call_args = mock_autoscaling.update_auto_scaling_group.call_args
        assert "MaxSize" in call_args[1]
        assert call_args[1]["MaxSize"] == 5
        assert "MinSize" not in call_args[1]
        assert "DesiredCapacity" not in call_args[1]


# Tests for container configuration updating
def test_handle_job_intake_container_config_update(model_table, sample_model, lambda_context):
    """Test updating container configuration."""
    event = {
        "model_id": "test-model",
        "update_payload": {
            "containerConfig": {
                "environment": {"NEW_VAR": "new_value", "TO_UPDATE": "updated_value"},
            }
        },
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_job_intake(event, lambda_context)

        assert result["needs_ecs_update"] is True
        assert result["current_model_status"] == ModelStatus.UPDATING

        # Verify model config update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        updated_env = item["model_config"]["containerConfig"]["environment"]
        assert updated_env["NEW_VAR"] == "new_value"
        assert updated_env["TO_UPDATE"] == "updated_value"


def test_handle_job_intake_container_config_env_var_deletion(model_table, sample_model, lambda_context):
    """Test deleting environment variables using deletion markers."""
    event = {
        "model_id": "test-model",
        "update_payload": {
            "containerConfig": {
                "environment": {
                    "NEW_VAR": "new_value",
                    "TO_UPDATE": "LISA_MARKED_FOR_DELETION",  # This should be deleted
                }
            }
        },
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_job_intake(event, lambda_context)

        assert result["needs_ecs_update"] is True
        assert "container_metadata" in result
        assert "env_vars_to_delete" in result["container_metadata"]
        assert "TO_UPDATE" in result["container_metadata"]["env_vars_to_delete"]

        # Verify model config update - deleted var should be removed
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        updated_env = item["model_config"]["containerConfig"]["environment"]
        assert updated_env["NEW_VAR"] == "new_value"
        assert "TO_UPDATE" not in updated_env


def test_handle_job_intake_container_config_stopped_model_no_ecs_update(model_table, lambda_context):
    """Test container config update on stopped model doesn't trigger ECS update."""
    # Create stopped model with container config and autoScalingConfig
    item = {
        "model_id": "stopped-model",
        "model_status": ModelStatus.STOPPED,
        "auto_scaling_group": "test-asg",
        "model_config": {
            "modelId": "stopped-model",
            "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 3, "metricConfig": {"estimatedInstanceWarmup": 300}},
            "containerConfig": {"environment": {"TEST_VAR": "test_value"}},
        },
    }
    model_table.put_item(Item=item)

    event = {
        "model_id": "stopped-model",
        "update_payload": {"containerConfig": {"environment": {"NEW_VAR": "new_value"}}},
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_job_intake(event, lambda_context)

        assert result["needs_ecs_update"] is False  # Stopped model shouldn't trigger ECS update
        assert result["current_model_status"] == ModelStatus.UPDATING


def test_update_simple_field():
    """Test the _update_simple_field helper function."""
    model_config = {"streaming": True}
    _update_simple_field(model_config, "streaming", False, "test-model")
    assert model_config["streaming"] is False


def test_update_container_config():
    """Test the _update_container_config helper function."""
    model_config = {"containerConfig": {"environment": {"EXISTING": "value"}}}
    container_config = {
        "environment": {"NEW_VAR": "new_value", "DELETE_ME": "LISA_MARKED_FOR_DELETION"},
    }

    metadata = _update_container_config(model_config, container_config, "test-model")

    # Check environment variables
    assert model_config["containerConfig"]["environment"]["NEW_VAR"] == "new_value"
    assert "DELETE_ME" not in model_config["containerConfig"]["environment"]

    # Check metadata
    assert "env_vars_to_delete" in metadata
    assert "DELETE_ME" in metadata["env_vars_to_delete"]


def test_process_metadata_updates():
    """Test the _process_metadata_updates helper function."""
    model_config = {
        "streaming": True,
        "modelType": "textgen",
        "containerConfig": {"environment": {"EXISTING_VAR": "existing_value"}},
    }
    update_payload = {
        "streaming": False,
        "modelDescription": "Updated description",
        "containerConfig": {"environment": {"NEW_VAR": "value"}},
    }

    has_updates, metadata = _process_metadata_updates(model_config, update_payload, "test-model")

    assert has_updates is True
    assert model_config["streaming"] is False
    assert model_config["modelDescription"] == "Updated description"
    assert model_config["containerConfig"]["environment"]["NEW_VAR"] == "value"


def test_handle_ecs_update(model_table, sample_model, lambda_context):
    """Test ECS update handler."""
    event = {"model_id": "test-model", "container_metadata": {"env_vars_to_delete": ["TO_DELETE"]}}

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_ecs_update(event, lambda_context)

        assert result["new_task_definition_arn"] == "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2"
        assert result["ecs_service_arn"] == "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service"
        assert result["ecs_cluster_arn"] == "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster"
        assert result["remaining_ecs_polls"] == 30

        # Verify ECS client calls
        mock_cfn.describe_stack_resources.assert_called_once_with(StackName="test-stack")
        mock_ecs.describe_services.assert_called_once()
        mock_ecs.describe_task_definition.assert_called_once()
        mock_ecs.register_task_definition.assert_called_once()
        mock_ecs.update_service.assert_called_once()


def test_handle_ecs_update_no_stack_error(model_table, lambda_context):
    """Test ECS update handler when no CloudFormation stack found."""
    # Create model without stack name
    item = {
        "model_id": "no-stack-model",
        "model_status": ModelStatus.IN_SERVICE,
        "model_config": {"containerConfig": {"environment": {"VAR": "value"}}},
    }
    model_table.put_item(Item=item)

    event = {"model_id": "no-stack-model"}

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_ecs_update(event, lambda_context)

        assert "ecs_update_error" in result
        assert "No CloudFormation stack found" in result["ecs_update_error"]


def test_handle_poll_ecs_deployment_completed(lambda_context):
    """Test ECS deployment polling when deployment is completed."""
    event = {
        "model_id": "test-model",
        "ecs_cluster_arn": "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster",
        "ecs_service_arn": "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service",
        "new_task_definition_arn": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2",
        "remaining_ecs_polls": 20,
    }

    result = handle_poll_ecs_deployment(event, lambda_context)

    assert result["should_continue_ecs_polling"] is False
    assert result["remaining_ecs_polls"] == 19


def test_handle_poll_ecs_deployment_in_progress(lambda_context):
    """Test ECS deployment polling when deployment is in progress."""
    # Mock deployment in progress
    mock_ecs.describe_services.return_value = {
        "services": [
            {
                "deployments": [
                    {
                        "status": "PRIMARY",
                        "rolloutState": "IN_PROGRESS",
                        "taskDefinition": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2",
                    }
                ]
            }
        ]
    }

    event = {
        "model_id": "test-model",
        "ecs_cluster_arn": "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster",
        "ecs_service_arn": "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service",
        "new_task_definition_arn": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2",
        "remaining_ecs_polls": 20,
    }

    result = handle_poll_ecs_deployment(event, lambda_context)

    assert result["should_continue_ecs_polling"] is True
    assert result["remaining_ecs_polls"] == 19

    # Reset mock for other tests
    mock_ecs.describe_services.return_value = {
        "services": [
            {
                "taskDefinition": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:1",
                "deployments": [
                    {
                        "status": "PRIMARY",
                        "rolloutState": "COMPLETED",
                        "taskDefinition": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2",
                    }
                ],
            }
        ]
    }


def test_handle_poll_ecs_deployment_timeout(lambda_context):
    """Test ECS deployment polling when polls are exhausted."""
    event = {
        "model_id": "test-model",
        "ecs_cluster_arn": "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster",
        "ecs_service_arn": "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service",
        "new_task_definition_arn": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2",
        "remaining_ecs_polls": 1,
    }

    # Mock deployment still in progress
    mock_ecs.describe_services.return_value = {
        "services": [
            {
                "deployments": [
                    {
                        "status": "PRIMARY",
                        "rolloutState": "IN_PROGRESS",
                        "taskDefinition": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2",
                    }
                ]
            }
        ]
    }

    result = handle_poll_ecs_deployment(event, lambda_context)

    assert result["should_continue_ecs_polling"] is False
    assert "ecs_polling_error" in result
    assert "did not complete within expected time" in result["ecs_polling_error"]


def test_handle_poll_ecs_deployment_with_error(lambda_context):
    """Test ECS deployment polling with previous error."""
    event = {"model_id": "test-model", "ecs_update_error": "Previous ECS update failed"}

    result = handle_poll_ecs_deployment(event, lambda_context)

    assert result["should_continue_ecs_polling"] is False
    assert "ecs_update_error" in result


def test_handle_job_intake_container_config_for_lisa_only_model(model_table, lambda_context):
    """Test container config update fails for models without ASG (LiteLLM-only)."""
    # Create model without ASG but with containerConfig
    item = {
        "model_id": "litellm-only-model",
        "model_status": ModelStatus.IN_SERVICE,
        "model_config": {
            "modelName": "test-model",
            "containerConfig": {"environment": {"EXISTING_VAR": "existing_value"}},
        },
    }
    model_table.put_item(Item=item)

    event = {
        "model_id": "litellm-only-model",
        "update_payload": {"containerConfig": {"environment": {"NEW_VAR": "new_value"}}},
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        # This should not fail because container config updates don't require ASG when model status is IN_SERVICE and no ASG is present
        result = handle_job_intake(event, lambda_context)

        # Instead of raising an error, it should process the metadata update but set needs_ecs_update to False
        assert result["needs_ecs_update"] is False  # No ASG means no ECS update needed
        assert result["current_model_status"] == ModelStatus.UPDATING


def test_handle_job_intake_multiple_metadata_updates(model_table, sample_model, lambda_context):
    """Test updating multiple metadata fields at once."""
    event = {
        "model_id": "test-model",
        "update_payload": {
            "streaming": False,
            "modelType": "embedding",
            "modelDescription": "Updated description",
            "allowedGroups": ["group1", "group2"],
            "features": [{"name": "feature1", "overview": "overview1"}],
        },
    }

    with patch("models.state_machine.update_model.model_table", model_table):
        result = handle_job_intake(event, lambda_context)

        assert result["current_model_status"] == ModelStatus.UPDATING
        assert result["needs_ecs_update"] is False

        # Verify all metadata updates
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        config = item["model_config"]
        assert config["streaming"] is False
        assert config["modelType"] == "embedding"
        assert config["modelDescription"] == "Updated description"
        assert config["allowedGroups"] == ["group1", "group2"]
        assert len(config["features"]) == 1
        assert config["features"][0]["name"] == "feature1"
