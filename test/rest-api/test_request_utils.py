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
            
            mock_cache = {
                RestApiResource.GENERATE: {
                    "ecs.textgen.tgi": ["test-model", "other-model"]
                }
            }
            
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
            
            mock_cache = {
                RestApiResource.GENERATE: {
                    "ecs.textgen.tgi": ["test-model", "other-model"]
                }
            }
            
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
