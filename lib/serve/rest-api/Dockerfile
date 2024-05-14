# Use an argument for the base image
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

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

# Make entrypoint.sh executable
RUN chmod +x src/entrypoint.sh

# Set the entrypoint script
ENTRYPOINT ["./src/entrypoint.sh"]
