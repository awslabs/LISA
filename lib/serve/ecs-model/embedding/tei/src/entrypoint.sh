#!/bin/bash
set -e

# Environment variables for LISA deployment
declare -a vars=("S3_BUCKET_MODELS" "LOCAL_MODEL_PATH" "MODEL_NAME" "S3_MOUNT_POINT" "THREADS")

# TEI Configuration Environment Variables
# Based on official TEI documentation: https://huggingface.co/docs/text-embeddings-inference/cli_arguments
#
# PERFORMANCE & BATCHING (Critical for throughput):
#   MAX_CONCURRENT_REQUESTS - Maximum concurrent requests (default: 512)
#   MAX_BATCH_TOKENS - Maximum tokens per batch (default: 16384) **CRITICAL for GPU utilization**
#   MAX_BATCH_REQUESTS - Maximum requests per batch (optional)
#   MAX_CLIENT_BATCH_SIZE - Maximum inputs per client request (default: 32)
#   TOKENIZATION_WORKERS - Number of tokenization workers (default: CPU cores)
#
# MODEL CONFIGURATION:
#   REVISION - Model revision/branch to use
#   DTYPE - Data type for model weights (float16, float32)
#   POOLING - Pooling method (cls, mean, splade, last-token)
#   DEFAULT_PROMPT_NAME - Default prompt name from model config
#   DEFAULT_PROMPT - Default prompt text to prepend
#   DENSE_PATH - Path to Dense module for some models
#   SERVED_MODEL_NAME - Model name for OpenAI-compatible endpoints
#
# INPUT HANDLING:
#   AUTO_TRUNCATE - Automatically truncate long inputs (true/false)
#   PAYLOAD_LIMIT - Maximum payload size in bytes (default: 2000000)
#
# AUTHENTICATION & NETWORK:
#   HF_TOKEN - Hugging Face API token for private models
#   API_KEY - API key for request authorization
#   HOSTNAME - Server hostname (default: 0.0.0.0)
#   PORT - Server port (default: 3000, overridden to 8080)
#   UDS_PATH - Unix domain socket path
#   CORS_ALLOW_ORIGIN - CORS origin configuration
#
# OBSERVABILITY:
#   JSON_OUTPUT - Enable JSON output (true/false)
#   OTLP_ENDPOINT - OpenTelemetry endpoint for tracing
#   OTLP_SERVICE_NAME - Service name for OpenTelemetry
#   PROMETHEUS_PORT - Prometheus metrics port (default: 9000)
#   DISABLE_SPANS - Disable tracing spans
#
# STORAGE:
#   HUGGINGFACE_HUB_CACHE - Custom cache directory

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

# Build CLI arguments from environment variables
# TEI reads some env vars natively, but we explicitly pass them as CLI args for clarity
ADDITIONAL_ARGS=""

echo "Building TEI CLI arguments from environment variables..."

# Performance & Batching
if [[ -n "${MAX_CONCURRENT_REQUESTS}" ]]; then
    ADDITIONAL_ARGS+=" --max-concurrent-requests ${MAX_CONCURRENT_REQUESTS}"
    echo "  --max-concurrent-requests ${MAX_CONCURRENT_REQUESTS}"
fi

if [[ -n "${MAX_BATCH_TOKENS}" ]]; then
    ADDITIONAL_ARGS+=" --max-batch-tokens ${MAX_BATCH_TOKENS}"
    echo "  --max-batch-tokens ${MAX_BATCH_TOKENS}"
fi

if [[ -n "${MAX_BATCH_REQUESTS}" ]]; then
    ADDITIONAL_ARGS+=" --max-batch-requests ${MAX_BATCH_REQUESTS}"
    echo "  --max-batch-requests ${MAX_BATCH_REQUESTS}"
fi

if [[ -n "${MAX_CLIENT_BATCH_SIZE}" ]]; then
    ADDITIONAL_ARGS+=" --max-client-batch-size ${MAX_CLIENT_BATCH_SIZE}"
    echo "  --max-client-batch-size ${MAX_CLIENT_BATCH_SIZE}"
fi

if [[ -n "${TOKENIZATION_WORKERS}" ]]; then
    ADDITIONAL_ARGS+=" --tokenization-workers ${TOKENIZATION_WORKERS}"
    echo "  --tokenization-workers ${TOKENIZATION_WORKERS}"
fi

# Model Configuration
if [[ -n "${REVISION}" ]]; then
    ADDITIONAL_ARGS+=" --revision ${REVISION}"
    echo "  --revision ${REVISION}"
fi

if [[ -n "${DTYPE}" ]]; then
    ADDITIONAL_ARGS+=" --dtype ${DTYPE}"
    echo "  --dtype ${DTYPE}"
fi

if [[ -n "${POOLING}" ]]; then
    ADDITIONAL_ARGS+=" --pooling ${POOLING}"
    echo "  --pooling ${POOLING}"
fi

if [[ -n "${DEFAULT_PROMPT_NAME}" ]]; then
    ADDITIONAL_ARGS+=" --default-prompt-name ${DEFAULT_PROMPT_NAME}"
    echo "  --default-prompt-name ${DEFAULT_PROMPT_NAME}"
fi

if [[ -n "${DEFAULT_PROMPT}" ]]; then
    ADDITIONAL_ARGS+=" --default-prompt \"${DEFAULT_PROMPT}\""
    echo "  --default-prompt \"${DEFAULT_PROMPT}\""
fi

if [[ -n "${DENSE_PATH}" ]]; then
    ADDITIONAL_ARGS+=" --dense-path ${DENSE_PATH}"
    echo "  --dense-path ${DENSE_PATH}"
fi

if [[ -n "${SERVED_MODEL_NAME}" ]]; then
    ADDITIONAL_ARGS+=" --served-model-name ${SERVED_MODEL_NAME}"
    echo "  --served-model-name ${SERVED_MODEL_NAME}"
fi

# Input Handling
if [[ "${AUTO_TRUNCATE}" == "true" ]]; then
    ADDITIONAL_ARGS+=" --auto-truncate"
    echo "  --auto-truncate"
fi

if [[ -n "${PAYLOAD_LIMIT}" ]]; then
    ADDITIONAL_ARGS+=" --payload-limit ${PAYLOAD_LIMIT}"
    echo "  --payload-limit ${PAYLOAD_LIMIT}"
fi

# Authentication
if [[ -n "${HF_TOKEN}" ]]; then
    ADDITIONAL_ARGS+=" --hf-token ${HF_TOKEN}"
    echo "  --hf-token [REDACTED]"
fi

if [[ -n "${API_KEY}" ]]; then
    ADDITIONAL_ARGS+=" --api-key ${API_KEY}"
    echo "  --api-key [REDACTED]"
fi

# Observability
if [[ -n "${OTLP_ENDPOINT}" ]]; then
    ADDITIONAL_ARGS+=" --otlp-endpoint ${OTLP_ENDPOINT}"
    echo "  --otlp-endpoint ${OTLP_ENDPOINT}"
fi

if [[ -n "${OTLP_SERVICE_NAME}" ]]; then
    ADDITIONAL_ARGS+=" --otlp-service-name ${OTLP_SERVICE_NAME}"
    echo "  --otlp-service-name ${OTLP_SERVICE_NAME}"
fi

if [[ -n "${PROMETHEUS_PORT}" ]]; then
    ADDITIONAL_ARGS+=" --prometheus-port ${PROMETHEUS_PORT}"
    echo "  --prometheus-port ${PROMETHEUS_PORT}"
fi

if [[ "${DISABLE_SPANS}" == "true" ]]; then
    ADDITIONAL_ARGS+=" --disable-spans"
    echo "  --disable-spans"
fi

# CORS
if [[ -n "${CORS_ALLOW_ORIGIN}" ]]; then
    ADDITIONAL_ARGS+=" --cors-allow-origin ${CORS_ALLOW_ORIGIN}"
    echo "  --cors-allow-origin ${CORS_ALLOW_ORIGIN}"
fi

# Start the webserver
echo "Starting TEI with args: ${ADDITIONAL_ARGS}"
echo "TEI environment variables:"
env | grep -E "^(MAX_CONCURRENT_REQUESTS|MAX_BATCH_TOKENS|MAX_BATCH_REQUESTS|MAX_CLIENT_BATCH_SIZE|TOKENIZATION_WORKERS|REVISION|DTYPE|POOLING|DEFAULT_PROMPT|DENSE_PATH|SERVED_MODEL_NAME|AUTO_TRUNCATE|PAYLOAD_LIMIT|HF_TOKEN|API_KEY|OTLP_ENDPOINT|PROMETHEUS_PORT|CORS_ALLOW_ORIGIN)=" || echo "No TEI environment variables set"

text-embeddings-router --model-id $LOCAL_MODEL_PATH --port 8080 --json-output ${ADDITIONAL_ARGS}
