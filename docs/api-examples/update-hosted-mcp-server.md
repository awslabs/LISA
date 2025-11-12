# Hosted MCP Server Update API Examples

Use these examples to update an existing Hosted MCP server. Replace the placeholders before running:

- API_BASE: your API base URL (for example: https://abc123.execute-api.us-east-1.amazonaws.com/v2)
- SERVER_ID: ID of the hosted MCP server to update
- TOKEN: a valid bearer token

Endpoint

- Method: PUT
- URL: {API_BASE}/mcp/{SERVER_ID}
- Headers:
  - Authorization: Bearer {TOKEN}
  - Content-Type: application/json

Notes and constraints

- Do not combine enabled with autoScalingConfig in the same request.
- CPU must be one of: 256, 512, 1024, 2048, 4096.
- memoryLimitMiB must be between 512 and 30720.
- To delete an environment variable, set its value to "LISA_MARKED_FOR_DELETION".
- Groups are stored with a "group:" prefix automatically; pass plain names like "engineering" and the system will store "group:engineering".

---

## curl examples

Enable a server (STOPPED → STARTING → IN_SERVICE)

```bash
curl -X PUT \
  "$API_BASE/mcp/$SERVER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true
  }'
```

Disable a server (IN_SERVICE → STOPPING → STOPPED)

```bash
curl -X PUT \
  "$API_BASE/mcp/$SERVER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false
  }'
```

Update autoscaling (partial updates allowed; do not include "enabled" with this)

```bash
curl -X PUT \
  "$API_BASE/mcp/$SERVER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "autoScalingConfig": {
      "minCapacity": 1,
      "maxCapacity": 3,
      "cooldown": 120
    }
  }'
```

Add or update environment variables

```bash
curl -X PUT \
  "$API_BASE/mcp/$SERVER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "environment": {
      "FOO": "bar",
      "LOG_LEVEL": "info"
    }
  }'
```

Delete an environment variable

```bash
curl -X PUT \
  "$API_BASE/mcp/$SERVER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "environment": {
      "FOO": "LISA_MARKED_FOR_DELETION"
    }
  }'
```

Update CPU and memory

```bash
curl -X PUT \
  "$API_BASE/mcp/$SERVER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cpu": 512,
    "memoryLimitMiB": 2048
  }'
```

Update container health checks

```bash
curl -X PUT \
  "$API_BASE/mcp/$SERVER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "containerHealthCheckConfig": {
      "command": ["CMD-SHELL", "curl -f http://127.0.0.1:8000/health || exit 1"],
      "interval": 30,
      "timeout": 5,
      "startPeriod": 0,
      "retries": 3
    }
  }'
```

Update description and groups

```bash
curl -X PUT \
  "$API_BASE/mcp/$SERVER_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Internal tools server",
    "groups": ["engineering", "platform"]
  }'
```

---

## HTTPie examples

```bash
http PUT "$API_BASE/mcp/$SERVER_ID" \
  Authorization:"Bearer $TOKEN" \
  Content-Type:"application/json" \
  enabled:=true
```

```bash
http PUT "$API_BASE/mcp/$SERVER_ID" \
  Authorization:"Bearer $TOKEN" \
  Content-Type:"application/json" \
  autoScalingConfig:='{"minCapacity":2,"maxCapacity":5,"cooldown":90}'
```

```bash
http PUT "$API_BASE/mcp/$SERVER_ID" \
  Authorization:"Bearer $TOKEN" \
  Content-Type:"application/json" \
  environment:='{"FOO":"bar","REMOVE_ME":"LISA_MARKED_FOR_DELETION"}'
```

```bash
http PUT "$API_BASE/mcp/$SERVER_ID" \
  Authorization:"Bearer $TOKEN" \
  Content-Type:"application/json" \
  cpu:=1024 memoryLimitMiB:=4096
```

```bash
http PUT "$API_BASE/mcp/$SERVER_ID" \
  Authorization:"Bearer $TOKEN" \
  Content-Type:"application/json" \
  containerHealthCheckConfig:='{"command":["CMD-SHELL","healthcheck.sh"],"interval":30,"timeout":5,"startPeriod":0,"retries":3}'
```

```bash
http PUT "$API_BASE/mcp/$SERVER_ID" \
  Authorization:"Bearer $TOKEN" \
  Content-Type:"application/json" \
  description="Internal tools" groups:='["engineering","platform"]'
```

---

## Python (requests) example

```python
import os
import json
import requests

API_BASE = os.environ["API_BASE"]
SERVER_ID = os.environ["SERVER_ID"]
TOKEN = os.environ["TOKEN"]

def update_hosted_mcp_server(payload: dict) -> dict:
    url = f"{API_BASE}/mcp/{SERVER_ID}"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.put(url, headers=headers, data=json.dumps(payload), timeout=30)
    resp.raise_for_status()
    return resp.json()

# Enable
update_hosted_mcp_server({"enabled": True})

# Autoscaling (separate request from enabled)
update_hosted_mcp_server({"autoScalingConfig": {"minCapacity": 1, "maxCapacity": 3, "cooldown": 120}})

# Env vars (add/update and delete)
update_hosted_mcp_server({"environment": {"FOO": "bar", "REMOVE_ME": "LISA_MARKED_FOR_DELETION"}})

# CPU/memory
update_hosted_mcp_server({"cpu": 512, "memoryLimitMiB": 2048})

# Container health check
update_hosted_mcp_server({
    "containerHealthCheckConfig": {
        "command": ["CMD-SHELL", "curl -f http://127.0.0.1:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "startPeriod": 0,
        "retries": 3
    }
})

# Metadata (description, groups)
update_hosted_mcp_server({"description": "Internal tools server", "groups": ["engineering", "platform"]})
```
