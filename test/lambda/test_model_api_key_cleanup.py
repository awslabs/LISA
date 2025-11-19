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
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture
def setup_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("DEPLOYMENT_PREFIX", "/test/prefix")


@pytest.fixture
def mock_ssm():
    with patch("boto3.client") as mock_client:
        mock_ssm = MagicMock()
        mock_client.return_value = mock_ssm
        yield mock_ssm


def test_get_all_dynamodb_models_success(setup_env):
    from models.model_api_key_cleanup import get_all_dynamodb_models

    with patch("boto3.client") as mock_client:
        mock_dynamodb = MagicMock()
        mock_ssm = MagicMock()

        def client_factory(service, **kwargs):
            if service == "dynamodb":
                return mock_dynamodb
            return mock_ssm

        mock_client.side_effect = client_factory
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "test-table"}}
        mock_dynamodb.scan.return_value = {
            "Items": [{"model_id": {"S": "model1"}, "model_config": {"M": {"modelName": {"S": "bedrock/test"}}}}]
        }

        models = get_all_dynamodb_models()
        assert len(models) == 1
        assert models[0]["model_id"] == "model1"


def test_get_all_dynamodb_models_no_prefix(monkeypatch):
    from models.model_api_key_cleanup import get_all_dynamodb_models

    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("DEPLOYMENT_PREFIX", raising=False)

    # Function returns empty list instead of raising
    result = get_all_dynamodb_models()
    assert result == []


def test_get_database_connection_success(setup_env):
    with patch("boto3.client") as mock_client:
        mock_ssm = MagicMock()
        mock_secrets = MagicMock()

        def client_factory(service, **kwargs):
            if service == "ssm":
                return mock_ssm
            return mock_secrets

        mock_client.side_effect = client_factory
        mock_ssm.get_parameter.return_value = {
            "Parameter": {
                "Value": json.dumps(
                    {
                        "dbHost": "localhost",
                        "dbPort": 5432,
                        "dbName": "test",
                        "username": "user",
                        "passwordSecretId": "secret",
                    }
                )
            }
        }
        mock_secrets.get_secret_value.return_value = {"SecretString": json.dumps({"password": "pass"})}

        with patch("models.model_api_key_cleanup.connect") as mock_connect:
            mock_connect.return_value = MagicMock()

            from models.model_api_key_cleanup import get_database_connection

            conn = get_database_connection()
            assert conn is not None


def test_lambda_handler_missing_env_var(monkeypatch):
    from models.model_api_key_cleanup import lambda_handler

    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("DEPLOYMENT_PREFIX", raising=False)

    result = lambda_handler({}, {})
    assert result["Status"] == "FAILED"


def test_lambda_handler_no_litellm_table(setup_env):
    from models.model_api_key_cleanup import lambda_handler

    with patch("models.model_api_key_cleanup.get_database_connection") as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("other_table",)]
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_connection

        result = lambda_handler({}, {})
        assert result["Status"] == "SUCCESS"
        assert result["Data"]["ModelsUpdated"] == "0"


def test_lambda_handler_success(setup_env):
    from models.model_api_key_cleanup import lambda_handler

    with patch("models.model_api_key_cleanup.get_database_connection") as mock_conn:
        with patch("models.model_api_key_cleanup.get_all_dynamodb_models") as mock_models:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.side_effect = [
                [("LiteLLM_ProxyModelTable",)],
                [("id", "name", "params")],
                [("1", "model1", '{"api_key": "ignored"}')],
            ]
            mock_cursor.description = [("id",), ("name",), ("params",)]
            mock_connection = MagicMock()
            mock_connection.cursor.return_value = mock_cursor
            mock_conn.return_value = mock_connection

            mock_models.return_value = [{"model_id": "model1", "model_name": "bedrock/test"}]

            result = lambda_handler({}, {})
            assert result["Status"] == "SUCCESS"
