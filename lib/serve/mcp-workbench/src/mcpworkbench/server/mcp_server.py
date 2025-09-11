"""MCP Workbench FastMCP 2.0 server implementation."""

import asyncio
import contextlib
import inspect
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..config.models import ServerConfig
from ..core.tool_discovery import ToolDiscovery
from ..core.tool_registry import ToolRegistry
from ..core.tool_discovery import ToolInfo, ToolType
from ..core.base_tool import BaseTool

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


logger = logging.getLogger(__name__)


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
        self.registered_tools: Dict[str, Any] = {}
        
        # Create FastMCP application
        self.app = FastMCP("mcpworkbench")
        logger.info("FastMCP 2.0 server initialized")
        
        # Register built-in management tools
        self._register_management_tools()
    
    def _register_management_tools(self):
        """Register built-in management tools - now removed as they are HTTP routes."""
        # Management functionality moved to HTTP GET endpoints
        pass

    
    def _add_management_routes(self, app: Starlette):
        if self.config.exit_route_path:
            async def exit_endpoint(request):
                """HTTP GET endpoint to gracefully shutdown the server."""
                logger.info("Exit requested via HTTP endpoint")
                
                # Schedule shutdown after response is sent
                async def delayed_shutdown():
                    await asyncio.sleep(1)
                    logger.info("Shutting down server...")
                    sys.exit(0)
                
                asyncio.create_task(delayed_shutdown())
                
                result = {
                    "status": "success",
                    "message": "Server shutdown initiated",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                return JSONResponse(result)
            
            app.add_route(self.config.exit_route_path, exit_endpoint, methods=['GET'])

        if self.config.rescan_route_path:
            async def rescan_endpoint(request):
                """HTTP GET endpoint to rescan tools directory and reload tools."""
                try:
                    logger.info("Rescanning tools directory via HTTP...")
                    
                    # Use the enhanced rescan_tools method which includes module reloading
                    rescan_result = self.tool_discovery.rescan_tools()
                    
                    # Clear existing registered tools tracking
                    # Note: FastMCP 2.0 may not have tool unregistration
                    # This is a limitation we'll document
                    old_registered_tools = self.registered_tools.copy()
                    self.registered_tools.clear()
                    
                    # Get the newly discovered tools and register them
                    tools = list(self.tool_discovery.current_tools.values())
                    self.tool_registry.register_tools(tools)
                    await self._register_discovered_tools(tools)
                    
                    # Build result using the rescan_result data
                    result = {
                        "status": "success",
                        "tools_added": rescan_result.tools_added,
                        "tools_updated": rescan_result.tools_updated,
                        "tools_removed": rescan_result.tools_removed,
                        "total_tools": rescan_result.total_tools,
                        "errors": rescan_result.errors,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    
                    logger.info(f"Rescan completed: {result}")
                    return JSONResponse(result)
                    
                except Exception as e:
                    logger.error(f"Error during rescan: {e}")
                    error_result = {
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    return JSONResponse(error_result, status_code=500)
                
            app.add_route(self.config.rescan_route_path, rescan_endpoint, methods=['GET'])


    def _create_starlette_app(self):
        """Create Starlette application with MCP and HTTP routes."""

        mcp_app = self.app.http_app(
            path="/",
            transport="streamable-http",
            stateless_http=True
        )

        async def health_check(request):
            """Health check endpoint for Docker health checks."""
            return JSONResponse({"status": "healthy", "service": "mcpworkbench"})

        logger.info(f"CORS Allowed Origins: {self.config.cors_settings.allow_origins}")
        mcp_app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_settings.allow_origins,
            allow_methods=self.config.cors_settings.allow_methods,
            allow_headers=self.config.cors_settings.allow_headers,
        )
        
        # Add MCP mount
        routes = [
            Route("/health", health_check),
            Mount("/v2/mcp", mcp_app),
        ]
        
        self._add_management_routes(mcp_app)
        
        return Starlette(routes=routes, lifespan=mcp_app.lifespan)
    
    async def _register_discovered_tools(self, tools: List[ToolInfo]):
        """Register discovered tools with FastMCP."""
        for tool_info in tools:
            try:
                await self._register_single_tool(tool_info)
            except Exception as e:
                logger.error(f"Failed to register tool {tool_info.name}: {e}")
    
    async def _register_single_tool(self, tool_info: ToolInfo):
        """Register a single discovered tool with FastMCP."""
        if tool_info.tool_type == ToolType.CLASS_BASED:
            await self._register_class_tool(tool_info)
        elif tool_info.tool_type == ToolType.FUNCTION_BASED:
            await self._register_function_tool(tool_info)
        else:
            logger.error(f"Unknown tool type for {tool_info.name}: {tool_info.tool_type}")
    
    async def _register_class_tool(self, tool_info: ToolInfo):
        """Register a class-based tool with FastMCP."""
        if not isinstance(tool_info.tool_instance, BaseTool):
            raise ValueError(f"Class tool {tool_info.name} instance must be a BaseTool")
        
        tool_instance = tool_info.tool_instance
        
        # # Create wrapper function for FastMCP
        # async def tool_wrapper(**kwargs) -> Any:
        #     return await tool_instance.execute(**kwargs)
        tool = await tool_instance.execute()
        
        # Register with FastMCP using the tool's metadata
        self.app.tool(
            name=tool_info.name,
            description=tool_info.description,
        )(tool)
        
        self.registered_tools[tool_info.name] = tool_info
        logger.debug(f"Registered class-based tool: {tool_info.name}")
    
    async def _register_function_tool(self, tool_info: ToolInfo):
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
            async def async_wrapper(**kwargs):
                return function(**kwargs)
            wrapper_func = async_wrapper
        
        # Register with FastMCP using the tool's metadata
        self.app.tool(
            name=tool_info.name,
            description=tool_info.description,
        )(wrapper_func)
        
        self.registered_tools[tool_info.name] = tool_info
        logger.debug(f"Registered function-based tool: {tool_info.name}")
    
    async def discover_and_register_tools(self):
        """Discover and register initial tools."""
        logger.info("Discovering initial tools...")
        tools = self.tool_discovery.discover_tools()
        self.tool_registry.register_tools(tools)
        await self._register_discovered_tools(tools)
        
        logger.info(f"Registered {len(tools)} tools")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")
        
        return tools
    
    async def start(self):
        """Start the server."""
        # Discover and register tools
        await self.discover_and_register_tools()
        
        # Create Starlette app with both MCP and HTTP routes
        starlette_app = self._create_starlette_app()
        
        # Start server with Starlette app
        logger.info(f"Starting MCP Workbench server on {self.config.server_host}:{self.config.server_port}")
        logger.info("Available endpoints:")
        logger.info("  - MCP Protocol: /v2/mcp")
        
        if self.config.rescan_route_path:
            logger.info(f"  - Rescan Tools: GET {self.config.rescan_route_path}")
        if self.config.exit_route_path:
            logger.info(f"  - Exit Server: GET {self.config.exit_route_path}")
        
        # Use uvicorn to serve the Starlette app
        import uvicorn
        config = uvicorn.Config(
            starlette_app,
            host=self.config.server_host,
            port=self.config.server_port,
            log_level="info",
            forwarded_allow_ips="*"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    def run(self):
        """Run the server (blocking)."""
        # Use a more robust approach to handle event loops
        import threading
        import queue
        
        # Create a queue to get results from the thread
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        asyncio.run(self.start())
