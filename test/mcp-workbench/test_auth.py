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

"""Unit tests for MCP Workbench authentication."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest

# Set up environment before imports
os.environ["AWS_REGION"] = "us-east-1"
os.environ["TOKEN_TABLE_NAME"] = "test-tokens"
os.environ["MANAGEMENT_KEY_NAME"] = "test-management-key"
os.environ["AUTHORITY"] = "https://test-authority.com"
os.environ["CLIENT_ID"] = "test-client-id"
os.environ["USE_AUTH"] = "true"

# Import the auth module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib/serve/mcp-workbench/src"))

from mcpworkbench.server.auth import (
    ApiTokenAuthorizer,
    ManagementTokenAuthorizer,
    get_authorization_token,
    get_jwks_client,
    get_oidc_metadata,
    id_token_is_valid,
    is_idp_used,
    is_user_in_group,
)


def test_is_idp_used_true():
    """Test is_idp_used returns True when USE_AUTH is true."""
    with patch.dict(os.environ, {"USE_AUTH": "true"}):
        assert is_idp_used() is True


def test_is_idp_used_false():
    """Test is_idp_used returns False when USE_AUTH is false."""
    with patch.dict(os.environ, {"USE_AUTH": "false"}):
        assert is_idp_used() is False


def test_get_authorization_token_with_bearer():
    """Test extracting Bearer token from Authorization header."""
    headers = {"Authorization": "Bearer test-token-123"}
    token = get_authorization_token(headers)
    assert token == "test-token-123"


def test_get_authorization_token_without_bearer():
    """Test extracting token without Bearer prefix."""
    headers = {"Authorization": "test-token-123"}
    token = get_authorization_token(headers)
    assert token == "test-token-123"


def test_get_authorization_token_lowercase_header():
    """Test extracting token from lowercase header."""
    headers = {"authorization": "Bearer test-token-123"}
    token = get_authorization_token(headers)
    assert token == "test-token-123"


def test_get_authorization_token_custom_header():
    """Test extracting token from custom header name."""
    headers = {"Api-Key": "Bearer test-token-123"}
    token = get_authorization_token(headers, "Api-Key")
    assert token == "test-token-123"


def test_get_authorization_token_missing():
    """Test extracting token when header is missing."""
    headers = {}
    token = get_authorization_token(headers)
    assert token == ""


@patch("mcpworkbench.server.auth.requests.get")
def test_get_oidc_metadata(mock_get):
    """Test getting OIDC metadata."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "jwks_uri": "https://test-authority.com/.well-known/jwks.json",
        "issuer": "https://test-authority.com",
    }
    mock_get.return_value = mock_response
    
    metadata = get_oidc_metadata()
    
    assert metadata["jwks_uri"] == "https://test-authority.com/.well-known/jwks.json"
    mock_get.assert_called_once()


@patch("mcpworkbench.server.auth.get_oidc_metadata")
@patch("mcpworkbench.server.auth.jwt.PyJWKClient")
def test_get_jwks_client(mock_jwk_client, mock_get_metadata):
    """Test getting JWKS client."""
    mock_get_metadata.return_value = {
        "jwks_uri": "https://test-authority.com/.well-known/jwks.json"
    }
    
    client = get_jwks_client()
    
    mock_jwk_client.assert_called_once()
    assert client is not None


def test_is_user_in_group_simple():
    """Test checking if user is in group with simple property."""
    jwt_data = {"groups": ["admin", "users"]}
    
    assert is_user_in_group(jwt_data, "admin", "groups") is True
    assert is_user_in_group(jwt_data, "superadmin", "groups") is False


def test_is_user_in_group_nested():
    """Test checking if user is in group with nested property."""
    jwt_data = {
        "cognito": {
            "groups": ["admin", "users"]
        }
    }
    
    assert is_user_in_group(jwt_data, "admin", "cognito.groups") is True
    assert is_user_in_group(jwt_data, "superadmin", "cognito.groups") is False


def test_is_user_in_group_missing_property():
    """Test checking if user is in group when property is missing."""
    jwt_data = {"other": "value"}
    
    assert is_user_in_group(jwt_data, "admin", "groups") is False


@patch("mcpworkbench.server.auth.jwt.decode")
def test_id_token_is_valid_success(mock_decode):
    """Test validating a valid ID token."""
    mock_jwks_client = Mock()
    mock_signing_key = Mock()
    mock_signing_key.key = "test-key"
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
    
    mock_decode.return_value = {
        "sub": "user123",
        "email": "user@example.com",
    }
    
    result = id_token_is_valid(
        "test-token",
        "test-client-id",
        "https://test-authority.com",
        mock_jwks_client,
    )
    
    assert result is not None
    assert result["sub"] == "user123"


@patch("mcpworkbench.server.auth.jwt.decode")
def test_id_token_is_valid_expired(mock_decode):
    """Test validating an expired ID token."""
    mock_jwks_client = Mock()
    mock_signing_key = Mock()
    mock_signing_key.key = "test-key"
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
    
    mock_decode.side_effect = jwt.exceptions.ExpiredSignatureError()
    
    result = id_token_is_valid(
        "test-token",
        "test-client-id",
        "https://test-authority.com",
        mock_jwks_client,
    )
    
    assert result is None


@patch("mcpworkbench.server.auth.jwt.decode")
def test_id_token_is_valid_decode_error(mock_decode):
    """Test validating an invalid ID token."""
    mock_jwks_client = Mock()
    mock_signing_key = Mock()
    mock_signing_key.key = "test-key"
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
    
    mock_decode.side_effect = jwt.exceptions.DecodeError()
    
    result = id_token_is_valid(
        "test-token",
        "test-client-id",
        "https://test-authority.com",
        mock_jwks_client,
    )
    
    assert result is None


class TestApiTokenAuthorizer:
    """Tests for ApiTokenAuthorizer class."""
    
    @patch("mcpworkbench.server.auth.boto3.resource")
    def test_init(self, mock_boto_resource):
        """Test ApiTokenAuthorizer initialization."""
        mock_table = Mock()
        mock_ddb = Mock()
        mock_ddb.Table.return_value = mock_table
        mock_boto_resource.return_value = mock_ddb
        
        authorizer = ApiTokenAuthorizer()
        
        assert authorizer._token_table == mock_table
        mock_boto_resource.assert_called_once_with("dynamodb", region_name="us-east-1")
    
    @patch("mcpworkbench.server.auth.boto3.resource")
    def test_is_valid_api_token_valid(self, mock_boto_resource):
        """Test validating a valid API token."""
        mock_table = Mock()
        mock_ddb = Mock()
        mock_ddb.Table.return_value = mock_table
        mock_boto_resource.return_value = mock_ddb
        
        # Token expires in the future
        future_time = int((datetime.now() + timedelta(days=1)).timestamp())
        mock_table.get_item.return_value = {
            "Item": {
                "token": "test-token",
                "tokenExpiration": future_time,
            }
        }
        
        authorizer = ApiTokenAuthorizer()
        headers = {"Authorization": "Bearer test-token"}
        
        assert authorizer.is_valid_api_token(headers) is True
    
    @patch("mcpworkbench.server.auth.boto3.resource")
    def test_is_valid_api_token_expired(self, mock_boto_resource):
        """Test validating an expired API token."""
        mock_table = Mock()
        mock_ddb = Mock()
        mock_ddb.Table.return_value = mock_table
        mock_boto_resource.return_value = mock_ddb
        
        # Token expired in the past
        past_time = int((datetime.now() - timedelta(days=1)).timestamp())
        mock_table.get_item.return_value = {
            "Item": {
                "token": "test-token",
                "tokenExpiration": past_time,
            }
        }
        
        authorizer = ApiTokenAuthorizer()
        headers = {"Authorization": "Bearer test-token"}
        
        assert authorizer.is_valid_api_token(headers) is False
    
    @patch("mcpworkbench.server.auth.boto3.resource")
    def test_is_valid_api_token_not_found(self, mock_boto_resource):
        """Test validating a non-existent API token."""
        mock_table = Mock()
        mock_ddb = Mock()
        mock_ddb.Table.return_value = mock_table
        mock_boto_resource.return_value = mock_ddb
        
        mock_table.get_item.return_value = {}
        
        authorizer = ApiTokenAuthorizer()
        headers = {"Authorization": "Bearer test-token"}
        
        assert authorizer.is_valid_api_token(headers) is False


class TestManagementTokenAuthorizer:
    """Tests for ManagementTokenAuthorizer class."""
    
    @patch("mcpworkbench.server.auth.boto3.client")
    def test_init(self, mock_boto_client):
        """Test ManagementTokenAuthorizer initialization."""
        mock_sm = Mock()
        mock_boto_client.return_value = mock_sm
        
        authorizer = ManagementTokenAuthorizer()
        
        assert authorizer._secrets_manager == mock_sm
        mock_boto_client.assert_called_once_with("secretsmanager", region_name="us-east-1")
    
    @patch("mcpworkbench.server.auth.boto3.client")
    @patch("mcpworkbench.server.auth.time")
    def test_is_valid_api_token_valid(self, mock_time, mock_boto_client):
        """Test validating a valid management token."""
        mock_sm = Mock()
        mock_boto_client.return_value = mock_sm
        
        mock_sm.get_secret_value.return_value = {"SecretString": "management-token-123"}
        # Mock time() function call to return a value that triggers refresh
        mock_time.return_value = 10000
        
        authorizer = ManagementTokenAuthorizer()
        authorizer._last_run = 0  # Force refresh
        
        headers = {"Authorization": "Bearer management-token-123"}
        
        assert authorizer.is_valid_api_token(headers) is True
    
    @patch("mcpworkbench.server.auth.boto3.client")
    @patch("mcpworkbench.server.auth.time")
    def test_is_valid_api_token_invalid(self, mock_time, mock_boto_client):
        """Test validating an invalid management token."""
        mock_sm = Mock()
        mock_boto_client.return_value = mock_sm
        
        mock_sm.get_secret_value.return_value = {"SecretString": "management-token-123"}
        mock_time.return_value = 1000
        
        authorizer = ManagementTokenAuthorizer()
        authorizer._last_run = 0  # Force refresh
        
        headers = {"Authorization": "Bearer wrong-token"}
        
        assert authorizer.is_valid_api_token(headers) is False
    
    @patch("mcpworkbench.server.auth.boto3.client")
    @patch("mcpworkbench.server.auth.time")
    def test_refresh_tokens_with_previous(self, mock_time, mock_boto_client):
        """Test refreshing tokens with previous version."""
        mock_sm = Mock()
        mock_boto_client.return_value = mock_sm
        
        def get_secret_side_effect(*args, **kwargs):
            if kwargs.get("VersionStage") == "AWSCURRENT":
                return {"SecretString": "current-token"}
            elif kwargs.get("VersionStage") == "AWSPREVIOUS":
                return {"SecretString": "previous-token"}
        
        mock_sm.get_secret_value.side_effect = get_secret_side_effect
        mock_time.return_value = 5000
        
        authorizer = ManagementTokenAuthorizer()
        authorizer._last_run = 0  # Force refresh
        
        headers = {"Authorization": "Bearer previous-token"}
        
        assert authorizer.is_valid_api_token(headers) is True
    
    @patch("mcpworkbench.server.auth.boto3.client")
    @patch("mcpworkbench.server.auth.time")
    def test_refresh_tokens_no_previous(self, mock_time, mock_boto_client):
        """Test refreshing tokens without previous version."""
        mock_sm = Mock()
        mock_boto_client.return_value = mock_sm
        
        def get_secret_side_effect(*args, **kwargs):
            if kwargs.get("VersionStage") == "AWSCURRENT":
                return {"SecretString": "current-token"}
            elif kwargs.get("VersionStage") == "AWSPREVIOUS":
                raise Exception("No previous version")
        
        mock_sm.get_secret_value.side_effect = get_secret_side_effect
        mock_time.return_value = 5000
        
        authorizer = ManagementTokenAuthorizer()
        authorizer._last_run = 0  # Force refresh
        
        headers = {"Authorization": "Bearer current-token"}
        
        assert authorizer.is_valid_api_token(headers) is True
