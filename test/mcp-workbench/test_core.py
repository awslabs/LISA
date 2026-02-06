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

"""Tests for core components."""

from pathlib import Path

import pytest
from mcpworkbench.core.annotations import get_tool_metadata, is_mcp_tool, mcp_tool
from mcpworkbench.core.base_tool import BaseTool, ToolInfo, ToolType
from mcpworkbench.core.tool_discovery import RescanResult, ToolDiscovery
from mcpworkbench.core.tool_registry import ToolRegistry


class TestBaseTool:
    """Test BaseTool abstract class."""

    def test_base_tool_instantiation(self):
        """Test that BaseTool cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseTool("test", "test description")

    def test_concrete_tool_implementation(self):
        """Test concrete implementation of BaseTool."""

        class ConcreteTool(BaseTool):
            def get_parameters(self):
                return {}

            async def execute(self, **kwargs):
                return {"result": "test"}

        tool = ConcreteTool("test_tool", "A test tool")
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.get_parameters() == {}


class TestAnnotations:
    """Test mcp_tool annotation functionality."""

    def test_mcp_tool_decorator(self):
        """Test the @mcp_tool decorator."""

        @mcp_tool(name="test_func", description="A test function")
        def test_function():
            return "test"

        assert is_mcp_tool(test_function)
        metadata = get_tool_metadata(test_function)
        assert metadata["name"] == "test_func"
        assert metadata["description"] == "A test function"

    def test_mcp_tool_without_parameters(self):
        """Test @mcp_tool decorator without parameters."""

        @mcp_tool(name="simple_func", description="Simple function")
        def simple_function():
            return "simple"

        assert is_mcp_tool(simple_function)
        metadata = get_tool_metadata(simple_function)
        assert metadata["name"] == "simple_func"

    def test_is_mcp_tool_false(self):
        """Test is_mcp_tool returns False for regular functions."""

        def regular_function():
            return "regular"

        assert not is_mcp_tool(regular_function)

    def test_get_tool_metadata_error(self):
        """Test get_tool_metadata raises error for non-MCP tools."""

        def regular_function():
            return "regular"

        with pytest.raises(ValueError, match="Function is not marked as an MCP tool"):
            get_tool_metadata(regular_function)


class TestToolDiscovery:
    """Test tool discovery functionality."""

    def test_tool_discovery_init(self, temp_tools_dir: Path):
        """Test ToolDiscovery initialization."""
        discovery = ToolDiscovery(str(temp_tools_dir))
        assert discovery.tools_directory == temp_tools_dir

    def test_tool_discovery_invalid_directory(self):
        """Test ToolDiscovery with invalid directory."""
        with pytest.raises(ValueError, match="Tools directory does not exist"):
            ToolDiscovery("/nonexistent/directory")

    def test_discover_tools(self, tool_discovery: ToolDiscovery):
        """Test discovering tools from files."""
        tools = tool_discovery.discover_tools()

        # Should find both function and class-based tools
        assert len(tools) == 3, f"Expected 3 tools, found {len(tools)}: {[t.name for t in tools]}"

        tool_names = [tool.name for tool in tools]
        assert "echo_test" in tool_names, "echo_test not found in discovered tools"
        assert "add_test" in tool_names, "add_test not found in discovered tools"
        assert "greeting_test" in tool_names, "greeting_test not found in discovered tools"

        # Check tool types
        function_tools = [t for t in tools if t.tool_type == ToolType.FUNCTION_BASED]
        class_tools = [t for t in tools if t.tool_type == ToolType.CLASS_BASED]

        assert len(function_tools) == 2
        assert len(class_tools) == 1

    def test_rescan_tools(self, tool_discovery: ToolDiscovery):
        """Test rescanning tools."""
        # Initial discovery
        initial_tools = tool_discovery.discover_tools()

        # Rescan
        rescan_result = tool_discovery.rescan_tools()

        assert isinstance(rescan_result, RescanResult)
        assert rescan_result.total_tools == len(initial_tools)


class TestToolRegistry:
    """Test tool registry functionality."""

    def test_empty_registry(self, tool_registry: ToolRegistry):
        """Test empty registry operations."""
        assert tool_registry.get_tool_count() == 0
        assert tool_registry.list_tools() == []
        assert tool_registry.list_tool_names() == []
        assert not tool_registry.has_tool("nonexistent")
        assert tool_registry.get_tool("nonexistent") is None

    def test_register_single_tool(self, tool_registry: ToolRegistry):
        """Test registering a single tool."""
        tool_info = ToolInfo(
            name="test_tool",
            description="A test tool",
            tool_type=ToolType.FUNCTION_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            function_name="test_function",
        )

        tool_registry.register_tool(tool_info)

        assert tool_registry.get_tool_count() == 1
        assert tool_registry.has_tool("test_tool")

        retrieved_tool = tool_registry.get_tool("test_tool")
        assert retrieved_tool is not None
        assert retrieved_tool.name == "test_tool"
        assert retrieved_tool.description == "A test tool"

    def test_register_multiple_tools(self, tool_registry: ToolRegistry, tool_discovery: ToolDiscovery):
        """Test registering multiple tools."""
        tools = tool_discovery.discover_tools()
        tool_registry.register_tools(tools)

        assert tool_registry.get_tool_count() == len(tools)

        tool_names = tool_registry.list_tool_names()
        assert "echo_test" in tool_names
        assert "add_test" in tool_names
        assert "greeting_test" in tool_names

    def test_unregister_tool(self, tool_registry: ToolRegistry):
        """Test unregistering a tool."""
        tool_info = ToolInfo(
            name="test_tool",
            description="A test tool",
            tool_type=ToolType.FUNCTION_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            function_name="test_function",
        )

        tool_registry.register_tool(tool_info)
        assert tool_registry.has_tool("test_tool")

        # Unregister existing tool
        result = tool_registry.unregister_tool("test_tool")
        assert result is True
        assert not tool_registry.has_tool("test_tool")

        # Unregister non-existing tool
        result = tool_registry.unregister_tool("nonexistent")
        assert result is False

    def test_clear_registry(self, tool_registry: ToolRegistry, tool_discovery: ToolDiscovery):
        """Test clearing the registry."""
        tools = tool_discovery.discover_tools()
        tool_registry.register_tools(tools)

        assert tool_registry.get_tool_count() > 0

        tool_registry.clear()
        assert tool_registry.get_tool_count() == 0
        assert tool_registry.list_tools() == []

    def test_update_registry(self, tool_registry: ToolRegistry, tool_discovery: ToolDiscovery):
        """Test updating the registry with new tools."""
        # Add initial tool
        initial_tool = ToolInfo(
            name="initial_tool",
            description="Initial tool",
            tool_type=ToolType.FUNCTION_BASED,
            file_path="/test/initial.py",
            module_name="initial_module",
            function_name="initial_function",
        )
        tool_registry.register_tool(initial_tool)
        assert tool_registry.get_tool_count() == 1

        # Update with discovered tools
        discovered_tools = tool_discovery.discover_tools()
        tool_registry.update_registry(discovered_tools)

        # Should have only the discovered tools now
        assert tool_registry.get_tool_count() == len(discovered_tools)
        assert not tool_registry.has_tool("initial_tool")  # Should be replaced
        assert tool_registry.has_tool("echo_test")
