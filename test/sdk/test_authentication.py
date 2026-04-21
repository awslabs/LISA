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

"""Unit tests for authentication helpers."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from lisapy.authentication import get_management_key, setup_authentication


def _client_error(code: str = "ResourceNotFoundException") -> ClientError:
    """Build a botocore ClientError."""
    return ClientError({"Error": {"Code": code, "Message": "not found"}}, "GetSecretValue")


class TestGetManagementKey:
    """Tests for get_management_key exception handling."""

    @patch("lisapy.authentication.boto3.client")
    def test_client_error_falls_through_to_next_pattern(self, mock_boto_client):
        """ClientError on first pattern should try the next pattern."""
        mock_sm = MagicMock()
        mock_boto_client.return_value = mock_sm
        mock_sm.get_secret_value.side_effect = [
            _client_error(),
            {"SecretString": "the-key"},
        ]
        key = get_management_key("myapp", region="us-east-1")
        assert key == "the-key"
        assert mock_sm.get_secret_value.call_count == 2

    @patch("lisapy.authentication.boto3.client")
    def test_non_client_error_reraises_immediately(self, mock_boto_client):
        """Non-ClientError (e.g., RuntimeError) should re-raise, not try next pattern."""
        mock_sm = MagicMock()
        mock_boto_client.return_value = mock_sm
        mock_sm.get_secret_value.side_effect = RuntimeError("unexpected")
        with pytest.raises(RuntimeError, match="Unexpected error"):
            get_management_key("myapp", region="us-east-1")
        # Should have stopped after the first call, not tried all patterns
        assert mock_sm.get_secret_value.call_count == 1

    @patch("lisapy.authentication.boto3.client")
    def test_success_on_second_pattern(self, mock_boto_client):
        """First pattern fails with ClientError, second succeeds."""
        mock_sm = MagicMock()
        mock_boto_client.return_value = mock_sm
        mock_sm.get_secret_value.side_effect = [
            _client_error(),
            _client_error(),
            {"SecretString": "found-it"},
        ]
        key = get_management_key("myapp", region="us-east-1")
        assert key == "found-it"


class TestSetupAuthentication:
    """Tests for setup_authentication exception handling."""

    @patch("lisapy.authentication.create_api_token")
    @patch("lisapy.authentication.get_management_key")
    def test_dynamo_client_error_continues(self, mock_get_key, mock_create_token):
        """ClientError from DynamoDB token creation should not block auth."""
        mock_get_key.return_value = "the-key"
        mock_create_token.side_effect = _client_error("AccessDeniedException")
        headers = setup_authentication("myapp", region="us-east-1")
        assert headers["Api-Key"] == "the-key"
        assert headers["Authorization"] == "the-key"

    @patch("lisapy.authentication.create_api_token")
    @patch("lisapy.authentication.get_management_key")
    def test_dynamo_non_client_error_continues(self, mock_get_key, mock_create_token):
        """Non-ClientError from DynamoDB should also not block auth (non-fatal)."""
        mock_get_key.return_value = "the-key"
        mock_create_token.side_effect = RuntimeError("unexpected dynamo failure")
        headers = setup_authentication("myapp", region="us-east-1")
        assert headers["Api-Key"] == "the-key"
        assert headers["Authorization"] == "the-key"
