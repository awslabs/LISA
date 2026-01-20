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
from contextvars import ContextVar
from typing import Any, Callable, Dict, TypeVar, Union

from utilities.event_parser import sanitize_event_for_logging
from utilities.input_validation import validate_input
from utilities.response_builder import generate_exception_response, generate_html_response

logger = logging.getLogger(__name__)

# Context variable to store Lambda context across the request
ctx_context: ContextVar[Any] = ContextVar("lamdbacontext")

F = TypeVar("F", bound=Callable[..., Any])


def api_wrapper(f: F) -> F:
    """
    Wrap Lambda function with comprehensive API Gateway integration.

    This decorator provides:
    - Input validation (null bytes, request size, HTTP methods)
    - Request logging with sanitized headers
    - Exception handling with appropriate status codes
    - Security headers in responses

    Parameters
    ----------
    f : F
        The Lambda handler function to wrap.

    Returns
    -------
    F
        The wrapped function with API Gateway integration.

    Example
    -------
    >>> @api_wrapper
    ... def get_user(event: dict, context: dict) -> dict:
    ...     user_id = event["pathParameters"]["userId"]
    ...     return {"userId": user_id, "name": "John"}
    """

    @functools.wraps(f)
    @validate_input()  # Add input validation before processing
    def wrapper(event: dict, context: dict) -> Dict[str, Union[str, int, Dict[str, str]]]:
        """Execute Lambda handler with API Gateway integration."""
        ctx_context.set(context)
        code_func_name = f.__name__
        lambda_func_name = context.function_name  # type: ignore [attr-defined]

        # Log request with sanitized event data
        sanitized_event = sanitize_event_for_logging(event)
        logger.info(f"Lambda {lambda_func_name}({code_func_name}) invoked with {sanitized_event}")

        try:
            result = f(event, context)
            return generate_html_response(200, result)
        except Exception as e:
            return generate_exception_response(e)

    return wrapper  # type: ignore [return-value]


def authorization_wrapper(f: F) -> F:
    """
    Wrap Lambda authorizer function.

    This decorator sets up the Lambda context for authorizer functions
    without adding API Gateway response formatting.

    Parameters
    ----------
    f : F
        The Lambda authorizer function to wrap.

    Returns
    -------
    F
        The wrapped authorizer function.

    Example
    -------
    >>> @authorization_wrapper
    ... def authorizer(event: dict, context: dict) -> dict:
    ...     token = event["authorizationToken"]
    ...     return {"principalId": "user123", "policyDocument": {...}}
    """

    @functools.wraps(f)
    def wrapper(event: dict, context: dict) -> F:
        """Execute Lambda authorizer with context setup."""
        ctx_context.set(context)
        return f(event, context)  # type: ignore [no-any-return]

    return wrapper  # type: ignore [return-value]


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
