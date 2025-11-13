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

"""Unit tests for MCP server lambda functions."""

import functools
import json
import logging
import os
import sys
from datetime import datetime
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
os.environ["MCP_SERVERS_BY_OWNER_INDEX_NAME"] = "mcp-servers-by-owner-index"

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


def mock_api_wrapper(func):
    """Mock API wrapper that handles both success and error cases for testing."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if isinstance(result, dict) and "statusCode" in result:
                return result
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps(result, default=str),
            }
        except ValueError as e:
            error_msg = str(e)
            status_code = 400
            if "not found" in error_msg.lower():
                status_code = 404
            elif "Not authorized" in error_msg or "not authorized" in error_msg:
                status_code = 403
            return {
                "statusCode": status_code,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": error_msg}, default=str),
            }
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": str(e)}),
            }

    return wrapper


# Create mock modules
mock_create_env = MagicMock()
mock_common = MagicMock()

# Set up common mock values - defaults that tests can override
mock_common.username = "test-user"
mock_common.groups = ["test-group"]
mock_common.is_admin_value = False


# Create mock functions that read from mock_common attributes (dynamic)
def get_username_mock(event):
    return mock_common.username


def get_groups_mock(event):
    return mock_common.groups


def is_admin_mock(event):
    return mock_common.is_admin_value


def get_user_context_mock(event):
    return (mock_common.username, mock_common.is_admin_value, mock_common.groups)


mock_common.get_username = MagicMock(side_effect=get_username_mock)
mock_common.get_groups = MagicMock(side_effect=get_groups_mock)
mock_common.is_admin = MagicMock(side_effect=is_admin_mock)
mock_common.get_user_context = MagicMock(side_effect=get_user_context_mock)
mock_common.retry_config = retry_config
mock_common.api_wrapper = mock_api_wrapper

# Patch BEFORE importing - this ensures the mock is used when decorators are applied
patch.dict("sys.modules", {"create_env_variables": mock_create_env}).start()
patch("utilities.auth.get_username", mock_common.get_username).start()
patch("utilities.auth.get_groups", mock_common.get_groups).start()
patch("utilities.auth.is_admin", mock_common.is_admin).start()
patch("utilities.auth.get_user_context", mock_common.get_user_context).start()
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.api_wrapper", mock_api_wrapper).start()

# Now import the lambda functions - they will use the mocked dependencies
from mcp_server.lambda_functions import (
    _get_mcp_servers,
    create,
    create_hosted_mcp_server,
    delete,
    get,
    get_hosted_mcp_server,
    get_mcp_server_id,
    list,
    list_hosted_mcp_servers,
    update,
    update_hosted_mcp_server,
)


def get_error_message(body):
    """Extract error message from response body (handles both string and dict formats)."""
    if isinstance(body, str):
        return body
    return body.get("error", "")


def set_auth_user(username="test-user", groups=None, is_admin=False):
    """Helper to set auth mock values for a test."""
    if groups is None:
        groups = ["test-group"]
    mock_common.username = username
    mock_common.groups = groups
    mock_common.is_admin_value = is_admin


def reset_auth():
    """Reset auth mocks to defaults."""
    set_auth_user("test-user", ["test-group"], False)


@pytest.fixture(autouse=True)
def ensure_mcp_auth_patches(request, mock_auth):
    """Ensure our module-level auth patches take precedence over conftest's patches.

    This runs after conftest's setup_auth_patches and re-applies our patches
    so they persist for the test. We depend on mock_auth to ensure we run after
    conftest's setup_auth_patches fixture.
    """
    # Re-apply our patches to ensure they override conftest's patches
    # This must happen after conftest's patches are applied
    patches = [
        patch("utilities.auth.get_username", mock_common.get_username),
        patch("utilities.auth.get_groups", mock_common.get_groups),
        patch("utilities.auth.is_admin", mock_common.is_admin),
        patch("utilities.auth.get_user_context", mock_common.get_user_context),
        # Also patch where they're imported
        patch("mcp_server.lambda_functions.get_user_context", mock_common.get_user_context),
    ]

    for p in patches:
        p.start()

    # Reset to defaults before each test
    reset_auth()

    yield

    # Cleanup - stop our patches
    for p in patches:
        p.stop()

    reset_auth()


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
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "owner", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "mcp-servers-by-owner-index",
                "KeySchema": [{"AttributeName": "owner", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            }
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
def sample_mcp_server():
    return {
        "id": "test-server-id",
        "created": datetime.now().isoformat(),
        "owner": "test-user",
        "url": "https://example.com/mcp-server",
        "name": "Test MCP Server",
    }


@pytest.fixture
def sample_global_mcp_server():
    return {
        "id": "global-server-id",
        "created": datetime.now().isoformat(),
        "owner": "lisa:public",
        "url": "https://example.com/global-mcp-server",
        "name": "Global MCP Server",
    }


@pytest.fixture
def sample_hosted_mcp_server():
    """Sample hosted MCP server data."""
    return {
        "id": "hosted-server-id",
        "created": datetime.now().isoformat(),
        "owner": "test-user",
        "name": "Test Hosted MCP Server",
        "description": "Test description",
        "startCommand": "python server.py",
        "port": 8000,
        "serverType": "http",
        "autoScalingConfig": {
            "minCapacity": 1,
            "maxCapacity": 10,
            "targetValue": 5,
        },
        "status": "Creating",
    }


def test_get_mcp_server_id():
    """Test extracting MCP server ID from event path parameters."""
    event = {"pathParameters": {"serverId": "test-server-123"}}

    result = get_mcp_server_id(event)
    assert result == "test-server-123"


def test_get_mcp_servers_no_filter(mcp_servers_table, sample_mcp_server):
    """Test _get_mcp_servers helper function without user filter."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    result = _get_mcp_servers()
    assert "Items" in result
    assert len(result["Items"]) == 1
    assert result["Items"][0]["id"] == "test-server-id"


def test_get_mcp_servers_with_user_filter(mcp_servers_table, sample_mcp_server):
    """Test _get_mcp_servers helper function with user filter."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    result = _get_mcp_servers(user_id="test-user")
    assert "Items" in result


def test_get_mcp_server_success(mcp_servers_table, sample_mcp_server, lambda_context, mock_auth):
    """Test successful retrieval of MCP server by owner."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    response = get(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "test-server-id"
    assert body["owner"] == "test-user"
    assert body["isOwner"] is True


def test_get_global_mcp_server_success(mcp_servers_table, sample_global_mcp_server, lambda_context, mock_auth):
    """Test successful retrieval of global MCP server by any user."""
    mcp_servers_table.put_item(Item=sample_global_mcp_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "any-user"}}},
        "pathParameters": {"serverId": "global-server-id"},
    }

    set_auth_user("any-user", [], False)

    response = get(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "global-server-id"
    assert body["owner"] == "lisa:public"
    assert body["isOwner"] is True


def test_get_mcp_server_admin_access(mcp_servers_table, sample_mcp_server, lambda_context, mock_auth):
    """Test admin can access any MCP server."""
    # Create a server owned by different user
    other_user_server = sample_mcp_server.copy()
    other_user_server["owner"] = "other-user"
    mcp_servers_table.put_item(Item=other_user_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    set_auth_user("admin-user", [], True)

    response = get(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "test-server-id"
    assert "isOwner" not in body  # Admin doesn't get isOwner flag


def test_delete_hosted_mcp_server_success(mcp_servers_table, lambda_context, mock_auth):
    """Test successful deletion of hosted MCP server."""
    # Add a server to the table
    server_item = {
        "id": "test-server-id",
        "name": "Test Hosted MCP Server",
        "status": "InService",
        "stack_name": "test-stack-name",
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    with patch.dict(
        os.environ,
        {"DELETE_MCP_SERVER_SFN_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:DeleteTestStateMachine"},
    ):
        # Import the module to get access to stepfunctions
        import mcp_server.lambda_functions as mcp_module

        # Create a mock client with start_execution method
        mock_sfn_client = MagicMock()
        mock_sfn_client.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123456789012:execution:DeleteTestStateMachine:test-execution"
        }

        # Patch the stepfunctions attribute directly in the already-imported module
        original_stepfunctions = mcp_module.stepfunctions
        mcp_module.stepfunctions = mock_sfn_client

        try:
            set_auth_user("admin-user", [], True)

            # Call the function from the module namespace to ensure it uses the patched stepfunctions
            response = mcp_module.delete_hosted_mcp_server(event, lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert "message" in body
            assert "test-server-id" in body["message"]

            # Verify state machine was invoked
            mock_sfn_client.start_execution.assert_called_once()
            call_args = mock_sfn_client.start_execution.call_args
            assert (
                call_args[1]["stateMachineArn"]
                == "arn:aws:states:us-east-1:123456789012:stateMachine:DeleteTestStateMachine"
            )
            input_data = json.loads(call_args[1]["input"])
            assert input_data["id"] == "test-server-id"

            # Reset mocks
        finally:
            # Restore original stepfunctions client
            mcp_module.stepfunctions = original_stepfunctions


def test_delete_hosted_mcp_server_not_found(mcp_servers_table, lambda_context, mock_auth):
    """Test deletion of non-existent hosted MCP server."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "non-existent-server"},
    }

    import mcp_server.lambda_functions as mcp_module

    set_auth_user("admin-user", [], True)

    response = mcp_module.delete_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "not found" in get_error_message(body).lower()

    # Reset mocks


def test_delete_hosted_mcp_server_not_admin(mcp_servers_table, lambda_context, mock_auth):
    """Test that non-admin cannot delete hosted MCP server."""
    # Add a server to the table
    server_item = {
        "id": "test-server-id",
        "name": "Test Hosted MCP Server",
        "status": "InService",
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    import mcp_server.lambda_functions as mcp_module

    response = mcp_module.delete_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert "Not authorized" in get_error_message(body)

    # Reset mocks


def test_delete_hosted_mcp_server_missing_sfn_arn(mcp_servers_table, lambda_context, mock_auth):
    """Test that missing SFN ARN raises error."""
    # Add a server to the table
    server_item = {
        "id": "test-server-id",
        "name": "Test Hosted MCP Server",
        "status": "InService",
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    import mcp_server.lambda_functions as mcp_module

    with patch.dict(os.environ, {}, clear=True):
        os.environ["MCP_SERVERS_TABLE_NAME"] = "mcp-servers-table"
        os.environ["MCP_SERVERS_BY_OWNER_INDEX_NAME"] = "mcp-servers-by-owner-index"
        set_auth_user("admin-user", [], True)

        response = mcp_module.delete_hosted_mcp_server(event, lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "DELETE_MCP_SERVER_SFN_ARN not configured" in get_error_message(body)

        # Reset mocks


def test_get_mcp_server_not_found(mcp_servers_table, lambda_context, mock_auth):
    """Test MCP server not found error."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "non-existent-server"},
    }

    response = get(event, lambda_context)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "MCP Server non-existent-server not found" in get_error_message(body)


def test_get_mcp_server_not_authorized(mcp_servers_table, sample_mcp_server, lambda_context, mock_auth):
    """Test unauthorized access to MCP server."""
    # Create a server owned by different user
    other_user_server = sample_mcp_server.copy()
    other_user_server["owner"] = "other-user"
    mcp_servers_table.put_item(Item=other_user_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    response = get(event, lambda_context)
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert "Not authorized to get test-server-id" in get_error_message(body)


def test_list_mcp_servers_regular_user(mcp_servers_table, sample_mcp_server, lambda_context, mock_auth):
    """Test listing MCP servers for regular user."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    response = list(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "Items" in body


def test_list_mcp_servers_admin(mcp_servers_table, sample_mcp_server, lambda_context, mock_auth):
    """Test listing MCP servers for admin user."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    event = {"requestContext": {"authorizer": {"claims": {"username": "admin-user"}}}}

    set_auth_user("admin-user", [], True)

    response = list(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "Items" in body

    # Reset mocks


def test_create_mcp_server_success(mcp_servers_table, lambda_context, mock_auth):
    """Test successful creation of MCP server."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "body": json.dumps(
            {
                "name": "Test MCP Server",
                "url": "https://example.com/mcp-server",
            }
        ),
    }

    response = create(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["name"] == "Test MCP Server"
    assert body["url"] == "https://example.com/mcp-server"
    assert body["owner"] == "test-user"
    assert "id" in body
    assert "created" in body


def test_create_mcp_server_with_owner(mcp_servers_table, lambda_context, mock_auth):
    """Test creation of MCP server with explicit owner."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "body": json.dumps(
            {
                "name": "Test MCP Server",
                "url": "https://example.com/mcp-server",
                "owner": "custom-owner",
            }
        ),
    }

    response = create(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["owner"] == "test-user"


def test_update_mcp_server_success(mcp_servers_table, sample_mcp_server, lambda_context, mock_auth):
    """Test successful update of MCP server."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    updated_server = {
        "id": "test-server-id",
        "name": "Updated MCP Server",
        "url": "https://example.com/updated-mcp-server",
        "owner": "test-user",
    }

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
        "body": json.dumps(updated_server),
    }

    response = update(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["name"] == "Updated MCP Server"
    assert body["url"] == "https://example.com/updated-mcp-server"


def test_update_mcp_server_admin_access(mcp_servers_table, sample_mcp_server, lambda_context, mock_auth):
    """Test admin can update any MCP server."""
    # Create a server owned by different user
    other_user_server = sample_mcp_server.copy()
    other_user_server["owner"] = "other-user"
    mcp_servers_table.put_item(Item=other_user_server)

    updated_server = {
        "id": "test-server-id",
        "name": "Admin Updated Server",
        "url": "https://example.com/admin-updated",
        "owner": "other-user",
    }

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
        "body": json.dumps(updated_server),
    }

    set_auth_user("admin-user", [], True)

    response = update(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["name"] == "Admin Updated Server"

    # Reset mocks


def test_update_mcp_server_id_mismatch(mcp_servers_table, sample_mcp_server, lambda_context):
    """Test update with mismatched IDs."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    updated_server = {
        "id": "different-server-id",  # Different from URL path
        "name": "Updated MCP Server",
        "url": "https://example.com/updated-mcp-server",
        "owner": "test-user",
    }

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
        "body": json.dumps(updated_server),
    }

    response = update(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "URL id test-server-id doesn't match body id different-server-id" in get_error_message(body)


def test_update_mcp_server_not_found(mcp_servers_table, lambda_context):
    """Test update of non-existent MCP server."""
    updated_server = {
        "id": "non-existent-server",
        "name": "Updated MCP Server",
        "url": "https://example.com/updated-mcp-server",
        "owner": "test-user",
    }

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "non-existent-server"},
        "body": json.dumps(updated_server),
    }

    response = update(event, lambda_context)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "not found" in get_error_message(body).lower()


def test_update_mcp_server_not_authorized(mcp_servers_table, sample_mcp_server, lambda_context):
    """Test unauthorized update of MCP server."""
    # Create a server owned by different user
    other_user_server = sample_mcp_server.copy()
    other_user_server["owner"] = "other-user"
    mcp_servers_table.put_item(Item=other_user_server)

    updated_server = {
        "id": "test-server-id",
        "name": "Unauthorized Update",
        "url": "https://example.com/unauthorized",
        "owner": "other-user",
    }

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
        "body": json.dumps(updated_server),
    }

    response = update(event, lambda_context)
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert "Not authorized to update test-server-id" in get_error_message(body)


def test_delete_mcp_server_success(mcp_servers_table, sample_mcp_server, lambda_context, mock_auth):
    """Test successful deletion of MCP server."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    response = delete(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "ok"


def test_delete_mcp_server_admin_access(mcp_servers_table, sample_mcp_server, lambda_context, mock_auth):
    """Test admin can delete any MCP server."""
    # Create a server owned by different user
    other_user_server = sample_mcp_server.copy()
    other_user_server["owner"] = "other-user"
    mcp_servers_table.put_item(Item=other_user_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    set_auth_user("admin-user", [], True)

    response = delete(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "ok"

    # Reset mocks


def test_delete_mcp_server_not_found(mcp_servers_table, lambda_context):
    """Test deletion of non-existent MCP server."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "non-existent-server"},
    }

    response = delete(event, lambda_context)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "MCP Server non-existent-server not found" in get_error_message(body)


def test_delete_mcp_server_not_authorized(mcp_servers_table, sample_mcp_server, lambda_context):
    """Test unauthorized deletion of MCP server."""
    # Create a server owned by different user
    other_user_server = sample_mcp_server.copy()
    other_user_server["owner"] = "other-user"
    mcp_servers_table.put_item(Item=other_user_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    response = delete(event, lambda_context)
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert "Not authorized to delete test-server-id" in get_error_message(body)


def test_get_mcp_servers_pagination(mcp_servers_table):
    """Test pagination handling in _get_mcp_servers."""
    # Create some test data
    server1 = {"id": "server-1", "name": "Server 1", "owner": "test-user", "url": "https://example.com"}
    server2 = {"id": "server-2", "name": "Server 2", "owner": "test-user", "url": "https://example.com"}

    mcp_servers_table.put_item(Item=server1)
    mcp_servers_table.put_item(Item=server2)

    # Test that the function can handle multiple items
    result = _get_mcp_servers()
    assert len(result["Items"]) == 2
    server_ids = [item["id"] for item in result["Items"]]
    assert "server-1" in server_ids
    assert "server-2" in server_ids


def test_get_mcp_server_missing_path_parameters():
    """Test get_mcp_server_id with missing path parameters."""
    event = {"pathParameters": None}

    with pytest.raises(TypeError):
        get_mcp_server_id(event)


def test_get_mcp_server_missing_server_id():
    """Test get_mcp_server_id with missing serverId parameter."""
    event = {"pathParameters": {}}

    with pytest.raises(KeyError):
        get_mcp_server_id(event)


def test_create_mcp_server_invalid_json(lambda_context, mock_auth):
    """Test create with invalid JSON body."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "body": "invalid-json",
    }

    response = create(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


def test_create_mcp_server_missing_fields(lambda_context):
    """Test create with missing required fields."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "body": json.dumps(
            {
                "name": "Test MCP Server",
                # Missing url field
            }
        ),
    }

    response = create(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


def test_update_mcp_server_invalid_json(mcp_servers_table, sample_mcp_server, lambda_context, mock_auth):
    """Test update with invalid JSON body."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
        "body": "invalid-json",
    }

    response = update(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # JSONDecodeError returns as string "Bad Request: ..."
    assert isinstance(body, str) or "error" in body


def test_get_mcp_servers_empty_result(mcp_servers_table):
    """Test _get_mcp_servers with no results."""
    result = _get_mcp_servers()
    assert "Items" in result
    assert len(result["Items"]) == 0


def test_get_mcp_servers_with_filter_no_match(mcp_servers_table, sample_mcp_server):
    """Test _get_mcp_servers with user filter that doesn't match."""
    # Create a server with different owner
    other_server = sample_mcp_server.copy()
    other_server["owner"] = "other-user"
    mcp_servers_table.put_item(Item=other_server)

    result = _get_mcp_servers(user_id="different-user")
    assert "Items" in result


def test_get_mcp_server_global_non_owner_access(mcp_servers_table, sample_global_mcp_server, lambda_context, mock_auth):
    """Test that non-owner can access global MCP server."""
    mcp_servers_table.put_item(Item=sample_global_mcp_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
        "pathParameters": {"serverId": "global-server-id"},
    }

    set_auth_user("different-user", [], False)

    response = get(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "global-server-id"
    assert body["owner"] == "lisa:public"
    assert body["isOwner"] is True  # Global servers are accessible to everyone

    # Reset mock


def test_get_mcp_servers_groups_filtering(mcp_servers_table, lambda_context):
    """Test groups filtering logic in _get_mcp_servers function."""
    from mcp_server.lambda_functions import _get_mcp_servers

    # Create test servers with different group configurations
    test_servers = [
        # Server owned by user with no groups - should be included
        {"id": "server1", "owner": "test-user", "status": "active", "groups": None},
        # Server owned by user with matching groups - should be included
        {"id": "server2", "owner": "test-user", "status": "active", "groups": ["group:admin", "group:user"]},
        # Server owned by user with non-matching groups - should be excluded
        {"id": "server3", "owner": "test-user", "status": "active", "groups": ["group:other"]},
        # Public server with no groups - should be included
        {"id": "server4", "owner": "lisa:public", "status": "active", "groups": None},
        # Public server with matching groups - should be included
        {"id": "server5", "owner": "lisa:public", "status": "active", "groups": ["group:admin"]},
        # Public server with non-matching groups - should be excluded
        {"id": "server6", "owner": "lisa:public", "status": "active", "groups": ["group:other"]},
        # Inactive server - should be excluded
        {"id": "server7", "owner": "test-user", "status": "inactive", "groups": ["group:admin"]},
    ]

    # Insert test servers into the table
    for server in test_servers:
        mcp_servers_table.put_item(Item=server)

    # Test with groups filter
    result = _get_mcp_servers(user_id="test-user", active=True, groups=["admin", "user"])

    # Should include: server1 (user owns, no groups), server2 (user owns, matching groups),
    # server3 (user owns, non-matching groups), server4 (public, no groups), server5 (public, matching groups)
    # Should exclude: server6 (public, non-matching groups), server7 (inactive)
    expected_ids = {"server1", "server2", "server3", "server4", "server5"}
    actual_ids = {item["id"] for item in result["Items"]}

    assert actual_ids == expected_ids, f"Expected {expected_ids}, got {actual_ids}"


def test_get_mcp_servers_no_groups_filter(mcp_servers_table, lambda_context):
    """Test behavior when no groups are provided."""
    from mcp_server.lambda_functions import _get_mcp_servers

    test_servers = [
        {"id": "server1", "owner": "test-user", "status": "active", "groups": None},
        {"id": "server2", "owner": "test-user", "status": "active", "groups": ["group:admin"]},
    ]

    for server in test_servers:
        mcp_servers_table.put_item(Item=server)

    # Test without groups filter
    result = _get_mcp_servers(user_id="test-user", active=True, groups=None)

    # Should include all servers (no groups filtering)
    expected_ids = {"server1", "server2"}
    actual_ids = {item["id"] for item in result["Items"]}

    assert actual_ids == expected_ids


def test_get_mcp_servers_empty_groups_filter(mcp_servers_table, lambda_context):
    """Test behavior when empty groups list is provided."""
    from mcp_server.lambda_functions import _get_mcp_servers

    test_servers = [
        {"id": "server1", "owner": "test-user", "status": "active", "groups": None},
        {"id": "server2", "owner": "test-user", "status": "active", "groups": ["group:admin"]},
    ]

    for server in test_servers:
        mcp_servers_table.put_item(Item=server)

    # Test with empty groups list
    result = _get_mcp_servers(user_id="test-user", active=True, groups=[])

    # Should include all servers (empty groups list means no filtering)
    expected_ids = {"server1", "server2"}
    actual_ids = {item["id"] for item in result["Items"]}

    assert actual_ids == expected_ids


# ============================================================================
# Hosted MCP Server Tests
# ============================================================================


def test_create_hosted_mcp_server_success(mcp_servers_table, lambda_context, mock_auth):
    """Test successful creation of hosted MCP server."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "body": json.dumps(
            {
                "name": "Test Hosted MCP Server",
                "description": "Test description",
                "startCommand": "python server.py",
                "port": 8000,
                "serverType": "http",
                "autoScalingConfig": {
                    "minCapacity": 1,
                    "maxCapacity": 10,
                    "targetValue": 5,
                },
            }
        ),
    }

    with patch.dict(
        os.environ, {"CREATE_MCP_SERVER_SFN_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:TestStateMachine"}
    ):
        # Create a mock client with start_execution method
        mock_sfn_client = MagicMock()
        mock_sfn_client.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123456789012:execution:TestStateMachine:test-execution"
        }

        # Import the module to get access to stepfunctions
        import mcp_server.lambda_functions as mcp_module

        # Patch the stepfunctions attribute directly in the already-imported module
        original_stepfunctions = mcp_module.stepfunctions
        mcp_module.stepfunctions = mock_sfn_client

        try:
            set_auth_user("admin-user", [], True)

            # Call the function from the module namespace to ensure it uses the patched stepfunctions
            response = mcp_module.create_hosted_mcp_server(event, lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["name"] == "Test Hosted MCP Server"
            assert body["startCommand"] == "python server.py"
            assert body["status"] == "Creating"
            assert "id" in body
            assert "created" in body

            # Verify state machine was invoked
            mock_sfn_client.start_execution.assert_called_once()
            call_args = mock_sfn_client.start_execution.call_args
            assert (
                call_args[1]["stateMachineArn"] == "arn:aws:states:us-east-1:123456789012:stateMachine:TestStateMachine"
            )

            # Reset mocks
        finally:
            # Restore original stepfunctions client
            mcp_module.stepfunctions = original_stepfunctions


def test_create_hosted_mcp_server_not_admin(mcp_servers_table, lambda_context, mock_auth):
    """Test that non-admin cannot create hosted MCP server."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "body": json.dumps(
            {
                "name": "Test Hosted MCP Server",
                "startCommand": "python server.py",
                "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 10},
            }
        ),
    }

    with patch("mcp_server.lambda_functions.stepfunctions"):
        set_auth_user("test-user", [], False)

        response = create_hosted_mcp_server(event, lambda_context)
        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert "Not authorized to create hosted MCP server" in get_error_message(body)


def test_create_hosted_mcp_server_missing_sfn_arn(mcp_servers_table, lambda_context, mock_auth):
    """Test that missing SFN ARN raises error."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "body": json.dumps(
            {
                "name": "Test Hosted MCP Server",
                "startCommand": "python server.py",
                "serverType": "http",
                "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 10},
            }
        ),
    }

    import mcp_server.lambda_functions as mcp_module

    with patch.object(mcp_module, "stepfunctions", MagicMock()):
        with patch.dict(os.environ, {}, clear=True):
            os.environ["MCP_SERVERS_TABLE_NAME"] = "mcp-servers-table"
            os.environ["MCP_SERVERS_BY_OWNER_INDEX_NAME"] = "mcp-servers-by-owner-index"
            set_auth_user("admin-user", [], True)

            response = mcp_module.create_hosted_mcp_server(event, lambda_context)
            assert response["statusCode"] == 400
            body = json.loads(response["body"])
            assert "CREATE_MCP_SERVER_SFN_ARN not configured" in get_error_message(body)

            # Reset mocks


def test_create_hosted_mcp_server_duplicate_normalized_name(mcp_servers_table, lambda_context, mock_auth):
    """Test that creating a server with duplicate normalized name fails."""
    # Add an existing server with name "Test Server"
    existing_server = {
        "id": "existing-server-id",
        "name": "Test Server",
        "owner": "admin-user",
        "status": "InService",
        "startCommand": "python server.py",
        "serverType": "http",
        "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 10},
    }
    mcp_servers_table.put_item(Item=existing_server)

    # Try to create a new server with name "Test-Server" (normalizes to same as existing)
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "body": json.dumps(
            {
                "name": "Test-Server",  # Normalizes to "TestServer" same as "Test Server"
                "description": "Test description",
                "startCommand": "python server.py",
                "port": 8000,
                "serverType": "http",
                "autoScalingConfig": {
                    "minCapacity": 1,
                    "maxCapacity": 10,
                    "targetValue": 5,
                },
            }
        ),
    }

    with patch.dict(
        os.environ, {"CREATE_MCP_SERVER_SFN_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:TestStateMachine"}
    ):
        import mcp_server.lambda_functions as mcp_module

        set_auth_user("admin-user", [], True)

        response = mcp_module.create_hosted_mcp_server(event, lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "conflicts with existing server" in get_error_message(body).lower()
        assert "normalized names must be unique" in get_error_message(body).lower()

        # Reset mocks


def test_create_hosted_mcp_server_empty_normalized_name(mcp_servers_table, lambda_context, mock_auth):
    """Test that creating a server with only special characters fails."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "body": json.dumps(
            {
                "name": "!@#$%^&*()",  # Only special characters, normalizes to empty string
                "description": "Test description",
                "startCommand": "python server.py",
                "port": 8000,
                "serverType": "http",
                "autoScalingConfig": {
                    "minCapacity": 1,
                    "maxCapacity": 10,
                    "targetValue": 5,
                },
            }
        ),
    }

    with patch.dict(
        os.environ, {"CREATE_MCP_SERVER_SFN_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:TestStateMachine"}
    ):
        import mcp_server.lambda_functions as mcp_module

        set_auth_user("admin-user", [], True)

        response = mcp_module.create_hosted_mcp_server(event, lambda_context)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "must contain at least one alphanumeric character" in get_error_message(body).lower()

        # Reset mocks


def test_delete_hosted_mcp_server_invalid_status_creating(mcp_servers_table, lambda_context, mock_auth):
    """Test that deleting a server with status 'Creating' fails."""
    server_item = {
        "id": "test-server-id",
        "name": "Test Hosted MCP Server",
        "status": "Creating",
        "stack_name": "test-stack-name",
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    import mcp_server.lambda_functions as mcp_module

    set_auth_user("admin-user", [], True)

    response = mcp_module.delete_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "cannot delete server" in get_error_message(body).lower()
    assert "creating" in get_error_message(body).lower()

    # Reset mocks


def test_delete_hosted_mcp_server_invalid_status_starting(mcp_servers_table, lambda_context, mock_auth):
    """Test that deleting a server with status 'Starting' fails."""
    server_item = {
        "id": "test-server-id",
        "name": "Test Hosted MCP Server",
        "status": "Starting",
        "stack_name": "test-stack-name",
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    import mcp_server.lambda_functions as mcp_module

    set_auth_user("admin-user", [], True)

    response = mcp_module.delete_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "cannot delete server" in get_error_message(body).lower()

    # Reset mocks


def test_delete_hosted_mcp_server_invalid_status_stopping(mcp_servers_table, lambda_context, mock_auth):
    """Test that deleting a server with status 'Stopping' fails."""
    server_item = {
        "id": "test-server-id",
        "name": "Test Hosted MCP Server",
        "status": "Stopping",
        "stack_name": "test-stack-name",
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    import mcp_server.lambda_functions as mcp_module

    set_auth_user("admin-user", [], True)

    response = mcp_module.delete_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "cannot delete server" in get_error_message(body).lower()

    # Reset mocks


def test_delete_hosted_mcp_server_invalid_status_updating(mcp_servers_table, lambda_context, mock_auth):
    """Test that deleting a server with status 'Updating' fails."""
    server_item = {
        "id": "test-server-id",
        "name": "Test Hosted MCP Server",
        "status": "Updating",
        "stack_name": "test-stack-name",
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    import mcp_server.lambda_functions as mcp_module

    set_auth_user("admin-user", [], True)

    response = mcp_module.delete_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "cannot delete server" in get_error_message(body).lower()

    # Reset mocks


def test_delete_hosted_mcp_server_invalid_status_deleting(mcp_servers_table, lambda_context, mock_auth):
    """Test that deleting a server with status 'Deleting' fails."""
    server_item = {
        "id": "test-server-id",
        "name": "Test Hosted MCP Server",
        "status": "Deleting",
        "stack_name": "test-stack-name",
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    import mcp_server.lambda_functions as mcp_module

    set_auth_user("admin-user", [], True)

    response = mcp_module.delete_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "cannot delete server" in get_error_message(body).lower()

    # Reset mocks


def test_delete_hosted_mcp_server_valid_status_stopped(mcp_servers_table, lambda_context, mock_auth):
    """Test that deleting a server with status 'Stopped' succeeds."""
    server_item = {
        "id": "test-server-id",
        "name": "Test Hosted MCP Server",
        "status": "Stopped",
        "stack_name": "test-stack-name",
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    with patch.dict(
        os.environ,
        {"DELETE_MCP_SERVER_SFN_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:DeleteTestStateMachine"},
    ):
        import mcp_server.lambda_functions as mcp_module

        mock_sfn_client = MagicMock()
        mock_sfn_client.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123456789012:execution:DeleteTestStateMachine:test-execution"
        }

        original_stepfunctions = mcp_module.stepfunctions
        mcp_module.stepfunctions = mock_sfn_client

        try:
            set_auth_user("admin-user", [], True)

            response = mcp_module.delete_hosted_mcp_server(event, lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert "Deletion initiated" in body["message"]

            mock_sfn_client.start_execution.assert_called_once()
        finally:
            mcp_module.stepfunctions = original_stepfunctions


def test_delete_hosted_mcp_server_valid_status_failed(mcp_servers_table, lambda_context, mock_auth):
    """Test that deleting a server with status 'Failed' succeeds."""
    server_item = {
        "id": "test-server-id",
        "name": "Test Hosted MCP Server",
        "status": "Failed",
        "stack_name": "test-stack-name",
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    with patch.dict(
        os.environ,
        {"DELETE_MCP_SERVER_SFN_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:DeleteTestStateMachine"},
    ):
        import mcp_server.lambda_functions as mcp_module

        mock_sfn_client = MagicMock()
        mock_sfn_client.start_execution.return_value = {
            "executionArn": "arn:aws:states:us-east-1:123456789012:execution:DeleteTestStateMachine:test-execution"
        }

        original_stepfunctions = mcp_module.stepfunctions
        mcp_module.stepfunctions = mock_sfn_client

        try:
            set_auth_user("admin-user", [], True)

            response = mcp_module.delete_hosted_mcp_server(event, lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert "Deletion initiated" in body["message"]

            mock_sfn_client.start_execution.assert_called_once()
        finally:
            mcp_module.stepfunctions = original_stepfunctions


def test_list_hosted_mcp_servers_success(mcp_servers_table, sample_hosted_mcp_server, lambda_context, mock_auth):
    """Test successful listing of hosted MCP servers."""
    # Add some hosted servers
    mcp_servers_table.put_item(Item=sample_hosted_mcp_server)
    another_server = sample_hosted_mcp_server.copy()
    another_server["id"] = "hosted-server-id-2"
    another_server["name"] = "Another Hosted Server"
    mcp_servers_table.put_item(Item=another_server)

    event = {"requestContext": {"authorizer": {"claims": {"username": "admin-user"}}}}

    set_auth_user("admin-user", [], True)

    response = list_hosted_mcp_servers(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "Items" in body
    assert len(body["Items"]) == 2

    # Reset mocks


def test_list_hosted_mcp_servers_empty(mcp_servers_table, lambda_context, mock_auth):
    """Test listing hosted MCP servers when table is empty."""
    event = {"requestContext": {"authorizer": {"claims": {"username": "admin-user"}}}}

    set_auth_user("admin-user", [], True)

    response = list_hosted_mcp_servers(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "Items" in body
    assert len(body["Items"]) == 0

    # Reset mocks


def test_list_hosted_mcp_servers_not_admin(mcp_servers_table, lambda_context, mock_auth):
    """Test that non-admin cannot list hosted MCP servers."""
    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    response = list_hosted_mcp_servers(event, lambda_context)
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert "Not authorized to list hosted MCP servers" in get_error_message(body)


def test_get_hosted_mcp_server_success(mcp_servers_table, sample_hosted_mcp_server, lambda_context, mock_auth):
    """Test successful retrieval of hosted MCP server."""
    mcp_servers_table.put_item(Item=sample_hosted_mcp_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "hosted-server-id"},
    }

    set_auth_user("admin-user", [], True)

    response = get_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "hosted-server-id"
    assert body["name"] == "Test Hosted MCP Server"
    assert body["startCommand"] == "python server.py"

    # Reset mocks


def test_get_hosted_mcp_server_not_found(mcp_servers_table, lambda_context, mock_auth):
    """Test hosted MCP server not found error."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "non-existent-server"},
    }

    set_auth_user("admin-user", [], True)

    response = get_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "Hosted MCP Server non-existent-server not found" in get_error_message(body)

    # Reset mocks


def test_get_hosted_mcp_server_not_admin(mcp_servers_table, sample_hosted_mcp_server, lambda_context, mock_auth):
    """Test that non-admin cannot get hosted MCP server."""
    mcp_servers_table.put_item(Item=sample_hosted_mcp_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "hosted-server-id"},
    }

    response = get_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    assert "Not authorized to get hosted MCP server" in get_error_message(body)


def test_list_hosted_mcp_servers_pagination(mcp_servers_table, sample_hosted_mcp_server, lambda_context, mock_auth):
    """Test pagination handling in list_hosted_mcp_servers."""
    # Create multiple servers
    for i in range(5):
        server = sample_hosted_mcp_server.copy()
        server["id"] = f"hosted-server-{i}"
        server["name"] = f"Hosted Server {i}"
        mcp_servers_table.put_item(Item=server)

    event = {"requestContext": {"authorizer": {"claims": {"username": "admin-user"}}}}

    set_auth_user("admin-user", [], True)

    response = list_hosted_mcp_servers(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "Items" in body
    assert len(body["Items"]) == 5

    # Reset mocks


# ============================================================================
# Hosted MCP Server Update Tests
# ============================================================================


def test_update_hosted_mcp_server_enable_success(mcp_servers_table, lambda_context, mock_auth):
    """Test enabling a stopped hosted MCP server."""
    server_item = {
        "id": "hosted-server-id",
        "name": "Test Hosted MCP Server",
        "owner": "admin-user",
        "status": "Stopped",
        "stack_name": "test-stack",
        "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 2},
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "hosted-server-id"},
        "body": json.dumps({"enabled": True}),
    }

    with patch.dict(os.environ, {"UPDATE_MCP_SERVER_SFN_ARN": "arn:aws:states:us-east-1:123:stateMachine:Update"}):
        import mcp_server.lambda_functions as mcp_module

        mock_sfn_client = MagicMock()
        original_stepfunctions = mcp_module.stepfunctions
        mcp_module.stepfunctions = mock_sfn_client
        try:
            set_auth_user("admin-user", [], True)
            response = mcp_module.update_hosted_mcp_server(event, lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["id"] == "hosted-server-id"

            mock_sfn_client.start_execution.assert_called_once()
            call_args = mock_sfn_client.start_execution.call_args
            payload = json.loads(call_args[1]["input"])
            assert payload["server_id"] == "hosted-server-id"
            assert payload["update_payload"]["enabled"] is True
        finally:
            mcp_module.stepfunctions = original_stepfunctions


def test_update_hosted_mcp_server_autoscaling_mutually_exclusive(mcp_servers_table, lambda_context, mock_auth):
    """Test that enabled and autoScalingConfig cannot be updated together."""
    server_item = {
        "id": "hosted-server-id",
        "name": "Test Hosted MCP Server",
        "owner": "admin-user",
        "status": "Stopped",
        "stack_name": "test-stack",
        "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 2},
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "hosted-server-id"},
        "body": json.dumps({"enabled": True, "autoScalingConfig": {"minCapacity": 2}}),
    }

    set_auth_user("admin-user", [], True)
    response = update_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "must happen in separate requests" in get_error_message(body)


def test_update_hosted_mcp_server_autoscaling_requires_stack(mcp_servers_table, lambda_context, mock_auth):
    """Test that autoscaling update requires a CloudFormation stack."""
    server_item = {
        "id": "hosted-server-id",
        "name": "Test Hosted MCP Server",
        "owner": "admin-user",
        "status": "InService",
        # no stack_name
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "hosted-server-id"},
        "body": json.dumps({"autoScalingConfig": {"minCapacity": 2}}),
    }

    set_auth_user("admin-user", [], True)
    response = update_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "does not have a CloudFormation stack" in get_error_message(body)


def test_update_hosted_mcp_server_not_admin(mcp_servers_table, lambda_context, mock_auth):
    """Test that non-admin cannot update hosted MCP server."""
    server_item = {
        "id": "hosted-server-id",
        "name": "Test Hosted MCP Server",
        "owner": "admin-user",
        "status": "Stopped",
        "stack_name": "test-stack",
        "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 2},
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "hosted-server-id"},
        "body": json.dumps({"enabled": True}),
    }

    set_auth_user("test-user", [], False)
    response = update_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 403
    body = json.loads(response["body"])
    # Real api_wrapper returns error message as a string (JSON-encoded), not a dict
    error_msg = body if isinstance(body, str) else body.get("error", "")
    assert "Not authorized" in error_msg


def test_update_hosted_mcp_server_not_found(mcp_servers_table, lambda_context, mock_auth):
    """Test updating non-existent hosted MCP server."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "missing"},
        "body": json.dumps({"enabled": True}),
    }

    set_auth_user("admin-user", [], True)
    response = update_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "not found" in get_error_message(body).lower()
