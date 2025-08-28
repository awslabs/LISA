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
os.environ["SESSIONS_TABLE_NAME"] = "sessions-table"
os.environ["SESSIONS_BY_USER_ID_INDEX_NAME"] = "sessions-by-user-id-index"
os.environ["GENERATED_IMAGES_S3_BUCKET_NAME"] = "bucket"

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


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def s3():
    """Create a mock S3 service."""
    with mock_aws():
        # Create the bucket that our code expects
        s3_resource = boto3.resource("s3", region_name="us-east-1")
        s3_client = boto3.client("s3", region_name="us-east-1")

        # Create the bucket with proper parameters for US region
        s3_client.create_bucket(Bucket="bucket", CreateBucketConfiguration={"LocationConstraint": "us-east-1"})

        yield s3_resource


@pytest.fixture(scope="function")
def dynamodb_table(dynamodb):
    """Create a mock DynamoDB table."""
    table = dynamodb.create_table(
        TableName="sessions-table",
        KeySchema=[{"AttributeName": "sessionId", "KeyType": "HASH"}, {"AttributeName": "userId", "KeyType": "RANGE"}],
        AttributeDefinitions=[
            {"AttributeName": "sessionId", "AttributeType": "S"},
            {"AttributeName": "userId", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "sessions-by-user-id-index",
                "KeySchema": [{"AttributeName": "userId", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


# Create mock modules
mock_common = MagicMock()
mock_common.get_username.return_value = "test-user"
mock_common.retry_config = retry_config
mock_common.get_session_id.return_value = "test-session"
mock_common.api_wrapper = mock_api_wrapper

# Create mock create_env_variables
mock_create_env = MagicMock()

# First, patch sys.modules
patch.dict(
    "sys.modules",
    {
        "create_env_variables": mock_create_env,
    },
).start()

# Then patch the specific functions
patch("utilities.common_functions.get_username", mock_common.get_username).start()
patch("utilities.common_functions.get_session_id", mock_common.get_session_id).start()
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.api_wrapper", mock_api_wrapper).start()

# Now import the lambda functions
from session.lambda_functions import delete_session, delete_user_sessions, get_session, list_sessions, put_session


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
def sample_session():
    return {
        "sessionId": "test-session",
        "userId": "test-user",
        "history": [{"type": "human", "content": "Hello"}, {"type": "assistant", "content": "Hi there!"}],
        "configuration": {"model": "test-model"},
        "startTime": datetime.now().isoformat(),
        "createTime": datetime.now().isoformat(),
    }


def test_list_sessions(dynamodb_table, sample_session, lambda_context):
    # Create a few sessions
    dynamodb_table.put_item(Item=sample_session)

    session2 = sample_session.copy()
    session2["sessionId"] = "test-session-2"
    dynamodb_table.put_item(Item=session2)

    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    response = list_sessions(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 2
    assert any(s["sessionId"] == "test-session" for s in body)
    assert any(s["sessionId"] == "test-session-2" for s in body)


def test_get_session(dynamodb_table, sample_session, lambda_context):
    dynamodb_table.put_item(Item=sample_session)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
    }

    response = get_session(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["sessionId"] == sample_session["sessionId"]
    assert body["userId"] == "test-user"


def test_missing_path_parameters(lambda_context):
    """Test handling missing path parameters."""
    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    # Mock get_session_id to raise ValueError
    mock_common.get_session_id.side_effect = ValueError("Missing sessionId")

    response = get_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Missing sessionId" in body["error"]

    # Reset the mock
    mock_common.get_session_id.side_effect = None
    mock_common.get_session_id.return_value = "test-session"


def test_missing_username(lambda_context):
    """Test handling missing username in claims."""
    event = {"requestContext": {"authorizer": {"claims": {}}}, "pathParameters": {"sessionId": "test-session"}}

    # Mock get_username to raise ValueError
    mock_common.get_username.side_effect = ValueError("Missing username")

    response = get_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Missing username" in body["error"]

    # Reset the mock
    mock_common.get_username.side_effect = None
    mock_common.get_username.return_value = "test-user"


@pytest.fixture(autouse=True)
def mock_s3_operations():
    """Mock S3 operations to avoid errors."""
    with patch("session.lambda_functions._delete_user_session") as mock_delete:
        # Make the mocked function return True by default
        mock_delete.return_value = {"deleted": True}
        yield mock_delete


def test_delete_session(dynamodb_table, sample_session, lambda_context, mock_s3_operations):
    """Test deleting a session."""
    dynamodb_table.put_item(Item=sample_session)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
    }

    response = delete_session(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["deleted"] is True

    # Verify the mock was called with correct parameters
    mock_s3_operations.assert_called_once_with("test-session", "test-user")


def test_delete_user_sessions(dynamodb_table, sample_session, lambda_context, mock_s3_operations):
    """Test deleting all sessions for a user."""
    # Create multiple sessions
    dynamodb_table.put_item(Item=sample_session)

    session2 = sample_session.copy()
    session2["sessionId"] = "test-session-2"
    dynamodb_table.put_item(Item=session2)

    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    response = delete_user_sessions(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["deleted"] is True


def test_delete_session_not_found(dynamodb_table, lambda_context, mock_s3_operations):
    """Test deleting a non-existent session."""
    # Temporarily change the session ID for this test
    original_session_id = mock_common.get_session_id.return_value
    mock_common.get_session_id.return_value = "non-existent-session"

    try:
        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "pathParameters": {"sessionId": "non-existent-session"},
        }

        response = delete_session(event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["deleted"] is True

        # Verify the mock was called with correct parameters
        mock_s3_operations.assert_called_once_with("non-existent-session", "test-user")
    finally:
        # Restore the original session ID
        mock_common.get_session_id.return_value = original_session_id


def test_put_session(dynamodb_table, sample_session, lambda_context):
    """Test putting a session."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps(
            {"messages": sample_session["history"], "configuration": sample_session["configuration"]}, default=str
        ),
    }

    response = put_session(event, lambda_context)
    assert response["statusCode"] == 200


def test_get_session_not_found(dynamodb_table, lambda_context):
    """Test getting a non-existent session."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "non-existent-session"},
    }

    response = get_session(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body == {}


def test_put_session_invalid_body(dynamodb_table, lambda_context):
    """Test putting a session with invalid body."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": "invalid-json",
    }

    response = put_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Invalid JSON" in body["error"]


def test_put_session_missing_required_fields(dynamodb_table, lambda_context):
    """Test putting a session with missing required fields."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({}),
    }

    response = put_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Missing required fields" in body["error"]


def test_list_sessions_empty(dynamodb_table, lambda_context):
    """Test listing sessions when there are none."""
    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    response = list_sessions(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 0
