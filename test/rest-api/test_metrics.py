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

"""Unit tests for REST API metrics utilities."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add REST API src to path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))

# Mock AWS_REGION before importing metrics
import os

os.environ.setdefault("AWS_REGION", "us-east-1")

from utils.metrics import extract_messages_for_metrics, extract_token_usage, publish_metrics_event


class TestExtractMessagesForMetrics:
    """Test suite for extract_messages_for_metrics function."""

    def test_extract_simple_messages(self):
        """Test extraction of simple string messages."""
        params = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
                {"role": "system", "content": "You are helpful"},
            ]
        }

        result = extract_messages_for_metrics(params)

        assert len(result) == 3
        assert result[0]["type"] == "human"
        assert result[0]["content"] == "Hello"
        assert result[1]["type"] == "ai"
        assert result[1]["content"] == "Hi there"
        assert result[2]["type"] == "system"
        assert result[2]["content"] == "You are helpful"

    def test_extract_array_content_messages(self):
        """Test extraction of messages with array content."""
        params = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "First part"},
                        {"type": "text", "text": "Second part"},
                    ],
                }
            ]
        }

        result = extract_messages_for_metrics(params)

        assert len(result) == 1
        assert result[0]["type"] == "human"
        # Content should be preserved as array
        assert isinstance(result[0]["content"], list)

    def test_extract_messages_with_rag_context(self):
        """Test detection of RAG context in messages."""
        params = {"messages": [{"role": "user", "content": "Question about File context: document.pdf"}]}

        result = extract_messages_for_metrics(params)

        assert len(result) == 1
        assert result[0]["metadata"].get("ragContext") is True

    def test_extract_messages_with_tool_calls(self):
        """Test extraction of messages with tool calls."""
        params = {
            "messages": [
                {
                    "role": "assistant",
                    "content": "Let me check that",
                    "tool_calls": [
                        {"id": "call_123", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}}
                    ],
                }
            ]
        }

        result = extract_messages_for_metrics(params)

        assert len(result) == 1
        assert "toolCalls" in result[0]
        assert len(result[0]["toolCalls"]) == 1
        assert result[0]["toolCalls"][0]["id"] == "call_123"

    def test_extract_empty_messages(self):
        """Test extraction with no messages."""
        params = {"messages": []}

        result = extract_messages_for_metrics(params)

        assert result == []

    def test_extract_missing_messages_key(self):
        """Test extraction when messages key is missing."""
        params = {}

        result = extract_messages_for_metrics(params)

        assert result == []

    def test_extract_unknown_role(self):
        """Test extraction with unknown role."""
        params = {"messages": [{"role": "custom_role", "content": "Test"}]}

        result = extract_messages_for_metrics(params)

        assert len(result) == 1
        assert result[0]["type"] == "custom_role"

    def test_extract_mixed_content_types(self):
        """Test extraction with mixed content types."""
        params = {
            "messages": [
                {"role": "user", "content": "Simple string"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Array content"},
                        {"type": "image", "url": "http://example.com/image.jpg"},
                    ],
                },
            ]
        }

        result = extract_messages_for_metrics(params)

        assert len(result) == 2
        assert isinstance(result[0]["content"], str)
        assert isinstance(result[1]["content"], list)


class TestPublishMetricsEvent:
    """Test suite for publish_metrics_event function."""

    def test_publish_metrics_success(self, mock_env_vars, mock_request):
        """Test successful metrics publishing."""
        mock_env_vars["USAGE_METRICS_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789/metrics"

        params = {"messages": [{"role": "user", "content": "Hello"}]}

        mock_request.state.username = "test-user"
        mock_request.state.groups = ["users"]

        mock_sqs = MagicMock()

        with patch.dict("os.environ", mock_env_vars), patch("utils.metrics.sqs_client", mock_sqs), patch(
            "utils.metrics.get_user_context", return_value=("test-user", ["users"])
        ), patch("utils.metrics.is_api_user", return_value=True):

            publish_metrics_event(mock_request, params, 200)

            mock_sqs.send_message.assert_called_once()
            call_args = mock_sqs.send_message.call_args

            assert call_args[1]["QueueUrl"] == mock_env_vars["USAGE_METRICS_QUEUE_URL"]

            # Verify message body structure
            message_body = json.loads(call_args[1]["MessageBody"])
            assert message_body["userId"] == "test-user"
            assert message_body["userGroups"] == ["users"]
            assert "sessionId" in message_body
            assert "messages" in message_body
            assert "timestamp" in message_body

    def test_publish_metrics_non_200_status(self, mock_env_vars, mock_request):
        """Test metrics not published for non-200 status."""
        mock_env_vars["USAGE_METRICS_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789/metrics"

        params = {"messages": []}
        mock_sqs = MagicMock()

        with patch.dict("os.environ", mock_env_vars), patch("utils.metrics.sqs_client", mock_sqs):

            publish_metrics_event(mock_request, params, 400)

            mock_sqs.send_message.assert_not_called()

    def test_publish_metrics_no_queue_url(self, mock_env_vars, mock_request):
        """Test metrics not published when queue URL not configured."""
        mock_env_vars.pop("USAGE_METRICS_QUEUE_URL", None)

        params = {"messages": []}
        mock_sqs = MagicMock()

        with patch.dict("os.environ", mock_env_vars, clear=True), patch("utils.metrics.sqs_client", mock_sqs):

            publish_metrics_event(mock_request, params, 200)

            mock_sqs.send_message.assert_not_called()

    def test_publish_metrics_error_handling(self, mock_env_vars, mock_request):
        """Test error handling during metrics publishing."""
        mock_env_vars["USAGE_METRICS_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789/metrics"

        params = {"messages": []}
        mock_sqs = MagicMock()
        mock_sqs.send_message.side_effect = Exception("SQS error")

        with patch.dict("os.environ", mock_env_vars), patch("utils.metrics.sqs_client", mock_sqs), patch(
            "utils.metrics.get_user_context", return_value=("test-user", [])
        ):

            # Should not raise exception
            publish_metrics_event(mock_request, params, 200)

    def test_publish_metrics_session_id_format(self, mock_env_vars, mock_request):
        """Test session ID format for API users."""
        mock_env_vars["USAGE_METRICS_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789/metrics"

        params = {"messages": []}
        mock_sqs = MagicMock()

        with patch.dict("os.environ", mock_env_vars), patch("utils.metrics.sqs_client", mock_sqs), patch(
            "utils.metrics.get_user_context", return_value=("api-user", [])
        ), patch("utils.metrics.is_api_user", return_value=True):

            publish_metrics_event(mock_request, params, 200)

            call_args = mock_sqs.send_message.call_args
            message_body = json.loads(call_args[1]["MessageBody"])

            # Session ID should start with "api-"
            assert message_body["sessionId"].startswith("api-")

    def test_publish_metrics_with_complex_messages(self, mock_env_vars, mock_request):
        """Test metrics publishing with complex message structure."""
        mock_env_vars["USAGE_METRICS_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789/metrics"

        params = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi", "tool_calls": [{"id": "call_1", "type": "function"}]},
            ]
        }

        mock_sqs = MagicMock()

        with patch.dict("os.environ", mock_env_vars), patch("utils.metrics.sqs_client", mock_sqs), patch(
            "utils.metrics.get_user_context", return_value=("user", ["users"])
        ), patch("utils.metrics.is_api_user", return_value=True):

            publish_metrics_event(mock_request, params, 200)

            call_args = mock_sqs.send_message.call_args
            message_body = json.loads(call_args[1]["MessageBody"])

            assert len(message_body["messages"]) == 2
            assert "toolCalls" in message_body["messages"][1]


class TestExtractTokenUsage:
    """Test suite for extract_token_usage function (covers both non-streaming and SSE chunk paths)."""

    def test_extract_from_non_streaming_response(self):
        """Verify token extraction from a representative LiteLLM non-streaming response body.

        Expected: Returns (prompt_tokens, completion_tokens) from the 'usage' field.
        """
        response_body = {
            "id": "chatcmpl-abc",
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": "Hi"}}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 7, "total_tokens": 22},
        }

        pt, ct = extract_token_usage(response_body)

        assert pt == 15
        assert ct == 7

    def test_extract_from_sse_usage_chunk(self):
        """Verify token extraction from the SSE usage chunk emitted at end of streaming response.

        LiteLLM emits a final chunk: {"usage": {"prompt_tokens": N, "completion_tokens": N, ...}}
        The same extract_token_usage function handles both cases.
        """
        chunk_data = {
            "id": "chatcmpl-xyz",
            "usage": {"prompt_tokens": 42, "completion_tokens": 18, "total_tokens": 60},
        }

        pt, ct = extract_token_usage(chunk_data)

        assert pt == 42
        assert ct == 18

    def test_extract_missing_usage_field(self):
        """Returns (None, None) when 'usage' key is absent."""
        response_body = {"choices": [{"message": {"content": "Hi"}}]}

        pt, ct = extract_token_usage(response_body)

        assert pt is None
        assert ct is None

    def test_extract_none_input(self):
        """Returns (None, None) for None input."""
        pt, ct = extract_token_usage(None)

        assert pt is None
        assert ct is None

    def test_extract_empty_usage_dict(self):
        """Returns (None, None) when usage dict is empty."""
        response_body = {"usage": {}}

        pt, ct = extract_token_usage(response_body)

        assert pt is None
        assert ct is None

    def test_total_tokens_not_returned(self):
        """Confirms total_tokens is intentionally not returned (it is derivable)."""
        response_body = {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}

        result = extract_token_usage(response_body)

        # Result is a 2-tuple; total_tokens must not be present
        assert len(result) == 2


class TestPublishMetricsEventTokenPaths:
    """Tests covering JWT token-only publish path and token extraction from response_body."""

    def test_jwt_user_with_tokens_publishes_token_only_event(self, mock_env_vars, mock_request):
        """JWT/UI user with token counts publishes eventType='token_only' with empty messages.

        Expected: SQS message has eventType='token_only', messages=[], and token fields set.
        """
        mock_env_vars["USAGE_METRICS_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789/metrics"
        params = {"messages": [{"role": "user", "content": "Hello"}], "model": "my-model"}
        mock_sqs = MagicMock()

        with patch.dict("os.environ", mock_env_vars), patch("utils.metrics.sqs_client", mock_sqs), patch(
            "utils.metrics.get_user_context", return_value=("jwt-user", ["users"])
        ), patch("utils.metrics.is_api_user", return_value=False):

            publish_metrics_event(mock_request, params, 200, prompt_tokens=50, completion_tokens=20)

            mock_sqs.send_message.assert_called_once()
            body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])

            assert body["eventType"] == "token_only"
            assert body["messages"] == []
            assert body["sessionId"].startswith("ui-tokens-")
            assert body["promptTokens"] == 50
            assert body["completionTokens"] == 20

    def test_jwt_user_without_tokens_skips_publish(self, mock_env_vars, mock_request):
        """JWT/UI user with no token counts must not publish anything (no point — session lambda owns prompts).

        Expected: SQS send_message is never called.
        """
        mock_env_vars["USAGE_METRICS_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789/metrics"
        params = {"messages": [{"role": "user", "content": "Hello"}]}
        mock_sqs = MagicMock()

        with patch.dict("os.environ", mock_env_vars), patch("utils.metrics.sqs_client", mock_sqs), patch(
            "utils.metrics.get_user_context", return_value=("jwt-user", ["users"])
        ), patch("utils.metrics.is_api_user", return_value=False):

            publish_metrics_event(mock_request, params, 200)  # no tokens passed

            mock_sqs.send_message.assert_not_called()

    def test_tokens_extracted_from_response_body_for_non_streaming(self, mock_env_vars, mock_request):
        """When response_body is provided and prompt_tokens is not passed directly, tokens should be extracted from the
        response body before publishing.

        Expected: Published message contains promptTokens/completionTokens from the response body.
        """
        mock_env_vars["USAGE_METRICS_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789/metrics"
        params = {"messages": [{"role": "user", "content": "Hello"}]}
        response_body = {
            "choices": [],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
        }
        mock_sqs = MagicMock()

        with patch.dict("os.environ", mock_env_vars), patch("utils.metrics.sqs_client", mock_sqs), patch(
            "utils.metrics.get_user_context", return_value=("api-user", [])
        ), patch("utils.metrics.is_api_user", return_value=True):

            publish_metrics_event(mock_request, params, 200, response_body=response_body)

            body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])
            assert body["promptTokens"] == 30
            assert body["completionTokens"] == 10

    def test_api_user_publishes_full_event_type(self, mock_env_vars, mock_request):
        """API token users should publish eventType='full' with message list populated.

        Expected: eventType='full', messages list non-empty, sessionId starts with 'api-'.
        """
        mock_env_vars["USAGE_METRICS_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789/metrics"
        params = {"messages": [{"role": "user", "content": "Hello"}]}
        mock_sqs = MagicMock()

        with patch.dict("os.environ", mock_env_vars), patch("utils.metrics.sqs_client", mock_sqs), patch(
            "utils.metrics.get_user_context", return_value=("api-user", [])
        ), patch("utils.metrics.is_api_user", return_value=True):

            publish_metrics_event(mock_request, params, 200)

            body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])
            assert body["eventType"] == "full"
            assert len(body["messages"]) == 1
            assert body["sessionId"].startswith("api-")
