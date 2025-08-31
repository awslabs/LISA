#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

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
    if 'models.clients.litellm_client' in sys.modules:
        del sys.modules['models.clients.litellm_client']
    
    from starlette.datastructures import Headers
    from models.clients.litellm_client import LiteLLMClient
    
    headers = Headers({"Authorization": "Bearer test-token"})
    client = LiteLLMClient(
        base_uri="https://api.example.com",
        headers=headers,
        verify=True,
        timeout=30
    )
    
    # Test that attributes are set correctly
    assert hasattr(client, '_base_uri')
    assert hasattr(client, '_headers')
    assert hasattr(client, '_verify')
    assert hasattr(client, '_timeout')


@patch('requests.get')
def test_list_models_basic(mock_get):
    """Test list_models basic functionality."""
    if 'models.clients.litellm_client' in sys.modules:
        del sys.modules['models.clients.litellm_client']
    
    from starlette.datastructures import Headers
    from models.clients.litellm_client import LiteLLMClient
    
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}
    mock_get.return_value = mock_response
    
    headers = Headers({})
    client = LiteLLMClient("https://api.example.com", headers, True, 30)
    
    result = client.list_models()
    assert isinstance(result, list)


@patch('requests.post')
def test_add_model_basic(mock_post):
    """Test add_model basic functionality."""
    if 'models.clients.litellm_client' in sys.modules:
        del sys.modules['models.clients.litellm_client']
    
    from starlette.datastructures import Headers
    from models.clients.litellm_client import LiteLLMClient
    
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ok"}
    mock_post.return_value = mock_response
    
    headers = Headers({})
    client = LiteLLMClient("https://api.example.com", headers, True, 30)
    
    result = client.add_model("test-model", {"model": "gpt-3.5-turbo"})
    assert "status" in result


def test_get_model_not_found_basic():
    """Test get_model raises ModelNotFoundError when model doesn't exist."""
    if 'models.clients.litellm_client' in sys.modules:
        del sys.modules['models.clients.litellm_client']
    if 'models.exception' in sys.modules:
        del sys.modules['models.exception']
    
    from starlette.datastructures import Headers
    from models.clients.litellm_client import LiteLLMClient
    from models.exception import ModelNotFoundError
    
    headers = Headers({})
    client = LiteLLMClient("https://api.example.com", headers, True, 30)
    
    with patch.object(client, 'list_models', return_value=[]):
        with pytest.raises(ModelNotFoundError):
            client.get_model("nonexistent-model")