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

"""Utilities for parsing API Gateway Lambda events."""

import copy
import json
from typing import Any

from utilities.header_sanitizer import sanitize_headers


def sanitize_event_for_logging(event: dict[str, Any]) -> str:
    """
    Sanitize Lambda event before logging.

    This function sanitizes the event by:
    1. Redacting authorization headers
    2. Applying allowlist to only log safe headers
    3. Replacing security-critical headers with server-controlled values

    Parameters
    ----------
    event : Dict[str, Any]
        The Lambda event from API Gateway.

    Returns
    -------
    str
        The sanitized event as a JSON-formatted string.

    Example
    -------
    >>> event = {
    ...     "headers": {"Authorization": "Bearer token123"},
    ...     "path": "/users/123"
    ... }
    >>> sanitized = sanitize_event_for_logging(event)
    >>> "token123" in sanitized
    False
    """
    # Deep copy to avoid modifying original event
    sanitized = copy.deepcopy(event)

    # Redact authorization headers BEFORE applying allowlist
    # This ensures we log that auth was present, but not the actual token
    if "headers" in sanitized:
        # Normalize to lowercase and redact authorization
        normalized_headers = {}
        for key, value in sanitized["headers"].items():
            key_lower = key.lower()
            if key_lower == "authorization":
                normalized_headers[key_lower] = "<REDACTED>"
            else:
                normalized_headers[key_lower] = value
        sanitized["headers"] = normalized_headers

    if "multiValueHeaders" in sanitized:
        # Normalize to lowercase and redact authorization
        normalized_multi = {}
        for key, value in sanitized["multiValueHeaders"].items():
            key_lower = key.lower()
            if key_lower == "authorization":
                normalized_multi[key_lower] = ["<REDACTED>"]
            else:
                normalized_multi[key_lower] = value
        sanitized["multiValueHeaders"] = normalized_multi

    # Apply allowlist filtering to headers
    if "headers" in sanitized:
        sanitized["headers"] = sanitize_headers(sanitized["headers"], event)
        # Add back redacted authorization if it was present
        if "authorization" in event.get("headers", {}) or "Authorization" in event.get("headers", {}):
            sanitized["headers"]["authorization"] = "<REDACTED>"

    # Also sanitize multiValueHeaders if present
    if "multiValueHeaders" in sanitized:
        # Convert to single-value dict for sanitization, then back
        multi_headers = sanitized["multiValueHeaders"]
        single_value_headers = {k: v[0] if v else "" for k, v in multi_headers.items()}
        sanitized_single = sanitize_headers(single_value_headers, event)

        # Rebuild multiValueHeaders with sanitized values
        sanitized["multiValueHeaders"] = {k: [v] for k, v in sanitized_single.items()}
        # Add back redacted authorization if it was present
        if "authorization" in event.get("multiValueHeaders", {}) or "Authorization" in event.get(
            "multiValueHeaders", {}
        ):
            sanitized["multiValueHeaders"]["authorization"] = ["<REDACTED>"]

    return json.dumps(sanitized)


def get_session_id(event: dict) -> str:
    """
    Extract session ID from Lambda event path parameters.

    Parameters
    ----------
    event : dict
        Lambda event from API Gateway.

    Returns
    -------
    str
        The session ID from path parameters.

    Example
    -------
    >>> event = {"pathParameters": {"sessionId": "sess-123"}}
    >>> get_session_id(event)
    'sess-123'
    """
    session_id: str = event.get("pathParameters", {}).get("sessionId")
    return session_id


def get_principal_id(event: dict) -> str:
    """
    Extract principal ID from Lambda event authorizer context.

    Parameters
    ----------
    event : dict
        Lambda event from API Gateway.

    Returns
    -------
    str
        The principal ID from authorizer context.

    Example
    -------
    >>> event = {
    ...     "requestContext": {
    ...         "authorizer": {"principal": "user-123"}
    ...     }
    ... }
    >>> get_principal_id(event)
    'user-123'
    """
    principal: str = event.get("requestContext", {}).get("authorizer", {}).get("principal", "")
    return principal


def get_bearer_token(event: dict) -> str | None:
    """
    Extract Bearer token from Authorization header in Lambda event.

    Parameters
    ----------
    event : dict
        Lambda event from API Gateway.

    Returns
    -------
    Optional[str]
        The token string if present and properly formatted, else None.

    Example
    -------
    >>> event = {"headers": {"Authorization": "Bearer abc123"}}
    >>> get_bearer_token(event)
    'abc123'
    """
    headers = event.get("headers") or {}
    # Headers may vary in casing
    auth_header: str | None = headers.get("Authorization") or headers.get("authorization")
    if not auth_header:
        return None

    if not auth_header.lower().startswith("bearer "):
        return None

    # Return the token after "Bearer "
    token: str = auth_header.split(" ", 1)[1].strip()
    return token


def get_id_token(event: dict) -> str:
    """
    Extract ID token from Authorization header in Lambda event.

    This function extracts the bearer token from the authorization header,
    removing the "Bearer" prefix if present.

    Parameters
    ----------
    event : dict
        Lambda event from API Gateway.

    Returns
    -------
    str
        The ID token without the "Bearer" prefix.

    Raises
    ------
    ValueError
        If authorization header is missing.

    Example
    -------
    >>> event = {"headers": {"Authorization": "Bearer token123"}}
    >>> get_id_token(event)
    'token123'
    """
    auth_header = None

    if "authorization" in event["headers"]:
        auth_header = event["headers"]["authorization"]
    elif "Authorization" in event["headers"]:
        auth_header = event["headers"]["Authorization"]
    else:
        raise ValueError("Missing authorization token.")

    # Remove bearer token prefix if present
    return str(auth_header).removeprefix("Bearer ").removeprefix("bearer ").strip()
