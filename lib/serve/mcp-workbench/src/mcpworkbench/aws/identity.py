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

"""Helpers for extracting caller identity inside MCP tool functions.

Tool functions call :func:`get_caller_identity` to obtain the current :class:`CallerIdentity`.  On first access within a
request, the function reads HTTP headers from the underlying MCP request context and caches the result in a
``ContextVar``.

No FastMCP middleware is required — identity is resolved lazily on demand.
"""

from __future__ import annotations

import base64
import contextvars
import json
import logging
from dataclasses import dataclass
from typing import Any, cast

logger = logging.getLogger(__name__)

_current_identity: contextvars.ContextVar[CallerIdentity | None] = contextvars.ContextVar(
    "current_caller_identity", default=None
)


@dataclass(frozen=True)
class CallerIdentity:
    user_id: str
    session_id: str


class CallerIdentityError(Exception):
    """Raised when caller identity cannot be determined from the HTTP request."""


def decode_jwt_payload(token: str) -> dict:
    """Extract claims from a JWT payload via base64 decode (no signature check).

    The OIDCHTTPBearer middleware already verified the signature, so this is purely for reading claims.
    """
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    payload += "=" * ((4 - len(payload) % 4) % 4)
    try:
        return cast(dict[str, Any], json.loads(base64.urlsafe_b64decode(payload)))
    except Exception:
        return {}


def _extract_identity_from_headers(headers: dict[str, str]) -> CallerIdentity | None:
    """Try to build a :class:`CallerIdentity` from raw HTTP headers.

    Returns ``None`` when either ``user_id`` or ``session_id`` cannot be determined.
    """
    user_id: str | None = headers.get("x-user-id")
    if not user_id:
        auth_header = headers.get("authorization", "")
        token = auth_header.removeprefix("Bearer").strip() if auth_header else ""
        if token:
            claims = decode_jwt_payload(token)
            user_id = claims.get("sub")
            logger.debug("Extracted user_id=%s from JWT sub claim", user_id)

    session_id = headers.get("x-session-id")

    if user_id and session_id:
        return CallerIdentity(user_id=user_id, session_id=session_id)
    return None


def _get_headers_from_request_ctx() -> dict[str, str]:
    """Read HTTP headers directly from the MCP low-level request context.

    Falls back to FastMCP's ``get_http_headers()`` if the direct approach fails.  Returns an empty dict if neither
    method succeeds.
    """
    # Approach 1: read directly from the MCP request_ctx ContextVar
    try:
        from mcp.server.lowlevel.server import request_ctx  # noqa: PLC0415

        ctx = request_ctx.get()
        request = ctx.request
        if request is not None:
            headers = cast(
                dict[str, str],
                {name.lower(): value for name, value in request.headers.items()},
            )
            logger.debug(
                "identity: read %d headers from request_ctx (keys: %s)",
                len(headers),
                sorted(headers.keys()),
            )
            return headers
        logger.warning("identity: request_ctx.request is None")
    except LookupError:
        logger.warning("identity: request_ctx ContextVar not set")
    except Exception:
        logger.warning("identity: failed reading request_ctx", exc_info=True)

    # Approach 2: use FastMCP's helper (catches RuntimeError internally)
    try:
        from fastmcp.server.dependencies import get_http_headers  # noqa: PLC0415

        headers = cast(dict[str, str], get_http_headers(include_all=True))
        logger.debug(
            "identity: fastmcp get_http_headers returned %d headers (keys: %s)",
            len(headers),
            sorted(headers.keys()),
        )
        return headers
    except Exception:
        logger.warning("identity: fastmcp get_http_headers failed", exc_info=True)

    return {}


def _populate_identity_from_http() -> CallerIdentity | None:
    """Read HTTP headers from the current MCP request and set the ContextVar.

    Must be called inside an MCP tool-call context.

    Returns the identity if successfully extracted, ``None`` otherwise.
    """
    headers = _get_headers_from_request_ctx()
    if not headers:
        logger.warning("identity: no headers available — cannot extract identity")
        return None

    identity = _extract_identity_from_headers(headers)
    if identity:
        _current_identity.set(identity)
        logger.debug(
            "identity: resolved user_id=%s session_id=%s",
            identity.user_id,
            identity.session_id,
        )
    else:
        has_auth = "authorization" in headers
        has_session = "x-session-id" in headers
        logger.warning(
            "identity: extraction failed — authorization present=%s, x-session-id present=%s, header keys=%s",
            has_auth,
            has_session,
            sorted(headers.keys()),
        )
    return identity


def get_caller_identity() -> CallerIdentity:
    """Return the caller identity for the current MCP tool invocation.

    On first call within a request, lazily reads HTTP headers from the MCP request context and caches the result.
    Subsequent calls in the same context return the cached value.

    Raises :class:`CallerIdentityError` when identity cannot be determined (required headers absent or not in an MCP
    request context).
    """
    identity = _current_identity.get()
    if identity is not None:
        return identity

    try:
        identity = _populate_identity_from_http()
    except Exception as exc:
        raise CallerIdentityError("Could not read HTTP headers — not in an MCP request context.") from exc

    if identity is None:
        raise CallerIdentityError(
            "Cannot determine caller identity. Ensure the MCP connection sends Authorization and X-Session-Id headers."
        )
    return identity
