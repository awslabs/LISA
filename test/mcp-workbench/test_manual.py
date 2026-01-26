#!/usr/bin/env python3
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

"""
Test script for MCP Workbench.

This script creates a temporary tools directory, populates it with example tools,
starts the MCP workbench server, and tests the API endpoints.
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests


def create_test_tools(tools_dir: Path):
    """Create test tools in the given directory."""

    # Create a simple function-based tool
    function_tool = """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(
    name="echo",
    description="Echo back the input text",
)
def echo_message(message: str):
    return {"echoed": message, "length": len(message)}

@mcp_tool(
    name="add_numbers",
    description="Add two numbers together",
)
async def add_numbers(a: float, b: float):
    return {"a": a, "b": b, "sum": a + b}
"""

    # Create a class-based tool
    class_tool = """
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
"""

    # Write the tools to files
    (tools_dir / "function_tools.py").write_text(function_tool)
    (tools_dir / "class_tools.py").write_text(class_tool)

    print(f"Created test tools in {tools_dir}")


def check_api_endpoints(base_url: str):
    """Test the API endpoints."""
    print(f"\nTesting API endpoints at {base_url}")

    try:
        # Test list tools
        print("1. Testing GET /mcp/tools")
        response = requests.get(f"{base_url}/mcp/tools")
        if response.status_code == 200:
            tools = response.json()
            print(f"   ✓ Found {tools['count']} tools:")
            for tool in tools["tools"]:
                print(f"     - {tool['name']}: {tool['description']}")
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")
            return False

        # Test get specific tool
        print("\n2. Testing GET /mcp/tools/echo")
        response = requests.get(f"{base_url}/mcp/tools/echo")
        if response.status_code == 200:
            tool = response.json()
            print(f"   ✓ Tool info: {tool['name']} - {tool['description']}")
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")

        # Test call echo tool
        print("\n3. Testing POST /mcp/tools/echo/call")
        response = requests.post(
            f"{base_url}/mcp/tools/echo/call", json={"arguments": {"message": "Hello, MCP Workbench!"}}
        )
        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Result: {result['result']}")
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")

        # Test call add_numbers tool
        print("\n4. Testing POST /mcp/tools/add_numbers/call")
        response = requests.post(f"{base_url}/mcp/tools/add_numbers/call", json={"arguments": {"a": 15, "b": 27}})
        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Result: {result['result']}")
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")

        # Test call greeting tool
        print("\n5. Testing POST /mcp/tools/greeting/call")
        response = requests.post(
            f"{base_url}/mcp/tools/greeting/call", json={"arguments": {"name": "Alice", "style": "enthusiastic"}}
        )
        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Result: {result['result']}")
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")

        return True

    except requests.exceptions.ConnectionError:
        print(f"   ✗ Could not connect to server at {base_url}")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def main():
    """Main test function."""
    print("MCP Workbench Test Script")
    print("=" * 40)

    # Create temporary directory for tools
    with tempfile.TemporaryDirectory() as temp_dir:
        tools_dir = Path(temp_dir) / "tools"
        tools_dir.mkdir()

        # Create test tools
        create_test_tools(tools_dir)

        # Start the server in the background
        print("\nStarting MCP Workbench server...")
        print(f"Tools directory: {tools_dir}")

        server_process = None
        try:
            # Start server
            server_process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "mcpworkbench.cli",
                    "--tools-dir",
                    str(tools_dir),
                    "--port",
                    "8001",
                    "--host",
                    "127.0.0.1",
                    "--rescan-route",
                    "/rescan",
                    "--verbose",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for server to start
            print("Waiting for server to start...")
            time.sleep(3)

            # Check if server is running
            if server_process.poll() is not None:
                stdout, stderr = server_process.communicate()
                print("Server failed to start:")
                print(f"STDOUT: {stdout}")
                print(f"STDERR: {stderr}")
                return 1

            # Test the API
            success = check_api_endpoints("http://127.0.0.1:8001")

            if success:
                print("\n" + "=" * 40)
                print("✅ All tests passed!")
                print("\nYou can now:")
                print("1. Visit http://127.0.0.1:8001/mcp/tools to see available tools")
                print("2. Use the rescan endpoint: curl -X POST http://127.0.0.1:8001/rescan")
                print("3. Call tools via the API as demonstrated above")
                print("\nPress Ctrl+C to stop the server...")

                # Keep server running for manual testing
                try:
                    server_process.wait()
                except KeyboardInterrupt:
                    print("\nShutting down server...")

                return 0
            else:
                print("\n❌ Some tests failed")
                return 1

        except KeyboardInterrupt:
            print("\nTest interrupted by user")
            return 1
        except Exception as e:
            print(f"\nError running test: {e}")
            return 1
        finally:
            if server_process and server_process.poll() is None:
                print("Terminating server...")
                server_process.terminate()
                try:
                    server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server_process.kill()


if __name__ == "__main__":
    exit(main())
