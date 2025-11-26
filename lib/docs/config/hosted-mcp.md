# Hosted MCP Servers

## Overview

LISA MCP provides scalable infrastructure to support the deployment and hosting of first-party MCP servers and tools.
It is a stand-alone solution that can either be deployed independently of LISA Serve, or configured to work seamlessly
with LISA Serve. Each MCP server deployed via LISA MCP is provisioned on AWS Fargate via Amazon ECS, fronted by
Application/Network Load Balancers, and published through the existing API Gateway. This allows chat sessions to securely invoke
MCP tools without leaving your VPC. Every route remains protected by the same API Gateway Lambda authorizer that guards the rest
of LISA, so API Keys, IDP lockdown, and JWT group enforcement continue to apply automatically. Because the endpoints are
standard HTTP routes behind API Gateway, you can also share them with trusted third-party agents, copilots, or workflow engines
outside of LISA while preserving the same authentication store; you may issue API keys, short-lived JWTs, or IDP credentials, and those external consumers can use the MCP server just like LISA chat clients. The Create, Update, Delete workflows are orchestrated by
Step Functions and are auditable through DynamoDB status records.

## Key Features

- **Turn‑key hosting** – Deploy STDIO, HTTP, or SSE MCP servers with a single API/UI workflow
- **Dynamic container builds** – Bring a pre-built image or point to S3 artifacts that are turned into a container at deploy time
- **mcp-proxy support** – STDIO servers are automatically wrapped with `mcp-proxy` and exposed over HTTP
- **Auto scaling** – Configure Fargate min/max capacity, custom metrics, and scaling targets per server
- **Secure networking** – Private VPC networking with ALB for internal traffic and NLB + VPC Link for API Gateway access
- **Group-aware routing** – Limit server visibility to specific identity provider groups or make them public (`lisa:public`)
- **Lifecycle automation** – Step Functions manage provisioning, health polling, failure handling, and connection publishing
- **UI & API parity** – Manage servers through the MCP Management admin page or the `/mcp` REST endpoints
- **External integrations** – Exposed via API Gateway URLs so external copilots, RPA bots, or SaaS workloads can invoke
  the hosted MCP server using the same credentials and auth controls you already enforce in LISA

## Architecture

### Workflow

1. **Create request** – Admin issues `POST /{stage}/mcp` (or uses the UI) with a `HostedMcpServerModel` payload.
2. **DynamoDB record** – The Lambda API validates the payload, enforces unique normalized names, and writes the server
   record with status `CREATING`.
3. **State machine** – The `CreateMcpServer` Step Functions workflow executes:
   - `handle_set_server_to_creating` – persists status
   - `handle_deploy_server` – calls the MCP server deployer Lambda with the sanitized config
   - `handle_poll_deployment` – waits for the CloudFormation stack to finish
   - `handle_add_server_to_active` – marks the record `IN_SERVICE` and (optionally) publishes a connection for the chat UI
4. **Deployer Lambda** – Synthesizes a dedicated CloudFormation stack that builds/launches an ECS Fargate service,
   load balancers, VPC Link integration, and optional auto scaling targets.
5. **API Gateway** – Receives MCP traffic on `/mcp/{serverId}` and forwards through the VPC Link/NLB to the Fargate task.

### Data Storage

- **`MCP_SERVERS_TABLE`** – Primary metadata store (status, scaling config, networking details, groups).
- **`McpConnectionsTable`** (optional) – When `DEPLOYMENT_PREFIX` is set, completed servers are published here so the
  chat application can surface them alongside externally hosted connections.
- **SSM** – Stores the Lisa API base URL (`LisaApiUrl`) and the optional hosted connections table name.

### Networking

- ECS tasks run inside your VPC using the same subnets/security groups as the MCP API stack.
- An **Application Load Balancer** fronts internal traffic while a **Network Load Balancer** terminates the API Gateway
  VPC Link.
- STDIO servers always expose port `8080` (via `mcp-proxy`); HTTP/SSE servers use the configured `port` (default `8000`).
- API clients send JWTs; the MCP server receives `Authorization: Bearer {LISA_BEARER_TOKEN}`, which LISA replaces per user
  when establishing a connection.
- API Gateway enforces the same Lambda authorizer used across LISA (JWT validation + optional API key checks). If
  **API Key Required** or **IDP Lockdown** is enabled at the stage, hosted MCP endpoints automatically inherit those
  protections—no extra configuration is necessary on the server itself.
- External consumers (agents, other apps, automation) call the same API Gateway URLs; simply provision them API keys or
  federated identities and they gain access to the MCP server without any direct network connectivity to the VPC.

## Prerequisites

- Administrator access to LISA and the MCP Management UI.
- MCP Server Connections feature enabled (see [Model Context Protocol (MCP)](./mcp.md)).
- AWS resources created by `deploylisa` (state machines, MCP API stack, hosting bucket, etc.).
- S3 bucket path (if you need to sync binaries, Python files, or configuration at container start).
- Optional pre-built ECR image ARN or Docker Hub image reference (if not using dynamic builds).
- Identified server type (`stdio`, `http`, or `sse`) and the exact `startCommand` to launch it.
- IAM task execution/task roles if your container must call other AWS services (otherwise defaults are generated).

## Deployment Flow

1. **Prepare artifacts**
   - Upload your MCP server files to the hosting bucket (e.g., `s3://<bucket>/servers/my-server/`), or publish a container
     image that already includes the server runtime.
2. **Send create request**
   - Use the REST API or MCP Management UI to submit the configuration (see examples below).
3. **Monitor progress**
   - The UI surfaces status transitions (`CREATING → IN_SERVICE`). For API-only workflows, poll `GET /{stage}/mcp/{id}` or
     view the Step Functions execution in CloudWatch for stack details.
4. **Publish to users**
   - Once `IN_SERVICE`, the server automatically appears on the MCP Management table. If groups are defined, only members
     of those groups will see the connection by default.

## Configuration Reference

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | ✅ | Human-friendly name (must normalize to a unique alphanumeric identifier). |
| `description` | string | | Optional UI description. |
| `serverType` | `'stdio' \| 'http' \| 'sse'` | ✅ | Determines networking and entrypoint behavior. STDIO servers run behind `mcp-proxy`. |
| `startCommand` | string | ✅ | Command executed inside the container (e.g., `python server.py`). |
| `s3Path` | string | | Optional `bucket/path` pointing at artifacts to sync into `/app/server`. |
| `image` | string | | Container image to start from. If omitted, a base image is selected automatically based on `serverType`. |
| `port` | number | | TCP port exposed by HTTP/SSE servers. STDIO servers default to `8080`. |
| `cpu` | number | | Fargate CPU units (256, 512, 1024, 2048, 4096). Defaults to 256. |
| `memoryLimitMiB` | number | | Fargate memory in MiB (min 512, max 30720). Defaults to 512. |
| `autoScalingConfig.minCapacity` | number | ✅ | Minimum number of tasks (must be ≥ 1). |
| `autoScalingConfig.maxCapacity` | number | ✅ | Maximum number of tasks (must be ≥ minCapacity). |
| `autoScalingConfig.targetValue` | number | | Target metric value (e.g., requests per target). |
| `autoScalingConfig.metricName` | string | | Optional custom metric identifier. |
| `autoScalingConfig.duration` | number | | Scaling lookback window (seconds). |
| `autoScalingConfig.cooldown` | number | | Cooldown between scaling actions (seconds). |
| `loadBalancerConfig.healthCheckConfig.*` | object | | Optional ALB health check overrides (`path`, `interval`, `timeout`, `healthyThresholdCount`, `unhealthyThresholdCount`). |
| `containerHealthCheckConfig.*` | object | | Optional ECS task health checks (`command`, `interval`, `startPeriod`, `timeout`, `retries`). |
| `environment` | map<string,string> | | Extra environment variables for your server. Avoid putting secrets here—use AWS Secrets Manager or SSM and reference them from your code. |
| `taskExecutionRoleArn` | string | | Execution role to pull private images / read from ECR or S3. Generated automatically if omitted. |
| `taskRoleArn` | string | | Task role used by your server code to call AWS APIs. Generated automatically if omitted. |
| `groups` | string[] | | Identity provider groups allowed to see/use the server. Prefix is added automatically if missing (`group:finance`). Empty/null defaults to `lisa:public`. |

## Example: Create a Hosted MCP Server

```bash
curl -X POST https://api.example.com/prod/mcp \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "docs-mcp-workbench",
    "description": "Company knowledge base tools",
    "serverType": "stdio",
    "startCommand": "python main.py",
    "autoScalingConfig": { "minCapacity": 1, "maxCapacity": 2, "targetValue": 80 },
    "s3Path": "servers/docs-mcp/",
    "cpu": 512,
    "memoryLimitMiB": 1024,
    "environment": {
      "TOOLS_DIR": "/app/server/tools",
      "LOG_LEVEL": "info"
    },
    "loadBalancerConfig": {
      "healthCheckConfig": {
        "path": "/health",
        "interval": 30,
        "timeout": 5,
        "healthyThresholdCount": 2,
        "unhealthyThresholdCount": 3
      }
    },
    "containerHealthCheckConfig": {
      "command": "curl -f http://localhost:8080/healthz",
      "interval": 30,
      "startPeriod": 10,
      "timeout": 5,
      "retries": 3
    },
    "groups": ["group:admins"]
  }'
```

Response (truncated):

```json
{
  "id": "3f5a…",
  "name": "docs-mcp-workbench",
  "status": "Creating",
  "autoScalingConfig": {
    "minCapacity": 1,
    "maxCapacity": 2
  },
  "stack_name": null
}
```

## API Operations

| Method & Path | Description |
|---------------|-------------|
| `POST /{stage}/mcp` | Create a hosted server (admin only). |
| `GET /{stage}/mcp` | List hosted servers (admin only). |
| `GET /{stage}/mcp/{serverId}` | Retrieve a single hosted server, including current status and stack info. |
| `PUT /{stage}/mcp/{serverId}` | Update auto scaling, environment, health checks, or enable/disable the service. Only servers in `IN_SERVICE` or `STOPPED` can be updated. |
| `DELETE /{stage}/mcp/{serverId}` | Begin the teardown workflow. Only `IN_SERVICE`, `STOPPED`, or `FAILED` servers can be deleted. |

> **Tip:** The Update API accepts an `UpdateHostedMcpServerRequest` payload. Use the `enabled` flag to start/stop an
> existing server; supply `autoScalingConfig`, `environment`, or health-check fields to update those aspects. The request
> must include at least one field or validation will fail.

## MCP Management UI Workflow

1. **Navigate** – Select **Admin → MCP Management** in the top navigation (admin-only).
2. **Create** – Click **Create hosted MCP server** to open the wizard:
   - **Server details** – Name, owner visibility (public vs. private), server type, start command, optional S3 path/image,
     environment variables, and group assignments.
   - **Scaling** – Min/max capacity, CPU/memory, optional custom metric target.
   - **Health checks** – Configure ALB and container checks or accept the defaults.
3. **Review & launch** – Submit the form. A banner will display the provisioning status and surface Step Functions failure
   messages if any arise.
4. **Manage** – Use the action bar to **Edit**, **Delete**, **Start**, or **Stop** selected servers. Bulk actions are
   available when multiple rows are selected.
5. **Monitor** – Columns expose current status, stack name, owner, groups, and timestamps. Use the table preferences panel
   to adjust visible columns or export the data.

## Working with S3 Artifacts

- Uploaded files are synced into `/app/server` before the `startCommand` runs. Ensure your script either resides at the
  root of that directory or adjusts paths accordingly.
- Make your scripts executable (`chmod +x`) when copying to S3 if they are shell/binary files.
- If you provide both `image` and `s3Path`, the image is used as the base layer and the artifacts overwrite/add files at
  runtime. This is useful for extending a golden image with per-server content.
- Grant the specified task role `s3:GetObject` permissions on the hosting bucket path. When using the default role, LISA
  automatically injects the policy.

## Best Practices

- **Unique names** – Server names are normalized to alphanumeric characters for stack/resource naming. Choose descriptive
  names and avoid collisions.
- **Secrets management** – Do not embed secrets in `environment`. Instead, fetch them from AWS Secrets Manager or SSM in
  your server code.
- **Scaling guardrails** – Start with conservative `minCapacity` values and validate CPU/memory usage before increasing
  `maxCapacity`.
- **Health checks** – Provide both container and load balancer health checks so the workflow can detect failures early.
- **Group scoping** – Restrict access to high-privilege tools by assigning identity provider groups at creation time.
- **Testing** – Use the [MCP Workbench](./mcp-workbench.md) to iterate on tools locally, then package the same files for
  hosted deployment.
- **Monitoring** – Use CloudWatch metrics/alarms for the ECS service, Application Load Balancer, and the Step Functions
  workflows to detect regressions quickly.

## Troubleshooting

### Create API returns *“CREATE_MCP_SERVER_SFN_ARN not configured”*
- **Cause:** Environment variables were not set when the MCP API Lambda was deployed.
- **Resolution:** Re-run `deploylisa` or manually set `CREATE_MCP_SERVER_SFN_ARN`, `DELETE_MCP_SERVER_SFN_ARN`, and
  `UPDATE_MCP_SERVER_SFN_ARN` on the MCP API Lambda, then retry.

### Error *“Server name conflicts with existing server”*
- **Cause:** Another record normalizes to the same alphanumeric identifier (e.g., `Docs-MCP` vs `docs_mcp`).
- **Resolution:** Choose a different name or delete the prior server before re-creating it.

### Stack stuck in `CREATING`
- **Cause:** CloudFormation deployment failed (missing IAM roles, invalid container image, unreachable S3 path).
- **Resolution:** Inspect the `CreateMcpServer` Step Functions execution, then open the CloudFormation stack events to
  identify the failing resource. Fix the underlying issue and re-run the create workflow.

### Hosted server is `IN_SERVICE` but unreachable
- **Cause:** Incorrect `port`, health check, or security group settings.
- **Resolution:** Verify the ALB target group health, container logs, and that the application is listening on the
  expected port. For STDIO servers, ensure the `startCommand` launches an MCP-compatible process that `mcp-proxy` can wrap.

### Bearer token placeholder not replaced
- **Cause:** Custom headers still show `{LISA_BEARER_TOKEN}`.
- **Resolution:** The placeholder is replaced at connection time. Make sure the consuming application sends an
  `Authorization` header when invoking the MCP connection. The API automatically replaces the placeholder right before
  returning connection details.

### Update API rejects payload
- **Cause:** The `UpdateHostedMcpServerRequest` validator requires at least one field; it also blocks simultaneous
  enable/disable and auto scaling changes.
- **Resolution:** Split enable/disable operations from scaling updates, and include only the fields you intend to change.
