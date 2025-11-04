# MCP Server API Gateway Testing Examples

This document provides example HTTP requests for testing MCP server deployments through API Gateway with and without the proxy path, as well as payload examples for creating MCP servers.

---

## Creating MCP Servers

### API Endpoint

To create a hosted MCP server, make a POST request to:
```
POST /mcp
```

The payload should match the `McpServerConfig` interface structure.

---

## Deployment Payload Examples

### Example 1: STDIO Server with S3 Artifacts (Binary Executable)

```json
{
  "id": "my-stdio-server",
  "name": "My STDIO MCP Server",
  "startCommand": "/app/server/my-server-binary",
  "serverType": "stdio",
  "s3Path": "mcp-servers/my-server/v1.0.0/binaries",
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 5,
    "targetValue": 10,
    "metricName": "RequestCountPerTarget",
    "duration": 60,
    "cooldown": 60
  },
  "idpGroups": ["admin", "developers"],
  "environment": {
    "ENV": "production",
    "LOG_LEVEL": "info"
  }
}
```

**Notes:**
- `serverType: "stdio"` explicitly sets the server type (will be auto-detected if omitted)
- No `port` specified - STDIO servers don't listen on ports
- Automatically wrapped with `mcp-proxy` to expose HTTP endpoint on port 8080
- S3 path contains binary executable that will be downloaded at container startup

---

### Example 2: HTTP Server with S3 Artifacts (Python Files)

```json
{
  "id": "python-mcp-server",
  "name": "Python HTTP MCP Server",
  "startCommand": "python3 /app/server/server.py",
  "port": 8000,
  "serverType": "http",
  "s3Path": "mcp-servers/python-server/v1.0.0",
  "autoScalingConfig": {
    "minCapacity": 2,
    "maxCapacity": 10,
    "targetValue": 20,
    "metricName": "RequestCountPerTarget",
    "duration": 60,
    "cooldown": 120
  },
  "idpGroups": ["users"],
  "environment": {
    "PYTHONUNBUFFERED": "1",
    "API_KEY": "your-api-key"
  }
}
```

**Notes:**
- `port: 8000` specifies the HTTP server port
- `serverType: "http"` explicitly sets the type (auto-detected from port if omitted)
- S3 path contains Python source files
- Container will download files and execute Python script at startup

---

### Example 3: HTTP Server with Pre-built Container Image

```json
{
  "id": "pre-built-server",
  "name": "Pre-built Container Server",
  "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-mcp-server:latest",
  "startCommand": "node /app/index.js",
  "port": 3000,
  "serverType": "http",
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 3,
    "targetValue": 15
  },
  "idpGroups": ["admin"],
  "environment": {
    "NODE_ENV": "production"
  }
}
```

**Notes:**
- `image` field specifies pre-built container image (ECR or Docker Hub)
- If `image` is provided, `s3Path` is ignored
- Image must be pullable by the ECS task execution role

---

### Example 4: SSE (Server-Sent Events) Server

```json
{
  "id": "sse-mcp-server",
  "name": "SSE MCP Server",
  "startCommand": "node /app/server/events-server.js",
  "port": 8080,
  "serverType": "sse",
  "s3Path": "mcp-servers/sse-server/v1.0.0",
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 5,
    "targetValue": 25
  },
  "idpGroups": ["users"],
  "environment": {
    "EVENT_STREAM_ENABLED": "true"
  }
}
```

**Notes:**
- `serverType: "sse"` explicitly sets Server-Sent Events type
- Port required for SSE servers to handle HTTP connections

---

### Example 5: Server with Custom IAM Roles

```json
{
  "id": "secure-server",
  "name": "Secure MCP Server",
  "startCommand": "python3 /app/server.py",
  "port": 8000,
  "serverType": "http",
  "s3Path": "mcp-servers/secure-server/v1.0.0",
  "taskExecutionRoleArn": "arn:aws:iam::123456789012:role/custom-execution-role",
  "taskRoleArn": "arn:aws:iam::123456789012:role/custom-task-role",
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 3,
    "targetValue": 10
  },
  "idpGroups": ["admin"],
  "environment": {
    "SECRET_KEY": "encrypted-value"
  }
}
```

**Notes:**
- `taskExecutionRoleArn`: IAM role for ECS task execution (pulling images, CloudWatch logs)
- `taskRoleArn`: IAM role for the running container (application permissions)
- If not provided, default roles will be created automatically
- Custom roles must have necessary permissions for S3 access, logging, etc.

---

### Example 6: Minimal Configuration (Auto-detected)

```json
{
  "id": "simple-server",
  "name": "Simple MCP Server",
  "startCommand": "python3 server.py",
  "port": 8000,
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 2
  },
  "idpGroups": ["users"]
}
```

**Notes:**
- No `serverType` - will be auto-detected as `http` because `port` is provided
- No `s3Path` - assumes server files are baked into container image or base image
- Minimal auto-scaling config - only `minCapacity` and `maxCapacity` required
- Other auto-scaling fields will use defaults

---

### Example 7: Node.js Server with NPM Start

```json
{
  "id": "nodejs-server",
  "name": "Node.js MCP Server",
  "startCommand": "npm start",
  "port": 3000,
  "serverType": "http",
  "s3Path": "mcp-servers/nodejs-server/v1.0.0",
  "autoScalingConfig": {
    "minCapacity": 2,
    "maxCapacity": 8,
    "targetValue": 30,
    "duration": 120,
    "cooldown": 180
  },
  "idpGroups": ["developers"],
  "environment": {
    "NODE_ENV": "production",
    "PORT": "3000"
  }
}
```

**Notes:**
- Uses Node.js base image (auto-detected from `npm` in start command)
- `PORT` environment variable matches the `port` configuration
- Longer cooldown periods for more stable scaling behavior

---

### Example 8: Rust Binary Server (STDIO)

```json
{
  "id": "rust-stdio-server",
  "name": "Rust STDIO MCP Server",
  "startCommand": "/app/server/target/release/mcp-server",
  "serverType": "stdio",
  "s3Path": "mcp-servers/rust-server/v1.0.0/binaries",
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 3,
    "targetValue": 10
  },
  "idpGroups": ["developers"],
  "environment": {
    "RUST_LOG": "info"
  }
}
```

**Notes:**
- Rust binary detected from command structure
- STDIO server automatically wrapped with `mcp-proxy`
- Binary executable downloaded from S3 and made executable

---

### Example 9: Custom Rust Dockerfile with Cargo Install (Pre-built Image)

If you have a custom Dockerfile that installs a Rust MCP server via `cargo install`, build it and push to ECR first, then use:

```json
{
  "id": "dad-jokes-mcp-server",
  "name": "Dad Jokes MCP Server",
  "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/dad-jokes-mcp-server:latest",
  "startCommand": "/root/.cargo/bin/dad-jokes-mcp-server",
  "serverType": "stdio",
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 3,
    "targetValue": 10
  },
  "idpGroups": ["users"],
  "environment": {
    "RUST_LOG": "info"
  }
}
```

**Your Dockerfile Context:**
```dockerfile
FROM rust:1-slim-bullseye

RUN apt-get update && apt-get install -y --no-install-recommends \
  nodejs npm python3 python3-pip curl && \
  curl -LsSf https://astral.sh/uv/install.sh | sh && \
  apt-get clean && rm -rf /var/lib/apt/lists/* /root/.npm /root/.cache

RUN /root/.local/bin/uv tool install mcp-proxy

# Install the Rust MCP server
RUN cargo install --git https://github.com/OrenGrinker/dad-jokes-mcp-server

# Note: The system will override ENTRYPOINT, but this ensures mcp-proxy is installed
```

**Notes:**
- Build and push your Docker image to ECR
- Use the `image` field with the ECR image URL
- The `startCommand` should be the binary path installed by `cargo install`
- Typically cargo-installed binaries are in `/root/.cargo/bin/`
- The system will still wrap it with `mcp-proxy` automatically (even if your Dockerfile has its own ENTRYPOINT)
- S3 artifacts are ignored when `image` is provided

**Alternative: Using Cargo Install Command Directly**

If you want to avoid pre-building the image, you could structure it to use cargo at runtime:

```json
{
  "id": "dad-jokes-mcp-server",
  "name": "Dad Jokes MCP Server",
  "startCommand": "cargo install --git https://github.com/OrenGrinker/dad-jokes-mcp-server && /root/.cargo/bin/dad-jokes-mcp-server",
  "serverType": "stdio",
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 3,
    "targetValue": 10
  },
  "idpGroups": ["users"],
  "environment": {
    "RUST_LOG": "info"
  }
}
```

**However**, this approach has limitations:
- Slower startup time (compiles during container start)
- Requires Rust toolchain in the base image
- May fail if compilation takes too long

**Recommended Approach for Your Dockerfile:**

Since your Dockerfile closely matches what the system generates, you have two best options:

**Option A: Use system-generated Dockerfile (Recommended)**
Put your pre-compiled Rust binary in S3 and use:

```json
{
  "id": "dad-jokes-mcp-server",
  "name": "Dad Jokes MCP Server",
  "startCommand": "/app/server/dad-jokes-mcp-server",
  "serverType": "stdio",
  "s3Path": "mcp-servers/dad-jokes/v1.0.0/binaries",
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 3,
    "targetValue": 10
  },
  "idpGroups": ["users"]
}
```

The system will generate a similar Dockerfile to yours automatically.

**Option B: Use pre-built image with your exact Dockerfile**
Build your Dockerfile, push to ECR, and use the `image` field as shown in Example 9 above.

---

## Ready-to-Use Payload for Time MCP Server

Here's a complete JSON payload you can use to test the official MCP Time Server from the [Model Context Protocol servers repository](https://github.com/modelcontextprotocol/servers/tree/main/src/time).

### Option 1: Using Pre-built ECR Image (Recommended)

```json
{
  "id": "time-mcp-server",
  "name": "Time MCP Server",
  "image": "YOUR_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/time-mcp-server:latest",
  "startCommand": "node /app/servers/src/time/dist/index.js",
  "serverType": "stdio",
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 3,
    "targetValue": 10,
    "metricName": "RequestCountPerTarget",
    "duration": 60,
    "cooldown": 60
  },
  "idpGroups": ["users"],
  "environment": {
    "TZ": "UTC",
    "NODE_ENV": "production"
  }
}
```

**Your Dockerfile would be:**
```dockerfile
FROM node:20-slim

# Install dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
  git curl ca-certificates && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv and mcp-proxy in the same RUN to preserve shell state
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    export PATH="/root/.cargo/bin:/root/.local/bin:$PATH" && \
    uv tool install mcp-proxy

# Ensure uv is in PATH for subsequent commands
ENV PATH="/root/.cargo/bin:/root/.local/bin:$PATH"

# Clone and build the MCP servers repository
WORKDIR /app
RUN git clone https://github.com/modelcontextprotocol/servers.git
WORKDIR /app/servers

# Install dependencies and build the time server
RUN npm install && npm run build

# Set working directory to time server location
WORKDIR /app/servers/src/time

# Note: You do NOT need to set ENTRYPOINT or CMD
# The system will automatically override the container command
# to wrap STDIO servers with mcp-proxy when the image is deployed
```

**Alternative Dockerfile (If the above doesn't work):**

If you still encounter issues, use this version that uses bash explicitly:

```dockerfile
FROM node:20-slim

# Install dependencies including bash
RUN apt-get update && apt-get install -y --no-install-recommends \
  git curl ca-certificates bash && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv using bash to properly handle the installer
RUN bash -c "curl -LsSf https://astral.sh/uv/install.sh | bash" && \
    export PATH="/root/.cargo/bin:/root/.local/bin:$PATH" && \
    bash -c "uv tool install mcp-proxy"

# Ensure uv is in PATH for subsequent commands
ENV PATH="/root/.cargo/bin:/root/.local/bin:$PATH"

# Clone and build the MCP servers repository
WORKDIR /app
RUN git clone https://github.com/modelcontextprotocol/servers.git
WORKDIR /app/servers

# Install dependencies and build the time server
RUN npm install && npm run build

# Set working directory to time server location
WORKDIR /app/servers/src/time

# Note: The system will override ENTRYPOINT and wrap with mcp-proxy automatically
```

**Important Notes:**
- **No ENTRYPOINT needed**: Your Dockerfile should NOT set an ENTRYPOINT or CMD
- **System override**: The system automatically overrides the container command to wrap STDIO servers with mcp-proxy
- **mcp-proxy required**: Your image must have `mcp-proxy` installed (the system looks in `/root/.local/bin/mcp-proxy`, `/root/.cargo/bin/mcp-proxy`, or in PATH)
- **Command wrapping**: The `startCommand` you provide will be automatically wrapped by `mcp-proxy` when deployed

**Steps to use:**
1. Create a Dockerfile with the content above (no ENTRYPOINT needed)
2. Build your Dockerfile: `docker build -t time-mcp-server .`
3. Create ECR repository (if needed):
   ```bash
   aws ecr create-repository --repository-name time-mcp-server --region YOUR_REGION
   ```
4. Tag and push to ECR:
   ```bash
   aws ecr get-login-password --region YOUR_REGION | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com
   docker tag time-mcp-server:latest YOUR_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/time-mcp-server:latest
   docker push YOUR_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/time-mcp-server:latest
   ```
5. Replace `YOUR_ACCOUNT_ID` and `YOUR_REGION` in the JSON payload above
6. Send POST request to `/mcp` endpoint with this payload

**Troubleshooting Container Exit Issues:**

If your container exits immediately ("Essential container in task exited"):

1. **Check CloudWatch Logs**:
   ```bash
   # Find your log group (format: /ecs/{stack-name}-{identifier})
   aws logs describe-log-groups --log-group-name-prefix "/ecs/"

   # View recent logs
   aws logs tail /ecs/YOUR_LOG_GROUP_NAME --follow
   ```

2. **Common Issues**:
   - **mcp-proxy not found**: Ensure `mcp-proxy` is installed in your image (check `/root/.local/bin/` or `/root/.cargo/bin/`)
   - **Start command fails**: Verify the `startCommand` path exists and is executable in your image
   - **Missing dependencies**: Your image needs `bash`, `curl` (for health checks), and `awscli` (if using S3)

3. **Test locally first**:
   ```bash
   # Test that your image has mcp-proxy
   docker run --rm time-mcp-server ls -la /root/.local/bin/mcp-proxy

   # Test the start command path
   docker run --rm time-mcp-server ls -la /app/servers/src/time/dist/index.js
   ```

4. **Health Check**: The system checks if mcp-proxy is responding on port 8080. If health checks fail, the container will be restarted.

### Option 2: Using S3 with Source Files (Alternative)

If you prefer to download the source from S3 at runtime:

```json
{
  "id": "time-mcp-server",
  "name": "Time MCP Server",
  "startCommand": "node src/time/dist/index.js",
  "serverType": "stdio",
  "s3Path": "mcp-servers/time-server/v1.0.0",
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 3,
    "targetValue": 10,
    "metricName": "RequestCountPerTarget",
    "duration": 60,
    "cooldown": 60
  },
  "idpGroups": ["users"],
  "environment": {
    "TZ": "UTC",
    "NODE_ENV": "production"
  }
}
```

**For S3 approach:**
1. Clone the repository: `git clone https://github.com/modelcontextprotocol/servers.git`
2. Build the time server: `cd servers && npm install && npm run build`
3. Upload the built files to S3:
   ```bash
   aws s3 sync servers/src/time/ s3://YOUR_BUCKET/mcp-servers/time-server/v1.0.0/
   ```
4. The system will automatically generate a Node.js-based Dockerfile

### Complete cURL Command for Testing (ECR Image)

```bash
curl -X POST \
  "https://{API_GATEWAY_URL}/mcp" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "time-mcp-server",
    "name": "Time MCP Server",
    "image": "YOUR_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/time-mcp-server:latest",
    "startCommand": "node /app/servers/src/time/dist/index.js",
    "serverType": "stdio",
    "autoScalingConfig": {
      "minCapacity": 1,
      "maxCapacity": 3,
      "targetValue": 10,
      "metricName": "RequestCountPerTarget",
      "duration": 60,
      "cooldown": 60
    },
    "idpGroups": ["users"],
    "environment": {
      "TZ": "UTC",
      "NODE_ENV": "production"
    }
  }'
```

**Note:** Replace the placeholders:
- `{API_GATEWAY_URL}` - Your API Gateway URL
- `{AUTH_TOKEN}` - Your authentication token
- `YOUR_ACCOUNT_ID` - Your AWS account ID
- `YOUR_REGION` - Your AWS region (e.g., `us-east-1`)
- `["users"]` - Update to your actual IDP groups

### Finding the Correct Start Command

If the built file path differs, verify it:

**To check the correct path:**
1. Build your Dockerfile locally: `docker build -t time-mcp-server .`
2. Check the structure:
   ```bash
   docker run --rm time-mcp-server ls -la /app/servers/src/time/
   docker run --rm time-mcp-server ls -la /app/servers/src/time/dist/
   ```
3. Update the `startCommand` in the JSON payload with the actual path to the built `index.js` file

**Common paths:**
- `node /app/servers/src/time/dist/index.js` (direct from clone - recommended)
- `node src/time/dist/index.js` (if working directory is set to /app/servers/src/time)

---

## cURL Examples for Creating Servers

### Create STDIO Server

```bash
curl -X POST \
  "https://{API_GATEWAY_URL}/mcp" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my-stdio-server",
    "name": "My STDIO MCP Server",
    "startCommand": "/app/server/my-server-binary",
    "serverType": "stdio",
    "s3Path": "mcp-servers/my-server/v1.0.0/binaries",
    "autoScalingConfig": {
      "minCapacity": 1,
      "maxCapacity": 5,
      "targetValue": 10
    },
    "idpGroups": ["admin", "developers"]
  }'
```

### Create HTTP Server

```bash
curl -X POST \
  "https://{API_GATEWAY_URL}/mcp" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "python-mcp-server",
    "name": "Python HTTP MCP Server",
    "startCommand": "python3 /app/server/server.py",
    "port": 8000,
    "serverType": "http",
    "s3Path": "mcp-servers/python-server/v1.0.0",
    "autoScalingConfig": {
      "minCapacity": 2,
      "maxCapacity": 10,
      "targetValue": 20
    },
    "idpGroups": ["users"],
    "environment": {
      "PYTHONUNBUFFERED": "1"
    }
  }'
```

---

## Payload Field Reference

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier for the server (used in API Gateway routes) |
| `name` | string | Human-readable name for the server |
| `startCommand` | string | Command to start the server (e.g., `"python3 server.py"`, `"/app/server/binary"`) |
| `autoScalingConfig` | object | Auto-scaling configuration (see below) |
| `idpGroups` | string[] | Array of IDP groups authorized to access this server |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `port` | number | Auto-detected | Port number for HTTP/SSE servers |
| `serverType` | `'stdio' \| 'http' \| 'sse'` | Auto-detected | Explicit server type |
| `s3Path` | string | - | S3 path to server artifacts (binaries, source files) |
| `image` | string | - | Pre-built container image (ECR or Docker Hub) |
| `environment` | object | {} | Environment variables for the container |
| `taskExecutionRoleArn` | string | Auto-created | IAM role ARN for task execution |
| `taskRoleArn` | string | Auto-created | IAM role ARN for running tasks |

### Auto-scaling Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `minCapacity` | number | **Required** | Minimum number of tasks |
| `maxCapacity` | number | **Required** | Maximum number of tasks |
| `targetValue` | number | - | Target metric value for scaling |
| `metricName` | string | `"RequestCountPerTarget"` | CloudWatch metric name |
| `duration` | number | 60 | Metric evaluation period (seconds) |
| `cooldown` | number | 60 | Cooldown period between scaling actions (seconds) |

### Server Type Auto-detection

The system automatically detects server type if not explicitly provided:

1. **If `serverType` is set**: Use that value
2. **Else if `port` is provided**: Assume `"http"`
3. **Else if command contains "sse" or "server-sent"**: Assume `"sse"`
4. **Else**: Default to `"stdio"`

### Container Base Image Selection

When building from S3 artifacts, the base image is automatically selected based on `startCommand`:

- **Python**: `python:3.12-slim-bookworm` (if command contains `python` or `.py`)
- **Node.js**: `node:20-slim` (if command contains `node` or `npm`)
- **Rust**: `rust:1-slim-bullseye` (if command contains `cargo` or `rust`)
- **Default**: `python:3.12-slim-bookworm`

---

## Variables

Replace these placeholders in the examples:
- `{API_GATEWAY_URL}` - Your API Gateway base URL (e.g., `https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod`)
- `{SERVER_ID}` - The server identifier (normalized from `id` or `name`, alphanumeric only)
  - Example: If your `id` is `"my-mcp-server"`, the identifier becomes `"mymcpserver"`
  - Example: If your `id` is `"test_server_123"`, the identifier becomes `"testserver123"`
- `{AUTH_TOKEN}` - Your API authorization token (Bearer token or API key, depending on your authorizer)

## API Gateway Routes

The MCP server deployment creates two API Gateway routes under the existing `/mcp` resource:

1. **Root Route**: `/mcp/{SERVER_ID}` - Routes directly to the server root
2. **Proxy Route**: `/mcp/{SERVER_ID}/{proxy+}` - Routes with path proxying

---

## Testing WITHOUT Proxy (Root Route)

### Example 1: Health Check (GET request to root)

```bash
curl -X GET \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/health" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json"
```

### Example 2: MCP Initialize (POST request to root)

```bash
curl -X POST \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    }
  }'
```

### Example 3: Server Info (GET request to root)

```bash
curl -X GET \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json"
```

---

## Testing WITH Proxy (Proxy Route)

### Example 4: Health Check via Proxy

```bash
curl -X GET \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/health" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json"
```

Note: The `/health` path is captured by the `{proxy+}` wildcard and forwarded to the server.

### Example 5: MCP Tools List via Proxy

```bash
curl -X POST \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/mcp/v1/tools/list" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

The path `/mcp/v1/tools/list` is forwarded to the server as the `proxy` path.

### Example 6: MCP Tool Call via Proxy

```bash
curl -X POST \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/mcp/v1/tools/call" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "example_tool",
      "arguments": {
        "param1": "value1"
      }
    }
  }'
```

### Example 7: Custom Server Endpoint via Proxy

```bash
curl -X GET \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/api/v1/status" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json"
```

### Example 8: Nested Paths via Proxy

```bash
curl -X POST \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/api/v2/resource/create" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "example",
    "data": {"key": "value"}
  }'
```

---

## Testing with HTTPie

If you prefer using `httpie`:

### Without Proxy:
```bash
http GET \
  "{API_GATEWAY_URL}/mcp/{SERVER_ID}/health" \
  "Authorization:Bearer {AUTH_TOKEN}"
```

### With Proxy:
```bash
http POST \
  "{API_GATEWAY_URL}/mcp/{SERVER_ID}/mcp/v1/tools/list" \
  "Authorization:Bearer {AUTH_TOKEN}" \
  jsonrpc="2.0" id:=2 method="tools/list"
```

---

## Testing with Python Requests

```python
import requests

api_gateway_url = "https://{API_GATEWAY_URL}"
server_id = "{SERVER_ID}"
auth_token = "{AUTH_TOKEN}"

headers = {
    "Authorization": f"Bearer {auth_token}",
    "Content-Type": "application/json"
}

# Without proxy - root endpoint
response = requests.get(
    f"{api_gateway_url}/mcp/{server_id}/health",
    headers=headers
)
print(f"Health Check Status: {response.status_code}")
print(f"Response: {response.text}")

# With proxy - MCP tools list
payload = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
}
response = requests.post(
    f"{api_gateway_url}/mcp/{server_id}/mcp/v1/tools/list",
    headers=headers,
    json=payload
)
print(f"Tools List Status: {response.status_code}")
print(f"Response: {response.json()}")
```

---

## Testing with JavaScript/Node.js

```javascript
const fetch = require('node-fetch');

const API_GATEWAY_URL = 'https://{API_GATEWAY_URL}';
const SERVER_ID = '{SERVER_ID}';
const AUTH_TOKEN = '{AUTH_TOKEN}';

const headers = {
  'Authorization': `Bearer ${AUTH_TOKEN}`,
  'Content-Type': 'application/json'
};

// Without proxy - health check
async function testHealthCheck() {
  const response = await fetch(
    `${API_GATEWAY_URL}/mcp/${SERVER_ID}/health`,
    { method: 'GET', headers }
  );
  console.log('Health Check:', await response.text());
}

// With proxy - MCP tools list
async function testToolsList() {
  const payload = {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/list',
    params: {}
  };

  const response = await fetch(
    `${API_GATEWAY_URL}/mcp/${SERVER_ID}/mcp/v1/tools/list`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    }
  );
  console.log('Tools List:', await response.json());
}

// Run tests
testHealthCheck();
testToolsList();
```

---

## Testing OPTIONS (CORS Preflight)

The OPTIONS method bypasses authorization for CORS preflight requests:

```bash
curl -X OPTIONS \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/health" \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: GET"
```

---

## Common Test Scenarios

### 1. STDIO Server (via mcp-proxy)
STDIO servers are automatically wrapped with `mcp-proxy` and exposed on port 8080.

```bash
# Health check
curl -X GET \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/health" \
  -H "Authorization: Bearer {AUTH_TOKEN}"

# MCP protocol calls
curl -X POST \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

### 2. HTTP Server
HTTP servers with their own port (e.g., 8000):

```bash
# Custom health endpoint
curl -X GET \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/health" \
  -H "Authorization: Bearer {AUTH_TOKEN}"

# Custom API endpoints
curl -X POST \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/api/v1/endpoint" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"key":"value"}'
```

### 3. SSE Server
Server-Sent Events servers:

```bash
# SSE endpoint (may use proxy or root depending on implementation)
curl -X GET \
  "https://{API_GATEWAY_URL}/mcp/{SERVER_ID}/events" \
  -H "Authorization: Bearer {AUTH_TOKEN}" \
  -H "Accept: text/event-stream"
```

---

## Expected Responses

### Success Response (200)
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "serverInfo": {
      "name": "mcp-server",
      "version": "1.0.0"
    }
  }
}
```

### Error Response (400/500)
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32600,
    "message": "Invalid Request"
  }
}
```

### Health Check Response
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Troubleshooting

### Finding Your Server Identifier

The server identifier is created by normalizing your `id` or `name`:
- Removes all non-alphanumeric characters
- Example: `"my-mcp-server"` → `"mymcpserver"`
- Example: `"test_server_123"` → `"testserver123"`

### Finding Your API Gateway URL

Check your CloudFormation stack outputs or API Gateway console for the REST API URL.

### Authentication Issues

- Ensure your `{AUTH_TOKEN}` is valid and not expired
- Check that your authorizer is properly configured
- OPTIONS requests do not require authentication (for CORS)

### Path Forwarding

- **Root route** (`/mcp/{SERVER_ID}`): Forwards requests to the server root
- **Proxy route** (`/mcp/{SERVER_ID}/{proxy+}`): Forwards the `{proxy+}` portion as the path
  - Example: `/mcp/myserver/api/health` → Forwards `/api/health` to the server

---

## Notes

- All routes support: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS`
- Authorization is required for all methods except `OPTIONS`
- CORS headers are automatically included in responses
- The proxy path forwarding preserves query parameters and request bodies
