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

"""Unit tests for REST API request utilities."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add REST API src to path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))

# Note: We cannot directly import request_utils because it imports lisa_serve.registry
# which has dependencies on text_generation and other packages not available in test environment.
# These tests verify the logic through mocking.


class TestValidateModel:
    """Test suite for validate_model function."""

    @pytest.mark.asyncio
    async def test_validate_model_success(self):
        """Test successful model validation."""
        # Import inside test with mocked dependencies
        with patch.dict("sys.modules", {"lisa_serve.registry": MagicMock()}):
            from utils.request_utils import validate_model
            from utils.resources import RestApiResource

            request_data = {
                "provider": "ecs.textgen.tgi",
                "modelName": "test-model",
            }

            mock_cache = {RestApiResource.GENERATE: {"ecs.textgen.tgi": ["test-model", "other-model"]}}

            with patch("utils.request_utils.get_registered_models_cache", return_value=mock_cache):
                # Should not raise exception
                await validate_model(request_data, RestApiResource.GENERATE)

    @pytest.mark.asyncio
    async def test_validate_model_not_registered(self):
        """Test validation fails for unregistered model."""
        with patch.dict("sys.modules", {"lisa_serve.registry": MagicMock()}):
            from utils.request_utils import validate_model
            from utils.resources import RestApiResource

            request_data = {
                "provider": "ecs.textgen.tgi",
                "modelName": "unknown-model",
            }

            mock_cache = {RestApiResource.GENERATE: {"ecs.textgen.tgi": ["test-model", "other-model"]}}

            with patch("utils.request_utils.get_registered_models_cache", return_value=mock_cache):
                with pytest.raises(ValueError) as exc_info:
                    await validate_model(request_data, RestApiResource.GENERATE)

                assert "does not support model" in str(exc_info.value)


class TestHandleStreamExceptions:
    """Test suite for handle_stream_exceptions decorator."""

    @pytest.mark.asyncio
    async def test_handle_stream_normal_operation(self):
        """Test decorator passes through normal stream items."""
        with patch.dict("sys.modules", {"lisa_serve.registry": MagicMock()}):
            from utils.request_utils import handle_stream_exceptions

            @handle_stream_exceptions
            async def test_stream():
                yield "item1"
                yield "item2"
                yield "item3"

            results = []
            async for item in test_stream():
                results.append(item)

            assert results == ["item1", "item2", "item3"]

    @pytest.mark.asyncio
    async def test_handle_stream_with_exception(self):
        """Test decorator handles exceptions in stream."""
        with patch.dict("sys.modules", {"lisa_serve.registry": MagicMock()}):
            from utils.request_utils import handle_stream_exceptions

            @handle_stream_exceptions
            async def test_stream():
                yield "item1"
                raise ValueError("Test error")

            results = []
            async for item in test_stream():
                results.append(item)

            assert len(results) == 2
            assert results[0] == "item1"
            assert "data:" in results[1]
            assert "error" in results[1]
            assert "ValueError" in results[1]

    @pytest.mark.asyncio
    async def test_handle_stream_error_format(self):
        """Test error message format in stream."""
        with patch.dict("sys.modules", {"lisa_serve.registry": MagicMock()}):
            from utils.request_utils import handle_stream_exceptions

            @handle_stream_exceptions
            async def test_stream():
                yield "dummy"  # Need at least one yield to make it a generator
                raise RuntimeError("Custom error message")

            results = []
            async for item in test_stream():
                results.append(item)

            assert len(results) == 2
            assert results[0] == "dummy"
            error_data = json.loads(results[1].replace("data:", ""))

            assert error_data["event"] == "error"
            assert error_data["data"]["error"]["type"] == "RuntimeError"
            assert error_data["data"]["error"]["message"] == "Custom error message"
            assert "trace" in error_data["data"]["error"]



class TestGetModelAndValidator:
    """Test suite for get_model_and_validator function."""

    @pytest.mark.asyncio
    async def test_get_model_from_cache(self):
        """Test getting model and validator from cache."""
        with patch.dict("sys.modules", {"lisa_serve.registry": MagicMock()}):
            from utils.request_utils import get_model_and_validator

            mock_model = MagicMock()
            mock_validator = MagicMock()

            with patch("utils.request_utils.get_model_assets") as mock_get_assets:
                mock_get_assets.return_value = (mock_model, mock_validator)

                request_data = {
                    "provider": "ecs.textgen.tgi",
                    "modelName": "test-model",
                }

                model, validator = await get_model_and_validator(request_data)

                assert model == mock_model
                assert validator == mock_validator
                mock_get_assets.assert_called_once_with("ecs.textgen.tgi.test-model")

    @pytest.mark.asyncio
    async def test_get_model_from_registry(self):
        """Test getting model from registry when not cached."""
        with patch.dict("sys.modules", {"lisa_serve.registry": MagicMock()}):
            from utils.request_utils import get_model_and_validator

            mock_adapter = MagicMock()
            mock_validator = MagicMock()
            mock_model = MagicMock()
            mock_adapter.return_value = mock_model

            mock_registry = MagicMock()
            mock_registry.get_assets.return_value = {
                "adapter": mock_adapter,
                "validator": mock_validator,
            }

            with patch("utils.request_utils.get_model_assets") as mock_get_assets:
                with patch("utils.request_utils.registry", mock_registry):
                    with patch("utils.request_utils.get_registered_models_cache") as mock_cache:
                        with patch("utils.request_utils.cache_model_assets") as mock_cache_assets:
                            # Not in cache
                            mock_get_assets.return_value = None
                            
                            # Cache has endpoint URL
                            mock_cache.return_value = {
                                "endpointUrls": {"ecs.textgen.tgi.test-model": "http://test-endpoint"}
                            }

                            request_data = {
                                "provider": "ecs.textgen.tgi",
                                "modelName": "test-model",
                            }

                            model, validator = await get_model_and_validator(request_data)

                            assert model == mock_model
                            assert validator == mock_validator
                            mock_adapter.assert_called_once_with(
                                model_name="test-model",
                                endpoint_url="http://test-endpoint"
                            )
                            mock_cache_assets.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_model_endpoint_not_found(self):
        """Test error when endpoint URL not found."""
        with patch.dict("sys.modules", {"lisa_serve.registry": MagicMock()}):
            from utils.request_utils import get_model_and_validator

            mock_registry = MagicMock()
            mock_registry.get_assets.return_value = {
                "adapter": MagicMock(),
                "validator": MagicMock(),
            }

            with patch("utils.request_utils.get_model_assets") as mock_get_assets:
                with patch("utils.request_utils.registry", mock_registry):
                    with patch("utils.request_utils.get_registered_models_cache") as mock_cache:
                        mock_get_assets.return_value = None
                        mock_cache.return_value = {"endpointUrls": {}}

                        request_data = {
                            "provider": "unknown",
                            "modelName": "unknown-model",
                        }

                        with pytest.raises(KeyError) as exc_info:
                            await get_model_and_validator(request_data)

                        assert "Model endpoint URL not found" in str(exc_info.value)


class TestValidateAndPrepareLlmRequest:
    """Test suite for validate_and_prepare_llm_request function."""

    @pytest.mark.asyncio
    async def test_validate_and_prepare_success(self):
        """Test successful validation and preparation."""
        with patch.dict("sys.modules", {"lisa_serve.registry": MagicMock()}):
            from utils.request_utils import validate_and_prepare_llm_request
            from utils.resources import RestApiResource

            mock_model = MagicMock()
            mock_validator_class = MagicMock()
            mock_validator_instance = MagicMock()
            mock_validator_instance.dict.return_value = {"temperature": 0.7}
            mock_validator_class.return_value = mock_validator_instance

            with patch("utils.request_utils.validate_model") as mock_validate:
                with patch("utils.request_utils.get_model_and_validator") as mock_get_model:
                    mock_validate.return_value = None
                    mock_get_model.return_value = (mock_model, mock_validator_class)

                    request_data = {
                        "provider": "ecs.textgen.tgi",
                        "modelName": "test-model",
                        "text": "test prompt",
                        "modelKwargs": {"temperature": 0.7},
                    }

                    model, kwargs, text = await validate_and_prepare_llm_request(
                        request_data, RestApiResource.GENERATE
                    )

                    assert model == mock_model
                    assert kwargs == {"temperature": 0.7}
                    assert text == "test prompt"

    @pytest.mark.asyncio
    async def test_validate_and_prepare_missing_text(self):
        """Test error when text field is missing."""
        with patch.dict("sys.modules", {"lisa_serve.registry": MagicMock()}):
            from utils.request_utils import validate_and_prepare_llm_request
            from utils.resources import RestApiResource

            with patch("utils.request_utils.validate_model") as mock_validate:
                with patch("utils.request_utils.get_model_and_validator") as mock_get_model:
                    mock_validate.return_value = None
                    mock_validator = MagicMock()
                    mock_validator.return_value.dict.return_value = {}
                    mock_get_model.return_value = (MagicMock(), mock_validator)

                    request_data = {
                        "provider": "ecs.textgen.tgi",
                        "modelName": "test-model",
                        "modelKwargs": {},
                    }

                    with pytest.raises(ValueError) as exc_info:
                        await validate_and_prepare_llm_request(request_data, RestApiResource.GENERATE)

                    assert "Missing required field: text" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_and_prepare_with_empty_kwargs(self):
        """Test validation with empty model kwargs."""
        with patch.dict("sys.modules", {"lisa_serve.registry": MagicMock()}):
            from utils.request_utils import validate_and_prepare_llm_request
            from utils.resources import RestApiResource

            mock_model = MagicMock()
            mock_validator_class = MagicMock()
            mock_validator_instance = MagicMock()
            mock_validator_instance.dict.return_value = {}
            mock_validator_class.return_value = mock_validator_instance

            with patch("utils.request_utils.validate_model") as mock_validate:
                with patch("utils.request_utils.get_model_and_validator") as mock_get_model:
                    mock_validate.return_value = None
                    mock_get_model.return_value = (mock_model, mock_validator_class)

                    request_data = {
                        "provider": "ecs.textgen.tgi",
                        "modelName": "test-model",
                        "text": "test prompt",
                        "modelKwargs": {},
                    }

                    model, kwargs, text = await validate_and_prepare_llm_request(
                        request_data, RestApiResource.GENERATE
                    )

                    assert model == mock_model
                    assert kwargs == {}
                    assert text == "test prompt"
