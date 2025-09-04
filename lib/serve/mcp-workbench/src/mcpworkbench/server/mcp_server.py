"""MCP Workbench HTTP server implementation."""

import asyncio
import logging
from typing import Dict, Any, List
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from ..config.models import ServerConfig
from ..core.tool_discovery import ToolDiscovery
from ..core.tool_registry import ToolRegistry
from ..adapters.tool_adapter import create_adapter, ToolAdapter
from .middleware import CORSMiddleware, ExitRouteMiddleware, RescanMiddleware

# Note: The actual MCP Python SDK import will need to be adjusted based on the real SDK
# For now, this is a placeholder structure that can be adapted
try:
    from mcp import Server as MCPServer, Tool as MCPTool
    from mcp.http import HTTPTransport
    MCP_AVAILABLE = True
except ImportError:
    # Fallback for development/testing
    MCP_AVAILABLE = False
    logging.warning("MCP SDK not available - using mock implementation")


logger = logging.getLogger(__name__)


class MCPWorkbenchServer:
    """MCP Workbench HTTP server."""
    
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
        self.tool_adapters: Dict[str, ToolAdapter] = {}
        
        # Create the ASGI application
        self.app = self._create_app()
        
        # Initialize MCP server if available
        self.mcp_server = None
        if MCP_AVAILABLE:
            self._setup_mcp_server()
        else:
            logger.warning("Running without MCP SDK - tools will be served via REST API only")
    
    def _create_app(self) -> Starlette:
        """Create the ASGI application with routes and middleware."""
        # Define routes
        routes = [
            Route(f"{self.config.mcp_route_path}/tools", self._list_tools, methods=["GET"]),
            Route(f"{self.config.mcp_route_path}/tools/{{tool_name}}", self._get_tool, methods=["GET"]),
            Route(f"{self.config.mcp_route_path}/tools/{{tool_name}}/call", self._call_tool, methods=["POST"]),
        ]
        
        # If MCP SDK is available, add MCP-specific routes
        if MCP_AVAILABLE:
            routes.extend([
                Route(f"{self.config.mcp_route_path}/mcp", self._handle_mcp_request, methods=["POST"]),
            ])
        
        app = Starlette(routes=routes)
        
        # Add middleware in reverse order (last added = first executed)
        self._setup_middleware(app)
        
        return app
    
    def _setup_middleware(self, app: Starlette):
        """Setup middleware for the application."""
        # Add conditional middleware based on configuration
        if self.config.rescan_route_path:
            app.add_middleware(
                RescanMiddleware,
                rescan_path=self.config.rescan_route_path,
                tool_discovery=self.tool_discovery,
                tool_registry=self.tool_registry
            )
        
        if self.config.exit_route_path:
            app.add_middleware(ExitRouteMiddleware, exit_path=self.config.exit_route_path)
        
        # Always add CORS middleware
        app.add_middleware(CORSMiddleware, cors_config=self.config.cors_settings)
    
    def _setup_mcp_server(self):
        """Setup the MCP server integration."""
        if not MCP_AVAILABLE:
            return
        
        # This is a placeholder - the actual implementation will depend on the MCP SDK API
        try:
            self.mcp_server = MCPServer("mcpworkbench")
            # Register tools with MCP server will be done in register_tools method
        except Exception as e:
            logger.error(f"Failed to setup MCP server: {e}")
            self.mcp_server = None
    
    async def register_tools(self, tools: List[Any]):
        """Register tools with the server."""
        self.tool_adapters.clear()
        
        for tool_info in tools:
            try:
                adapter = create_adapter(tool_info)
                self.tool_adapters[tool_info.name] = adapter
                
                # Register with MCP server if available
                if self.mcp_server and MCP_AVAILABLE:
                    await self._register_tool_with_mcp(adapter)
                
            except Exception as e:
                logger.error(f"Failed to register tool {tool_info.name}: {e}")
    
    async def _register_tool_with_mcp(self, adapter: ToolAdapter):
        """Register a tool with the MCP server."""
        if not self.mcp_server:
            return
        
        # This is a placeholder - actual implementation depends on MCP SDK
        try:
            # Create MCP tool definition
            mcp_tool = MCPTool(
                name=adapter.name,
                description=adapter.description,
                parameters=adapter.parameters
            )
            
            # Register the tool with the MCP server
            await self.mcp_server.register_tool(mcp_tool, adapter.execute)
            
        except Exception as e:
            logger.error(f"Failed to register tool {adapter.name} with MCP server: {e}")
    
    async def _list_tools(self, request):
        """List all available tools (REST API endpoint)."""
        tools = []
        for adapter in self.tool_adapters.values():
            tools.append({
                "name": adapter.name,
                "description": adapter.description,
                "parameters": adapter.parameters
            })
        
        return JSONResponse({
            "tools": tools,  
            "count": len(tools)
        })
    
    async def _get_tool(self, request):
        """Get information about a specific tool (REST API endpoint)."""
        tool_name = request.path_params["tool_name"]
        
        if tool_name not in self.tool_adapters:
            return JSONResponse(
                {"error": f"Tool '{tool_name}' not found"},
                status_code=404
            )
        
        adapter = self.tool_adapters[tool_name]
        return JSONResponse({
            "name": adapter.name,
            "description": adapter.description,
            "parameters": adapter.parameters
        })
    
    async def _call_tool(self, request):
        """Execute a tool (REST API endpoint)."""
        tool_name = request.path_params["tool_name"]
        
        if tool_name not in self.tool_adapters:
            return JSONResponse(
                {"error": f"Tool '{tool_name}' not found"},
                status_code=404
            )
        
        try:
            # Parse request body
            body = await request.json()
            arguments = body.get("arguments", {})
            
            # Execute the tool
            adapter = self.tool_adapters[tool_name]
            result = await adapter.execute(arguments)
            
            return JSONResponse({
                "result": result,
                "tool": tool_name
            })
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return JSONResponse(
                {"error": f"Tool execution failed: {str(e)}"},
                status_code=500
            )
    
    async def _handle_mcp_request(self, request):
        """Handle MCP protocol requests."""
        if not self.mcp_server:
            return JSONResponse(
                {"error": "MCP server not available"},
                status_code=503
            )
        
        try:
            # Parse MCP request
            body = await request.json()
            
            # Forward to MCP server (placeholder implementation)
            # The actual implementation will depend on the MCP SDK
            response = await self.mcp_server.handle_request(body)
            
            return JSONResponse(response)
            
        except Exception as e:
            logger.error(f"Error handling MCP request: {e}")
            return JSONResponse(
                {"error": f"MCP request failed: {str(e)}"},
                status_code=500
            )
    
    async def start(self):
        """Start the server."""
        # Discover and register initial tools
        logger.info("Discovering initial tools...")
        tools = self.tool_discovery.discover_tools()
        self.tool_registry.register_tools(tools)
        await self.register_tools(tools)
        
        logger.info(f"Registered {len(tools)} tools")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")
        
        # Start the HTTP server
        logger.info(f"Starting MCP Workbench server on {self.config.server_host}:{self.config.server_port}")
        
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
        asyncio.run(self.start())
