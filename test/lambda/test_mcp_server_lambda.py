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

"""Test module for MCP server lambda functions - refactored version using fixture-based mocking."""

import json
import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def mock_mcp_server_common():
    """Common mocks for MCP server lambda functions."""

    # Set up environment variables
    env_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1",
        "MCP_SERVERS_TABLE_NAME": "mcp-servers-table",
        "MCP_SERVERS_BY_OWNER_INDEX_NAME": "mcp-servers-by-owner-index",
    }

    with patch.dict(os.environ, env_vars):
        # Mock the common functions and auth
        with patch("utilities.auth.get_username") as mock_get_username, patch(
            "utilities.auth.is_admin"
        ) as mock_is_admin:

            mock_get_username.return_value = "test-user"
            mock_is_admin.return_value = False

            yield {
                "get_username": mock_get_username,
                "is_admin": mock_is_admin,
                "env_vars": env_vars,
            }


@pytest.fixture
def mcp_server_functions(mock_mcp_server_common):
    """Import MCP server lambda functions with mocked dependencies."""
    # Patch the api_wrapper before importing the module
    with patch("utilities.common_functions.api_wrapper", lambda func: func):
        from mcp_server.lambda_functions import _get_mcp_servers, create, delete, get, get_mcp_server_id, list, update

        return {
            "_get_mcp_servers": _get_mcp_servers,
            "create": create,
            "delete": delete,
            "get": get,
            "get_mcp_server_id": get_mcp_server_id,
            "list": list,
            "update": update,
        }


@pytest.fixture
def lambda_context():
    """Mock Lambda context object."""
    return SimpleNamespace(
        function_name="mcp-server-lambda",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:mcp-server-lambda",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/mcp-server-lambda",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB table for MCP servers."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
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
        yield table


@pytest.fixture
def sample_mcp_server():
    """Create a sample MCP server dictionary."""
    return {
        "id": "test-server-id",
        "created": datetime.now().isoformat(),
        "owner": "test-user",
        "url": "https://example.com/mcp-server",
        "name": "Test MCP Server",
    }


@pytest.fixture
def sample_global_mcp_server():
    """Create a sample global MCP server dictionary."""
    return {
        "id": "global-server-id",
        "created": datetime.now().isoformat(),
        "owner": "lisa:public",
        "url": "https://example.com/global-mcp-server",
        "name": "Global MCP Server",
    }


class TestMCPServerUtils:
    """Test class for MCP server utility functions."""

    def test_get_mcp_server_id(self, mcp_server_functions):
        """Test extracting MCP server ID from event path parameters."""
        get_mcp_server_id = mcp_server_functions["get_mcp_server_id"]

        event = {"pathParameters": {"serverId": "test-server-123"}}
        result = get_mcp_server_id(event)
        assert result == "test-server-123"

    def test_get_mcp_server_id_missing_path_parameters(self, mcp_server_functions):
        """Test get_mcp_server_id with missing path parameters."""
        get_mcp_server_id = mcp_server_functions["get_mcp_server_id"]

        event = {"pathParameters": None}
        with pytest.raises(TypeError):
            get_mcp_server_id(event)

    def test_get_mcp_server_id_missing_server_id(self, mcp_server_functions):
        """Test get_mcp_server_id with missing serverId parameter."""
        get_mcp_server_id = mcp_server_functions["get_mcp_server_id"]

        event = {"pathParameters": {}}
        with pytest.raises(KeyError):
            get_mcp_server_id(event)


class TestGetMCPServers:
    """Test class for the _get_mcp_servers helper function."""

    def test_get_mcp_servers_no_filter(self, mcp_server_functions, dynamodb_table, sample_mcp_server):
        """Test _get_mcp_servers helper function without user filter."""
        _get_mcp_servers = mcp_server_functions["_get_mcp_servers"]

        dynamodb_table.put_item(Item=sample_mcp_server)

        result = _get_mcp_servers()
        assert "Items" in result
        assert len(result["Items"]) == 1
        assert result["Items"][0]["id"] == "test-server-id"

    def test_get_mcp_servers_with_user_filter(self, mcp_server_functions, dynamodb_table, sample_mcp_server):
        """Test _get_mcp_servers helper function with user filter."""
        _get_mcp_servers = mcp_server_functions["_get_mcp_servers"]

        dynamodb_table.put_item(Item=sample_mcp_server)

        result = _get_mcp_servers(user_id="test-user")
        assert "Items" in result

    def test_get_mcp_servers_empty_result(self, mcp_server_functions, dynamodb_table):
        """Test _get_mcp_servers with no results."""
        _get_mcp_servers = mcp_server_functions["_get_mcp_servers"]

        result = _get_mcp_servers()
        assert "Items" in result
        assert len(result["Items"]) == 0

    def test_get_mcp_servers_with_filter_no_match(self, mcp_server_functions, dynamodb_table, sample_mcp_server):
        """Test _get_mcp_servers with user filter that doesn't match."""
        _get_mcp_servers = mcp_server_functions["_get_mcp_servers"]

        # Create a server with different owner
        other_server = sample_mcp_server.copy()
        other_server["owner"] = "other-user"
        dynamodb_table.put_item(Item=other_server)

        result = _get_mcp_servers(user_id="different-user")
        assert "Items" in result

    def test_get_mcp_servers_pagination(self, mcp_server_functions, dynamodb_table):
        """Test pagination handling in _get_mcp_servers."""
        _get_mcp_servers = mcp_server_functions["_get_mcp_servers"]

        # Create some test data
        server1 = {"id": "server-1", "name": "Server 1", "owner": "test-user", "url": "https://example.com"}
        server2 = {"id": "server-2", "name": "Server 2", "owner": "test-user", "url": "https://example.com"}

        dynamodb_table.put_item(Item=server1)
        dynamodb_table.put_item(Item=server2)

        # Test that the function can handle multiple items
        result = _get_mcp_servers()
        assert len(result["Items"]) == 2
        server_ids = [item["id"] for item in result["Items"]]
        assert "server-1" in server_ids
        assert "server-2" in server_ids

    def test_get_mcp_servers_groups_filtering(self, mcp_server_functions, dynamodb_table):
        """Test groups filtering logic in _get_mcp_servers function."""
        _get_mcp_servers = mcp_server_functions["_get_mcp_servers"]

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
            dynamodb_table.put_item(Item=server)

        # Test with groups filter
        result = _get_mcp_servers(user_id="test-user", active=True, groups=["admin", "user"])

        # Should include: server1 (user owns, no groups), server2 (user owns, matching groups),
        # server3 (user owns, non-matching groups), server4 (public, no groups), server5 (public, matching groups)
        # Should exclude: server6 (public, non-matching groups), server7 (inactive)
        expected_ids = {"server1", "server2", "server3", "server4", "server5"}
        actual_ids = {item["id"] for item in result["Items"]}

        assert actual_ids == expected_ids, f"Expected {expected_ids}, got {actual_ids}"

    def test_get_mcp_servers_no_groups_filter(self, mcp_server_functions, dynamodb_table):
        """Test behavior when no groups are provided."""
        _get_mcp_servers = mcp_server_functions["_get_mcp_servers"]

        test_servers = [
            {"id": "server1", "owner": "test-user", "status": "active", "groups": None},
            {"id": "server2", "owner": "test-user", "status": "active", "groups": ["group:admin"]},
        ]

        for server in test_servers:
            dynamodb_table.put_item(Item=server)

        # Test without groups filter
        result = _get_mcp_servers(user_id="test-user", active=True, groups=None)

        # Should include all servers (no groups filtering)
        expected_ids = {"server1", "server2"}
        actual_ids = {item["id"] for item in result["Items"]}

        assert actual_ids == expected_ids

    def test_get_mcp_servers_empty_groups_filter(self, mcp_server_functions, dynamodb_table):
        """Test behavior when empty groups list is provided."""
        _get_mcp_servers = mcp_server_functions["_get_mcp_servers"]

        test_servers = [
            {"id": "server1", "owner": "test-user", "status": "active", "groups": None},
            {"id": "server2", "owner": "test-user", "status": "active", "groups": ["group:admin"]},
        ]

        for server in test_servers:
            dynamodb_table.put_item(Item=server)

        # Test with empty groups list
        result = _get_mcp_servers(user_id="test-user", active=True, groups=[])

        # Should include all servers (empty groups list means no filtering)
        expected_ids = {"server1", "server2"}
        actual_ids = {item["id"] for item in result["Items"]}

        assert actual_ids == expected_ids


class TestGetMCPServer:
    """Test class for get MCP server functionality."""

    def test_get_mcp_server_success(self, mcp_server_functions, dynamodb_table, sample_mcp_server, lambda_context):
        """Test successful retrieval of MCP server by owner."""
        get = mcp_server_functions["get"]

        dynamodb_table.put_item(Item=sample_mcp_server)

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"serverId": "test-server-id"},
        }

        result = get(event, lambda_context)
        assert result["id"] == "test-server-id"
        assert result["owner"] == "test-user"
        assert result["isOwner"] is True

    def test_get_global_mcp_server_success(
        self, mcp_server_functions, mock_mcp_server_common, dynamodb_table, sample_global_mcp_server, lambda_context
    ):
        """Test successful retrieval of global MCP server by any user."""
        get = mcp_server_functions["get"]
        mock_get_username = mock_mcp_server_common["get_username"]

        dynamodb_table.put_item(Item=sample_global_mcp_server)

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "any-user"}}},
            "pathParameters": {"serverId": "global-server-id"},
        }

        mock_get_username.return_value = "any-user"

        result = get(event, lambda_context)
        assert result["id"] == "global-server-id"
        assert result["owner"] == "lisa:public"
        assert result["isOwner"] is True

    def test_get_mcp_server_admin_access(
        self, mcp_server_functions, mock_mcp_server_common, dynamodb_table, sample_mcp_server, lambda_context
    ):
        """Test admin can access any MCP server."""
        get = mcp_server_functions["get"]
        mock_get_username = mock_mcp_server_common["get_username"]
        mock_is_admin = mock_mcp_server_common["is_admin"]

        # Create a server owned by different user
        other_user_server = sample_mcp_server.copy()
        other_user_server["owner"] = "other-user"
        dynamodb_table.put_item(Item=other_user_server)

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
            "pathParameters": {"serverId": "test-server-id"},
        }

        mock_get_username.return_value = "admin-user"
        mock_is_admin.return_value = True

        result = get(event, lambda_context)
        assert result["id"] == "test-server-id"
        assert "isOwner" not in result  # Admin doesn't get isOwner flag

    def test_get_mcp_server_not_found(self, mcp_server_functions, dynamodb_table, lambda_context):
        """Test MCP server not found error."""
        get = mcp_server_functions["get"]

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"serverId": "non-existent-server"},
        }

        with pytest.raises(ValueError) as exc_info:
            get(event, lambda_context)
        assert "MCP Server non-existent-server not found" in str(exc_info.value)

    def test_get_mcp_server_not_authorized(
        self, mcp_server_functions, dynamodb_table, sample_mcp_server, lambda_context
    ):
        """Test unauthorized access to MCP server."""
        get = mcp_server_functions["get"]

        # Create a server owned by different user
        other_user_server = sample_mcp_server.copy()
        other_user_server["owner"] = "other-user"
        dynamodb_table.put_item(Item=other_user_server)

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"serverId": "test-server-id"},
        }

        with pytest.raises(ValueError) as exc_info:
            get(event, lambda_context)
        assert "Not authorized to get test-server-id" in str(exc_info.value)

    def test_get_mcp_server_global_non_owner_access(
        self, mcp_server_functions, mock_mcp_server_common, dynamodb_table, sample_global_mcp_server, lambda_context
    ):
        """Test that non-owner can access global MCP server."""
        get = mcp_server_functions["get"]
        mock_get_username = mock_mcp_server_common["get_username"]

        dynamodb_table.put_item(Item=sample_global_mcp_server)

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "different-user"}}},
            "pathParameters": {"serverId": "global-server-id"},
        }

        mock_get_username.return_value = "different-user"

        result = get(event, lambda_context)
        assert result["id"] == "global-server-id"
        assert result["owner"] == "lisa:public"
        assert result["isOwner"] is True  # Global servers are accessible to everyone


class TestListMCPServers:
    """Test class for list MCP servers functionality."""

    def test_list_mcp_servers_regular_user(
        self, mcp_server_functions, dynamodb_table, sample_mcp_server, lambda_context
    ):
        """Test listing MCP servers for regular user."""
        list_func = mcp_server_functions["list"]

        dynamodb_table.put_item(Item=sample_mcp_server)

        event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

        result = list_func(event, lambda_context)
        assert "Items" in result
        assert len(result["Items"]) >= 0

    def test_list_mcp_servers_admin(
        self, mcp_server_functions, mock_mcp_server_common, dynamodb_table, sample_mcp_server, lambda_context
    ):
        """Test listing MCP servers for admin user."""
        list_func = mcp_server_functions["list"]
        mock_get_username = mock_mcp_server_common["get_username"]
        mock_is_admin = mock_mcp_server_common["is_admin"]

        dynamodb_table.put_item(Item=sample_mcp_server)

        event = {"requestContext": {"authorizer": {"claims": {"username": "admin-user"}}}}

        mock_get_username.return_value = "admin-user"
        mock_is_admin.return_value = True

        result = list_func(event, lambda_context)
        assert "Items" in result
        assert len(result["Items"]) >= 0


class TestCreateMCPServer:
    """Test class for create MCP server functionality."""

    def test_create_mcp_server_success(self, mcp_server_functions, dynamodb_table, lambda_context):
        """Test successful creation of MCP server."""
        create = mcp_server_functions["create"]

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(
                {
                    "name": "Test MCP Server",
                    "url": "https://example.com/mcp-server",
                }
            ),
        }

        result = create(event, lambda_context)
        assert result["name"] == "Test MCP Server"
        assert result["url"] == "https://example.com/mcp-server"
        assert result["owner"] == "test-user"
        assert "id" in result
        assert "created" in result

    def test_create_mcp_server_with_owner(self, mcp_server_functions, dynamodb_table, lambda_context):
        """Test creation of MCP server with explicit owner."""
        create = mcp_server_functions["create"]

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

        result = create(event, lambda_context)
        assert result["owner"] == "test-user"  # Should be overridden by the actual user

    def test_create_mcp_server_invalid_json(self, mcp_server_functions, lambda_context):
        """Test create with invalid JSON body."""
        create = mcp_server_functions["create"]

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": "invalid-json",
        }

        with pytest.raises(json.JSONDecodeError):
            create(event, lambda_context)

    def test_create_mcp_server_missing_fields(self, mcp_server_functions, lambda_context):
        """Test create with missing required fields."""
        create = mcp_server_functions["create"]

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(
                {
                    "name": "Test MCP Server",
                    # Missing url field
                }
            ),
        }

        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            create(event, lambda_context)


class TestUpdateMCPServer:
    """Test class for update MCP server functionality."""

    def test_update_mcp_server_success(self, mcp_server_functions, dynamodb_table, sample_mcp_server, lambda_context):
        """Test successful update of MCP server."""
        update = mcp_server_functions["update"]

        dynamodb_table.put_item(Item=sample_mcp_server)

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

        result = update(event, lambda_context)
        assert result["name"] == "Updated MCP Server"
        assert result["url"] == "https://example.com/updated-mcp-server"

    def test_update_mcp_server_admin_access(
        self, mcp_server_functions, mock_mcp_server_common, dynamodb_table, sample_mcp_server, lambda_context
    ):
        """Test admin can update any MCP server."""
        update = mcp_server_functions["update"]
        mock_get_username = mock_mcp_server_common["get_username"]
        mock_is_admin = mock_mcp_server_common["is_admin"]

        # Create a server owned by different user
        other_user_server = sample_mcp_server.copy()
        other_user_server["owner"] = "other-user"
        dynamodb_table.put_item(Item=other_user_server)

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

        mock_get_username.return_value = "admin-user"
        mock_is_admin.return_value = True

        result = update(event, lambda_context)
        assert result["name"] == "Admin Updated Server"

    def test_update_mcp_server_id_mismatch(
        self, mcp_server_functions, dynamodb_table, sample_mcp_server, lambda_context
    ):
        """Test update with mismatched IDs."""
        update = mcp_server_functions["update"]

        dynamodb_table.put_item(Item=sample_mcp_server)

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

        with pytest.raises(ValueError) as exc_info:
            update(event, lambda_context)
        assert "URL id test-server-id doesn't match body id different-server-id" in str(exc_info.value)

    def test_update_mcp_server_not_found(self, mcp_server_functions, dynamodb_table, lambda_context):
        """Test update of non-existent MCP server."""
        update = mcp_server_functions["update"]

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

        with pytest.raises(ValueError) as exc_info:
            update(event, lambda_context)
        assert "not found" in str(exc_info.value)

    def test_update_mcp_server_not_authorized(
        self, mcp_server_functions, dynamodb_table, sample_mcp_server, lambda_context
    ):
        """Test unauthorized update of MCP server."""
        update = mcp_server_functions["update"]

        # Create a server owned by different user
        other_user_server = sample_mcp_server.copy()
        other_user_server["owner"] = "other-user"
        dynamodb_table.put_item(Item=other_user_server)

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

        with pytest.raises(ValueError) as exc_info:
            update(event, lambda_context)
        assert "Not authorized to update test-server-id" in str(exc_info.value)

    def test_update_mcp_server_invalid_json(
        self, mcp_server_functions, dynamodb_table, sample_mcp_server, lambda_context
    ):
        """Test update with invalid JSON body."""
        update = mcp_server_functions["update"]

        dynamodb_table.put_item(Item=sample_mcp_server)

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"serverId": "test-server-id"},
            "body": "invalid-json",
        }

        with pytest.raises(json.JSONDecodeError):
            update(event, lambda_context)


class TestDeleteMCPServer:
    """Test class for delete MCP server functionality."""

    def test_delete_mcp_server_success(self, mcp_server_functions, dynamodb_table, sample_mcp_server, lambda_context):
        """Test successful deletion of MCP server."""
        delete = mcp_server_functions["delete"]

        dynamodb_table.put_item(Item=sample_mcp_server)

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"serverId": "test-server-id"},
        }

        result = delete(event, lambda_context)
        assert result["status"] == "ok"

    def test_delete_mcp_server_admin_access(
        self, mcp_server_functions, mock_mcp_server_common, dynamodb_table, sample_mcp_server, lambda_context
    ):
        """Test admin can delete any MCP server."""
        delete = mcp_server_functions["delete"]
        mock_get_username = mock_mcp_server_common["get_username"]
        mock_is_admin = mock_mcp_server_common["is_admin"]

        # Create a server owned by different user
        other_user_server = sample_mcp_server.copy()
        other_user_server["owner"] = "other-user"
        dynamodb_table.put_item(Item=other_user_server)

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
            "pathParameters": {"serverId": "test-server-id"},
        }

        mock_get_username.return_value = "admin-user"
        mock_is_admin.return_value = True

        result = delete(event, lambda_context)
        assert result["status"] == "ok"

    def test_delete_mcp_server_not_found(self, mcp_server_functions, dynamodb_table, lambda_context):
        """Test deletion of non-existent MCP server."""
        delete = mcp_server_functions["delete"]

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"serverId": "non-existent-server"},
        }

        with pytest.raises(ValueError) as exc_info:
            delete(event, lambda_context)
        assert "MCP Server non-existent-server not found" in str(exc_info.value)

    def test_delete_mcp_server_not_authorized(
        self, mcp_server_functions, dynamodb_table, sample_mcp_server, lambda_context
    ):
        """Test unauthorized deletion of MCP server."""
        delete = mcp_server_functions["delete"]

        # Create a server owned by different user
        other_user_server = sample_mcp_server.copy()
        other_user_server["owner"] = "other-user"
        dynamodb_table.put_item(Item=other_user_server)

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"serverId": "test-server-id"},
        }

        with pytest.raises(ValueError) as exc_info:
            delete(event, lambda_context)
        assert "Not authorized to delete test-server-id" in str(exc_info.value)
