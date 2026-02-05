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

"""Tests for REST API handlers with dependency injection."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the REST API source to the path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))


class MockRegistry:
    """Mock registry for testing."""

    def get_assets(self, provider: str):
        """Mock get_assets method."""
        return {
            "adapter": MagicMock(return_value=MagicMock()),
            "validator": MagicMock,
        }


@pytest.fixture
def mock_registry():
    """Fixture for mock registry."""
    return MockRegistry()


@pytest.fixture
def mock_registered_models_cache():
    """Fixture for mock registered models cache."""
    from utils.resources import ModelType, RestApiResource

    return {
        ModelType.TEXTGEN: {"test-provider": ["test-model"]},
        ModelType.EMBEDDING: {"test-provider": ["test-embedding-model"]},
        RestApiResource.EMBEDDINGS: {"test-provider": ["test-embedding-model"]},
        RestApiResource.GENERATE: {"test-provider": ["test-model"]},
        RestApiResource.GENERATE_STREAM: {"test-provider": ["test-model"]},
        "metadata": {},
        "endpointUrls": {
            "test-provider.test-model": "http://test-endpoint",
            "test-provider.test-embedding-model": "http://test-embedding-endpoint",
        },
    }


class TestGenerationHandlers:
    """Tests for generation handlers."""

    @pytest.mark.asyncio
    async def test_handle_generate_success(self, mock_registry, mock_registered_models_cache):
        """Test successful generation."""
        from handlers.generation import handle_generate

        # Mock the cache and model
        with patch("utils.request_utils.get_registered_models_cache", return_value=mock_registered_models_cache):
            with patch("utils.request_utils.get_model_assets", return_value=None):
                with patch("utils.request_utils.cache_model_assets"):
                    # Create mock model with generate method
                    mock_model = MagicMock()
                    mock_response = MagicMock()
                    mock_response.dict.return_value = {"generated_text": "test response"}
                    mock_model.generate = AsyncMock(return_value=mock_response)

                    # Mock the adapter to return our mock model
                    mock_registry.get_assets = MagicMock(
                        return_value={
                            "adapter": MagicMock(return_value=mock_model),
                            "validator": MagicMock(return_value=MagicMock(dict=MagicMock(return_value={}))),
                        }
                    )

                    request_data = {
                        "provider": "test-provider",
                        "modelName": "test-model",
                        "text": "test prompt",
                        "modelKwargs": {},
                    }

                    result = await handle_generate(request_data, registry=mock_registry)

                    assert result == {"generated_text": "test response"}
                    mock_model.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_generate_error(self, mock_registry, mock_registered_models_cache):
        """Test generation with error."""
        from handlers.generation import handle_generate

        with patch("utils.request_utils.get_registered_models_cache", return_value=mock_registered_models_cache):
            with patch("utils.request_utils.get_model_assets", return_value=None):
                with patch("utils.request_utils.cache_model_assets"):
                    # Create mock model that raises an exception
                    mock_model = MagicMock()
                    mock_model.generate = AsyncMock(side_effect=RuntimeError("Model error"))

                    mock_registry.get_assets = MagicMock(
                        return_value={
                            "adapter": MagicMock(return_value=mock_model),
                            "validator": MagicMock(return_value=MagicMock(dict=MagicMock(return_value={}))),
                        }
                    )

                    request_data = {
                        "provider": "test-provider",
                        "modelName": "test-model",
                        "text": "test prompt",
                        "modelKwargs": {},
                    }

                    with pytest.raises(RuntimeError, match="Model error"):
                        await handle_generate(request_data, registry=mock_registry)

    @pytest.mark.asyncio
    async def test_handle_generate_stream_success(self, mock_registry, mock_registered_models_cache):
        """Test successful streaming generation."""
        from handlers.generation import handle_generate_stream

        with patch("utils.request_utils.get_registered_models_cache", return_value=mock_registered_models_cache):
            with patch("utils.request_utils.get_model_assets", return_value=None):
                with patch("utils.request_utils.cache_model_assets"):
                    # Create mock model with generate_stream method
                    mock_model = MagicMock()

                    async def mock_stream(*args, **kwargs):
                        mock_response = MagicMock()
                        mock_response.dict.return_value = {"text": "chunk1"}
                        yield mock_response
                        mock_response = MagicMock()
                        mock_response.dict.return_value = {"text": "chunk2"}
                        yield mock_response

                    mock_model.generate_stream = mock_stream

                    mock_registry.get_assets = MagicMock(
                        return_value={
                            "adapter": MagicMock(return_value=mock_model),
                            "validator": MagicMock(return_value=MagicMock(dict=MagicMock(return_value={}))),
                        }
                    )

                    request_data = {
                        "provider": "test-provider",
                        "modelName": "test-model",
                        "text": "test prompt",
                        "modelKwargs": {},
                    }

                    chunks = []
                    async for chunk in handle_generate_stream(request_data, registry=mock_registry):
                        chunks.append(chunk)

                    assert len(chunks) == 2
                    assert 'data:{"text": "chunk1"}' in chunks[0]
                    assert 'data:{"text": "chunk2"}' in chunks[1]

    @pytest.mark.asyncio
    async def test_handle_openai_generate_stream_chat(self, mock_registry, mock_registered_models_cache):
        """Test OpenAI chat completions streaming."""
        from handlers.generation import handle_openai_generate_stream

        with patch("utils.request_utils.get_registered_models_cache", return_value=mock_registered_models_cache):
            with patch("utils.request_utils.get_model_assets", return_value=None):
                with patch("utils.request_utils.cache_model_assets"):
                    # Create mock model
                    mock_model = MagicMock()

                    async def mock_stream(*args, **kwargs):
                        mock_response = MagicMock()
                        mock_response.dict.return_value = {"choices": [{"delta": {"content": "test"}}]}
                        yield mock_response

                    mock_model.openai_generate_stream = mock_stream

                    mock_registry.get_assets = MagicMock(
                        return_value={
                            "adapter": MagicMock(return_value=mock_model),
                            "validator": MagicMock(return_value=MagicMock(dict=MagicMock(return_value={}))),
                        }
                    )

                    request_data = {
                        "model": "test-model (test-provider)",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": True,
                    }

                    chunks = []
                    async for chunk in handle_openai_generate_stream(
                        request_data, is_text_completion=False, registry=mock_registry
                    ):
                        chunks.append(chunk)

                    assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_handle_openai_generate_stream_text_completion(self, mock_registry, mock_registered_models_cache):
        """Test OpenAI text completions streaming."""
        from handlers.generation import handle_openai_generate_stream

        with patch("utils.request_utils.get_registered_models_cache", return_value=mock_registered_models_cache):
            with patch("utils.request_utils.get_model_assets", return_value=None):
                with patch("utils.request_utils.cache_model_assets"):
                    # Create mock model
                    mock_model = MagicMock()

                    async def mock_stream(*args, **kwargs):
                        mock_response = MagicMock()
                        mock_response.dict.return_value = {"choices": [{"text": "test"}]}
                        yield mock_response

                    mock_model.openai_generate_stream = mock_stream

                    mock_registry.get_assets = MagicMock(
                        return_value={
                            "adapter": MagicMock(return_value=mock_model),
                            "validator": MagicMock(return_value=MagicMock(dict=MagicMock(return_value={}))),
                        }
                    )

                    request_data = {
                        "model": "test-model (test-provider)",
                        "prompt": "Hello",
                        "stream": True,
                    }

                    chunks = []
                    async for chunk in handle_openai_generate_stream(
                        request_data, is_text_completion=True, registry=mock_registry
                    ):
                        chunks.append(chunk)

                    # Should have at least the response chunk and [DONE]
                    assert len(chunks) >= 2
                    assert "data: [DONE]" in chunks[-1]

    @pytest.mark.asyncio
    async def test_backward_compatibility_aliases(self):
        """Test backward compatibility aliases."""
        from handlers.generation import parse_model_provider_names, render_context
        from services.text_processing import parse_model_provider_from_string, render_context_from_messages

        # These should be the same functions
        assert render_context == render_context_from_messages
        assert parse_model_provider_names == parse_model_provider_from_string


class TestEmbeddingHandlers:
    """Tests for embedding handlers."""

    @pytest.mark.asyncio
    async def test_handle_embeddings_success(self, mock_registry, mock_registered_models_cache):
        """Test successful embeddings."""
        from handlers.embeddings import handle_embeddings

        with patch("utils.request_utils.get_registered_models_cache", return_value=mock_registered_models_cache):
            with patch("utils.request_utils.get_model_assets", return_value=None):
                with patch("utils.request_utils.cache_model_assets"):
                    # Create mock model with embed_query method
                    mock_model = MagicMock()
                    mock_response = MagicMock()
                    mock_response.dict.return_value = {"embeddings": [0.1, 0.2, 0.3]}
                    mock_model.embed_query = AsyncMock(return_value=mock_response)

                    mock_registry.get_assets = MagicMock(
                        return_value={
                            "adapter": MagicMock(return_value=mock_model),
                            "validator": MagicMock(return_value=MagicMock(dict=MagicMock(return_value={}))),
                        }
                    )

                    request_data = {
                        "provider": "test-provider",
                        "modelName": "test-embedding-model",
                        "text": "test text",
                        "modelKwargs": {},
                    }

                    result = await handle_embeddings(request_data, registry=mock_registry)

                    assert result == {"embeddings": [0.1, 0.2, 0.3]}
                    mock_model.embed_query.assert_called_once()


class TestModelsHandlers:
    """Tests for models handlers."""

    @pytest.mark.asyncio
    async def test_handle_list_models(self):
        """Test listing models."""
        from handlers.models import handle_list_models
        from services.model_service import ModelService
        from utils.resources import ModelType

        mock_cache = {
            ModelType.TEXTGEN: {"provider1": ["model1", "model2"]},
            ModelType.EMBEDDING: {"provider2": ["embed1"]},
        }

        mock_service = ModelService(mock_cache)

        result = await handle_list_models([ModelType.TEXTGEN], model_service=mock_service)

        assert ModelType.TEXTGEN in result
        assert "provider1" in result[ModelType.TEXTGEN]
        assert result[ModelType.TEXTGEN]["provider1"] == ["model1", "model2"]

    @pytest.mark.asyncio
    async def test_handle_list_models_default_service(self):
        """Test listing models with default service (no injection)."""
        from handlers.models import handle_list_models
        from utils.resources import ModelType

        mock_cache = {
            ModelType.TEXTGEN: {"provider1": ["model1"]},
        }

        with patch("handlers.models.get_registered_models_cache", return_value=mock_cache):
            result = await handle_list_models([ModelType.TEXTGEN])

            assert ModelType.TEXTGEN in result
            assert "provider1" in result[ModelType.TEXTGEN]

    @pytest.mark.asyncio
    async def test_handle_openai_list_models(self):
        """Test OpenAI-compatible model listing."""
        from handlers.models import handle_openai_list_models
        from services.model_service import ModelService
        from utils.resources import ModelType

        mock_cache = {
            ModelType.TEXTGEN: {"provider1": ["model1"], "provider2": ["model2"]},
            ModelType.EMBEDDING: {"provider3": ["embed1"]},
        }

        mock_service = ModelService(mock_cache)

        result = await handle_openai_list_models(model_service=mock_service)

        assert "object" in result
        assert result["object"] == "list"
        assert "data" in result
        assert len(result["data"]) == 2  # Only textgen models

    @pytest.mark.asyncio
    async def test_handle_describe_model_success(self):
        """Test describing a specific model."""
        from handlers.models import handle_describe_model
        from services.model_service import ModelService
        from utils.resources import ModelType

        mock_cache = {
            ModelType.TEXTGEN: {"provider1": ["model1"]},
            "metadata": {"provider1.model1": {"name": "model1", "type": "textgen", "description": "Test model"}},
        }

        mock_service = ModelService(mock_cache)

        result = await handle_describe_model("provider1", "model1", model_service=mock_service)

        assert result["name"] == "model1"
        assert result["type"] == "textgen"

    @pytest.mark.asyncio
    async def test_handle_describe_model_not_found(self):
        """Test describing a model that doesn't exist."""
        from fastapi import HTTPException
        from handlers.models import handle_describe_model
        from services.model_service import ModelService

        mock_cache = {
            "metadata": {},
        }

        mock_service = ModelService(mock_cache)

        with pytest.raises(HTTPException) as exc_info:
            await handle_describe_model("unknown", "unknown-model", model_service=mock_service)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_handle_describe_models(self):
        """Test describing multiple models."""
        from handlers.models import handle_describe_models
        from services.model_service import ModelService
        from utils.resources import ModelType

        mock_cache = {
            ModelType.TEXTGEN: {"provider1": ["model1", "model2"]},
            "metadata": {
                "provider1.model1": {"name": "model1", "type": "textgen"},
                "provider1.model2": {"name": "model2", "type": "textgen"},
            },
        }

        mock_service = ModelService(mock_cache)

        result = await handle_describe_models([ModelType.TEXTGEN], model_service=mock_service)

        assert "textgen" in result
        assert "provider1" in result["textgen"]
        assert len(result["textgen"]["provider1"]) == 2
        assert result["textgen"]["provider1"][0]["name"] == "model1"
        assert result["textgen"]["provider1"][1]["name"] == "model2"


class TestRequestUtils:
    """Tests for request utility functions."""

    @pytest.mark.asyncio
    async def test_validate_model_success(self, mock_registered_models_cache):
        """Test successful model validation."""
        from utils.request_utils import validate_model
        from utils.resources import RestApiResource

        with patch("utils.request_utils.get_registered_models_cache", return_value=mock_registered_models_cache):
            request_data = {"provider": "test-provider", "modelName": "test-model"}

            # Should not raise
            await validate_model(request_data, RestApiResource.GENERATE)

    @pytest.mark.asyncio
    async def test_validate_model_not_found(self, mock_registered_models_cache):
        """Test model validation with model not found."""
        from utils.request_utils import validate_model
        from utils.resources import RestApiResource

        with patch("utils.request_utils.get_registered_models_cache", return_value=mock_registered_models_cache):
            request_data = {"provider": "test-provider", "modelName": "nonexistent-model"}

            with pytest.raises(ValueError, match="Provider does not support model"):
                await validate_model(request_data, RestApiResource.GENERATE)

    @pytest.mark.asyncio
    async def test_get_model_and_validator_from_cache(self, mock_registry):
        """Test getting model and validator from cache."""
        from utils.request_utils import get_model_and_validator

        mock_model = MagicMock()
        mock_validator = MagicMock()
        cached_assets = (mock_model, mock_validator)

        with patch("utils.request_utils.get_model_assets", return_value=cached_assets):
            request_data = {"provider": "test-provider", "modelName": "test-model"}

            model, validator = await get_model_and_validator(request_data, registry=mock_registry)

            assert model == mock_model
            assert validator == mock_validator

    @pytest.mark.asyncio
    async def test_get_model_and_validator_from_registry(self, mock_registry, mock_registered_models_cache):
        """Test getting model and validator from registry."""
        from utils.request_utils import get_model_and_validator

        with patch("utils.request_utils.get_model_assets", return_value=None):
            with patch("utils.request_utils.get_registered_models_cache", return_value=mock_registered_models_cache):
                with patch("utils.request_utils.cache_model_assets") as mock_cache:
                    mock_model = MagicMock()
                    mock_validator = MagicMock()

                    mock_registry.get_assets = MagicMock(
                        return_value={"adapter": MagicMock(return_value=mock_model), "validator": mock_validator}
                    )

                    request_data = {"provider": "test-provider", "modelName": "test-model"}

                    model, validator = await get_model_and_validator(request_data, registry=mock_registry)

                    assert model == mock_model
                    assert validator == mock_validator
                    mock_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_and_prepare_llm_request(self, mock_registry, mock_registered_models_cache):
        """Test validate and prepare LLM request."""
        from utils.request_utils import validate_and_prepare_llm_request
        from utils.resources import RestApiResource

        with patch("utils.request_utils.get_registered_models_cache", return_value=mock_registered_models_cache):
            with patch("utils.request_utils.get_model_assets", return_value=None):
                with patch("utils.request_utils.cache_model_assets"):
                    mock_model = MagicMock()
                    mock_validator_instance = MagicMock()
                    mock_validator_instance.dict.return_value = {"param": "value"}
                    mock_validator = MagicMock(return_value=mock_validator_instance)

                    mock_registry.get_assets = MagicMock(
                        return_value={"adapter": MagicMock(return_value=mock_model), "validator": mock_validator}
                    )

                    request_data = {
                        "provider": "test-provider",
                        "modelName": "test-model",
                        "text": "test text",
                        "modelKwargs": {"param": "value"},
                    }

                    model, model_kwargs, text = await validate_and_prepare_llm_request(
                        request_data, RestApiResource.GENERATE, registry=mock_registry
                    )

                    assert model == mock_model
                    assert model_kwargs == {"param": "value"}
                    assert text == "test text"

    @pytest.mark.asyncio
    async def test_validate_and_prepare_llm_request_missing_text(self, mock_registry, mock_registered_models_cache):
        """Test validate and prepare LLM request with missing text."""
        from utils.request_utils import validate_and_prepare_llm_request
        from utils.resources import RestApiResource

        with patch("utils.request_utils.get_registered_models_cache", return_value=mock_registered_models_cache):
            with patch("utils.request_utils.get_model_assets", return_value=None):
                with patch("utils.request_utils.cache_model_assets"):
                    mock_model = MagicMock()
                    mock_validator_instance = MagicMock()
                    mock_validator_instance.dict.return_value = {}
                    mock_validator = MagicMock(return_value=mock_validator_instance)

                    mock_registry.get_assets = MagicMock(
                        return_value={"adapter": MagicMock(return_value=mock_model), "validator": mock_validator}
                    )

                    request_data = {
                        "provider": "test-provider",
                        "modelName": "test-model",
                        "modelKwargs": {},
                    }

                    with pytest.raises(ValueError, match="Missing required field: text"):
                        await validate_and_prepare_llm_request(
                            request_data, RestApiResource.GENERATE, registry=mock_registry
                        )
