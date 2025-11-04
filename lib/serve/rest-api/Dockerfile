ARG BASE_IMAGE=python:3.11
FROM ${BASE_IMAGE}

# Install build dependencies for madoka package
RUN apt-get update && apt-get install -y \
gcc \
g++ \
make \
&& rm -rf /var/lib/apt/lists/*

# Copy LiteLLM config directly out of the LISA config.yaml file
ARG LITELLM_CONFIG

#### POINT TO NEW PYPI CONFIG
ARG PYPI_INDEX_URL
ARG PYPI_TRUSTED_HOST
ARG NODEENV_CACHE_DIR=NODEENV_CACHE
RUN if [ "$PYPI_INDEX_URL" != "" ]; then \
pip config set global.index-url $PYPI_INDEX_URL && \
pip config set global.trusted-host $PYPI_TRUSTED_HOST;fi

# Set working directory in the container
WORKDIR /app

# Install dependencies
COPY src/requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy nodeenv cache directory (always exists, may be empty or populated)
COPY ${NODEENV_CACHE_DIR} /tmp/nodeenv-cache/

# Pre-cache nodeenv for prisma-client-py
# If the copied directory has content, use it (for offline environments)
# Otherwise, download it during build (requires internet)
RUN mkdir -p /root/.cache/prisma-python && \
    if [ -d "/tmp/nodeenv-cache" ] && [ -n "$(ls /tmp/nodeenv-cache 2>/dev/null)" ]; then \
        echo "Using pre-cached nodeenv from host" && \
        cp -r /tmp/nodeenv-cache /root/.cache/prisma-python/nodeenv && \
        rm -rf /tmp/nodeenv-cache; \
    else \
        echo "Downloading nodeenv (requires internet)" && \
        python -m nodeenv /root/.cache/prisma-python/nodeenv; \
    fi

# Copy the source code into the container
COPY src/ ./src

COPY TIKTOKEN_CACHE ./TIKTOKEN_CACHE

# LiteLLM will handle Prisma setup at runtime with --use_prisma_db_push flag

# Copy LiteLLM config directly to container, it will be updated at runtime
# with LISA-hosted models. This filename is expected in the entrypoint.sh file, so do not modify
# the filename unless you modify it in the entrypoint.sh file too.
RUN echo "$LITELLM_CONFIG" > litellm_config.yaml

# Make entrypoint.sh executable
RUN chmod +x src/entrypoint.sh

# Set the entrypoint script
ENTRYPOINT ["./src/entrypoint.sh"]
