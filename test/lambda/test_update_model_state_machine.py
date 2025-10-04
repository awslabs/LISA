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
os.environ["LISA_API_URL_PS_NAME"] = "test-api-url"
os.environ["LITELLM_CONFIG_OBJ"] = '{"litellm_settings": {"drop_params": true}}'

# Create SSM parameter using moto before module imports
with mock_aws():
    ssm_setup = boto3.client("ssm", region_name="us-east-1")
    ssm_setup.put_parameter(Name="test-api-url", Value="https://test-api.example.com", Type="String")

# Create retry config
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

# Patch sys.modules
patch.dict(
    "sys.modules",
    {
        "create_env_variables": MagicMock(),
    },
).start()

# Patch functions
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


# Mock boto3.client
def mock_boto3_client(*args, **kwargs):
    # Support both (service_name, region_name, config) and (service_name)
    service = args[0] if args else kwargs.get("service_name", kwargs.get("service"))
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


# Note: This module needs global boto3.client patch for import-time dependencies
patch("boto3.client", side_effect=mock_boto3_client).start()

from models.domain_objects import ModelStatus

# Import state machine functions
from models.state_machine.update_model import (
    _get_metadata_update_handlers,
    _process_metadata_updates,
    _update_container_config,
    _update_simple_field,
    create_updated_task_definition,
    get_ecs_resources_from_stack,
    handle_ecs_update,
    handle_finish_update,
    handle_job_intake,
    handle_poll_capacity,
    handle_poll_ecs_deployment,
    update_ecs_service,
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


def test_handle_job_intake_comprehensive(model_table, sample_model, stopped_model, litellm_only_model, lambda_context):
    """Comprehensive test covering multiple job intake scenarios."""
    # Reset mocks
    mock_autoscaling.reset_mock()
    mock_litellm_client.reset_mock()

    with patch("models.state_machine.update_model.model_table", model_table):
        # Test 1: Enable stopped model
        event1 = {"model_id": "stopped-model", "update_payload": {"enabled": True}}
        result1 = handle_job_intake(event1, lambda_context)
        assert result1["has_capacity_update"] is True
        assert result1["current_model_status"] == ModelStatus.STARTING

        # Test 2: Disable running model
        mock_autoscaling.reset_mock()
        mock_litellm_client.reset_mock()
        event2 = {"model_id": "test-model", "update_payload": {"enabled": False}}
        result2 = handle_job_intake(event2, lambda_context)
        assert result2["is_disable"] is True
        assert result2["current_model_status"] == ModelStatus.STOPPING
        mock_litellm_client.delete_model.assert_called_once_with(identifier="test-litellm-id")

        # Test 3: Autoscaling with all parameters (cooldown, warmup, capacity)
        # Reset model status back to IN_SERVICE for autoscaling test
        model_table.update_item(
            Key={"model_id": "test-model"},
            UpdateExpression="SET model_status = :ms",
            ExpressionAttributeValues={":ms": ModelStatus.IN_SERVICE},
        )
        mock_autoscaling.reset_mock()
        event3 = {
            "model_id": "test-model",
            "update_payload": {
                "autoScalingInstanceConfig": {
                    "minCapacity": 2,
                    "maxCapacity": 5,
                    "desiredCapacity": 3,
                    "cooldown": 600,
                    "defaultInstanceWarmup": 400,
                }
            },
        }
        result3 = handle_job_intake(event3, lambda_context)
        assert result3["current_model_status"] == ModelStatus.UPDATING
        # Verify autoscaling was called since the model is IN_SERVICE
        assert mock_autoscaling.update_auto_scaling_group.called
        call_args = mock_autoscaling.update_auto_scaling_group.call_args
        assert call_args[1]["MinSize"] == 2
        assert call_args[1]["MaxSize"] == 5
        assert call_args[1]["DefaultCooldown"] == 600
        assert call_args[1]["DefaultInstanceWarmup"] == 400

        # Test 4: Container config with all features (env vars, health check, shared memory, deletion)
        # Reset model status to IN_SERVICE for ECS update test
        model_table.update_item(
            Key={"model_id": "test-model"},
            UpdateExpression="SET model_status = :ms",
            ExpressionAttributeValues={":ms": ModelStatus.IN_SERVICE},
        )
        event4 = {
            "model_id": "test-model",
            "update_payload": {
                "containerConfig": {
                    "environment": {
                        "NEW_VAR": "new_value",
                        "TO_UPDATE": "LISA_MARKED_FOR_DELETION",  # Test deletion
                    },
                    "sharedMemorySize": 2048,
                    "healthCheckCommand": ["CMD-SHELL", "curl -f http://localhost:8080/health"],
                    "healthCheckInterval": 60,
                    "healthCheckTimeout": 10,
                    "healthCheckStartPeriod": 120,
                    "healthCheckRetries": 5,
                }
            },
        }
        result4 = handle_job_intake(event4, lambda_context)
        assert result4["needs_ecs_update"] is True
        assert "container_metadata" in result4
        assert "TO_UPDATE" in result4["container_metadata"]["env_vars_to_delete"]

        # Test 5: Multiple metadata updates
        event5 = {
            "model_id": "test-model",
            "update_payload": {
                "streaming": False,
                "modelType": "embedding",
                "modelDescription": "Updated description",
                "allowedGroups": ["group1", "group2"],
                "features": [{"name": "feature1", "overview": "overview1"}],
            },
        }
        result5 = handle_job_intake(event5, lambda_context)
        assert result5["current_model_status"] == ModelStatus.UPDATING
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_config"]["streaming"] is False
        assert item["model_config"]["modelType"] == "embedding"


def test_handle_job_intake_errors(model_table, litellm_only_model, sample_model, lambda_context):
    """Test error conditions in job intake."""
    with patch("models.state_machine.update_model.model_table", model_table):
        # Test 1: Model not found
        with pytest.raises(RuntimeError, match="Requested model 'nonexistent-model' was not found"):
            handle_job_intake({"model_id": "nonexistent-model", "update_payload": {"enabled": True}}, lambda_context)

        # Test 2: LiteLLM-only model activation error
        with pytest.raises(
            RuntimeError, match="Cannot request AutoScaling updates to models that are not hosted by LISA"
        ):
            handle_job_intake({"model_id": "litellm-model", "update_payload": {"enabled": False}}, lambda_context)

        # Test 3: Concurrent activation and autoscaling error
        with pytest.raises(
            RuntimeError, match="Cannot request AutoScaling updates at the same time as an enable or disable operation"
        ):
            handle_job_intake(
                {
                    "model_id": "test-model",
                    "update_payload": {"enabled": False, "autoScalingInstanceConfig": {"minCapacity": 2}},
                },
                lambda_context,
            )


def test_handle_poll_capacity_scenarios(lambda_context):
    """Test all capacity polling scenarios."""
    # Test 1: Healthy instances
    result1 = handle_poll_capacity(
        {"model_id": "test-model", "asg_name": "test-asg", "remaining_capacity_polls": 20}, lambda_context
    )
    assert result1["should_continue_capacity_polling"] is False
    assert result1["remaining_capacity_polls"] == 19

    # Test 2: Unhealthy instances (continue polling)
    mock_autoscaling.describe_auto_scaling_groups.return_value = {
        "AutoScalingGroups": [
            {"DesiredCapacity": 2, "Instances": [{"HealthStatus": "Healthy"}, {"HealthStatus": "Unhealthy"}]}
        ]
    }
    result2 = handle_poll_capacity(
        {"model_id": "test-model", "asg_name": "test-asg", "remaining_capacity_polls": 20}, lambda_context
    )
    assert result2["should_continue_capacity_polling"] is True

    # Test 3: Max polls exceeded (timeout)
    result3 = handle_poll_capacity(
        {"model_id": "test-model", "asg_name": "test-asg", "remaining_capacity_polls": 1}, lambda_context
    )
    assert result3["should_continue_capacity_polling"] is False
    assert "polling_error" in result3

    # Reset mock
    mock_autoscaling.describe_auto_scaling_groups.return_value = {
        "AutoScalingGroups": [
            {"DesiredCapacity": 2, "Instances": [{"HealthStatus": "Healthy"}, {"HealthStatus": "Healthy"}]}
        ]
    }


def test_handle_finish_update_scenarios(model_table, lambda_context):
    """Test all finish update scenarios."""
    with patch("models.state_machine.update_model.model_table", model_table):
        # Test 1: Successful enable
        item1 = {
            "model_id": "enable-model",
            "model_status": ModelStatus.STARTING,
            "auto_scaling_group": "test-asg",
            "model_url": "https://test-model.example.com/v1",
            "model_config": {"modelName": "test-model-name"},
        }
        model_table.put_item(Item=item1)
        result1 = handle_finish_update(
            {
                "model_id": "enable-model",
                "asg_name": "test-asg",
                "has_capacity_update": True,
                "is_disable": False,
                "initial_model_status": ModelStatus.STOPPED,
            },
            lambda_context,
        )
        assert result1["current_model_status"] == ModelStatus.IN_SERVICE
        assert result1["litellm_id"] == "test-litellm-id"

        # Test 2: Successful disable
        item2 = {
            "model_id": "disable-model",
            "model_status": ModelStatus.STOPPING,
            "auto_scaling_group": "test-asg",
            "model_url": "https://test-model.example.com/v1",
            "model_config": {"modelName": "test-model-name"},
        }
        model_table.put_item(Item=item2)
        result2 = handle_finish_update(
            {
                "model_id": "disable-model",
                "asg_name": "test-asg",
                "has_capacity_update": False,
                "is_disable": True,
                "initial_model_status": ModelStatus.IN_SERVICE,
            },
            lambda_context,
        )
        assert result2["current_model_status"] == ModelStatus.STOPPED

        # Test 3: Metadata-only update
        item3 = {
            "model_id": "metadata-model",
            "model_status": ModelStatus.UPDATING,
            "auto_scaling_group": "test-asg",
            "model_url": "https://test-model.example.com/v1",
            "model_config": {"modelName": "test-model-name"},
        }
        model_table.put_item(Item=item3)
        result3 = handle_finish_update(
            {
                "model_id": "metadata-model",
                "asg_name": "test-asg",
                "has_capacity_update": False,
                "is_disable": False,
                "initial_model_status": ModelStatus.IN_SERVICE,
            },
            lambda_context,
        )
        assert result3["current_model_status"] == ModelStatus.IN_SERVICE

        # Test 4: Polling error handling
        mock_autoscaling.reset_mock()
        item4 = {
            "model_id": "error-model",
            "model_status": ModelStatus.STARTING,
            "auto_scaling_group": "test-asg",
            "model_url": "https://test-model.example.com/v1",
            "model_config": {"modelName": "test-model-name"},
        }
        model_table.put_item(Item=item4)
        result4 = handle_finish_update(
            {
                "model_id": "error-model",
                "asg_name": "test-asg",
                "has_capacity_update": True,
                "is_disable": False,
                "polling_error": "Model did not start in time",
                "initial_model_status": ModelStatus.STOPPED,
            },
            lambda_context,
        )
        assert result4["current_model_status"] == ModelStatus.STOPPED
        # Verify ASG scaled down on error
        call_args = mock_autoscaling.update_auto_scaling_group.call_args
        assert call_args[1]["MinSize"] == 0


def test_ecs_update_and_polling(model_table, sample_model, lambda_context):
    """Test ECS update and deployment polling."""
    with patch("models.state_machine.update_model.model_table", model_table):
        # Test 1: ECS update success
        result1 = handle_ecs_update(
            {"model_id": "test-model", "container_metadata": {"env_vars_to_delete": ["TO_DELETE"]}}, lambda_context
        )
        assert (
            result1["new_task_definition_arn"] == "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2"
        )
        assert result1["ecs_service_arn"] == "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service"

        # Test 2: ECS update error (no stack)
        item = {
            "model_id": "no-stack-model",
            "model_status": ModelStatus.IN_SERVICE,
            "model_config": {"containerConfig": {"environment": {"VAR": "value"}}},
        }
        model_table.put_item(Item=item)
        result2 = handle_ecs_update({"model_id": "no-stack-model"}, lambda_context)
        assert "ecs_update_error" in result2

        # Test 3: ECS deployment completed
        event = {
            "model_id": "test-model",
            "ecs_cluster_arn": "cluster",
            "ecs_service_arn": "service",
            "new_task_definition_arn": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2",
            "remaining_ecs_polls": 20,
        }
        result3 = handle_poll_ecs_deployment(event, lambda_context)
        assert result3["should_continue_ecs_polling"] is False

        # Test 4: ECS deployment in progress
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
        result4 = handle_poll_ecs_deployment(event, lambda_context)
        assert result4["should_continue_ecs_polling"] is True

        # Test 5: ECS deployment timeout
        result5 = handle_poll_ecs_deployment({**event, "remaining_ecs_polls": 1}, lambda_context)
        assert result5["should_continue_ecs_polling"] is False
        assert "ecs_polling_error" in result5

        # Reset mock
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


def test_helper_functions():
    """Test helper functions for maximum coverage."""
    # Test _update_simple_field
    model_config = {"streaming": True}
    _update_simple_field(model_config, "streaming", False, "test-model")
    assert model_config["streaming"] is False

    # Test _update_container_config with all features
    model_config = {"containerConfig": {"environment": {"EXISTING": "value"}}}
    container_config = {
        "environment": {"NEW_VAR": "new_value", "DELETE_ME": "LISA_MARKED_FOR_DELETION"},
        "sharedMemorySize": 1024,
        "healthCheckCommand": ["CMD-SHELL", "curl -f http://localhost:8080/health"],
        "healthCheckInterval": 30,
        "healthCheckTimeout": 5,
        "healthCheckStartPeriod": 60,
        "healthCheckRetries": 3,
    }
    metadata = _update_container_config(model_config, container_config, "test-model")
    assert model_config["containerConfig"]["environment"]["NEW_VAR"] == "new_value"
    assert "DELETE_ME" not in model_config["containerConfig"]["environment"]
    assert model_config["containerConfig"]["sharedMemorySize"] == 1024
    assert metadata["env_vars_to_delete"] == ["DELETE_ME"]

    # Test _process_metadata_updates
    model_config = {"streaming": True, "modelType": "textgen", "containerConfig": {"environment": {"VAR": "value"}}}
    update_payload = {
        "streaming": False,
        "modelDescription": "Updated",
        "containerConfig": {"environment": {"NEW": "value"}},
    }
    has_updates, metadata = _process_metadata_updates(model_config, update_payload, "test-model")
    assert has_updates is True
    assert model_config["streaming"] is False
    assert model_config["modelDescription"] == "Updated"

    # Test _get_metadata_update_handlers
    handlers = _get_metadata_update_handlers(model_config, "test-model")
    expected_handlers = ["modelType", "streaming", "modelDescription", "allowedGroups", "features", "containerConfig"]
    for handler_name in expected_handlers:
        assert handler_name in handlers
        assert callable(handlers[handler_name])

    # Test get_ecs_resources_from_stack
    service_arn, cluster_arn, task_def_arn = get_ecs_resources_from_stack("test-stack")
    assert service_arn == "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service"
    assert cluster_arn == "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster"
    assert task_def_arn == "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:1"

    # Test get_ecs_resources_from_stack error case
    mock_cfn.describe_stack_resources.return_value = {
        "StackResources": [{"ResourceType": "AWS::ECS::Cluster", "PhysicalResourceId": "cluster"}]
    }
    with pytest.raises(RuntimeError, match="Failed to get ECS resources from CloudFormation stack"):
        get_ecs_resources_from_stack("test-stack")

    # Reset mock
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

    # Test create_updated_task_definition
    task_def_arn = "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:1"
    updated_env_vars = {"NEW_VAR": "new_value", "UPDATED_VAR": "updated_value"}
    env_vars_to_delete = ["TO_DELETE"]
    updated_container_config = {
        "sharedMemorySize": 1024,
        "healthCheckConfig": {
            "command": ["CMD-SHELL", "health"],
            "interval": 30,
            "timeout": 5,
            "startPeriod": 60,
            "retries": 3,
        },
    }
    new_task_def_arn = create_updated_task_definition(
        task_def_arn, updated_env_vars, env_vars_to_delete, updated_container_config
    )
    assert new_task_def_arn == "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2"

    # Test update_ecs_service
    update_ecs_service("cluster-arn", "service-arn", "task-def-arn")
    mock_ecs.update_service.assert_called_with(
        cluster="cluster-arn", service="service-arn", taskDefinition="task-def-arn"
    )


def test_edge_cases_and_json_error(model_table, lambda_context):
    """Test edge cases and JSON decoding error for complete coverage."""
    with patch("models.state_machine.update_model.model_table", model_table):
        # Test JSON decode error in handle_finish_update
        item = {
            "model_id": "json-error-model",
            "model_status": ModelStatus.STARTING,
            "auto_scaling_group": "test-asg",
            "model_url": "https://test-model.example.com/v1",
            "model_config": {"modelName": "test-model-name"},
        }
        model_table.put_item(Item=item)

        with patch("os.environ.get") as mock_env:
            mock_env.return_value = "invalid-json"
            result = handle_finish_update(
                {
                    "model_id": "json-error-model",
                    "asg_name": "test-asg",
                    "has_capacity_update": True,
                    "is_disable": False,
                    "initial_model_status": ModelStatus.STOPPED,
                },
                lambda_context,
            )
            assert result["litellm_id"] == "test-litellm-id"

        # Test ECS deployment with previous error
        result_with_error = handle_poll_ecs_deployment(
            {"model_id": "test-model", "ecs_update_error": "Previous error"}, lambda_context
        )
        assert result_with_error["should_continue_ecs_polling"] is False
        assert "ecs_update_error" in result_with_error

        # Test container config on LiteLLM-only model (should not fail but not trigger ECS update)
        litellm_item = {
            "model_id": "litellm-container-model",
            "model_status": ModelStatus.IN_SERVICE,
            "model_config": {
                "modelName": "test-model",
                "containerConfig": {"environment": {"EXISTING_VAR": "existing_value"}},
            },
        }
        model_table.put_item(Item=litellm_item)
        result_litellm = handle_job_intake(
            {
                "model_id": "litellm-container-model",
                "update_payload": {"containerConfig": {"environment": {"NEW_VAR": "new_value"}}},
            },
            lambda_context,
        )
        assert result_litellm["needs_ecs_update"] is False
