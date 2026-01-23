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

"""Input validation utilities for Lambda functions."""

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from utilities.response_builder import generate_html_response

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Default maximum request size: 1MB
DEFAULT_MAX_REQUEST_SIZE = 1024 * 1024
# Max API Gateway size - use for image uploads / chat sessions
MAX_LARGE_REQUEST_SIZE = 10 * 1024 * 1024


def contains_null_bytes(data: str) -> bool:
    """
    Check if a string contains null bytes.

    Null bytes (\\x00) can be used to bypass input validation or cause
    unexpected behavior in string processing.

    Args:
        data: String to check for null bytes

    Returns:
        True if null bytes are found, False otherwise
    """
    return "\x00" in data


def validate_input(max_request_size: int = DEFAULT_MAX_REQUEST_SIZE) -> Callable[[F], F]:
    """
    Decorator to validate Lambda event input before processing.

    This decorator provides security protections against:
    - Null byte injection attacks
    - Oversized payload attacks
    - Invalid HTTP methods

    Args:
        max_request_size: Maximum allowed request body size in bytes (default: 1MB)

    Returns:
        Decorator function that wraps the Lambda handler
    """

    def decorator(f: F) -> F:
        @functools.wraps(f)
        def wrapper(event: dict, context: dict) -> dict[str, str | int | dict[str, str]]:
            """
            Validate Lambda event input.

            Validation order:
            1. HTTP method validation (returns 405 if invalid)
            2. Request size check (returns 413 if too large)
            3. Path validation (returns 400 if null bytes found)
            4. Query parameter validation (returns 400 if null bytes found)
            5. Request body validation (returns 400 if null bytes found)

            Args:
                event: Lambda event from API Gateway
                context: Lambda context

            Returns:
                Error response if validation fails, otherwise calls wrapped function
            """
            # 1. Validate HTTP method
            http_method = event.get("httpMethod", "")
            valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
            if http_method not in valid_methods:
                logger.warning(
                    f"Invalid HTTP method: {http_method}",
                    extra={
                        "method": http_method,
                        "path": event.get("path", ""),
                    },
                )
                return generate_html_response(
                    405,
                    {
                        "error": "Method Not Allowed",
                        "message": f"HTTP method {http_method} is not allowed",
                    },
                )

            # 2. Check request size
            body = event.get("body", "")
            if body:
                body_size = len(body.encode("utf-8"))
                if body_size > max_request_size:
                    logger.warning(
                        f"Request size {body_size} bytes exceeds maximum {max_request_size} bytes",
                        extra={
                            "request_size": body_size,
                            "max_size": max_request_size,
                            "path": event.get("path", ""),
                            "method": http_method,
                        },
                    )
                    return generate_html_response(
                        413,
                        {
                            "error": "Payload Too Large",
                            "message": f"Request body size exceeds maximum allowed size of {max_request_size} bytes",
                        },
                    )

            # 3. Validate path for null bytes
            path = event.get("path", "")
            if contains_null_bytes(path):
                logger.warning(
                    "Null byte detected in path",
                    extra={
                        "path": path,
                        "method": http_method,
                    },
                )
                return generate_html_response(
                    400,
                    {
                        "error": "Bad Request",
                        "message": "Invalid characters detected in request path",
                    },
                )

            # 4. Validate query parameters for null bytes
            query_params = event.get("queryStringParameters") or {}
            for key, value in query_params.items():
                if contains_null_bytes(key) or contains_null_bytes(str(value)):
                    logger.warning(
                        f"Null byte detected in query parameter: {key}",
                        extra={
                            "parameter_name": key,
                            "path": path,
                            "method": http_method,
                        },
                    )
                    return generate_html_response(
                        400,
                        {
                            "error": "Bad Request",
                            "message": "Invalid characters detected in query parameters",
                        },
                    )

            # 5. Validate request body for null bytes
            if body and contains_null_bytes(body):
                logger.warning(
                    "Null byte detected in request body",
                    extra={
                        "path": path,
                        "method": http_method,
                        "body_size": body_size,
                    },
                )
                return generate_html_response(
                    400,
                    {
                        "error": "Bad Request",
                        "message": "Invalid characters detected in request body",
                    },
                )

            # All validations passed, call the wrapped function
            result: dict[str, str | int | dict[str, str]] = f(event, context)
            return result

        return wrapper  # type: ignore [return-value]

    return decorator
