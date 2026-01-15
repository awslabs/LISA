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
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Security-critical headers that should be replaced with server-controlled values
SECURITY_CRITICAL_HEADERS = {
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-server",
    "x-amzn-client-id",
    "x-real-ip",
    "forwarded",
}


def get_real_client_ip(event: Dict[str, Any]) -> str:
    """
    Extract the real client IP address from API Gateway event context.

    This function retrieves the actual source IP from the API Gateway request context,
    which cannot be spoofed by the client. User-provided headers like x-forwarded-for
    should never be trusted for security-critical operations.

    Args:
        event: Lambda event from API Gateway containing requestContext

    Returns:
        Real client IP address from API Gateway, or "unknown" if not available
    """
    try:
        # API Gateway provides the real source IP in requestContext.identity.sourceIp
        # This value is set by AWS and cannot be manipulated by the client
        source_ip = event.get("requestContext", {}).get("identity", {}).get("sourceIp")
        if source_ip:
            return source_ip

        # Fallback: check if this is a direct Lambda invocation (testing)
        logger.warning("No sourceIp found in API Gateway event context")
        return "unknown"

    except Exception as e:
        logger.error(f"Error extracting real client IP: {e}")
        return "unknown"


def sanitize_headers(headers: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize HTTP headers by replacing user-controlled values with server-controlled values.

    This prevents attackers from manipulating security-critical headers in logs,
    which could be used to hide their true source IP or manipulate audit trails.

    Args:
        headers: Original HTTP headers from the request
        event: Lambda event from API Gateway (used to extract real values)

    Returns:
        Dictionary of sanitized headers with security-critical values replaced

    Example:
        >>> headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
        >>> event = {"requestContext": {"identity": {"sourceIp": "9.10.11.12"}}}
        >>> sanitized = sanitize_headers(headers, event)
        >>> sanitized["x-forwarded-for"]
        "9.10.11.12"
    """
    if not headers:
        return {}

    # Create a copy to avoid modifying the original
    sanitized = dict(headers)

    # Get the real client IP from API Gateway
    real_ip = get_real_client_ip(event)

    # Replace security-critical headers with server-controlled values
    for header_name in SECURITY_CRITICAL_HEADERS:
        # Check both lowercase and original case (HTTP headers are case-insensitive)
        header_lower = header_name.lower()

        # Find the actual header key (may have different casing)
        actual_key = None
        for key in sanitized.keys():
            if key.lower() == header_lower:
                actual_key = key
                break

        if actual_key:
            # Store original value for debugging (with clear marker)
            original_value = sanitized[actual_key]

            # Replace with server-controlled value
            if header_lower in ("x-forwarded-for", "x-real-ip"):
                sanitized[actual_key] = real_ip
            elif header_lower == "x-forwarded-host":
                # Use the actual Host header from API Gateway
                sanitized[actual_key] = event.get("requestContext", {}).get("domainName", "unknown")
            elif header_lower == "x-forwarded-server":
                # Use API Gateway stage
                sanitized[actual_key] = event.get("requestContext", {}).get("stage", "unknown")
            elif header_lower == "x-amzn-client-id":
                # Use the validated request ID from API Gateway
                sanitized[actual_key] = event.get("requestContext", {}).get("requestId", "unknown")
            elif header_lower == "forwarded":
                # Reconstruct Forwarded header with server values
                sanitized[actual_key] = f"for={real_ip}"

            # Log the sanitization for security monitoring
            if original_value != sanitized[actual_key]:
                logger.debug(
                    f"Sanitized header {actual_key}: original={original_value}, sanitized={sanitized[actual_key]}"
                )

    return sanitized


def get_sanitized_headers_for_logging(event: Dict[str, Any]) -> Dict[str, Any]:
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
