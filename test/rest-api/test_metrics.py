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

from utils.metrics import extract_messages_for_metrics, publish_metrics_event


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
        ):

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
        ):

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
        ):

            publish_metrics_event(mock_request, params, 200)

            call_args = mock_sqs.send_message.call_args
            message_body = json.loads(call_args[1]["MessageBody"])

            assert len(message_body["messages"]) == 2
            assert "toolCalls" in message_body["messages"][1]
