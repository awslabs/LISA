# LISA Langfuse Integration Guide

Langfuse is an open source tool that supports advanced traces, evals, and metrics. This guide provides step-by-step instructions for integrating Langfuse with LISA to enable tracing and monitoring of LLM interactions.

## Prerequisites

First ensure that Langfuse is properly deployed by either:

- Creating a managed Langfuse account at [Langfuse Cloud](https://langfuse.com)
- Self-hosting Langfuse using the [official self-hosting documentation](https://langfuse.com/self-hosting)

### Initial Langfuse Setup

After deploying Langfuse, complete the following setup steps:

1. Navigate to the Langfuse web interface
2. Create a user account
3. Create an organization
4. Create a project within the organization
5. Generate API credentials (Public Key and Secret Key)

Retain the generated API credentials as they will be required for the LISA configuration in Step 1.

## Configuration Steps

### Step 1: Update LiteLLM Configuration

Configure the LiteLLM integration by updating the `litellmConfig` section in the `config-base.yaml` file:

```yaml
litellmConfig:
  callbacks: ["langfuse"]
  LANGFUSE_HOST: {YOUR_LANGFUSE_ENDPOINT}
  LANGFUSE_PUBLIC_KEY: pk-{YOUR_PUBLIC_KEY}
  LANGFUSE_SECRET_KEY: sk-{YOUR_SECRET_KEY}
```

Replace the placeholder values with the appropriate Langfuse endpoint and API credentials obtained during the initial setup.

### Step 2: Update Python Dependencies

Add the Langfuse Python package to the LISA Serve REST API dependencies by including the following line in the [`requirements.txt`](https://github.com/awslabs/LISA/blob/main/lib/serve/rest-api/src/requirements.txt) file located at `lib/serve/rest-api/src/`:

```
langfuse>=3.0.0
```

### Step 3: Configure Environment Variables

#### Update Configuration Schema

Modify the `LiteLLMConfig` schema in the [`configSchema.ts`](https://github.com/awslabs/LISA/blob/main/lib/schema/configSchema.ts#L758) file located at `lib/schema/configSchema.ts` to include the Langfuse environment variables:

```typescript
const LiteLLMConfig = z.object({
    db_key: z.string().refine(
        ...
    ),
    general_settings: z.any().optional(),
    litellm_settings: z.any().optional(),
    router_settings: z.any().optional(),
    environment_variables: z.any().optional(),
    callbacks: z.array(z.string()).optional().describe('LiteLLM callbacks to enable (e.g., ["langfuse"])'),
    LANGFUSE_HOST: z.string().optional().describe('Langfuse host URL (e.g., https://us.cloud.langfuse.com)'),
    LANGFUSE_PUBLIC_KEY: z.string().optional().describe('Langfuse public key for authentication'),
    LANGFUSE_SECRET_KEY: z.string().optional().describe('Langfuse secret key for authentication'),
})
```

#### Update FastAPI Container Environment

Modify the [`fastApiContainer.ts`](https://github.com/awslabs/LISA/blob/95a38b055044b0930df7b66ca4fa25dc58fddcd8/lib/api-base/fastApiContainer.ts#L64) file located at `lib/api-base/fastApiContainer.ts` to include the Langfuse environment variables in the `baseEnvironment`:

```typescript
if (config.litellmConfig.LANGFUSE_HOST) {
    baseEnvironment.LANGFUSE_HOST = config.litellmConfig.LANGFUSE_HOST;
}
if (config.litellmConfig.LANGFUSE_PUBLIC_KEY) {
    baseEnvironment.LANGFUSE_PUBLIC_KEY = config.litellmConfig.LANGFUSE_PUBLIC_KEY;
}
if (config.litellmConfig.LANGFUSE_SECRET_KEY) {
    baseEnvironment.LANGFUSE_SECRET_KEY = config.litellmConfig.LANGFUSE_SECRET_KEY;
}
```

### Step 4: Implement Langfuse

#### Decorate the LiteLLM Passthrough Function

> [!WARNING] The implementation in this section is designed for non-streamed responses. Streaming responses require additional implementation considerations for properly handling `StreamingResponse` objects.

Add the Langfuse observe decorator to the [`litellm_passthrough`](https://github.com/awslabs/LISA/blob/main/lib/serve/rest-api/src/api/endpoints/v2/litellm_passthrough.py#L94) function located at `lib/serve/rest-api/src/api/endpoints/v2/litellm_passthrough.py`:

```python
from langfuse import observe

@router.api_route("/{api_path:path}", methods=["GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE", "HEAD"])
@observe()
async def litellm_passthrough(request: Request, api_path: str) -> Response:
    ...
```

> [!NOTE] The decorator order is significant. The `@observe()` decorator must be positioned directly above the function definition.

## Verification and Monitoring

### Deployment and Testing

After completing all configuration changes, redeploy LISA. Once the deployment is successful, interactions with models via LISA will automatically send telemetry data to Langfuse.

Access the Langfuse tracing interface to view collected traces.

### Trace Structure

#### Non-Streamed Response Traces

Non-streamed responses generate traces with the following structure:

**Input:**
```json
{
    "args": [],
    "kwargs": {
        "api_path": "chat/completions",
        "request": {}
    }
}
```

**Output:**
```json
{
    "status_code": 200,
    "background": null,
    "body": {
        "id": "chatcmpl-4c0f3c88-12d9-4e4d-a38e-9c83fabfa9df",
        "created": 1758912436,
        "model": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        "object": "chat.completion",
        "choices": [
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {
                    "content": "Hi there! I notice we're just exchanging greetings. Is there something I can help you with today? I'm happy to assist with questions, provide information on a topic you're interested in, or help with a specific task. Just let me know what you need!",
                    "role": "assistant"
                }
            }
        ],
        "usage": {
            "completion_tokens": 60,
            "prompt_tokens": 1324,
            "total_tokens": 1384,
            "prompt_tokens_details": {
                "cached_tokens": 0
            },
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0
        }
    },
    "raw_headers": [
        [
            "content-length",
            "674"
        ],
        [
            "content-type",
            "application/json"
        ]
    ]
}
```

#### Streamed Response Traces

Streamed responses maintain identical input structure to non-streamed responses but the output differs.

The default trace output for streamed responses are:
```xml
<starlette.responses.StreamingResponse object at 0x7fd112d31b50>
```

#### Advanced Streaming Implementation

For enhanced observability into streaming responses, implement a custom transformation function for the [`generate_response`](https://github.com/awslabs/LISA/blob/main/lib/serve/rest-api/src/api/endpoints/v2/litellm_passthrough.py#L84) function located at `lib/serve/rest-api/src/api/endpoints/v2/litellm_passthrough.py`:

```python
def custom_transformer(line):
    return f"{line}\n\n"

@observe(transform_to_string=custom_transformer)
def generate_response(iterator: Iterator[Union[str, bytes]]) -> Iterator[str]:
    ...
```

The [`transform_to_string`](https://python.reference.langfuse.com/langfuse#observe) parameter enables custom handling of generator chunks, allowing for proper string concatenation and formatting.

## Additional Resources

### Langfuse Docs MCP

For enhanced troubleshooting and integration support, Langfuse provides:

- [Langfuse Docs MCP Server](https://langfuse.com/docs/docs-mcp)
- [Custom Integration Prompt](https://langfuse.com/docs/observability/get-started)

### Reference Documentation

**LiteLLM Integration:**
- [Langfuse Logging with LiteLLM](https://docs.litellm.ai/docs/proxy/logging#langfuse)
- [OpenTelemetry Integration with LiteLLM Proxy](https://litellm.vercel.app/docs/observability/langfuse_otel_integration#with-litellm-proxy)

**Langfuse Documentation:**
- [LiteLLM Proxy with @observe Decorator](https://langfuse.com/guides/cookbook/integration_litellm_proxy)
- [LiteLLM SDK Integration Guide](https://langfuse.com/integrations/frameworks/litellm-sdk)
- [Python SDK Documentation](https://python.reference.langfuse.com/langfuse)
- [Langfuse Self-Hosting Guide](https://langfuse.com/self-hosting)