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

"""Unit tests for text processing utilities."""

import sys
from pathlib import Path

import pytest

# Add REST API src to path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))


class TestRenderContextFromMessages:
    """Test suite for render_context_from_messages function."""

    def test_render_single_message(self):
        """Test rendering a single message."""
        from services.text_processing import render_context_from_messages

        messages = [{"role": "user", "content": "Hello"}]
        result = render_context_from_messages(messages)

        assert result == "Hello"

    def test_render_multiple_messages(self):
        """Test rendering multiple messages."""
        from services.text_processing import render_context_from_messages

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]
        result = render_context_from_messages(messages)

        assert result == "Hello\n\nHi there\n\nHow are you?"

    def test_render_empty_messages(self):
        """Test rendering empty message list."""
        from services.text_processing import render_context_from_messages

        result = render_context_from_messages([])

        assert result == ""

    def test_render_messages_with_empty_content(self):
        """Test rendering messages with empty content."""
        from services.text_processing import render_context_from_messages

        messages = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "Response"},
        ]
        result = render_context_from_messages(messages)

        assert result == "\n\nResponse"


class TestParseModelProviderFromString:
    """Test suite for parse_model_provider_from_string function."""

    def test_parse_valid_format(self):
        """Test parsing valid model string."""
        from services.text_processing import parse_model_provider_from_string

        model_name, provider = parse_model_provider_from_string("gpt-4 (openai)")

        assert model_name == "gpt-4"
        assert provider == "openai"

    def test_parse_complex_model_name(self):
        """Test parsing complex model names."""
        from services.text_processing import parse_model_provider_from_string

        model_name, provider = parse_model_provider_from_string("llama-2-70b (ecs.textgen.tgi)")

        assert model_name == "llama-2-70b"
        assert provider == "ecs.textgen.tgi"

    def test_parse_invalid_format_no_parentheses(self):
        """Test parsing invalid format without parentheses."""
        from services.text_processing import parse_model_provider_from_string

        with pytest.raises(ValueError) as exc_info:
            parse_model_provider_from_string("gpt-4")

        assert "Invalid model string format" in str(exc_info.value)

    def test_parse_invalid_format_empty_string(self):
        """Test parsing empty string."""
        from services.text_processing import parse_model_provider_from_string

        with pytest.raises(ValueError) as exc_info:
            parse_model_provider_from_string("")

        assert "Invalid model string format" in str(exc_info.value)

    def test_parse_invalid_format_only_parentheses(self):
        """Test parsing string with only parentheses."""
        from services.text_processing import parse_model_provider_from_string

        with pytest.raises(ValueError) as exc_info:
            parse_model_provider_from_string("()")

        assert "Invalid model string format" in str(exc_info.value)

    def test_parse_invalid_format_missing_provider(self):
        """Test parsing string with missing provider."""
        from services.text_processing import parse_model_provider_from_string

        with pytest.raises(ValueError) as exc_info:
            parse_model_provider_from_string("model ()")

        assert "Invalid model string format" in str(exc_info.value)


class TestMapOpenAIParamsToLisa:
    """Test suite for map_openai_params_to_lisa function."""

    def test_map_all_params(self):
        """Test mapping all supported parameters."""
        from services.text_processing import map_openai_params_to_lisa

        request_data = {
            "echo": True,
            "frequency_penalty": 0.5,
            "max_tokens": 100,
            "seed": 42,
            "stop": ["END"],
            "temperature": 0.7,
            "top_p": 0.9,
        }

        result = map_openai_params_to_lisa(request_data)

        assert result["return_full_text"] is True
        assert result["repetition_penalty"] == 0.5
        assert result["max_new_tokens"] == 100
        assert result["seed"] == 42
        assert result["stop_sequences"] == ["END"]
        assert result["temperature"] == 0.7
        assert result["top_p"] == 0.9

    def test_map_partial_params(self):
        """Test mapping only some parameters."""
        from services.text_processing import map_openai_params_to_lisa

        request_data = {
            "temperature": 0.8,
            "max_tokens": 50,
        }

        result = map_openai_params_to_lisa(request_data)

        assert result == {
            "temperature": 0.8,
            "max_new_tokens": 50,
        }

    def test_map_empty_params(self):
        """Test mapping with no parameters."""
        from services.text_processing import map_openai_params_to_lisa

        result = map_openai_params_to_lisa({})

        assert result == {}

    def test_map_ignores_unsupported_params(self):
        """Test that unsupported parameters are ignored."""
        from services.text_processing import map_openai_params_to_lisa

        request_data = {
            "temperature": 0.7,
            "unsupported_param": "value",
            "another_param": 123,
        }

        result = map_openai_params_to_lisa(request_data)

        assert result == {"temperature": 0.7}
        assert "unsupported_param" not in result

    def test_map_ignores_none_values(self):
        """Test that None values are ignored."""
        from services.text_processing import map_openai_params_to_lisa

        request_data = {
            "temperature": 0.7,
            "max_tokens": None,
            "seed": 42,
        }

        result = map_openai_params_to_lisa(request_data)

        assert result == {
            "temperature": 0.7,
            "seed": 42,
        }
        assert "max_new_tokens" not in result
