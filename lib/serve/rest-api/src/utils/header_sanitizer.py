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

"""Utility for sanitizing HTTP headers before logging to prevent log injection attacks.

This module is adapted for the serve API (ECS context) where we don't have
API Gateway event context. Instead, we extract real client IP from ECS/ALB headers.
"""

from fastapi import Request
from loguru import logger

# Security-critical headers that should be replaced with server-controlled values
SECURITY_CRITICAL_HEADERS = {
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-server",
    "x-amzn-client-id",
    "x-real-ip",
    "forwarded",
}


def get_real_client_ip(request: Request) -> str:
    """
    Extract the real client IP address from the request.

    In ECS behind ALB, the real client IP is typically in the last entry
    of x-forwarded-for added by the ALB, or we can use the client host.

    Args:
        request: FastAPI Request object

    Returns:
        Real client IP address, or "unknown" if not available
    """
    try:
        # In ECS behind ALB, the client IP is available from the request
        if request.client and request.client.host:
            return str(request.client.host)

        logger.warning("No client IP found in request")
        return "unknown"

    except Exception as e:
        logger.error(f"Error extracting real client IP: {e}")
        return "unknown"


def sanitize_headers_for_logging(
    headers: dict[str, str],
    real_client_ip: str | None = None,
) -> dict[str, str]:
    """
    Sanitize HTTP headers by replacing user-controlled values with server-controlled values.

    This prevents attackers from manipulating security-critical headers in logs,
    which could be used to hide their true source IP or manipulate audit trails.

    Args:
        headers: Original HTTP headers from the request
        real_client_ip: The real client IP (from request.client.host)

    Returns:
        Dictionary of sanitized headers with security-critical values replaced

    Example:
        >>> headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
        >>> sanitized = sanitize_headers_for_logging(headers, "9.10.11.12")
        >>> sanitized["x-forwarded-for"]
        "9.10.11.12"
    """
    if not headers:
        return {}

    # Create a copy to avoid modifying the original
    sanitized = dict(headers)

    # Use provided IP or default to unknown
    real_ip = real_client_ip or "unknown"

    # Track modifications for logging
    modifications: list[str] = []

    # Replace security-critical headers with server-controlled values
    for header_name in SECURITY_CRITICAL_HEADERS:
        header_lower = header_name.lower()

        # Find the actual header key (may have different casing)
        actual_key = None
        for key in sanitized.keys():
            if key.lower() == header_lower:
                actual_key = key
                break

        if actual_key:
            original_value = sanitized[actual_key]

            # Replace with server-controlled value
            if header_lower in ("x-forwarded-for", "x-real-ip"):
                sanitized[actual_key] = real_ip
            elif header_lower == "x-forwarded-host":
                # Redact - we don't have API Gateway context
                sanitized[actual_key] = "[REDACTED]"
            elif header_lower == "x-forwarded-server":
                sanitized[actual_key] = "[REDACTED]"
            elif header_lower == "x-amzn-client-id":
                sanitized[actual_key] = "[REDACTED]"
            elif header_lower == "forwarded":
                sanitized[actual_key] = f"for={real_ip}"

            # Track modification
            if original_value != sanitized[actual_key]:
                modifications.append(actual_key)

    # Log sanitization actions for security monitoring
    if modifications:
        logger.debug(f"Sanitized headers: {', '.join(modifications)}")

    return sanitized


def get_sanitized_headers_from_request(request: Request) -> dict[str, str]:
    """
    Extract and sanitize headers from a FastAPI request for safe logging.

    This is a convenience function that extracts headers from the request
    and sanitizes them in one step.

    Args:
        request: FastAPI Request object

    Returns:
        Dictionary of sanitized headers safe for logging
    """
    headers = dict(request.headers)
    real_ip = get_real_client_ip(request)
    return sanitize_headers_for_logging(headers, real_ip)
