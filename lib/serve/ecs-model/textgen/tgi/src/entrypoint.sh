#!/bin/bash
set -e

# Environment variables for LISA deployment
declare -a vars=("S3_BUCKET_MODELS" "LOCAL_MODEL_PATH" "MODEL_NAME" "S3_MOUNT_POINT" "THREADS")

# TGI Configuration Environment Variables (read natively by TGI):
#
# PERFORMANCE & CONCURRENCY:
#   MAX_CONCURRENT_REQUESTS - Maximum concurrent requests (default: 128)
#   MAX_INPUT_LENGTH - Maximum input sequence length (default: 1024)
#   MAX_TOTAL_TOKENS - Maximum total tokens (input + output, default: 2048)
#   MAX_BATCH_PREFILL_TOKENS - Maximum tokens for prefill batching
#   MAX_BATCH_TOTAL_TOKENS - Maximum total tokens per batch
#   WAITING_SERVED_RATIO - Ratio of waiting vs served requests (default: 1.2)
#
# MODEL CONFIGURATION:
#   QUANTIZE - Quantization method (bitsandbytes/bitsandbytes-nf4/bitsandbytes-fp4/eetq/awq/gptq)
#   DTYPE - Model data type (float16/bfloat16/float32)
#   TRUST_REMOTE_CODE - Allow custom model code (true/false)
#   REVISION - Model revision/branch to use
#
# HARDWARE & PARALLELISM:
#   NUM_SHARD - Number of shards for tensor parallelism (default: 1)
#   CUDA_VISIBLE_DEVICES - GPU devices to use (default: "0")
#   CUDA_MEMORY_FRACTION - Fraction of GPU memory to use (0.0-1.0)
#
# ATTENTION & OPTIMIZATION:
#   ATTENTION - Attention implementation (paged/flashinfer)
#   SPECULATE - Number of speculative tokens (default: 0)
#   ROPE_SCALING - RoPE scaling method (linear/dynamic)
#   ROPE_FACTOR - RoPE scaling factor
#
# LOGGING & OUTPUT:
#   JSON_OUTPUT - Enable JSON output (true/false, default: false)
#   LOG_LEVEL - Logging level (TRACE/DEBUG/INFO/WARN/ERROR)
#   OTLP_ENDPOINT - OpenTelemetry endpoint for metrics
#
# TOKENIZER:
#   TOKENIZER_CONFIG_PATH - Custom tokenizer config path
#   DISABLE_CUSTOM_KERNELS - Disable custom CUDA kernels (true/false)
#
# Custom LISA Environment Variables:
#   (None - TGI uses standard environment variables)

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

# Set default values for required environment variables
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export NUM_SHARD="${NUM_SHARD:-1}"

# Build minimal arguments (TGI reads most config from environment variables)
startArgs=()
startArgs+=('--model-id' "${LOCAL_MODEL_PATH}")
startArgs+=('--port' '8080')
startArgs+=('--json-output')

# Start the webserver
# TGI natively reads environment variables for configuration
echo "Starting TGI with args: ${startArgs[*]}"
echo "TGI environment variables:"
env | grep -E "^(MAX_CONCURRENT_REQUESTS|MAX_INPUT_LENGTH|MAX_TOTAL_TOKENS|MAX_BATCH_PREFILL_TOKENS|MAX_BATCH_TOTAL_TOKENS|WAITING_SERVED_RATIO|QUANTIZE|DTYPE|TRUST_REMOTE_CODE|REVISION|NUM_SHARD|CUDA_VISIBLE_DEVICES|CUDA_MEMORY_FRACTION|ATTENTION|SPECULATE|ROPE_SCALING|ROPE_FACTOR|JSON_OUTPUT|LOG_LEVEL|OTLP_ENDPOINT|TOKENIZER_CONFIG_PATH|DISABLE_CUSTOM_KERNELS)=" || echo "No TGI environment variables set"

text-generation-launcher "${startArgs[@]}"
