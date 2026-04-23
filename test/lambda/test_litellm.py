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


import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


def test_litellm_client_basic():
    """Test basic LiteLLMClient functionality."""
    if "lisa.domain.clients.litellm_client" in sys.modules:
        del sys.modules["lisa.domain.clients.litellm_client"]

    from lisa.domain.clients.litellm_client import LiteLLMClient
    from starlette.datastructures import Headers

    headers = Headers({"Authorization": "Bearer test-token"})
    client = LiteLLMClient(base_uri="https://api.example.com", headers=headers, verify=True, timeout=30)

    # Test that attributes are set correctly
    assert hasattr(client, "_base_uri")
    assert hasattr(client, "_headers")
    assert hasattr(client, "_verify")
    assert hasattr(client, "_timeout")


@patch("requests.get")
def test_list_models_basic(mock_get):
    """Test list_models basic functionality."""
    if "lisa.domain.clients.litellm_client" in sys.modules:
        del sys.modules["lisa.domain.clients.litellm_client"]

    from lisa.domain.clients.litellm_client import LiteLLMClient
    from starlette.datastructures import Headers

    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}
    mock_get.return_value = mock_response

    headers = Headers({})
    client = LiteLLMClient("https://api.example.com", headers, True, 30)

    result = client.list_models()
    assert isinstance(result, list)


@patch("requests.post")
def test_add_model_basic(mock_post):
    """Test add_model basic functionality."""
    if "lisa.domain.clients.litellm_client" in sys.modules:
        del sys.modules["lisa.domain.clients.litellm_client"]

    from lisa.domain.clients.litellm_client import LiteLLMClient
    from starlette.datastructures import Headers

    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ok"}
    mock_post.return_value = mock_response

    headers = Headers({})
    client = LiteLLMClient("https://api.example.com", headers, True, 30)

    result = client.add_model("test-model", {"model": "gpt-3.5-turbo"})
    assert "status" in result


def test_get_model_not_found_basic():
    """Test get_model raises ModelNotFoundError when model doesn't exist."""
    if "lisa.domain.clients.litellm_client" in sys.modules:
        del sys.modules["lisa.domain.clients.litellm_client"]
    if "models.exception" in sys.modules:
        del sys.modules["models.exception"]

    from lisa.domain.clients.litellm_client import LiteLLMClient
    from lisa.domain.exception import ModelNotFoundError
    from starlette.datastructures import Headers

    headers = Headers({})
    client = LiteLLMClient("https://api.example.com", headers, True, 30)

    with patch.object(client, "list_models", return_value=[]):
        with pytest.raises(ModelNotFoundError):
            client.get_model("nonexistent-model")


def test_get_model_found_basic():
    """Test get_model returns model data when model exists."""
    if "lisa.domain.clients.litellm_client" in sys.modules:
        del sys.modules["lisa.domain.clients.litellm_client"]

    from lisa.domain.clients.litellm_client import LiteLLMClient
    from starlette.datastructures import Headers

    headers = Headers({})
    client = LiteLLMClient("https://api.example.com", headers, True, 30)

    mock_model = {
        "model_name": "test-model",
        "model_info": {
            "id": "test-id-123",
            "max_input_tokens": 200000,
            "max_output_tokens": 64000,
        },
    }

    with patch.object(client, "list_models", return_value=[mock_model]):
        result = client.get_model("test-id-123")
        assert result == mock_model
        assert result["model_info"]["max_input_tokens"] == 200000


def test_get_model_returns_context_window_info():
    """Test get_model returns model_info containing max_input_tokens (context window)."""
    if "lisa.domain.clients.litellm_client" in sys.modules:
        del sys.modules["lisa.domain.clients.litellm_client"]

    from lisa.domain.clients.litellm_client import LiteLLMClient
    from starlette.datastructures import Headers

    headers = Headers({})
    client = LiteLLMClient("https://api.example.com", headers, True, 30)

    mock_model = {
        "model_name": "sonnet-4-5",
        "litellm_params": {
            "model": "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        },
        "model_info": {
            "id": "litellm-uuid-abc",
            "max_tokens": 64000,
            "max_input_tokens": 200000,
            "max_output_tokens": 64000,
        },
    }

    with patch.object(client, "list_models", return_value=[mock_model]):
        result = client.get_model("litellm-uuid-abc")
        context_window = result.get("model_info", {}).get("max_input_tokens")
        assert context_window == 200000


def test_get_model_without_context_window():
    """Test get_model handles models that have no max_input_tokens in model_info."""
    if "lisa.domain.clients.litellm_client" in sys.modules:
        del sys.modules["lisa.domain.clients.litellm_client"]

    from lisa.domain.clients.litellm_client import LiteLLMClient
    from starlette.datastructures import Headers

    headers = Headers({})
    client = LiteLLMClient("https://api.example.com", headers, True, 30)

    mock_model = {
        "model_name": "custom-model",
        "model_info": {
            "id": "litellm-uuid-xyz",
        },
    }

    with patch.object(client, "list_models", return_value=[mock_model]):
        result = client.get_model("litellm-uuid-xyz")
        context_window = result.get("model_info", {}).get("max_input_tokens")
        assert context_window is None
