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

"""Tests for RDS authentication utilities."""

from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from utilities.rds_auth import generate_auth_token


class TestRdsAuth:
    """Test cases for RDS authentication utilities."""

    def test_generate_auth_token_success(self):
        """Test successful generation of RDS auth token."""
        with patch.dict("os.environ", {"AWS_REGION": "us-east-1"}):
            with patch("boto3.client") as mock_boto3:
                mock_rds = Mock()
                mock_rds.generate_db_auth_token.return_value = "test-token-value"
                mock_boto3.return_value = mock_rds

                result = generate_auth_token("test-host", "5432", "test-user")

                assert result == "test-token-value"
                mock_rds.generate_db_auth_token.assert_called_once_with(
                    DBHostname="test-host", Port="5432", DBUsername="test-user"
                )

    def test_generate_auth_token_with_special_characters(self):
        """Test token with special characters is returned raw without URL encoding."""
        with patch.dict("os.environ", {"AWS_REGION": "us-east-1"}):
            with patch("boto3.client") as mock_boto3:
                mock_rds = Mock()
                mock_rds.generate_db_auth_token.return_value = "token+with/special=chars&more"
                mock_boto3.return_value = mock_rds

                result = generate_auth_token("test-host", "5432", "test-user")

                # Raw token returned directly — psycopg3 handles encoding natively
                assert result == "token+with/special=chars&more"

    def test_generate_auth_token_client_error(self):
        """Test handling of ClientError from RDS client."""
        with patch.dict("os.environ", {"AWS_REGION": "us-east-1"}):
            with patch("boto3.client") as mock_boto3:
                mock_rds = Mock()
                mock_rds.generate_db_auth_token.side_effect = ClientError(
                    error_response={"Error": {"Code": "InvalidParameterValue"}}, operation_name="GenerateDBAuthToken"
                )
                mock_boto3.return_value = mock_rds

                with pytest.raises(ClientError):
                    generate_auth_token("invalid-host", "5432", "test-user")

    def test_generate_auth_token_missing_region(self):
        """Test handling of missing AWS_REGION environment variable."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(KeyError):
                generate_auth_token("test-host", "5432", "test-user")
