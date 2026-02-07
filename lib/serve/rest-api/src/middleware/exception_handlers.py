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

"""Exception handlers for the serve API.

This module provides exception handlers that return proper HTTP status codes
with generic error messages, preventing internal details from being exposed.
"""

import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions with a generic error response.

    This handler catches all unhandled exceptions and returns a generic
    500 error message without exposing internal details like stack traces,
    file paths, or variable names.

    Args:
        request: The incoming FastAPI request
        exc: The unhandled exception

    Returns:
        JSONResponse with generic error message and 500 status code
    """
    # Log the full exception details internally for debugging
    logger.error(
        f"Unhandled exception for {request.method} {request.url.path}: "
        f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    )

    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPException with appropriate status codes.

    This handler processes HTTPException instances and returns the
    appropriate status code with a sanitized error message.

    Args:
        request: The incoming FastAPI request
        exc: The HTTPException raised

    Returns:
        JSONResponse with error details and appropriate status code
    """
    # Log the exception for monitoring
    logger.warning(f"HTTP exception for {request.method} {request.url.path}: {exc.status_code} - {exc.detail}")

    # Map status codes to generic error types
    error_types = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        413: "Payload Too Large",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }

    error_type = error_types.get(exc.status_code, "Error")

    # For 500 errors, use a generic message to avoid leaking internal details
    if exc.status_code >= 500:
        message = "An unexpected error occurred"
    else:
        # For client errors, we can use the detail if it's a simple string
        # but sanitize it to avoid exposing internal paths or stack traces
        detail = str(exc.detail) if exc.detail else error_type
        # Remove any potential file paths or stack trace indicators
        if "/" in detail and (".py" in detail or "line" in detail.lower()):
            message = error_type
        else:
            message = detail

    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "error": error_type,
            "message": message,
        },
    )

    # Add headers from the exception if present
    if exc.headers:
        for key, value in exc.headers.items():
            response.headers[key] = value

    return response


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors with a generic message.

    This handler processes RequestValidationError instances and returns
    a 422 status code with a generic validation error message, without
    exposing internal field names or validation details.

    Args:
        request: The incoming FastAPI request
        exc: The RequestValidationError raised

    Returns:
        JSONResponse with generic validation error and 422 status code
    """
    # Log the full validation errors internally for debugging
    logger.warning(f"Validation error for {request.method} {request.url.path}: {exc.errors()}")

    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Unprocessable Entity",
            "message": "Request validation failed",
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers for the serve API.

    This function registers exception handlers for:
    - Generic exceptions (500 with generic message)
    - HTTPException (appropriate status code with sanitized message)
    - RequestValidationError (422 with generic message)

    Args:
        app: The FastAPI application instance
    """
    app.add_exception_handler(Exception, generic_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
