#!/bin/bash
set -e

# Host and port configuration
HOST="0.0.0.0"
PORT="8080"

# Generate Prisma client at runtime to ensure it's available
echo "Generating Prisma client..."
cd src && prisma generate

# Update LiteLLM config that was already copied from config.yaml with runtime-deployed models.
# Depends on SSM Parameter for registered models.
echo "Configuring and starting LiteLLM"
# litellm_config.yaml is generated from the REST API Dockerfile from the LISA config.yaml.
# Do not modify the litellm_config.yaml name unless you change it in the Dockerfile and in the `litellm` command below.
python ./src/utils/generate_litellm_config.py -f litellm_config.yaml

# Start LiteLLM in the background, default port 4000, not exposed outside of container.
# If you need to change the port, you can specify the --port option, and then the port needs to be updated in
# src/api/endpoints/v2/litellm_passthrough.py for the LiteLLM URI
litellm -c litellm_config.yaml &

echo "Starting Gunicorn with $THREADS workers..."

# Start Gunicorn with Uvicorn workers.
exec gunicorn -k uvicorn.workers.UvicornWorker -t 600 -w "$THREADS" -b "$HOST:$PORT" "src.main:app"
