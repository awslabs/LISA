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
from datetime import datetime
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware as StarletteCORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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
                    status_code=500,
                )

        # Continue with normal request processing
        return await call_next(request)
