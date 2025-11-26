#!/bin/bash
set -e

# Download from S3 if configured (safe to include - will be no-op if env vars not set)
if [ -n "$S3_BUCKET" ] && [ -n "$S3_PATH" ]; then
    echo "Downloading server files from s3://$S3_BUCKET/$S3_PATH..."
    aws s3 sync "s3://$S3_BUCKET/$S3_PATH" /app/server/
    chmod +x /app/server/* 2>/dev/null || true
fi
if [ -d /app/server ] && [ "$(ls -A /app/server)" ]; then
    cd /app/server
fi

# Execute with mcp-proxy
if [ -f /root/.local/bin/mcp-proxy ]; then
    eval exec /root/.local/bin/mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_COMMAND"
elif [ -f /root/.cargo/bin/mcp-proxy ]; then
    eval exec /root/.cargo/bin/mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_COMMAND"
elif command -v mcp-proxy >/dev/null 2>&1; then
    eval exec mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_COMMAND"
else
    echo "ERROR: mcp-proxy not found. Please ensure mcp-proxy is installed in your Docker image."
    exit 1
fi
