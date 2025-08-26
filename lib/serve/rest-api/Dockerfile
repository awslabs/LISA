ARG BASE_IMAGE
FROM ${BASE_IMAGE}

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

# Copy the source code into the container
COPY src/ ./src

COPY TIKTOKEN_CACHE ./TIKTOKEN_CACHE

# Generate Prisma client from LiteLLM's schema (find schema dynamically)
RUN python -c "import litellm.proxy; import os; schema_path = os.path.join(os.path.dirname(litellm.proxy.__file__), 'schema.prisma'); print(schema_path)" > schema_path.txt && \
    SCHEMA_PATH=$(cat schema_path.txt) && \
    echo "Using schema at: $SCHEMA_PATH" && \
    python -m prisma generate --schema "$SCHEMA_PATH"

# Copy LiteLLM config directly to container, it will be updated at runtime
# with LISA-hosted models. This filename is expected in the entrypoint.sh file, so do not modify
# the filename unless you modify it in the entrypoint.sh file too.
RUN echo "$LITELLM_CONFIG" > litellm_config.yaml

# Make entrypoint.sh executable
RUN chmod +x src/entrypoint.sh

# Set the entrypoint script
ENTRYPOINT ["./src/entrypoint.sh"]
