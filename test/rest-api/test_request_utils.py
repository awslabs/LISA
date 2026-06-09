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

import pytest

# Add REST API src to path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))

from utils.request_utils import get_lisa_end_user_id, handle_stream_exceptions, strip_unsupported_model_params


class TestHandleStreamExceptions:
    """Test suite for handle_stream_exceptions decorator."""

    @pytest.mark.asyncio
    async def test_handle_stream_normal_operation(self):
        """Test decorator passes through normal stream items."""

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


class TestGetLisaEndUserId:
    """Test suite for get_lisa_end_user_id precedence and edge cases."""

    def test_precedence_cognito_username_over_username(self):
        jwt_data = {
            "username": "user_from_username",
            "cognito:username": "user_from_cognito",
            "sub": "user_from_sub",
        }
        assert get_lisa_end_user_id(jwt_data=jwt_data, state_username="state_user") == "user_from_cognito"

    def test_precedence_username_over_sub(self):
        jwt_data = {
            "username": "user_from_username",
            "cognito:username": None,
            "sub": "user_from_sub",
        }
        assert get_lisa_end_user_id(jwt_data=jwt_data, state_username="state_user") == "user_from_username"

    def test_precedence_sub_fallback(self):
        jwt_data = {
            "username": "",
            "cognito:username": "",
            "sub": "user_from_sub",
        }
        assert get_lisa_end_user_id(jwt_data=jwt_data, state_username="state_user") == "user_from_sub"

    def test_state_username_fallback_when_jwt_missing(self):
        assert get_lisa_end_user_id(jwt_data=None, state_username="state_user") == "state_user"

    def test_none_return_when_all_sources_empty_or_invalid(self):
        jwt_data = {
            "username": "",
            "cognito:username": "",
            "sub": "",
        }
        assert get_lisa_end_user_id(jwt_data=jwt_data, state_username="") is None

    def test_ignore_non_string_claims(self):
        jwt_data = {
            "username": 123,
            "cognito:username": {},
            "sub": ["not-a-string"],
        }
        assert get_lisa_end_user_id(jwt_data=jwt_data, state_username="state_user") == "state_user"


class TestStripUnsupportedModelParams:
    """Test suite for strip_unsupported_model_params."""

    def test_strips_top_p_for_claude_opus_4_7(self):
        params = {"top_p": 0.9, "temperature": 0.7}
        removed = strip_unsupported_model_params(params, "bedrock/us.anthropic.claude-opus-4-7-20260101-v1:0")
        assert removed == ["top_p"]
        assert params == {"temperature": 0.7}

    def test_strips_top_p_for_claude_opus_4_8(self):
        params = {"top_p": 0.9, "temperature": 0.7}
        removed = strip_unsupported_model_params(params, "bedrock/us.anthropic.claude-opus-4-8-20260601-v1:0")
        assert removed == ["top_p"]
        assert params == {"temperature": 0.7}

    def test_strips_top_p_for_claude_fable(self):
        params = {"top_p": 0.9, "temperature": 0.7}
        removed = strip_unsupported_model_params(params, "bedrock/us.anthropic.claude-fable-5-20260301-v1:0")
        assert removed == ["top_p"]
        assert params == {"temperature": 0.7}

    def test_strips_top_p_for_claude_fable_direct_anthropic(self):
        params = {"top_p": 0.9}
        removed = strip_unsupported_model_params(params, "anthropic/claude-fable-5")
        assert removed == ["top_p"]
        assert params == {}

    def test_leaves_params_for_non_matching_model(self):
        params = {"top_p": 0.9, "temperature": 0.7}
        removed = strip_unsupported_model_params(params, "bedrock/us.anthropic.claude-sonnet-4-6-20251001-v1:0")
        assert removed == []
        assert params == {"top_p": 0.9, "temperature": 0.7}

    def test_noop_when_model_name_missing(self):
        params = {"top_p": 0.9}
        assert strip_unsupported_model_params(params, None) == []
        assert strip_unsupported_model_params(params, "") == []
        assert params == {"top_p": 0.9}

    def test_noop_when_param_absent(self):
        params = {"temperature": 0.7}
        removed = strip_unsupported_model_params(params, "anthropic/claude-fable-5")
        assert removed == []
        assert params == {"temperature": 0.7}
