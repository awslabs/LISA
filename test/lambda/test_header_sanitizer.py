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

"""Unit tests for header_sanitizer module."""

import pytest
from utilities.header_sanitizer import (
    get_sanitized_headers_for_logging,
    sanitize_headers,
)


@pytest.fixture
def mock_event():
    """Create a mock API Gateway event."""
    return {
        "requestContext": {
            "identity": {"sourceIp": "203.0.113.42"},
            "domainName": "api.example.com",
            "stage": "prod",
            "requestId": "test-request-123",
        }
    }


class TestSanitizeHeaders:
    """Test sanitize_headers function."""

    def test_only_logs_allowlisted_headers(self, mock_event):
        """Test that only allowlisted headers are included in output."""
        headers = {
            "accept": "application/json",
            "x-amzn-actiontrace": "vof-test-injected-header-1770159407",
            "x-amzn-actiontrace-caller": "malicious-caller",
            "x-custom-malicious-header": "malicious-value",
            "user-agent": "curl/8.7.1",
            "content-type": "application/json",
        }

        result = sanitize_headers(headers, mock_event)

        # Only allowlisted headers should be present
        assert result["accept"] == "application/json"
        assert result["user-agent"] == "curl/8.7.1"
        assert result["content-type"] == "application/json"

        # Non-allowlisted headers should be removed
        assert "x-amzn-actiontrace" not in result
        assert "x-amzn-actiontrace-caller" not in result
        assert "x-custom-malicious-header" not in result

    def test_drops_all_non_allowlisted_headers(self, mock_event):
        """Test that all non-allowlisted headers are dropped."""
        headers = {
            "X-Amzn-ActionTrace": "injected-value",
            "X-AMZN-ACTIONTRACE-CALLER": "injected-caller",
            "X-Custom-Header": "custom-value",
            "X-Forwarded-Server": "malicious-server",
        }

        result = sanitize_headers(headers, mock_event)

        # No non-allowlisted headers should be present
        assert len(result) == 0

    def test_replaces_x_forwarded_for_with_real_ip(self, mock_event):
        """Test that x-forwarded-for is replaced with real client IP."""
        headers = {
            "x-forwarded-for": "1.2.3.4, 5.6.7.8",
            "accept": "application/json",
        }

        result = sanitize_headers(headers, mock_event)

        assert result["x-forwarded-for"] == "203.0.113.42"
        assert result["accept"] == "application/json"

    def test_replaces_x_forwarded_host_with_domain_name(self, mock_event):
        """Test that x-forwarded-host is replaced with API Gateway domain."""
        headers = {
            "x-forwarded-host": "malicious.example.com",
            "accept": "application/json",
        }

        result = sanitize_headers(headers, mock_event)

        assert result["x-forwarded-host"] == "api.example.com"
        assert result["accept"] == "application/json"

    def test_replaces_x_forwarded_proto_with_https(self, mock_event):
        """Test that x-forwarded-proto is replaced with https."""
        headers = {
            "x-forwarded-proto": "http",
            "accept": "application/json",
        }

        result = sanitize_headers(headers, mock_event)

        assert result["x-forwarded-proto"] == "https"
        assert result["accept"] == "application/json"

    def test_handles_empty_headers(self, mock_event):
        """Test that empty headers dict is handled correctly."""
        result = sanitize_headers({}, mock_event)
        assert result == {}

    def test_handles_none_headers(self, mock_event):
        """Test that None headers is handled correctly."""
        result = sanitize_headers(None, mock_event)
        assert result == {}

    def test_preserves_safe_headers(self, mock_event):
        """Test that allowlisted headers are preserved."""
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "curl/8.7.1",
            "host": "api.example.com",
            "accept-encoding": "gzip, deflate",
        }

        result = sanitize_headers(headers, mock_event)

        assert result["accept"] == "application/json"
        assert result["content-type"] == "application/json"
        assert result["user-agent"] == "curl/8.7.1"
        assert result["host"] == "api.example.com"
        assert result["accept-encoding"] == "gzip, deflate"

    def test_combined_sanitization(self, mock_event):
        """Test sanitization with mix of allowlisted, server-controlled, and malicious headers."""
        headers = {
            "accept": "application/json",
            "x-forwarded-for": "1.2.3.4",
            "x-amzn-actiontrace": "injected-trace",
            "x-amzn-actiontrace-caller": "injected-caller",
            "user-agent": "curl/8.7.1",
            "x-forwarded-host": "malicious.com",
            "x-custom-header": "should-be-dropped",
        }

        result = sanitize_headers(headers, mock_event)

        # allowlisted headers preserved
        assert result["accept"] == "application/json"
        assert result["user-agent"] == "curl/8.7.1"

        # Server-controlled headers replaced
        assert result["x-forwarded-for"] == "203.0.113.42"
        assert result["x-forwarded-host"] == "api.example.com"

        # Non-allowlisted headers dropped
        assert "x-amzn-actiontrace" not in result
        assert "x-amzn-actiontrace-caller" not in result
        assert "x-custom-header" not in result


class TestGetSanitizedHeadersForLogging:
    """Test get_sanitized_headers_for_logging function."""

    def test_extracts_and_sanitizes_headers(self, mock_event):
        """Test that headers are extracted from event and sanitized."""
        event = {
            **mock_event,
            "headers": {
                "accept": "application/json",
                "x-amzn-actiontrace": "injected-value",
                "x-forwarded-for": "1.2.3.4",
                "x-malicious-header": "bad-value",
            },
        }

        result = get_sanitized_headers_for_logging(event)

        # allowlisted header preserved
        assert result["accept"] == "application/json"

        # Server-controlled header replaced
        assert result["x-forwarded-for"] == "203.0.113.42"

        # Non-allowlisted headers dropped
        assert "x-amzn-actiontrace" not in result
        assert "x-malicious-header" not in result

    def test_handles_missing_headers(self, mock_event):
        """Test that missing headers key is handled correctly."""
        result = get_sanitized_headers_for_logging(mock_event)
        assert result == {}

    def test_handles_empty_headers(self, mock_event):
        """Test that empty headers dict is handled correctly."""
        event = {**mock_event, "headers": {}}
        result = get_sanitized_headers_for_logging(event)
        assert result == {}
