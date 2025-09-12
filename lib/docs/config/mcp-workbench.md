# MCP Workbench

The MCP Workbench is a development environment that enables administrators to create, test, and deploy custom tools through LISA's hosted Model Context Protocol (MCP) server. This feature provides a browser-based Python editor for rapid prototyping and deployment of custom functionality.

> **Note:** For comprehensive information about the Model Context Protocol, please refer to the [Model Context Protocol (MCP)](./mcp.md) documentation.

## Overview

The MCP Workbench serves as an introduction to hosted tool development within the MCP ecosystem. It provides administrators with the capability to:

- Create custom Python-based tools accessible to all users
- Test and iterate on tool functionality in real-time
- Deploy tools seamlessly through LISA's MCP server infrastructure
- Share tools across the organization without complex deployment processes

The integrated browser-based editor allows administrators to write Python code and expose functions as MCP tools by using simple annotations or class extensions.

## Prerequisites

- Administrator privileges in LISA
- MCP Server Connections feature enabled
- Basic understanding of Python programming
- Familiarity with MCP concepts (recommended)

## Configuration

### Step 1: Enable the MCP Workbench Menu

1. **Access Admin Configuration**
   - Navigate to the Admin menu
   - Select "Configuration"

2. **Enable Required Features**
   - Ensure "MCP Server Connections" is enabled
   - Enable "Show MCP Workbench"
   - Save the configuration

This configuration creates a new menu item in the administrators section, providing access to the Python file editor for tool creation, modification, and deletion.

### Step 2: Activate the MCP Server Connection

Enabling the MCP Workbench automatically creates a new MCP Connection to LISA's hosted MCP server. This connection must be activated to make the tools available in the chat application.

1. **Navigate to MCP Connections**
   - Go to the Libraries menu
   - Select "MCP Connections"

2. **Activate the Connection**
   - Locate the "MCP Workbench" connection
   - Click the radio button to select it
   - Choose "Edit" from the actions menu
   - Toggle the "Active" setting to enabled
   - Save the configuration

> **Security Note:** The MCP Workbench connection uses a special Bearer Token with the placeholder `{LISA_BEARER_TOKEN}`, which is automatically replaced with each user's individual OIDC token for secure access.

## Usage

### Chat Interface Integration

Once the MCP Workbench connection is activated, all custom enabled tools become immediately available in the chat interface. Users can discover and utilize these tools through the standard MCP tool invocation methods within their conversations.

### Programmatic API Access

LISA automatically hosts an MCP Server containing all MCP Workbench tools. The server is accessible through the following endpoints:

**AWS Load Balancer URL:**
```
https://abc-rest-<account-number>.<region>.elb.amazonaws.com/v2/mcp/
```

**Custom Domain URL (if configured):**
```
https://<your-custom-domain>/v2/mcp/
```

> **Authentication Required:** API access requires [Programmatic API Tokens](./api-tokens.md) for authentication.

## Development Guidelines

### Creating Your First Tool

Tools can be created using two simple approaches:

#### Function-based Tool (Annotation Method)

```python
from mcpworkbench.core.annotations import mcp_tool
from typing import Annotated

@mcp_tool(
   name="hello_world",
   description="A personalized greeting to the a person."
)
def hello_world(name: Annotated[str, "The name of the person to greet."]) -> str:
    """
    A simple hello world tool that greets a user.
    
    Args:
        name: The name of the person to greet
        
    Returns:
        A greeting message
    """
    return f"Hello, {name}! Welcome to MCP Workbench."
```

> **Note:** Using `Annotated` on function parameters is optional. You can use standard Python type hints if preferred.

#### Class-based Tool (Inherited Class Method)

```python
from mcpworkbench.tools import BaseTool

class HelloWorldTool(BaseTool):
    """A simple hello world tool using class inheritance."""
    
    name = "hello_world_class"
    description = "A class-based hello world tool"
    
    def execute(self, name: Annotated[str, "The name of the person to greet."]) -> str:
        """
        Execute the hello world functionality.
        
        Args:
            name: The name of the person to greet
            
        Returns:
            A greeting message
        """
        return f"Hello, {name}! This is from a class-based tool."
```

Both approaches will make your tool available in the chat interface once deployed.

## Advanced Usage

### Adding Python Dependencies

Operators can modify `lib/serve/mcp-workbench/requirements.txt` to add additional Python libraries that will be available in the MCP Workbench environment. After modifying the requirements file, you'll need to perform a CDK deployment for those additional libraries to become available to your custom tools.
