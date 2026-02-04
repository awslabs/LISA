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

"""Input validation middleware for FastAPI REST API."""
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger

# Maximum request size: 10MB
# This allows for large prompts, image uploads, and other content
# Token limits are enforced by LiteLLM and the models themselves
DEFAULT_MAX_REQUEST_SIZE = 10 * 1024 * 1024


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


async def validate_input_middleware(
    request: Request, call_next: Callable[[Request], Any], max_request_size: int = DEFAULT_MAX_REQUEST_SIZE
) -> Response:
    """
    Middleware to validate request input before processing.

    This middleware provides security protections against:
    - Null byte injection attacks
    - Oversized payload attacks
    - Invalid HTTP methods

    Args:
        request: The incoming FastAPI request
        call_next: The next middleware or route handler
        max_request_size: Maximum allowed request body size in bytes (default: 10MB)

    Returns:
        Error response if validation fails, otherwise calls next handler
    """
    event = "validate_input"
    task_logger = logger.bind(event=event)

    # 1. Validate HTTP method
    valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
    if request.method not in valid_methods:
        task_logger.warning(
            f"Invalid HTTP method: {request.method}",
            status="ERROR",
        )
        return JSONResponse(
            status_code=405,
            content={
                "error": "Method Not Allowed",
                "message": f"HTTP method {request.method} is not allowed",
            },
        )

    # 2. Validate path for null bytes
    if contains_null_bytes(str(request.url.path)):
        task_logger.warning(
            "Null byte detected in path",
            status="ERROR",
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": "Bad Request",
                "message": "Invalid characters detected in request path",
            },
        )

    # 3. Validate path parameters for null bytes
    for key, value in request.path_params.items():
        if contains_null_bytes(key) or contains_null_bytes(str(value)):
            task_logger.warning(
                f"Null byte detected in path parameter: {key}",
                status="ERROR",
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Bad Request",
                    "message": "Invalid characters detected in path parameters",
                },
            )

    # 4. Validate query parameters for null bytes
    for key, value in request.query_params.items():
        if contains_null_bytes(key) or contains_null_bytes(str(value)):
            task_logger.warning(
                f"Null byte detected in query parameter: {key}",
                status="ERROR",
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Bad Request",
                    "message": "Invalid characters detected in query parameters",
                },
            )

    # 5. Check request size and validate body for null bytes
    # Only check body for methods that typically have a body
    if request.method in {"POST", "PUT", "PATCH"}:
        # Read the body
        body = await request.body()

        # Check size
        body_size = len(body)
        if body_size > max_request_size:
            task_logger.warning(
                f"Request size {body_size} bytes exceeds maximum {max_request_size} bytes",
                status="ERROR",
            )
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Payload Too Large",
                    "message": f"Request body size exceeds maximum allowed size of {max_request_size} bytes",
                },
            )

        # Check for null bytes in body
        if body:
            try:
                body_str = body.decode("utf-8")
                if contains_null_bytes(body_str):
                    task_logger.warning(
                        "Null byte detected in request body",
                        status="ERROR",
                    )
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "Bad Request",
                            "message": "Invalid characters detected in request body",
                        },
                    )
            except UnicodeDecodeError:
                # If body is not valid UTF-8, it might be binary data (e.g., file upload)
                # In this case, we skip null byte validation
                pass

        # Important: We need to make the body available again for the route handler
        # FastAPI's Request.body() can only be called once, so we need to store it
        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body}

        request._receive = receive

    # All validations passed, call the next handler
    response = await call_next(request)
    return response
