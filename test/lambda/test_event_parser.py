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

"""Unit tests for event_parser module."""

import json

import pytest
<<<<<<< HEAD
<<<<<<< HEAD
=======

>>>>>>> 4e53cd7f (Added input validation, security headers, and logging to FastAPI lambdas and apiWrappers)
=======
>>>>>>> 5bc884ee (pre)
from utilities.event_parser import (
    get_bearer_token,
    get_id_token,
    get_principal_id,
    get_session_id,
    sanitize_event_for_logging,
)


class TestSanitizeEventForLogging:
    """Test sanitize_event_for_logging function."""

    def test_redacts_authorization_header(self):
        """Test sanitize_event_for_logging redacts authorization header."""
        event = {"headers": {"Authorization": "Bearer secret-token-123"}, "path": "/test"}

        sanitized = sanitize_event_for_logging(event)
        parsed = json.loads(sanitized)

        assert parsed["headers"]["authorization"] == "<REDACTED>"
        assert "secret-token-123" not in sanitized

    def test_normalizes_header_keys(self):
        """Test sanitize_event_for_logging normalizes header keys to lowercase."""
        event = {"headers": {"Content-Type": "application/json", "X-Custom-Header": "value"}, "path": "/test"}

        sanitized = sanitize_event_for_logging(event)
        parsed = json.loads(sanitized)

        assert "content-type" in parsed["headers"]
        assert "x-custom-header" in parsed["headers"]
        assert "Content-Type" not in parsed["headers"]

    def test_handles_multi_value_headers(self):
        """Test sanitize_event_for_logging handles multiValueHeaders."""
        event = {
            "headers": {"authorization": "Bearer token"},
            "multiValueHeaders": {"Authorization": ["Bearer token"], "Accept": ["application/json", "text/html"]},
            "path": "/test",
        }

        sanitized = sanitize_event_for_logging(event)
        parsed = json.loads(sanitized)

        assert parsed["multiValueHeaders"]["authorization"] == ["<REDACTED>"]
        assert "accept" in parsed["multiValueHeaders"]

    def test_preserves_other_fields(self):
        """Test sanitize_event_for_logging preserves non-header fields."""
        event = {
            "headers": {"content-type": "application/json"},
            "path": "/users/123",
            "httpMethod": "GET",
            "queryStringParameters": {"filter": "active"},
        }

        sanitized = sanitize_event_for_logging(event)
        parsed = json.loads(sanitized)

        assert parsed["path"] == "/users/123"
        assert parsed["httpMethod"] == "GET"
        assert parsed["queryStringParameters"]["filter"] == "active"

    def test_does_not_modify_original_event(self):
        """Test sanitize_event_for_logging does not modify original event."""
        event = {"headers": {"Authorization": "Bearer token"}, "path": "/test"}
        original_auth = event["headers"]["Authorization"]

        sanitize_event_for_logging(event)

        assert event["headers"]["Authorization"] == original_auth


class TestGetSessionId:
    """Test get_session_id function."""

    def test_extracts_session_id(self):
        """Test get_session_id extracts session ID from path parameters."""
        event = {"pathParameters": {"sessionId": "session-abc-123"}}

        session_id = get_session_id(event)

        assert session_id == "session-abc-123"

    def test_returns_none_when_missing(self):
        """Test get_session_id returns None when session ID is missing."""
        event = {"pathParameters": {}}

        session_id = get_session_id(event)

        assert session_id is None

    def test_handles_missing_path_parameters(self):
        """Test get_session_id handles missing pathParameters."""
        event = {}

        session_id = get_session_id(event)

        assert session_id is None


class TestGetPrincipalId:
    """Test get_principal_id function."""

    def test_extracts_principal_id(self):
        """Test get_principal_id extracts principal from authorizer context."""
        event = {"requestContext": {"authorizer": {"principal": "user-123"}}}

        principal = get_principal_id(event)

        assert principal == "user-123"

    def test_returns_empty_string_when_missing(self):
        """Test get_principal_id returns empty string when principal is missing."""
        event = {"requestContext": {"authorizer": {}}}

        principal = get_principal_id(event)

        assert principal == ""

    def test_handles_missing_request_context(self):
        """Test get_principal_id handles missing requestContext."""
        event = {}

        principal = get_principal_id(event)

        assert principal == ""


class TestGetBearerToken:
    """Test get_bearer_token function."""

    def test_extracts_token_uppercase_authorization(self):
        """Test get_bearer_token extracts token from uppercase Authorization header."""
        event = {"headers": {"Authorization": "Bearer test-token-123"}}

        token = get_bearer_token(event)

        assert token == "test-token-123"

    def test_extracts_token_lowercase_authorization(self):
        """Test get_bearer_token extracts token from lowercase authorization header."""
        event = {"headers": {"authorization": "Bearer test-token-456"}}

        token = get_bearer_token(event)

        assert token == "test-token-456"

    def test_returns_none_when_missing(self):
        """Test get_bearer_token returns None when header is missing."""
        event = {"headers": {}}

        token = get_bearer_token(event)

        assert token is None

    def test_returns_none_for_non_bearer(self):
        """Test get_bearer_token returns None for non-Bearer auth."""
        event = {"headers": {"Authorization": "Basic dXNlcjpwYXNz"}}

        token = get_bearer_token(event)

        assert token is None

    def test_handles_missing_headers(self):
        """Test get_bearer_token handles missing headers."""
        event = {}

        token = get_bearer_token(event)

        assert token is None

    def test_strips_whitespace(self):
        """Test get_bearer_token strips whitespace from token."""
        event = {"headers": {"Authorization": "Bearer  token-with-spaces  "}}

        token = get_bearer_token(event)

        assert token == "token-with-spaces"


class TestGetIdToken:
    """Test get_id_token function."""

    def test_extracts_token_lowercase_authorization(self):
        """Test get_id_token extracts token from lowercase authorization header."""
        event = {"headers": {"authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}}

        token = get_id_token(event)

        assert token == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"

    def test_extracts_token_uppercase_authorization(self):
        """Test get_id_token extracts token from uppercase Authorization header."""
        event = {"headers": {"Authorization": "Bearer eyJzdWIiOiIxMjM0NTY3ODkwIn0"}}

        token = get_id_token(event)

        assert token == "eyJzdWIiOiIxMjM0NTY3ODkwIn0"

    def test_handles_lowercase_bearer(self):
        """Test get_id_token handles lowercase bearer prefix."""
        event = {"headers": {"authorization": "bearer test-token"}}

        token = get_id_token(event)

        assert token == "test-token"

    def test_raises_error_when_missing(self):
        """Test get_id_token raises ValueError when header is missing."""
        event = {"headers": {}}

        with pytest.raises(ValueError, match="Missing authorization token"):
            get_id_token(event)

    def test_strips_whitespace(self):
        """Test get_id_token strips whitespace from token."""
        event = {"headers": {"Authorization": "Bearer  token-123  "}}

        token = get_id_token(event)

        assert token == "token-123"
