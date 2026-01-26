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

"""Fixtures for REST API unit tests."""

from unittest.mock import MagicMock, Mock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    env_vars = {
        "AWS_REGION": "us-east-1",
        "LOG_LEVEL": "INFO",
        "USE_AUTH": "false",
        "TOKEN_TABLE_NAME": "test-token-table",
        "MANAGEMENT_KEY_NAME": "test-management-key",
        "CLIENT_ID": "test-client-id",
        "AUTHORITY": "https://test-authority.com",
        "ADMIN_GROUP": "admin",
        "USER_GROUP": "users",
        "JWT_GROUPS_PROP": "cognito:groups",
        "REGISTERED_MODELS_PS_NAME": "/test/models",
        "GUARDRAILS_TABLE_NAME": "test-guardrails-table",
        "USAGE_METRICS_QUEUE_URL": "",
        "LITELLM_KEY": "test-litellm-key",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request object."""
    request = Mock(spec=Request)
    request.headers = {}
    request.method = "GET"
    request.url = Mock()
    request.url.path = "/test"

    # Use a simple object for state instead of Mock to allow attribute deletion
    class State:
        pass

    request.state = State()
    return request


@pytest.fixture
def mock_jwt_data() -> dict:
    """Mock JWT data for testing."""
    return {
        "sub": "user-123",
        "username": "testuser",
        "cognito:groups": ["users", "developers"],
        "email": "test@example.com",
        "exp": 9999999999,  # Far future
        "iat": 1000000000,
        "iss": "https://test-authority.com",
        "aud": "test-client-id",
    }


@pytest.fixture
def mock_admin_jwt_data() -> dict:
    """Mock JWT data for admin user."""
    return {
        "sub": "admin-123",
        "username": "adminuser",
        "cognito:groups": ["admin", "users"],
        "email": "admin@example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "iss": "https://test-authority.com",
        "aud": "test-client-id",
    }


@pytest.fixture
def mock_token_info() -> dict:
    """Mock API token info from DynamoDB."""
    return {
        "token": "hashed-token-value",
        "tokenUUID": "token-uuid-123",
        "tokenExpiration": 9999999999,  # Far future
        "username": "api-user",
        "groups": ["users"],
    }


@pytest.fixture
def mock_admin_token_info() -> dict:
    """Mock admin API token info from DynamoDB."""
    return {
        "token": "hashed-admin-token",
        "tokenUUID": "admin-token-uuid",
        "tokenExpiration": 9999999999,
        "username": "api-admin",
        "groups": ["admin", "users"],
    }


@pytest.fixture
def simple_fastapi_app():
    """Create a simple FastAPI app for testing."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    @app.get("/health")
    async def health():
        return {"status": "OK"}

    return app


@pytest.fixture
def test_client(simple_fastapi_app):
    """Create a test client for the FastAPI app."""
    return TestClient(simple_fastapi_app)


@pytest.fixture
def mock_boto3_client(monkeypatch):
    """Mock boto3 clients."""
    mock_ddb_table = MagicMock()
    mock_secrets_client = MagicMock()
    mock_ssm_client = MagicMock()
    mock_sqs_client = MagicMock()

    def mock_resource(service_name, **kwargs):
        if service_name == "dynamodb":
            mock_resource = MagicMock()
            mock_resource.Table.return_value = mock_ddb_table
            return mock_resource
        return MagicMock()

    def mock_client(service_name, **kwargs):
        if service_name == "secretsmanager":
            return mock_secrets_client
        elif service_name == "ssm":
            return mock_ssm_client
        elif service_name == "sqs":
            return mock_sqs_client
        return MagicMock()

    monkeypatch.setattr("boto3.resource", mock_resource)
    monkeypatch.setattr("boto3.client", mock_client)

    return {
        "dynamodb_table": mock_ddb_table,
        "secrets_manager": mock_secrets_client,
        "ssm": mock_ssm_client,
        "sqs": mock_sqs_client,
    }


@pytest.fixture
def mock_guardrails():
    """Mock guardrails data."""
    return [
        {
            "guardrailName": "content-filter",
            "modelId": "test-model",
            "allowedGroups": ["users"],
            "markedForDeletion": False,
        },
        {
            "guardrailName": "pii-filter",
            "modelId": "test-model",
            "allowedGroups": [],
            "markedForDeletion": False,
        },
    ]


@pytest.fixture
def mock_registered_models():
    """Mock registered models cache."""
    return {
        "textgen": {"ecs.textgen.tgi": ["test-model", "other-model"]},
        "embedding": {"ecs.embedding.tei": ["embedding-model"]},
        "embeddings": {"ecs.embedding.tei": ["embedding-model"]},
        "generate": {"ecs.textgen.tgi": ["test-model", "other-model"]},
        "generateStream": {"ecs.textgen.tgi": ["test-model"]},
        "metadata": {
            "ecs.textgen.tgi.test-model": {
                "provider": "ecs.textgen.tgi",
                "modelName": "test-model",
                "modelType": "textgen",
                "modelKwargs": {},
            }
        },
        "endpointUrls": {"ecs.textgen.tgi.test-model": "http://test-endpoint"},
    }
