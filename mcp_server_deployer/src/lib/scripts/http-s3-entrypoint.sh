#!/bin/bash
set -e

# Install AWS CLI if not present
if ! command -v aws >/dev/null 2>&1; then
    apt-get update && apt-get install -y --no-install-recommends awscli && apt-get clean && rm -rf /var/lib/apt/lists/*
fi

# Create working directory
mkdir -p /app/server

# Download from S3
if [ -n "$S3_BUCKET" ] && [ -n "$S3_PATH" ]; then
    echo "Downloading server files from s3://$S3_BUCKET/$S3_PATH..."
    aws s3 sync "s3://$S3_BUCKET/$S3_PATH" /app/server/
    chmod +x /app/server/* 2>/dev/null || true
    export PATH="/app/server:$PATH"
fi

# Change to server directory if files were downloaded, otherwise stay in /app
if [ -d /app/server ] && [ "$(ls -A /app/server)" ]; then
    cd /app/server
else
    cd /app
fi

# Execute the start command (wrap in sh -c to handle shell operators like &&)
exec sh -c "$START_COMMAND"
