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
# Set TOKEN_TABLE_NAME before importing - this will be used by lambda_functions.py
if "TOKEN_TABLE_NAME" not in os.environ:
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


# =====================
# Test lambda_functions.py - FastAPI endpoints
# =====================


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request object."""
    from unittest.mock import MagicMock

    request = MagicMock()
    request.scope = {
        "aws.event": {
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "username": "test-user",
                        "cognito:groups": "user-group",
                    }
                }
            }
        }
    }
    return request


@pytest.fixture
def mock_admin_request():
    """Create a mock FastAPI Request object for admin user."""
    from unittest.mock import MagicMock

    request = MagicMock()
    request.scope = {
        "aws.event": {
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "username": "admin-user",
                        "cognito:groups": "admin-group",
                    }
                }
            }
        }
    }
    return request


@pytest.fixture
def mock_api_user_request():
    """Create a mock FastAPI Request object for API user."""
    from unittest.mock import MagicMock

    request = MagicMock()
    request.scope = {
        "aws.event": {
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "username": "api-user",
                        "cognito:groups": "api-group",
                    }
                }
            }
        }
    }
    return request


@pytest.mark.asyncio
async def test_create_token_for_user_endpoint_success(token_table, mock_admin_request, future_timestamp):
    """Test create_token_for_user endpoint with admin user."""
    from api_tokens.lambda_functions import create_token_for_user

    with patch("api_tokens.lambda_functions.token_table", token_table):
        with patch("api_tokens.lambda_functions.get_user_context") as mock_get_user:
            with patch("api_tokens.lambda_functions.CreateTokenAdminHandler") as mock_handler_class:
                mock_get_user.return_value = ("admin-user", True, ["admin-group"])

                mock_handler = MagicMock()
                mock_handler.return_value = CreateTokenResponse(
                    token="test-token",
                    tokenUUID="test-uuid",
                    tokenExpiration=future_timestamp,
                    createdDate=int(datetime.now().timestamp()),
                    username="target-user",
                    name="Test Token",
                    groups=["admin"],
                    isSystemToken=False,
                )
                mock_handler_class.return_value = mock_handler

                request_data = CreateTokenAdminRequest(
                    tokenExpiration=future_timestamp, groups=["admin"], name="Test Token", isSystemToken=False
                )

                result = await create_token_for_user("target-user", mock_admin_request, request_data)

                assert result.token == "test-token"
                assert result.username == "target-user"
                mock_handler.assert_called_once_with("target-user", request_data, "admin-user", True)


@pytest.mark.asyncio
async def test_create_token_for_user_endpoint_unauthorized(token_table, future_timestamp):
    """Test create_token_for_user endpoint without AWS event context."""
    from api_tokens.lambda_functions import create_token_for_user
    from fastapi import HTTPException

    mock_request = MagicMock()
    mock_request.scope = {}  # No aws.event

    request_data = CreateTokenAdminRequest(tokenExpiration=future_timestamp, name="Test Token")

    with pytest.raises(HTTPException) as excinfo:
        await create_token_for_user("target-user", mock_request, request_data)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_create_own_token_endpoint_success(token_table, mock_api_user_request, future_timestamp):
    """Test create_own_token endpoint with API user."""
    from api_tokens.lambda_functions import create_own_token

    with patch("api_tokens.lambda_functions.token_table", token_table):
        with patch("api_tokens.lambda_functions.get_user_context") as mock_get_user:
            with patch("api_tokens.lambda_functions.is_api_user") as mock_is_api:
                with patch("api_tokens.lambda_functions.CreateTokenUserHandler") as mock_handler_class:
                    mock_get_user.return_value = ("api-user", False, ["api-group"])
                    mock_is_api.return_value = True

                    mock_handler = MagicMock()
                    mock_handler.return_value = CreateTokenResponse(
                        token="user-token",
                        tokenUUID="user-uuid",
                        tokenExpiration=future_timestamp,
                        createdDate=int(datetime.now().timestamp()),
                        username="api-user",
                        name="My Token",
                        groups=["api-group"],
                        isSystemToken=False,
                    )
                    mock_handler_class.return_value = mock_handler

                    request_data = CreateTokenUserRequest(name="My Token", tokenExpiration=future_timestamp)

                    result = await create_own_token(mock_api_user_request, request_data)

                    assert result.token == "user-token"
                    assert result.username == "api-user"
                    mock_handler.assert_called_once_with(request_data, "api-user", ["api-group"], False, True)


@pytest.mark.asyncio
async def test_create_own_token_endpoint_unauthorized(token_table, future_timestamp):
    """Test create_own_token endpoint without AWS event context."""
    from api_tokens.lambda_functions import create_own_token
    from fastapi import HTTPException

    mock_request = MagicMock()
    mock_request.scope = {}  # No aws.event

    request_data = CreateTokenUserRequest(name="My Token", tokenExpiration=future_timestamp)

    with pytest.raises(HTTPException) as excinfo:
        await create_own_token(mock_request, request_data)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_list_tokens_endpoint_success(token_table, mock_request, future_timestamp):
    """Test list_tokens endpoint."""
    from api_tokens.lambda_functions import list_tokens

    # Add test token
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "test-user",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "test-user",
            "name": "Test Token",
            "groups": [],
            "isSystemToken": False,
        }
    )

    with patch("api_tokens.lambda_functions.token_table", token_table):
        with patch("api_tokens.lambda_functions.get_user_context") as mock_get_user:
            mock_get_user.return_value = ("test-user", False, ["user-group"])

            result = await list_tokens(mock_request)

            assert len(result.tokens) == 1
            assert result.tokens[0].username == "test-user"


@pytest.mark.asyncio
async def test_list_tokens_endpoint_unauthorized(token_table):
    """Test list_tokens endpoint without AWS event context."""
    from api_tokens.lambda_functions import list_tokens
    from fastapi import HTTPException

    mock_request = MagicMock()
    mock_request.scope = {}  # No aws.event

    with pytest.raises(HTTPException) as excinfo:
        await list_tokens(mock_request)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_get_token_endpoint_success(token_table, mock_request, future_timestamp):
    """Test get_token endpoint."""
    from api_tokens.lambda_functions import get_token

    # Add test token
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "test-user",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "test-user",
            "name": "Test Token",
            "groups": [],
            "isSystemToken": False,
        }
    )

    with patch("api_tokens.lambda_functions.token_table", token_table):
        with patch("api_tokens.lambda_functions.get_user_context") as mock_get_user:
            mock_get_user.return_value = ("test-user", False, ["user-group"])

            result = await get_token("uuid1", mock_request)

            assert result.tokenUUID == "uuid1"
            assert result.username == "test-user"


@pytest.mark.asyncio
async def test_get_token_endpoint_unauthorized(token_table):
    """Test get_token endpoint without AWS event context."""
    from api_tokens.lambda_functions import get_token
    from fastapi import HTTPException

    mock_request = MagicMock()
    mock_request.scope = {}  # No aws.event

    with pytest.raises(HTTPException) as excinfo:
        await get_token("uuid1", mock_request)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_delete_token_endpoint_success(token_table, mock_request, future_timestamp):
    """Test delete_token endpoint."""
    from api_tokens.lambda_functions import delete_token

    # Add test token
    token_table.put_item(
        Item={
            "token": "hash1",
            "tokenUUID": "uuid1",
            "username": "test-user",
            "tokenExpiration": future_timestamp,
            "createdDate": int(datetime.now().timestamp()),
            "createdBy": "test-user",
            "name": "Test Token",
            "groups": [],
            "isSystemToken": False,
        }
    )

    with patch("api_tokens.lambda_functions.token_table", token_table):
        with patch("api_tokens.lambda_functions.get_user_context") as mock_get_user:
            mock_get_user.return_value = ("test-user", False, ["user-group"])

            result = await delete_token("uuid1", mock_request)

            assert result.message == "Token deleted successfully"
            assert result.tokenUUID == "uuid1"


@pytest.mark.asyncio
async def test_delete_token_endpoint_unauthorized(token_table):
    """Test delete_token endpoint without AWS event context."""
    from api_tokens.lambda_functions import delete_token
    from fastapi import HTTPException

    mock_request = MagicMock()
    mock_request.scope = {}  # No aws.event

    with pytest.raises(HTTPException) as excinfo:
        await delete_token("uuid1", mock_request)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_exception_handlers():
    """Test FastAPI exception handlers."""
    from api_tokens.lambda_functions import (
        forbidden_handler,
        token_not_found_handler,
        unauthorized_handler,
        user_error_handler,
    )

    mock_request = MagicMock()

    # Test TokenNotFoundError handler
    exc = TokenNotFoundError("Token not found")
    response = await token_not_found_handler(mock_request, exc)
    assert response.status_code == 404
    assert "Token not found" in response.body.decode()

    # Test UnauthorizedError handler
    exc = UnauthorizedError("Not authorized")
    response = await unauthorized_handler(mock_request, exc)
    assert response.status_code == 401
    assert "Not authorized" in response.body.decode()

    # Test ForbiddenError handler
    exc = ForbiddenError("Forbidden")
    response = await forbidden_handler(mock_request, exc)
    assert response.status_code == 403
    assert "Forbidden" in response.body.decode()

    # Test TokenAlreadyExistsError handler
    exc = TokenAlreadyExistsError("Token exists")
    response = await user_error_handler(mock_request, exc)
    assert response.status_code == 400
    assert "Token exists" in response.body.decode()

    # Test ValueError handler
    exc = ValueError("Invalid value")
    response = await user_error_handler(mock_request, exc)
    assert response.status_code == 400
    assert "Invalid value" in response.body.decode()


@pytest.mark.asyncio
async def test_validation_exception_handler():
    """Test RequestValidationError handler."""
    import json

    from api_tokens.lambda_functions import validation_exception_handler
    from fastapi.exceptions import RequestValidationError

    mock_request = MagicMock()

    # Create a validation error
    exc = RequestValidationError(
        [
            {
                "loc": ("body", "name"),
                "msg": "field required",
                "type": "value_error.missing",
            }
        ]
    )

    response = await validation_exception_handler(mock_request, exc)
    assert response.status_code == 422
    body = json.loads(response.body)
    assert "detail" in body
    assert body["type"] == "RequestValidationError"


def test_mangum_handler_initialization():
    """Test that Mangum handlers are properly initialized."""
    from api_tokens.lambda_functions import docs, handler

    assert handler is not None
    assert docs is not None


def test_fastapi_app_configuration():
    """Test FastAPI app configuration."""
    from api_tokens.lambda_functions import app

    # Test app configuration
    assert app.docs_url == "/docs"
    assert app.openapi_url == "/openapi.json"
    # Check middleware is configured
    assert len(app.user_middleware) > 0


def test_dynamodb_initialization():
    """Test DynamoDB resource and table initialization."""
    from api_tokens.lambda_functions import dynamodb, token_table

    assert dynamodb is not None
    assert token_table is not None
    # Table name can vary based on environment (test-token-table or token-table)
    assert "token" in token_table.name.lower()
    assert "table" in token_table.name.lower()


# =====================
# Test handler.py - Exception handling paths
# =====================


def test_get_token_handler_scan_exception(token_table, future_timestamp):
    """Test GetTokenHandler handles scan exceptions gracefully."""
    # Add a legacy token (no tokenUUID)
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

    # Mock scan to raise exception, should fall back to get_item
    with patch.object(token_table, "scan", side_effect=Exception("Scan failed")):
        result = handler("legacy-hash", "user1", is_admin=False)
        assert result.isLegacy is True
        assert result.name == "legacy-hash"


def test_get_token_handler_both_lookups_fail(token_table):
    """Test GetTokenHandler when both scan and get_item fail."""
    handler = GetTokenHandler(token_table)

    # Mock both scan and get_item to raise exceptions
    with patch.object(token_table, "scan", side_effect=Exception("Scan failed")):
        with patch.object(token_table, "get_item", side_effect=Exception("Get failed")):
            with pytest.raises(TokenNotFoundError):
                handler("non-existent", "user1", is_admin=False)


def test_delete_token_handler_scan_exception(token_table, future_timestamp):
    """Test DeleteTokenHandler handles scan exceptions gracefully."""
    # Add a legacy token (no tokenUUID)
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

    # Mock scan to raise exception, should fall back to get_item
    with patch.object(token_table, "scan", side_effect=Exception("Scan failed")):
        # Admin should be able to delete legacy token even when scan fails
        result = handler("legacy-hash", "admin", is_admin=True)
        assert "deleted successfully" in result.message


def test_delete_token_handler_both_lookups_fail(token_table):
    """Test DeleteTokenHandler when both scan and get_item fail."""
    handler = DeleteTokenHandler(token_table)

    # Mock both scan and get_item to raise exceptions
    with patch.object(token_table, "scan", side_effect=Exception("Scan failed")):
        with patch.object(token_table, "get_item", side_effect=Exception("Get failed")):
            with pytest.raises(TokenNotFoundError):
                handler("non-existent", "user1", is_admin=False)
