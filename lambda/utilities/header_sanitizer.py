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

"""Utility for sanitizing HTTP headers before logging to prevent log injection attacks."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Whitelist of headers that are safe and useful to log
# This prevents log injection attacks by only logging known, trusted headers
ALLOWED_HEADERS = {
    "accept",
    "accept-encoding",
    "accept-language",
    "content-type",
    "content-length",
    "host",
    "user-agent",
    "referer",
    "origin",
    # Note: authorization is handled separately and redacted
}

# Headers that need server-controlled values for security
# These will be replaced with values from API Gateway context
HEADERS_WITH_SERVER_VALUES = {
    "x-forwarded-for": lambda event: event.get("requestContext", {}).get("identity", {}).get("sourceIp", "unknown"),
    "x-forwarded-host": lambda event: event.get("requestContext", {}).get("domainName", "unknown"),
    "x-forwarded-proto": lambda event: "https",  # API Gateway always uses HTTPS
}


def sanitize_headers(headers: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize HTTP headers using a whitelist approach.

    Only headers in the ALLOWED_HEADERS set are logged. This prevents log injection
    attacks by rejecting any unexpected or potentially malicious headers.

    Security-critical headers like x-forwarded-for are replaced with server-controlled
    values from API Gateway to prevent IP spoofing in logs.

    Args:
        headers: Original HTTP headers from the request
        event: Lambda event from API Gateway (used to extract real values)

    Returns:
        Dictionary containing only whitelisted headers with sanitized values

    Example:
        >>> headers = {
        ...     "accept": "application/json",
        ...     "x-amzn-actiontrace": "injected-value",
        ...     "x-forwarded-for": "1.2.3.4"
        ... }
        >>> event = {"requestContext": {"identity": {"sourceIp": "9.10.11.12"}}}
        >>> sanitized = sanitize_headers(headers, event)
        >>> sanitized
        {"accept": "application/json", "x-forwarded-for": "9.10.11.12"}
    """
    if not headers:
        return {}

    sanitized = {}

    # Process each header
    for key, value in headers.items():
        key_lower = key.lower()

        # Check if this header should have a server-controlled value
        if key_lower in HEADERS_WITH_SERVER_VALUES:
            server_value = HEADERS_WITH_SERVER_VALUES[key_lower](event)
            sanitized[key_lower] = server_value

            # Log when we replace a user-provided value
            if value != server_value:
                logger.debug(f"Replaced header {key_lower}: user_value={value}, server_value={server_value}")

        # Check if this header is in the whitelist
        elif key_lower in ALLOWED_HEADERS:
            sanitized[key_lower] = value

        # All other headers are silently dropped (not logged)
        else:
            logger.debug(f"Dropped non-whitelisted header: {key_lower}")

    return sanitized


def get_sanitized_headers_for_logging(event: dict[str, Any]) -> dict[str, Any]:
    """
    Extract and sanitize headers from Lambda event for safe logging.

    This is a convenience function that extracts headers from the event
    and sanitizes them in one step.

    Args:
        event: Lambda event from API Gateway

    Returns:
        Dictionary of sanitized headers safe for logging

    Example:
        >>> event = {
        ...     "headers": {"x-forwarded-for": "1.2.3.4"},
        ...     "requestContext": {"identity": {"sourceIp": "5.6.7.8"}}
        ... }
        >>> headers = get_sanitized_headers_for_logging(event)
        >>> headers["x-forwarded-for"]
        "5.6.7.8"
    """
    headers = event.get("headers", {})
    return sanitize_headers(headers, event)
