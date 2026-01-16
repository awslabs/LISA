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

"""Unit tests for lambda_decorators module."""

import json
from types import SimpleNamespace
<<<<<<< HEAD
<<<<<<< HEAD
from unittest.mock import patch

import pytest
=======
from unittest.mock import MagicMock, patch

import pytest

>>>>>>> 4e53cd7f (Added input validation, security headers, and logging to FastAPI lambdas and apiWrappers)
=======
from unittest.mock import patch

import pytest
>>>>>>> 5bc884ee (pre)
from utilities.lambda_decorators import api_wrapper, authorization_wrapper, ctx_context, get_lambda_context


class TestApiWrapper:
    """Test api_wrapper decorator."""

    def test_success_response(self):
        """Test api_wrapper with successful function execution."""

        @api_wrapper
        def test_function(event, context):
            return {"result": "success", "data": "test"}

        mock_context = SimpleNamespace(function_name="test-func", aws_request_id="req-123")
        event = {"headers": {}, "httpMethod": "GET", "path": "/test"}

        response = test_function(event, mock_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["result"] == "success"
        assert body["data"] == "test"
        assert "Strict-Transport-Security" in response["headers"]

    def test_exception_handling(self):
        """Test api_wrapper handles exceptions properly."""

        @api_wrapper
        def test_function(event, context):
            raise ValueError("Test error message")

        mock_context = SimpleNamespace(function_name="test-func", aws_request_id="req-123")
        event = {"headers": {}, "httpMethod": "GET", "path": "/test"}

        response = test_function(event, mock_context)

        assert response["statusCode"] == 500
        assert "An unexpected error occurred" in response["body"]

    def test_input_validation_null_bytes(self):
        """Test api_wrapper rejects null bytes in path."""

        @api_wrapper
        def test_function(event, context):
            return {"result": "success"}

        mock_context = SimpleNamespace(function_name="test-func", aws_request_id="req-123")
        event = {"headers": {}, "httpMethod": "GET", "path": "/test\x00/path"}

        response = test_function(event, mock_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid characters" in body["message"]

    def test_input_validation_invalid_method(self):
        """Test api_wrapper rejects invalid HTTP methods."""

        @api_wrapper
        def test_function(event, context):
            return {"result": "success"}

        mock_context = SimpleNamespace(function_name="test-func", aws_request_id="req-123")
        event = {"headers": {}, "httpMethod": "TRACE", "path": "/test"}

        response = test_function(event, mock_context)

        assert response["statusCode"] == 405
        body = json.loads(response["body"])
        assert "Method Not Allowed" in body["error"]

    def test_context_is_set(self):
        """Test api_wrapper sets Lambda context."""
<<<<<<< HEAD
<<<<<<< HEAD
=======
        from utilities.lambda_decorators import ctx_context
>>>>>>> 4e53cd7f (Added input validation, security headers, and logging to FastAPI lambdas and apiWrappers)
=======
>>>>>>> 5bc884ee (pre)

        @api_wrapper
        def test_function(event, context):
            # Access context from context variable
            current_context = ctx_context.get()
            return {"function_name": current_context.function_name}

        mock_context = SimpleNamespace(function_name="test-func-context", aws_request_id="req-456")
        event = {"headers": {}, "httpMethod": "GET", "path": "/test"}

        response = test_function(event, mock_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["function_name"] == "test-func-context"

    @patch("utilities.lambda_decorators.logger")
    def test_request_logging(self, mock_logger):
        """Test api_wrapper logs requests."""

        @api_wrapper
        def test_function(event, context):
            return {"result": "success"}

        mock_context = SimpleNamespace(function_name="test-func", aws_request_id="req-123")
        event = {"headers": {}, "httpMethod": "GET", "path": "/test"}

        test_function(event, mock_context)

        # Verify logging was called
        assert mock_logger.info.called


class TestAuthorizationWrapper:
    """Test authorization_wrapper decorator."""

    def test_passes_through_result(self):
        """Test authorization_wrapper passes through result unchanged."""

        @authorization_wrapper
        def test_function(event, context):
            return {"authorized": True, "principal": "user-123"}

        mock_context = SimpleNamespace(function_name="test-func", aws_request_id="req-123")
        event = {"authorizationToken": "Bearer token"}

        result = test_function(event, mock_context)

        assert result == {"authorized": True, "principal": "user-123"}

    def test_context_is_set(self):
        """Test authorization_wrapper sets Lambda context."""
<<<<<<< HEAD
<<<<<<< HEAD
=======
        from utilities.lambda_decorators import ctx_context
>>>>>>> 4e53cd7f (Added input validation, security headers, and logging to FastAPI lambdas and apiWrappers)
=======
>>>>>>> 5bc884ee (pre)

        @authorization_wrapper
        def test_function(event, context):
            current_context = ctx_context.get()
            return {"function_name": current_context.function_name}

        mock_context = SimpleNamespace(function_name="authorizer-func-test", aws_request_id="req-789")
        event = {"authorizationToken": "Bearer token"}

        result = test_function(event, mock_context)

        assert result["function_name"] == "authorizer-func-test"

    def test_exception_propagates(self):
        """Test authorization_wrapper allows exceptions to propagate."""

        @authorization_wrapper
        def test_function(event, context):
            raise ValueError("Authorization failed")

        mock_context = SimpleNamespace(function_name="authorizer-func", aws_request_id="req-456")
        event = {"authorizationToken": "Bearer token"}

        with pytest.raises(ValueError, match="Authorization failed"):
            test_function(event, mock_context)


class TestGetLambdaContext:
    """Test get_lambda_context function."""

    def test_get_context_when_set(self):
        """Test get_lambda_context returns context when set."""
<<<<<<< HEAD
<<<<<<< HEAD
=======
        from utilities.lambda_decorators import ctx_context
>>>>>>> 4e53cd7f (Added input validation, security headers, and logging to FastAPI lambdas and apiWrappers)
=======
>>>>>>> 5bc884ee (pre)

        mock_context = SimpleNamespace(function_name="get-context-test", aws_request_id="req-999")
        ctx_context.set(mock_context)

        context = get_lambda_context()

        assert context.function_name == "get-context-test"
        assert context.aws_request_id == "req-999"

    def test_get_context_when_not_set(self):
        """Test get_lambda_context raises error when context not set."""
        # Create a new context var to ensure it's not set
        from contextvars import ContextVar

        test_ctx = ContextVar("test_context")

        with pytest.raises(LookupError):
            test_ctx.get()
