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

from lisapy.authentication import get_cognito_token


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
