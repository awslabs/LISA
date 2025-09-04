"""Tool adapters for wrapping tools for MCP server integration."""

from abc import ABC, abstractmethod
from typing import Any, Dict
import asyncio
import inspect
import logging

from ..core.base_tool import BaseTool, ToolInfo, ToolType


logger = logging.getLogger(__name__)


class ToolAdapter(ABC):
    """Base class for tool adapters."""
    
    def __init__(self, tool_info: ToolInfo):
        self.tool_info = tool_info
    
    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the tool with the given arguments."""
        pass
    
    @property
    def name(self) -> str:
        """Get the tool name."""
        return self.tool_info.name
    
    @property
    def description(self) -> str:
        """Get the tool description."""
        return self.tool_info.description
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """Get the tool parameters schema."""
        return self.tool_info.parameters


class BaseToolAdapter(ToolAdapter):
    """Adapter for BaseTool class instances."""
    
    def __init__(self, tool_info: ToolInfo):
        if tool_info.tool_type != ToolType.CLASS_BASED:
            raise ValueError("BaseToolAdapter requires a class-based tool")
        
        if not isinstance(tool_info.tool_instance, BaseTool):
            raise ValueError("Tool instance must be a BaseTool instance")
        
        super().__init__(tool_info)
        self.tool_instance: BaseTool = tool_info.tool_instance
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the BaseTool instance."""
        try:
            # Call the tool's execute method
            result = await self.tool_instance.execute(**arguments)
            return result
        except Exception as e:
            logger.error(f"Error executing tool {self.name}: {e}")
            raise


class FunctionToolAdapter(ToolAdapter):
    """Adapter for @mcp_tool decorated functions."""
    
    def __init__(self, tool_info: ToolInfo):
        if tool_info.tool_type != ToolType.FUNCTION_BASED:
            raise ValueError("FunctionToolAdapter requires a function-based tool")
        
        if not callable(tool_info.tool_instance):
            raise ValueError("Tool instance must be callable")
        
        super().__init__(tool_info)
        self.function = tool_info.tool_instance
    
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the decorated function."""
        try:
            # Check if the function is async
            if asyncio.iscoroutinefunction(self.function):
                result = await self.function(**arguments)
            else:
                # Run sync function in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: self.function(**arguments))
            
            return result
        except Exception as e:
            logger.error(f"Error executing function tool {self.name}: {e}")
            raise


def create_adapter(tool_info: ToolInfo) -> ToolAdapter:
    """
    Create the appropriate adapter for a tool.
    
    Args:
        tool_info: Information about the tool
        
    Returns:
        Appropriate adapter instance
    """
    if tool_info.tool_type == ToolType.CLASS_BASED:
        return BaseToolAdapter(tool_info)
    elif tool_info.tool_type == ToolType.FUNCTION_BASED:
        return FunctionToolAdapter(tool_info)
    else:
        raise ValueError(f"Unknown tool type: {tool_info.tool_type}")
