"""Base tool class and related data structures."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, Callable
from pydantic import BaseModel, Field
from enum import Enum


class ToolType(str, Enum):
    """Types of tools that can be discovered."""
    CLASS_BASED = "class_based"
    FUNCTION_BASED = "function_based"


class ToolInfo(BaseModel):
    """Information about a discovered tool."""
    
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    tool_type: ToolType = Field(..., description="Type of tool (class or function based)")
    file_path: str = Field(..., description="Path to the file containing the tool")
    module_name: str = Field(..., description="Python module name")
    
    # For class-based tools
    class_name: Optional[str] = Field(default=None, description="Class name for class-based tools")
    
    # For function-based tools
    function_name: Optional[str] = Field(default=None, description="Function name for function-based tools")
    
    # Tool instance or function reference (not serialized)
    tool_instance: Optional[Union[Any, Callable]] = Field(default=None, exclude=True, description="Tool instance or function")


class BaseTool(ABC):
    """Abstract base class for MCP tools."""
    
    def __init__(self, name: str, description: str):
        """
        Initialize the tool with required metadata.
        
        Args:
            name: The name of the tool
            description: A description of what the tool does
        """
        self.name = name
        self.description = description
    
    @abstractmethod
    async def execute(self) -> Callable[..., Any]:
        """
        Returns an function to be executed as the tool.
            
        Returns:
            The function to be executed
        """
        pass
