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

"""Unit tests for MCP server delete state machine handlers."""

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
os.environ["DEPLOYMENT_PREFIX"] = "/test/deployment"

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


@pytest.fixture(scope="function")
def mcp_connections_table(dynamodb):
    """Create a mock DynamoDB table for MCP connections."""
    table = dynamodb.create_table(
        TableName="mcp-connections-table",
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"},
            {"AttributeName": "owner", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "owner", "AttributeType": "S"},
        ],
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
    """Sample event for MCP server delete state machine."""
    return {
        "id": "test-server-id",
        "name": "Test MCP Server",
        "description": "Test description",
        "owner": "test-user",
        "stack_name": "test-stack-name",
    }


@pytest.fixture(scope="function")
def sample_mcp_server_with_stack():
    """Sample MCP server item with stack."""
    return {
        "id": "test-server-id",
        "name": "Test MCP Server",
        "description": "Test description",
        "owner": "test-user",
        "status": "InService",
        "stack_name": "test-stack-name",
        "cloudformation_stack_arn": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123",
    }


@pytest.fixture
def sample_mcp_server_without_stack():
    """Sample MCP server item without stack."""
    return {
        "id": "test-server-id",
        "name": "Test MCP Server",
        "description": "Test description",
        "owner": "test-user",
        "status": "InService",
    }


def test_handle_set_server_to_deleting(mcp_servers_table, sample_mcp_server_with_stack, lambda_context):
    """Test successful setting of server status to DELETING."""
    mcp_servers_table.put_item(Item=sample_mcp_server_with_stack)

    from mcp_server.state_machine.delete_mcp_server import handle_set_server_to_deleting

    event = {"id": sample_mcp_server_with_stack["id"]}
    result = handle_set_server_to_deleting(event, lambda_context)

    assert result["id"] == "test-server-id"
    assert (
        result["cloudformation_stack_arn"]
        == "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123"
    )
    assert result["stack_name"] == "test-stack-name"

    # Verify DynamoDB was updated
    item = mcp_servers_table.get_item(Key={"id": "test-server-id"})["Item"]
    assert item["status"] == "Deleting"


def test_handle_set_server_to_deleting_not_found(mcp_servers_table, lambda_context):
    """Test handling deletion for non-existent server."""
    from mcp_server.state_machine.delete_mcp_server import handle_set_server_to_deleting

    event = {"id": "non-existent-server"}

    with pytest.raises(RuntimeError, match="not found"):
        handle_set_server_to_deleting(event, lambda_context)


def test_handle_set_server_to_deleting_no_stack(mcp_servers_table, sample_mcp_server_without_stack, lambda_context):
    """Test setting server to deleting when no stack exists."""
    mcp_servers_table.put_item(Item=sample_mcp_server_without_stack)

    from mcp_server.state_machine.delete_mcp_server import handle_set_server_to_deleting

    event = {"id": sample_mcp_server_without_stack["id"]}
    result = handle_set_server_to_deleting(event, lambda_context)

    assert result["id"] == "test-server-id"
    assert result["cloudformation_stack_arn"] is None


def test_handle_delete_stack(mcp_servers_table, lambda_context):
    """Test successful stack deletion initiation."""
    from mcp_server.state_machine.delete_mcp_server import handle_delete_stack

    event = {
        "id": "test-server-id",
        "stack_name": "test-stack-name",
        "cloudformation_stack_arn": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123",
    }

    # Mock CloudFormation client
    with patch("mcp_server.state_machine.delete_mcp_server.cfnClient") as mock_cfn:
        mock_cfn.delete_stack.return_value = {}

        result = handle_delete_stack(event, lambda_context)

        assert (
            result["cloudformation_stack_arn"]
            == "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123"
        )
        # Verify delete_stack was called with provided ARN
        mock_cfn.delete_stack.assert_called_once()
        call_args = mock_cfn.delete_stack.call_args
        assert call_args[1]["StackName"] == "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123"
        assert "ClientRequestToken" in call_args[1]


def test_handle_delete_stack_missing_stack_name(mcp_servers_table, lambda_context):
    """Test delete stack with missing stack name."""
    from mcp_server.state_machine.delete_mcp_server import handle_delete_stack

    event = {
        "id": "test-server-id",
    }

    with pytest.raises(ValueError, match="Stack arn not found in event"):
        handle_delete_stack(event, lambda_context)


def test_handle_monitor_delete_stack_complete(mcp_servers_table, lambda_context):
    """Test monitoring stack deletion when complete."""
    from mcp_server.state_machine.delete_mcp_server import handle_monitor_delete_stack

    event = {
        "id": "test-server-id",
        "stack_name": "test-stack-name",
        "cloudformation_stack_arn": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123",
    }

    # Mock CloudFormation client
    with patch("mcp_server.state_machine.delete_mcp_server.cfnClient") as mock_cfn:
        mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "DELETE_COMPLETE"}]}

        result = handle_monitor_delete_stack(event, lambda_context)

        assert result["continue_polling"] is False
        # Verify ARN was used for monitoring
        mock_cfn.describe_stacks.assert_called_once_with(
            StackName="arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123"
        )


def test_handle_monitor_delete_stack_in_progress(mcp_servers_table, lambda_context):
    """Test monitoring stack deletion when in progress."""
    from mcp_server.state_machine.delete_mcp_server import handle_monitor_delete_stack

    event = {
        "id": "test-server-id",
        "stack_name": "test-stack-name",
        "cloudformation_stack_arn": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123",
    }

    # Mock CloudFormation client
    with patch("mcp_server.state_machine.delete_mcp_server.cfnClient") as mock_cfn:
        mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "DELETE_IN_PROGRESS"}]}

        result = handle_monitor_delete_stack(event, lambda_context)

        assert result["continue_polling"] is True
        # Verify ARN was used for monitoring
        mock_cfn.describe_stacks.assert_called_once_with(
            StackName="arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123"
        )


def test_handle_monitor_delete_stack_failed(mcp_servers_table, lambda_context):
    """Test monitoring stack deletion when failed."""
    from mcp_server.state_machine.delete_mcp_server import handle_monitor_delete_stack

    event = {
        "id": "test-server-id",
        "stack_name": "test-stack-name",
        "cloudformation_stack_arn": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123",
    }

    # Mock CloudFormation client
    with patch("mcp_server.state_machine.delete_mcp_server.cfnClient") as mock_cfn:
        mock_cfn.describe_stacks.return_value = {"Stacks": [{"StackStatus": "DELETE_FAILED"}]}

        with pytest.raises(RuntimeError, match="unexpected terminal state"):
            handle_monitor_delete_stack(event, lambda_context)


def test_handle_monitor_delete_stack_missing_stack_name(mcp_servers_table, lambda_context):
    """Test monitoring with missing stack name/ARN."""
    from mcp_server.state_machine.delete_mcp_server import handle_monitor_delete_stack

    event = {
        "id": "test-server-id",
    }

    with pytest.raises(ValueError, match="Stack ARN or name not found"):
        handle_monitor_delete_stack(event, lambda_context)


def test_handle_monitor_delete_stack_not_found(mcp_servers_table, lambda_context):
    """Test monitoring stack deletion when stack no longer exists (successfully deleted)."""
    from botocore.exceptions import ClientError
    from mcp_server.state_machine.delete_mcp_server import handle_monitor_delete_stack

    event = {
        "id": "test-server-id",
        "stack_name": "test-stack-name",
        "cloudformation_stack_arn": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123",
    }

    # Mock CloudFormation client
    with patch("mcp_server.state_machine.delete_mcp_server.cfnClient") as mock_cfn:
        # Create a ClientError with ValidationError code
        error_response = {
            "Error": {
                "Code": "ValidationError",
                "Message": (
                    "Stack with id arn:aws:cloudformation:us-east-1:123456789012:stack/"
                    "test-stack-name/abc123 does not exist"
                ),
            }
        }
        mock_cfn.describe_stacks.side_effect = ClientError(error_response, "DescribeStacks")

        result = handle_monitor_delete_stack(event, lambda_context)

        # Stack doesn't exist means deletion was successful
        assert result["continue_polling"] is False
        # Verify ARN was used for monitoring
        mock_cfn.describe_stacks.assert_called_once_with(
            StackName="arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack-name/abc123"
        )


def test_handle_delete_from_ddb(mcp_servers_table, sample_mcp_server_with_stack, lambda_context):
    """Test successful deletion from DynamoDB."""
    mcp_servers_table.put_item(Item=sample_mcp_server_with_stack)

    from mcp_server.state_machine.delete_mcp_server import handle_delete_from_ddb

    event = {"id": sample_mcp_server_with_stack["id"]}

    # Mock SSM client to return None (no connections table)
    with patch("mcp_server.state_machine.delete_mcp_server.ssmClient") as mock_ssm:
        mock_ssm.exceptions.ParameterNotFound = Exception
        mock_ssm.get_parameter.side_effect = Exception("Parameter not found")

        result = handle_delete_from_ddb(event, lambda_context)

        assert result == event

        # Verify server was deleted from main table
        response = mcp_servers_table.get_item(Key={"id": "test-server-id"})
        assert "Item" not in response


def test_handle_delete_from_ddb_with_connections_table(
    mcp_servers_table, mcp_connections_table, sample_mcp_server_with_stack, lambda_context
):
    """Test deletion from DynamoDB including connections table."""
    mcp_servers_table.put_item(Item=sample_mcp_server_with_stack)

    # Add connection entry
    connection_entry = {
        "id": "test-server-id",
        "owner": "test-user",
        "name": "Test MCP Server",
        "url": "https://api.example.com/mcp/test-server/mcp",
    }
    mcp_connections_table.put_item(Item=connection_entry)

    from mcp_server.state_machine.delete_mcp_server import handle_delete_from_ddb

    event = {"id": sample_mcp_server_with_stack["id"]}

    # Mock SSM client to return connections table name
    with patch("mcp_server.state_machine.delete_mcp_server.ssmClient") as mock_ssm:
        mock_ssm.exceptions.ParameterNotFound = Exception
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "mcp-connections-table"}}

        result = handle_delete_from_ddb(event, lambda_context)

        assert result == event

        # Verify server was deleted from main table
        response = mcp_servers_table.get_item(Key={"id": "test-server-id"})
        assert "Item" not in response

        # Verify connection was deleted from connections table
        response = mcp_connections_table.get_item(Key={"id": "test-server-id", "owner": "test-user"})
        assert "Item" not in response


def test_handle_delete_from_ddb_connections_table_error(
    mcp_servers_table, sample_mcp_server_with_stack, lambda_context
):
    """Test deletion continues even if connections table deletion fails."""
    mcp_servers_table.put_item(Item=sample_mcp_server_with_stack)

    from mcp_server.state_machine.delete_mcp_server import handle_delete_from_ddb

    event = {"id": sample_mcp_server_with_stack["id"]}

    # Mock SSM client to return connections table name, but simulate error
    with patch("mcp_server.state_machine.delete_mcp_server.ssmClient") as mock_ssm:
        mock_ssm.exceptions.ParameterNotFound = Exception
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "mcp-connections-table"}}

        # Mock the table scan to raise an error
        with patch("mcp_server.state_machine.delete_mcp_server.ddbResource") as mock_ddb:
            mock_table = MagicMock()
            mock_table.scan.side_effect = Exception("Connection table error")
            mock_ddb.Table.return_value = mock_table

            # Should still succeed and delete from main table
            result = handle_delete_from_ddb(event, lambda_context)

            assert result == event

            # Verify server was deleted from main table despite connection table error
            response = mcp_servers_table.get_item(Key={"id": "test-server-id"})
            assert "Item" not in response
