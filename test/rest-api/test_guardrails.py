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

"""Unit tests for REST API guardrails utilities."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add REST API src to path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))

from utils.guardrails import (
    create_guardrail_json_response,
    create_guardrail_streaming_response,
    extract_guardrail_response,
    get_applicable_guardrails,
    get_model_guardrails,
    is_guardrail_violation,
)


class TestGetModelGuardrails:
    """Test suite for get_model_guardrails function."""

    @pytest.mark.asyncio
    async def test_get_guardrails_success(self, mock_env_vars):
        """Test successful retrieval of model guardrails."""
        mock_guardrails = [
            {
                "guardrailName": "content-filter",
                "modelId": "test-model",
                "allowedGroups": ["users"],
            },
            {
                "guardrailName": "pii-filter",
                "modelId": "test-model",
                "allowedGroups": [],
            },
        ]

        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": mock_guardrails}

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch.dict("os.environ", mock_env_vars), patch("boto3.resource", return_value=mock_dynamodb):

            result = await get_model_guardrails("test-model")

            assert result == mock_guardrails
            mock_table.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_guardrails_empty(self, mock_env_vars):
        """Test retrieval when no guardrails exist."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch.dict("os.environ", mock_env_vars), patch("boto3.resource", return_value=mock_dynamodb):

            result = await get_model_guardrails("test-model")

            assert result == []

    @pytest.mark.asyncio
    async def test_get_guardrails_error(self, mock_env_vars):
        """Test error handling during guardrail retrieval."""
        mock_table = MagicMock()
        mock_table.query.side_effect = Exception("DynamoDB error")

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch.dict("os.environ", mock_env_vars), patch("boto3.resource", return_value=mock_dynamodb):

            result = await get_model_guardrails("test-model")

            assert result == []


class TestGetApplicableGuardrails:
    """Test suite for get_applicable_guardrails function."""

    def test_public_guardrail_applies_to_all(self):
        """Test that public guardrails (no allowed_groups) apply to all users."""
        user_groups = ["users"]
        guardrails = [
            {
                "guardrailName": "public-filter",
                "allowedGroups": [],
                "markedForDeletion": False,
            }
        ]

        result = get_applicable_guardrails(user_groups, guardrails, "test-model")

        assert result == ["public-filter-test-model"]

    def test_group_specific_guardrail_applies(self):
        """Test that group-specific guardrails apply to matching users."""
        user_groups = ["admin", "users"]
        guardrails = [
            {
                "guardrailName": "admin-filter",
                "allowedGroups": ["admin"],
                "markedForDeletion": False,
            }
        ]

        result = get_applicable_guardrails(user_groups, guardrails, "test-model")

        assert result == ["admin-filter-test-model"]

    def test_group_specific_guardrail_does_not_apply(self):
        """Test that group-specific guardrails don't apply to non-matching users."""
        user_groups = ["users"]
        guardrails = [
            {
                "guardrailName": "admin-filter",
                "allowedGroups": ["admin"],
                "markedForDeletion": False,
            }
        ]

        result = get_applicable_guardrails(user_groups, guardrails, "test-model")

        assert result == []

    def test_multiple_guardrails_mixed(self):
        """Test multiple guardrails with mixed applicability."""
        user_groups = ["users", "developers"]
        guardrails = [
            {
                "guardrailName": "public-filter",
                "allowedGroups": [],
                "markedForDeletion": False,
            },
            {
                "guardrailName": "dev-filter",
                "allowedGroups": ["developers"],
                "markedForDeletion": False,
            },
            {
                "guardrailName": "admin-filter",
                "allowedGroups": ["admin"],
                "markedForDeletion": False,
            },
        ]

        result = get_applicable_guardrails(user_groups, guardrails, "test-model")

        assert len(result) == 2
        assert "public-filter-test-model" in result
        assert "dev-filter-test-model" in result
        assert "admin-filter-test-model" not in result

    def test_marked_for_deletion_excluded(self):
        """Test that guardrails marked for deletion are excluded."""
        user_groups = ["users"]
        guardrails = [
            {
                "guardrailName": "active-filter",
                "allowedGroups": [],
                "markedForDeletion": False,
            },
            {
                "guardrailName": "deleted-filter",
                "allowedGroups": [],
                "markedForDeletion": True,
            },
        ]

        result = get_applicable_guardrails(user_groups, guardrails, "test-model")

        assert result == ["active-filter-test-model"]

    def test_missing_guardrail_name(self):
        """Test handling of guardrails without guardrailName."""
        user_groups = ["users"]
        guardrails = [
            {
                "allowedGroups": [],
                "markedForDeletion": False,
            }
        ]

        result = get_applicable_guardrails(user_groups, guardrails, "test-model")

        assert result == []

    def test_empty_user_groups(self):
        """Test with user having no groups."""
        user_groups = []
        guardrails = [
            {
                "guardrailName": "public-filter",
                "allowedGroups": [],
                "markedForDeletion": False,
            },
            {
                "guardrailName": "group-filter",
                "allowedGroups": ["users"],
                "markedForDeletion": False,
            },
        ]

        result = get_applicable_guardrails(user_groups, guardrails, "test-model")

        # Only public guardrail should apply
        assert result == ["public-filter-test-model"]


class TestIsGuardrailViolation:
    """Test suite for is_guardrail_violation function."""

    def test_is_violation_true(self):
        """Test detection of guardrail violation message."""
        error_msg = "Violated guardrail policy: content filter triggered"
        assert is_guardrail_violation(error_msg) is True

    def test_is_violation_false(self):
        """Test non-violation error message."""
        error_msg = "Model not found"
        assert is_guardrail_violation(error_msg) is False

    def test_is_violation_empty_string(self):
        """Test with empty error message."""
        assert is_guardrail_violation("") is False


class TestExtractGuardrailResponse:
    """Test suite for extract_guardrail_response function."""

    def test_extract_response_success(self):
        """Test successful extraction of guardrail response."""
        error_msg = "Error: 'bedrock_guardrail_response': 'Content blocked due to policy violation'"
        result = extract_guardrail_response(error_msg)
        assert result == "Content blocked due to policy violation"

    def test_extract_response_not_found(self):
        """Test extraction when response not in message."""
        error_msg = "Some other error message"
        result = extract_guardrail_response(error_msg)
        assert result is None

    def test_extract_response_empty_string(self):
        """Test extraction with empty error message."""
        result = extract_guardrail_response("")
        assert result is None

    def test_extract_response_complex_message(self):
        """Test extraction from complex error message."""
        error_msg = (
            "LiteLLM error: Violated guardrail policy. "
            "'bedrock_guardrail_response': 'I cannot assist with that request' "
            "Additional context here"
        )
        result = extract_guardrail_response(error_msg)
        assert result == "I cannot assist with that request"


class TestCreateGuardrailStreamingResponse:
    """Test suite for create_guardrail_streaming_response function."""

    def test_streaming_response_format(self):
        """Test format of streaming guardrail response."""
        guardrail_response = "Content blocked"
        model_id = "test-model"
        created = 1234567890

        chunks = list(create_guardrail_streaming_response(guardrail_response, model_id, created))

        assert len(chunks) == 3

        # First chunk with content
        first_chunk = json.loads(chunks[0].replace("data: ", "").strip())
        assert first_chunk["model"] == model_id
        assert first_chunk["created"] == created
        assert first_chunk["choices"][0]["delta"]["content"] == guardrail_response
        assert first_chunk["lisa_guardrail_triggered"] is True

        # Second chunk with finish_reason
        second_chunk = json.loads(chunks[1].replace("data: ", "").strip())
        assert second_chunk["choices"][0]["finish_reason"] == "stop"

        # Final [DONE] marker
        assert chunks[2] == "data: [DONE]\n\n"

    def test_streaming_response_default_created(self):
        """Test streaming response with default created timestamp."""
        chunks = list(create_guardrail_streaming_response("Blocked", "model", 0))

        first_chunk = json.loads(chunks[0].replace("data: ", "").strip())
        assert first_chunk["created"] == 0


class TestCreateGuardrailJsonResponse:
    """Test suite for create_guardrail_json_response function."""

    def test_json_response_format(self):
        """Test format of JSON guardrail response."""
        guardrail_response = "Content blocked"
        model_id = "test-model"
        created = 1234567890

        response = create_guardrail_json_response(guardrail_response, model_id, created)

        assert response.status_code == 200
        response_data = json.loads(response.body)

        assert response_data["model"] == model_id
        assert response_data["created"] == created
        assert response_data["choices"][0]["message"]["content"] == guardrail_response
        assert response_data["choices"][0]["finish_reason"] == "stop"
        assert response_data["lisa_guardrail_triggered"] is True
        assert response_data["usage"]["total_tokens"] == 0

    def test_json_response_default_created(self):
        """Test JSON response with default created timestamp."""
        response = create_guardrail_json_response("Blocked", "model", 0)
        response_data = json.loads(response.body)

        assert response_data["created"] == 0

    def test_json_response_structure(self):
        """Test complete structure of JSON response."""
        response = create_guardrail_json_response("Test response", "test-model", 123)
        response_data = json.loads(response.body)

        # Check all required fields
        assert "id" in response_data
        assert "object" in response_data
        assert "created" in response_data
        assert "model" in response_data
        assert "choices" in response_data
        assert "usage" in response_data
        assert "lisa_guardrail_triggered" in response_data

        # Check choices structure
        assert len(response_data["choices"]) == 1
        choice = response_data["choices"][0]
        assert "index" in choice
        assert "message" in choice
        assert "finish_reason" in choice

        # Check message structure
        message = choice["message"]
        assert message["role"] == "assistant"
        assert message["content"] == "Test response"
