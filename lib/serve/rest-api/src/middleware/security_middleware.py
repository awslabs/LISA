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

"""Security middleware for the serve API.

This middleware provides input validation and security checks for all incoming requests:
- Null byte detection in path, query params, and body
- HTTP method validation
- Request body validation for POST/PUT/PATCH requests
- Configurable size limits (with exemptions for model proxy endpoints)
"""

import fnmatch
import json
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_413_CONTENT_TOO_LARGE,
)

# HTTP methods that require a request body
METHODS_REQUIRING_BODY = {"POST", "PUT", "PATCH"}

# HTTP methods that are allowed by the serve API
ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}

# Default size limit for non-exempt endpoints (1MB)
DEFAULT_MAX_SIZE = 1024 * 1024

# Endpoints exempt from size limits - all serve API routes are model proxy routes
SIZE_LIMIT_EXEMPT_PATTERNS = ["/*"]


def contains_null_bytes(data: bytes) -> bool:
    """Check if data contains null bytes.

    Args:
        data: Bytes to check for null bytes

    Returns:
        True if null bytes are found, False otherwise
    """
    return b"\x00" in data


def is_exempt_from_size_limit(path: str, exempt_patterns: list[str] | None = None) -> bool:
    """Check if path is exempt from size limits.

    Args:
        path: Request path to check
        exempt_patterns: List of glob patterns for exempt endpoints

    Returns:
        True if path matches an exempt pattern, False otherwise
    """
    patterns = exempt_patterns or SIZE_LIMIT_EXEMPT_PATTERNS
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def create_error_response(status_code: int, error: str, message: str) -> JSONResponse:
    """Create a standardized error response.

    Args:
        status_code: HTTP status code
        error: Error type (e.g., "Bad Request")
        message: User-friendly error message

    Returns:
        JSONResponse with error details
    """
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message},
    )


async def security_middleware(
    request: Request,
    call_next: Callable[[Request], Response],
    default_max_size: int = DEFAULT_MAX_SIZE,
    exempt_patterns: list[str] | None = None,
) -> Response:
    """Security middleware for input validation.

    This middleware performs the following security checks:
    1. HTTP method validation - returns 405 for unsupported methods
    2. Null byte detection - returns 400 if null bytes found
    3. Request body validation - returns 400 for missing/invalid body on POST/PUT/PATCH
    4. Size limit enforcement - returns 413 for oversized requests (non-exempt endpoints)

    Args:
        request: The incoming FastAPI request
        call_next: The next middleware or route handler
        default_max_size: Default max request size in bytes for non-exempt endpoints
        exempt_patterns: List of glob patterns for endpoints exempt from size limits

    Returns:
        Response from the next handler or an error response
    """
    path = request.url.path
    method = request.method

    # 1. HTTP Method Validation
    if method not in ALLOWED_METHODS:
        logger.warning(f"Unsupported HTTP method: {method} for path: {path}")
        response = create_error_response(
            status_code=HTTP_405_METHOD_NOT_ALLOWED,
            error="Method Not Allowed",
            message=f"HTTP method {method} is not allowed",
        )
        response.headers["Allow"] = ", ".join(sorted(ALLOWED_METHODS))
        return response

    # 2. Check for null bytes in path
    if contains_null_bytes(path.encode("utf-8", errors="surrogateescape")):
        logger.warning(f"Null bytes detected in request path: {path}")
        return create_error_response(
            status_code=HTTP_400_BAD_REQUEST,
            error="Bad Request",
            message="Invalid characters detected in request",
        )

    # 3. Check for null bytes in query string
    query_string = str(request.url.query) if request.url.query else ""
    if contains_null_bytes(query_string.encode("utf-8", errors="surrogateescape")):
        logger.warning(f"Null bytes detected in query string for path: {path}")
        return create_error_response(
            status_code=HTTP_400_BAD_REQUEST,
            error="Bad Request",
            message="Invalid characters detected in request",
        )

    # 4. Request body validation for methods that require a body
    if method in METHODS_REQUIRING_BODY:
        # Read the body
        body = await request.body()

        # Check content type to determine if we should validate body
        content_type = request.headers.get("content-type", "").lower()

        # Skip null byte check for multipart/form-data (binary file uploads contain null bytes)
        # and other binary content types
        is_binary_content = (
            "multipart/form-data" in content_type
            or "application/octet-stream" in content_type
            or "image/" in content_type
            or "video/" in content_type
            or "audio/" in content_type
        )

        # Check for null bytes in body (only for text-based content)
        if not is_binary_content and contains_null_bytes(body):
            logger.warning(f"Null bytes detected in request body for path: {path}")
            return create_error_response(
                status_code=HTTP_400_BAD_REQUEST,
                error="Bad Request",
                message="Invalid characters detected in request",
            )

        # Skip body validation for multipart/form-data (file uploads)
        if "multipart/form-data" not in content_type:
            # Check for missing body
            if not body:
                logger.warning(f"Missing request body for {method} request to: {path}")
                return create_error_response(
                    status_code=HTTP_400_BAD_REQUEST,
                    error="Bad Request",
                    message="Request body is required",
                )

            # Validate JSON body (only for JSON content types or when no content type specified)
            if "application/json" in content_type or not content_type:
                try:
                    json.loads(body)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in request body for path: {path}")
                    return create_error_response(
                        status_code=HTTP_400_BAD_REQUEST,
                        error="Bad Request",
                        message="Request body must be valid JSON",
                    )

        # 5. Size limit enforcement (only for non-exempt endpoints)
        if not is_exempt_from_size_limit(path, exempt_patterns):
            if len(body) > default_max_size:
                logger.warning(
                    f"Request body too large ({len(body)} bytes) for path: {path}, "
                    f"max allowed: {default_max_size} bytes"
                )
                return create_error_response(
                    status_code=HTTP_413_CONTENT_TOO_LARGE,
                    error="Payload Too Large",
                    message="Request body exceeds maximum size",
                )

    # All validations passed, continue to next handler
    return await call_next(request)
