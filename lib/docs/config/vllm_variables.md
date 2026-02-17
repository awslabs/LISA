# vLLM Environment Variables

LISA Serve supports configuring vLLM model serving through environment variables. These variables allow you to control performance, memory usage, parallelization, and advanced features when deploying models with vLLM.
- **NOTE:** Standard vLLM environment variables are supported and passed directly into the VLLM container.  [See vLLM's documentation](https://docs.vllm.ai/en/latest/configuration/env_vars/)

## Core Performance & Memory

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VLLM_GPU_MEMORY_UTILIZATION` | Fraction of GPU memory to use (0.0-1.0) | `0.9` | `0.85` |
| `VLLM_MAX_MODEL_LEN` | Maximum context length override | Auto | `4096` |
| `MAX_TOTAL_TOKENS` | *Legacy alias for `VLLM_MAX_MODEL_LEN`* | Auto | `4096` |

## Model Format & Loading

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VLLM_DTYPE` | Model precision | `auto` | `half`, `float16`, `bfloat16`, `float32` |
| `VLLM_QUANTIZATION` | Quantization method | - | `awq`, `gptq`, `squeezellm`, `fp8` |
| `VLLM_TRUST_REMOTE_CODE` | Allow custom model code execution | `false` | `true` |

## Performance Tuning

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VLLM_MAX_NUM_BATCHED_TOKENS` | Maximum tokens per batch | Auto | `8192` |
| `VLLM_MAX_NUM_SEQS` | Maximum concurrent sequences | `256` | `128`, `512` |
| `VLLM_ENABLE_PREFIX_CACHING` | Enable prefix caching for repeated prompts | `false` | `true` |
| `VLLM_ENABLE_CHUNKED_PREFILL` | Enable chunked prefill | `false` | `true` |
| `VLLM_ASYNC_SCHEDULING` | Adds --async-scheduling for higher performance if hardware supported | `false` | `true` |

## Parallel Processing

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VLLM_TENSOR_PARALLEL_SIZE` | Split model across N GPUs | `1` | `2`, `4`, `8` |

## Tool Calling / Function Calling

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VLLM_ENABLE_AUTO_TOOL_CHOICE` | Enable automatic tool choice routing | `false` | `true` |
| `VLLM_TOOL_CALL_PARSER` | Tool call parser implementation | - | `hermes`, `mistral`, `llama3_json`, `qwen` |

> **Note**: Tool calling requires both `VLLM_ENABLE_AUTO_TOOL_CHOICE=true` and specifying an appropriate `VLLM_TOOL_CALL_PARSER` for your model. See [vLLM Tool Calling Documentation](https://docs.vllm.ai/en/stable/features/tool_calling/) for details.

## Reference

For more details on vLLM configuration, see the [official vLLM documentation](https://docs.vllm.ai/en/latest/configuration/env_vars/).
