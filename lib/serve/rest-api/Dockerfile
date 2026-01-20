ARG BASE_IMAGE=python:3.13-slim
FROM ${BASE_IMAGE}

ARG PRISMA_CACHE_DIR=PRISMA_CACHE
ENV PRISMA_CACHE_DIR=$PRISMA_CACHE_DIR

# Install build dependencies for madoka package
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for running the application
RUN groupadd -r lisa && useradd -r -g lisa -d /app -s /sbin/nologin lisa

# Copy LiteLLM config directly out of the LISA config.yaml file
ARG LITELLM_CONFIG

#### POINT TO NEW PYPI CONFIG
ARG PYPI_INDEX_URL
ARG PYPI_TRUSTED_HOST
RUN if [ "$PYPI_INDEX_URL" != "" ]; then \
        pip config set global.index-url $PYPI_INDEX_URL && \
        pip config set global.trusted-host $PYPI_TRUSTED_HOST;fi

# Set working directory in the container
WORKDIR /app

# Install dependencies
COPY src/requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy prisma cache directory (always exists, may be empty or populated)
COPY ${PRISMA_CACHE_DIR} /tmp/prisma-cache/

# Pre-cache prisma for prisma-client-py
# If the copied directory has content, use it (for offline environments)
# Otherwise, download it during build (requires internet)
# Note: Prisma cache is set up in /app/.cache for the non-root user
RUN mkdir -p /app/.cache && \
    if [ -d "/tmp/prisma-cache" ] && [ -n "$(ls /tmp/prisma-cache 2>/dev/null)" ]; then \
        echo "Using pre-cached Prisma dependencies from host" && \
        cp -r /tmp/prisma-cache/prisma* /app/.cache && \
        rm -rf /tmp/prisma-cache; \
    else \
        echo "Fetching Prisma Dependencies (requires internet)" && \
        HOME=/app prisma version; \
    fi

# Set Prisma home to use the non-root user's cache directory
ENV PRISMA_HOME=/app/.cache

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

# Set ownership of application files to non-root user
RUN chown -R lisa:lisa /app

# Switch to non-root user
USER lisa

# Set the entrypoint script
ENTRYPOINT ["./src/entrypoint.sh"]
