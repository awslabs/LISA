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

"""MCP Workbench FastMCP 2.0 server implementation."""

import asyncio
import inspect
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from ..aws.aws_routes import router as aws_router
from ..config.models import ServerConfig
from ..core.base_tool import BaseTool
from ..core.tool_discovery import ToolDiscovery, ToolInfo, ToolType
from ..core.tool_registry import ToolRegistry
from .auth import is_idp_used, OIDCHTTPBearer
from .middleware import CORSMiddleware, wrap_asgi_with_cors_headers

logger = logging.getLogger(__name__)


def _utc_iso_z() -> str:
    """UTC instant as ISO-8601 with Z suffix (RFC 3339)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MCPWorkbenchServer:
    """MCP Workbench server using pure FastMCP 2.0."""

    def __init__(self, config: ServerConfig, tool_discovery: ToolDiscovery, tool_registry: ToolRegistry):
        """
        Initialize the MCP Workbench server.

        Args:
            config: Server configuration
            tool_discovery: Tool discovery instance
            tool_registry: Tool registry instance
        """
        self.config = config
        self.tool_discovery = tool_discovery
        self.tool_registry = tool_registry
        self.registered_tools: dict[str, Any] = {}

        # Create FastMCP application
        self.app = FastMCP("mcpworkbench")
        logger.info("FastMCP 2.0 server initialized")

        # Register built-in management tools
        self._register_management_tools()

    def _register_management_tools(self) -> None:
        """Register built-in management tools - now removed as they are HTTP routes."""
        # Management functionality moved to HTTP GET endpoints
        pass

    def _add_management_routes(self, app: Starlette) -> None:
        if self.config.exit_route_path:

            async def exit_endpoint(request: Request) -> JSONResponse:
                """HTTP GET endpoint to gracefully shutdown the server."""
                logger.info("Exit requested via HTTP endpoint")

                # Schedule shutdown after response is sent
                async def delayed_shutdown() -> None:
                    await asyncio.sleep(1)
                    logger.info("Shutting down server...")
                    sys.exit(0)

                asyncio.create_task(delayed_shutdown())

                result = {
                    "status": "success",
                    "message": "Server shutdown initiated",
                    "timestamp": _utc_iso_z(),
                }
                return JSONResponse(result)

            app.add_route(self.config.exit_route_path, exit_endpoint, methods=["GET"])

        if self.config.rescan_route_path:

            async def rescan_endpoint(request: Request) -> JSONResponse:
                """HTTP GET endpoint to rescan tools directory and reload tools."""
                try:
                    logger.info("Rescanning tools directory via HTTP...")

                    # Use the enhanced rescan_tools method which includes module reloading
                    rescan_result = self.tool_discovery.rescan_tools()

                    # Unbind prior FastMCP registrations so deletes take effect and same-name tools pick up
                    # new callables after file edits (FastMCP 2.10+ remove_tool).
                    to_unbind = set(rescan_result.tools_removed) | set(rescan_result.tools_updated)
                    remove_fn = getattr(self.app, "remove_tool", None)
                    if callable(remove_fn):
                        for name in to_unbind:
                            try:
                                remove_fn(name)
                                logger.debug("FastMCP remove_tool before rescan reconcile: %s", name)
                            except Exception as rm_err:
                                logger.warning("Could not remove tool %s from FastMCP: %s", name, rm_err)
                    elif to_unbind:
                        logger.warning(
                            "FastMCP has no remove_tool(); rescan may not reflect deletes or in-place "
                            "updates for tools %s until process restart",
                            sorted(to_unbind),
                        )

                    self.registered_tools.clear()

                    tools = list(self.tool_discovery.current_tools.values())
                    self.tool_registry.update_registry(tools)
                    await self._register_discovered_tools(tools)

                    # Build result using the rescan_result data
                    result = {
                        "status": "success",
                        "tools_added": rescan_result.tools_added,
                        "tools_updated": rescan_result.tools_updated,
                        "tools_removed": rescan_result.tools_removed,
                        "total_tools": rescan_result.total_tools,
                        "errors": rescan_result.errors,
                        "timestamp": _utc_iso_z(),
                    }

                    logger.info(f"Rescan completed: {result}")
                    return JSONResponse(result)

                except Exception as e:
                    logger.error(f"Error during rescan: {e}")
                    error_result = {
                        "status": "error",
                        "error": str(e),
                        "timestamp": _utc_iso_z(),
                    }
                    return JSONResponse(error_result, status_code=HTTP_500_INTERNAL_SERVER_ERROR)

            app.add_route(self.config.rescan_route_path, rescan_endpoint, methods=["GET"])

    def _create_starlette_app(self) -> Starlette:
        """Create Starlette application with MCP and HTTP routes."""

        mcp_app = self.app.http_app(path="/", transport="streamable-http", stateless_http=True)

        async def health_check(request: Request) -> JSONResponse:
            """Health check endpoint for Docker health checks."""
            return JSONResponse({"status": "healthy", "service": "mcpworkbench"})

        logger.info(f"CORS Allowed Origins: {self.config.cors_settings.allow_origins}")
        # Auth only on mounted apps; CORS is applied at the root Starlette app so OPTIONS preflight
        # is handled before routing (avoids FastMCP 500 on OPTIONS and missing ACAO on errors).
        if is_idp_used():
            mcp_app.add_middleware(OIDCHTTPBearer)
        else:
            logger.info(
                "USE_AUTH is false or unset: OIDC/API-token auth middleware is disabled (same as Serve REST API)."
            )

        # Add MCP mount
        # GET /v2/mcp/ returns 200 so MCP clients (e.g. use-mcp) that probe with GET
        # for SSE support don't surface a 405 error in the browser console.
        async def mcp_get_probe(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok", "transport": "streamable-http", "stateless": True})

        routes = [
            Route("/health", health_check),
            Route("/v2/mcp", mcp_get_probe, methods=["GET"]),
            Mount("/v2/mcp", mcp_app),
        ]

        # Mount AWS session management routes under /api/aws
        from fastapi import FastAPI  # noqa: PLC0415

        aws_app = FastAPI()
        if is_idp_used():
            aws_app.add_middleware(OIDCHTTPBearer)
        aws_app.include_router(aws_router)
        routes.append(Mount("/api/aws", aws_app))

        self._add_management_routes(mcp_app)

        return Starlette(
            routes=routes,
            middleware=[Middleware(CORSMiddleware, cors_config=self.config.cors_settings)],
            lifespan=mcp_app.lifespan,
        )

    async def _register_discovered_tools(self, tools: list[ToolInfo]) -> None:
        """Register discovered tools with FastMCP."""
        for tool_info in tools:
            try:
                await self._register_single_tool(tool_info)
            except Exception as e:
                logger.error(f"Failed to register tool {tool_info.name}: {e}")

    async def _register_single_tool(self, tool_info: ToolInfo) -> None:
        """Register a single discovered tool with FastMCP."""
        if tool_info.tool_type == ToolType.CLASS_BASED:
            await self._register_class_tool(tool_info)
        elif tool_info.tool_type == ToolType.FUNCTION_BASED:
            await self._register_function_tool(tool_info)
        else:
            logger.error(f"Unknown tool type for {tool_info.name}: {tool_info.tool_type}")

    async def _register_class_tool(self, tool_info: ToolInfo) -> None:
        """Register a class-based tool with FastMCP."""
        if not isinstance(tool_info.tool_instance, BaseTool):
            raise ValueError(f"Class tool {tool_info.name} instance must be a BaseTool")

        tool_instance = tool_info.tool_instance

        tool = await tool_instance.execute()

        # Register with FastMCP using the tool's metadata
        self.app.tool(
            name=tool_info.name,
            description=tool_info.description,
        )(tool)

        self.registered_tools[tool_info.name] = tool_info
        logger.debug(f"Registered class-based tool: {tool_info.name}")

    async def _register_function_tool(self, tool_info: ToolInfo) -> None:
        """Register a function-based tool with FastMCP."""
        if not callable(tool_info.tool_instance):
            raise ValueError(f"Function tool {tool_info.name} instance must be callable")

        function = tool_info.tool_instance

        # Check if function is async
        is_async = inspect.iscoroutinefunction(function)

        if is_async:
            # Function is already async
            wrapper_func = function
        else:
            # Wrap sync function to be async
            async def async_wrapper(**kwargs: Any) -> Any:
                return function(**kwargs)

            wrapper_func = async_wrapper

        # Register with FastMCP using the tool's metadata
        self.app.tool(
            name=tool_info.name,
            description=tool_info.description,
        )(wrapper_func)

        self.registered_tools[tool_info.name] = tool_info
        logger.debug(f"Registered function-based tool: {tool_info.name}")

    async def discover_and_register_tools(self) -> list[ToolInfo]:
        """Discover and register initial tools."""
        logger.info("Discovering initial tools...")
        tools = self.tool_discovery.discover_tools()
        self.tool_registry.register_tools(tools)
        await self._register_discovered_tools(tools)

        logger.info(f"Registered {len(tools)} tools")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")

        return tools

    async def start(self) -> None:
        """Start the server."""
        # Discover and register tools
        await self.discover_and_register_tools()

        # Create Starlette app with both MCP and HTTP routes
        starlette_app = self._create_starlette_app()
        # Outer ASGI wrapper so 500s from ServerErrorMiddleware still get CORS headers (browser can read body)
        asgi_app = wrap_asgi_with_cors_headers(starlette_app, self.config.cors_settings)

        # Start server with Starlette app
        logger.info(f"Starting MCP Workbench server on {self.config.server_host}:{self.config.server_port}")
        logger.info("Available endpoints:")
        logger.info("  - MCP Protocol: /v2/mcp")

        if self.config.rescan_route_path:
            logger.info(f"  - Rescan Tools: GET {self.config.rescan_route_path}")
        if self.config.exit_route_path:
            logger.info(f"  - Exit Server: GET {self.config.exit_route_path}")

        # Use uvicorn to serve the Starlette app
        import uvicorn  # noqa: PLC0415

        config = uvicorn.Config(
            asgi_app,
            host=self.config.server_host,
            port=self.config.server_port,
            log_level="info",
            forwarded_allow_ips="*",
        )
        server = uvicorn.Server(config)
        await server.serve()

    def run(self) -> None:
        """Run the server (blocking)."""
        # Use a more robust approach to handle event loops
        asyncio.run(self.start())
