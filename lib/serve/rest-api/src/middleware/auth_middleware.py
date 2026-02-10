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

"""Authentication middleware for the serve API.

This middleware handles authentication at the request level, validating tokens
and setting user context on request.state for downstream handlers.
"""

import os
from collections.abc import Callable
from functools import wraps
from typing import Any

from auth import Authorizer
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from utils.route_utils import is_openai_or_anthropic_route

# Paths that don't require authentication
PUBLIC_PATHS = {"/health", "/health/readiness", "/health/liveliness"}


def is_public_path(path: str) -> bool:
    """Check if path is public (no auth required)."""
    return path in PUBLIC_PATHS


async def auth_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    """Authentication middleware.

    Validates authentication tokens and sets user context on request.state.
    Public paths (health checks) and OPTIONS requests (CORS preflight) bypass authentication.
    OpenAI/Anthropic routes require authentication but authorization is handled by the endpoint.

    Sets on request.state:
        - authenticated: bool - Whether user is authenticated
        - jwt_data: dict | None - JWT claims if OIDC auth, None for API tokens
        - is_admin: bool - Whether user has admin privileges
        - username: str - Username from token
        - groups: list[str] - User groups from token

    Args:
        request: The incoming FastAPI request
        call_next: The next middleware or route handler

    Returns:
        Response from the next handler or 401 error
    """
    path = request.url.path

    # Skip auth for OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        return await call_next(request)

    # Skip auth for public paths
    if is_public_path(path):
        return await call_next(request)

    # Skip auth if disabled
    if os.getenv("USE_AUTH", "true").lower() != "true":
        request.state.authenticated = True
        request.state.jwt_data = None
        request.state.is_admin = True
        request.state.username = "anonymous"
        request.state.groups = []
        return await call_next(request)

    # For OpenAI/Anthropic routes, authentication is required but we let the endpoint handle authorization
    is_openai_route = is_openai_or_anthropic_route(path)

    try:
        authorizer = Authorizer()
        jwt_data = await authorizer.authenticate_request(request)

        # Set authentication context on request state
        request.state.authenticated = True
        request.state.jwt_data = jwt_data

        # Determine admin status based on auth type
        if jwt_data:
            # OIDC auth - check JWT for admin group
            request.state.is_admin = authorizer.auth_provider.check_admin_access_jwt(
                jwt_data, authorizer.jwt_groups_property
            )
            request.state.username = jwt_data.get("sub", jwt_data.get("username", "unknown"))
            request.state.groups = _extract_groups_from_jwt(jwt_data, authorizer.jwt_groups_property)
        elif hasattr(request.state, "api_token_info"):
            # API token auth
            token_info = request.state.api_token_info
            request.state.is_admin = authorizer.auth_provider.check_admin_access(
                token_info.get("username", ""), token_info.get("groups", [])
            )
            request.state.username = token_info.get("username", "api-token")
            request.state.groups = token_info.get("groups", [])
        else:
            # Management token - full admin access
            request.state.is_admin = True
            request.state.username = "management-token"
            request.state.groups = []

        return await call_next(request)

    except HTTPException as e:
        # For OpenAI/Anthropic routes, provide more specific error messages
        if is_openai_route:
            logger.warning(f"Authentication failed for OpenAI/Anthropic route {path}: {e.detail}")
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={
                    "error": {
                        "message": "Invalid authentication credentials",
                        "type": "invalid_request_error",
                        "code": "invalid_api_key",
                    }
                },
            )
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        if is_openai_route:
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={
                    "error": {
                        "message": "Authentication failed",
                        "type": "invalid_request_error",
                        "code": "authentication_error",
                    }
                },
            )
        return JSONResponse(
            status_code=HTTP_401_UNAUTHORIZED,
            content={"error": "Unauthorized", "message": "Authentication failed"},
        )


def _extract_groups_from_jwt(jwt_data: dict[str, Any], jwt_groups_property: str) -> list[str]:
    """Extract user groups from JWT data."""
    if not jwt_groups_property:
        return []

    props = jwt_groups_property.split(".")
    current_node: Any = jwt_data

    for prop in props:
        if isinstance(current_node, dict) and prop in current_node:
            current_node = current_node[prop]
        else:
            return []

    return current_node if isinstance(current_node, list) else []


def require_auth(func: Callable) -> Callable:
    """Decorator to require authentication on a route.

    Use this for routes that need authentication but not admin access.
    The auth middleware must run before this decorator.

    Example:
        @router.get("/protected")
        @require_auth
        async def protected_route(request: Request):
            return {"user": request.state.username}
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        request = kwargs.get("request") or (args[0] if args else None)
        if not request or not isinstance(request, Request):
            raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Request object not found")

        if not getattr(request.state, "authenticated", False):
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Authentication required")

        return await func(*args, **kwargs)

    return wrapper


def require_admin(func: Callable) -> Callable:
    """Decorator to require admin access on a route.

    Use this for routes that need admin privileges.
    The auth middleware must run before this decorator.

    Example:
        @router.post("/admin-only")
        @require_admin
        async def admin_route(request: Request):
            return {"admin": request.state.username}
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        request = kwargs.get("request") or (args[0] if args else None)
        if not request or not isinstance(request, Request):
            raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Request object not found")

        if not getattr(request.state, "authenticated", False):
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Authentication required")

        if not getattr(request.state, "is_admin", False):
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Admin access required")

        return await func(*args, **kwargs)

    return wrapper
