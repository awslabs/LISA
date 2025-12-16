#!/bin/bash
set -e

# Environment variables for LISA deployment
declare -a vars=("S3_BUCKET_MODELS" "LOCAL_MODEL_PATH" "MODEL_NAME" "S3_MOUNT_POINT" "THREADS")

# TEI Configuration Environment Variables (read natively by TEI):
# Performance & Concurrency:
#   MAX_CONCURRENT_REQUESTS - Maximum concurrent requests (default: 512)
#   MAX_BATCH_TOKENS - Maximum tokens per batch (default: 16384)
#   MAX_BATCH_REQUESTS - Maximum requests per batch
#   MAX_CLIENT_BATCH_SIZE - Maximum client batch size (default: 1024)
#   TOKENIZATION_WORKERS - Number of tokenization workers
#
# Model Configuration:
#   REVISION - Model revision/branch to use
#   DTYPE - Data type for model weights (float16, float32, etc.)
#   HUGGINGFACE_HUB_CACHE - Custom cache directory (default: /data)
#   HF_API_TOKEN - Hugging Face API token for private models
#
# Features:
#   AUTO_TRUNCATE - Enable automatic truncation (true/false, default: false)
#   PAYLOAD_LIMIT - Maximum payload size in bytes (default: 2000000)
#
# Network & Security:
#   HOSTNAME - Server hostname (default: container hostname)
#   PORT - Server port (default: 8080, overridden by --port)
#   UDS_PATH - Unix domain socket path (default: /tmp/text-embeddings-inference-server)
#   API_KEY - API key for authentication
#   CORS_ALLOW_ORIGIN - CORS origin configuration
#
# Output & Observability:
#   JSON_OUTPUT - Enable JSON output (true/false, overridden by --json-output)
#   OTLP_ENDPOINT - OpenTelemetry endpoint for metrics
#
# Custom LISA Environment Variables:
#   TEI_POOLING - Pooling method (mean, cls, max, mean_sqrt_len) - not available as native env var

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

# Build additional arguments for TEI (only for parameters not supported via env vars)
ADDITIONAL_ARGS=""

# Pooling configuration (not available as env var)
if [[ -n "${TEI_POOLING}" ]]; then
    ADDITIONAL_ARGS+=" --pooling ${TEI_POOLING}"
    echo "Using pooling method: ${TEI_POOLING}"
fi

# Start the webserver
# TEI natively reads these environment variables:
# - MAX_CONCURRENT_REQUESTS
# - MAX_BATCH_TOKENS
# - MAX_BATCH_REQUESTS
# - MAX_CLIENT_BATCH_SIZE
# - REVISION
# - TOKENIZATION_WORKERS
# - DTYPE
# - AUTO_TRUNCATE
# - PAYLOAD_LIMIT
# - HUGGINGFACE_HUB_CACHE
# - HF_API_TOKEN
# - HOSTNAME
# - PORT
# - UDS_PATH
# - API_KEY
# - JSON_OUTPUT
# - OTLP_ENDPOINT
# - CORS_ALLOW_ORIGIN

echo "Starting TEI with args: ${ADDITIONAL_ARGS}"
echo "TEI environment variables:"
env | grep -E "^(MAX_CONCURRENT_REQUESTS|MAX_BATCH_TOKENS|MAX_BATCH_REQUESTS|MAX_CLIENT_BATCH_SIZE|REVISION|TOKENIZATION_WORKERS|DTYPE|AUTO_TRUNCATE|PAYLOAD_LIMIT|HUGGINGFACE_HUB_CACHE|HF_API_TOKEN|HOSTNAME|PORT|UDS_PATH|API_KEY|JSON_OUTPUT|OTLP_ENDPOINT|CORS_ALLOW_ORIGIN|TEI_POOLING)=" || echo "No TEI environment variables set"

text-embeddings-router --model-id $LOCAL_MODEL_PATH --port 8080 --json-output ${ADDITIONAL_ARGS}
