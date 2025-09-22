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
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": str(e)}),
            }

    return wrapper


# Create mock modules
mock_common = MagicMock()
mock_common.get_username.return_value = "test-user"
mock_common.is_admin.return_value = False
mock_common.retry_config = retry_config
mock_common.api_wrapper = mock_api_wrapper

# Create mock create_env_variables
mock_create_env = MagicMock()

# Setup patches without .start() to avoid global interference
patches = [
    patch.dict("sys.modules", {"create_env_variables": mock_create_env}),
    patch("utilities.auth.get_username", mock_common.get_username),
    patch("utilities.auth.is_admin", mock_common.is_admin),
    patch("utilities.common_functions.retry_config", retry_config),
    patch("utilities.common_functions.api_wrapper", mock_api_wrapper),
]

# Start patches
for p in patches:
    p.start()

# Now import the lambda functions
from mcp_server.lambda_functions import _get_mcp_servers, create, delete, get, get_mcp_server_id, list, update

# Stop patches to avoid global interference
for p in patches:
    p.stop()


@pytest.fixture(autouse=True)
def setup_mcp_mocks():
    """Setup mocks for MCP server tests with proper cleanup."""
    patches = [
        patch("utilities.auth.get_username", mock_common.get_username),
        patch("utilities.auth.is_admin", mock_common.is_admin),
        patch("utilities.common_functions.retry_config", retry_config),
        patch("utilities.common_functions.api_wrapper", mock_api_wrapper),
    ]

    for p in patches:
        p.start()

    yield

    for p in patches:
        p.stop()


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


def test_get_mcp_server_success(mcp_servers_table, sample_mcp_server, lambda_context):
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


def test_get_global_mcp_server_success(mcp_servers_table, sample_global_mcp_server, lambda_context):
    """Test successful retrieval of global MCP server by any user."""
    mcp_servers_table.put_item(Item=sample_global_mcp_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "any-user"}}},
        "pathParameters": {"serverId": "global-server-id"},
    }

    mock_common.get_username.return_value = "any-user"

    response = get(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "global-server-id"
    assert body["owner"] == "lisa:public"
    assert body["isOwner"] is True

    # Reset mock
    mock_common.get_username.return_value = "test-user"


def test_get_mcp_server_admin_access(mcp_servers_table, sample_mcp_server, lambda_context):
    """Test admin can access any MCP server."""
    # Create a server owned by different user
    other_user_server = sample_mcp_server.copy()
    other_user_server["owner"] = "other-user"
    mcp_servers_table.put_item(Item=other_user_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    mock_common.get_username.return_value = "admin-user"
    mock_common.is_admin.return_value = True

    response = get(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "test-server-id"
    assert "isOwner" not in body  # Admin doesn't get isOwner flag

    # Reset mocks
    mock_common.get_username.return_value = "test-user"
    mock_common.is_admin.return_value = False


def test_get_mcp_server_not_found(mcp_servers_table, lambda_context):
    """Test MCP server not found error."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "non-existent-server"},
    }

    response = get(event, lambda_context)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "MCP Server non-existent-server not found" in body["error"]


def test_get_mcp_server_not_authorized(mcp_servers_table, sample_mcp_server, lambda_context):
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
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Not authorized to get test-server-id" in body["error"]


def test_list_mcp_servers_regular_user(mcp_servers_table, sample_mcp_server, lambda_context):
    """Test listing MCP servers for regular user."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    response = list(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "Items" in body


def test_list_mcp_servers_admin(mcp_servers_table, sample_mcp_server, lambda_context):
    """Test listing MCP servers for admin user."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    event = {"requestContext": {"authorizer": {"claims": {"username": "admin-user"}}}}

    mock_common.get_username.return_value = "admin-user"
    mock_common.is_admin.return_value = True

    response = list(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "Items" in body

    # Reset mocks
    mock_common.get_username.return_value = "test-user"
    mock_common.is_admin.return_value = False


def test_create_mcp_server_success(mcp_servers_table, lambda_context):
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


def test_create_mcp_server_with_owner(mcp_servers_table, lambda_context):
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


def test_update_mcp_server_success(mcp_servers_table, sample_mcp_server, lambda_context):
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


def test_update_mcp_server_admin_access(mcp_servers_table, sample_mcp_server, lambda_context):
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

    mock_common.get_username.return_value = "admin-user"
    mock_common.is_admin.return_value = True

    response = update(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["name"] == "Admin Updated Server"

    # Reset mocks
    mock_common.get_username.return_value = "test-user"
    mock_common.is_admin.return_value = False


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
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "URL id test-server-id doesn't match body id different-server-id" in body["error"]


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
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "not found" in body["error"]


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
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Not authorized to update test-server-id" in body["error"]


def test_delete_mcp_server_success(mcp_servers_table, sample_mcp_server, lambda_context):
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


def test_delete_mcp_server_admin_access(mcp_servers_table, sample_mcp_server, lambda_context):
    """Test admin can delete any MCP server."""
    # Create a server owned by different user
    other_user_server = sample_mcp_server.copy()
    other_user_server["owner"] = "other-user"
    mcp_servers_table.put_item(Item=other_user_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
    }

    mock_common.get_username.return_value = "admin-user"
    mock_common.is_admin.return_value = True

    response = delete(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "ok"

    # Reset mocks
    mock_common.get_username.return_value = "test-user"
    mock_common.is_admin.return_value = False


def test_delete_mcp_server_not_found(mcp_servers_table, lambda_context):
    """Test deletion of non-existent MCP server."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "non-existent-server"},
    }

    response = delete(event, lambda_context)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "MCP Server non-existent-server not found" in body["error"]


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
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Not authorized to delete test-server-id" in body["error"]


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


def test_create_mcp_server_invalid_json(lambda_context):
    """Test create with invalid JSON body."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "body": "invalid-json",
    }

    response = create(event, lambda_context)
    assert response["statusCode"] == 500
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
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body


def test_update_mcp_server_invalid_json(mcp_servers_table, sample_mcp_server, lambda_context):
    """Test update with invalid JSON body."""
    mcp_servers_table.put_item(Item=sample_mcp_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "test-server-id"},
        "body": "invalid-json",
    }

    response = update(event, lambda_context)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body


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


def test_get_mcp_server_global_non_owner_access(mcp_servers_table, sample_global_mcp_server, lambda_context):
    """Test that non-owner can access global MCP server."""
    mcp_servers_table.put_item(Item=sample_global_mcp_server)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
        "pathParameters": {"serverId": "global-server-id"},
    }

    mock_common.get_username.return_value = "different-user"

    response = get(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "global-server-id"
    assert body["owner"] == "lisa:public"
    assert body["isOwner"] is True  # Global servers are accessible to everyone

    # Reset mock
    mock_common.get_username.return_value = "test-user"


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
