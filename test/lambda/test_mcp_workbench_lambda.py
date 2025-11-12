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

"""Unit tests for MCP workbench lambda functions."""

import functools
import json
import logging
import os
import sys
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import botocore.exceptions
import pytest
from botocore.config import Config
from moto import mock_aws

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials and environment variables before importing
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["WORKBENCH_BUCKET"] = "workbench-bucket"

mock_env = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SECURITY_TOKEN": "testing",
    "AWS_SESSION_TOKEN": "testing",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_REGION": "us-east-1",
    "WORKBENCH_BUCKET": "workbench-bucket",
}

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")

# Define the bucket name used in tests
WORKBENCH_BUCKET = "workbench-bucket"


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


# Create mock modules for patching with complete isolation
@pytest.fixture(autouse=True, scope="function")
def mock_common():
    """Ensure complete test isolation with fresh environment."""
    with patch.dict("os.environ", mock_env, clear=True):
        # Reset any module-level variables that might be cached
        yield


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


SAMPLE_TOOL_CONTENT = """
def hello_world():
    print("Hello, world!")
    return "Hello from MCP Tool"
"""

SAMPLE_TOOL_ID = "test_tool.py"


@pytest.fixture
def s3_setup():
    """Set up S3 with moto and create bucket. Uses complete isolation to avoid test interference."""
    # More aggressive approach: Temporarily replace boto3.client entirely
    import importlib

    import boto3

    # Save original boto3.client
    original_boto3_client = boto3.client

    try:
        # Create a completely isolated moto context
        with mock_aws():
            # Force a fresh import of boto3 within the moto context
            importlib.reload(boto3)

            # Create a fresh S3 client
            s3_client = boto3.client("s3", region_name="us-east-1")

            # Create the bucket
            s3_client.create_bucket(Bucket=WORKBENCH_BUCKET)

            # Create a storage dict to track what we put in S3 during tests
            # This helps with debugging if moto state gets corrupted
            s3_storage = {}

            # Wrap the original methods to track operations
            original_put_object = s3_client.put_object
            original_get_object = s3_client.get_object
            original_delete_object = s3_client.delete_object
            original_list_objects_v2 = s3_client.list_objects_v2

            def tracked_put_object(**kwargs):
                key = kwargs.get("Key")
                body = kwargs.get("Body")
                if isinstance(body, bytes):
                    s3_storage[key] = body.decode("utf-8")
                else:
                    s3_storage[key] = str(body)
                return original_put_object(**kwargs)

            def tracked_get_object(**kwargs):
                return original_get_object(**kwargs)

            def tracked_delete_object(**kwargs):
                key = kwargs.get("Key")
                if key in s3_storage:
                    del s3_storage[key]
                return original_delete_object(**kwargs)

            def tracked_list_objects_v2(**kwargs):
                return original_list_objects_v2(**kwargs)

            s3_client.put_object = tracked_put_object
            s3_client.get_object = tracked_get_object
            s3_client.delete_object = tracked_delete_object
            s3_client.list_objects_v2 = tracked_list_objects_v2

            yield s3_client
    finally:
        # Restore original boto3.client
        boto3.client = original_boto3_client


# Test the MCPToolModel directly without mocking dependencies
def test_mcp_tool_model():
    """Test the MCPToolModel class."""
    # Import inside the test to avoid import-time patching issues
    from mcp_workbench.lambda_functions import MCPToolModel

    # Test with .py extension
    tool = MCPToolModel(id="test_tool.py", contents="print('hello')")
    assert tool.s3_key == "test_tool.py"

    # Test without .py extension
    tool = MCPToolModel(id="test_tool", contents="print('hello')")
    assert tool.s3_key == "test_tool.py"

    # Test with updated_at
    timestamp = datetime.now().isoformat()
    tool = MCPToolModel(id="test_tool.py", contents="print('hello')", updated_at=timestamp)
    assert tool.updated_at == timestamp


# Test CRUD operations with moto
def test_get_tool_from_s3(s3_setup):
    """Test retrieving a tool from S3."""
    # Upload a file to the mocked S3
    s3_setup.put_object(
        Bucket=WORKBENCH_BUCKET,
        Key=SAMPLE_TOOL_ID,
        Body=SAMPLE_TOOL_CONTENT.encode("utf-8"),
        ContentType="text/x-python",
    )

    # Import and test the function
    from mcp_workbench.lambda_functions import _get_tool_from_s3

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET
    ):
        tool = _get_tool_from_s3(SAMPLE_TOOL_ID)

    # Verify tool properties
    assert tool.id == SAMPLE_TOOL_ID
    assert tool.contents == SAMPLE_TOOL_CONTENT


def test_get_tool_from_s3_not_found(s3_setup):
    """Test retrieving a non-existent tool from S3."""
    # Import and test the function
    from mcp_workbench.lambda_functions import _get_tool_from_s3

    # Test retrieving non-existent tool with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET
    ):
        with pytest.raises(Exception) as excinfo:
            _get_tool_from_s3("non_existent_tool.py")
        assert "not found" in str(excinfo.value).lower()


def test_get_tool_from_s3_adds_py_extension(s3_setup):
    """Test retrieving a tool without .py extension."""
    # Upload a file to the mocked S3 with .py extension
    s3_setup.put_object(
        Bucket=WORKBENCH_BUCKET,
        Key="test_tool.py",
        Body=SAMPLE_TOOL_CONTENT.encode("utf-8"),
        ContentType="text/x-python",
    )

    # Import and test the function
    from mcp_workbench.lambda_functions import _get_tool_from_s3

    # Use the actual function with moto S3, but request without .py extension
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET
    ):
        tool = _get_tool_from_s3("test_tool")

    assert tool.id == "test_tool.py"
    assert tool.contents == SAMPLE_TOOL_CONTENT


def test_read_success(s3_setup, lambda_context):
    """Test successful retrieval of tool."""
    # Upload a file to the mocked S3
    s3_setup.put_object(
        Bucket=WORKBENCH_BUCKET,
        Key=SAMPLE_TOOL_ID,
        Body=SAMPLE_TOOL_CONTENT.encode("utf-8"),
        ContentType="text/x-python",
    )

    # Create the event
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "pathParameters": {"toolId": SAMPLE_TOOL_ID},
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import read

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ), patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET):
        response = read(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == SAMPLE_TOOL_ID
    assert body["contents"] == SAMPLE_TOOL_CONTENT


def test_read_not_admin(s3_setup, lambda_context):
    """Test unauthorized retrieval of tool."""
    # Create the event
    event = {
        "requestContext": {"authorizer": {"username": "regular-user"}},
        "pathParameters": {"toolId": SAMPLE_TOOL_ID},
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import read

    # Use the actual function with moto S3 and patched is_admin
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "utilities.auth.get_username", return_value="regular-user"
    ), patch("mcp_workbench.lambda_functions.api_wrapper", mock_api_wrapper):
        response = read(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "Only admin users can access tools" in error_text


def test_read_not_found(s3_setup, lambda_context):
    """Test reading a non-existent tool."""
    # Create the event for a non-existent tool
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "pathParameters": {"toolId": "non_existent_tool.py"},
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import read

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ), patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET):
        response = read(event, lambda_context)

    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "not found" in error_text.lower()


def test_read_missing_tool_id(s3_setup, lambda_context):
    """Test reading without a toolId parameter."""
    # Create the event with missing pathParameters
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "pathParameters": {},
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import read

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ):
        response = read(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "Missing toolId parameter" in error_text


def test_list_success(s3_setup, lambda_context):
    """Test successful listing of tools."""
    # Upload files to the mocked S3
    s3_setup.put_object(
        Bucket=WORKBENCH_BUCKET, Key="tool1.py", Body=SAMPLE_TOOL_CONTENT.encode("utf-8"), ContentType="text/x-python"
    )
    s3_setup.put_object(
        Bucket=WORKBENCH_BUCKET, Key="tool2.py", Body=SAMPLE_TOOL_CONTENT.encode("utf-8"), ContentType="text/x-python"
    )
    s3_setup.put_object(
        Bucket=WORKBENCH_BUCKET, Key="not_a_tool.txt", Body=b"This is not a python file", ContentType="text/plain"
    )

    # Create the event
    event = {"requestContext": {"authorizer": {"username": "test-admin"}}}

    # Import and test the function
    from mcp_workbench.lambda_functions import list as list_tools

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ), patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET):
        response = list_tools(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "tools" in body
    assert len(body["tools"]) == 2  # Only the .py files

    # Verify the tool ids
    tool_ids = [tool["id"] for tool in body["tools"]]
    assert "tool1.py" in tool_ids
    assert "tool2.py" in tool_ids
    assert "not_a_tool.txt" not in tool_ids


def test_list_not_admin(s3_setup, lambda_context):
    """Test unauthorized listing of tools."""
    # Create the event
    event = {"requestContext": {"authorizer": {"username": "regular-user"}}}

    # Import and test the function
    from mcp_workbench.lambda_functions import list as list_tools

    # Use the actual function with moto S3 and patched is_admin
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "utilities.auth.get_username", return_value="regular-user"
    ), patch("mcp_workbench.lambda_functions.api_wrapper", mock_api_wrapper):
        response = list_tools(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "Only admin users can access tools" in error_text


def test_list_empty_bucket(s3_setup, lambda_context):
    """Test listing tools in an empty bucket."""
    # Create the event (bucket is already empty from s3_setup)
    event = {"requestContext": {"authorizer": {"username": "test-admin"}}}

    # Import and test the function
    from mcp_workbench.lambda_functions import list as list_tools

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ), patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET):
        response = list_tools(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "tools" in body
    assert len(body["tools"]) == 0


def test_create_success(s3_setup, lambda_context):
    """Test successful creation of a tool."""
    # Create the event
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "body": json.dumps({"id": "new_tool.py", "contents": SAMPLE_TOOL_CONTENT}),
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import create

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ), patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET):
        response = create(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "new_tool.py"
    assert body["contents"] == SAMPLE_TOOL_CONTENT

    # Verify the object was actually created in S3
    s3_obj = s3_setup.get_object(Bucket=WORKBENCH_BUCKET, Key="new_tool.py")
    created_content = s3_obj["Body"].read().decode("utf-8")
    assert created_content == SAMPLE_TOOL_CONTENT


def test_create_without_py_extension(s3_setup, lambda_context):
    """Test creating a tool without .py extension."""
    # Create the event
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "body": json.dumps({"id": "new_tool", "contents": SAMPLE_TOOL_CONTENT}),
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import create

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ), patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET):
        response = create(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "new_tool"

    # Verify the object was actually created in S3 with .py extension
    s3_obj = s3_setup.get_object(Bucket=WORKBENCH_BUCKET, Key="new_tool.py")
    created_content = s3_obj["Body"].read().decode("utf-8")
    assert created_content == SAMPLE_TOOL_CONTENT


def test_create_not_admin(s3_setup, lambda_context):
    """Test unauthorized creation of a tool."""
    # Create the event
    event = {
        "requestContext": {"authorizer": {"username": "regular-user"}},
        "body": json.dumps({"id": "unauthorized_tool.py", "contents": SAMPLE_TOOL_CONTENT}),
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import create

    # Use the actual function with moto S3 and patched is_admin
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "utilities.auth.get_username", return_value="regular-user"
    ), patch("mcp_workbench.lambda_functions.api_wrapper", mock_api_wrapper):
        response = create(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "Only admin users can access tools" in error_text


def test_create_missing_fields(s3_setup, lambda_context):
    """Test creating a tool with missing required fields."""
    # Create the event with missing contents
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "body": json.dumps({"id": "incomplete_tool.py"}),
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import create

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ):
        response = create(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "Missing required fields" in error_text


def test_update_success(s3_setup, lambda_context):
    """Test successful update of a tool."""
    # Upload initial file to the mocked S3
    s3_setup.put_object(
        Bucket=WORKBENCH_BUCKET,
        Key=SAMPLE_TOOL_ID,
        Body=SAMPLE_TOOL_CONTENT.encode("utf-8"),
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
        "pathParameters": {"toolId": SAMPLE_TOOL_ID},
        "body": json.dumps({"contents": updated_content}),
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import update

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ), patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET):
        response = update(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == SAMPLE_TOOL_ID
    assert body["contents"] == updated_content

    # Verify the object was actually updated in S3
    s3_obj = s3_setup.get_object(Bucket=WORKBENCH_BUCKET, Key=SAMPLE_TOOL_ID)
    updated_content_from_s3 = s3_obj["Body"].read().decode("utf-8")
    assert updated_content_from_s3 == updated_content


def test_update_not_admin(s3_setup, lambda_context):
    """Test unauthorized update of a tool."""
    # Create the event
    event = {
        "requestContext": {"authorizer": {"username": "regular-user"}},
        "pathParameters": {"toolId": SAMPLE_TOOL_ID},
        "body": json.dumps({"contents": "Updated content"}),
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import update

    # Use the actual function with moto S3 and patched is_admin
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "utilities.auth.get_username", return_value="regular-user"
    ), patch("mcp_workbench.lambda_functions.api_wrapper", mock_api_wrapper):
        response = update(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "Only admin users can access tools" in error_text


def test_update_not_found(s3_setup, lambda_context):
    """Test updating a non-existent tool."""
    # Create the event for a non-existent tool
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "pathParameters": {"toolId": "non_existent_tool.py"},
        "body": json.dumps({"contents": "Updated content"}),
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import update

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ), patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET):
        response = update(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "does not exist" in error_text


def test_update_missing_tool_id(s3_setup, lambda_context):
    """Test updating without a toolId parameter."""
    # Create the event with missing pathParameters
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "pathParameters": {},
        "body": json.dumps({"contents": "Updated content"}),
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import update

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ):
        response = update(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "Missing toolId parameter" in error_text


def test_update_missing_contents(s3_setup, lambda_context):
    """Test updating a tool without contents."""
    # Upload initial file to the mocked S3
    s3_setup.put_object(
        Bucket=WORKBENCH_BUCKET,
        Key=SAMPLE_TOOL_ID,
        Body=SAMPLE_TOOL_CONTENT.encode("utf-8"),
        ContentType="text/x-python",
    )

    # Create the event with missing contents
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "pathParameters": {"toolId": SAMPLE_TOOL_ID},
        "body": json.dumps({}),
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import update

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ):
        response = update(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "Missing required field: 'contents'" in error_text


# Test delete operations with moto
def test_delete_success(s3_setup, lambda_context):
    """Test successful deletion of a tool."""
    # Upload a file to the mocked S3
    s3_setup.put_object(
        Bucket=WORKBENCH_BUCKET,
        Key=SAMPLE_TOOL_ID,
        Body=SAMPLE_TOOL_CONTENT.encode("utf-8"),
        ContentType="text/x-python",
    )

    # Create the event
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "pathParameters": {"toolId": SAMPLE_TOOL_ID},
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import delete

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ), patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET):
        response = delete(event, lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "status" in body
    assert body["status"] == "ok"
    assert f"Tool {SAMPLE_TOOL_ID} deleted successfully" in body["message"]

    # Verify the object was actually deleted from S3
    try:
        s3_setup.head_object(Bucket=WORKBENCH_BUCKET, Key=SAMPLE_TOOL_ID)
        assert False, "Object still exists in S3"
    except botocore.exceptions.ClientError as e:
        assert e.response["Error"]["Code"] == "404"


def test_delete_not_admin(s3_setup, lambda_context):
    """Test unauthorized deletion of a tool."""
    # Create the event
    event = {
        "requestContext": {"authorizer": {"username": "regular-user"}},
        "pathParameters": {"toolId": SAMPLE_TOOL_ID},
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import delete

    # Use the actual function with moto S3 and patched is_admin
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "utilities.auth.get_username", return_value="regular-user"
    ), patch("mcp_workbench.lambda_functions.api_wrapper", mock_api_wrapper):
        response = delete(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "Only admin users can access tools" in error_text


def test_delete_not_found(s3_setup, lambda_context):
    """Test deleting a non-existent tool."""
    # Create the event for a non-existent tool
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "pathParameters": {"toolId": "non_existent_tool.py"},
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import delete

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ), patch("mcp_workbench.lambda_functions.WORKBENCH_BUCKET", WORKBENCH_BUCKET):
        response = delete(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "does not exist" in error_text


def test_delete_missing_tool_id(s3_setup, lambda_context):
    """Test deleting without a toolId parameter."""
    # Create the event with missing pathParameters
    event = {
        "requestContext": {"authorizer": {"username": "test-admin"}},
        "pathParameters": {},
    }

    # Import and test the function
    from mcp_workbench.lambda_functions import delete

    # Use the actual function with moto S3
    with patch("mcp_workbench.lambda_functions.s3_client", s3_setup), patch(
        "mcp_workbench.lambda_functions.is_admin", return_value=True
    ):
        response = delete(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Handle both string and dict response formats
    error_text = body if isinstance(body, str) else body.get("error", "")
    assert "Missing toolId parameter" in error_text
