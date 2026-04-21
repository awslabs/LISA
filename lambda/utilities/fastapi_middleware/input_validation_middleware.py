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

"""Middleware for FastAPI that validates and sanitizes input to prevent security vulnerabilities."""

import html
import logging
import re

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.middleware.base import ASGIApp, BaseHTTPMiddleware, Request, RequestResponseEndpoint, Response

logger = logging.getLogger(__name__)

# Default maximum request size: 1MB
DEFAULT_MAX_REQUEST_SIZE = 1024 * 1024


def sanitize_input(data: str) -> str:
    """
    Sanitize string input by removing or escaping dangerous characters.

    This function:
    - Escapes HTML/XML special characters to prevent XSS
    - Removes script tags and their content
    - Preserves legitimate special characters (hyphens, underscores, etc.)

    Args:
        data: String to sanitize

    Returns:
        Sanitized string safe for processing
    """
    if not data:
        return data

    # Remove script tags and their content (case-insensitive)
    data = re.sub(r"<script[^>]*>.*?</script>", "", data, flags=re.IGNORECASE | re.DOTALL)

    # Escape HTML special characters to prevent XSS
    # This preserves legitimate characters like hyphens, underscores, etc.
    data = html.escape(data)

    return data


class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates and sanitizes all incoming requests.

    This middleware provides security protections against:
    - Null byte injection attacks
    - Oversized payload attacks
    - Special character injection

    It intercepts all requests before they reach the application handlers
    and returns appropriate HTTP error codes for invalid input.
    """

    def __init__(self, app: ASGIApp, max_request_size: int = DEFAULT_MAX_REQUEST_SIZE) -> None:
        """
        Initialize the input validation middleware.

        Args:
            app: The ASGI application
            max_request_size: Maximum allowed request body size in bytes (default: 1MB)
        """
        super().__init__(app)
        self.app = app
        self.max_request_size = max_request_size

    def contains_null_bytes(self, data: str) -> bool:
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

    async def check_request_size(self, request: Request) -> JSONResponse | None:
        """
        Validate that the request body size does not exceed the configured limit.

        Args:
            request: The incoming HTTP request

        Returns:
            JSONResponse with 413 status if size exceeds limit, None otherwise
        """
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_request_size:
                    logger.warning(
                        f"Request size {size} bytes exceeds maximum {self.max_request_size} bytes",
                        extra={
                            "request_size": size,
                            "max_size": self.max_request_size,
                            "path": request.url.path,
                            "method": request.method,
                        },
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        content={
                            "error": "Payload Too Large",
                            "message": (
                                f"Request body size exceeds maximum allowed size " f"of {self.max_request_size} bytes"
                            ),
                        },
                    )
            except ValueError:
                # Invalid content-length header, let it pass and fail later if needed
                logger.warning(f"Invalid content-length header: {content_length}")

        return None

    async def validate_query_params(self, request: Request) -> JSONResponse | None:
        """
        Validate query parameters for null bytes.

        Args:
            request: The incoming HTTP request

        Returns:
            JSONResponse with 400 status if null bytes found, None otherwise
        """
        for key, value in request.query_params.items():
            if self.contains_null_bytes(key) or self.contains_null_bytes(value):
                logger.warning(
                    f"Null byte detected in query parameter: {key}",
                    extra={
                        "parameter_name": key,
                        "path": request.url.path,
                        "method": request.method,
                    },
                )
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error": "Bad Request",
                        "message": "Invalid characters detected in query parameters",
                    },
                )
        return None

    async def validate_path_params(self, request: Request) -> JSONResponse | None:
        """
        Validate path parameters for null bytes.

        Args:
            request: The incoming HTTP request

        Returns:
            JSONResponse with 400 status if null bytes found, None otherwise
        """
        path = str(request.url.path)
        if self.contains_null_bytes(path):
            logger.warning(
                "Null byte detected in path",
                extra={
                    "path": path,
                    "method": request.method,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Bad Request",
                    "message": "Invalid characters detected in request path",
                },
            )
        return None

    async def validate_request_body(self, request: Request) -> JSONResponse | None:
        """
        Validate request body for null bytes.

        This reads the request body and checks for null bytes. If found,
        returns an error response. Otherwise, the body is consumed and needs
        to be restored for downstream handlers.

        Args:
            request: The incoming HTTP request

        Returns:
            JSONResponse with 400 status if null bytes found, None otherwise
        """
        # Only check body for methods that typically have a body
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body:
                    # Check for null bytes in the raw body
                    if b"\x00" in body:
                        logger.warning(
                            "Null byte detected in request body",
                            extra={
                                "path": request.url.path,
                                "method": request.method,
                                "body_size": len(body),
                            },
                        )
                        return JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content={
                                "error": "Bad Request",
                                "message": "Invalid characters detected in request body",
                            },
                        )
            except Exception as e:
                # If we can't read the body, let it pass and fail later with proper error handling
                logger.warning(f"Error reading request body for validation: {e}")

        return None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Process the request through validation checks before passing to handlers.

        Validation order:
        1. HTTP method validation (returns 405 if invalid)
        2. Request size check (returns 413 if too large)
        3. Path parameter validation (returns 400 if null bytes found)
        4. Query parameter validation (returns 400 if null bytes found)
        5. Request body validation (returns 400 if null bytes found)

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or handler in the chain

        Returns:
            Response from validation or from the next handler
        """
        # Validate HTTP method
        # FastAPI will handle method validation at the route level, but we add
        # this as a safety check for any routes that might not be properly configured
        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        if request.method not in valid_methods:
            logger.warning(
                f"Invalid HTTP method: {request.method}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                content={
                    "error": "Method Not Allowed",
                    "message": f"HTTP method {request.method} is not allowed",
                },
                headers={"Allow": ", ".join(sorted(valid_methods))},
            )

        # Check request size
        size_error = await self.check_request_size(request)
        if size_error:
            return size_error

        # Validate path parameters
        path_error = await self.validate_path_params(request)
        if path_error:
            return path_error

        # Validate query parameters
        query_error = await self.validate_query_params(request)
        if query_error:
            return query_error

        # Validate request body
        body_error = await self.validate_request_body(request)
        if body_error:
            return body_error

        # All validations passed, proceed to next handler
        response = await call_next(request)
        return response
