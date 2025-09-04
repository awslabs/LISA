FROM python:3.11@sha256:1d6131b5d479888b43200645e03a78443c7157efbdb730e6b48129740727c312

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
COPY src/requirements-hashes.txt* ./
RUN if [ -f "requirements-hashes.txt" ]; then \
        pip install --no-cache-dir --require-hashes -r requirements-hashes.txt; \
    else \
        pip install --no-cache-dir --upgrade -r requirements.txt; \
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
