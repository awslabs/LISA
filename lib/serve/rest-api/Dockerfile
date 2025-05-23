FROM public.ecr.aws/sam/build-python3.11:latest

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

# Copy LiteLLM config directly to container, it will be updated at runtime
# with LISA-hosted models. This filename is expected in the entrypoint.sh file, so do not modify
# the filename unless you modify it in the entrypoint.sh file too.
RUN echo "$LITELLM_CONFIG" > litellm_config.yaml

# Copy the source code into the container
COPY src/ ./src

# Generate the prisma binary
RUN prisma generate

# Make entrypoint.sh executable
RUN chmod +x src/entrypoint.sh

# Set the entrypoint script
ENTRYPOINT ["./src/entrypoint.sh"]
