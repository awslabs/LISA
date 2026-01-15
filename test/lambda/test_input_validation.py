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

"""Unit tests for input validation decorator."""

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from utilities.input_validation import contains_null_bytes, validate_input


class TestContainsNullBytes:
    """Test null byte detection function."""

    def test_no_null_bytes(self):
        """Test string without null bytes."""
        assert not contains_null_bytes("normal string")
        assert not contains_null_bytes("string with special chars: !@#$%^&*()")
        assert not contains_null_bytes("")

    def test_with_null_bytes(self):
        """Test string with null bytes."""
        assert contains_null_bytes("string\x00with null")
        assert contains_null_bytes("\x00at start")
        assert contains_null_bytes("at end\x00")
        assert contains_null_bytes("\x00")


class TestValidateInputDecorator:
    """Test input validation decorator."""

    @pytest.fixture
    def mock_context(self):
        """Create mock Lambda context."""
        context = MagicMock()
        context.function_name = "test-function"
        context.aws_request_id = "test-request-id"
        return context

    @pytest.fixture
    def valid_event(self):
        """Create valid Lambda event."""
        return {
            "httpMethod": "GET",
            "path": "/test/path",
            "queryStringParameters": {"param1": "value1"},
            "body": None,
            "headers": {"content-type": "application/json"},
        }

    def test_valid_request_passes(self, valid_event, mock_context):
        """Test that valid request passes validation."""

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["success"] is True

    def test_invalid_http_method(self, valid_event, mock_context):
        """Test that invalid HTTP method returns 405."""
        valid_event["httpMethod"] = "TRACE"

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["statusCode"] == 405
        body = json.loads(result["body"])
        assert body["error"] == "Method Not Allowed"
        assert "TRACE" in body["message"]

    def test_oversized_request_body(self, valid_event, mock_context):
        """Test that oversized request body returns 413."""
        # Create body larger than 1MB
        large_body = "x" * (1024 * 1024 + 1)
        valid_event["body"] = large_body

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["statusCode"] == 413
        body = json.loads(result["body"])
        assert body["error"] == "Payload Too Large"

    def test_custom_max_request_size(self, valid_event, mock_context):
        """Test custom max request size limit."""
        # Create body larger than custom limit (100 bytes)
        valid_event["body"] = "x" * 101

        @validate_input(max_request_size=100)
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["statusCode"] == 413

    def test_null_byte_in_path(self, valid_event, mock_context):
        """Test that null byte in path returns 400."""
        valid_event["path"] = "/test\x00/path"

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "Bad Request"
        assert "path" in body["message"]

    def test_null_byte_in_query_param_key(self, valid_event, mock_context):
        """Test that null byte in query parameter key returns 400."""
        valid_event["queryStringParameters"] = {"param\x00": "value"}

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "Bad Request"
        assert "query parameters" in body["message"]

    def test_null_byte_in_query_param_value(self, valid_event, mock_context):
        """Test that null byte in query parameter value returns 400."""
        valid_event["queryStringParameters"] = {"param": "value\x00"}

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "Bad Request"
        assert "query parameters" in body["message"]

    def test_null_byte_in_request_body(self, valid_event, mock_context):
        """Test that null byte in request body returns 400."""
        valid_event["httpMethod"] = "POST"
        valid_event["body"] = '{"key": "value\x00"}'

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "Bad Request"
        assert "request body" in body["message"]

    def test_empty_query_parameters(self, valid_event, mock_context):
        """Test that None query parameters are handled correctly."""
        valid_event["queryStringParameters"] = None

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["success"] is True

    def test_empty_body(self, valid_event, mock_context):
        """Test that empty body is handled correctly."""
        valid_event["body"] = ""

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["success"] is True

    def test_post_request_with_valid_body(self, valid_event, mock_context):
        """Test POST request with valid body passes validation."""
        valid_event["httpMethod"] = "POST"
        valid_event["body"] = '{"key": "value"}'

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["success"] is True

    def test_all_valid_http_methods(self, valid_event, mock_context):
        """Test that all valid HTTP methods are accepted."""
        valid_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

        for method in valid_methods:
            valid_event["httpMethod"] = method

            @validate_input()
            def handler(event, context):
                return {"success": True}

            result = handler(valid_event, mock_context)
            assert result["success"] is True, f"Method {method} should be valid"

    def test_special_characters_allowed(self, valid_event, mock_context):
        """Test that legitimate special characters are allowed."""
        valid_event["path"] = "/test/path-with_special.chars"
        valid_event["queryStringParameters"] = {
            "param": "value-with_special.chars!@#$%"
        }

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["success"] is True

    def test_unicode_characters_allowed(self, valid_event, mock_context):
        """Test that unicode characters are allowed."""
        valid_event["queryStringParameters"] = {"param": "value with émojis 🎉"}

        @validate_input()
        def handler(event, context):
            return {"success": True}

        result = handler(valid_event, mock_context)
        assert result["success"] is True
