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

from generate_litellm_config import _build_model_config, _is_embedding_model, get_database_credentials


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


def test_get_database_credentials_secret_not_found():
    """Test error handling when secret is not found."""
    db_params = {
        "username": "testuser",
        "passwordSecretId": "missing-secret-id",
        "dbHost": "db.example.com",
        "dbPort": "5432",
        "dbName": "testdb",
    }

    with patch("generate_litellm_config.boto3.client") as mock_boto:
        mock_secrets = MagicMock()
        mock_secrets.exceptions.ResourceNotFoundException = Exception
        mock_secrets.get_secret_value.side_effect = Exception("Secret not found")
        mock_boto.return_value = mock_secrets

        with pytest.raises(Exception):
            get_database_credentials(db_params)


class TestIsEmbeddingModel:
    """Tests for _is_embedding_model helper function."""

    def test_embedding_in_model_name(self):
        """Test detection when 'embed' is in modelName."""
        model = {"modelName": "qwen3-embed-06b", "modelId": "my-model"}
        assert _is_embedding_model(model) is True

    def test_embedding_in_model_id(self):
        """Test detection when 'embed' is in modelId."""
        model = {"modelName": "some-model", "modelId": "text-embedding-model"}
        assert _is_embedding_model(model) is True

    def test_embedding_case_insensitive(self):
        """Test that detection is case-insensitive."""
        model = {"modelName": "EMBEDDING-MODEL", "modelId": "test"}
        assert _is_embedding_model(model) is True

    def test_non_embedding_model(self):
        """Test that non-embedding models return False."""
        model = {"modelName": "llama-3-70b", "modelId": "my-llama"}
        assert _is_embedding_model(model) is False

    def test_missing_fields(self):
        """Test handling of missing fields."""
        model = {}
        assert _is_embedding_model(model) is False


class TestBuildModelConfig:
    """Tests for _build_model_config helper function."""

    def test_regular_model_config(self):
        """Test config generation for a regular (non-embedding) model."""
        model = {
            "modelId": "my-llama",
            "modelName": "llama-3-70b",
            "endpointUrl": "http://localhost:8000",
        }
        config = _build_model_config(model)

        assert config["model_name"] == "my-llama"
        assert config["litellm_params"]["model"] == "openai/llama-3-70b"
        assert config["litellm_params"]["api_base"] == "http://localhost:8000/v1"
        assert "additional_drop_params" not in config["litellm_params"]

    def test_embedding_model_config(self):
        """Test config generation for an embedding model uses hosted_vllm provider."""
        model = {
            "modelId": "qwen3-embed-06b",
            "modelName": "qwen3-embed-06b",
            "endpointUrl": "http://localhost:8001",
        }
        config = _build_model_config(model)

        assert config["model_name"] == "qwen3-embed-06b"
        assert config["litellm_params"]["model"] == "hosted_vllm/qwen3-embed-06b"
        assert config["litellm_params"]["api_base"] == "http://localhost:8001/v1"
        assert config["litellm_params"]["drop_params"] is True
