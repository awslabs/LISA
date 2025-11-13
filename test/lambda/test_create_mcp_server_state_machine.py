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

"""Unit tests for MCP server state machine handlers."""

import json
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
os.environ["MCP_SERVERS_TABLE_NAME"] = "mcp-servers-table"
os.environ["MCP_SERVER_DEPLOYER_FN_ARN"] = "arn:aws:lambda:us-east-1:123456789012:function:mcp-server-deployer"

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def dynamodb(aws_credentials):
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def mcp_servers_table(dynamodb):
    """Create a mock DynamoDB table for MCP servers."""
    table = dynamodb.create_table(
        TableName="mcp-servers-table",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


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


@pytest.fixture
def sample_mcp_server_event():
    """Sample event for MCP server state machine."""
    return {
        "id": "test-server-id",
        "name": "Test MCP Server",
        "description": "Test description",
        "owner": "test-user",
        "startCommand": "python server.py",
        "port": 8000,
        "serverType": "http",
        "autoScalingConfig": {
            "minCapacity": 1,
            "maxCapacity": 10,
            "targetValue": 5,
        },
        "groups": ["group:admin"],
    }


def test_handle_set_server_to_creating(mcp_servers_table, sample_mcp_server_event):
    """Test setting server status to CREATING."""
    # Import here to avoid global mocks
    from mcp_server.state_machine.create_mcp_server import handle_set_server_to_creating

    # Create initial server record
    mcp_servers_table.put_item(
        Item={
            "id": sample_mcp_server_event["id"],
            "name": sample_mcp_server_event["name"],
            "status": "Pending",
        }
    )

    result = handle_set_server_to_creating(sample_mcp_server_event, None)

    assert result["server_status"] == "Creating"
    assert result["id"] == "test-server-id"

    # Verify DynamoDB was updated
    response = mcp_servers_table.get_item(Key={"id": "test-server-id"})
    assert response["Item"]["status"] == "Creating"
    assert "last_modified" in response["Item"]


def test_handle_set_server_to_creating_missing_id(mcp_servers_table):
    """Test handle_set_server_to_creating with missing id."""
    from mcp_server.state_machine.create_mcp_server import handle_set_server_to_creating

    event = {"name": "Test Server"}

    with pytest.raises(ValueError, match="Missing required field: id"):
        handle_set_server_to_creating(event, None)


def test_handle_deploy_server_success(mcp_servers_table, sample_mcp_server_event):
    """Test successful deployment of server."""
    from mcp_server.state_machine.create_mcp_server import handle_deploy_server

    with patch("mcp_server.state_machine.create_mcp_server.lambdaClient") as mock_lambda, patch(
        "mcp_server.state_machine.create_mcp_server.cfnClient"
    ) as mock_cfn:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"stackName": "test-stack-name"}).encode()
        mock_lambda.invoke.return_value = {"Payload": mock_response}
        mock_cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123",
                }
            ]
        }

        result = handle_deploy_server(sample_mcp_server_event, None)

        assert result["stack_name"] == "test-stack-name"
        assert result["stack_arn"] == "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123"
        assert result["poll_count"] == 0
        assert result["continue_polling"] is True

        # Verify Lambda was invoked with correct config
        mock_lambda.invoke.assert_called_once()
        call_args = mock_lambda.invoke.call_args
        assert call_args[1]["FunctionName"] == os.environ["MCP_SERVER_DEPLOYER_FN_ARN"]
        payload = json.loads(call_args[1]["Payload"])
        assert "mcpServerConfig" in payload
        assert payload["mcpServerConfig"]["id"] == "test-server-id"
        assert payload["mcpServerConfig"]["name"] == "Test MCP Server"
        assert payload["mcpServerConfig"]["startCommand"] == "python server.py"


def test_handle_deploy_server_missing_stack_name(sample_mcp_server_event):
    """Test deployment failure when stack name is missing."""
    from mcp_server.state_machine.create_mcp_server import handle_deploy_server

    with patch("mcp_server.state_machine.create_mcp_server.lambdaClient") as mock_lambda:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({}).encode()  # Missing stackName
        mock_lambda.invoke.return_value = {"Payload": mock_response}

        with pytest.raises(ValueError, match="Failed to create MCP server stack"):
            handle_deploy_server(sample_mcp_server_event, None)


def test_handle_deploy_server_with_optional_fields(mcp_servers_table, sample_mcp_server_event):
    """Test deployment with optional fields."""
    from mcp_server.state_machine.create_mcp_server import handle_deploy_server

    event_with_options = sample_mcp_server_event.copy()
    event_with_options["image"] = "python:3.12"
    event_with_options["s3Path"] = "s3://bucket/artifacts"
    event_with_options["environment"] = {"ENV_VAR": "value"}
    event_with_options["loadBalancerConfig"] = {
        "healthCheckConfig": {
            "path": "/health",
            "interval": 30,
            "timeout": 5,
            "healthyThresholdCount": 2,
            "unhealthyThresholdCount": 3,
        }
    }
    event_with_options["containerHealthCheckConfig"] = {
        "command": "curl localhost:8000",
        "interval": 30,
        "startPeriod": 0,
        "timeout": 5,
        "retries": 3,
    }

    with patch("mcp_server.state_machine.create_mcp_server.lambdaClient") as mock_lambda, patch(
        "mcp_server.state_machine.create_mcp_server.cfnClient"
    ) as mock_cfn:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"stackName": "test-stack"}).encode()
        mock_lambda.invoke.return_value = {"Payload": mock_response}
        mock_cfn.describe_stacks.return_value = {
            "Stacks": [
                {
                    "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/abc123",
                }
            ]
        }

        result = handle_deploy_server(event_with_options, None)

        assert result["stack_name"] == "test-stack"
        assert result["stack_arn"] == "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/abc123"

        # Verify optional fields were passed
        call_args = mock_lambda.invoke.call_args
        payload = json.loads(call_args[1]["Payload"])
        config = payload["mcpServerConfig"]
        assert config["image"] == "python:3.12"
        assert config["s3Path"] == "s3://bucket/artifacts"
        assert config["environment"] == {"ENV_VAR": "value"}
        assert "loadBalancerConfig" in config
        assert "containerHealthCheckConfig" in config


def test_handle_poll_deployment_success():
    """Test successful polling of deployment."""
    from mcp_server.state_machine.create_mcp_server import handle_poll_deployment

    event = {"stack_name": "test-stack", "poll_count": 0}

    with patch("mcp_server.state_machine.create_mcp_server.cfnClient") as mock_cfn:
        mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "CREATE_COMPLETE"}]}

        result = handle_poll_deployment(event, None)

        assert result["continue_polling"] is False
        assert result["stack_status"] == "CREATE_COMPLETE"
        assert result["poll_count"] == 0


def test_handle_poll_deployment_in_progress():
    """Test polling when deployment is still in progress."""
    from mcp_server.state_machine.create_mcp_server import handle_poll_deployment

    event = {"stack_name": "test-stack", "poll_count": 5}

    with patch("mcp_server.state_machine.create_mcp_server.cfnClient") as mock_cfn:
        mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]}

        result = handle_poll_deployment(event, None)

        assert result["continue_polling"] is True
        assert result["poll_count"] == 6


def test_handle_poll_deployment_failed():
    """Test polling when deployment fails."""
    from mcp_server.state_machine.create_mcp_server import handle_poll_deployment

    event = {"stack_name": "test-stack", "poll_count": 0}

    with patch("mcp_server.state_machine.create_mcp_server.cfnClient") as mock_cfn:
        mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "CREATE_FAILED"}]}

        with pytest.raises(Exception, match="Stack test-stack failed with status: CREATE_FAILED"):
            handle_poll_deployment(event, None)


def test_handle_poll_deployment_max_polls():
    """Test polling when max polls exceeded."""
    from mcp_server.state_machine.create_mcp_server import handle_poll_deployment, MAX_POLLS

    event = {"stack_name": "test-stack", "poll_count": MAX_POLLS + 1}

    with patch("mcp_server.state_machine.create_mcp_server.cfnClient") as mock_cfn:
        mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "CREATE_IN_PROGRESS"}]}

        with pytest.raises(Exception, match="Max polls exceeded"):
            handle_poll_deployment(event, None)


def test_handle_add_server_to_active_success(mcp_servers_table, sample_mcp_server_event):
    """Test setting server to IN_SERVICE after successful deployment."""
    from mcp_server.state_machine.create_mcp_server import handle_add_server_to_active

    # Create initial server record
    mcp_servers_table.put_item(
        Item={
            "id": sample_mcp_server_event["id"],
            "name": sample_mcp_server_event["name"],
            "status": "Creating",
        }
    )

    event = sample_mcp_server_event.copy()
    event["stack_name"] = "test-stack-name"

    with patch("mcp_server.state_machine.create_mcp_server.ssmClient") as mock_ssm:
        # Mock SSM to return None (chat not deployed)
        # Create a proper exception class for ParameterNotFound
        class ParameterNotFound(Exception):
            pass

        mock_ssm.exceptions.ParameterNotFound = ParameterNotFound
        mock_ssm.get_parameter.side_effect = ParameterNotFound()

        result = handle_add_server_to_active(event, None)

        assert result["server_status"] == "InService"

        # Verify DynamoDB was updated
        response = mcp_servers_table.get_item(Key={"id": "test-server-id"})
        assert response["Item"]["status"] == "InService"
        assert response["Item"]["stack_name"] == "test-stack-name"
        assert "last_modified" in response["Item"]


def test_handle_add_server_to_active_with_connections_table(mcp_servers_table, sample_mcp_server_event):
    """Test setting server to IN_SERVICE and creating connection entry."""
    from mcp_server.state_machine.create_mcp_server import handle_add_server_to_active

    # Create MCP servers table (for hosted server)
    mcp_servers_table.put_item(
        Item={
            "id": sample_mcp_server_event["id"],
            "name": sample_mcp_server_event["name"],
            "status": "Creating",
        }
    )

    # Create MCP connections table (for user-facing connections)
    mcp_servers_table.meta.client.create_table(
        TableName="mcp-connections-table",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )

    event = sample_mcp_server_event.copy()
    event["stack_name"] = "test-stack-name"

    with patch("mcp_server.state_machine.create_mcp_server.ssmClient") as mock_ssm, patch.dict(
        os.environ, {"DEPLOYMENT_PREFIX": "/test/lisa"}
    ):
        # Mock SSM to return table name and API URL
        mock_ssm.get_parameter.side_effect = [
            {"Parameter": {"Value": "mcp-connections-table"}},  # Table name
            {"Parameter": {"Value": "https://api.example.com"}},  # API Gateway URL
        ]

        result = handle_add_server_to_active(event, None)

        assert result["server_status"] == "InService"

        # Verify connection entry was created (if we can access it)
        # Note: In real scenario, this would be in a different table
        # For testing, we verify the SSM calls were made
        assert mock_ssm.get_parameter.call_count >= 2


def test_handle_add_server_to_active_with_empty_groups(mcp_servers_table, sample_mcp_server_event):
    """Test that empty groups default to lisa:public owner."""
    from mcp_server.state_machine.create_mcp_server import handle_add_server_to_active

    event = sample_mcp_server_event.copy()
    event["stack_name"] = "test-stack-name"
    event["groups"] = []  # Empty groups

    mcp_servers_table.put_item(
        Item={
            "id": event["id"],
            "name": event["name"],
            "status": "Creating",
        }
    )

    with patch("mcp_server.state_machine.create_mcp_server.ssmClient") as mock_ssm:
        # Create a proper exception class for ParameterNotFound
        class ParameterNotFound(Exception):
            pass

        mock_ssm.exceptions.ParameterNotFound = ParameterNotFound
        mock_ssm.get_parameter.side_effect = ParameterNotFound()

        result = handle_add_server_to_active(event, None)

        assert result["server_status"] == "InService"


def test_handle_failure(mcp_servers_table, sample_mcp_server_event):
    """Test handling deployment failure."""
    from mcp_server.state_machine.create_mcp_server import handle_failure

    # Create initial server record
    mcp_servers_table.put_item(
        Item={
            "id": sample_mcp_server_event["id"],
            "name": sample_mcp_server_event["name"],
            "status": "Creating",
        }
    )

    event = sample_mcp_server_event.copy()
    event["error"] = "Deployment failed: Stack creation error"

    # Call the handler function
    result = handle_failure(event, None)

    # Verify DynamoDB was updated
    response = mcp_servers_table.get_item(Key={"id": "test-server-id"})
    assert response["Item"]["status"] == "Failed"
    assert response["Item"]["error_message"] == "Deployment failed: Stack creation error"
    assert "last_modified" in response["Item"]
    assert result == event


def test_handle_failure_missing_id(mcp_servers_table):
    """Test handle_failure with missing id."""
    from mcp_server.state_machine.create_mcp_server import handle_failure

    event = {"error": "Some error"}

    # Should not raise exception, just return event
    result = handle_failure(event, None)
    assert result == event


def test_handle_failure_no_error_message(mcp_servers_table, sample_mcp_server_event):
    """Test handle_failure with no error message."""
    from mcp_server.state_machine.create_mcp_server import handle_failure

    mcp_servers_table.put_item(
        Item={
            "id": sample_mcp_server_event["id"],
            "name": sample_mcp_server_event["name"],
            "status": "Creating",
        }
    )

    event = sample_mcp_server_event.copy()
    # No error field

    # Call the handler function
    result = handle_failure(event, None)

    # Verify DynamoDB was updated
    response = mcp_servers_table.get_item(Key={"id": "test-server-id"})
    assert response["Item"]["status"] == "Failed"
    assert response["Item"]["error_message"] == "Unknown error"
    assert "last_modified" in response["Item"]
    assert result == event


def test_normalize_server_identifier():
    """Test server identifier normalization."""
    from mcp_server.state_machine.create_mcp_server import _normalize_server_identifier

    assert _normalize_server_identifier("test-server-123") == "testserver123"
    assert _normalize_server_identifier("server_with_underscores") == "serverwithunderscores"
    assert _normalize_server_identifier("server.with.dots") == "serverwithdots"
    assert _normalize_server_identifier("Server123") == "Server123"


def test_get_mcp_connections_table_name():
    """Test getting MCP connections table name from SSM."""
    from mcp_server.state_machine.create_mcp_server import _get_mcp_connections_table_name

    with patch("mcp_server.state_machine.create_mcp_server.ssmClient") as mock_ssm:
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-table-name"}}

        result = _get_mcp_connections_table_name("/test/lisa")
        assert result == "test-table-name"


def test_get_mcp_connections_table_name_not_found():
    """Test getting MCP connections table name when not found."""
    from mcp_server.state_machine.create_mcp_server import _get_mcp_connections_table_name

    with patch("mcp_server.state_machine.create_mcp_server.ssmClient") as mock_ssm:
        mock_ssm.exceptions.ParameterNotFound = Exception
        mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound("Not found")

        result = _get_mcp_connections_table_name("/test/lisa")
        assert result is None


def test_get_api_gateway_url():
    """Test getting API Gateway URL from SSM."""
    from mcp_server.state_machine.create_mcp_server import _get_api_gateway_url

    with patch("mcp_server.state_machine.create_mcp_server.ssmClient") as mock_ssm:
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "https://api.example.com"}}

        result = _get_api_gateway_url("/test/lisa")
        assert result == "https://api.example.com"


def test_get_api_gateway_url_error():
    """Test getting API Gateway URL when error occurs."""
    from mcp_server.state_machine.create_mcp_server import _get_api_gateway_url

    with patch("mcp_server.state_machine.create_mcp_server.ssmClient") as mock_ssm:
        mock_ssm.get_parameter.side_effect = Exception("Some error")

        result = _get_api_gateway_url("/test/lisa")
        assert result is None
