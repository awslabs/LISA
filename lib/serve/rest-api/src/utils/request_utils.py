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

"""Utility functions for handling request data."""
import json
import os
import sys
import traceback
from collections.abc import AsyncGenerator, Callable
from typing import Any

from loguru import logger

logger.remove()
logger_level = os.environ.get("LOG_LEVEL", "INFO")
logger.configure(
    extra={
        "request_id": "NO_REQUEST_ID",
        "endpoint": "NO_ENDPOINT",
        "event": "NO_EVENT",
        "status": "NO_STATUS",
    },
    handlers=[
        {
            "sink": sys.stdout,
            "format": (
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <cyan>{extra[request_id]}</cyan> | "
                "<level>{level: <8}</level> | <yellow>{extra[endpoint]}</yellow> | "
                "<blue>{extra[event]}</blue> | <magenta>{extra[status]}</magenta> | {message}"
            ),
            "level": logger_level.upper(),
        }
    ],
)


def handle_stream_exceptions(
    func: Callable[..., AsyncGenerator[str]],
) -> Callable[..., AsyncGenerator[str]]:
    """Decorate a streaming function to handle exceptions gracefully.

    This decorator catches any exceptions raised during the execution of a streaming function
    and yields a formatted error message as a string in the stream. The error message contains
    the type of the exception, the error message, and the traceback.

    Parameters
    ----------
    func : Callable[..., AsyncGenerator[str, None]]
        The streaming function to wrap. This function is expected to be an asynchronous generator
        yielding strings.

    Returns
    -------
    wrapper : Callable[..., AsyncGenerator[str, None]]
        The wrapped function, which handles exceptions by yielding them as formatted error messages
        in the stream.

    Yields
    ------
    str
        The items yielded by the original function, or a JSON-formatted error message in case of an exception.
    """

    async def wrapper(*args: Any, **kwargs: Any) -> AsyncGenerator[str]:
        try:
            async for item in func(*args, **kwargs):
                yield item
        except Exception as e:
            error_message = {
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "trace": traceback.format_exc(),
                }
            }
            logger.exception(
                error_message["error"]["message"],
                extra={"event": "handle_stream_exceptions", "status": "ERROR"},
            )
            yield f"data:{json.dumps({'event': 'error', 'data': error_message})}\n\n"

    return wrapper
