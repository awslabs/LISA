"""Pytest configuration and shared fixtures."""

import asyncio
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from mcpworkbench.config.models import ServerConfig, CORSConfig
from mcpworkbench.core.tool_discovery import ToolDiscovery
from mcpworkbench.core.tool_registry import ToolRegistry


@pytest.fixture
def temp_tools_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test tools."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tools_dir = Path(temp_dir)
        yield tools_dir


@pytest.fixture
def sample_function_tool_content() -> str:
    """Sample function-based tool content."""
    return '''
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(
    name="echo_test",
    description="Echo back the input text for testing",
    parameters={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Message to echo"}
        },
        "required": ["message"]
    }
)
def echo_message(message: str):
    return {"echoed": message, "length": len(message)}

@mcp_tool(
    name="add_test",
    description="Add two numbers together for testing",
    parameters={
        "type": "object",
        "properties": {
            "a": {"type": "number", "description": "First number"},
            "b": {"type": "number", "description": "Second number"}
        },
        "required": ["a", "b"]
    }
)
async def add_numbers(a: float, b: float):
    return {"a": a, "b": b, "sum": a + b}
'''


@pytest.fixture
def sample_class_tool_content() -> str:
    """Sample class-based tool content."""
    return '''
from mcpworkbench.core.base_tool import BaseTool

class TestGreetingTool(BaseTool):
    """Test greeting tool."""
    
    def __init__(self):
        super().__init__(
            name="greeting_test",
            description="Generate personalized greetings for testing"
        )
    
    def get_parameters(self):
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name to greet"},
                "style": {
                    "type": "string",
                    "enum": ["formal", "casual", "enthusiastic"],
                    "description": "Greeting style",
                    "default": "casual"
                }
            },
            "required": ["name"]
        }
    
    async def execute(self, **kwargs):
        name = kwargs["name"]
        style = kwargs.get("style", "casual")
        
        if style == "formal":
            greeting = f"Good day, {name}."
        elif style == "enthusiastic":
            greeting = f"Hey there, {name}! How exciting to meet you!"
        else:  # casual
            greeting = f"Hi {name}!"
        
        return {"greeting": greeting, "name": name, "style": style}
'''


@pytest.fixture
def populated_tools_dir(temp_tools_dir: Path, sample_function_tool_content: str, sample_class_tool_content: str) -> Path:
    """Create a tools directory populated with sample tools."""
    # Create function-based tools file
    (temp_tools_dir / "function_tools.py").write_text(sample_function_tool_content)
    
    # Create class-based tools file
    (temp_tools_dir / "class_tools.py").write_text(sample_class_tool_content)
    
    return temp_tools_dir


@pytest.fixture
def sample_config() -> ServerConfig:
    """Sample server configuration for testing."""
    return ServerConfig(
        server_host="127.0.0.1",
        server_port=8001,
        tools_directory="/tmp/test-tools",
        mcp_route_path="/mcp",
        exit_route_path="/shutdown",
        rescan_route_path="/rescan",
        cors_settings=CORSConfig(
            allow_origins=["*"],
            allow_methods=["GET", "POST"],
            allow_headers=["*"]
        )
    )


@pytest.fixture
def tool_discovery(populated_tools_dir: Path) -> ToolDiscovery:
    """Create a tool discovery instance with populated tools directory."""
    return ToolDiscovery(str(populated_tools_dir))


@pytest.fixture
def tool_registry() -> ToolRegistry:
    """Create a fresh tool registry instance."""
    return ToolRegistry()


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
