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
import re
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


def get_lisa_end_user_id(
    jwt_data: dict[str, Any] | None,
    state_username: str | None,
) -> str | None:
    """
    Derive a human-readable end-user id for logs/spend attribution.

    LiteLLM uses the provided end-user identifier for spend/budget/logging.
    We prefer the same claims used by the authorizer/session to make the
    logs match what admins see in the UI/session DB.

    Precedence (highest to lowest):
    1. jwt_data["cognito:username"] (if present)
    2. jwt_data["username"] (if present and no cognito:username)
    3. jwt_data["sub"]
    4. fallback to state_username (request.state.username)
    """
    candidate: str | None = None
    if isinstance(jwt_data, dict):
        username = jwt_data.get("username")
        candidate = username if isinstance(username, str) and username else None

        cognito_username = jwt_data.get("cognito:username")
        if isinstance(cognito_username, str) and cognito_username:
            candidate = cognito_username

        if not candidate:
            sub = jwt_data.get("sub")
            if isinstance(sub, str) and sub:
                candidate = sub

    if candidate:
        return candidate

    if isinstance(state_username, str) and state_username:
        return state_username

    return None


# Parameters that specific provider models are known to reject. We strip them
# server-side before forwarding to LiteLLM for two reasons:
#
#   1. LiteLLM's ``drop_params: true`` only drops OpenAI parameters the provider
#      is known (to LiteLLM) not to support. Anthropic's post-release
#      deprecations (e.g. Opus 4.7 deprecating ``top_p``) lag LiteLLM's provider
#      map, so users hit raw BedrockException 400s until a LiteLLM bump lands.
#   2. The chat UI exposes generic sliders (e.g. ``top_p``, ``temperature``)
#      that users can set independent of the selected model. We don't want to
#      burden every client (UI, SDK, Claude Code, etc.) with per-model quirks.
#
# Entries are matched against the canonical LiteLLM model path (``model_name``
# resolved via ``get_model_info``, e.g.
# ``"bedrock/us.anthropic.claude-opus-4-7-20260101-v1:0"``). Extend this list as
# providers deprecate additional parameters.
_MODEL_UNSUPPORTED_PARAMS: list[tuple[re.Pattern[str], tuple[str, ...]]] = [
    # Anthropic Claude Opus 4.7 on Bedrock rejects ``top_p`` with
    # "`top_p` is deprecated for this model." The adaptive-thinking rework also
    # landed in this family; see BerriAI/litellm#25867 for the LiteLLM fix that
    # handled the ``thinking.type`` shape.
    (re.compile(r"claude-opus-4-7", re.IGNORECASE), ("top_p",)),
]


def strip_unsupported_model_params(
    params: dict[str, Any],
    model_name: str | None,
) -> list[str]:
    """Remove parameters the target provider model is known to reject.

    Mutates ``params`` in place.

    Parameters
    ----------
    params : dict[str, Any]
        The request payload that will be forwarded to LiteLLM.
    model_name : str | None
        The canonical LiteLLM model path (the value of
        ``litellm_params.model`` returned by ``get_model_info``). ``None`` /
        empty strings disable stripping.

    Returns
    -------
    list[str]
        The parameter keys that were removed, intended for logging /
        observability. Empty list when nothing was stripped.
    """
    if not model_name or not isinstance(params, dict):
        return []

    removed: list[str] = []
    for pattern, unsupported in _MODEL_UNSUPPORTED_PARAMS:
        if pattern.search(model_name):
            for key in unsupported:
                if key in params:
                    params.pop(key, None)
                    removed.append(key)
    return removed
