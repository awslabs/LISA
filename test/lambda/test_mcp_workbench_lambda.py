"""Test module for MCP workbench lambda functions - using fixture-based mocking with strong isolation."""

import json
import os
import pytest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from moto import mock_aws
import boto3
import botocore.exceptions


# Module-level isolation to prevent global mock interference
@pytest.fixture(scope="session", autouse=True)
def isolate_mcp_workbench_tests():
    """Session-scoped fixture to isolate MCP workbench tests from global mocks."""
    # Stop any existing patches that might interfere with moto
    try:
        patch.stopall()  # Stop all active patches
    except Exception:
        pass  # No patches to stop or error occurred
    
    yield
    
    # Clean up after tests
    try:
        patch.stopall()
    except Exception:
        pass


@pytest.fixture
def mock_mcp_workbench_common():
    """Common mocks for MCP workbench lambda functions with strong isolation."""
    
    # Set up environment variables
    env_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing", 
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1",
        "WORKBENCH_BUCKET": "workbench-bucket",
    }
    
    with patch.dict(os.environ, env_vars):
        # Create completely isolated auth mocks that override any global ones
        with patch("utilities.auth.get_username", return_value="test-user") as mock_get_username, \
             patch("utilities.auth.is_admin", return_value=False) as mock_is_admin_util, \
             patch("mcp_workbench.lambda_functions.is_admin", return_value=False) as mock_is_admin_module:
            
            yield {
                "get_username": mock_get_username,
                "is_admin": mock_is_admin_module,  # Return the module-level mock
                "env_vars": env_vars,
            }


@pytest.fixture
def mcp_workbench_functions():
    """Import MCP workbench lambda functions with mocked dependencies."""
    # Only patch the api_wrapper to bypass it - avoid patching boto3.client globally
    with patch('utilities.common_functions.api_wrapper', lambda func: func):
        from mcp_workbench.lambda_functions import (
            MCPToolModel,
            _get_tool_from_s3,
            create,
            delete,
            list,
            read, 
            update,
        )
        
        return {
            "MCPToolModel": MCPToolModel,
            "_get_tool_from_s3": _get_tool_from_s3,
            "create": create,
            "delete": delete,
            "list": list,
            "read": read,
            "update": update,
        }


@pytest.fixture
def lambda_context():
    """Mock AWS Lambda context."""
    return SimpleNamespace(
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:mcp-workbench-lambda",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/mcp-workbench-lambda",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture
def mock_s3():
    """Create mock S3 environment with moto."""
    with mock_aws():
        # Create S3 client and bucket - must be inside mock_aws context
        s3_client = boto3.client("s3", region_name="us-east-1")
        s3_client.create_bucket(Bucket="workbench-bucket")
        yield s3_client


@pytest.fixture
def sample_tool_content():
    """Sample Python tool content for testing."""
    return """
def hello_world():
    print("Hello, world!")
    return "Hello from MCP Tool"
"""


@pytest.fixture
def sample_tool_id():
    """Sample tool ID for testing."""
    return "test_tool.py"


class TestMCPToolModel:
    """Test class for MCPToolModel."""

    def test_mcp_tool_model_with_py_extension(self, mcp_workbench_functions):
        """Test the MCPToolModel class with .py extension."""
        MCPToolModel = mcp_workbench_functions["MCPToolModel"]
        
        tool = MCPToolModel(id="test_tool.py", contents="print('hello')")
        assert tool.s3_key == "test_tool.py"

    def test_mcp_tool_model_without_py_extension(self, mcp_workbench_functions):
        """Test the MCPToolModel class without .py extension."""
        MCPToolModel = mcp_workbench_functions["MCPToolModel"]
        
        tool = MCPToolModel(id="test_tool", contents="print('hello')")
        assert tool.s3_key == "test_tool.py"

    def test_mcp_tool_model_with_updated_at(self, mcp_workbench_functions):
        """Test the MCPToolModel class with updated_at timestamp."""
        MCPToolModel = mcp_workbench_functions["MCPToolModel"]
        
        timestamp = datetime.now().isoformat()
        tool = MCPToolModel(id="test_tool.py", contents="print('hello')", updated_at=timestamp)
        assert tool.updated_at == timestamp


class TestGetToolFromS3:
    """Test class for _get_tool_from_s3 helper function."""

    def test_get_tool_from_s3_success(self, mcp_workbench_functions, mock_s3, sample_tool_content, sample_tool_id):
        """Test retrieving a tool from S3."""
        _get_tool_from_s3 = mcp_workbench_functions["_get_tool_from_s3"]
        
        # Upload a file to the mocked S3
        mock_s3.put_object(
            Bucket="workbench-bucket",
            Key=sample_tool_id,
            Body=sample_tool_content.encode("utf-8"),
            ContentType="text/x-python",
        )
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            tool = _get_tool_from_s3(sample_tool_id)
        
        # Verify tool properties
        assert tool.id == sample_tool_id
        assert tool.contents == sample_tool_content

    def test_get_tool_from_s3_not_found(self, mcp_workbench_functions, mock_s3):
        """Test retrieving a non-existent tool from S3."""
        from utilities.exceptions import HTTPException
        _get_tool_from_s3 = mcp_workbench_functions["_get_tool_from_s3"]
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            with pytest.raises(HTTPException) as excinfo:
                _get_tool_from_s3("non_existent_tool.py")
        assert "not found" in str(excinfo.value).lower()

    def test_get_tool_from_s3_adds_py_extension(self, mcp_workbench_functions, mock_s3, sample_tool_content):
        """Test retrieving a tool without .py extension."""
        _get_tool_from_s3 = mcp_workbench_functions["_get_tool_from_s3"]
        
        # Upload a file to the mocked S3 with .py extension
        mock_s3.put_object(
            Bucket="workbench-bucket",
            Key="test_tool.py",
            Body=sample_tool_content.encode("utf-8"),
            ContentType="text/x-python",
        )
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            # Request without .py extension
            tool = _get_tool_from_s3("test_tool")
        
        assert tool.id == "test_tool.py"
        assert tool.contents == sample_tool_content


class TestReadTool:
    """Test class for read tool functionality."""

    def test_read_success(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                         sample_tool_content, sample_tool_id, lambda_context):
        """Test successful retrieval of tool."""
        read = mcp_workbench_functions["read"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Upload a file to the mocked S3
        mock_s3.put_object(
            Bucket="workbench-bucket",
            Key=sample_tool_id,
            Body=sample_tool_content.encode("utf-8"),
            ContentType="text/x-python",
        )
        
        # Create the event
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "pathParameters": {"toolId": sample_tool_id},
        }
        
        mock_is_admin.return_value = True
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            response = read(event, lambda_context)
        
        # With api_wrapper bypassed, expect direct return value
        assert response["id"] == sample_tool_id
        assert response["contents"] == sample_tool_content

    def test_read_not_admin(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                           sample_tool_id, lambda_context):
        """Test unauthorized retrieval of tool."""
        read = mcp_workbench_functions["read"]
        mock_get_username = mock_mcp_workbench_common["get_username"]
        
        # Create the event
        event = {
            "requestContext": {"authorizer": {"username": "regular-user"}},
            "pathParameters": {"toolId": sample_tool_id},
        }
        
        mock_get_username.return_value = "regular-user"
        
        # With api_wrapper bypassed, expect direct exception
        with pytest.raises(ValueError) as excinfo:
            read(event, lambda_context)
        assert "Only admin users can access tools" in str(excinfo.value)

    def test_read_not_found(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                           lambda_context):
        """Test reading a non-existent tool."""
        from utilities.exceptions import HTTPException
        read = mcp_workbench_functions["read"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Create the event for a non-existent tool
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "pathParameters": {"toolId": "non_existent_tool.py"},
        }
        
        mock_is_admin.return_value = True
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            # With api_wrapper bypassed, expect direct exception
            with pytest.raises(HTTPException) as excinfo:
                read(event, lambda_context)
        assert "not found" in str(excinfo.value).lower()

    def test_read_missing_tool_id(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                                 lambda_context):
        """Test reading without a toolId parameter."""
        read = mcp_workbench_functions["read"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Create the event with missing pathParameters
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "pathParameters": {},
        }
        
        mock_is_admin.return_value = True
        
        # With api_wrapper bypassed, expect direct exception
        with pytest.raises(ValueError) as excinfo:
            read(event, lambda_context)
        assert "Missing toolId parameter" in str(excinfo.value)


class TestListTools:
    """Test class for list tools functionality."""

    def test_list_success(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                         sample_tool_content, lambda_context):
        """Test successful listing of tools."""
        list_func = mcp_workbench_functions["list"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Upload files to the mocked S3
        mock_s3.put_object(
            Bucket="workbench-bucket", Key="tool1.py", 
            Body=sample_tool_content.encode("utf-8"), ContentType="text/x-python"
        )
        mock_s3.put_object(
            Bucket="workbench-bucket", Key="tool2.py", 
            Body=sample_tool_content.encode("utf-8"), ContentType="text/x-python"
        )
        mock_s3.put_object(
            Bucket="workbench-bucket", Key="not_a_tool.txt", 
            Body=b"This is not a python file", ContentType="text/plain"
        )
        
        # Create the event
        event = {"requestContext": {"authorizer": {"username": "test-admin"}}}
        
        mock_is_admin.return_value = True
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            response = list_func(event, lambda_context)
        
        # With api_wrapper bypassed, expect direct return value
        assert "tools" in response
        assert len(response["tools"]) == 2  # Only the .py files
        
        # Verify the tool ids
        tool_ids = [tool["id"] for tool in response["tools"]]
        assert "tool1.py" in tool_ids
        assert "tool2.py" in tool_ids
        assert "not_a_tool.txt" not in tool_ids

    def test_list_not_admin(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                           lambda_context):
        """Test unauthorized listing of tools."""
        list_func = mcp_workbench_functions["list"]
        mock_get_username = mock_mcp_workbench_common["get_username"]
        
        # Create the event
        event = {"requestContext": {"authorizer": {"username": "regular-user"}}}
        
        mock_get_username.return_value = "regular-user"
        
        # With api_wrapper bypassed, expect direct exception
        with pytest.raises(ValueError) as excinfo:
            list_func(event, lambda_context)
        assert "Only admin users can access tools" in str(excinfo.value)

    def test_list_empty_bucket(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                              lambda_context):
        """Test listing tools in an empty bucket."""
        list_func = mcp_workbench_functions["list"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Create the event (bucket is already empty from mock_s3 fixture)
        event = {"requestContext": {"authorizer": {"username": "test-admin"}}}
        
        mock_is_admin.return_value = True
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            response = list_func(event, lambda_context)
        
        # With api_wrapper bypassed, expect direct return value
        assert "tools" in response
        assert len(response["tools"]) == 0


class TestCreateTool:
    """Test class for create tool functionality."""

    def test_create_success(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                           sample_tool_content, lambda_context):
        """Test successful creation of a tool."""
        create = mcp_workbench_functions["create"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Create the event
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "body": json.dumps({"id": "new_tool.py", "contents": sample_tool_content}),
        }
        
        mock_is_admin.return_value = True
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            response = create(event, lambda_context)
        
        # With api_wrapper bypassed, expect direct return value
        assert response["id"] == "new_tool.py"
        assert response["contents"] == sample_tool_content
        
        # Verify the object was actually created in S3
        s3_obj = mock_s3.get_object(Bucket="workbench-bucket", Key="new_tool.py")
        created_content = s3_obj["Body"].read().decode("utf-8")
        assert created_content == sample_tool_content

    def test_create_without_py_extension(self, mcp_workbench_functions, mock_mcp_workbench_common, 
                                        mock_s3, sample_tool_content, lambda_context):
        """Test creating a tool without .py extension."""
        create = mcp_workbench_functions["create"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Create the event
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "body": json.dumps({"id": "new_tool", "contents": sample_tool_content}),
        }
        
        mock_is_admin.return_value = True
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            response = create(event, lambda_context)
        
        # With api_wrapper bypassed, expect direct return value
        assert response["id"] == "new_tool"
        
        # Verify the object was actually created in S3 with .py extension
        s3_obj = mock_s3.get_object(Bucket="workbench-bucket", Key="new_tool.py")
        created_content = s3_obj["Body"].read().decode("utf-8")
        assert created_content == sample_tool_content

    def test_create_not_admin(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                             sample_tool_content, lambda_context):
        """Test unauthorized creation of a tool."""
        create = mcp_workbench_functions["create"]
        mock_get_username = mock_mcp_workbench_common["get_username"]
        
        # Create the event
        event = {
            "requestContext": {"authorizer": {"username": "regular-user"}},
            "body": json.dumps({"id": "unauthorized_tool.py", "contents": sample_tool_content}),
        }
        
        mock_get_username.return_value = "regular-user"
        
        # With api_wrapper bypassed, expect direct exception
        with pytest.raises(ValueError) as excinfo:
            create(event, lambda_context)
        assert "Only admin users can access tools" in str(excinfo.value)

    def test_create_missing_fields(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                                  lambda_context):
        """Test creating a tool with missing required fields."""
        create = mcp_workbench_functions["create"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Create the event with missing contents
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "body": json.dumps({"id": "incomplete_tool.py"}),
        }
        
        mock_is_admin.return_value = True
        
        # With api_wrapper bypassed, expect direct exception
        with pytest.raises(ValueError) as excinfo:
            create(event, lambda_context)
        assert "Missing required fields" in str(excinfo.value)


class TestUpdateTool:
    """Test class for update tool functionality."""

    def test_update_success(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                           sample_tool_content, sample_tool_id, lambda_context):
        """Test successful update of a tool."""
        update = mcp_workbench_functions["update"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Upload initial file to the mocked S3
        mock_s3.put_object(
            Bucket="workbench-bucket",
            Key=sample_tool_id,
            Body=sample_tool_content.encode("utf-8"),
            ContentType="text/x-python",
        )
        
        # Updated content
        updated_content = """
def updated_function():
    return "This is the updated function"
"""
        
        # Create the event
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "pathParameters": {"toolId": sample_tool_id},
            "body": json.dumps({"contents": updated_content}),
        }
        
        mock_is_admin.return_value = True
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            response = update(event, lambda_context)
        
        # With api_wrapper bypassed, expect direct return value
        assert response["id"] == sample_tool_id
        assert response["contents"] == updated_content
        
        # Verify the object was actually updated in S3
        s3_obj = mock_s3.get_object(Bucket="workbench-bucket", Key=sample_tool_id)
        updated_content_from_s3 = s3_obj["Body"].read().decode("utf-8")
        assert updated_content_from_s3 == updated_content

    def test_update_not_admin(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                             sample_tool_id, lambda_context):
        """Test unauthorized update of a tool."""
        update = mcp_workbench_functions["update"]
        mock_get_username = mock_mcp_workbench_common["get_username"]
        
        # Create the event
        event = {
            "requestContext": {"authorizer": {"username": "regular-user"}},
            "pathParameters": {"toolId": sample_tool_id},
            "body": json.dumps({"contents": "Updated content"}),
        }
        
        mock_get_username.return_value = "regular-user"
        
        # With api_wrapper bypassed, expect direct exception
        with pytest.raises(ValueError) as excinfo:
            update(event, lambda_context)
        assert "Only admin users can access tools" in str(excinfo.value)

    def test_update_not_found(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                             lambda_context):
        """Test updating a non-existent tool."""
        update = mcp_workbench_functions["update"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Create the event for a non-existent tool
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "pathParameters": {"toolId": "non_existent_tool.py"},
            "body": json.dumps({"contents": "Updated content"}),
        }
        
        mock_is_admin.return_value = True
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            # With api_wrapper bypassed, expect direct exception
            # The HTTPException gets wrapped in a ValueError by the outer exception handler
            with pytest.raises(ValueError) as excinfo:
                update(event, lambda_context)
        assert "does not exist" in str(excinfo.value).lower()

    def test_update_missing_tool_id(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                                   lambda_context):
        """Test updating without a toolId parameter."""
        update = mcp_workbench_functions["update"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Create the event with missing pathParameters
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "pathParameters": {},
            "body": json.dumps({"contents": "Updated content"}),
        }
        
        mock_is_admin.return_value = True
        
        # With api_wrapper bypassed, expect direct exception
        with pytest.raises(ValueError) as excinfo:
            update(event, lambda_context)
        assert "Missing toolId parameter" in str(excinfo.value)

    def test_update_missing_contents(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                                    sample_tool_content, sample_tool_id, lambda_context):
        """Test updating a tool without contents."""
        update = mcp_workbench_functions["update"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Upload initial file to the mocked S3
        mock_s3.put_object(
            Bucket="workbench-bucket",
            Key=sample_tool_id,
            Body=sample_tool_content.encode("utf-8"),
            ContentType="text/x-python",
        )
        
        # Create the event with missing contents
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "pathParameters": {"toolId": sample_tool_id},
            "body": json.dumps({}),
        }
        
        mock_is_admin.return_value = True
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            # With api_wrapper bypassed, expect direct exception
            with pytest.raises(ValueError) as excinfo:
                update(event, lambda_context)
        assert "Missing required field: 'contents'" in str(excinfo.value)


class TestDeleteTool:
    """Test class for delete tool functionality."""

    def test_delete_success(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                           sample_tool_content, sample_tool_id, lambda_context):
        """Test successful deletion of a tool."""
        delete = mcp_workbench_functions["delete"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Upload a file to the mocked S3
        mock_s3.put_object(
            Bucket="workbench-bucket",
            Key=sample_tool_id,
            Body=sample_tool_content.encode("utf-8"),
            ContentType="text/x-python",
        )
        
        # Create the event
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "pathParameters": {"toolId": sample_tool_id},
        }
        
        mock_is_admin.return_value = True
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            response = delete(event, lambda_context)
        
        # With api_wrapper bypassed, expect direct return value
        assert "status" in response
        assert response["status"] == "ok"
        assert f"Tool {sample_tool_id} deleted successfully" in response["message"]
        
        # Verify the object was actually deleted from S3
        try:
            mock_s3.head_object(Bucket="workbench-bucket", Key=sample_tool_id)
            assert False, "Object still exists in S3"
        except botocore.exceptions.ClientError as e:
            assert e.response["Error"]["Code"] == "404"

    def test_delete_not_admin(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                             sample_tool_id, lambda_context):
        """Test unauthorized deletion of a tool."""
        delete = mcp_workbench_functions["delete"]
        mock_get_username = mock_mcp_workbench_common["get_username"]
        
        # Create the event
        event = {
            "requestContext": {"authorizer": {"username": "regular-user"}},
            "pathParameters": {"toolId": sample_tool_id},
        }
        
        mock_get_username.return_value = "regular-user"
        
        # With api_wrapper bypassed, expect direct exception
        with pytest.raises(ValueError) as excinfo:
            delete(event, lambda_context)
        assert "Only admin users can access tools" in str(excinfo.value)

    def test_delete_not_found(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                             lambda_context):
        """Test deleting a non-existent tool."""
        delete = mcp_workbench_functions["delete"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Create the event for a non-existent tool
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "pathParameters": {"toolId": "non_existent_tool.py"},
        }
        
        mock_is_admin.return_value = True
        
        # Patch s3_client and WORKBENCH_BUCKET for the function call
        with patch("mcp_workbench.lambda_functions.s3_client", mock_s3), \
             patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", "workbench-bucket"):
            # With api_wrapper bypassed, expect direct exception
            # The HTTPException gets wrapped in a ValueError by the outer exception handler
            with pytest.raises(ValueError) as excinfo:
                delete(event, lambda_context)
        assert "does not exist" in str(excinfo.value).lower()

    def test_delete_missing_tool_id(self, mcp_workbench_functions, mock_mcp_workbench_common, mock_s3,
                                   lambda_context):
        """Test deleting without a toolId parameter."""
        delete = mcp_workbench_functions["delete"]
        mock_is_admin = mock_mcp_workbench_common["is_admin"]
        
        # Create the event with missing pathParameters
        event = {
            "requestContext": {"authorizer": {"username": "test-admin"}},
            "pathParameters": {},
        }
        
        mock_is_admin.return_value = True
        
        # With api_wrapper bypassed, expect direct exception  
        with pytest.raises(ValueError) as excinfo:
            delete(event, lambda_context)
        assert "Missing toolId parameter" in str(excinfo.value)
