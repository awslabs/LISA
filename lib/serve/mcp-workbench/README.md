# MCP Workbench

A dynamic host for Python files used as MCP (Model Context Protocol) tools. MCP Workbench allows you to dynamically load and serve Python tools as MCP tools through a pure FastMCP 2.0 server.

## Features

- **Dynamic Tool Discovery**: Automatically discovers tools from Python files in a configurable directory
- **Two Tool Types**: Supports both class-based tools (inheriting from `BaseTool`) and function-based tools (using `@mcp_tool` decorator)
- **Pure MCP Protocol**: Native MCP protocol implementation via FastMCP 2.0
- **Hot Reloading**: HTTP GET endpoint to rescan and reload tools without server restart
- **Professional Module Loading**: Uses `importlib` and `inspect` for safe module analysis
- **Configurable**: Support for YAML configuration files and CLI arguments
- **Better Parameter Support**: Leverages FastMCP 2.0's improved JSON schema handling
- **Clean Architecture**: Simplified single-protocol design

## Installation

```bash
# Install from the project directory
cd lib/serve/mcp-workbench
pip install -e .
```

## Quick Start

1. **Create a tools directory with some example tools:**

```bash
mkdir /tmp/my-tools
```

2. **Create a simple tool (save as `/tmp/my-tools/hello.py`):**

```python
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(
    name="hello",
    description="Say hello to someone",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name to greet"}
        },
        "required": ["name"]
    }
)
def say_hello(name: str):
    return f"Hello, {name}!"
```

3. **Start the server:**

```bash
mcpworkbench --tools-dir /tmp/my-tools --port 8000
```

4. **Connect with an MCP client:**

The server exposes a pure MCP protocol endpoint that MCP clients can connect to for tool discovery and execution.

## Tool Development

### Class-Based Tools

Create tools by inheriting from `BaseTool`:

```python
from mcpworkbench.core.base_tool import BaseTool

class MyTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="Description of what my tool does"
        )

    def get_parameters(self):
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "First parameter"}
            },
            "required": ["param1"]
        }

    async def execute(self, **kwargs):
        param1 = kwargs["param1"]
        return {"result": f"Processed: {param1}"}
```

### Function-Based Tools

Create tools using the `@mcp_tool` decorator:

```python
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(
    name="my_function_tool",
    description="A function-based tool",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Input text"}
        },
        "required": ["text"]
    }
)
async def process_text(text: str):
    return {"processed": text.upper()}
```

## Configuration

### Command Line Usage

```bash
mcpworkbench [OPTIONS]

Options:
  -c, --config PATH          Path to YAML configuration file
  -t, --tools-dir PATH       Directory containing tool files
  --host TEXT                Server host address (default: 127.0.0.1)
  -p, --port INTEGER         Server port (default: 8000)
  --exit-route TEXT          Enable exit_server HTTP GET endpoint (optional)
  --rescan-route TEXT        Enable rescan_tools HTTP GET endpoint (optional)
  --cors-origins TEXT        Comma-separated list of allowed CORS origins
  -v, --verbose              Enable verbose logging
  --debug                    Enable debug logging
```

### YAML Configuration

```yaml
# Server settings
host: "0.0.0.0"
port: 8000

# Tool settings
tools_dir: "/path/to/tools"

# Management routes (optional)
exit_route: "/shutdown"     # Enables exit_server HTTP GET endpoint
rescan_route: "/rescan"     # Enables rescan_tools HTTP GET endpoint

# CORS settings (simple format)
cors_origins: ["*"]

# Advanced CORS settings (optional - will use defaults if not specified)
cors_settings:
  allow_methods: ["GET", "POST", "OPTIONS"]
  allow_headers: ["*"]
  allow_credentials: false
  expose_headers: []
  max_age: 600
```

## Architecture

**Pure FastMCP 2.0 Server:**
- **Native MCP Protocol**: 100% MCP protocol implementation via FastMCP 2.0
- **Dynamic Tool Registration**: Tools discovered and registered as native FastMCP tools
- **Management Routes**: Rescan and exit functionality as HTTP GET endpoints
- **Better Parameter Support**: Leverages FastMCP 2.0's improved JSON schema handling
- **Simplified Codebase**: Single protocol, no adapter layer needed

## MCP Tools

### Discovered Tools

All Python tools from your tools directory are automatically registered as MCP tools with their:
- Original names and descriptions
- Parameter schemas
- Execution capabilities

### Built-in Management Routes

**GET /rescan** (when enabled):
- Rescans the tools directory for new/updated tools
- Returns JSON status of changes made
- Accessible via HTTP GET requests

**GET /shutdown** (when enabled):
- Gracefully shuts down the MCP Workbench server
- Returns JSON confirmation before shutdown
- Useful for remote management

## Example Usage

### Using an MCP Client

```python
# Example MCP client usage (pseudocode)
import mcp_client

client = mcp_client.connect("http://localhost:8000")

# List available tools
tools = client.list_tools()
print(f"Available tools: {[tool.name for tool in tools]}")

# Call a tool
result = client.call_tool("hello", {"name": "World"})
print(f"Result: {result}")

# Rescan for new tools via HTTP GET (if enabled)
import requests
rescan_result = requests.get("http://localhost:8000/rescan")
print(f"Rescan result: {rescan_result.json()}")
```

## Docker Usage

The project includes a Dockerfile for containerized deployment using s6-overlay for service management:

```bash
# Build the container
docker build -t mcp-workbench lib/serve/mcp-workbench/

# Run with mounted tools directory and environment variables
docker run -v /path/to/tools:/workspace/tools \
  -p 8000:8000 \
  -e TOOLS_DIR=/workspace/tools \
  -e RESCAN_ROUTE=/rescan \
  -e LOG_LEVEL=debug \
  mcp-workbench
```

### Environment Variables

The container supports the following environment variables:

- `TOOLS_DIR` - Directory containing tool files (default: `/workspace/tools`)
- `HOST` - Server host address (default: `0.0.0.0`)
- `PORT` - Server port (default: `8000`)
- `RESCAN_ROUTE` - Enable rescan_tools HTTP GET endpoint (optional)
- `EXIT_ROUTE` - Enable exit_server HTTP GET endpoint (optional)
- `CORS_ORIGINS` - Comma-separated list of allowed CORS origins (default: `*`)
- `LOG_LEVEL` - Logging level: `info`, `verbose`, or `debug` (default: `info`)

### s6-overlay Service Management

The container uses s6-overlay to manage the MCP workbench service as a long-running process. This provides:

- **Automatic restart** if the service crashes
- **Proper signal handling** for graceful shutdown
- **Service dependency management**
- **Logging and monitoring capabilities**

The service is configured in `/etc/s6-overlay/s6-rc.d/mcpworkbench/` and starts automatically when the container launches.

## AWS Integration

This project is designed to work with the existing LISA MCP infrastructure:

1. Tools are created/edited via the LISA web interface
2. Tools are stored in S3 via the existing Lambda functions
3. S3 bucket is mounted to the container filesystem
4. MCP Workbench reads tools from the mounted location
5. External processes can trigger rescans via HTTP GET requests

## Development

### Project Structure

```
src/mcpworkbench/
├── __init__.py
├── cli.py                    # Command line interface
├── config/
│   ├── __init__.py
│   └── models.py            # Configuration data models
├── core/
│   ├── __init__.py
│   ├── base_tool.py         # BaseTool abstract class
│   ├── tool_discovery.py    # Tool discovery component
│   ├── tool_registry.py     # Tool registry component
│   └── annotations.py       # Tool function annotations
├── server/
│   ├── __init__.py
│   ├── mcp_server.py        # FastMCP 2.0 server implementation
│   └── middleware.py        # Legacy middleware (may be removed)
└── adapters/
    ├── __init__.py
    └── tool_adapter.py      # Legacy adapters (may be removed)
```

### Testing

#### Pytest Tests

The project includes comprehensive pytest-based tests:

```bash
# Install with development dependencies
cd lib/serve/mcp-workbench
pip install -e ".[dev]"

# Alternative if above doesn't work:
pip install -e .
pip install pytest pytest-asyncio requests pytest-timeout

# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run specific test files
pytest tests/test_core.py
pytest tests/test_adapters.py
pytest tests/test_integration.py

# Run tests with coverage
pytest --cov=mcpworkbench

# Run only unit tests (exclude integration tests)
pytest tests/test_core.py tests/test_adapters.py
```

#### Manual Testing

For manual testing and interactive server exploration:

```bash
# Run the manual test script (includes API testing)
python tests/test_manual.py

# Or run with example tools
mcpworkbench --tools-dir src/examples/sample_tools --port 8001 --debug
```

#### Test Structure

- `tests/test_core.py` - Unit tests for core components (BaseTool, annotations, discovery, registry)
- `tests/test_adapters.py` - Unit tests for tool adapters
- `tests/test_integration.py` - Full integration tests with running server
- `tests/test_manual.py` - Interactive manual testing script
- `tests/conftest.py` - Pytest fixtures and configuration

## Migration from Hybrid Architecture

If migrating from the previous hybrid REST API + MCP architecture:

### What Changed
- **Management as HTTP Routes**: Rescan/exit are now HTTP GET endpoints, not MCP tools
- **Added Dependencies**: Added Starlette/Uvicorn dependencies for HTTP route support
- **Hybrid Architecture**: MCP protocol for tools + HTTP GET endpoints for management
- **FastMCP 2.0**: Better parameter support and native MCP integration

### What Stayed the Same
- **Tool Discovery**: Same Python file scanning and tool detection
- **Tool Types**: Both class-based and function-based tools still supported
- **Configuration**: Same YAML and CLI configuration options
- **Docker Support**: Same containerization and s6-overlay integration

## License

Licensed under the Apache License, Version 2.0. See the LICENSE file for details.
