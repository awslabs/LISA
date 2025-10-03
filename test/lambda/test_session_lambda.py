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

"""
Refactored session lambda tests using fixture-based mocking instead of global mocks.
This replaces the original test_session_lambda.py with isolated, maintainable tests.
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from moto import mock_aws
import boto3
from conftest import SessionTestHelper, LambdaTestHelper


# Set up test environment variables
@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    env_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing", 
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "SESSIONS_TABLE_NAME": "sessions-table",
        "SESSIONS_BY_USER_ID_INDEX_NAME": "sessions-by-user-id-index",
        "GENERATED_IMAGES_S3_BUCKET_NAME": "test-bucket",
        "MODEL_TABLE_NAME": "model-table",
        "CONFIG_TABLE_NAME": "config-table",
        "SESSION_ENCRYPTION_KEY_ARN": "arn:aws:kms:us-east-1:123456789012:key/test-key"
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    yield
    
    # Cleanup
    for key in env_vars.keys():
        if key in os.environ:
            del os.environ[key]


@pytest.fixture
def dynamodb_service():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture
def sessions_table(dynamodb_service):
    """Create a mock sessions DynamoDB table."""
    table = dynamodb_service.create_table(
        TableName="sessions-table",
        KeySchema=[
            {"AttributeName": "sessionId", "KeyType": "HASH"},
            {"AttributeName": "userId", "KeyType": "RANGE"}
        ],
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
    table.wait_until_exists()
    return table


@pytest.fixture
def config_table(dynamodb_service):
    """Create a mock config DynamoDB table."""
    table = dynamodb_service.create_table(
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
    return table


@pytest.fixture
def mock_session_functions():
    """Mock session-specific functions."""
    with patch('session.lambda_functions.table') as mock_table, \
         patch('session.lambda_functions.config_table') as mock_config_table, \
         patch('session.lambda_functions.s3_resource') as mock_s3_resource, \
         patch('session.lambda_functions.s3_client') as mock_s3_client:
        
        yield {
            'table': mock_table,
            'config_table': mock_config_table,
            's3_resource': mock_s3_resource,
            's3_client': mock_s3_client
        }


# Test list_sessions function
def test_list_sessions(sessions_table, mock_session_auth, lambda_context):
    """Test list_sessions function - REFACTORED VERSION."""
    from session.lambda_functions import list_sessions
    
    # Create test sessions
    session1_data = SessionTestHelper.create_session_data("session-1", "test-user")
    session2_data = SessionTestHelper.create_session_data("session-2", "test-user")
    
    sessions_table.put_item(Item=session1_data)
    sessions_table.put_item(Item=session2_data)
    
    # Create test event
    event = SessionTestHelper.create_session_event(username="test-user")
    del event["pathParameters"]  # list_sessions doesn't need sessionId
    
    # Mock the table reference
    with patch('session.lambda_functions.table', sessions_table):
        response = list_sessions(event, lambda_context)
    
    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 2
    session_ids = [session["sessionId"] for session in body]
    assert "session-1" in session_ids
    assert "session-2" in session_ids


def test_get_session(sessions_table, mock_session_auth, lambda_context):
    """Test get_session function - REFACTORED VERSION."""
    from session.lambda_functions import get_session
    
    # Create test session
    session_data = SessionTestHelper.create_session_data("test-session", "test-user")
    sessions_table.put_item(Item=session_data)
    
    # Create test event
    event = SessionTestHelper.create_session_event("test-session", "test-user")
    
    # Mock the table reference and model config update
    with patch('session.lambda_functions.table', sessions_table), \
         patch('session.lambda_functions._update_session_with_current_model_config') as mock_update_config:
        
        # Mock config update to return the original config
        mock_update_config.return_value = session_data.get("configuration", {})
        
        response = get_session(event, lambda_context)
    
    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["sessionId"] == "test-session"
    assert body["userId"] == "test-user"


def test_get_session_not_found(sessions_table, mock_session_auth, lambda_context):
    """Test get_session with non-existent session - REFACTORED VERSION."""
    from session.lambda_functions import get_session
    
    # Create test event for non-existent session
    event = SessionTestHelper.create_session_event("non-existent-session", "test-user")
    
    # Mock the table reference
    with patch('session.lambda_functions.table', sessions_table):
        response = get_session(event, lambda_context)
    
    # The api_wrapper wraps the response, so we need to extract the inner response
    assert response["statusCode"] == 200  # api_wrapper always returns 200
    inner_response = json.loads(response["body"])  # Get the actual response
    assert inner_response["statusCode"] == 404
    inner_body = json.loads(inner_response["body"])
    assert "error" in inner_body


def test_put_session(sessions_table, config_table, mock_session_auth, lambda_context):
    """Test put_session function - REFACTORED VERSION."""
    from session.lambda_functions import put_session
    
    # Create test data
    session_data = SessionTestHelper.create_session_data("test-session", "test-user")
    
    # Create test event
    event = SessionTestHelper.create_session_event("test-session", "test-user")
    event["body"] = json.dumps({
        "messages": session_data["history"],
        "configuration": session_data["configuration"]
    })
    
    # Mock dependencies
    with patch('session.lambda_functions.table', sessions_table), \
         patch('session.lambda_functions.config_table', config_table), \
         patch('session.lambda_functions._is_session_encryption_enabled') as mock_encryption, \
         patch('session.lambda_functions._update_session_with_current_model_config') as mock_update_config:
        
        # Configure mocks
        mock_encryption.return_value = False  # Disable encryption for simpler test
        mock_update_config.return_value = session_data["configuration"]
        
        response = put_session(event, lambda_context)
    
    # Verify response
    assert response["statusCode"] == 200


def test_put_session_invalid_json(mock_session_auth, lambda_context):
    """Test put_session with invalid JSON - REFACTORED VERSION."""
    from session.lambda_functions import put_session
    
    # Create test event with invalid JSON
    event = SessionTestHelper.create_session_event("test-session", "test-user")
    event["body"] = "invalid-json"
    
    response = put_session(event, lambda_context)
    
    # Verify response (api_wrapper wraps the response)
    assert response["statusCode"] == 200  # api_wrapper always returns 200
    inner_response = json.loads(response["body"])  # Get the actual response
    assert inner_response["statusCode"] == 400
    inner_body = json.loads(inner_response["body"])
    assert "Invalid JSON" in inner_body["error"]


def test_delete_session(sessions_table, mock_session_auth, lambda_context):
    """Test delete_session function - REFACTORED VERSION."""
    from session.lambda_functions import delete_session
    
    # Create test session
    session_data = SessionTestHelper.create_session_data("test-session", "test-user")
    sessions_table.put_item(Item=session_data)
    
    # Create test event
    event = SessionTestHelper.create_session_event("test-session", "test-user")
    
    # Mock the _delete_user_session function to avoid S3 operations
    with patch('session.lambda_functions.table', sessions_table), \
         patch('session.lambda_functions._delete_user_session') as mock_delete:
        
        mock_delete.return_value = {"deleted": True}
        
        response = delete_session(event, lambda_context)
    
    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["deleted"] is True


def test_delete_user_sessions(sessions_table, mock_session_auth, lambda_context):
    """Test delete_user_sessions function - REFACTORED VERSION."""
    from session.lambda_functions import delete_user_sessions
    
    # Create test sessions
    session1_data = SessionTestHelper.create_session_data("session-1", "test-user")
    session2_data = SessionTestHelper.create_session_data("session-2", "test-user")
    
    sessions_table.put_item(Item=session1_data)
    sessions_table.put_item(Item=session2_data)
    
    # Create test event
    event = LambdaTestHelper.create_basic_event("test-user")
    
    # Mock dependencies
    with patch('session.lambda_functions.table', sessions_table), \
         patch('session.lambda_functions._get_all_user_sessions') as mock_get_sessions, \
         patch('session.lambda_functions._delete_user_session') as mock_delete:
        
        # Configure mocks
        mock_get_sessions.return_value = [session1_data, session2_data]
        mock_delete.return_value = {"deleted": True}
        
        response = delete_user_sessions(event, lambda_context)
    
    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["deleted"] is True


def test_rename_session(sessions_table, mock_session_auth, lambda_context):
    """Test rename_session function - REFACTORED VERSION."""
    from session.lambda_functions import rename_session

    # Create test session
    session_data = SessionTestHelper.create_session_data("test-session", "test-user")
    session_data["name"] = "Old Name"
    sessions_table.put_item(Item=session_data)

    # Create test event
    event = SessionTestHelper.create_session_event("test-session", "test-user")
    event["body"] = json.dumps({"name": "New Name"})

    # Mock the table reference
    with patch('session.lambda_functions.table', sessions_table):
        response = rename_session(event, lambda_context)

    # Verify response - api_wrapper returns 200 with inner response in body
    assert response["statusCode"] == 200
    inner_response = json.loads(response["body"])
    assert inner_response["statusCode"] == 200
    inner_body = json.loads(inner_response["body"])
    assert "Session name updated successfully" in inner_body["message"]


def test_rename_session_missing_name(mock_session_auth, lambda_context):
    """Test rename_session with missing name field - REFACTORED VERSION."""
    from session.lambda_functions import rename_session
    
    # Create test event without name
    event = SessionTestHelper.create_session_event("test-session", "test-user")
    event["body"] = json.dumps({})
    
    response = rename_session(event, lambda_context)
    
    # Verify response (api_wrapper wraps the response)
    assert response["statusCode"] == 200  # api_wrapper always returns 200
    inner_response = json.loads(response["body"])  # Get the actual response
    assert inner_response["statusCode"] == 400
    inner_body = json.loads(inner_response["body"])
    assert "Missing required field: name" in inner_body["error"]


def test_attach_image_to_session(mock_aws_services, lambda_context):
    """Test attach_image_to_session function - REFACTORED VERSION."""
    from session.lambda_functions import attach_image_to_session

    # Create test data with base64 image
    image_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    # Create test event
    event = {
        "pathParameters": {"sessionId": "test-session"},
        "body": json.dumps({
            "message": {
                "type": "image_url",
                "image_url": {"url": image_data}
            }
        })
    }

    # Mock S3 operations and presigned URL generation
    with patch('session.lambda_functions.s3_client', mock_aws_services['s3']), \
         patch('session.lambda_functions._generate_presigned_image_url') as mock_generate:

        mock_generate.return_value = "https://test-presigned-url"

        response = attach_image_to_session(event, lambda_context)

    # Verify response - api_wrapper returns 200 with inner response in body
    assert response["statusCode"] == 200
    inner_response = json.loads(response["body"])
    assert inner_response["statusCode"] == 200
    # The body contains the processed message object
    body = inner_response["body"]
    assert body["image_url"]["url"] == "https://test-presigned-url"


def test_attach_image_invalid_json(lambda_context):
    """Test attach_image_to_session with invalid JSON - REFACTORED VERSION."""
    from session.lambda_functions import attach_image_to_session
    
    # Create test event with invalid JSON
    event = {
        "pathParameters": {"sessionId": "test-session"},
        "body": "invalid-json"
    }
    
    response = attach_image_to_session(event, lambda_context)
    
    # Verify response (api_wrapper wraps the response)
    assert response["statusCode"] == 200  # api_wrapper always returns 200
    inner_response = json.loads(response["body"])  # Get the actual response
    assert inner_response["statusCode"] == 400
    inner_body = json.loads(inner_response["body"])
    assert "Invalid JSON" in inner_body["error"]


# Test session encryption functionality
def test_is_session_encryption_enabled(config_table, lambda_context):
    """Test _is_session_encryption_enabled function - REFACTORED VERSION."""
    from session.lambda_functions import _is_session_encryption_enabled, cache
    
    # Add config entry with encryption enabled
    config_table.put_item(
        Item={
            "configScope": "global",
            "versionId": 0,
            "configuration": {"enabledComponents": {"encryptSession": True}},
            "created_at": "1234567890",
        }
    )
    
    # Clear cache to ensure fresh result
    cache.clear()
    
    # Mock the config table reference
    with patch('session.lambda_functions.config_table', config_table):
        result = _is_session_encryption_enabled()
    
    assert result is True


def test_get_current_model_config():
    """Test _get_current_model_config function - REFACTORED VERSION."""
    from session.lambda_functions import _get_current_model_config
    
    # Mock model table
    mock_model_table = MagicMock()
    mock_model_table.get_item.return_value = {
        "Item": {
            "model_id": "test-model",
            "model_config": {
                "features": ["feature1"],
                "streaming": True
            }
        }
    }
    
    with patch('session.lambda_functions.model_table', mock_model_table):
        result = _get_current_model_config("test-model")
    
    assert result == {"features": ["feature1"], "streaming": True}


def test_get_current_model_config_missing_table():
    """Test _get_current_model_config with missing table - REFACTORED VERSION."""
    from session.lambda_functions import _get_current_model_config
    
    with patch('session.lambda_functions.model_table', None):
        result = _get_current_model_config("test-model")
    
    assert result == {}


def test_update_session_with_current_model_config():
    """Test _update_session_with_current_model_config function - REFACTORED VERSION."""
    from session.lambda_functions import _update_session_with_current_model_config
    
    session_config = {"selectedModel": {"modelId": "test-model"}}
    current_model_config = {
        "features": ["new-feature"],
        "streaming": False,
        "modelType": "updated-type"
    }
    
    with patch('session.lambda_functions._get_current_model_config') as mock_get_config:
        mock_get_config.return_value = current_model_config
        
        result = _update_session_with_current_model_config(session_config)
    
    # Verify the selectedModel was updated
    assert result["selectedModel"]["features"] == ["new-feature"]
    assert result["selectedModel"]["streaming"] is False
    assert result["selectedModel"]["modelType"] == "updated-type"


def test_find_first_human_message():
    """Test _find_first_human_message function - REFACTORED VERSION."""
    from session.lambda_functions import _find_first_human_message
    
    # Test with unencrypted session
    session = {
        "sessionId": "test-session",
        "is_encrypted": False,
        "history": [
            {"type": "human", "content": "Hello world"},
            {"type": "assistant", "content": "Hi there!"}
        ]
    }
    
    result = _find_first_human_message(session, "test-user")
    assert result == "Hello world"


def test_find_first_human_message_encrypted():
    """Test _find_first_human_message with encrypted session - REFACTORED VERSION."""
    from session.lambda_functions import _find_first_human_message
    
    # Test with encrypted session
    session = {
        "sessionId": "test-session",
        "is_encrypted": True,
        "history": [{"type": "human", "content": "Encrypted content"}]
    }
    
    # Mock successful decryption
    with patch('session.lambda_functions.decrypt_session_fields') as mock_decrypt:
        decrypted_session = {
            "sessionId": "test-session",
            "is_encrypted": False,
            "history": [{"type": "human", "content": "Decrypted Hello"}]
        }
        mock_decrypt.return_value = decrypted_session
        
        result = _find_first_human_message(session, "test-user")
    
    assert result == "Decrypted Hello"


def test_find_first_human_message_no_user_id():
    """Test _find_first_human_message encrypted session without user_id - REFACTORED VERSION."""
    from session.lambda_functions import _find_first_human_message
    
    session = {
        "sessionId": "test-session", 
        "is_encrypted": True,
        "history": [{"type": "human", "content": "Hello"}]
    }
    
    result = _find_first_human_message(session, None)
    assert result == "[Encrypted Session - User ID required]"


def test_process_image_success():
    """Test _process_image function - REFACTORED VERSION."""
    from session.lambda_functions import _process_image
    
    msg = {"image_url": {"s3_key": "test-key"}}
    key = "test-key"
    
    with patch('session.lambda_functions._generate_presigned_image_url') as mock_generate:
        mock_generate.return_value = "https://presigned-url.com"
        
        _process_image((msg, key))
    
    assert msg["image_url"]["url"] == "https://presigned-url.com"
    mock_generate.assert_called_once_with("test-key")


def test_generate_presigned_image_url(mock_aws_services):
    """Test _generate_presigned_image_url function - REFACTORED VERSION."""
    from session.lambda_functions import _generate_presigned_image_url

    with patch('session.lambda_functions.s3_client', mock_aws_services['s3']):
        result = _generate_presigned_image_url("test-key")

    # Check that result is a valid presigned URL string
    assert isinstance(result, str)
    assert result.startswith("https://")
    assert "test-key" in result
    # Note: mock_aws_services['s3'] is a real moto client, not a MagicMock, so no assert_called_once()


# Test error handling
def test_get_session_encrypted_decryption_error(sessions_table, mock_session_auth, lambda_context):
    """Test get_session with encrypted session decryption error - REFACTORED VERSION."""
    from session.lambda_functions import get_session
    from utilities.session_encryption import SessionEncryptionError
    
    # Create encrypted session
    encrypted_session = SessionTestHelper.create_session_data("test-session", "test-user")
    encrypted_session["is_encrypted"] = True
    encrypted_session["encrypted_history"] = "encrypted_data"
    sessions_table.put_item(Item=encrypted_session)
    
    # Create test event
    event = SessionTestHelper.create_session_event("test-session", "test-user")
    
    # Mock decryption error
    with patch('session.lambda_functions.table', sessions_table), \
         patch('session.lambda_functions.decrypt_session_fields') as mock_decrypt:
        
        mock_decrypt.side_effect = SessionEncryptionError("Decryption failed")
        
        response = get_session(event, lambda_context)
    
    # Verify response (api_wrapper wraps the response)
    assert response["statusCode"] == 200  # api_wrapper always returns 200
    inner_response = json.loads(response["body"])  # Get the actual response
    assert inner_response["statusCode"] == 500
    inner_body = json.loads(inner_response["body"])
    assert "Failed to decrypt session data" in inner_body["error"]


def test_put_session_with_encryption_enabled(sessions_table, config_table, mock_session_auth, lambda_context):
    """Test put_session with encryption enabled - REFACTORED VERSION."""
    from session.lambda_functions import put_session
    
    # Create test data
    session_data = SessionTestHelper.create_session_data("test-session", "test-user")
    
    # Create test event
    event = SessionTestHelper.create_session_event("test-session", "test-user")
    event["body"] = json.dumps({
        "messages": session_data["history"],
        "configuration": session_data["configuration"]
    })
    
    # Mock dependencies
    with patch('session.lambda_functions.table', sessions_table), \
         patch('session.lambda_functions.config_table', config_table), \
         patch('session.lambda_functions._is_session_encryption_enabled') as mock_encryption, \
         patch('session.lambda_functions.migrate_session_to_encrypted') as mock_migrate, \
         patch('session.lambda_functions._update_session_with_current_model_config') as mock_update_config:

        # Configure mocks for encryption
        mock_encryption.return_value = True
        mock_migrate.return_value = {
            "encrypted_history": "encrypted_history_data",
            "name": session_data.get("name"),
            "encrypted_configuration": "encrypted_configuration_data", 
            "startTime": "2024-01-01T00:00:00.000000",
            "createTime": "2024-01-01T00:00:00.000000",
            "lastUpdated": "2024-01-01T00:00:00.000000",
            "is_encrypted": True,
            "encryption_version": "1.0"
        }
        mock_update_config.return_value = session_data["configuration"]
        
        response = put_session(event, lambda_context)
    
    # Verify response
    assert response["statusCode"] == 200
    mock_encryption.assert_called_once()
    mock_migrate.assert_called_once()
