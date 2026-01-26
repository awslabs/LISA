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

# Configure logging behavior based on DEBUG environment variable
# Set DEBUG=true in ECS task definition to enable debug logging for all services
if [ "${DEBUG}" = "true" ]; then
    LOG_LEVEL="DEBUG"
    GUNICORN_LOG_LEVEL="debug"
    PRISMA_LOG_LEVEL="info,query"
else
    LOG_LEVEL="${LITELLM_LOG_LEVEL:-INFO}"
    GUNICORN_LOG_LEVEL="info"
    PRISMA_LOG_LEVEL="warn"
fi

# Configure LiteLLM logging
export LITELLM_LOG=${LOG_LEVEL}
export LITELLM_JSON_LOGS=${LITELLM_JSON_LOGS:-false}
export LITELLM_DISABLE_HEALTH_CHECK_LOGS=${LITELLM_DISABLE_HEALTH_CHECK_LOGS:-true}

# Configure Prisma logging
export PRISMA_LOG_LEVEL=${PRISMA_LOG_LEVEL}

# Wait for database to be reachable before starting LiteLLM
# This prevents startup errors from race conditions
if [ -n "$DATABASE_HOST" ] && [ -n "$DATABASE_PORT" ]; then
    echo "🔍 Checking database connectivity..."
    echo "   - Host: $DATABASE_HOST"
    echo "   - Port: $DATABASE_PORT"
    
    MAX_RETRIES=30
    RETRY_INTERVAL=2
    retry_count=0
    
    while [ $retry_count -lt $MAX_RETRIES ]; do
        if timeout 5 bash -c "echo > /dev/tcp/$DATABASE_HOST/$DATABASE_PORT" 2>/dev/null; then
            echo "✅ Database is reachable"
            break
        fi
        retry_count=$((retry_count + 1))
        echo "   - Waiting for database... (attempt $retry_count/$MAX_RETRIES)"
        sleep $RETRY_INTERVAL
    done
    
    if [ $retry_count -eq $MAX_RETRIES ]; then
        echo "⚠️  Database not reachable after $MAX_RETRIES attempts, proceeding anyway..."
    fi
fi

# Start LiteLLM in the background with better error handling
# Note: For IAM RDS authentication, LiteLLM handles token refresh natively
# when IAM_TOKEN_DB_AUTH=true is set (configured via CDK environment variables)
echo "🚀 Starting LiteLLM server..."
echo "   - Config file: litellm_config.yaml"
echo "   - Port: 4000 (internal)"
echo "   - Database: Prisma with auto-push enabled"
echo "   - Debug mode: ${DEBUG:-false}"
echo "   - Log level: $LOG_LEVEL"
echo "   - Prisma log level: $PRISMA_LOG_LEVEL"
if [ "$IAM_TOKEN_DB_AUTH" = "true" ]; then
    echo "   - IAM Auth: enabled (tokens auto-refresh)"
    echo "   - Database User: $DATABASE_USER"
fi

# Start LiteLLM and capture its PID
# Note: Transient DB connection errors may appear during IAM token refresh cycles
# These are expected with LiteLLM < 1.81 and the service recovers automatically
# Set LITELLM_LOG_LEVEL=INFO to see all logs, or DEBUG for verbose output
litellm -c litellm_config.yaml --use_prisma_db_push > litellm.log 2>&1 &
LITELLM_PID=$!

echo "   - LiteLLM PID: $LITELLM_PID"
echo "   - Log file: litellm.log"

# Tail the log file to stdout so Docker can capture it
tail -f litellm.log &
TAIL_PID=$!

echo "   - Log tail PID: $TAIL_PID"

# LiteLLM is starting in the background, proceed with Gunicorn startup

# Validate THREADS variable with default value
THREADS=${THREADS:-4}
echo "🚀 Starting Gunicorn with $THREADS workers..."

# Start Gunicorn with Uvicorn workers
echo "   - Host: $HOST"
echo "   - Port: $PORT"
echo "   - Workers: $THREADS"
echo "   - Timeout: 600 seconds"
echo "   - Log level: $GUNICORN_LOG_LEVEL"

# Set PYTHONPATH to include src directory so imports work correctly
export PYTHONPATH="/app/src:${PYTHONPATH:-}"

exec gunicorn -k uvicorn.workers.UvicornWorker -t 600 -w "$THREADS" -b "$HOST:$PORT" \
    --log-level "$GUNICORN_LOG_LEVEL" \
    "src.main:app"
