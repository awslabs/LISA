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

"""Request processing middleware."""
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from utils.header_sanitizer import get_real_client_ip, get_sanitized_headers_from_request


async def process_request_middleware(request: Request, call_next: Callable[[Request], Any]) -> Any:
    """Middleware for processing all HTTP requests.

    Parameters
    ----------
    request : Request
        The incoming request
    call_next : Callable
        The next middleware or route handler

    Returns
    -------
    Response
        The response with added request ID header
    """
    event = "process_request"
    request_id = str(uuid4())  # Unique ID for this request
    tic = time.time()

    # Get real client IP for logging (sanitized)
    client_ip = get_real_client_ip(request)

    with logger.contextualize(request_id=request_id, endpoint=request.url.path, client_ip=client_ip):
        try:
            task_logger = logger.bind(event=event)
            task_logger.debug("Start task", status="START")

            # Sanitize headers before any logging that might include them
            # This prevents log injection attacks via user-controlled headers
            _ = get_sanitized_headers_from_request(request)

            # Attempt to call the next request handler
            response = await call_next(request)

            # If response is successful, log the finish status
            duration = time.time() - tic
            task_logger.debug(f"Finish task (took {duration:.2f} seconds)", status="FINISH")

        except Exception as e:
            # In case of an exception, log the error and prepare a generic response
            duration = time.time() - tic
            task_logger.exception(
                f"Error occurred during processing: {e} (took {duration:.2f} seconds)",
                status="ERROR",
            )
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

        # Add the unique request ID to the response headers
        if response is not None and isinstance(response, Response):
            response.headers["X-Request-ID"] = request_id

    return response
