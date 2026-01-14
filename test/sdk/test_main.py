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
from unittest.mock import MagicMock, Mock, patch

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
            provider="test-provider",
            model_name="test-model",
            model_type=ModelType.TEXTGEN,
            model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "generatedText": "Generated response",
            "generatedTokens": 10,
            "finishReason": "stop",
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
            provider="test-provider",
            model_name="test-model",
            model_type=ModelType.TEXTGEN,
            model_kwargs=kwargs
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "generatedText": "Response",
            "generatedTokens": 5,
            "finishReason": "stop",
        }

        with patch.object(llm._session, "post", return_value=mock_response) as mock_post:
            llm.generate("prompt", model)

            # Verify model kwargs were included in request
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert "modelKwargs" in payload
            assert payload["modelKwargs"]["temperature"] == 0.7

    def test_generate_error(self):
        """Test generation with error response."""
        from lisapy.main import LisaLlm
        from lisapy.types import FoundationModel, ModelType

        llm = LisaLlm(url="https://api.example.com")
        model = FoundationModel(
            provider="test-provider",
            model_name="test-model",
            model_type=ModelType.TEXTGEN,
            model_kwargs=None
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
            provider="test-provider",
            model_name="embed-model",
            model_type=ModelType.EMBEDDING,
            model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embeddings": [[0.1, 0.2, 0.3]]
        }

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
            provider="test-provider",
            model_name="embed-model",
            model_type=ModelType.EMBEDDING,
            model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embeddings": [[0.1, 0.2], [0.3, 0.4]]
        }

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
            provider="test-provider",
            model_name="embed-model",
            model_type=ModelType.EMBEDDING,
            model_kwargs=None
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
            provider="test-provider",
            model_name="test-model",
            model_type=ModelType.TEXTGEN,
            model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data:{"token":{"text":"Hello"}}',
            b'data:{"token":{"text":" world"}}',
            b'data:{"finishReason":"stop","generatedTokens":2}',
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
            provider="test-provider",
            model_name="test-model",
            model_type=ModelType.TEXTGEN,
            model_kwargs=None
        )

        mock_response = Mock()
        mock_response.status_code = 400

        with patch.object(llm._session, "post", return_value=mock_response):
            with pytest.raises(Exception):
                list(llm.generate_stream("prompt", model))


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
