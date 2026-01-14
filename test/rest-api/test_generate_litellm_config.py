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

"""Unit tests for LiteLLM config generation."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Set up environment
os.environ["AWS_REGION"] = "us-east-1"
os.environ["REGISTERED_MODELS_PS_NAME"] = "/test/models"
os.environ["LITELLM_DB_INFO_PS_NAME"] = "/test/db"

# Add REST API to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib/serve/rest-api/src/utils"))

from generate_litellm_config import get_database_credentials


@pytest.fixture
def temp_config_file():
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"db_key": "test-master-key", "model_list": []}
        yaml.dump(config, f)
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


def test_get_database_credentials_with_secret():
    """Test getting database credentials from Secrets Manager."""
    db_params = {
        "username": "testuser",
        "passwordSecretId": "test-secret-id",
        "dbHost": "db.example.com",
        "dbPort": "5432",
        "dbName": "testdb",
    }

    with patch("generate_litellm_config.boto3.client") as mock_boto:
        mock_secrets = MagicMock()
        mock_secrets.get_secret_value.return_value = {"SecretString": json.dumps({"password": "test-password-123"})}
        mock_boto.return_value = mock_secrets

        username, password = get_database_credentials(db_params)

        assert username == "testuser"
        assert password == "test-password-123"
        mock_secrets.get_secret_value.assert_called_once_with(SecretId="test-secret-id")


def test_get_database_credentials_with_iam():
    """Test getting database credentials using IAM auth."""
    db_params = {"dbHost": "db.example.com", "dbPort": "5432", "dbName": "testdb"}

    with patch("generate_litellm_config.get_lambda_role_name") as mock_role:
        with patch("generate_litellm_config.generate_auth_token") as mock_token:
            mock_role.return_value = "MyLambdaRole"
            mock_token.return_value = "iam-auth-token"

            username, password = get_database_credentials(db_params)

            assert username == "MyLambdaRole"
            assert password == "iam-auth-token"
            mock_token.assert_called_once_with("db.example.com", "5432", "MyLambdaRole")


def test_get_database_credentials_prefers_secret():
    """Test that Secrets Manager is preferred over IAM auth."""
    db_params = {
        "username": "testuser",
        "passwordSecretId": "test-secret-id",
        "dbHost": "db.example.com",
        "dbPort": "5432",
        "dbName": "testdb",
    }

    with patch("generate_litellm_config.boto3.client") as mock_boto:
        with patch("generate_litellm_config.get_lambda_role_name") as mock_role:
            with patch("generate_litellm_config.generate_auth_token") as mock_token:
                mock_secrets = MagicMock()
                mock_secrets.get_secret_value.return_value = {
                    "SecretString": json.dumps({"password": "secret-password"})
                }
                mock_boto.return_value = mock_secrets

                username, password = get_database_credentials(db_params)

                # Should use Secrets Manager, not IAM
                assert username == "testuser"
                assert password == "secret-password"
                mock_role.assert_not_called()
                mock_token.assert_not_called()
