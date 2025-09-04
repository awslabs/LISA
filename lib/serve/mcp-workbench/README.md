# MCP Workbench

A dynamic host for Python files used as MCP (Model Context Protocol) tools. MCP Workbench allows you to dynamically load and serve Python tools as MCP tools through an HTTP server.

## Features

- **Dynamic Tool Discovery**: Automatically discovers tools from Python files in a configurable directory
- **Two Tool Types**: Supports both class-based tools (inheriting from `BaseTool`) and function-based tools (using `@mcp_tool` decorator)
- **HTTP Server**: Serves tools via HTTP endpoints with full MCP protocol support
- **Hot Reloading**: Optional HTTP endpoint to rescan and reload tools without server restart
- **Professional Module Loading**: Uses `importlib` and `inspect` for safe module analysis
- **Configurable**: Support for YAML configuration files and CLI arguments
- **CORS Support**: Configurable CORS settings for web integration
- **Clean Architecture**: Modular design with dependency injection

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

4. **Test the tool:**

```bash
# List available tools
curl http://localhost:8000/mcp/tools

# Call the hello tool
curl -X POST http://localhost:8000/mcp/tools/hello/call \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"name": "World"}}'
```

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
  --mcp-route TEXT           URL path for MCP endpoints (default: /mcp)
  --exit-route TEXT          URL path to exit application (optional)
  --rescan-route TEXT        URL path to trigger tool rescanning (optional)
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

# Route settings
mcp_route: "/mcp"
exit_route: "/shutdown"     # Optional
rescan_route: "/rescan"     # Optional

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

## API Endpoints

### Tool Management

- `GET /mcp/tools` - List all available tools
- `GET /mcp/tools/{tool_name}` - Get information about a specific tool
- `POST /mcp/tools/{tool_name}/call` - Execute a tool

### Management Endpoints (Optional)

- `POST /rescan` - Rescan tools directory and reload tools
- `POST /shutdown` - Shutdown the server gracefully

### MCP Protocol

- `POST /mcp/mcp` - Handle MCP protocol requests (when MCP SDK is available)

## Example API Usage

### List Tools

```bash
curl http://localhost:8000/mcp/tools
```

Response:
```json
{
  "tools": [
    {
      "name": "calculator",
      "description": "Performs basic arithmetic operations",
      "parameters": {...}
    }
  ],
  "count": 1
}
```

### Execute Tool

```bash
curl -X POST http://localhost:8000/mcp/tools/calculator/call \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "operation": "add",
      "a": 5,
      "b": 3
    }
  }'
```

Response:
```json
{
  "result": {
    "operation": "add",
    "a": 5,
    "b": 3,
    "result": 8
  },
  "tool": "calculator"
}
```

### Rescan Tools

```bash
curl -X POST http://localhost:8000/rescan
```

Response:
```json
{
  "status": "success",
  "tools_added": ["new_tool"],
  "tools_updated": ["existing_tool"],
  "tools_removed": [],
  "total_tools": 5,
  "timestamp": "2025-01-04T16:32:00Z"
}
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
- `MCP_ROUTE` - URL path for MCP endpoints (default: `/mcp`)
- `RESCAN_ROUTE` - URL path to trigger tool rescanning (optional)
- `EXIT_ROUTE` - URL path to exit application (optional)
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
5. External processes can trigger rescans via HTTP

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
│   ├── mcp_server.py        # MCP server implementation
│   └── middleware.py        # CORS and other middleware
└── adapters/
    ├── __init__.py
    └── tool_adapter.py      # Adapters for wrapping tools
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

## License

Licensed under the Apache License, Version 2.0. See the LICENSE file for details.
