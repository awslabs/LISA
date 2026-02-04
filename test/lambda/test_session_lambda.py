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
os.environ["AWS_REGION"] = "us-east-1"
os.environ["SESSIONS_TABLE_NAME"] = "sessions-table"
os.environ["SESSIONS_BY_USER_ID_INDEX_NAME"] = "sessions-by-user-id-index"
os.environ["GENERATED_IMAGES_S3_BUCKET_NAME"] = "bucket"
os.environ["MODEL_TABLE_NAME"] = "model-table"
os.environ["CONFIG_TABLE_NAME"] = "config-table"
os.environ["SESSION_ENCRYPTION_KEY_ARN"] = "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


def mock_api_wrapper(_func=None, **kwargs):
    """Mock api_wrapper that accepts any kwargs."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            try:
                result = func(*args, **kw)
                if isinstance(result, dict) and "statusCode" in result:
                    return result
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps(result, default=str),
                }
            except ValueError as e:
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": str(e)}),
                }
            except Exception as e:
                logging.error(f"Error in {func.__name__}: {str(e)}")
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": str(e)}),
                }

        return wrapper

    if _func is not None:
        return decorator(_func)
    return decorator


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
    # Patch the module-level table with our test fixture
    with patch("session.lambda_functions.table", table):
        yield table


@pytest.fixture(scope="function")
def config_table(dynamodb):
    """Create a mock configuration DynamoDB table."""
    table = dynamodb.create_table(
        TableName="config-table",
        KeySchema=[
            {"AttributeName": "configScope", "KeyType": "HASH"},
            {"AttributeName": "versionId", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "configScope", "AttributeType": "S"},
            {"AttributeName": "versionId", "AttributeType": "N"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    # Patch the module-level config_table with our test fixture
    with patch("session.lambda_functions.config_table", table):
        yield table


# Create mock modules
mock_common = MagicMock()
mock_common.get_username.return_value = "test-user"
mock_common.get_user_context.return_value = ("test-user", False, ["test-group"])
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
patch("utilities.auth.get_username", mock_common.get_username).start()
patch("utilities.auth.get_user_context", mock_common.get_user_context).start()
patch("utilities.common_functions.get_session_id", mock_common.get_session_id).start()
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.api_wrapper", mock_api_wrapper).start()

# Import Pydantic models for type-safe testing
from models.domain_objects import DeleteResponse, SuccessResponse

# Now import the lambda functions
from session.lambda_functions import delete_session, delete_user_sessions, get_session, list_sessions, put_session
from session.models import (
    PutSessionRequest,
    RenameSessionRequest,
    Session,
    SessionSummary,
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
    # Validate response items match SessionSummary structure
    session_summaries = [SessionSummary.model_validate(s) for s in body]
    session_ids = [s.sessionId for s in session_summaries]
    assert "test-session" in session_ids
    assert "test-session-2" in session_ids


def test_get_session(dynamodb_table, sample_session, lambda_context):
    dynamodb_table.put_item(Item=sample_session)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
    }

    response = get_session(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    # Validate response matches Session model structure
    session = Session.model_validate(body)
    assert session.sessionId == sample_session["sessionId"]
    assert session.userId == "test-user"


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
        # Make the mocked function return DeleteResponse by default
        mock_delete.return_value = DeleteResponse(deleted=True)
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
    # Validate response matches DeleteResponse model
    delete_response = DeleteResponse.model_validate(body)
    assert delete_response.deleted is True

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
    # Validate response matches DeleteResponse model
    delete_response = DeleteResponse.model_validate(body)
    assert delete_response.deleted is True


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
        # Validate response matches DeleteResponse model
        delete_response = DeleteResponse.model_validate(body)
        assert delete_response.deleted is True

        # Verify the mock was called with correct parameters
        mock_s3_operations.assert_called_once_with("non-existent-session", "test-user")
    finally:
        # Restore the original session ID
        mock_common.get_session_id.return_value = original_session_id


def test_put_session(dynamodb_table, config_table, sample_session, lambda_context):
    """Test putting a session."""
    # Create request using PutSessionRequest model
    put_request = PutSessionRequest(messages=sample_session["history"], configuration=sample_session["configuration"])

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": put_request.model_dump_json(),
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
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "error" in body


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
    # Pydantic validation error for missing 'messages' field
    assert "error" in body


def test_list_sessions_empty(dynamodb_table, lambda_context):
    """Test listing sessions when there are none."""
    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    response = list_sessions(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert isinstance(body, list)
    assert len(body) == 0


# Import the configuration functions for testing
from session.lambda_functions import (
    _delete_user_session,
    _find_first_human_message,
    _generate_presigned_image_url,
    _get_all_user_sessions,
    _get_current_model_config,
    _is_session_encryption_enabled,
    _process_image,
    _update_session_with_current_model_config,
    attach_image_to_session,
    rename_session,
)


def test_is_session_encryption_enabled_true(config_table, lambda_context):
    """Test session encryption enabled via global configuration."""

    # Add global configuration entry with encryption enabled
    config_table.put_item(
        Item={
            "configScope": "global",
            "versionId": 0,
            "configuration": {"enabledComponents": {"encryptSession": True}},
            "created_at": "1234567890",
        }
    )

    # Clear cache to ensure fresh result
    from session.lambda_functions import cache

    cache.clear()

    result = _is_session_encryption_enabled()
    assert result is True


def test_is_session_encryption_enabled_false(config_table, lambda_context):
    """Test session encryption disabled via global configuration."""

    # Add global configuration entry with encryption disabled
    config_table.put_item(
        Item={
            "configScope": "global",
            "versionId": 0,
            "configuration": {"enabledComponents": {"encryptSession": False}},
            "created_at": "1234567890",
        }
    )

    # Clear cache to ensure fresh result
    from session.lambda_functions import cache

    cache.clear()

    result = _is_session_encryption_enabled()
    assert result is False


def test_is_session_encryption_enabled_default_fallback(config_table, lambda_context):
    """Test session encryption defaults to disabled when configuration is missing."""

    # Don't add any configuration entry
    # Clear cache to ensure fresh result
    from session.lambda_functions import cache

    cache.clear()

    result = _is_session_encryption_enabled()
    assert result is False  # Should default to disabled


@patch("session.lambda_functions.config_table")
def test_is_session_encryption_enabled_error_fallback(mock_config_table, lambda_context):
    """Test session encryption defaults to disabled when there's an error accessing configuration."""
    # Mock the config table to raise an exception
    mock_config_table.query.side_effect = Exception("Database error")

    # Clear cache to ensure fresh result
    from session.lambda_functions import cache

    cache.clear()

    result = _is_session_encryption_enabled()
    assert result is False  # Should default to disabled on error


@patch("session.lambda_functions.config_table")
def test_is_session_encryption_enabled_client_error(mock_config_table, lambda_context):
    """Test session encryption with ClientError in configuration lookup."""
    from botocore.exceptions import ClientError

    # Mock config table to raise ClientError
    mock_config_table.query.side_effect = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}}, operation_name="Query"
    )

    # Clear cache to ensure fresh result
    from session.lambda_functions import cache

    cache.clear()

    result = _is_session_encryption_enabled()
    assert result is False  # Should default to False on ClientError


@patch("session.lambda_functions.config_table")
def test_is_session_encryption_enabled_general_exception(mock_config_table, lambda_context):
    """Test session encryption with general exception in configuration lookup."""

    # Mock config table to raise general exception
    mock_config_table.query.side_effect = Exception("General database error")

    # Clear cache to ensure fresh result
    from session.lambda_functions import cache

    cache.clear()

    result = _is_session_encryption_enabled()
    assert result is False  # Should default to False on general exception


# Model Configuration Tests
@pytest.fixture(scope="function")
def model_table(dynamodb):
    """Create a mock model DynamoDB table."""
    table = dynamodb.create_table(
        TableName="model-table",
        KeySchema=[{"AttributeName": "model_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "model_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


def test_get_current_model_config_missing_table():
    """Test _get_current_model_config with missing model_table."""
    with patch("session.lambda_functions.model_table", None):
        result = _get_current_model_config("test-model")
        assert result == {}


def test_get_current_model_config_missing_model_id():
    """Test _get_current_model_config with missing model_id."""
    with patch("session.lambda_functions.model_table") as mock_table:
        result = _get_current_model_config("")
        assert result == {}
        mock_table.get_item.assert_not_called()


@patch("session.lambda_functions.model_table")
def test_get_current_model_config_client_error(mock_model_table):
    """Test _get_current_model_config with ClientError."""
    from botocore.exceptions import ClientError

    mock_model_table.get_item.side_effect = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}}, operation_name="GetItem"
    )

    result = _get_current_model_config("test-model")
    assert result == {}


def test_get_current_model_config_success(model_table):
    """Test _get_current_model_config with successful retrieval."""
    # Add a model to the table
    model_table.put_item(Item={"model_id": "test-model", "model_config": {"features": ["feature1"], "streaming": True}})

    with patch("session.lambda_functions.model_table", model_table):
        result = _get_current_model_config("test-model")
        assert result == {"features": ["feature1"], "streaming": True}


def test_update_session_with_current_model_config_empty_config():
    """Test _update_session_with_current_model_config with empty config."""
    result = _update_session_with_current_model_config({})
    assert result == {}


def test_update_session_with_current_model_config_no_model_id():
    """Test _update_session_with_current_model_config with no modelId."""
    session_config = {"selectedModel": {"name": "test-model"}}  # No modelId

    result = _update_session_with_current_model_config(session_config)
    assert result == session_config


def test_update_session_with_current_model_config_model_not_found():
    """Test _update_session_with_current_model_config when model not found."""
    session_config = {"selectedModel": {"modelId": "non-existent-model"}}

    with patch("session.lambda_functions._get_current_model_config") as mock_get_config:
        mock_get_config.return_value = {}

        result = _update_session_with_current_model_config(session_config)
        assert result == session_config


def test_update_session_with_current_model_config_success():
    """Test _update_session_with_current_model_config with successful update."""
    session_config = {"selectedModel": {"modelId": "test-model"}}

    current_model_config = {
        "features": ["new-feature"],
        "streaming": False,
        "modelType": "updated-type",
        "modelDescription": "Updated description",
        "allowedGroups": ["group1", "group2"],
    }

    with patch("session.lambda_functions._get_current_model_config") as mock_get_config:
        mock_get_config.return_value = current_model_config

        result = _update_session_with_current_model_config(session_config)

        # Verify the selectedModel was updated with current config
        assert result["selectedModel"]["features"] == ["new-feature"]
        assert result["selectedModel"]["streaming"] is False
        assert result["selectedModel"]["modelType"] == "updated-type"
        assert result["selectedModel"]["modelDescription"] == "Updated description"
        assert result["selectedModel"]["allowedGroups"] == ["group1", "group2"]


# Session Processing Tests
@patch("session.lambda_functions.table")
def test_get_all_user_sessions_resource_not_found(mock_table):
    """Test _get_all_user_sessions with ResourceNotFoundException."""
    from botocore.exceptions import ClientError

    mock_table.query.side_effect = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}}, operation_name="Query"
    )

    result = _get_all_user_sessions("test-user")
    assert result == []


@patch("session.lambda_functions.table")
def test_get_all_user_sessions_general_client_error(mock_table):
    """Test _get_all_user_sessions with general ClientError."""
    from botocore.exceptions import ClientError

    mock_table.query.side_effect = ClientError(
        error_response={"Error": {"Code": "AccessDeniedException"}}, operation_name="Query"
    )

    result = _get_all_user_sessions("test-user")
    assert result == []


@patch("session.lambda_functions.table")
@patch("session.lambda_functions.s3_resource")
def test_delete_user_session_resource_not_found(mock_s3_resource, mock_table):
    """Test _delete_user_session with ResourceNotFoundException."""
    from botocore.exceptions import ClientError

    mock_table.delete_item.side_effect = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}}, operation_name="DeleteItem"
    )

    result = _delete_user_session("test-session", "test-user")
    # Result should be DeleteResponse model
    assert isinstance(result, DeleteResponse)
    assert result.deleted is False


@patch("session.lambda_functions.table")
@patch("session.lambda_functions.s3_resource")
def test_delete_user_session_general_client_error(mock_s3_resource, mock_table):
    """Test _delete_user_session with general ClientError."""
    from botocore.exceptions import ClientError

    mock_table.delete_item.side_effect = ClientError(
        error_response={"Error": {"Code": "AccessDeniedException"}}, operation_name="DeleteItem"
    )

    result = _delete_user_session("test-session", "test-user")
    # Result should be DeleteResponse model
    assert isinstance(result, DeleteResponse)
    assert result.deleted is False


@patch("session.lambda_functions.s3_client")
def test_generate_presigned_image_url_success(mock_s3_client):
    """Test _generate_presigned_image_url with success."""
    mock_s3_client.generate_presigned_url.return_value = "https://presigned-url.com"

    result = _generate_presigned_image_url("test-key")
    assert result == "https://presigned-url.com"

    mock_s3_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={
            "Bucket": "bucket",
            "Key": "test-key",
            "ResponseContentType": "image/png",
            "ResponseCacheControl": "no-cache",
            "ResponseContentDisposition": "inline",
        },
    )


def test_process_image_success():
    """Test _process_image with success."""
    msg = {"image_url": {"s3_key": "test-key"}}
    key = "test-key"

    with patch("session.lambda_functions._generate_presigned_image_url") as mock_generate:
        mock_generate.return_value = "https://presigned-url.com"

        _process_image((msg, key))

        assert msg["image_url"]["url"] == "https://presigned-url.com"
        mock_generate.assert_called_once_with("test-key")


def test_process_image_exception():
    """Test _process_image with exception."""
    msg = {"image_url": {"s3_key": "test-key"}}
    key = "test-key"

    with patch("session.lambda_functions._generate_presigned_image_url") as mock_generate:
        mock_generate.side_effect = Exception("S3 error")

        # Should not raise exception, just print error
        _process_image((msg, key))

        # URL should not be set
        assert "url" not in msg["image_url"]


# Encrypted Session Tests
def test_find_first_human_message_encrypted_with_user_id():
    """Test _find_first_human_message with encrypted session and user_id."""
    session = {"sessionId": "test-session", "is_encrypted": True, "history": [{"type": "human", "content": "Hello"}]}

    with patch("session.lambda_functions.decrypt_session_fields") as mock_decrypt:
        decrypted_session = {
            "sessionId": "test-session",
            "is_encrypted": False,
            "history": [{"type": "human", "content": "Decrypted Hello"}],
        }
        mock_decrypt.return_value = decrypted_session

        result = _find_first_human_message(session, "test-user")
        assert result == "Decrypted Hello"
        mock_decrypt.assert_called_once_with(session, "test-user", "test-session")


def test_find_first_human_message_encrypted_without_user_id():
    """Test _find_first_human_message with encrypted session but no user_id."""
    session = {"sessionId": "test-session", "is_encrypted": True, "history": [{"type": "human", "content": "Hello"}]}

    result = _find_first_human_message(session, None)
    assert result == "[Encrypted Session - User ID required]"


def test_find_first_human_message_encrypted_decryption_error():
    """Test _find_first_human_message with encrypted session decryption error."""
    from utilities.session_encryption import SessionEncryptionError

    session = {"sessionId": "test-session", "is_encrypted": True, "history": [{"type": "human", "content": "Hello"}]}

    with patch("session.lambda_functions.decrypt_session_fields") as mock_decrypt:
        mock_decrypt.side_effect = SessionEncryptionError("Decryption failed")

        result = _find_first_human_message(session, "test-user")
        assert result == "[Encrypted Session - Decryption failed]"


def test_find_first_human_message_unencrypted_string_content():
    """Test _find_first_human_message with unencrypted session and string content."""
    session = {
        "sessionId": "test-session",
        "is_encrypted": False,
        "history": [{"type": "human", "content": "Hello world"}],
    }

    result = _find_first_human_message(session, "test-user")
    assert result == "Hello world"


def test_find_first_human_message_unencrypted_list_content():
    """Test _find_first_human_message with unencrypted session and list content."""
    session = {
        "sessionId": "test-session",
        "is_encrypted": False,
        "history": [{"type": "human", "content": [{"text": "Hello from list"}]}],
    }

    result = _find_first_human_message(session, "test-user")
    assert result == "Hello from list"


def test_find_first_human_message_unencrypted_list_content_with_file_context():
    """Test _find_first_human_message with list content containing file context."""
    session = {
        "sessionId": "test-session",
        "is_encrypted": False,
        "history": [
            {"type": "human", "content": [{"text": "File context: some file"}]},
            {"type": "human", "content": [{"text": "Actual question"}]},
        ],
    }

    result = _find_first_human_message(session, "test-user")
    assert result == "Actual question"


def test_find_first_human_message_unencrypted_unhandled_content():
    """Test _find_first_human_message with unencrypted session and unhandled content type."""
    session = {
        "sessionId": "test-session",
        "is_encrypted": False,
        "history": [{"type": "human", "content": {"unhandled": "type"}}],
    }

    result = _find_first_human_message(session, "test-user")
    assert result == ""


def test_find_first_human_message_no_human_messages():
    """Test _find_first_human_message with no human messages."""
    session = {
        "sessionId": "test-session",
        "is_encrypted": False,
        "history": [{"type": "assistant", "content": "Assistant response"}],
    }

    result = _find_first_human_message(session, "test-user")
    assert result == ""


@patch("session.lambda_functions.decrypt_session_fields")
def test_get_session_encrypted_success(mock_decrypt, dynamodb_table, sample_session, lambda_context):
    """Test get_session with encrypted session and successful decryption."""
    # Create encrypted session
    encrypted_session = sample_session.copy()
    encrypted_session["is_encrypted"] = True
    encrypted_session["encrypted_history"] = "encrypted_data"

    dynamodb_table.put_item(Item=encrypted_session)

    # Mock successful decryption
    decrypted_session = sample_session.copy()
    mock_decrypt.return_value = decrypted_session

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
    }

    response = get_session(event, lambda_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    # Validate response matches Session model
    session = Session.model_validate(body)
    assert session.sessionId == "test-session"
    mock_decrypt.assert_called_once()


@patch("session.lambda_functions.decrypt_session_fields")
def test_get_session_encrypted_decryption_error(mock_decrypt, dynamodb_table, sample_session, lambda_context):
    """Test get_session with encrypted session and decryption error."""
    from utilities.session_encryption import SessionEncryptionError

    # Create encrypted session
    encrypted_session = sample_session.copy()
    encrypted_session["is_encrypted"] = True
    encrypted_session["encrypted_history"] = "encrypted_data"

    dynamodb_table.put_item(Item=encrypted_session)

    # Mock decryption error
    mock_decrypt.side_effect = SessionEncryptionError("Decryption failed")

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
    }

    response = get_session(event, lambda_context)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Failed to decrypt session data" in body["error"]


@patch("session.lambda_functions._update_session_with_current_model_config")
def test_get_session_model_config_update(mock_update_config, dynamodb_table, sample_session, lambda_context):
    """Test get_session with model configuration update."""
    # Create session with configuration
    session_with_config = sample_session.copy()
    session_with_config["configuration"] = {"selectedModel": {"modelId": "test-model"}}

    dynamodb_table.put_item(Item=session_with_config)

    # Mock model config update
    updated_config = {"selectedModel": {"modelId": "test-model", "features": ["new-feature"]}}
    mock_update_config.return_value = updated_config

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
    }

    response = get_session(event, lambda_context)
    assert response["statusCode"] == 200
    mock_update_config.assert_called_once()


# Image Attachment Tests
def test_attach_image_to_session_success(lambda_context):
    """Test attach_image_to_session with valid image data."""

    # Create a simple base64 encoded image
    image_data = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )

    event = {
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({"message": {"type": "image_url", "image_url": {"url": image_data}}}),
    }

    with patch("session.lambda_functions.s3_client"):
        with patch("session.lambda_functions._generate_presigned_image_url") as mock_generate:
            mock_generate.return_value = "https://presigned-url.com"

            response = attach_image_to_session(event, lambda_context)
            assert response["statusCode"] == 200
            body = response["body"]  # Already a dict, not JSON string
            assert body["image_url"]["url"] == "https://presigned-url.com"


def test_attach_image_to_session_invalid_json(lambda_context):
    """Test attach_image_to_session with invalid JSON."""
    event = {"pathParameters": {"sessionId": "test-session"}, "body": "invalid-json"}

    response = attach_image_to_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Invalid JSON" in body["error"]


def test_attach_image_to_session_missing_message(lambda_context):
    """Test attach_image_to_session with missing message field."""
    event = {"pathParameters": {"sessionId": "test-session"}, "body": json.dumps({})}

    response = attach_image_to_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Pydantic validation error for missing 'message' field
    assert "error" in body


def test_attach_image_to_session_s3_upload_error(lambda_context):
    """Test attach_image_to_session with S3 upload error."""

    image_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"

    event = {
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({"message": {"type": "image_url", "image_url": {"url": image_data}}}),
    }

    with patch("session.lambda_functions.s3_client") as mock_s3:
        mock_s3.put_object.side_effect = Exception("S3 upload failed")

        response = attach_image_to_session(event, lambda_context)
        assert response["statusCode"] == 200  # Should still return success


def test_attach_image_to_session_non_image_message(lambda_context):
    """Test attach_image_to_session with non-image message."""
    event = {
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({"message": {"type": "text", "content": "This is not an image"}}),
    }

    response = attach_image_to_session(event, lambda_context)
    assert response["statusCode"] == 200
    body = response["body"]  # Already a dict, not JSON string
    assert body["type"] == "text"


# Rename Session Tests
def test_rename_session_success(dynamodb_table, lambda_context):
    """Test rename_session with valid data."""
    # Create a session first
    session = {"sessionId": "test-session", "userId": "test-user", "name": "Old Name"}
    dynamodb_table.put_item(Item=session)

    # Create request using RenameSessionRequest model
    rename_request = RenameSessionRequest(name="New Name")

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": rename_request.model_dump_json(),
    }

    with patch("session.lambda_functions.table", dynamodb_table):
        response = rename_session(event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        # Validate response matches SuccessResponse model
        success_response = SuccessResponse.model_validate(body)
        assert "Session name updated successfully" in success_response.message


def test_rename_session_invalid_json(lambda_context):
    """Test rename_session with invalid JSON."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": "invalid-json",
    }

    response = rename_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Invalid JSON" in body["error"]


def test_rename_session_missing_name(lambda_context):
    """Test rename_session with missing name field."""
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({}),
    }

    response = rename_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    # Pydantic validation error for missing 'name' field
    assert "error" in body


# Put Session Edge Cases Tests
@patch("session.lambda_functions._is_session_encryption_enabled")
@patch("session.lambda_functions.migrate_session_to_encrypted")
def test_put_session_encryption_enabled_success(
    mock_migrate, mock_encryption_enabled, dynamodb_table, config_table, sample_session, lambda_context
):
    """Test put_session with encryption enabled and successful encryption."""

    # Mock encryption enabled
    mock_encryption_enabled.return_value = True

    # Mock successful encryption
    encrypted_data = {
        "encrypted_history": "encrypted_history_data",
        "name": "Test Session",
        "encrypted_configuration": "encrypted_config_data",
        "startTime": "2024-01-01T00:00:00",
        "createTime": "2024-01-01T00:00:00",
        "lastUpdated": "2024-01-01T00:00:00",
        "encryption_version": "1.0",
        "is_encrypted": True,
    }
    mock_migrate.return_value = encrypted_data

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({"messages": sample_session["history"], "configuration": sample_session["configuration"]}),
    }

    with patch("session.lambda_functions.table", dynamodb_table):
        response = put_session(event, lambda_context)
        assert response["statusCode"] == 200
        mock_encryption_enabled.assert_called_once()
        mock_migrate.assert_called_once()


@patch("session.lambda_functions._is_session_encryption_enabled")
@patch("session.lambda_functions.migrate_session_to_encrypted")
def test_put_session_encryption_error(
    mock_migrate, mock_encryption_enabled, dynamodb_table, config_table, sample_session, lambda_context
):
    """Test put_session with encryption enabled but encryption error."""
    from utilities.session_encryption import SessionEncryptionError

    # Mock encryption enabled
    mock_encryption_enabled.return_value = True

    # Mock encryption error
    mock_migrate.side_effect = SessionEncryptionError("Encryption failed")

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({"messages": sample_session["history"], "configuration": sample_session["configuration"]}),
    }

    with patch("session.lambda_functions.table", dynamodb_table):
        response = put_session(event, lambda_context)
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "Failed to encrypt session data" in body["error"]


@patch("session.lambda_functions.get_user_context")
@patch("session.lambda_functions.sqs_client")
def test_put_session_sqs_metrics_success(
    mock_sqs_client, mock_get_user_context, dynamodb_table, config_table, sample_session, lambda_context
):
    """Test put_session with successful SQS metrics publishing."""

    # Set environment variable for metrics queue
    os.environ["USAGE_METRICS_QUEUE_NAME"] = "test-metrics-queue"

    # Mock get_user_context
    mock_get_user_context.return_value = ("test-user", False, ["group1", "group2"])

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({"messages": sample_session["history"], "configuration": sample_session["configuration"]}),
    }

    with patch("session.lambda_functions.table", dynamodb_table):
        response = put_session(event, lambda_context)
        assert response["statusCode"] == 200
        mock_sqs_client.send_message.assert_called_once()


@patch("session.lambda_functions.sqs_client")
def test_put_session_sqs_metrics_missing_queue(
    mock_sqs_client, dynamodb_table, config_table, sample_session, lambda_context
):
    """Test put_session with missing USAGE_METRICS_QUEUE_NAME environment variable."""

    # Remove environment variable
    if "USAGE_METRICS_QUEUE_NAME" in os.environ:
        del os.environ["USAGE_METRICS_QUEUE_NAME"]

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({"messages": sample_session["history"], "configuration": sample_session["configuration"]}),
    }

    with patch("session.lambda_functions.table", dynamodb_table):
        response = put_session(event, lambda_context)
        assert response["statusCode"] == 200
        # SQS should not be called
        mock_sqs_client.send_message.assert_not_called()


@patch("session.lambda_functions.get_user_context")
@patch("session.lambda_functions.sqs_client")
def test_put_session_sqs_metrics_error(
    mock_sqs_client, mock_get_user_context, dynamodb_table, config_table, sample_session, lambda_context
):
    """Test put_session with SQS metrics publishing error."""

    # Set environment variable for metrics queue
    os.environ["USAGE_METRICS_QUEUE_NAME"] = "test-metrics-queue"

    # Mock get_user_context
    mock_get_user_context.return_value = ("test-user", False, ["group1", "group2"])

    # Mock SQS error
    mock_sqs_client.send_message.side_effect = Exception("SQS error")

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({"messages": sample_session["history"], "configuration": sample_session["configuration"]}),
    }

    with patch("session.lambda_functions.table", dynamodb_table):
        response = put_session(event, lambda_context)
        assert response["statusCode"] == 200  # Should still succeed despite SQS error


@patch("session.lambda_functions._update_session_with_current_model_config")
def test_put_session_model_config_update(
    mock_update_config, dynamodb_table, config_table, sample_session, lambda_context
):
    """Test put_session with model configuration update."""

    # Mock model config update
    updated_config = {"selectedModel": {"modelId": "test-model", "features": ["new-feature"]}}
    mock_update_config.return_value = updated_config

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps(
            {"messages": sample_session["history"], "configuration": {"selectedModel": {"modelId": "test-model"}}}
        ),
    }

    with patch("session.lambda_functions.table", dynamodb_table):
        response = put_session(event, lambda_context)
        assert response["statusCode"] == 200
        mock_update_config.assert_called_once()


# Import additional functions for testing
from session.lambda_functions import (
    _extract_video_s3_keys,
    _generate_presigned_video_url,
    _map_session,
    _process_video,
)


# Video S3 Key Extraction Tests
def test_extract_video_s3_keys_no_history():
    """Test _extract_video_s3_keys with no history."""
    session = {}
    result = _extract_video_s3_keys(session)
    assert result == []


def test_extract_video_s3_keys_empty_history():
    """Test _extract_video_s3_keys with empty history."""
    session = {"history": []}
    result = _extract_video_s3_keys(session)
    assert result == []


def test_extract_video_s3_keys_no_videos():
    """Test _extract_video_s3_keys with history but no videos."""
    session = {
        "history": [
            {"type": "human", "content": "Hello"},
            {"type": "assistant", "content": "Hi there!"},
        ]
    }
    result = _extract_video_s3_keys(session)
    assert result == []


def test_extract_video_s3_keys_with_videos():
    """Test _extract_video_s3_keys with videos in history."""
    session = {
        "history": [
            {
                "type": "assistant",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": {"url": "https://example.com/video.mp4", "s3_key": "videos/video1.mp4"},
                    }
                ],
            }
        ]
    }
    result = _extract_video_s3_keys(session)
    assert result == ["videos/video1.mp4"]


def test_extract_video_s3_keys_multiple_videos():
    """Test _extract_video_s3_keys with multiple videos."""
    session = {
        "history": [
            {
                "type": "assistant",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": {"url": "https://example.com/video1.mp4", "s3_key": "videos/v1.mp4"},
                    },
                    {
                        "type": "video_url",
                        "video_url": {"url": "https://example.com/video2.mp4", "s3_key": "videos/v2.mp4"},
                    },
                ],
            },
            {
                "type": "assistant",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": {"url": "https://example.com/video3.mp4", "s3_key": "videos/v3.mp4"},
                    },
                ],
            },
        ]
    }
    result = _extract_video_s3_keys(session)
    assert result == ["videos/v1.mp4", "videos/v2.mp4", "videos/v3.mp4"]


def test_extract_video_s3_keys_mixed_content():
    """Test _extract_video_s3_keys with mixed image and video content."""
    session = {
        "history": [
            {
                "type": "assistant",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/image.png", "s3_key": "images/img.png"},
                    },
                    {
                        "type": "video_url",
                        "video_url": {"url": "https://example.com/video.mp4", "s3_key": "videos/vid.mp4"},
                    },
                    {"type": "text", "text": "Here is your content"},
                ],
            }
        ]
    }
    result = _extract_video_s3_keys(session)
    assert result == ["videos/vid.mp4"]


def test_extract_video_s3_keys_no_s3_key():
    """Test _extract_video_s3_keys with video missing s3_key."""
    session = {
        "history": [
            {
                "type": "assistant",
                "content": [
                    {"type": "video_url", "video_url": {"url": "https://example.com/video.mp4"}},  # No s3_key
                ],
            }
        ]
    }
    result = _extract_video_s3_keys(session)
    assert result == []


def test_extract_video_s3_keys_string_content():
    """Test _extract_video_s3_keys with string content (not list)."""
    session = {"history": [{"type": "assistant", "content": "This is a text response"}]}
    result = _extract_video_s3_keys(session)
    assert result == []


# Video URL Generation Tests
@patch("session.lambda_functions.s3_client")
def test_generate_presigned_video_url_success(mock_s3_client):
    """Test _generate_presigned_video_url with success."""
    mock_s3_client.generate_presigned_url.return_value = "https://presigned-video-url.com"

    result = _generate_presigned_video_url("videos/test-video.mp4")
    assert result == "https://presigned-video-url.com"

    mock_s3_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={
            "Bucket": "bucket",
            "Key": "videos/test-video.mp4",
            "ResponseContentType": "video/mp4",
            "ResponseCacheControl": "no-cache",
            "ResponseContentDisposition": "inline",
        },
    )


# Video Processing Tests
def test_process_video_success():
    """Test _process_video with success."""
    msg = {"video_url": {"s3_key": "videos/test.mp4"}}
    key = "videos/test.mp4"

    with patch("session.lambda_functions._generate_presigned_video_url") as mock_generate:
        mock_generate.return_value = "https://presigned-video-url.com"

        _process_video((msg, key))

        assert msg["video_url"]["url"] == "https://presigned-video-url.com"
        mock_generate.assert_called_once_with("videos/test.mp4")


def test_process_video_exception():
    """Test _process_video with exception."""
    msg = {"video_url": {"s3_key": "videos/test.mp4"}}
    key = "videos/test.mp4"

    with patch("session.lambda_functions._generate_presigned_video_url") as mock_generate:
        mock_generate.side_effect = Exception("S3 error")

        # Should not raise exception, just print error
        _process_video((msg, key))

        # URL should not be set
        assert "url" not in msg["video_url"]


# Map Session Tests
def test_map_session_complete_data():
    """Test _map_session with complete session data."""
    session = {
        "sessionId": "test-session-123",
        "name": "Test Session",
        "history": [{"type": "human", "content": "Hello"}],
        "startTime": "2024-01-01T00:00:00",
        "createTime": "2024-01-01T00:00:00",
        "lastUpdated": "2024-01-02T00:00:00",
        "is_encrypted": False,
    }

    result = _map_session(session, "test-user")

    # Result is a SessionSummary model - use property access
    assert result.sessionId == "test-session-123"
    assert result.name == "Test Session"
    assert result.firstHumanMessage == "Hello"
    assert result.startTime == "2024-01-01T00:00:00"
    assert result.createTime == "2024-01-01T00:00:00"
    assert result.lastUpdated == "2024-01-02T00:00:00"
    assert result.isEncrypted is False


def test_map_session_missing_fields():
    """Test _map_session with missing optional fields."""
    session = {"sessionId": "test-session", "history": []}

    result = _map_session(session, "test-user")

    # Result is a SessionSummary model - use property access
    assert result.sessionId == "test-session"
    assert result.name is None
    assert result.firstHumanMessage == ""
    assert result.startTime is None
    assert result.createTime is None
    assert result.lastUpdated is None
    assert result.isEncrypted is False


def test_map_session_fallback_to_start_time():
    """Test _map_session falls back to startTime for lastUpdated."""
    session = {
        "sessionId": "test-session",
        "startTime": "2024-01-01T00:00:00",
        "history": [],
        # No lastUpdated field
    }

    result = _map_session(session, "test-user")

    # Result is a SessionSummary model - use property access
    assert result.lastUpdated == "2024-01-01T00:00:00"


def test_map_session_encrypted():
    """Test _map_session with encrypted session."""
    session = {
        "sessionId": "test-session",
        "is_encrypted": True,
        "encrypted_history": "encrypted_data",
    }

    with patch("session.lambda_functions.decrypt_session_fields") as mock_decrypt:
        mock_decrypt.return_value = {
            "sessionId": "test-session",
            "history": [{"type": "human", "content": "Decrypted message"}],
        }

        result = _map_session(session, "test-user")

        # Result is a SessionSummary model - use property access
        assert result.isEncrypted is True
        assert result.firstHumanMessage == "Decrypted message"


# Delete Session with Video Cleanup Tests
@patch("session.lambda_functions.s3_client")
@patch("session.lambda_functions.s3_resource")
@patch("session.lambda_functions.table")
def test_delete_user_session_with_video_cleanup(mock_table, mock_s3_resource, mock_s3_client):
    """Test _delete_user_session with successful video cleanup."""
    # Mock session with videos
    session_with_videos = {
        "sessionId": "test-session",
        "userId": "test-user",
        "history": [
            {
                "type": "assistant",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": {"url": "https://example.com/v1.mp4", "s3_key": "videos/v1.mp4"},
                    },
                    {
                        "type": "video_url",
                        "video_url": {"url": "https://example.com/v2.mp4", "s3_key": "videos/v2.mp4"},
                    },
                ],
            }
        ],
    }

    mock_table.get_item.return_value = {"Item": session_with_videos}
    mock_bucket = MagicMock()
    mock_s3_resource.Bucket.return_value = mock_bucket

    result = _delete_user_session("test-session", "test-user")

    # Result is a DeleteResponse model - use property access
    assert result.deleted is True
    mock_table.delete_item.assert_called_once()
    mock_bucket.objects.filter.assert_called_once_with(Prefix="images/test-session")

    # Verify video deletion calls
    assert mock_s3_client.delete_object.call_count == 2
    mock_s3_client.delete_object.assert_any_call(Bucket="bucket", Key="videos/v1.mp4")
    mock_s3_client.delete_object.assert_any_call(Bucket="bucket", Key="videos/v2.mp4")


@patch("session.lambda_functions.decrypt_session_fields")
@patch("session.lambda_functions.s3_client")
@patch("session.lambda_functions.s3_resource")
@patch("session.lambda_functions.table")
def test_delete_user_session_encrypted_with_videos(mock_table, mock_s3_resource, mock_s3_client, mock_decrypt):
    """Test _delete_user_session with encrypted session containing videos."""
    # Mock encrypted session
    encrypted_session = {
        "sessionId": "test-session",
        "userId": "test-user",
        "is_encrypted": True,
        "encrypted_history": "encrypted_data",
    }

    # Mock decrypted session with videos
    decrypted_session = {
        "sessionId": "test-session",
        "userId": "test-user",
        "history": [
            {
                "type": "assistant",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": {"url": "https://example.com/v1.mp4", "s3_key": "videos/v1.mp4"},
                    },
                ],
            }
        ],
    }

    mock_table.get_item.return_value = {"Item": encrypted_session}
    mock_decrypt.return_value = decrypted_session
    mock_bucket = MagicMock()
    mock_s3_resource.Bucket.return_value = mock_bucket

    result = _delete_user_session("test-session", "test-user")

    # Result is a DeleteResponse model - use property access
    assert result.deleted is True
    mock_decrypt.assert_called_once_with(encrypted_session, "test-user", "test-session")
    mock_s3_client.delete_object.assert_called_once_with(Bucket="bucket", Key="videos/v1.mp4")


@patch("session.lambda_functions.decrypt_session_fields")
@patch("session.lambda_functions.s3_client")
@patch("session.lambda_functions.s3_resource")
@patch("session.lambda_functions.table")
def test_delete_user_session_encrypted_decryption_fails(mock_table, mock_s3_resource, mock_s3_client, mock_decrypt):
    """Test _delete_user_session when decryption fails - should still delete session."""
    from utilities.session_encryption import SessionEncryptionError

    encrypted_session = {
        "sessionId": "test-session",
        "userId": "test-user",
        "is_encrypted": True,
        "encrypted_history": "encrypted_data",
    }

    mock_table.get_item.return_value = {"Item": encrypted_session}
    mock_decrypt.side_effect = SessionEncryptionError("Decryption failed")
    mock_bucket = MagicMock()
    mock_s3_resource.Bucket.return_value = mock_bucket

    result = _delete_user_session("test-session", "test-user")

    # Result is a DeleteResponse model - use property access
    # Should still succeed with deletion, just no video cleanup
    assert result.deleted is True
    mock_table.delete_item.assert_called_once()
    # No video deletion because decryption failed
    mock_s3_client.delete_object.assert_not_called()


@patch("session.lambda_functions.s3_client")
@patch("session.lambda_functions.s3_resource")
@patch("session.lambda_functions.table")
def test_delete_user_session_video_deletion_error(mock_table, mock_s3_resource, mock_s3_client):
    """Test _delete_user_session when video deletion fails - should continue."""
    from botocore.exceptions import ClientError

    session_with_videos = {
        "sessionId": "test-session",
        "userId": "test-user",
        "history": [
            {
                "type": "assistant",
                "content": [
                    {"type": "video_url", "video_url": {"s3_key": "videos/v1.mp4"}},
                    {"type": "video_url", "video_url": {"s3_key": "videos/v2.mp4"}},
                ],
            }
        ],
    }

    mock_table.get_item.return_value = {"Item": session_with_videos}
    mock_bucket = MagicMock()
    mock_s3_resource.Bucket.return_value = mock_bucket

    # First video deletion fails, second succeeds
    mock_s3_client.delete_object.side_effect = [
        ClientError(error_response={"Error": {"Code": "AccessDenied"}}, operation_name="DeleteObject"),
        None,
    ]

    result = _delete_user_session("test-session", "test-user")

    # Result is a DeleteResponse model - use property access
    # Should still succeed - video deletion errors are logged but don't fail the operation
    assert result.deleted is True
    assert mock_s3_client.delete_object.call_count == 2


# Get Session with Video Processing Tests
def test_get_session_with_videos(dynamodb_table, lambda_context):
    """Test get_session processes video URLs correctly."""
    session_with_video = {
        "sessionId": "test-session",
        "userId": "test-user",
        "history": [
            {
                "type": "assistant",
                "content": [
                    {"type": "video_url", "video_url": {"s3_key": "videos/test.mp4"}},
                ],
            }
        ],
    }
    dynamodb_table.put_item(Item=session_with_video)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"sessionId": "test-session"},
    }

    with patch("session.lambda_functions._process_video") as mock_process_video:
        response = get_session(event, lambda_context)
        assert response["statusCode"] == 200
        # Video processing should be called
        mock_process_video.assert_called()


# Attach Image Tests
def test_attach_image_to_session_https_url(lambda_context):
    """Test attach_image_to_session with already-https URL (should not upload)."""
    event = {
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps(
            {"message": {"type": "image_url", "image_url": {"url": "https://already-uploaded.com/image.png"}}}
        ),
    }

    with patch("session.lambda_functions.s3_client") as mock_s3:
        response = attach_image_to_session(event, lambda_context)
        assert response["statusCode"] == 200
        body = response["body"]
        # Should return the message unchanged, S3 should not be called
        assert body["image_url"]["url"] == "https://already-uploaded.com/image.png"
        mock_s3.put_object.assert_not_called()


def test_attach_image_to_session_missing_session_id(lambda_context):
    """Test attach_image_to_session with missing session ID."""
    mock_common.get_session_id.side_effect = ValueError("Missing sessionId")

    event = {"body": json.dumps({"message": {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}})}

    response = attach_image_to_session(event, lambda_context)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "Missing sessionId" in body["error"]

    # Reset the mock
    mock_common.get_session_id.side_effect = None
    mock_common.get_session_id.return_value = "test-session"


# Put Session API Token Auth Tests
@patch("session.lambda_functions.get_user_context")
@patch("session.lambda_functions.sqs_client")
def test_put_session_api_token_skips_metrics(
    mock_sqs_client, mock_get_user_context, dynamodb_table, config_table, sample_session, lambda_context
):
    """Test put_session with API token auth type skips SQS metrics."""
    os.environ["USAGE_METRICS_QUEUE_NAME"] = "test-metrics-queue"
    mock_get_user_context.return_value = ("test-user", False, ["group1"])

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}, "authType": "api_token"}},
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({"messages": sample_session["history"], "configuration": sample_session["configuration"]}),
    }

    with patch("session.lambda_functions.table", dynamodb_table):
        response = put_session(event, lambda_context)
        assert response["statusCode"] == 200
        # SQS should not be called for API token users
        mock_sqs_client.send_message.assert_not_called()


# List Sessions with Encrypted Sessions Tests
def test_list_sessions_with_encrypted_sessions(dynamodb_table, lambda_context):
    """Test list_sessions handles encrypted sessions correctly."""
    encrypted_session = {
        "sessionId": "encrypted-session",
        "userId": "test-user",
        "is_encrypted": True,
        "encrypted_history": "encrypted_data",
        "startTime": "2024-01-01T00:00:00",
    }
    dynamodb_table.put_item(Item=encrypted_session)

    event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

    with patch("session.lambda_functions.decrypt_session_fields") as mock_decrypt:
        mock_decrypt.return_value = {
            "sessionId": "encrypted-session",
            "history": [{"type": "human", "content": "Decrypted message"}],
        }

        response = list_sessions(event, lambda_context)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body) == 1
        # Validate response matches SessionSummary model
        session_summary = SessionSummary.model_validate(body[0])
        assert session_summary.sessionId == "encrypted-session"
        assert session_summary.isEncrypted is True


# Find First Human Message with List Content and Empty Text
def test_find_first_human_message_list_content_empty_text():
    """Test _find_first_human_message with list content containing empty text items."""
    session = {
        "sessionId": "test-session",
        "is_encrypted": False,
        "history": [
            {"type": "human", "content": [{"text": ""}, {"text": "Actual message"}]},
        ],
    }

    result = _find_first_human_message(session, "test-user")
    assert result == "Actual message"


def test_find_first_human_message_list_content_no_text_key():
    """Test _find_first_human_message with list content items missing text key."""
    session = {
        "sessionId": "test-session",
        "is_encrypted": False,
        "history": [
            {"type": "human", "content": [{"image": "data:image/png"}, {"text": "Message after image"}]},
        ],
    }

    result = _find_first_human_message(session, "test-user")
    assert result == "Message after image"
