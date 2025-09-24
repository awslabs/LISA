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

import json
from unittest.mock import Mock, patch

import pytest
from models.model_api_key_cleanup import get_database_connection, lambda_handler


class TestModelApiKeyCleanup:
    """Test cases for model_api_key_cleanup lambda function."""

    @patch("models.model_api_key_cleanup.get_database_connection")
    def test_lambda_handler_delete_request_type(self, mock_get_connection):
        """Test that DELETE request type still processes but returns SUCCESS."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_get_connection.return_value = mock_connection

        event = {"RequestType": "Delete"}
        context = Mock()

        with patch.dict("os.environ", {"AWS_REGION": "us-east-1", "DEPLOYMENT_PREFIX": "/test/LISA/lisa"}):
            result = lambda_handler(event, context)

            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"

    @patch("models.model_api_key_cleanup.get_database_connection")
    def test_lambda_handler_success(self, mock_get_connection):
        """Test successful execution."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [("model-1", '{"api_key": "ignored"}')]
        mock_get_connection.return_value = mock_connection

        with patch.dict("os.environ", {"AWS_REGION": "us-east-1", "DEPLOYMENT_PREFIX": "/test/LISA/lisa"}):
            event = {"RequestType": "Create"}
            context = Mock()

            result = lambda_handler(event, context)

            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
            assert "ModelsUpdated" in result["Data"]

    @patch("models.model_api_key_cleanup.get_database_connection")
    def test_lambda_handler_exception(self, mock_get_connection):
        """Test exception handling."""
        mock_get_connection.side_effect = Exception("Database connection failed")

        with patch.dict("os.environ", {"AWS_REGION": "us-east-1", "DEPLOYMENT_PREFIX": "/test/LISA/lisa"}):
            event = {"RequestType": "Create"}
            context = Mock()

            result = lambda_handler(event, context)

        assert result["Status"] == "FAILED"
        assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
        assert "Database connection failed" in result["Reason"]

    @patch("models.model_api_key_cleanup.boto3.client")
    def test_get_database_connection_success(self, mock_boto3_client):
        """Test successful database connection."""
        mock_ssm_client = Mock()
        mock_secrets_client = Mock()
        mock_boto3_client.side_effect = [mock_ssm_client, mock_secrets_client]

        # Mock SSM parameter response
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {
                "Value": json.dumps(
                    {
                        "dbHost": "test-host",
                        "dbPort": "5432",
                        "dbName": "testdb",
                        "username": "testuser",
                        "passwordSecretId": "test-secret",
                    }
                )
            }
        }

        # Mock Secrets Manager response
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"username": "testuser", "password": "testpass"})
        }

        with patch.dict("os.environ", {"AWS_REGION": "us-east-1", "DEPLOYMENT_PREFIX": "/test/LISA/lisa"}):
            with patch("models.model_api_key_cleanup.psycopg2.connect") as mock_connect:
                mock_connection = Mock()
                mock_connect.return_value = mock_connection

                result = get_database_connection()

                assert result == mock_connection
                mock_connect.assert_called_once()

    @patch("models.model_api_key_cleanup.boto3.client")
    def test_get_database_connection_ssm_error(self, mock_boto3_client):
        """Test SSM parameter retrieval failure."""
        mock_ssm_client = Mock()
        mock_boto3_client.return_value = mock_ssm_client
        mock_ssm_client.get_parameter.side_effect = Exception("SSM error")

        with patch.dict("os.environ", {"AWS_REGION": "us-east-1", "DEPLOYMENT_PREFIX": "/test/LISA/lisa"}):
            with pytest.raises(Exception, match="SSM error"):
                get_database_connection()

    def test_get_database_connection_secrets_error(self):
        """Test Secrets Manager error during database connection."""
        mock_ssm_client = Mock()
        mock_secrets_client = Mock()

        with patch("models.model_api_key_cleanup.boto3.client") as mock_boto3_client:
            mock_boto3_client.side_effect = [mock_ssm_client, mock_secrets_client]

            # Mock SSM parameter response
            mock_ssm_client.get_parameter.return_value = {
                "Parameter": {
                    "Value": json.dumps(
                        {
                            "dbHost": "test-host",
                            "dbPort": "5432",
                            "dbName": "testdb",
                            "username": "testuser",
                            "passwordSecretId": "test-secret",
                        }
                    )
                }
            }

            # Mock Secrets Manager error
            mock_secrets_client.get_secret_value.side_effect = Exception("Secrets error")

            with patch.dict("os.environ", {"AWS_REGION": "us-east-1", "DEPLOYMENT_PREFIX": "/test/LISA/lisa"}):
                with pytest.raises(Exception, match="Secrets error"):
                    get_database_connection()

    @patch("models.model_api_key_cleanup.get_database_connection")
    def test_lambda_handler_no_tables_found(self, mock_get_connection):
        """Test when no LiteLLM tables are found in database."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []  # No tables found
        mock_get_connection.return_value = mock_connection

        with patch.dict("os.environ", {"AWS_REGION": "us-east-1", "DEPLOYMENT_PREFIX": "/test/LISA/lisa"}):
            event = {"RequestType": "Create"}
            context = Mock()

            result = lambda_handler(event, context)

            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
            assert result["Data"]["ModelsUpdated"] == "0"

    @patch("models.model_api_key_cleanup.get_database_connection")
    def test_lambda_handler_table_found_but_no_models(self, mock_get_connection):
        """Test when LiteLLM table is found but no models need updating."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        # Mock table discovery
        mock_cursor.fetchall.side_effect = [
            [("LiteLLM_ProxyModelTable",)],  # Tables found
            [("id", "model_name", "litellm_params")],  # Column info
            [],  # No models with api_key
        ]
        mock_cursor.description = [("id",), ("model_name",), ("litellm_params",)]
        mock_get_connection.return_value = mock_connection

        with patch.dict("os.environ", {"AWS_REGION": "us-east-1", "DEPLOYMENT_PREFIX": "/test/LISA/lisa"}):
            event = {"RequestType": "Create"}
            context = Mock()

            result = lambda_handler(event, context)

            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
            assert "ModelsUpdated" in result["Data"]

    @patch("models.model_api_key_cleanup.get_database_connection")
    def test_lambda_handler_missing_columns(self, mock_get_connection):
        """Test when required columns are not found in the table."""
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        # Mock table discovery but missing required columns
        mock_cursor.fetchall.return_value = [("LiteLLM_ProxyModelTable",)]
        mock_cursor.description = [("some_column",), ("other_column",)]  # Missing required columns
        mock_get_connection.return_value = mock_connection

        with patch.dict("os.environ", {"AWS_REGION": "us-east-1", "DEPLOYMENT_PREFIX": "/test/LISA/lisa"}):
            event = {"RequestType": "Create"}
            context = Mock()

            result = lambda_handler(event, context)

            assert result["Status"] == "SUCCESS"
            assert result["PhysicalResourceId"] == "bedrock-auth-cleanup"
            assert result["Data"]["ModelsUpdated"] == "0"
