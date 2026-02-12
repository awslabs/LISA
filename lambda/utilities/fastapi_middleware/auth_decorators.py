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

"""Authentication decorators for FastAPI route handlers."""

from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import HTTPException, Request, status
from utilities.auth import is_admin


def require_admin(message: str = "User does not have permission to perform this action") -> Callable:
    """
    Decorator for FastAPI route handlers that require admin access.

    Works with async FastAPI handlers that have a `request: Request` parameter.
    The decorator extracts the AWS event from the request scope and checks admin status.

    Args:
        message: Custom error message for non-admin users

    Usage:
        from utilities.fastapi_middleware.auth_decorators import require_admin

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
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Internal error: Request object not found in handler",
                )

            # Extract event from request scope (set by AWSAPIGatewayMiddleware)
            event = request.scope.get("aws.event", {})

            # Check admin status using utilities.auth.is_admin
            if not is_admin(event):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)

            return await func(*args, **kwargs)

        return wrapper

    return decorator
