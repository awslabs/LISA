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

"""Middleware components for MCP Workbench server."""

import logging
import sys
from collections.abc import Callable
from datetime import datetime
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware as StarletteCORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..config.models import CORSConfig
from ..core.tool_discovery import ToolDiscovery
from ..core.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class CORSMiddleware(StarletteCORSMiddleware):
    """CORS middleware wrapper for configuration compatibility."""

    def __init__(self, app: Any, cors_config: CORSConfig) -> None:
        super().__init__(
            app,
            allow_origins=cors_config.allow_origins,
            allow_methods=cors_config.allow_methods,
            allow_headers=cors_config.allow_headers,
            allow_credentials=cors_config.allow_credentials,
            expose_headers=cors_config.expose_headers,
            max_age=cors_config.max_age,
        )


def _parse_request_origin(scope: Scope) -> str | None:
    if scope["type"] != "http":
        return None
    for key, value in scope.get("headers") or []:
        if key.lower() == b"origin" and isinstance(value, bytes):
            return value.decode("latin-1")
    return None


def _access_control_allow_origin_value(cors_config: CORSConfig, request_origin: str | None) -> str | None:
    origins = cors_config.allow_origins
    empty_origin_wildcard = "" in origins

    if cors_config.allow_credentials:
        # "" in allow_origins means "reflect any request Origin" (cannot use * with credentials).
        if empty_origin_wildcard:
            return request_origin if request_origin else None
        if request_origin and request_origin in origins:
            return request_origin
        fallback = origins[0] if origins else "*"
        return None if fallback == "" else fallback
    if "*" in origins:
        return "*"
    if request_origin and request_origin in origins:
        return request_origin
    return origins[0] if origins else "*"


def _merge_vary_origin(headers: MutableHeaders) -> None:
    existing = headers.get("vary")
    if existing:
        parts = [p.strip() for p in existing.split(",") if p.strip()]
        if "Origin" not in parts:
            headers["vary"] = f"{existing}, Origin"
    else:
        headers["vary"] = "Origin"


def wrap_asgi_with_cors_headers(app: ASGIApp, cors_config: CORSConfig) -> ASGIApp:
    """Outer ASGI wrapper: ensure CORS headers on every HTTP response when missing.

    Starlette's outer ``ServerErrorMiddleware`` can emit error responses that bypass inner
    ``CORSMiddleware``'s ``send`` wrapper, so browsers see 500 without
    ``Access-Control-Allow-Origin`` and block the response body.
    """

    async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        origin = _parse_request_origin(scope)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if "access-control-allow-origin" not in headers:
                    acao = _access_control_allow_origin_value(cors_config, origin)
                    if acao is not None:
                        headers["access-control-allow-origin"] = acao
                        if origin and acao == origin:
                            _merge_vary_origin(headers)
                if cors_config.allow_headers and "*" in cors_config.allow_headers:
                    if "access-control-allow-headers" not in headers:
                        headers["access-control-allow-headers"] = "*"

            await send(message)

        await app(scope, receive, send_wrapper)

    return asgi


class ExitRouteMiddleware(BaseHTTPMiddleware):
    """Middleware to handle application exit requests."""

    def __init__(self, app: Any, exit_path: str) -> None:
        super().__init__(app)
        self.exit_path = exit_path.rstrip("/")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle the request and check for exit route."""
        # Normalize the request path
        request_path = request.url.path.rstrip("/")

        if request_path == self.exit_path:
            logger.info("Exit route called - shutting down server")

            # Return success response before exiting
            response = JSONResponse(
                {"status": "ok", "message": "Server shutting down", "timestamp": datetime.now().isoformat()}
            )

            # Schedule the exit to happen after response is sent
            import asyncio  # noqa: PLC0415

            asyncio.create_task(self._delayed_exit())

            return response

        # Continue with normal request processing
        return await call_next(request)

    async def _delayed_exit(self) -> None:
        """Exit the application after a short delay."""
        import asyncio  # noqa: PLC0415

        await asyncio.sleep(0.1)  # Short delay to ensure response is sent
        logger.info("Exiting application")
        sys.exit(0)


class RescanMiddleware(BaseHTTPMiddleware):
    """Middleware to handle tool rescanning requests."""

    def __init__(self, app: Any, rescan_path: str, tool_discovery: ToolDiscovery, tool_registry: ToolRegistry) -> None:
        super().__init__(app)
        self.rescan_path = rescan_path.rstrip("/")
        self.tool_discovery = tool_discovery
        self.tool_registry = tool_registry

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle the request and check for rescan route."""
        # Normalize the request path
        request_path = request.url.path.rstrip("/")

        if request_path == self.rescan_path:
            logger.info("Rescan route called - rescanning tools")

            try:
                # Perform the rescan
                rescan_result = self.tool_discovery.rescan_tools()

                # Update the registry with new tools
                new_tools = self.tool_discovery.discover_tools()
                self.tool_registry.update_registry(new_tools)

                # Return rescan results
                response_data = {
                    "status": "success",
                    "tools_added": rescan_result.tools_added,
                    "tools_updated": rescan_result.tools_updated,
                    "tools_removed": rescan_result.tools_removed,
                    "total_tools": rescan_result.total_tools,
                    "errors": rescan_result.errors,
                    "timestamp": datetime.now().isoformat(),
                }

                logger.info(
                    f"Rescan completed: {len(rescan_result.tools_added)} added, "
                    f"{len(rescan_result.tools_updated)} updated, "
                    f"{len(rescan_result.tools_removed)} removed"
                )

                return JSONResponse(response_data)

            except Exception as e:
                logger.error(f"Error during rescan: {e}")
                return JSONResponse(
                    {"status": "error", "message": f"Rescan failed: {str(e)}", "timestamp": datetime.now().isoformat()},
                    status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Continue with normal request processing
        return await call_next(request)
