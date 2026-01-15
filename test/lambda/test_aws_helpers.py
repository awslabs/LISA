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

"""Unit tests for aws_helpers module."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set required environment variables before importing aws_helpers
os.environ.setdefault("AWS_REGION", "us-east-1")

from utilities.aws_helpers import (
    get_account_and_partition,
    get_cert_path,
    get_lambda_role_name,
    get_rest_api_container_endpoint,
)


class TestGetCertPath:
    """Test get_cert_path function."""

    @patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": ""}, clear=False)
    def test_returns_true_when_no_arn(self):
        """Test get_cert_path returns True when no ARN is specified."""
        mock_iam = MagicMock()

        # Clear cache
        get_cert_path.cache_clear()

        result = get_cert_path(mock_iam)

        assert result is True
        mock_iam.get_server_certificate.assert_not_called()

    @patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:acm:us-east-1:123456789012:certificate/abc-123"}, clear=False)
    def test_returns_true_for_acm_certificate(self):
        """Test get_cert_path returns True for ACM certificates."""
        mock_iam = MagicMock()

        # Clear cache
        get_cert_path.cache_clear()

        result = get_cert_path(mock_iam)

        assert result is True
        mock_iam.get_server_certificate.assert_not_called()

    @patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:iam::123456789012:server-certificate/test-cert"}, clear=False)
    def test_retrieves_iam_certificate(self):
        """Test get_cert_path retrieves IAM certificate."""
        mock_iam = MagicMock()
        mock_iam.get_server_certificate.return_value = {
            "ServerCertificate": {"CertificateBody": "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----"}
        }

        # Clear cache
        get_cert_path.cache_clear()

        result = get_cert_path(mock_iam)

        assert isinstance(result, str)
        assert result != ""
        mock_iam.get_server_certificate.assert_called_once_with(ServerCertificateName="test-cert")

    @patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:iam::123456789012:server-certificate/my-cert"}, clear=False)
    def test_falls_back_on_iam_error(self):
        """Test get_cert_path falls back to True when IAM call fails."""
        mock_iam = MagicMock()
        mock_iam.get_server_certificate.side_effect = Exception("IAM error")

        # Clear cache
        get_cert_path.cache_clear()

        result = get_cert_path(mock_iam)

        assert result is True

    @patch.dict(os.environ, {"RESTAPI_SSL_CERT_ARN": "arn:aws:iam::123456789012:server-certificate/test"}, clear=False)
    def test_caches_result(self):
        """Test get_cert_path caches the result."""
        mock_iam = MagicMock()
        mock_iam.get_server_certificate.return_value = {
            "ServerCertificate": {"CertificateBody": "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----"}
        }

        # Clear cache
        get_cert_path.cache_clear()

        # First call
        result1 = get_cert_path(mock_iam)
        # Second call
        result2 = get_cert_path(mock_iam)

        assert result1 == result2
        # Should only call IAM once due to caching
        assert mock_iam.get_server_certificate.call_count == 1


class TestGetRestApiContainerEndpoint:
    """Test get_rest_api_container_endpoint function."""

    @patch("utilities.aws_helpers.ssm_client")
    @patch.dict(os.environ, {"LISA_API_URL_PS_NAME": "/lisa/api/url", "REST_API_VERSION": "v2"}, clear=False)
    def test_retrieves_endpoint_from_ssm(self, mock_ssm):
        """Test get_rest_api_container_endpoint retrieves endpoint from SSM."""
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "https://api.example.com"}}

        # Clear cache
        get_rest_api_container_endpoint.cache_clear()

        result = get_rest_api_container_endpoint()

        assert result == "https://api.example.com/v2/serve"
        mock_ssm.get_parameter.assert_called_once_with(Name="/lisa/api/url")

    @patch("utilities.aws_helpers.ssm_client")
    @patch.dict(os.environ, {"LISA_API_URL_PS_NAME": "/test/url", "REST_API_VERSION": "v1"}, clear=False)
    def test_constructs_correct_endpoint(self, mock_ssm):
        """Test get_rest_api_container_endpoint constructs correct endpoint."""
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "https://test.api.com"}}

        # Clear cache
        get_rest_api_container_endpoint.cache_clear()

        result = get_rest_api_container_endpoint()

        assert result == "https://test.api.com/v1/serve"

    @patch("utilities.aws_helpers.ssm_client")
    @patch.dict(os.environ, {"LISA_API_URL_PS_NAME": "/api/url", "REST_API_VERSION": "v3"}, clear=False)
    def test_caches_result(self, mock_ssm):
        """Test get_rest_api_container_endpoint caches the result."""
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "https://cached.api.com"}}

        # Clear cache
        get_rest_api_container_endpoint.cache_clear()

        # First call
        result1 = get_rest_api_container_endpoint()
        # Second call
        result2 = get_rest_api_container_endpoint()

        assert result1 == result2
        # Should only call SSM once due to caching
        assert mock_ssm.get_parameter.call_count == 1


class TestGetLambdaRoleName:
    """Test get_lambda_role_name function."""

    @patch("utilities.aws_helpers.boto3.client")
    def test_extracts_role_name_from_arn(self, mock_boto_client):
        """Test get_lambda_role_name extracts role name from ARN."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Arn": "arn:aws:sts::123456789012:assumed-role/MyLambdaRole/lambda-function"
        }
        mock_boto_client.return_value = mock_sts

        role_name = get_lambda_role_name()

        assert role_name == "MyLambdaRole"

    @patch("utilities.aws_helpers.boto3.client")
    def test_handles_different_role_names(self, mock_boto_client):
        """Test get_lambda_role_name handles different role name formats."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Arn": "arn:aws:sts::987654321098:assumed-role/CustomRole-With-Dashes/function-name"
        }
        mock_boto_client.return_value = mock_sts

        role_name = get_lambda_role_name()

        assert role_name == "CustomRole-With-Dashes"


class TestGetAccountAndPartition:
    """Test get_account_and_partition function."""

    @patch.dict(os.environ, {"AWS_ACCOUNT_ID": "123456789012", "AWS_PARTITION": "aws"}, clear=True)
    def test_returns_from_environment_variables(self):
        """Test get_account_and_partition returns from environment variables."""
        os.environ["AWS_REGION"] = "us-east-1"

        account, partition = get_account_and_partition()

        assert account == "123456789012"
        assert partition == "aws"

    @patch.dict(
        os.environ,
        {"ECR_REPOSITORY_ARN": "arn:aws-us-gov:ecr:us-gov-west-1:987654321098:repository/my-repo"},
        clear=True,
    )
    def test_extracts_from_ecr_arn(self):
        """Test get_account_and_partition extracts from ECR ARN."""
        os.environ["AWS_REGION"] = "us-gov-west-1"

        account, partition = get_account_and_partition()

        assert account == "987654321098"
        assert partition == "aws-us-gov"

    @patch.dict(os.environ, {}, clear=True)
    def test_returns_defaults_when_missing(self):
        """Test get_account_and_partition returns defaults when variables missing."""
        os.environ["AWS_REGION"] = "us-east-1"

        account, partition = get_account_and_partition()

        assert account == ""
        assert partition == "aws"

    @patch.dict(os.environ, {"AWS_PARTITION": "aws-cn"}, clear=True)
    def test_uses_partition_from_env(self):
        """Test get_account_and_partition uses partition from environment."""
        os.environ["AWS_REGION"] = "cn-north-1"

        account, partition = get_account_and_partition()

        assert partition == "aws-cn"

    @patch.dict(
        os.environ,
        {"AWS_ACCOUNT_ID": "111111111111", "ECR_REPOSITORY_ARN": "arn:aws:ecr:us-east-1:222222222222:repository/repo"},
        clear=True,
    )
    def test_prefers_env_over_ecr_arn(self):
        """Test get_account_and_partition prefers environment variables over ECR ARN."""
        os.environ["AWS_REGION"] = "us-east-1"

        account, partition = get_account_and_partition()

        # Should use account from AWS_ACCOUNT_ID, not ECR ARN
        assert account == "111111111111"
