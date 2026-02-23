# Claude Code Setup for LISA Serve

This guide explains how to configure Claude Code with LISA Serve

### References
- [Claude Code Documentation](https://code.claude.com/docs)
- [Claude Cote LLM Gateway Configuration](https://code.claude.com/docs/en/llm-gateway)

### Prerequisites
- LISA instance deployed and accessible
- LISA serve endpoint URL
- LISA API key (See API Key Management)
- A model deployed via LISA Serve

### Setup Steps

1. **Configure Claude Code Environment Variables**:
   ```bash
   # Set the base URL to your LISA endpoint
   # Find it on cloudformation in the LISA-lisa-serve-<STAGE> stack in the outputs tab
   export ANTHROPIC_BASE_URL=https://your-lisa-serve-endpoint.com # Typically ends in '/v2/serve'

   # You can generate an API key in the API Key Management Page on LISA's UI
   export ANTHROPIC_AUTH_TOKEN=your-lisa-api-key

   # Specify your models, they must match your LISA model ids
   export ANTHROPIC_MODEL=your-lisa-model-id
   export ANTHROPIC_SMALL_FAST_MODEL=your-lisa-fast-model-id

   export ANTHROPIC_DEFAULT_SONNET_MODEL = your-lisa-model-id
   export ANTHROPIC_DEFAULT_OPUS_MODEL = your-lisa-model-id
   export ANTHROPIC_DEFAULT_HAIKU_MODEL = your-lisa-model-id
   export CLAUDE_CODE_SUBAGENT_MODEL = your-lisa-model-id

   export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = 1 # Disable experimental beta options

   export CLAUDE_CODE_MAX_OUTPUT_TOKENS = 4192 # Adjust according to your model's requirements
   export MAX_THINKING_TOKENS = 8192 # set to 0 to disable thinking
   ```


## Verification

After configuration, verify your setup:

```bash
# Start Claude Code with a simple prompt
claude "hello world"
```

### Testing in the VSCode extension
You have two options to test if the configuration is working
1. Open new claude code tab (This should reload the environment variables depending on your configuration)
2. Reload the vscode window

## Troubleshooting

### LISA Endpoint Issues
- Verify endpoint is accessible: `curl https://your-lisa-endpoint.com/health`
- Check API key is valid
- Confirm model names match LISA configuration
