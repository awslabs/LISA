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

"""Unit tests for LISA SDK authentication."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lisa-sdk"))

from lisapy.authentication import create_api_token, get_cognito_token, get_management_key, setup_authentication


@patch("lisapy.authentication.boto3.client")
@patch("lisapy.authentication.getpass.getpass")
def test_get_cognito_token_success(mock_getpass, mock_boto_client):
    """Test getting Cognito token successfully."""
    mock_getpass.return_value = "test-password"

    mock_cognito = MagicMock()
    mock_cognito.initiate_auth.return_value = {
        "AuthenticationResult": {
            "AccessToken": "access-token",
            "IdToken": "id-token",
            "RefreshToken": "refresh-token",
        }
    }
    mock_boto_client.return_value = mock_cognito

    result = get_cognito_token("test-client-id", "test-user", "us-east-1")

    assert "AuthenticationResult" in result
    assert result["AuthenticationResult"]["AccessToken"] == "access-token"

    mock_cognito.initiate_auth.assert_called_once_with(
        AuthFlow="USER_PASSWORD_AUTH",
        ClientId="test-client-id",
        AuthParameters={
            "USERNAME": "test-user",
            "PASSWORD": "test-password",
        },
    )


@patch("lisapy.authentication.boto3.client")
@patch("lisapy.authentication.getpass.getpass")
def test_get_cognito_token_default_region(mock_getpass, mock_boto_client):
    """Test getting Cognito token with default region."""
    mock_getpass.return_value = "test-password"

    mock_cognito = MagicMock()
    mock_cognito.initiate_auth.return_value = {"AuthenticationResult": {}}
    mock_boto_client.return_value = mock_cognito

    get_cognito_token("test-client-id", "test-user")

    mock_boto_client.assert_called_once_with("cognito-idp", region_name="us-east-1")


@patch("lisapy.authentication.boto3.client")
@patch("lisapy.authentication.getpass.getpass")
def test_get_cognito_token_custom_region(mock_getpass, mock_boto_client):
    """Test getting Cognito token with custom region."""
    mock_getpass.return_value = "test-password"

    mock_cognito = MagicMock()
    mock_cognito.initiate_auth.return_value = {"AuthenticationResult": {}}
    mock_boto_client.return_value = mock_cognito

    get_cognito_token("test-client-id", "test-user", "eu-west-1")

    mock_boto_client.assert_called_once_with("cognito-idp", region_name="eu-west-1")


@patch("lisapy.authentication.boto3.client")
@patch("lisapy.authentication.getpass.getpass")
def test_get_cognito_token_auth_failure(mock_getpass, mock_boto_client):
    """Test getting Cognito token with authentication failure."""
    mock_getpass.return_value = "wrong-password"

    mock_cognito = MagicMock()
    mock_cognito.initiate_auth.side_effect = Exception("NotAuthorizedException")
    mock_boto_client.return_value = mock_cognito

    with pytest.raises(Exception) as exc_info:
        get_cognito_token("test-client-id", "test-user")

    assert "NotAuthorizedException" in str(exc_info.value)


# Management-key authentication tests


@patch("lisapy.authentication.boto3.client")
def test_get_management_key_success(mock_boto_client):
    """Test retrieving management key successfully."""
    mock_secrets = MagicMock()
    mock_secrets.get_secret_value.return_value = {"SecretString": "test-api-key"}
    mock_boto_client.return_value = mock_secrets

    result = get_management_key("lisa-deploy", "us-east-1")

    assert result == "test-api-key"
    mock_boto_client.assert_called_once_with("secretsmanager", region_name="us-east-1")
    # Should try first pattern and succeed
    mock_secrets.get_secret_value.assert_called_once_with(SecretId="lisa-deploy-lisa-management-key")


@patch("lisapy.authentication.boto3.client")
def test_get_management_key_with_deployment_stage(mock_boto_client):
    """Test retrieving management key with deployment stage."""
    mock_secrets = MagicMock()
    mock_secrets.get_secret_value.return_value = {"SecretString": "stage-api-key"}
    mock_boto_client.return_value = mock_secrets

    result = get_management_key("myapp", "us-west-2", "prod")

    assert result == "stage-api-key"
    # With deployment_stage, should try that pattern first
    mock_secrets.get_secret_value.assert_called_once_with(SecretId="prod-myapp-management-key")


@patch("lisapy.authentication.boto3.client")
def test_get_management_key_fallback_pattern(mock_boto_client):
    """Test management key retrieval with pattern fallback."""
    mock_secrets = MagicMock()
    # First two patterns fail, third succeeds
    mock_secrets.get_secret_value.side_effect = [
        Exception("SecretNotFoundException"),
        Exception("SecretNotFoundException"),
        {"SecretString": "fallback-key"},
    ]
    mock_boto_client.return_value = mock_secrets

    result = get_management_key("deploy-name")

    assert result == "fallback-key"
    assert mock_secrets.get_secret_value.call_count == 3


@patch("lisapy.authentication.boto3.client")
def test_get_management_key_not_found(mock_boto_client):
    """Test management key retrieval when no patterns match."""
    mock_secrets = MagicMock()
    mock_secrets.get_secret_value.side_effect = Exception("SecretNotFoundException")
    mock_boto_client.return_value = mock_secrets

    with pytest.raises(RuntimeError) as exc_info:
        get_management_key("nonexistent")

    assert "Could not find management key" in str(exc_info.value)


@patch("lisapy.authentication.boto3.resource")
def test_create_api_token_success(mock_boto_resource):
    """Test creating API token in DynamoDB."""
    mock_dynamodb = MagicMock()
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_boto_resource.return_value = mock_dynamodb

    result = create_api_token("test-deploy", "test-key", "us-east-1", 7200)

    assert result == "test-key"
    mock_boto_resource.assert_called_once_with("dynamodb", region_name="us-east-1")
    mock_dynamodb.Table.assert_called_once_with("test-deploy-LISAApiBaseTokenTable")

    # Verify put_item was called with token and expiration
    assert mock_table.put_item.called
    call_args = mock_table.put_item.call_args[1]
    assert call_args["Item"]["token"] == "test-key"
    assert "tokenExpiration" in call_args["Item"]


@patch("lisapy.authentication.boto3.resource")
def test_create_api_token_default_region(mock_boto_resource):
    """Test creating API token with default region."""
    mock_dynamodb = MagicMock()
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_boto_resource.return_value = mock_dynamodb

    create_api_token("deploy", "key")

    # Should use boto3 default (no region_name kwarg)
    mock_boto_resource.assert_called_once_with("dynamodb")


@patch("lisapy.authentication.create_api_token")
@patch("lisapy.authentication.get_management_key")
def test_setup_authentication_success(mock_get_key, mock_create_token):
    """Test full authentication setup."""
    mock_get_key.return_value = "retrieved-key"
    mock_create_token.return_value = "retrieved-key"

    headers = setup_authentication("my-deployment", "us-east-2")

    assert headers == {"Api-Key": "retrieved-key", "Authorization": "retrieved-key"}
    mock_get_key.assert_called_once_with("my-deployment", "us-east-2", None)
    mock_create_token.assert_called_once_with("my-deployment", "retrieved-key", "us-east-2")


@patch("lisapy.authentication.create_api_token")
@patch("lisapy.authentication.get_management_key")
def test_setup_authentication_with_stage(mock_get_key, mock_create_token):
    """Test authentication setup with deployment stage."""
    mock_get_key.return_value = "stage-key"
    mock_create_token.return_value = "stage-key"

    headers = setup_authentication("app", "eu-west-1", "production")

    assert headers == {"Api-Key": "stage-key", "Authorization": "stage-key"}
    mock_get_key.assert_called_once_with("app", "eu-west-1", "production")


@patch("lisapy.authentication.create_api_token")
@patch("lisapy.authentication.get_management_key")
def test_setup_authentication_token_registration_fails(mock_get_key, mock_create_token):
    """Test authentication setup when token registration fails (should proceed anyway)."""
    mock_get_key.return_value = "key-from-secrets"
    mock_create_token.side_effect = Exception("DynamoDB error")

    # Should not raise, just log warning
    headers = setup_authentication("deploy")

    assert headers == {"Api-Key": "key-from-secrets", "Authorization": "key-from-secrets"}
    mock_get_key.assert_called_once()
    mock_create_token.assert_called_once()
