#!/bin/bash
set -e

# Host and port configuration
HOST="0.0.0.0"
PORT="8080"

# Production mode: disables load_dotenv() so LiteLLM won't try to load credentials
# from .env files. All env vars are injected by ECS task definition / CDK.
export LITELLM_MODE="PRODUCTION"

# Use prisma migrate deploy instead of prisma db push for safe, incremental DB migrations.
# prisma db push can drop columns/tables; migrate deploy only applies forward migrations.
export USE_PRISMA_MIGRATE="True"

# Disable LiteLLM's per-worker schema updates. We run prisma generate + migrate
# once below (before workers spawn) to avoid filesystem write contention when
# multiple Gunicorn workers try to generate the Prisma client simultaneously.
export DISABLE_SCHEMA_UPDATE="true"

echo "Starting LISA REST API Service"
echo "=================================="

# Prisma binaries are cached during Docker build; client generation happens below
# after DB connectivity is confirmed, before workers spawn.

# Generate the LiteLLM config for this environment.
# Model definitions are managed from the database, and DB connection info comes
# from the SSM parameter referenced by LITELLM_DB_INFO_PS_NAME.
echo "🔧 Configuring LiteLLM..."
echo "   - AWS Region: $AWS_REGION"
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

echo "📄 LiteLLM config sections:"
echo "--------------------------------"
python -c 'import yaml
with open("litellm_config.yaml") as f:
    cfg = yaml.safe_load(f)
for section in cfg:
    if section in ("general_settings", "litellm_settings", "router_settings", "callback_settings"):
        print(f"  {section}: {list(cfg[section].keys()) if isinstance(cfg[section], dict) else type(cfg[section]).__name__}")
    elif section == "model_list":
        print(f"  model_list: {len(cfg[section]) if isinstance(cfg[section], list) else 0} models")
    else:
        print(f"  {section}: [set]")
'
echo "--------------------------------"

# If LiteLLM OTEL message_logging is enabled, OTEL console output may still omit
# request/response payloads unless LiteLLM is run in a more verbose mode.
# LiteLLM uses --detailed_debug for this.
LITELLM_DETAILED_DEBUG_ARGS=""
ENABLE_LITELLM_MESSAGE_LOGGING=$(python -c 'import yaml
d=yaml.safe_load(open("litellm_config.yaml")) or {}
cs=d.get("callback_settings") or {}
otel=(cs.get("otel") if isinstance(cs, dict) else {}) or {}
print("true" if otel.get("message_logging") else "false")
')
if [ "$ENABLE_LITELLM_MESSAGE_LOGGING" = "true" ]; then
    echo "   - LiteLLM OTEL message_logging enabled; adding --detailed_debug"
    LITELLM_DETAILED_DEBUG_ARGS="--detailed_debug"
    # Ensure LiteLLM logs at least INFO so message/response payloads can appear in OTEL console output.
    # (Default is WARNING when DEBUG is not set.)
    if [ -z "${LITELLM_LOG_LEVEL:-}" ]; then
        export LITELLM_LOG_LEVEL="INFO"
    fi
fi

# Configure logging behavior based on DEBUG environment variable
# Set DEBUG=true in ECS task definition to enable debug logging for all services
if [ "${DEBUG}" = "true" ]; then
    LOG_LEVEL="DEBUG"
    GUNICORN_LOG_LEVEL="debug"
    PRISMA_LOG_LEVEL="info,query"
    # Use --detailed_debug for maximum LiteLLM verbosity
    LITELLM_DETAILED_DEBUG_ARGS="--detailed_debug"
    # Plain text logs are easier to read when debugging
    export LITELLM_JSON_LOGS=${LITELLM_JSON_LOGS:-false}
else
    LOG_LEVEL="${LITELLM_LOG_LEVEL:-WARNING}"
    GUNICORN_LOG_LEVEL="info"
    PRISMA_LOG_LEVEL="warn"
    # JSON logs are recommended for production (structured logging for CloudWatch/ECS)
    export LITELLM_JSON_LOGS=${LITELLM_JSON_LOGS:-true}
fi

# Configure LiteLLM logging
export LITELLM_LOG=${LOG_LEVEL}
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

# Pre-generate Prisma client and run migrations ONCE before spawning workers.
# This prevents the crash-loop caused by multiple Gunicorn workers simultaneously
# trying to generate the Prisma Python client to the same filesystem path.
# See src/utils/setup_prisma_db.py for full details.
echo "🔧 Pre-generating Prisma client and running migrations..."
python ./src/utils/setup_prisma_db.py

# Symlink schema.prisma into /app so LiteLLM's per-worker schema diff check
# (check_prisma_schema_diff) can find it via the relative path ./schema.prisma.
# Without this, each worker logs "Could not load --to-schema-datamodel from
# provided path schema.prisma: file or directory not found" on startup.
PRISMA_SCHEMA_DIR=$(python -c "import litellm.proxy, os; print(os.path.dirname(litellm.proxy.__file__))")
ln -sf "${PRISMA_SCHEMA_DIR}/schema.prisma" /app/schema.prisma

echo "✅ Prisma setup complete"

# Start LiteLLM in the background with better error handling
# Note: For IAM RDS authentication, LiteLLM handles token refresh natively
# when IAM_TOKEN_DB_AUTH=true is set (configured via CDK environment variables)
echo "🚀 Starting LiteLLM server..."
echo "   - Config file: litellm_config.yaml"
echo "   - Port: 4000 (internal)"
echo "   - Database: Prisma with migrate deploy"
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
# Use --num_workers to increase parallelism for embedding requests
# Both LISA and LiteLLM run as Gunicorn + Uvicorn async workers doing I/O-bound
# HTTP proxying. Every request passes through both serially (LISA :8080 → LiteLLM :4000),
# so they should have the same worker count. A single WORKER_COUNT env var controls both.
# Async Uvicorn workers handle many concurrent connections each, so 2 is sufficient
# for redundancy without excessive memory/DB connection overhead.
WORKER_COUNT=${WORKER_COUNT:-2}
LITELLM_WORKERS=${LITELLM_WORKERS:-$WORKER_COUNT}
# Recycle workers after 10000 requests to mitigate gradual memory leaks under sustained load
LITELLM_MAX_REQUESTS=${LITELLM_MAX_REQUESTS:-10000}
echo "   - LiteLLM workers: $LITELLM_WORKERS"
echo "   - Worker recycle after: $LITELLM_MAX_REQUESTS requests"
litellm -c litellm_config.yaml --run_gunicorn --num_workers "$LITELLM_WORKERS" --max_requests_before_restart "$LITELLM_MAX_REQUESTS" $LITELLM_DETAILED_DEBUG_ARGS > litellm.log 2>&1 &
LITELLM_PID=$!

echo "   - LiteLLM PID: $LITELLM_PID"
echo "   - Log file: litellm.log"

# Tail the log file to stdout so Docker can capture it
tail -f litellm.log &
TAIL_PID=$!

echo "   - Log tail PID: $TAIL_PID"

# LiteLLM is starting in the background, proceed with Gunicorn startup

# Use same worker count as LiteLLM — both are async Uvicorn behind Gunicorn
THREADS=${THREADS:-$WORKER_COUNT}
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
