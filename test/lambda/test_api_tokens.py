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

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws
from pydantic import ValidationError

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["TOKEN_TABLE_NAME"] = "test-token-table"

# Import after environment setup
from api_tokens.domain_objects import (
    CreateTokenAdminRequest,
    CreateTokenResponse,
    CreateTokenUserRequest,
    default_expiration,
    DeleteTokenResponse,
    ListTokensResponse,
    TokenInfo,
)
from api_tokens.exception import ForbiddenError, TokenAlreadyExistsError, TokenNotFoundError, UnauthorizedError
from api_tokens.handler import (
    CreateTokenAdminHandler,
    CreateTokenUserHandler,
    DeleteTokenHandler,
    GetTokenHandler,
    ListTokensHandler,
)

# =====================
# Fixtures
# =====================


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def token_table(dynamodb):
    """Create a mock DynamoDB table for tokens."""
    table = dynamodb.create_table(
        TableName="test-token-table",
        KeySchema=[{"AttributeName": "token", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "token", "AttributeType": "S"},
            {"AttributeName": "username", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "username-index",
                "KeySchema": [{"AttributeName": "username", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture
def future_timestamp():
    """Get a timestamp 90 days in the future."""
    return int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())


@pytest.fixture
def past_timestamp():
    """Get a timestamp 1 day in the past."""
    return int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())


# =====================
# Test domain_objects.py
# =====================


def test_default_expiration():
    """Test default_expiration function returns future timestamp."""
    expiration = default_expiration()
    current_time = int(datetime.now(timezone.utc).timestamp())
    assert expiration > current_time
    # Should be approximately 90 days in the future
    expected_time = int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())
    assert abs(expiration - expected_time) < 10  # Within 10 seconds tolerance


def test_create_token_admin_request_valid(future_timestamp):
    """Test CreateTokenAdminRequest with valid data."""
    request = CreateTokenAdminRequest(
        tokenExpiration=future_timestamp, groups=["admin", "users"], name="Test Token", isSystemToken=True
    )
    assert request.tokenExpiration == future_timestamp
    assert request.groups == ["admin", "users"]
    assert request.name == "Test Token"
    assert request.isSystemToken is True


def test_create_token_admin_request_defaults():
    """Test CreateTokenAdminRequest with default values."""
    request = CreateTokenAdminRequest(name="Test Token")
    assert request.tokenExpiration > int(datetime.now(timezone.utc).timestamp())
    assert request.groups == []
    assert request.isSystemToken is False


def test_create_token_admin_request_invalid_expiration(past_timestamp):
    """Test CreateTokenAdminRequest rejects past expiration."""
    with pytest.raises(ValidationError) as excinfo:
        CreateTokenAdminRequest(tokenExpiration=past_timestamp, name="Test Token")
    assert "tokenExpiration must be in the future" in str(excinfo.value)


def test_create_token_user_request_valid(future_timestamp):
    """Test CreateTokenUserRequest with valid data."""
    request = CreateTokenUserRequest(name="My Token", tokenExpiration=future_timestamp)
    assert request.name == "My Token"
    assert request.tokenExpiration == future_timestamp


def test_create_token_user_request_defaults():
    """Test CreateTokenUserRequest with default values."""
    request = CreateTokenUserRequest(name="My Token")
    assert request.tokenExpiration > int(datetime.now(timezone.utc).timestamp())


def test_create_token_user_request_invalid_expiration(past_timestamp):
    """Test CreateTokenUserRequest rejects past expiration."""
    with pytest.raises(ValidationError) as excinfo:
        CreateTokenUserRequest(name="My Token", tokenExpiration=past_timestamp)
    assert "tokenExpiration must be in the future" in str(excinfo.value)


def test_create_token_response():
    """Test CreateTokenResponse model."""
    response = CreateTokenResponse(
        token="abc123",
        tokenUUID="uuid-123",
        tokenExpiration=1234567890,
        createdDate=1234567800,
        username="testuser",
        name="Test Token",
        groups=["admin"],
        isSystemToken=False,
    )
    assert response.token == "abc123"
    assert response.tokenUUID == "uuid-123"
    assert response.username == "testuser"


def test_token_info():
    """Test TokenInfo model."""
    token_info = TokenInfo(
        tokenUUID="uuid-123",
        tokenExpiration=1234567890,
        createdDate=1234567800,
        username="testuser",
        createdBy="admin",
        name="Test Token",
        groups=["admin"],
        isSystemToken=False,
        isExpired=False,
        isLegacy=False,
    )
    assert token_info.tokenUUID == "uuid-123"
    assert token_info.isExpired is False
    assert token_info.isLegacy is False


def test_list_tokens_response():
    """Test ListTokensResponse model."""
    tokens = [
        TokenInfo(
            tokenUUID="uuid-1",
            tokenExpiration=1234567890,
            createdDate=1234567800,
            username="user1",
            createdBy="admin",
            name="Token 1",
            groups=[],
            isSystemToken=False,
            isExpired=False,
        )
    ]
    response = ListTokensResponse(tokens=tokens)
    assert len(response.tokens) == 1
    assert response.tokens[0].tokenUUID == "uuid-1"


def test_delete_token_response():
    """Test DeleteTokenResponse model."""
    response = DeleteTokenResponse(message="Token deleted", tokenUUID="uuid-123")
    assert response.message == "Token deleted"
    assert response.tokenUUID == "uuid-123"


# =====================
# Test exception.py
# =====================


def test_token_already_exists_error():
    """Test TokenAlreadyExistsError exception."""
    error = TokenAlreadyExistsError("Token exists")
    assert str(error) == "Token exists"
    assert isinstance(error, LookupError)


def test_token_not_found_error():
    """Test TokenNotFoundError exception."""
    error = TokenNotFoundError("Token not found")
    assert str(error) == "Token not found"
    assert isinstance(error, Exception)


def test_unauthorized_error():
    """Test UnauthorizedError exception."""
    error = UnauthorizedError("Not authorized")
    assert str(error) == "Not authorized"
    assert isinstance(error, Exception)


def test_forbidden_error():
    """Test ForbiddenError exception."""
    error = ForbiddenError("Forbidden")
    assert str(error) == "Forbidden"
    assert isinstance(error, Exception)


# =====================
# Test handler.py - CreateTokenAdminHandler
# =====================


@patch("api_tokens.handler.generate_token")
@patch("api_tokens.handler.hash_token")
@patch("api_tokens.handler.uuid4")
def test_create_token_admin_handler_success(mock_uuid, mock_hash, mock_generate, token_table, future_timestamp):
    """Test CreateTokenAdminHandler successfully creates token."""
    mock_generate.return_value = "plain-token-123"
    mock_hash.return_value = "hashed-token-123"
    mock_uuid.return_value = MagicMock(hex="uuid-123")

    handler = CreateTokenAdminHandler(token_table)
    request = CreateTokenAdminRequest(
        tokenExpiration=future_timestamp, groups=["admin"], name="Admin Token", isSystemToken=False
    )

    result = handler("testuser", request, "admin", True)

    assert result.token == "plain-token-123"
    assert result.username == "testuser"
    assert result.groups == ["admin"]
    assert result.isSystemToken is False

    # Verify token was stored
    response = token_table.get_item(Key={"token": "hashed-token-123"})
    assert "Item" in response


def test_create_token_admin_handler_not_admin(token_table, future_timestamp):
    """Test CreateTokenAdminHandler rejects non-admin users."""
    handler = CreateTokenAdminHandler(token_table)
    request = CreateTokenAdminRequest(tokenExpiration=future_timestamp, name="Token")

    with pytest.raises(UnauthorizedError) as excinfo:
        handler("testuser", request, "non-admin", False)
    assert "Only admins" in str(excinfo.value)


@patch("api_tokens.handler.generate_token")
@patch("api_tokens.handler.hash_token")
def test_create_token_admin_handler_duplicate_user_token(mock_hash, mock_generate, token_table, future_timestamp):
    """Test CreateTokenAdminHandler rejects duplicate user tokens."""
    # Create existing token
    token_table.put_item(
        Item={
            "token": "existing-hash",
            "tokenUUID": "existing-uuid",
            "username": "testuser",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "admin",
            "name": "Existing",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = CreateTokenAdminHandler(token_table)
    request = CreateTokenAdminRequest(tokenExpiration=future_timestamp, name="New Token", isSystemToken=False)

    with pytest.raises(TokenAlreadyExistsError):
        handler("testuser", request, "admin", True)


@patch("api_tokens.handler.generate_token")
@patch("api_tokens.handler.hash_token")
@patch("api_tokens.handler.uuid4")
def test_create_token_admin_handler_system_token_allows_duplicate(
    mock_uuid, mock_hash, mock_generate, token_table, future_timestamp
):
    """Test CreateTokenAdminHandler allows duplicate username for system tokens."""
    # Create existing token
    token_table.put_item(
        Item={
            "token": "existing-hash",
            "tokenUUID": "existing-uuid",
            "username": "testuser",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "admin",
            "name": "Existing",
            "groups": [],
            "isSystemToken": False,
        }
    )

    mock_generate.return_value = "plain-token-123"
    mock_hash.return_value = "hashed-token-123"
    mock_uuid.return_value = MagicMock(hex="uuid-123")

    handler = CreateTokenAdminHandler(token_table)
    request = CreateTokenAdminRequest(tokenExpiration=future_timestamp, name="System Token", isSystemToken=True)

    # Should not raise TokenAlreadyExistsError for system tokens
    result = handler("testuser", request, "admin", True)
    assert result.isSystemToken is True


# =====================
# Test handler.py - CreateTokenUserHandler
# =====================


@patch("api_tokens.handler.generate_token")
@patch("api_tokens.handler.hash_token")
@patch("api_tokens.handler.uuid4")
def test_create_token_user_handler_success(mock_uuid, mock_hash, mock_generate, token_table, future_timestamp):
    """Test CreateTokenUserHandler successfully creates token."""
    mock_generate.return_value = "plain-token-456"
    mock_hash.return_value = "hashed-token-456"
    mock_uuid.return_value = MagicMock(hex="uuid-456")

    handler = CreateTokenUserHandler(token_table)
    request = CreateTokenUserRequest(name="My Token", tokenExpiration=future_timestamp)

    result = handler(request, "testuser", ["user-group"], is_admin=False, is_api_user=True)

    assert result.token == "plain-token-456"
    assert result.username == "testuser"
    assert result.groups == ["user-group"]
    assert result.isSystemToken is False


def test_create_token_user_handler_not_api_user(token_table, future_timestamp):
    """Test CreateTokenUserHandler rejects non-API users."""
    handler = CreateTokenUserHandler(token_table)
    request = CreateTokenUserRequest(name="My Token", tokenExpiration=future_timestamp)

    with pytest.raises(ForbiddenError) as excinfo:
        handler(request, "testuser", ["other-group"], is_admin=False, is_api_user=False)
    assert "API group" in str(excinfo.value)


@patch("api_tokens.handler.generate_token")
@patch("api_tokens.handler.hash_token")
@patch("api_tokens.handler.uuid4")
def test_create_token_user_handler_admin_can_create(mock_uuid, mock_hash, mock_generate, token_table, future_timestamp):
    """Test CreateTokenUserHandler allows admins even without API group."""
    mock_generate.return_value = "plain-token-789"
    mock_hash.return_value = "hashed-token-789"
    mock_uuid.return_value = MagicMock(hex="uuid-789")

    handler = CreateTokenUserHandler(token_table)
    request = CreateTokenUserRequest(name="Admin Token", tokenExpiration=future_timestamp)

    result = handler(request, "admin", ["admin-group"], is_admin=True, is_api_user=False)
    assert result.username == "admin"


def test_create_token_user_handler_duplicate(token_table, future_timestamp):
    """Test CreateTokenUserHandler rejects duplicate tokens."""
    # Create existing token
    token_table.put_item(
        Item={
            "token": "existing-hash",
            "tokenUUID": "existing-uuid",
            "username": "testuser",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "testuser",
            "name": "Existing",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = CreateTokenUserHandler(token_table)
    request = CreateTokenUserRequest(name="New Token", tokenExpiration=future_timestamp)

    with pytest.raises(TokenAlreadyExistsError) as excinfo:
        handler(request, "testuser", ["user-group"], is_admin=False, is_api_user=True)
    assert "already exists" in str(excinfo.value)


# =====================
# Test handler.py - ListTokensHandler
# =====================


def test_list_tokens_handler_admin_sees_all(token_table, future_timestamp):
    """Test ListTokensHandler returns all tokens for admins."""
    # Create multiple tokens
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "user1",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "admin",
            "name": "Token 1",
            "groups": [],
            "isSystemToken": False,
        }
    )
    token_table.put_item(
        Item={
            "token": "hash2",
            "tokenUUID": "uuid2",
            "username": "user2",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "admin",
            "name": "Token 2",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = ListTokensHandler(token_table)
    result = handler("admin", is_admin=True)

    assert len(result.tokens) == 2
    usernames = [t.username for t in result.tokens]
    assert "user1" in usernames
    assert "user2" in usernames


def test_list_tokens_handler_user_sees_own(token_table, future_timestamp):
    """Test ListTokensHandler returns only user's own token."""
    # Create tokens for multiple users
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "user1",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "user1",
            "name": "Token 1",
            "groups": [],
            "isSystemToken": False,
        }
    )
    token_table.put_item(
        Item={
            "token": "hash2",
            "tokenUUID": "uuid2",
            "username": "user2",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "user2",
            "name": "Token 2",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = ListTokensHandler(token_table)
    result = handler("user1", is_admin=False)

    assert len(result.tokens) == 1
    assert result.tokens[0].username == "user1"


def test_list_tokens_handler_expired_flag(token_table, past_timestamp):
    """Test ListTokensHandler correctly flags expired tokens."""
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "user1",
            "tokenExpiration": past_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "user1",
            "name": "Expired Token",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = ListTokensHandler(token_table)
    result = handler("user1", is_admin=False)

    assert len(result.tokens) == 1
    assert result.tokens[0].isExpired is True


def test_list_tokens_handler_legacy_token(token_table, future_timestamp):
    """Test ListTokensHandler correctly identifies legacy tokens."""
    token_table.put_item(
        Item={
            "token": "legacy-hash",
            "username": "user1",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "user1",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = ListTokensHandler(token_table)
    result = handler("user1", is_admin=False)

    assert len(result.tokens) == 1
    assert result.tokens[0].isLegacy is True
    assert result.tokens[0].tokenUUID == "—"
    assert result.tokens[0].name == "legacy-hash"  # Uses token as name for legacy


# =====================
# Test handler.py - GetTokenHandler
# =====================


def test_get_token_handler_success(token_table, future_timestamp):
    """Test GetTokenHandler retrieves token successfully."""
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "user1",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "admin",
            "name": "Test Token",
            "groups": ["admin"],
            "isSystemToken": False,
        }
    )

    handler = GetTokenHandler(token_table)
    result = handler("uuid1", "user1", is_admin=False)

    assert result.tokenUUID == "uuid1"
    assert result.username == "user1"
    assert result.name == "Test Token"


def test_get_token_handler_not_found(token_table):
    """Test GetTokenHandler raises error for non-existent token."""
    handler = GetTokenHandler(token_table)

    with pytest.raises(TokenNotFoundError):
        handler("non-existent-uuid", "user1", is_admin=False)


def test_get_token_handler_user_cannot_access_other_token(token_table, future_timestamp):
    """Test GetTokenHandler prevents users from accessing other users' tokens."""
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "user1",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "admin",
            "name": "User1 Token",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = GetTokenHandler(token_table)

    with pytest.raises(TokenNotFoundError):
        handler("uuid1", "user2", is_admin=False)


def test_get_token_handler_admin_can_access_any_token(token_table, future_timestamp):
    """Test GetTokenHandler allows admins to access any token."""
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "user1",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "admin",
            "name": "User1 Token",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = GetTokenHandler(token_table)
    result = handler("uuid1", "admin", is_admin=True)

    assert result.username == "user1"


def test_get_token_handler_legacy_token(token_table, future_timestamp):
    """Test GetTokenHandler handles legacy tokens."""
    token_table.put_item(
        Item={
            "token": "legacy-hash",
            "username": "user1",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "user1",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = GetTokenHandler(token_table)
    result = handler("legacy-hash", "user1", is_admin=False)

    assert result.isLegacy is True
    assert result.name == "legacy-hash"


# =====================
# Test handler.py - DeleteTokenHandler
# =====================


def test_delete_token_handler_success(token_table, future_timestamp):
    """Test DeleteTokenHandler deletes token successfully."""
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "user1",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "user1",
            "name": "Test Token",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = DeleteTokenHandler(token_table)
    result = handler("uuid1", "user1", is_admin=False)

    assert result.message == "Token deleted successfully"
    assert result.tokenUUID == "uuid1"

    # Verify token was deleted
    response = token_table.get_item(Key={"token": "hash1"})
    assert "Item" not in response


def test_delete_token_handler_not_found(token_table):
    """Test DeleteTokenHandler raises error for non-existent token."""
    handler = DeleteTokenHandler(token_table)

    with pytest.raises(TokenNotFoundError):
        handler("non-existent-uuid", "user1", is_admin=False)


def test_delete_token_handler_user_cannot_delete_other_token(token_table, future_timestamp):
    """Test DeleteTokenHandler prevents users from deleting other users' tokens."""
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "user1",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "user1",
            "name": "User1 Token",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = DeleteTokenHandler(token_table)

    with pytest.raises(TokenNotFoundError):
        handler("uuid1", "user2", is_admin=False)


def test_delete_token_handler_admin_can_delete_any_token(token_table, future_timestamp):
    """Test DeleteTokenHandler allows admins to delete any token."""
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "user1",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "user1",
            "name": "User1 Token",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = DeleteTokenHandler(token_table)
    result = handler("uuid1", "admin", is_admin=True)

    assert result.tokenUUID == "uuid1"


def test_delete_token_handler_legacy_token_admin_only(token_table, future_timestamp):
    """Test DeleteTokenHandler only allows admins to delete legacy tokens."""
    token_table.put_item(
        Item={
            "token": "legacy-hash",
            "username": "user1",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "user1",
            "groups": [],
            "isSystemToken": False,
        }
    )

    handler = DeleteTokenHandler(token_table)

    # User should not be able to delete legacy token
    with pytest.raises(ForbiddenError) as excinfo:
        handler("legacy-hash", "user1", is_admin=False)
    assert "administrators" in str(excinfo.value)

    # Admin should be able to delete legacy token
    result = handler("legacy-hash", "admin", is_admin=True)
    assert "deleted successfully" in result.message
