#!/bin/bash
set -e

# Host and port configuration
HOST="0.0.0.0"
PORT="8080"

# Update LiteLLM config that was already copied from config.yaml with runtime-deployed models.
# Depends on SSM Parameter for registered models.
echo "Configuring and starting LiteLLM"
python ./src/utils/generate_litellm_config.py -f litellm_config.yaml

# Start LiteLLM in the background, default port 4000, not exposed outside of container.
litellm -c litellm_config.yaml &

echo "Starting Gunicorn with $THREADS workers..."

# Start Gunicorn with Uvicorn workers.
exec gunicorn -k uvicorn.workers.UvicornWorker -w "$THREADS" -b "$HOST:$PORT" "src.main:app"
