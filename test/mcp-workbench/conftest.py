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

"""Pytest configuration and shared fixtures."""

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from mcpworkbench.config.models import CORSConfig, ServerConfig
from mcpworkbench.core.tool_discovery import ToolDiscovery
from mcpworkbench.core.tool_registry import ToolRegistry


@pytest.fixture(scope="function", autouse=True)
def isolate_modules():
    """Isolate sys.modules for each test to prevent cross-test contamination."""
    # Save the current state of sys.modules
    original_modules = sys.modules.copy()
    
    # Get all mcpworkbench_tools modules before test
    tools_modules_before = {k for k in sys.modules.keys() if k.startswith('mcpworkbench_tools')}
    
    yield
    
    # Clean up any mcpworkbench_tools modules added during the test
    tools_modules_after = {k for k in sys.modules.keys() if k.startswith('mcpworkbench_tools')}
    new_modules = tools_modules_after - tools_modules_before
    
    for module_name in new_modules:
        if module_name in sys.modules:
            del sys.modules[module_name]


@pytest.fixture(scope="function")
def temp_tools_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test tools."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tools_dir = Path(temp_dir)
        yield tools_dir


@pytest.fixture(scope="function")
def sample_function_tool_content() -> str:
    """Sample function-based tool content."""
    return """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(
    name="echo_test",
    description="Echo back the input text for testing",
)
def echo_message(message: str):
    return {"echoed": message, "length": len(message)}

@mcp_tool(
    name="add_test",
    description="Add two numbers together for testing",
)
async def add_numbers(a: float, b: float):
    return {"a": a, "b": b, "sum": a + b}
"""


@pytest.fixture(scope="function")
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


@pytest.fixture(scope="function")
def populated_tools_dir(
    temp_tools_dir: Path, sample_function_tool_content: str, sample_class_tool_content: str
) -> Path:
    """Create a tools directory populated with sample tools."""
    # Create function-based tools file
    (temp_tools_dir / "function_tools.py").write_text(sample_function_tool_content)

    # Create class-based tools file
    (temp_tools_dir / "class_tools.py").write_text(sample_class_tool_content)

    return temp_tools_dir


@pytest.fixture(scope="function")
def sample_config() -> ServerConfig:
    """Sample server configuration for testing."""
    return ServerConfig(
        server_host="127.0.0.1",
        server_port=8001,
        tools_directory="/tmp/test-tools",
        mcp_route_path="/mcp",
        exit_route_path="/shutdown",
        rescan_route_path="/rescan",
        cors_settings=CORSConfig(allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"]),
    )


@pytest.fixture(scope="function")
def tool_discovery(populated_tools_dir: Path) -> ToolDiscovery:
    """Create a tool discovery instance with populated tools directory."""
    return ToolDiscovery(str(populated_tools_dir))


@pytest.fixture(scope="function")
def tool_registry() -> ToolRegistry:
    """Create a fresh tool registry instance."""
    return ToolRegistry()


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
