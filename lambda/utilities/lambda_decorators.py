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

"""Lambda function decorators for API Gateway integration."""

import functools
import logging
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, overload

from utilities.event_parser import sanitize_event_for_logging
from utilities.input_validation import DEFAULT_MAX_REQUEST_SIZE, validate_input
from utilities.response_builder import generate_exception_response, generate_html_response

logger = logging.getLogger(__name__)

# Context variable to store Lambda context across the request
ctx_context: ContextVar[Any] = ContextVar("lamdbacontext")

# Type for Lambda handler functions - can return dict, list, or any JSON-serializable type
LambdaHandler = Callable[[dict[Any, Any], dict[Any, Any]], Any]


@overload
def api_wrapper(_func: LambdaHandler) -> LambdaHandler:
    """Overload for decorator without parentheses."""
    ...


@overload
def api_wrapper(
    _func: None = None,
    *,
    max_request_size: int = DEFAULT_MAX_REQUEST_SIZE,
) -> Callable[[LambdaHandler], LambdaHandler]:
    """Overload for decorator with parameters."""
    ...


def api_wrapper(
    _func: LambdaHandler | None = None,
    *,
    max_request_size: int = DEFAULT_MAX_REQUEST_SIZE,
) -> LambdaHandler | Callable[[LambdaHandler], LambdaHandler]:
    """
    Wrap Lambda function with comprehensive API Gateway integration.

    This decorator provides:
    - Input validation (null bytes, request size, HTTP methods)
    - Request logging with sanitized headers
    - Exception handling with appropriate status codes
    - Security headers in responses

    Can be used with or without parameters:
    - @api_wrapper
    - @api_wrapper()
    - @api_wrapper(max_request_size=10 * 1024 * 1024)

    Parameters
    ----------
    _func : LambdaHandler | None
        The Lambda handler function (used when decorator is applied without parentheses).
    max_request_size : int
        Maximum allowed request body size in bytes (default: 1MB).

    Returns
    -------
    LambdaHandler | Callable[[LambdaHandler], LambdaHandler]
        The wrapped function with API Gateway integration.

    Example
    -------
    >>> @api_wrapper
    ... def get_user(event: dict, context: dict) -> dict:
    ...     user_id = event["pathParameters"]["userId"]
    ...     return {"userId": user_id, "name": "John"}

    >>> @api_wrapper(max_request_size=10 * 1024 * 1024)
    ... def upload_image(event: dict, context: dict) -> dict:
    ...     # Handle large payload
    ...     return {"status": "uploaded"}
    """

    def decorator(f: LambdaHandler) -> LambdaHandler:
        @functools.wraps(f)
        @validate_input(max_request_size=max_request_size)
        def wrapper(event: dict[Any, Any], context: dict[Any, Any]) -> dict[Any, Any]:
            """Execute Lambda handler with API Gateway integration."""
            ctx_context.set(context)
            code_func_name = f.__name__
            lambda_func_name = context.get("function_name", "unknown")

            # Log request with sanitized event data
            sanitized_event = sanitize_event_for_logging(event)
            logger.info(f"Lambda {lambda_func_name}({code_func_name}) invoked with {sanitized_event}")

            try:
                result = f(event, context)
                return generate_html_response(200, result)
            except Exception as e:
                return generate_exception_response(e)

        return wrapper

    # Handle both @api_wrapper and @api_wrapper() syntax
    if _func is not None:
        return decorator(_func)
    return decorator


def authorization_wrapper(f: LambdaHandler) -> LambdaHandler:
    """
    Wrap Lambda authorizer function.

    This decorator sets up the Lambda context for authorizer functions
    without adding API Gateway response formatting.

    Parameters
    ----------
    f : LambdaHandler
        The Lambda authorizer function to wrap.

    Returns
    -------
    LambdaHandler
        The wrapped authorizer function.

    Example
    -------
    >>> @authorization_wrapper
    ... def authorizer(event: dict, context: dict) -> dict:
    ...     token = event["authorizationToken"]
    ...     return {"principalId": "user123", "policyDocument": {...}}
    """

    @functools.wraps(f)
    def wrapper(event: dict[Any, Any], context: dict[Any, Any]) -> Any:
        """Execute Lambda authorizer with context setup."""
        ctx_context.set(context)
        return f(event, context)

    return wrapper


def get_lambda_context() -> Any:
    """
    Get the current Lambda context from context variable.

    Returns
    -------
    Any
        The Lambda context object.

    Raises
    ------
    LookupError
        If called outside of a Lambda execution context.
    """
    return ctx_context.get()
