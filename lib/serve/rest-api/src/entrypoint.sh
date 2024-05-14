#!/bin/bash
set -e

# Host and port configuration
HOST="0.0.0.0"
PORT="8080"

echo "Starting Gunicorn with $THREADS workers..."

# Start Gunicorn with Uvicorn workers.
exec gunicorn -k uvicorn.workers.UvicornWorker -w "$THREADS" -b "$HOST:$PORT" "src.main:app"
