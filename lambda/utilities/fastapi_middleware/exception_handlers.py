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

"""Common exception handlers for FastAPI applications."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all unhandled exceptions.

    This handler catches any exceptions not handled by more specific handlers.
    It logs detailed error information internally but returns a generic message
    to the client to avoid exposing internal implementation details.

    Security Note: Never expose internal details (stack traces, file paths, etc.)
    in error responses as they can aid attackers in reconnaissance.

    Args:
        request: The FastAPI request object
        exc: The exception that was raised

    Returns:
        JSONResponse with 500 status code and generic error message
    """
    # Log detailed error information for debugging
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}",
        exc_info=exc,
        extra={
            "method": request.method,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        },
    )

    # Return generic error message to client
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred while processing your request",
        },
    )
