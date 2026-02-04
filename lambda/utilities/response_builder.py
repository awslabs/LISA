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

"""Response builders for API Gateway Lambda functions."""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal, datetime, and Pydantic objects."""

    def default(self, obj: Any) -> Any:
        """
        Encode special types to JSON-serializable formats.

        Parameters
        ----------
        obj : Any
            Object to encode.

        Returns
        -------
        Any
            JSON-serializable representation.
        """
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        # Handle Pydantic models
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        return super().default(obj)


def _serialize_pydantic(obj: Any) -> Any:
    """
    Recursively serialize Pydantic models to dictionaries.

    Parameters
    ----------
    obj : Any
        Object to serialize.

    Returns
    -------
    Any
        Serialized object.
    """
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_serialize_pydantic(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _serialize_pydantic(value) for key, value in obj.items()}
    return obj


def generate_html_response(status_code: int, response_body: Any) -> dict[str, str | int | dict[str, str]]:
    """
    Generate API Gateway response with security headers.

    This function creates a properly formatted API Gateway response with:
    - JSON-encoded body
    - Security headers (HSTS, X-Frame-Options, etc.)
    - CORS headers
    - Cache control headers

    Parameters
    ----------
    status_code : int
        HTTP status code (e.g., 200, 400, 500).
    response_body : Any
        Response body to be JSON-encoded. Can be dict, list, Pydantic model, or list of Pydantic models.

    Returns
    -------
    Dict[str, Union[str, int, Dict[str, str]]]
        API Gateway response object.

    Example
    -------
    >>> generate_html_response(200, {"userId": "123", "name": "John"})
    {
        "statusCode": 200,
        "body": '{"userId": "123", "name": "John"}',
        "headers": {...}
    }
    """
    # Serialize Pydantic models before JSON encoding
    serialized_body = _serialize_pydantic(response_body)

    return {
        "statusCode": status_code,
        "body": json.dumps(serialized_body, cls=DecimalEncoder),
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json",
            "Cache-Control": "no-store, no-cache",
            "Pragma": "no-cache",
            "Strict-Transport-Security": "max-age:47304000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    }


def generate_exception_response(e: Exception) -> dict[str, str | int | dict[str, str]]:
    """
    Generate API Gateway error response from exception.

    This function maps exceptions to appropriate HTTP status codes and
    generates user-friendly error messages while logging detailed errors
    internally.

    Exception Mapping:
    - ValidationError → 400 Bad Request
    - AWS SDK exceptions → Status from response metadata
    - Custom exceptions with http_status_code/status_code → Custom status
    - Missing event parameters → 400 Bad Request
    - All other exceptions → 500 Internal Server Error

    Parameters
    ----------
    e : Exception
        Exception that was caught.

    Returns
    -------
    Dict[str, Union[str, int, Dict[str, str]]]
        API Gateway error response.

    Example
    -------
    >>> try:
    ...     raise ValueError("Invalid user ID")
    ... except Exception as e:
    ...     response = generate_exception_response(e)
    >>> response["statusCode"]
    500
    """
    status_code = 400
    error_message: str

    if type(e).__name__ == "ValidationError":
        # User input validation error - return 400 with error message
        error_message = str(e)
        logger.exception(e)
    elif hasattr(e, "response"):
        # AWS SDK exception - extract status code and message
        metadata = e.response.get("ResponseMetadata")
        if metadata:
            status_code = metadata.get("HTTPStatusCode", 400)
        error_message = str(e)
        logger.exception(e)
    elif hasattr(e, "http_status_code"):
        # Custom exception with http_status_code attribute
        status_code = e.http_status_code
        error_message = getattr(e, "message", str(e))
        logger.exception(e)
    elif hasattr(e, "status_code"):
        # Custom exception with status_code attribute (e.g., HTTPException)
        status_code = e.status_code
        error_message = getattr(e, "message", str(e))
        logger.exception(e)
    else:
        # Generic unhandled exception - return 500 with generic message
        error_msg = str(e)
        if error_msg in ["'requestContext'", "'pathParameters'", "'body'"]:
            # Missing event parameter - this is a 400 error
            status_code = 400
            error_message = f"Missing event parameter: {error_msg}"
        else:
            # Genuine server error - return 500 with generic message
            status_code = 500
            error_message = "An unexpected error occurred while processing your request"
            # Log detailed error for debugging
            logger.error(
                f"Unhandled exception: {type(e).__name__}: {error_msg}",
                exc_info=e,
                extra={
                    "exception_type": type(e).__name__,
                    "exception_message": error_msg,
                },
            )
        logger.exception(e)

    return generate_html_response(status_code, error_message)  # type: ignore [arg-type]
