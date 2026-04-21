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

### Deployment infrastructure

The MCP Workbench **HTTP server** (streamable MCP and AWS session routes) always runs on **its own** ECS cluster and Application Load Balancer, separate from the LISA Serve REST API. The container still serves `/v2/mcp/*` and `/api/aws/*` on that load balancer’s default listener.

The hosted MCP base URL is stored in SSM at `…/mcpWorkbench/endpoint` (and used by configuration Lambdas). It must target the **MCP Workbench** ALB, not the Serve API ALB. When you set `restApiConfig.domainName`, LISA derives a separate workbench hostname by default (for example `lisa-serve.<suffix>` becomes `lisa-mcp-workbench.<suffix>`, and `serve.<suffix>` becomes `mcp-workbench.<suffix>`) unless you override it with `mcpWorkbenchEcsConfig.domainName`. Create a DNS record for that hostname pointing at the **MCP Workbench** load balancer in EC2.

Optional `mcpWorkbenchEcsConfig` in your deployment configuration lets you tune instance type, ASG minimum and maximum capacity, root volume size, and scaling cooldown for the workbench cluster.

**CORS:** The browser calls the workbench from the **UI origin** (custom domain, ALB URL, or local dev), which changes with deployment and app configuration. By default, `mcpWorkbenchCorsOrigins` is `*` so the workbench container allows any origin (`CORS_ORIGINS`). Set `mcpWorkbenchCorsOrigins` in your deployment config to a comma-separated list if you need to restrict origins. The workbench hostname may still differ from the Serve API hostname; verify OIDC flows for your setup.

**CDK:** The workbench stack is deployed in the same account and VPC as the rest of LISA. In the current stage layout it is created when `deployMcpWorkbench` is enabled (alongside the Serve stack when `deployServe` is enabled).

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

LISA automatically hosts an MCP Server containing all MCP Workbench tools. The server is accessible on the **MCP Workbench** load balancer (see SSM `…/mcpWorkbench/endpoint`), for example:

**AWS Load Balancer URL (example):**

```text
https://abc-rest-<account-number>.<region>.elb.amazonaws.com/v2/mcp/
```

**Custom Domain URL (if configured on that load balancer):**

```text
https://<your-custom-domain>/v2/mcp/
```

> **Authentication Required:** API access requires [Programmatic API Tokens](./api-tokens.md) for authentication.

## API Reference

The MCP Workbench includes a REST API for managing tool source files and syntax validation in addition to hosted MCP runtime access.

Base path: `/mcp-workbench`

### List Tools

- Method: `GET`
- Path: `/mcp-workbench`
- Description: Lists MCP Workbench tools available to the caller.

### Create Tool

- Method: `POST`
- Path: `/mcp-workbench`
- Description: Creates a new MCP Workbench tool.

### Get Tool

- Method: `GET`
- Path: `/mcp-workbench/{toolId}`
- Description: Retrieves a single MCP Workbench tool.

Path parameters:

- `toolId` (string, required): Tool identifier

### Update Tool

- Method: `PUT`
- Path: `/mcp-workbench/{toolId}`
- Description: Updates an existing MCP Workbench tool.

Path parameters:

- `toolId` (string, required): Tool identifier

### Delete Tool

- Method: `DELETE`
- Path: `/mcp-workbench/{toolId}`
- Description: Deletes an MCP Workbench tool.

Path parameters:

- `toolId` (string, required): Tool identifier

### Validate Python Syntax

- Method: `POST`
- Path: `/mcp-workbench/validate-syntax`
- Description: Validates Python code syntax before creating or updating tools.

Example:

```bash
curl -X GET "https://<api-gateway-domain>/<stage>/mcp-workbench" \
  -H "Authorization: Bearer <token>"
```

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
from typing import Annotated

class HelloWorldTool(BaseTool):
    """A simple hello world tool using class inheritance."""

    def __init__(self):
        """
        Initialize the tool with metadata.

        The BaseTool constructor requires:
        - name: A unique identifier for the tool
        - description: A clear description of what the tool does
        """
        super().__init__(
            name = "hello_world_class",
            description = "A class-based hello world tool"
        )

    async def execute(self):
        return self.greet

    async def greet(self, name: Annotated[str, "The name of the person to greet."]) -> str:
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

### AWS Sessions

When the [AWS Sessions](/config/mcp#aws-sessions) feature is enabled, MCP Workbench tools can leverage per-session AWS credentials that users connect in the chat UI. Tools receive the caller's identity (user and session) from the request context and use it to look up stored credentials.

To create a tool that uses AWS credentials:

1. Import `get_caller_identity` from `mcpworkbench.aws.identity` and `get_aws_session_for_user` from the shared session service.
2. Call `get_caller_identity()` to obtain the current user and session IDs from the request headers.
3. Call `get_aws_session_for_user(user_id, session_id)` to retrieve the `AwsSessionRecord` (or handle `AwsSessionMissingError` if the user has not connected credentials).
4. Use the record's `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`, and `aws_region` to construct boto3 clients.

See `lib/serve/mcp-workbench/src/examples/sample_tools/aws_operator_tools.py` for a complete example. Without tools that leverage these credentials, the AWS Sessions feature has no effect.

### Adding Python Dependencies

Operators can modify `lib/serve/mcp-workbench/requirements.txt` to add additional Python libraries that will be available in the MCP Workbench environment. After modifying the requirements file, you'll need to perform a CDK deployment for those additional libraries to become available to your custom tools.
