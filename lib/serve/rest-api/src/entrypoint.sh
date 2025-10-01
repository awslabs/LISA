#!/bin/bash
set -e

# Host and port configuration
HOST="0.0.0.0"
PORT="8080"

echo "Starting LISA REST API Service"
echo "=================================="

# Prisma client is now generated during build from LiteLLM's schema
echo "Prisma client already generated during build"

# Update LiteLLM config that was already copied from config.yaml with runtime-deployed models.
# Depends on SSM Parameter for registered models.
echo "🔧 Configuring LiteLLM..."
echo "   - AWS Region: $AWS_REGION"
echo "   - Models Parameter: $REGISTERED_MODELS_PS_NAME"
echo "   - DB Info Parameter: $LITELLM_DB_INFO_PS_NAME"

# Generate LiteLLM config with error handling
if ! python ./src/utils/generate_litellm_config.py -f litellm_config.yaml; then
    echo "❌ Failed to generate LiteLLM configuration"
    echo "   This usually indicates issues with:"
    echo "   - SSM parameter access permissions"
    echo "   - Database connection parameters"
    echo "   - Model registration data"
    exit 1
fi

echo "✅ LiteLLM configuration generated successfully"

# Verify config file exists and has content
if [ ! -f "litellm_config.yaml" ]; then
    echo "❌ LiteLLM config file not found after generation"
    exit 1
fi

echo "📄 LiteLLM config file contents:"
echo "--------------------------------"
head -20 litellm_config.yaml
echo "--------------------------------"

# Start LiteLLM in the background with better error handling
echo "🚀 Starting LiteLLM server..."
echo "   - Config file: litellm_config.yaml"
echo "   - Port: 4000 (internal)"
echo "   - Database: Prisma with auto-push enabled"

# Start LiteLLM and capture its PID
litellm -c litellm_config.yaml --use_prisma_db_push > litellm.log 2>&1 &
LITELLM_PID=$!

echo "   - LiteLLM PID: $LITELLM_PID"
echo "   - Log file: litellm.log"

# LiteLLM is starting in the background, proceed with Gunicorn startup

# Validate THREADS variable with default value
THREADS=${THREADS:-4}
echo "🚀 Starting Gunicorn with $THREADS workers..."

# Start Gunicorn with Uvicorn workers
echo "   - Host: $HOST"
echo "   - Port: $PORT"
echo "   - Workers: $THREADS"
echo "   - Timeout: 600 seconds"

exec gunicorn -k uvicorn.workers.UvicornWorker -t 600 -w "$THREADS" -b "$HOST:$PORT" "src.main:app"
