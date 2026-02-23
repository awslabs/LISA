#!/bin/bash
set -e

# Environment variables for LISA deployment
declare -a vars=("S3_BUCKET_MODELS" "LOCAL_MODEL_PATH" "MODEL_NAME" "S3_MOUNT_POINT" "THREADS")

# vLLM Configuration Environment Variables (read natively by vLLM):
# Based on official vLLM documentation: https://docs.vllm.ai/en/latest/configuration/env_vars/
#
# CORE PERFORMANCE & MEMORY:
#   VLLM_GPU_MEMORY_UTILIZATION - GPU memory usage fraction (0.0-1.0, default: 0.9)
#   VLLM_CPU_OFFLOAD_GB - Offload model layers to CPU memory (GB)
#   VLLM_SWAP_SPACE - Disk swap space for memory overflow (GB)
#   VLLM_ENFORCE_EAGER - Disable CUDA graphs for debugging (true/false)
#   VLLM_MAX_MODEL_LEN - Maximum context length override
#   VLLM_ALLOW_LONG_MAX_MODEL_LEN - Allow context length > model config (true/false)
#
# PARALLEL PROCESSING & DISTRIBUTED:
#   VLLM_TENSOR_PARALLEL_SIZE - Split model across GPUs (1,2,4,8)
#   VLLM_PIPELINE_PARALLEL_SIZE - Pipeline parallelism stages
#   VLLM_DATA_PARALLEL_SIZE - Data parallel replicas
#   VLLM_DISTRIBUTED_EXECUTOR_BACKEND - Backend (ray/mp)
#   VLLM_WORKER_USE_RAY - Use Ray for workers (true/false)
#   VLLM_ENGINE_USE_RAY - Use Ray for engine (true/false)
#   VLLM_WORKER_MULTIPROC_METHOD - Multiprocess method (spawn/fork)
#   LOCAL_RANK - Local rank in distributed setting
#   CUDA_VISIBLE_DEVICES - GPU devices to use
#
# MODEL FORMAT & LOADING:
#   VLLM_LOAD_FORMAT - Model format (auto/pt/safetensors/npcache/dummy)
#   VLLM_DTYPE - Model precision (auto/half/float16/bfloat16/float/float32)
#   VLLM_KV_CACHE_DTYPE - KV cache precision (auto/fp8/fp8_e5m2/fp8_e4m3)
#   VLLM_QUANTIZATION - Quantization method (awq/gptq/squeezellm/fp8/etc)
#   VLLM_TRUST_REMOTE_CODE - Allow custom model code (true/false)
#   VLLM_REVISION - Model revision/branch to use
#   VLLM_TOKENIZER_REVISION - Tokenizer revision/branch
#   VLLM_USE_MODELSCOPE - Load from ModelScope instead of HF Hub (true/false)
#
# PERFORMANCE TUNING:
#   VLLM_MAX_NUM_BATCHED_TOKENS - Max tokens per batch
#   VLLM_MAX_NUM_SEQS - Max concurrent sequences (default: 256)
#   VLLM_MAX_PADDINGS - Max padding tokens per batch
#   VLLM_BLOCK_SIZE - Memory block size (8/16/32)
#   VLLM_SEED - Random seed for reproducibility
#   VLLM_FLOAT32_MATMUL_PRECISION - Float32 matmul precision (ieee/tf32)
#   VLLM_ASYNC_SCHEDULING - Adds --async-scheduling for higher performance
#
# ATTENTION & BACKENDS:
#   VLLM_ATTENTION_BACKEND - Attention backend (FLASH_ATTN/XFORMERS/ROCM_FLASH/TORCH_SDPA/FLASHINFER/etc)
#   VLLM_ENABLE_PREFIX_CACHING - Enable prefix caching (true/false, default: true)
#   VLLM_ENABLE_CHUNKED_PREFILL - Enable chunked prefill (true/false, default: true)
#   VLLM_MAX_CHUNKED_PREFILL_TOKENS - Max tokens per prefill chunk
#   VLLM_FLASH_ATTN_VERSION - Force Flash Attention version (2/3)
#   VLLM_USE_FLASHINFER_SAMPLER - Use FlashInfer sampler (true/false)
#
# COMPILATION & OPTIMIZATION:
#   VLLM_USE_AOT_COMPILE - Enable AOT compilation (true/false)
#   VLLM_FORCE_AOT_LOAD - Force loading AOT compiled models (true/false)
#   VLLM_USE_STANDALONE_COMPILE - Enable Inductor standalone compile (true/false)
#   VLLM_DISABLE_COMPILE_CACHE - Disable compilation cache (true/false)
#   VLLM_USE_V2_MODEL_RUNNER - Enable v2 model runner (true/false)
#
# SPECULATIVE DECODING:
#   VLLM_SPECULATIVE_MODEL - Draft model for speculative decoding
#   VLLM_NUM_SPECULATIVE_TOKENS - Number of speculative tokens
#   VLLM_SPECULATIVE_DRAFT_TENSOR_PARALLEL_SIZE - Draft model tensor parallel size
#
# MULTI-MODAL MODELS:
#   VLLM_IMAGE_FETCH_TIMEOUT - Timeout for fetching images (seconds, default: 5)
#   VLLM_VIDEO_FETCH_TIMEOUT - Timeout for fetching videos (seconds, default: 30)
#   VLLM_AUDIO_FETCH_TIMEOUT - Timeout for fetching audio (seconds, default: 10)
#   VLLM_MAX_AUDIO_CLIP_FILESIZE_MB - Max audio file size (MB, default: 25)
#
# LORA SUPPORT:
#   VLLM_ENABLE_LORA - Enable LoRA adapters (true/false)
#   VLLM_MAX_LORAS - Maximum number of LoRA adapters
#   VLLM_MAX_LORA_RANK - Maximum LoRA rank
#   VLLM_LORA_EXTRA_VOCAB_SIZE - Extra vocabulary for LoRA
#   VLLM_LORA_DTYPE - LoRA precision (auto/float16/bfloat16)
#   VLLM_ALLOW_RUNTIME_LORA_UPDATING - Allow runtime LoRA updates (true/false)
#
# LOGGING & DEBUGGING:
#   VLLM_CONFIGURE_LOGGING - Configure vLLM logging (true/false, default: true)
#   VLLM_LOGGING_LEVEL - Logging level (DEBUG/INFO/WARN/ERROR, default: INFO)
#   VLLM_LOGGING_CONFIG_PATH - Custom logging config file path
#   VLLM_LOG_STATS_INTERVAL - Stats logging interval (seconds, default: 10)
#   VLLM_TRACE_FUNCTION - Trace function calls for debugging (true/false)
#   VERBOSE - Enable verbose installation logs (true/false)
#
# CACHE & STORAGE:
#   VLLM_CACHE_ROOT - Root directory for vLLM cache files
#   VLLM_CONFIG_ROOT - Root directory for vLLM config files
#   VLLM_ASSETS_CACHE - Path for storing downloaded assets
#   VLLM_XLA_CACHE_PATH - XLA persistent cache directory (TPU)
#
# NETWORKING & API:
#   VLLM_HOST_IP - IP address for distributed communication
#   VLLM_PORT - Communication port for distributed setup
#   VLLM_API_KEY - API key for vLLM API server
#   VLLM_ENGINE_ITERATION_TIMEOUT_S - Timeout per engine iteration (seconds, default: 60)
#   VLLM_HTTP_TIMEOUT_KEEP_ALIVE - HTTP keep-alive timeout (seconds, default: 5)
#
# ADVANCED FEATURES:
#   VLLM_USE_TRITON_AWQ - Use Triton implementations of AWQ (true/false)
#   VLLM_FUSED_MOE_CHUNK_SIZE - Fused MoE chunk size (default: 16384)
#   VLLM_KEEP_ALIVE_ON_ENGINE_DEATH - Keep API server alive on engine error (true/false)
#   VLLM_SLEEP_WHEN_IDLE - Reduce CPU usage when idle (true/false)
#
# TOOL CALLING / FUNCTION CALLING (opt-in):
#   VLLM_ENABLE_AUTO_TOOL_CHOICE - Enable automatic tool choice routing (set to "true" to enable)
#   VLLM_TOOL_CALL_PARSER - Tool call parser name (hermes/mistral/llama3_json/qwen/etc.)
#
# ROCM SPECIFIC (AMD GPUs):
#   VLLM_ROCM_USE_AITER - Enable AITER ops on ROCm (true/false)
#   VLLM_ROCM_USE_SKINNY_GEMM - Use skinny GEMM on ROCm (true/false)
#   VLLM_ROCM_CUSTOM_PAGED_ATTN - Use custom paged attention on MI3* (true/false)
#
# Custom LISA Environment Variables:
#   MAX_TOTAL_TOKENS - Alias for VLLM_MAX_MODEL_LEN (for backward compatibility)

# Check the necessary environment variables
for var in "${vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "$var must be set"
        exit 1
    fi
done

# Create S3 mount point to ephemeral NVMe drive
echo "Creating S3 mountpoint for bucket ${S3_BUCKET_MODELS} at container mount point path ${S3_MOUNT_POINT}/${MODEL_NAME}"
mkdir -p ${S3_MOUNT_POINT}
mount-s3 ${S3_BUCKET_MODELS} ${S3_MOUNT_POINT}

echo "Downloading model ${S3_BUCKET_MODELS} to container path ${LOCAL_MODEL_PATH}"
mkdir -p ${LOCAL_MODEL_PATH}

# Use rsync with S3_MOUNT_POINT
ls ${S3_MOUNT_POINT}/${MODEL_NAME} | xargs -n1 -P${THREADS} -I% rsync -Pa --exclude "*.bin" ${S3_MOUNT_POINT}/${MODEL_NAME}/% ${LOCAL_MODEL_PATH}/

# Build additional arguments for parameters not supported via env vars
ADDITIONAL_ARGS=""

# Backward compatibility: MAX_TOTAL_TOKENS -> VLLM_MAX_MODEL_LEN
if [[ -n "${MAX_TOTAL_TOKENS}" ]] && [[ -z "${VLLM_MAX_MODEL_LEN}" ]]; then
  export VLLM_MAX_MODEL_LEN="${MAX_TOTAL_TOKENS}"
fi

# Check available memory and set defaults if not specified
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024))
echo "Total system memory: ${TOTAL_MEM_GB}GB"

# Check GPU availability
GPU_MEM_GB=0
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d '[:space:]')
    if [[ "${GPU_INFO}" =~ ^[0-9]+$ ]]; then
        GPU_MEM_GB=$((GPU_INFO / 1024))
        echo "GPU memory available: ${GPU_MEM_GB}GB"
    else
        echo "Warning: nvidia-smi returned unexpected output: '${GPU_INFO}', assuming no GPU"
    fi
else
    echo "No GPU detected or nvidia-smi not available"
fi

# Memory warnings and recommendations
if [[ -z "${VLLM_DEVICE}" ]] && [[ ${TOTAL_MEM_GB} -lt 20 ]]; then
  echo "Warning: Low system memory detected (${TOTAL_MEM_GB}GB)."
  if [[ ${GPU_MEM_GB} -gt 16 ]]; then
    echo "Recommendation: GPU has sufficient memory (${GPU_MEM_GB}GB), model should load on GPU"
  else
    echo "Recommendation: Consider using CPU-only mode with VLLM_DEVICE=cpu or upgrade instance type"
  fi
fi

# Validate tensor parallel configuration
if [[ -n "${VLLM_TENSOR_PARALLEL_SIZE}" ]] && [[ ${VLLM_TENSOR_PARALLEL_SIZE} -gt 1 ]]; then
    GPU_COUNT=$(nvidia-smi --list-gpus 2>/dev/null | wc -l || echo 0)
    if [[ ${GPU_COUNT} -eq 0 ]]; then
        echo "Warning: Tensor parallelism requested (${VLLM_TENSOR_PARALLEL_SIZE}) but no GPUs detected - proceeding anyway"
    else
        echo "Using tensor parallelism with ${VLLM_TENSOR_PARALLEL_SIZE} GPUs (${GPU_COUNT} detected)"
    fi
fi

# Start the webserver
# vLLM reads some VLLM_* environment variables natively, but many require CLI args
# Map environment variables to CLI arguments for full control

echo "Building vLLM CLI arguments from environment variables..."

# GPU memory utilization (0.0-1.0)
if [[ -n "${VLLM_GPU_MEMORY_UTILIZATION}" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --gpu-memory-utilization ${VLLM_GPU_MEMORY_UTILIZATION}"
    echo "  --gpu-memory-utilization ${VLLM_GPU_MEMORY_UTILIZATION}"
fi

# Max model length (context window)
if [[ -n "${VLLM_MAX_MODEL_LEN}" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --max-model-len ${VLLM_MAX_MODEL_LEN}"
    echo "  --max-model-len ${VLLM_MAX_MODEL_LEN}"
fi

# Max number of batched tokens per iteration
if [[ -n "${VLLM_MAX_NUM_BATCHED_TOKENS}" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --max-num-batched-tokens ${VLLM_MAX_NUM_BATCHED_TOKENS}"
    echo "  --max-num-batched-tokens ${VLLM_MAX_NUM_BATCHED_TOKENS}"
fi

# Max number of sequences (concurrent requests)
if [[ -n "${VLLM_MAX_NUM_SEQS}" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --max-num-seqs ${VLLM_MAX_NUM_SEQS}"
    echo "  --max-num-seqs ${VLLM_MAX_NUM_SEQS}"
fi

# Enable prefix caching
if [[ "${VLLM_ENABLE_PREFIX_CACHING}" == "true" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --enable-prefix-caching"
    echo "  --enable-prefix-caching"
fi

# Enable chunked prefill
if [[ "${VLLM_ENABLE_CHUNKED_PREFILL}" == "true" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --enable-chunked-prefill"
    echo "  --enable-chunked-prefill"
fi

# Data type (auto, half, float16, bfloat16, float, float32)
if [[ -n "${VLLM_DTYPE}" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --dtype ${VLLM_DTYPE}"
    echo "  --dtype ${VLLM_DTYPE}"
fi

# Tensor parallel size (for multi-GPU)
if [[ -n "${VLLM_TENSOR_PARALLEL_SIZE}" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --tensor-parallel-size ${VLLM_TENSOR_PARALLEL_SIZE}"
    echo "  --tensor-parallel-size ${VLLM_TENSOR_PARALLEL_SIZE}"
fi

# Attention backend override
if [[ -n "${VLLM_ATTENTION_BACKEND}" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --attention-backend ${VLLM_ATTENTION_BACKEND}"
    echo "  --attention-backend ${VLLM_ATTENTION_BACKEND}"
fi

# Quantization method
if [[ -n "${VLLM_QUANTIZATION}" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --quantization ${VLLM_QUANTIZATION}"
    echo "  --quantization ${VLLM_QUANTIZATION}"
fi

# Trust remote code (for custom models)
if [[ "${VLLM_TRUST_REMOTE_CODE}" == "true" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --trust-remote-code"
    echo "  --trust-remote-code"
fi

# Enable tool calling support (opt-in only)
# These flags are required for models that support function/tool calling with tool_choice: "auto"
# (e.g., Qwen, Mistral, Llama, etc.)
# See https://docs.vllm.ai/en/stable/features/tool_calling/
if [[ "${VLLM_ENABLE_AUTO_TOOL_CHOICE}" == "true" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --enable-auto-tool-choice"
    echo "  --enable-auto-tool-choice"
fi

if [[ -n "${VLLM_TOOL_CALL_PARSER}" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --tool-call-parser ${VLLM_TOOL_CALL_PARSER}"
    echo "  --tool-call-parser ${VLLM_TOOL_CALL_PARSER}"
fi

if [[ "${VLLM_ASYNC_SCHEDULING}" == "true" ]]; then
    ADDITIONAL_ARGS="${ADDITIONAL_ARGS} --async-scheduling"
    echo "  --async-scheduling"
fi

echo "Starting vLLM with args: ${ADDITIONAL_ARGS}"
# Print all VLLM_ environment variables at startup
echo "=== VLLM Environment Variables ==="
env | grep -E "^VLLM_" || echo "No VLLM_ environment variables set"
echo "==================================="


python3 -m vllm.entrypoints.openai.api_server \
    --model ${LOCAL_MODEL_PATH} \
    --served-model-name ${MODEL_NAME} \
    --port 8080 \
    ${ADDITIONAL_ARGS}
