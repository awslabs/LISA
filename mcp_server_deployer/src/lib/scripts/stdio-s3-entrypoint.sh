#!/bin/bash
set -e

# Install dependencies if not already present
if ! command -v aws >/dev/null 2>&1; then
    apt-get update && apt-get install -y --no-install-recommends awscli && apt-get clean && rm -rf /var/lib/apt/lists/*
fi

# Install mcp-proxy if not present
if ! command -v mcp-proxy >/dev/null 2>&1 && [ ! -f /root/.local/bin/mcp-proxy ]; then
    if ! command -v curl >/dev/null 2>&1; then
        apt-get update && apt-get install -y --no-install-recommends curl && apt-get clean && rm -rf /var/lib/apt/lists/*
    fi
    if ! command -v nodejs >/dev/null 2>&1; then
        apt-get update && apt-get install -y --no-install-recommends nodejs npm && apt-get clean && rm -rf /var/lib/apt/lists/*
    fi
    curl -LsSf https://astral.sh/uv/install.sh | sh || true
    export PATH="/root/.local/bin:$PATH"
    /root/.local/bin/uv tool install mcp-proxy || true
fi

# Create working directory
mkdir -p /app/server

# Download from S3
if [ -n "$S3_BUCKET" ] && [ -n "$S3_PATH" ]; then
    echo "Downloading server files from s3://$S3_BUCKET/$S3_PATH..."
    aws s3 sync "s3://$S3_BUCKET/$S3_PATH" /app/server/
    chmod +x /app/server/* 2>/dev/null || true
fi

# Change to server directory if files were downloaded
if [ -d /app/server ] && [ "$(ls -A /app/server)" ]; then
    cd /app/server
fi

# Execute with mcp-proxy
export PATH="/root/.local/bin:$PATH"
if [ -f /root/.local/bin/mcp-proxy ]; then
    eval exec /root/.local/bin/mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_COMMAND"
elif [ -f /root/.cargo/bin/mcp-proxy ]; then
    eval exec /root/.cargo/bin/mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_COMMAND"
elif command -v mcp-proxy >/dev/null 2>&1; then
    eval exec mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_COMMAND"
else
    echo "ERROR: mcp-proxy not found. Attempting to install..."
    curl -LsSf https://astral.sh/uv/install.sh | sh && /root/.local/bin/uv tool install mcp-proxy && eval exec /root/.local/bin/mcp-proxy --stateless --transport streamablehttp --port=8080 --host=0.0.0.0 --allow-origin="*" "$START_COMMAND"
fi
