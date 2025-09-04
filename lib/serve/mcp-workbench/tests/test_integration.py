"""Integration tests for MCP Workbench server."""

import asyncio
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Generator

import pytest
import requests


@pytest.fixture
def integration_test_tools_dir() -> Generator[Path, None, None]:
    """Create a temporary directory with integration test tools."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tools_dir = Path(temp_dir)
        
        # Create function-based tools
        function_tool = '''
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(
    name="echo",
    description="Echo back the input text",
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
    name="add_numbers",
    description="Add two numbers together",
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
        
        # Create class-based tool
        class_tool = '''
from mcpworkbench.core.base_tool import BaseTool

class GreetingTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="greeting",
            description="Generate personalized greetings"
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
        
        # Write tools to files
        (tools_dir / "function_tools.py").write_text(function_tool)
        (tools_dir / "class_tools.py").write_text(class_tool)
        
        yield tools_dir


@pytest.fixture
def server_process(integration_test_tools_dir: Path):
    """Start MCP Workbench server for integration testing."""
    process = None
    try:
        # Start server process
        process = subprocess.Popen([
            sys.executable, "-m", "mcpworkbench.cli",
            "--tools-dir", str(integration_test_tools_dir),
            "--port", "8002",  # Use different port to avoid conflicts
            "--host", "127.0.0.1",
            "--rescan-route", "/rescan",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait for server to start
        time.sleep(2)
        
        # Check if server started successfully
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            pytest.fail(f"Server failed to start. STDOUT: {stdout}, STDERR: {stderr}")
        
        yield process
        
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


@pytest.mark.timeout(30)
class TestServerIntegration:
    """Integration tests for the MCP Workbench server."""
    
    def test_server_health(self, server_process):
        """Test that server is running and responsive."""
        # Simple health check - try to connect
        try:
            response = requests.get("http://127.0.0.1:8002/mcp/tools", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.fail("Server is not responding")
    
    def test_list_tools(self, server_process):
        """Test listing available tools."""
        response = requests.get("http://127.0.0.1:8002/mcp/tools", timeout=5)
        assert response.status_code == 200
        
        data = response.json()
        assert "tools" in data
        assert "count" in data
        assert data["count"] >= 3  # Should have at least 3 tools
        
        tool_names = [tool["name"] for tool in data["tools"]]
        assert "echo" in tool_names
        assert "add_numbers" in tool_names
        assert "greeting" in tool_names
    
    def test_get_specific_tool(self, server_process):
        """Test getting information about a specific tool."""
        response = requests.get("http://127.0.0.1:8002/mcp/tools/echo", timeout=5)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "echo"
        assert data["description"] == "Echo back the input text"
        assert "parameters" in data
    
    def test_get_nonexistent_tool(self, server_process):
        """Test getting a tool that doesn't exist."""
        response = requests.get("http://127.0.0.1:8002/mcp/tools/nonexistent", timeout=5)
        assert response.status_code == 404
    
    def test_call_echo_tool(self, server_process):
        """Test calling the echo tool."""
        response = requests.post(
            "http://127.0.0.1:8002/mcp/tools/echo/call",
            json={"arguments": {"message": "Hello, Integration Test!"}},
            timeout=5
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["tool"] == "echo"
        assert data["result"]["echoed"] == "Hello, Integration Test!"
        assert data["result"]["length"] == len("Hello, Integration Test!")
    
    def test_call_add_numbers_tool(self, server_process):
        """Test calling the add_numbers tool."""
        response = requests.post(
            "http://127.0.0.1:8002/mcp/tools/add_numbers/call",
            json={"arguments": {"a": 15, "b": 27}},
            timeout=5
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["tool"] == "add_numbers"
        assert data["result"]["a"] == 15
        assert data["result"]["b"] == 27
        assert data["result"]["sum"] == 42
    
    def test_call_greeting_tool(self, server_process):
        """Test calling the greeting tool."""
        response = requests.post(
            "http://127.0.0.1:8002/mcp/tools/greeting/call",
            json={"arguments": {"name": "Pytest", "style": "enthusiastic"}},
            timeout=5
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["tool"] == "greeting"
        assert data["result"]["name"] == "Pytest"
        assert data["result"]["style"] == "enthusiastic"
        assert "Hey there, Pytest!" in data["result"]["greeting"]
    
    def test_call_tool_with_missing_arguments(self, server_process):
        """Test calling a tool with missing required arguments."""
        response = requests.post(
            "http://127.0.0.1:8002/mcp/tools/echo/call",
            json={"arguments": {}},  # Missing required 'message' argument
            timeout=5
        )
        assert response.status_code == 500  # Should fail with server error
    
    def test_call_nonexistent_tool(self, server_process):
        """Test calling a tool that doesn't exist."""
        response = requests.post(
            "http://127.0.0.1:8002/mcp/tools/nonexistent/call",
            json={"arguments": {}},
            timeout=5
        )
        assert response.status_code == 404
    
    def test_rescan_endpoint(self, server_process):
        """Test the rescan endpoint."""
        response = requests.post("http://127.0.0.1:8002/rescan", timeout=5)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "total_tools" in data
        assert "timestamp" in data
        assert isinstance(data["tools_added"], list)
        assert isinstance(data["tools_updated"], list)
        assert isinstance(data["tools_removed"], list)


@pytest.mark.timeout(60)
def test_server_startup_and_shutdown(integration_test_tools_dir: Path):
    """Test server startup and graceful shutdown."""
    process = None
    try:
        # Start server
        process = subprocess.Popen([
            sys.executable, "-m", "mcpworkbench.cli",
            "--tools-dir", str(integration_test_tools_dir),
            "--port", "8003",
            "--host", "127.0.0.1",
            "--exit-route", "/shutdown",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait for startup
        time.sleep(2)
        
        # Verify server is running
        response = requests.get("http://127.0.0.1:8003/mcp/tools", timeout=5)
        assert response.status_code == 200
        
        # Trigger graceful shutdown
        shutdown_response = requests.post("http://127.0.0.1:8003/shutdown", timeout=5)
        assert shutdown_response.status_code == 200
        
        shutdown_data = shutdown_response.json()
        assert shutdown_data["status"] == "ok"
        assert "shutting down" in shutdown_data["message"].lower()
        
        # Wait for process to exit
        process.wait(timeout=10)
        assert process.returncode == 0
        
    except subprocess.TimeoutExpired:
        if process:
            process.kill()
        pytest.fail("Server did not shut down gracefully")
    finally:
        if process and process.poll() is None:
            process.terminate()
