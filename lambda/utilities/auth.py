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
import hashlib
import json
import logging
import os
import secrets
import sys
from collections.abc import Callable
from functools import wraps
from typing import Any

import boto3
from botocore.config import Config
from fastapi import HTTPException as FastAPIHTTPException
from fastapi import Request
from utilities.exceptions import HTTPException

from .auth_provider import get_authorization_provider

logger = logging.getLogger(__name__)

retry_config = Config(
    retries={
        "max_attempts": 3,
        "mode": "standard",
    },
)

secrets_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)


def get_username(event: dict) -> str:
    """Get the username from the event."""
    username: str = event.get("requestContext", {}).get("authorizer", {}).get("username", "system")
    return username


def get_groups(event: Any) -> list[str]:
    """Get user groups from event."""
    groups: list[str] = json.loads(event.get("requestContext", {}).get("authorizer", {}).get("groups", "[]"))
    return groups


def is_admin(event: dict) -> bool:
    """Get admin status from event using the configured authorization provider."""
    username = get_username(event)
    groups = get_groups(event)
    auth_provider = get_authorization_provider()
    result = auth_provider.check_admin_access(username, groups)
    return result


def get_user_context(event: dict[str, Any]) -> tuple[str, bool, list[str]]:
    """Extract user context from event."""
    return get_username(event), is_admin(event), get_groups(event)


def user_has_group_access(user_groups: list[str], allowed_groups: list[str]) -> bool:
    """
    Check if user has access based on group membership.

    Args:
        user_groups: List of groups the user belongs to
        allowed_groups: List of groups allowed to access the resource

    Returns:
        True if user has access (either no restrictions or user has required group)
    """
    # Public resource (no group restrictions)
    if not allowed_groups:
        return True

    # Check if user has at least one matching group
    return len(set(user_groups).intersection(set(allowed_groups))) > 0


def admin_only(func: Callable) -> Callable:
    """Annotation to wrap is_admin for traditional Lambda handlers (event, context signature)."""

    @wraps(func)
    def wrapper(event: dict[str, Any], context: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        if not is_admin(event):
            raise HTTPException(status_code=403, message="User does not have permission to access this repository")
        return func(event, context, *args, **kwargs)

    return wrapper


def require_admin(message: str = "User does not have permission to perform this action") -> Callable:
    """
    Decorator for FastAPI route handlers that require admin access.

    Works with async FastAPI handlers that have a `request: Request` parameter.
    The decorator extracts the AWS event from the request scope and checks admin status.

    Args:
        message: Custom error message for non-admin users

    Usage:
        @app.post("/admin-endpoint")
        @require_admin()
        async def admin_endpoint(request: Request) -> Response:
            ...

        @app.delete("/models/{model_id}")
        @require_admin("User does not have permission to delete models")
        async def delete_model(model_id: str, request: Request) -> Response:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find the Request object in kwargs
            request = kwargs.get("request")
            if request is None:
                # Check positional args for Request type

                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                raise FastAPIHTTPException(
                    status_code=500, detail="Internal error: Request object not found in handler"
                )

            # Extract event from request scope
            event = request.scope.get("aws.event", {})
            # Look up is_admin from the module to allow patching in tests
            auth_module = sys.modules.get("utilities.auth")
            is_admin_func = getattr(auth_module, "is_admin", is_admin) if auth_module else is_admin
            if not is_admin_func(event):
                raise FastAPIHTTPException(status_code=403, detail=message)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def get_management_key() -> str:
    secret_name_param = ssm_client.get_parameter(Name=os.environ["MANAGEMENT_KEY_SECRET_NAME_PS"])
    secret_name = secret_name_param["Parameter"]["Value"]
    secret_response = secrets_client.get_secret_value(SecretId=secret_name)
    return secret_response["SecretString"]  # type: ignore[no-any-return]


# API token utility functions
def generate_token() -> str:
    """Generate cryptographically secure random token (64 bytes = 128 hex chars)"""
    return secrets.token_hex(64)


def hash_token(token: str) -> str:
    """Create SHA-256 hash of token"""
    return hashlib.sha256(token.encode()).hexdigest()


def is_api_user(event: dict) -> bool:
    """Get API user status from event."""
    api_group = os.environ.get("API_GROUP", "")
    groups = get_groups(event)
    logger.info(f"User groups: {groups} and api group: {api_group}")
    return api_group in groups
