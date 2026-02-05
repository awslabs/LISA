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

"""Tests for tool adapters."""

from unittest.mock import Mock

import pytest
from mcpworkbench.adapters.tool_adapter import BaseToolAdapter, create_adapter, FunctionToolAdapter
from mcpworkbench.core.annotations import mcp_tool
from mcpworkbench.core.base_tool import BaseTool, ToolInfo, ToolType


class MockBaseTool(BaseTool):
    """Mock implementation of BaseTool for testing."""

    def __init__(self):
        super().__init__("test_base_tool", "A test base tool")

    async def execute(self, **kwargs):
        message = kwargs.get("message", "default")
        return {"processed": f"Base tool processed: {message}"}

    def get_parameters(self):
        return {"type": "object", "properties": {"message": {"type": "string", "description": "Message to process"}}}


@mcp_tool(
    name="test_function_tool",
    description="A test function tool",
)
def mock_function(value: float):
    """Mock function for function adapter testing."""
    return {"doubled": value * 2}


@mcp_tool(name="test_async_function_tool", description="A test async function tool")
async def mock_async_function(text: str):
    """Mock async function for function adapter testing."""
    return {"uppercased": text.upper()}


class TestBaseToolAdapter:
    """Test BaseToolAdapter functionality."""

    def test_adapter_creation(self):
        """Test creating a BaseToolAdapter."""
        tool_instance = MockBaseTool()
        tool_info = ToolInfo(
            name="test_base_tool",
            description="A test base tool",
            tool_type=ToolType.CLASS_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            class_name="MockBaseTool",
            tool_instance=tool_instance,
        )

        adapter = BaseToolAdapter(tool_info)
        assert adapter.name == "test_base_tool"
        assert adapter.description == "A test base tool"
        assert adapter.tool_instance == tool_instance

    def test_adapter_wrong_type(self):
        """Test BaseToolAdapter with wrong tool type."""
        tool_info = ToolInfo(
            name="test_tool",
            description="A test tool",
            tool_type=ToolType.FUNCTION_BASED,  # Wrong type
            file_path="/test/path.py",
            module_name="test_module",
            function_name="test_function",
        )

        with pytest.raises(ValueError, match="BaseToolAdapter requires a class-based tool"):
            BaseToolAdapter(tool_info)

    def test_adapter_wrong_instance(self):
        """Test BaseToolAdapter with wrong instance type."""
        tool_info = ToolInfo(
            name="test_tool",
            description="A test tool",
            tool_type=ToolType.CLASS_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            class_name="TestTool",
            tool_instance="not_a_tool",  # Wrong type
        )

        with pytest.raises(ValueError, match="Tool instance must be a BaseTool instance"):
            BaseToolAdapter(tool_info)

    @pytest.mark.asyncio
    async def test_adapter_execute(self):
        """Test executing a tool through BaseToolAdapter."""
        tool_instance = MockBaseTool()
        tool_info = ToolInfo(
            name="test_base_tool",
            description="A test base tool",
            tool_type=ToolType.CLASS_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            class_name="MockBaseTool",
            tool_instance=tool_instance,
        )

        adapter = BaseToolAdapter(tool_info)
        result = await adapter.execute({"message": "hello"})

        assert result == {"processed": "Base tool processed: hello"}


class TestFunctionToolAdapter:
    """Test FunctionToolAdapter functionality."""

    def test_adapter_creation(self):
        """Test creating a FunctionToolAdapter."""
        tool_info = ToolInfo(
            name="test_function_tool",
            description="A test function tool",
            tool_type=ToolType.FUNCTION_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            function_name="test_function",
            tool_instance=mock_function,
        )

        adapter = FunctionToolAdapter(tool_info)
        assert adapter.name == "test_function_tool"
        assert adapter.description == "A test function tool"
        assert adapter.function == mock_function

    def test_adapter_wrong_type(self):
        """Test FunctionToolAdapter with wrong tool type."""
        tool_info = ToolInfo(
            name="test_tool",
            description="A test tool",
            tool_type=ToolType.CLASS_BASED,  # Wrong type
            file_path="/test/path.py",
            module_name="test_module",
            class_name="TestTool",
        )

        with pytest.raises(ValueError, match="FunctionToolAdapter requires a function-based tool"):
            FunctionToolAdapter(tool_info)

    def test_adapter_not_callable(self):
        """Test FunctionToolAdapter with non-callable instance."""
        tool_info = ToolInfo(
            name="test_tool",
            description="A test tool",
            tool_type=ToolType.FUNCTION_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            function_name="test_function",
            tool_instance="not_callable",  # Not callable
        )

        with pytest.raises(ValueError, match="Tool instance must be callable"):
            FunctionToolAdapter(tool_info)

    @pytest.mark.asyncio
    async def test_adapter_execute_sync_function(self):
        """Test executing a sync function through FunctionToolAdapter."""
        tool_info = ToolInfo(
            name="test_function_tool",
            description="A test function tool",
            tool_type=ToolType.FUNCTION_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            function_name="test_function",
            tool_instance=mock_function,
        )

        adapter = FunctionToolAdapter(tool_info)
        result = await adapter.execute({"value": 5})

        assert result == {"doubled": 10}

    @pytest.mark.asyncio
    async def test_adapter_execute_async_function(self):
        """Test executing an async function through FunctionToolAdapter."""
        tool_info = ToolInfo(
            name="test_async_function_tool",
            description="A test async function tool",
            tool_type=ToolType.FUNCTION_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            function_name="test_async_function",
            tool_instance=mock_async_function,
        )

        adapter = FunctionToolAdapter(tool_info)
        result = await adapter.execute({"text": "hello"})

        assert result == {"uppercased": "HELLO"}


class TestCreateAdapter:
    """Test the create_adapter factory function."""

    def test_create_base_tool_adapter(self):
        """Test creating a BaseToolAdapter via factory."""
        tool_instance = MockBaseTool()
        tool_info = ToolInfo(
            name="test_base_tool",
            description="A test base tool",
            tool_type=ToolType.CLASS_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            class_name="MockBaseTool",
            tool_instance=tool_instance,
        )

        adapter = create_adapter(tool_info)
        assert isinstance(adapter, BaseToolAdapter)
        assert adapter.name == "test_base_tool"

    def test_create_function_tool_adapter(self):
        """Test creating a FunctionToolAdapter via factory."""
        tool_info = ToolInfo(
            name="test_function_tool",
            description="A test function tool",
            tool_type=ToolType.FUNCTION_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            function_name="test_function",
            tool_instance=mock_function,
        )

        adapter = create_adapter(tool_info)
        assert isinstance(adapter, FunctionToolAdapter)
        assert adapter.name == "test_function_tool"

    def test_create_adapter_unknown_type(self):
        """Test create_adapter with unknown tool type."""
        # Use a mock ToolInfo that bypasses validation for testing
        with pytest.raises(ValueError, match="Unknown tool type"):
            create_adapter_with_invalid_type()

    def test_adapter_properties(self):
        """Test adapter properties are correctly exposed."""
        tool_instance = MockBaseTool()
        tool_info = ToolInfo(
            name="test_base_tool",
            description="A test base tool",
            tool_type=ToolType.CLASS_BASED,
            file_path="/test/path.py",
            module_name="test_module",
            class_name="MockBaseTool",
            tool_instance=tool_instance,
        )

        adapter = create_adapter(tool_info)

        assert adapter.name == "test_base_tool"
        assert adapter.description == "A test base tool"
        assert adapter.tool_info == tool_info


def create_adapter_with_invalid_type():
    """Helper function to test invalid tool type."""
    # Create a mock tool info with invalid type by bypassing validation
    tool_info = Mock()
    tool_info.tool_type = "unknown_type"
    tool_info.name = "test_tool"
    return create_adapter(tool_info)
