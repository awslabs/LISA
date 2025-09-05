"""MCP Workbench FastMCP 2.0 server implementation."""

import asyncio
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

# Import FastMCP 2.0
try:
    from fastmcp import FastMCP
    FASTMCP_AVAILABLE = True
except ImportError:
    # Fallback for development/testing
    FASTMCP_AVAILABLE = False
    logging.warning("FastMCP 2.0 not available")


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
        
        if not FASTMCP_AVAILABLE:
            raise ImportError("FastMCP 2.0 is required but not available")
        
        # Create FastMCP application
        self.app = FastMCP("mcpworkbench")
        logger.info("FastMCP 2.0 server initialized")
        
        # Register built-in management tools
        self._register_management_tools()
    
    def _register_management_tools(self):
        """Register built-in management tools for rescan and exit functionality."""
        
        if self.config.rescan_route_path:
            @self.app.tool(
                name="rescan_tools",
                description="Rescan the tools directory and reload all available tools"
            )
            async def rescan_tools() -> dict:
                """Rescan tools directory and reload tools."""
                try:
                    logger.info("Rescanning tools directory...")
                    
                    # Discover new tools
                    tools = self.tool_discovery.discover_tools()
                    old_count = len(self.registered_tools)
                    
                    # Clear existing registered tools (except management tools)
                    management_tools = {"rescan_tools", "exit_server"}
                    tools_to_remove = [name for name in self.registered_tools.keys() 
                                     if name not in management_tools]
                    
                    for tool_name in tools_to_remove:
                        # Note: FastMCP 2.0 may not have tool unregistration
                        # This is a limitation we'll document
                        pass
                    
                    # Register new tools
                    self.tool_registry.register_tools(tools)
                    await self._register_discovered_tools(tools)
                    
                    # Calculate changes
                    new_tools = [tool.name for tool in tools if tool.name not in self.registered_tools]
                    updated_tools = [tool.name for tool in tools if tool.name in self.registered_tools]
                    
                    result = {
                        "status": "success",
                        "tools_added": new_tools,
                        "tools_updated": updated_tools,
                        "tools_removed": [],  # FastMCP limitation
                        "total_tools": len(tools),
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    
                    logger.info(f"Rescan completed: {result}")
                    return result
                    
                except Exception as e:
                    logger.error(f"Error during rescan: {e}")
                    return {
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
        
        if self.config.exit_route_path:
            @self.app.tool(
                name="exit_server",
                description="Gracefully shutdown the MCP Workbench server"
            )
            async def exit_server() -> dict:
                """Exit the server gracefully."""
                logger.info("Exit requested via MCP tool")
                
                # Schedule shutdown after response is sent
                async def delayed_shutdown():
                    await asyncio.sleep(1)
                    logger.info("Shutting down server...")
                    sys.exit(0)
                
                asyncio.create_task(delayed_shutdown())
                
                return {
                    "status": "success",
                    "message": "Server shutdown initiated",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
    
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
        
        # Start FastMCP server
        logger.info(f"Starting MCP Workbench server on {self.config.server_host}:{self.config.server_port}")
        
        # FastMCP 2.0 server startup (API may vary)
        try:
            # This API might be different in FastMCP 2.0
            await self.app.run_http_async(
                transport="streamable-http",
                host=self.config.server_host,
                port=self.config.server_port
            )
        except AttributeError as e:
            # Fallback if API is different
            logger.info(f"Using alternative FastMCP startup method: {e.message}")
            # Alternative startup method - this will need to be adjusted based on actual API
            import uvicorn
            config = uvicorn.Config(
                self.app,
                host=self.config.server_host,
                port=self.config.server_port,
                log_level="info"
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
