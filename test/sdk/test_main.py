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

"""Unit tests for LISA SDK main module."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lisa-sdk"))


class TestLisaLlmInitialization:
    """Test suite for LisaLlm initialization."""

    def test_lisa_llm_basic_init(self):
        """Test basic LisaLlm initialization."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        assert llm.url == "https://api.example.com/v2"
        assert llm.timeout == 10
        assert llm._session is not None

    def test_lisa_llm_url_normalization(self):
        """Test URL normalization adds v2 if missing."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com/")

        assert llm.url == "https://api.example.com/v2"

    def test_lisa_llm_url_preserves_v2(self):
        """Test URL normalization preserves existing v2."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com/v2")

        assert llm.url == "https://api.example.com/v2"

    def test_lisa_llm_with_headers(self):
        """Test LisaLlm initialization with custom headers."""
        from lisapy.main import LisaLlm

        headers = {"Authorization": "Bearer token123"}
        llm = LisaLlm(url="https://api.example.com", headers=headers)

        assert llm.headers == headers
        assert "Authorization" in llm._session.headers

    def test_lisa_llm_with_cookies(self):
        """Test LisaLlm initialization with cookies."""
        from lisapy.main import LisaLlm

        cookies = {"session": "abc123"}
        llm = LisaLlm(url="https://api.example.com", cookies=cookies)

        assert llm.cookies == cookies

    def test_lisa_llm_with_verify(self):
        """Test LisaLlm initialization with SSL verification."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com", verify=False)

        assert llm.verify is False
        assert llm._session.verify is False

    def test_lisa_llm_with_timeout(self):
        """Test LisaLlm initialization with custom timeout."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com", timeout=30)

        assert llm.timeout == 30
        assert llm.async_timeout.total == 30 * 60


class TestLisaLlmListModels:
    """Test suite for list_models method."""

    def test_list_models_success(self):
        """Test successful model listing."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "model1", "object": "model"},
                {"id": "model2", "object": "model"},
            ]
        }

        with patch.object(llm._session, "get", return_value=mock_response):
            models = llm.list_models()

            assert len(models) == 2
            assert models[0]["id"] == "model1"
            assert models[1]["id"] == "model2"

    def test_list_models_error(self):
        """Test model listing with error response."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.object(llm._session, "get", return_value=mock_response):
            with pytest.raises(Exception):
                llm.list_models()


class TestLisaLlmGenerate:
    """Test suite for generate method."""

    def test_generate_success(self):
        """Test successful text generation."""
        from lisapy.main import LisaLlm
        from lisapy.types import FoundationModel, ModelType

        llm = LisaLlm(url="https://api.example.com")
        model = FoundationModel(
            provider="test-provider", model_name="test-model", model_type=ModelType.TEXTGEN, model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Generated response"}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": 10},
        }

        with patch.object(llm._session, "post", return_value=mock_response):
            response = llm.generate("test prompt", model)

            assert response.generated_text == "Generated response"
            assert response.generated_tokens == 10
            assert response.finish_reason == "stop"

    def test_generate_with_model_kwargs(self):
        """Test generation with model kwargs."""
        from lisapy.main import LisaLlm
        from lisapy.types import FoundationModel, ModelKwargs, ModelType

        llm = LisaLlm(url="https://api.example.com")
        kwargs = ModelKwargs(temperature=0.7, max_new_tokens=100)
        model = FoundationModel(
            provider="test-provider", model_name="test-model", model_type=ModelType.TEXTGEN, model_kwargs=kwargs
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": 5},
        }

        with patch.object(llm._session, "post", return_value=mock_response) as mock_post:
            llm.generate("prompt", model)

            # Verify model kwargs were included in request (max_new_tokens → max_tokens)
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert payload["max_tokens"] == 100
            assert payload["temperature"] == 0.7

    def test_generate_error(self):
        """Test generation with error response."""
        from lisapy.main import LisaLlm
        from lisapy.types import FoundationModel, ModelType

        llm = LisaLlm(url="https://api.example.com")
        model = FoundationModel(
            provider="test-provider", model_name="test-model", model_type=ModelType.TEXTGEN, model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch.object(llm._session, "post", return_value=mock_response):
            with pytest.raises(Exception):
                llm.generate("prompt", model)


class TestLisaLlmEmbed:
    """Test suite for embed method."""

    def test_embed_single_text(self):
        """Test embedding single text."""
        from lisapy.main import LisaLlm
        from lisapy.types import FoundationModel, ModelType

        llm = LisaLlm(url="https://api.example.com")
        model = FoundationModel(
            provider="test-provider", model_name="embed-model", model_type=ModelType.EMBEDDING, model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

        with patch.object(llm._session, "post", return_value=mock_response):
            embeddings = llm.embed("test text", model)

            assert len(embeddings) == 1
            assert embeddings[0] == [0.1, 0.2, 0.3]

    def test_embed_multiple_texts(self):
        """Test embedding multiple texts."""
        from lisapy.main import LisaLlm
        from lisapy.types import FoundationModel, ModelType

        llm = LisaLlm(url="https://api.example.com")
        model = FoundationModel(
            provider="test-provider", model_name="embed-model", model_type=ModelType.EMBEDDING, model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}

        with patch.object(llm._session, "post", return_value=mock_response):
            embeddings = llm.embed(["text1", "text2"], model)

            assert len(embeddings) == 2
            assert embeddings[0] == [0.1, 0.2]
            assert embeddings[1] == [0.3, 0.4]

    def test_embed_error(self):
        """Test embedding with error response."""
        from lisapy.main import LisaLlm
        from lisapy.types import FoundationModel, ModelType

        llm = LisaLlm(url="https://api.example.com")
        model = FoundationModel(
            provider="test-provider", model_name="embed-model", model_type=ModelType.EMBEDDING, model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        with patch.object(llm._session, "post", return_value=mock_response):
            with pytest.raises(Exception):
                llm.embed("text", model)


class TestLisaLlmGenerateStream:
    """Test suite for generate_stream method."""

    def test_generate_stream_success(self):
        """Test successful streaming generation."""
        from lisapy.main import LisaLlm
        from lisapy.types import FoundationModel, ModelType

        llm = LisaLlm(url="https://api.example.com")
        model = FoundationModel(
            provider="test-provider", model_name="test-model", model_type=ModelType.TEXTGEN, model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}',
            b'data: {"choices":[{"delta":{"content":" world"},"finish_reason":null}]}',
            b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"completion_tokens":2}}',
            b"data: [DONE]",
        ]

        with patch.object(llm._session, "post", return_value=mock_response):
            tokens = []
            for chunk in llm.generate_stream("prompt", model):
                tokens.append(chunk)

            assert len(tokens) == 3
            assert tokens[0].token == "Hello"
            assert tokens[1].token == " world"
            assert tokens[2].finish_reason == "stop"

    def test_generate_stream_error(self):
        """Test streaming with error response."""
        from lisapy.main import LisaLlm
        from lisapy.types import FoundationModel, ModelType

        llm = LisaLlm(url="https://api.example.com")
        model = FoundationModel(
            provider="test-provider", model_name="test-model", model_type=ModelType.TEXTGEN, model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 400

        with patch.object(llm._session, "post", return_value=mock_response):
            with pytest.raises(Exception):
                list(llm.generate_stream("prompt", model))


class TestLisaLlmHealth:
    """Test suite for health check methods."""

    def test_health_success(self):
        """Health check should return parsed JSON response."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}

        with patch.object(llm._session, "get", return_value=mock_response) as mock_get:
            result = llm.health()

            assert result == {"status": "healthy"}
            mock_get.assert_called_once_with(f"{llm.url}/serve/health")

    def test_health_error(self):
        """Health check should raise on non-200 response."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"status": "unhealthy"}

        with patch.object(llm._session, "get", return_value=mock_response):
            with pytest.raises(Exception):
                llm.health()

    def test_health_readiness_success(self):
        """Readiness check should return parsed JSON response."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ready"}

        with patch.object(llm._session, "get", return_value=mock_response) as mock_get:
            result = llm.health_readiness()

            assert result == {"status": "ready"}
            mock_get.assert_called_once_with(f"{llm.url}/serve/health/readiness")

    def test_health_readiness_error(self):
        """Readiness check should raise on non-200 response."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"status": "not ready"}

        with patch.object(llm._session, "get", return_value=mock_response):
            with pytest.raises(Exception):
                llm.health_readiness()

    def test_health_liveliness_success(self):
        """Liveliness check should normalize string response to dict."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        # LiteLLM returns a plain string "I'm alive!" for this endpoint
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = "I'm alive!"

        with patch.object(llm._session, "get", return_value=mock_response) as mock_get:
            result = llm.health_liveliness()

            assert result == {"status": "I'm alive!"}
            mock_get.assert_called_once_with(f"{llm.url}/serve/health/liveliness")

    def test_health_liveliness_error(self):
        """Liveliness check should raise on non-200 response."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"status": "not alive"}

        with patch.object(llm._session, "get", return_value=mock_response):
            with pytest.raises(Exception):
                llm.health_liveliness()


class TestLisaLlmGetModelInfo:
    """Test suite for get_model_info method."""

    def test_get_model_info_success(self):
        """get_model_info should return a list of ModelInfoEntry objects."""
        from lisapy.main import LisaLlm
        from lisapy.types import ModelInfoEntry

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "model_name": "mistral-vllm",
                    "litellm_params": {"model": "hosted_vllm/mistral-vllm", "api_base": "http://internal-alb/v1"},
                    "model_info": {"id": "abc123", "max_tokens": 4096},
                },
                {
                    "model_name": "titan-embed",
                    "litellm_params": {"model": "bedrock/titan-embed"},
                    "model_info": {"id": "def456"},
                },
            ]
        }

        with patch.object(llm._session, "get", return_value=mock_response) as mock_get:
            result = llm.get_model_info()

            assert len(result) == 2
            assert isinstance(result[0], ModelInfoEntry)
            assert result[0].model_name == "mistral-vllm"
            assert result[0].litellm_params["model"] == "hosted_vllm/mistral-vllm"
            assert result[1].model_name == "titan-embed"
            mock_get.assert_called_once_with(f"{llm.url}/serve/model/info")

    def test_get_model_info_empty(self):
        """get_model_info should return empty list when no models configured."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}

        with patch.object(llm._session, "get", return_value=mock_response):
            result = llm.get_model_info()

            assert result == []

    def test_get_model_info_error(self):
        """get_model_info should raise on non-200 response."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal Server Error"}

        with patch.object(llm._session, "get", return_value=mock_response):
            with pytest.raises(Exception):
                llm.get_model_info()


class TestLisaLlmComplete:
    """Test suite for legacy text completions."""

    def test_complete_success(self):
        """complete() should return a CompletionResponse with parsed fields."""
        from lisapy.main import LisaLlm
        from lisapy.types import CompletionResponse

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "cmpl-abc123",
            "choices": [{"text": " there was a", "index": 0, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9},
        }

        with patch.object(llm._session, "post", return_value=mock_response) as mock_post:
            result = llm.complete("Once upon a time", model="mistral-vllm")

            assert isinstance(result, CompletionResponse)
            assert result.id == "cmpl-abc123"
            assert result.choices[0].text == " there was a"
            assert result.choices[0].finish_reason == "length"
            assert result.usage["completion_tokens"] == 4

            payload = mock_post.call_args[1]["json"]
            assert payload["model"] == "mistral-vllm"
            assert payload["prompt"] == "Once upon a time"
            mock_post.assert_called_once()

    def test_complete_with_kwargs(self):
        """complete() should forward allowed kwargs and filter unknown ones."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "cmpl-xyz",
            "choices": [{"text": "hello", "index": 0, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

        with patch.object(llm._session, "post", return_value=mock_response) as mock_post:
            llm.complete(
                "Say hi",
                model="test-model",
                max_tokens=100,
                temperature=0.7,
                unknown_param="should_be_filtered",
            )

            payload = mock_post.call_args[1]["json"]
            assert payload["max_tokens"] == 100
            assert payload["temperature"] == 0.7
            assert "unknown_param" not in payload

    def test_complete_error(self):
        """complete() should raise on non-200 response."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Bad Request"}

        with patch.object(llm._session, "post", return_value=mock_response):
            with pytest.raises(Exception):
                llm.complete("prompt", model="test-model")


class TestLisaLlmCleanup:
    """Test suite for LisaLlm cleanup."""

    def test_session_cleanup(self):
        """Test session is closed on deletion."""
        from lisapy.main import LisaLlm

        llm = LisaLlm(url="https://api.example.com")
        session = llm._session

        with patch.object(session, "close") as mock_close:
            del llm
            mock_close.assert_called_once()


class TestOnLlmNewToken:
    """Test suite for on_llm_new_token callback."""

    def test_on_llm_new_token(self):
        """Test token callback writes to stdout."""
        from lisapy.main import on_llm_new_token

        with patch("sys.stdout.write") as mock_write:
            with patch("sys.stdout.flush") as mock_flush:
                on_llm_new_token("test_token")

                mock_write.assert_called_once_with("test_token")
                mock_flush.assert_called_once()
