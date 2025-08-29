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

"""Unit tests for delete_model state machine functions."""

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
os.environ["MANAGEMENT_KEY_NAME"] = "test-management-key"

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")

# Create mock modules
mock_common = MagicMock()
mock_common.get_cert_path.return_value = None
mock_common.get_rest_api_container_endpoint.return_value = "https://test-api.example.com"
mock_common.retry_config = retry_config

# Create mock LiteLLMClient
mock_litellm_client = MagicMock()
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
mock_cfn = MagicMock()
mock_iam = MagicMock()
mock_secrets = MagicMock()

mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "DELETE_COMPLETE"}]}
mock_cfn.delete_stack.return_value = {}
mock_secrets.get_secret_value.return_value = {"SecretString": "test-secret"}


# Create comprehensive mock for boto3.client to handle all possible service requests
def mock_boto3_client(*args, **kwargs):
    # Support both (service_name, region_name, config) and (service_name)
    service = args[0] if args else kwargs.get("service_name", kwargs.get("service"))
    if service == "cloudformation":
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

from models.domain_objects import ModelStatus

# Now import the state machine functions
from models.state_machine.delete_model import (
    handle_delete_from_ddb,
    handle_delete_from_litellm,
    handle_delete_stack,
    handle_monitor_delete_stack,
    handle_set_model_to_deleting,
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
        "cloudformation_stack_arn": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id",
        "litellm_id": "test-litellm-id",
        "model_config": {
            "modelId": "test-model",
            "modelName": "test-model-name",
            "modelType": "textgen",
            "streaming": True,
        },
    }
    model_table.put_item(Item=item)
    return item


@pytest.fixture
def sample_event():
    """Sample event for delete state machine functions."""
    return {"modelId": "test-model"}


def test_handle_set_model_to_deleting_success(model_table, sample_model, sample_event, lambda_context):
    """Test setting model to deleting status successfully."""
    with patch("models.state_machine.delete_model.ddb_table", model_table):
        result = handle_set_model_to_deleting(sample_event, lambda_context)

        assert result["cloudformation_stack_arn"] == sample_model["cloudformation_stack_arn"]
        assert result["litellm_id"] == sample_model["litellm_id"]
        assert result["modelId"] == "test-model"

        # Verify DDB update
        item = model_table.get_item(Key={"model_id": "test-model"})["Item"]
        assert item["model_status"] == ModelStatus.DELETING


def test_handle_set_model_to_deleting_model_not_found(model_table, sample_event, lambda_context):
    """Test setting model to deleting status when model doesn't exist."""
    with patch("models.state_machine.delete_model.ddb_table", model_table):
        with pytest.raises(RuntimeError, match="Requested model 'test-model' was not found"):
            handle_set_model_to_deleting(sample_event, lambda_context)


def test_handle_set_model_to_deleting_model_without_stack(model_table, sample_event, lambda_context):
    """Test setting model to deleting status for model without CloudFormation stack."""
    # Create model without stack info
    item = {
        "model_id": "test-model",
        "model_status": ModelStatus.IN_SERVICE,
        "litellm_id": "test-litellm-id",
        "model_config": {"modelId": "test-model", "modelName": "test-model-name"},
    }
    model_table.put_item(Item=item)

    with patch("models.state_machine.delete_model.ddb_table", model_table):
        result = handle_set_model_to_deleting(sample_event, lambda_context)

        assert result["cloudformation_stack_arn"] is None
        assert result["litellm_id"] == "test-litellm-id"
        assert result["modelId"] == "test-model"


def test_handle_delete_from_litellm_with_id(sample_event, lambda_context):
    """Test deleting model from LiteLLM when litellm_id exists."""
    event = deepcopy(sample_event)
    event["litellm_id"] = "test-litellm-id"

    result = handle_delete_from_litellm(event, lambda_context)

    assert result == event
    mock_litellm_client.delete_model.assert_called_once_with(identifier="test-litellm-id")


def test_handle_delete_from_litellm_without_id(sample_event, lambda_context):
    """Test deleting model from LiteLLM when litellm_id is None."""
    # Reset mock call count for this test
    mock_litellm_client.reset_mock()

    event = deepcopy(sample_event)
    event["litellm_id"] = None

    result = handle_delete_from_litellm(event, lambda_context)

    assert result == event
    # LiteLLM client should not be called when ID is None
    mock_litellm_client.delete_model.assert_not_called()


def test_handle_delete_from_litellm_empty_id(sample_event, lambda_context):
    """Test deleting model from LiteLLM when litellm_id is empty string."""
    # Reset mock call count for this test
    mock_litellm_client.reset_mock()

    event = deepcopy(sample_event)
    event["litellm_id"] = ""

    result = handle_delete_from_litellm(event, lambda_context)

    assert result == event
    # LiteLLM client should not be called when ID is empty
    mock_litellm_client.delete_model.assert_not_called()


def test_handle_delete_stack(sample_event, lambda_context):
    """Test initiating CloudFormation stack deletion."""
    event = deepcopy(sample_event)
    event["cloudformation_stack_arn"] = "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id"

    result = handle_delete_stack(event, lambda_context)

    assert result == event
    mock_cfn.delete_stack.assert_called_once()
    call_args = mock_cfn.delete_stack.call_args
    assert call_args[1]["StackName"] == event["cloudformation_stack_arn"]
    assert "ClientRequestToken" in call_args[1]


def test_handle_monitor_delete_stack_complete(sample_event, lambda_context):
    """Test monitoring stack deletion when complete."""
    event = deepcopy(sample_event)
    event["cloudformation_stack_arn"] = "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id"

    # Mock stack deletion complete
    mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "DELETE_COMPLETE"}]}

    result = handle_monitor_delete_stack(event, lambda_context)

    assert result["continue_polling"] is False
    assert result["modelId"] == "test-model"


def test_handle_monitor_delete_stack_in_progress(sample_event, lambda_context):
    """Test monitoring stack deletion when in progress."""
    event = deepcopy(sample_event)
    event["cloudformation_stack_arn"] = "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id"

    # Mock stack deletion in progress
    mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "DELETE_IN_PROGRESS"}]}

    result = handle_monitor_delete_stack(event, lambda_context)

    assert result["continue_polling"] is True
    assert result["modelId"] == "test-model"


def test_handle_monitor_delete_stack_unexpected_state(sample_event, lambda_context):
    """Test monitoring stack deletion with unexpected terminal state."""
    event = deepcopy(sample_event)
    event["cloudformation_stack_arn"] = "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id"

    # Mock unexpected terminal state
    mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "CREATE_COMPLETE"}]}

    with pytest.raises(RuntimeError, match="Stack entered unexpected terminal state 'CREATE_COMPLETE'"):
        handle_monitor_delete_stack(event, lambda_context)


def test_handle_monitor_delete_stack_failed_state(sample_event, lambda_context):
    """Test monitoring stack deletion with failed terminal state."""
    event = deepcopy(sample_event)
    event["cloudformation_stack_arn"] = "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id"

    # Mock failed state
    mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "DELETE_FAILED"}]}

    with pytest.raises(RuntimeError, match="Stack entered unexpected terminal state 'DELETE_FAILED'"):
        handle_monitor_delete_stack(event, lambda_context)


def test_handle_delete_from_ddb(model_table, sample_model, sample_event, lambda_context):
    """Test deleting model from DynamoDB."""
    with patch("models.state_machine.delete_model.ddb_table", model_table):
        result = handle_delete_from_ddb(sample_event, lambda_context)

        assert result == sample_event

        # Verify model is deleted from DDB
        response = model_table.get_item(Key={"model_id": "test-model"})
        assert "Item" not in response


def test_handle_delete_from_ddb_nonexistent_model(model_table, sample_event, lambda_context):
    """Test deleting nonexistent model from DynamoDB."""
    # Don't create the model item
    with patch("models.state_machine.delete_model.ddb_table", model_table):
        # Should not raise exception even if model doesn't exist
        result = handle_delete_from_ddb(sample_event, lambda_context)

        assert result == sample_event


def test_handle_set_model_to_deleting_model_without_litellm_id(model_table, sample_event, lambda_context):
    """Test setting model to deleting status for model without LiteLLM ID."""
    # Create model without litellm_id
    item = {
        "model_id": "test-model",
        "model_status": ModelStatus.IN_SERVICE,
        "cloudformation_stack_arn": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id",
        "model_config": {"modelId": "test-model", "modelName": "test-model-name"},
    }
    model_table.put_item(Item=item)

    with patch("models.state_machine.delete_model.ddb_table", model_table):
        result = handle_set_model_to_deleting(sample_event, lambda_context)

        assert result["cloudformation_stack_arn"] == item["cloudformation_stack_arn"]
        assert result["litellm_id"] is None
        assert result["modelId"] == "test-model"


def test_end_to_end_delete_workflow(model_table, sample_model, sample_event, lambda_context):
    """Test complete delete workflow end-to-end."""
    with patch("models.state_machine.delete_model.ddb_table", model_table):
        # Step 1: Set model to deleting
        event1 = handle_set_model_to_deleting(sample_event, lambda_context)
        assert event1["litellm_id"] == "test-litellm-id"
        assert event1["cloudformation_stack_arn"] is not None

        # Step 2: Delete from LiteLLM
        event2 = handle_delete_from_litellm(event1, lambda_context)
        assert event2 == event1

        # Step 3: Delete stack
        event3 = handle_delete_stack(event2, lambda_context)
        assert event3 == event2

        # Step 4: Monitor stack deletion (complete)
        mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "DELETE_COMPLETE"}]}
        event4 = handle_monitor_delete_stack(event3, lambda_context)
        assert event4["continue_polling"] is False

        # Step 5: Delete from DDB
        event5 = handle_delete_from_ddb(event4, lambda_context)
        assert event5 == event4

        # Verify model is deleted
        response = model_table.get_item(Key={"model_id": "test-model"})
        assert "Item" not in response


def test_handle_monitor_delete_stack_rollback_state(sample_event, lambda_context):
    """Test monitoring stack deletion with rollback state."""
    event = deepcopy(sample_event)
    event["cloudformation_stack_arn"] = "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id"

    # Mock rollback state
    mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "ROLLBACK_COMPLETE"}]}

    with pytest.raises(RuntimeError, match="Stack entered unexpected terminal state 'ROLLBACK_COMPLETE'"):
        handle_monitor_delete_stack(event, lambda_context)


def test_handle_monitor_delete_stack_update_state(sample_event, lambda_context):
    """Test monitoring stack deletion with update state."""
    event = deepcopy(sample_event)
    event["cloudformation_stack_arn"] = "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id"

    # Mock update state (should continue polling)
    mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "UPDATE_ROLLBACK_IN_PROGRESS"}]}

    result = handle_monitor_delete_stack(event, lambda_context)

    assert result["continue_polling"] is True


def test_handle_delete_from_litellm_litellm_error(sample_event, lambda_context):
    """Test handling LiteLLM deletion error."""
    event = deepcopy(sample_event)
    event["litellm_id"] = "test-litellm-id"

    # Mock LiteLLM client to raise exception
    mock_litellm_client.delete_model.side_effect = Exception("LiteLLM error")

    # The function should still complete and propagate the exception
    with pytest.raises(Exception, match="LiteLLM error"):
        handle_delete_from_litellm(event, lambda_context)


def test_handle_delete_stack_cloudformation_error(sample_event, lambda_context):
    """Test handling CloudFormation deletion error."""
    event = deepcopy(sample_event)
    event["cloudformation_stack_arn"] = "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id"

    # Mock CloudFormation client to raise exception
    mock_cfn.delete_stack.side_effect = Exception("CloudFormation error")

    # The function should propagate the exception
    with pytest.raises(Exception, match="CloudFormation error"):
        handle_delete_stack(event, lambda_context)


def test_handle_monitor_delete_stack_cloudformation_error(sample_event, lambda_context):
    """Test handling CloudFormation monitoring error."""
    event = deepcopy(sample_event)
    event["cloudformation_stack_arn"] = "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/test-id"

    # Mock CloudFormation client to raise exception
    mock_cfn.describe_stacks.side_effect = Exception("CloudFormation describe error")

    # The function should propagate the exception
    with pytest.raises(Exception, match="CloudFormation describe error"):
        handle_monitor_delete_stack(event, lambda_context)
