ARG BASE_IMAGE=public.ecr.aws/docker/library/python:3.13-slim
FROM ${BASE_IMAGE}

ARG PRISMA_CACHE_DIR=PRISMA_CACHE
ENV PRISMA_CACHE_DIR=$PRISMA_CACHE_DIR

# Apply SSH security hardening - disable weak ciphers (3DES-CBC, etc.)
RUN mkdir -p /etc/ssh && \
    echo "" >> /etc/ssh/ssh_config && \
    echo "# LISA Security Hardening - Disable weak ciphers" >> /etc/ssh/ssh_config && \
    echo "Host *" >> /etc/ssh/ssh_config && \
    echo "    Ciphers aes128-ctr,aes192-ctr,aes256-ctr,aes128-gcm@openssh.com,aes256-gcm@openssh.com,chacha20-poly1305@openssh.com" >> /etc/ssh/ssh_config && \
    echo "    MACs hmac-sha2-256,hmac-sha2-512,hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com" >> /etc/ssh/ssh_config && \
    echo "    KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,ecdh-sha2-nistp256,ecdh-sha2-nistp384,ecdh-sha2-nistp521,diffie-hellman-group-exchange-sha256,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512" >> /etc/ssh/ssh_config && \
    if [ -f /etc/ssh/sshd_config ]; then \
        echo "" >> /etc/ssh/sshd_config && \
        echo "# LISA Security Hardening - Disable weak ciphers" >> /etc/ssh/sshd_config && \
        echo "Ciphers aes128-ctr,aes192-ctr,aes256-ctr,aes128-gcm@openssh.com,aes256-gcm@openssh.com,chacha20-poly1305@openssh.com" >> /etc/ssh/sshd_config && \
        echo "MACs hmac-sha2-256,hmac-sha2-512,hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com" >> /etc/ssh/sshd_config && \
        echo "KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,ecdh-sha2-nistp256,ecdh-sha2-nistp384,ecdh-sha2-nistp521,diffie-hellman-group-exchange-sha256,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512" >> /etc/ssh/sshd_config; \
    fi

# Install build dependencies for madoka package
RUN if command -v apt-get >/dev/null 2>&1; then \
        apt-get update && apt-get install -y gcc g++ make procps && rm -rf /var/lib/apt/lists/*; \
    elif command -v yum >/dev/null 2>&1; then \
        yum install -y gcc gcc-c++ make procps-ng && yum clean all; \
    elif command -v apk >/dev/null 2>&1; then \
        apk add --no-cache gcc g++ make musl-dev procps; \
    fi

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
