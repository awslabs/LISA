"""Tool discovery component for MCP Workbench."""

import importlib.util
import inspect
import os
import sys
from pathlib import Path
from typing import Dict, List, Set
import logging

from pydantic import BaseModel
from .base_tool import BaseTool, ToolInfo, ToolType
from .annotations import is_mcp_tool, get_tool_metadata


logger = logging.getLogger(__name__)


class RescanResult(BaseModel):
    """Result of a tool directory rescan."""
    
    tools_added: List[str] = []
    tools_updated: List[str] = []
    tools_removed: List[str] = []
    total_tools: int = 0
    errors: List[str] = []


class ToolDiscovery:
    """Discovers and loads tools from Python files."""
    
    def __init__(self, tools_directory: str):
        """
        Initialize the tool discovery.
        
        Args:
            tools_directory: Path to directory containing tool files
        """
        self.tools_directory = Path(tools_directory)
        self.loaded_modules: Dict[str, any] = {}
        self.current_tools: Dict[str, ToolInfo] = {}
        
        if not self.tools_directory.exists():
            raise ValueError(f"Tools directory does not exist: {tools_directory}")
        
        if not self.tools_directory.is_dir():
            raise ValueError(f"Tools directory is not a directory: {tools_directory}")
    
    def discover_tools(self) -> List[ToolInfo]:
        """
        Discover all tools in the tools directory.
        
        Returns:
            List of discovered tool information
        """
        tools = []
        
        # Find all Python files in the directory
        python_files = list(self.tools_directory.glob("*.py"))
        
        for file_path in python_files:
            try:
                file_tools = self._discover_tools_in_file(file_path)
                tools.extend(file_tools)
            except Exception as e:
                logger.error(f"Error discovering tools in {file_path}: {e}")
                continue
        
        # Update current tools tracking
        self.current_tools = {tool.name: tool for tool in tools}
        
        return tools
    
    def rescan_tools(self) -> RescanResult:
        """
        Rescan the tools directory and return changes.
        
        Returns:
            RescanResult with information about changes
        """
        result = RescanResult()
        
        # Store current tool names for comparison
        old_tool_names = set(self.current_tools.keys())
        
        # Clear loaded modules to force reload
        self.loaded_modules.clear()
        
        # Discover tools fresh
        try:
            new_tools = self.discover_tools()
            new_tool_names = set(tool.name for tool in new_tools)
            
            # Calculate changes
            result.tools_added = list(new_tool_names - old_tool_names)
            result.tools_removed = list(old_tool_names - new_tool_names)
            
            # For tools that exist in both, check if they've been updated
            # (This is a simple check - in practice you might want to compare timestamps or content hashes)
            common_tools = new_tool_names & old_tool_names
            result.tools_updated = list(common_tools)  # Assume all common tools are updated for safety
            
            result.total_tools = len(new_tools)
            
        except Exception as e:
            result.errors.append(f"Error during rescan: {str(e)}")
            logger.error(f"Error during rescan: {e}")
        
        return result
    
    def _discover_tools_in_file(self, file_path: Path) -> List[ToolInfo]:
        """
        Discover tools in a single Python file.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            List of tools found in the file
        """
        tools = []
        
        try:
            # Create module name from file path
            module_name = f"mcpworkbench_tools_{file_path.stem}"
            
            # Load the module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                logger.warning(f"Could not create module spec for {file_path}")
                return tools
            
            module = importlib.util.module_from_spec(spec)
            
            # Add to sys.modules to handle imports within the module
            sys.modules[module_name] = module
            
            try:
                spec.loader.exec_module(module)
                self.loaded_modules[str(file_path)] = module
            except Exception as e:
                logger.error(f"Error executing module {file_path}: {e}")
                return tools
            
            # Inspect the module for tools
            tools.extend(self._find_class_based_tools(module, file_path, module_name))
            tools.extend(self._find_function_based_tools(module, file_path, module_name))
            
        except Exception as e:
            logger.error(f"Error loading module from {file_path}: {e}")
        
        return tools
    
    def _find_class_based_tools(self, module, file_path: Path, module_name: str) -> List[ToolInfo]:
        """Find BaseTool subclasses in the module."""
        tools = []
        
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Skip imported classes (only look at classes defined in this module)
            if obj.__module__ != module_name:
                continue
            
            # Check if it's a subclass of BaseTool (but not BaseTool itself)
            if (issubclass(obj, BaseTool) and obj != BaseTool and
                not inspect.isabstract(obj)):
                
                try:
                    # Try to instantiate the tool to get its metadata
                    # We need to handle different constructor signatures
                    sig = inspect.signature(obj.__init__)
                    params = list(sig.parameters.keys())[1:]  # Skip 'self'
                    
                    if len(params) == 2 and 'name' in params and 'description' in params:
                        # Standard BaseTool signature - we need to provide name and description
                        # Try to get them from class attributes or use defaults
                        tool_name = getattr(obj, 'name', name.lower())
                        tool_description = getattr(obj, 'description', f"Tool: {name}")
                        instance = obj(name=tool_name, description=tool_description)
                    else:
                        # Custom constructor - try to instantiate with no args
                        instance = obj()
                    
                    # Get tool metadata
                    tool_name = getattr(instance, 'name', name.lower())
                    tool_description = getattr(instance, 'description', f"Tool: {name}")
                    parameters = instance.get_parameters() if hasattr(instance, 'get_parameters') else {}
                    
                    tool_info = ToolInfo(
                        name=tool_name,
                        description=tool_description,
                        tool_type=ToolType.CLASS_BASED,
                        file_path=str(file_path),
                        module_name=module_name,
                        class_name=name,
                        tool_instance=instance,
                        parameters=parameters
                    )
                    
                    tools.append(tool_info)
                    
                except Exception as e:
                    logger.error(f"Error instantiating tool class {name} from {file_path}: {e}")
                    continue
        
        return tools
    
    def _find_function_based_tools(self, module, file_path: Path, module_name: str) -> List[ToolInfo]:
        """Find @mcp_tool decorated functions in the module."""
        tools = []
        
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            # Skip imported functions (only look at functions defined in this module)
            if obj.__module__ != module_name:
                continue
            
            if is_mcp_tool(obj):
                try:
                    metadata = get_tool_metadata(obj)
                    
                    tool_info = ToolInfo(
                        name=metadata['name'],
                        description=metadata['description'],
                        tool_type=ToolType.FUNCTION_BASED,
                        file_path=str(file_path),
                        module_name=module_name,
                        function_name=name,
                        tool_instance=obj,
                        parameters=metadata['parameters']
                    )
                    
                    tools.append(tool_info)
                    
                except Exception as e:
                    logger.error(f"Error processing tool function {name} from {file_path}: {e}")
                    continue
        
        return tools
