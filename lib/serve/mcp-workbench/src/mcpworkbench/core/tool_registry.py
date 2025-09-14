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

"""Tool registry component for MCP Workbench."""

import threading
from typing import Dict, List, Optional
import logging

from .base_tool import ToolInfo


logger = logging.getLogger(__name__)


class ToolRegistry:
    """Thread-safe registry for managing discovered tools."""
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, ToolInfo] = {}
        self._lock = threading.RLock()
    
    def register_tool(self, tool_info: ToolInfo) -> None:
        """
        Register a tool in the registry.
        
        Args:
            tool_info: Information about the tool to register
        """
        with self._lock:
            self._tools[tool_info.name] = tool_info
            logger.info(f"Registered tool: {tool_info.name}")
    
    def register_tools(self, tools: List[ToolInfo]) -> None:
        """
        Register multiple tools in the registry.
        
        Args:
            tools: List of tools to register
        """
        with self._lock:
            for tool in tools:
                self._tools[tool.name] = tool
            logger.info(f"Registered {len(tools)} tools")
    
    def unregister_tool(self, tool_name: str) -> bool:
        """
        Unregister a tool from the registry.
        
        Args:
            tool_name: Name of the tool to unregister
            
        Returns:
            True if the tool was found and removed, False otherwise
        """
        with self._lock:
            if tool_name in self._tools:
                del self._tools[tool_name]
                logger.info(f"Unregistered tool: {tool_name}")
                return True
            return False
    
    def get_tool(self, tool_name: str) -> Optional[ToolInfo]:
        """
        Get a tool by name.
        
        Args:
            tool_name: Name of the tool to retrieve
            
        Returns:
            ToolInfo if found, None otherwise
        """
        with self._lock:
            return self._tools.get(tool_name)
    
    def list_tools(self) -> List[ToolInfo]:
        """
        Get a list of all registered tools.
        
        Returns:
            List of all registered tools
        """
        with self._lock:
            return list(self._tools.values())
    
    def list_tool_names(self) -> List[str]:
        """
        Get a list of all registered tool names.
        
        Returns:
            List of all registered tool names
        """
        with self._lock:
            return list(self._tools.keys())
    
    def clear(self) -> None:
        """Clear all tools from the registry."""
        with self._lock:
            self._tools.clear()
            logger.info("Cleared all tools from registry")
    
    def update_registry(self, new_tools: List[ToolInfo]) -> None:
        """
        Update the registry with a new set of tools.
        This replaces all existing tools.
        
        Args:
            new_tools: New list of tools to register
        """
        with self._lock:
            self._tools.clear()
            for tool in new_tools:
                self._tools[tool.name] = tool
            logger.info(f"Updated registry with {len(new_tools)} tools")
    
    def get_tool_count(self) -> int:
        """
        Get the number of registered tools.
        
        Returns:
            Number of registered tools
        """
        with self._lock:
            return len(self._tools)
    
    def has_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is registered.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if the tool is registered, False otherwise
        """
        with self._lock:
            return tool_name in self._tools
