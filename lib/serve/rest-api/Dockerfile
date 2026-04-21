ARG BASE_IMAGE=public.ecr.aws/docker/library/python:3.13-slim
FROM ${BASE_IMAGE}

ARG PRISMA_CACHE_DIR=PRISMA_CACHE
ENV PRISMA_CACHE_DIR=$PRISMA_CACHE_DIR

# Install build dependencies for madoka package and Node.js for prisma-client-py.
# prisma-client-py requires a Node.js runtime to execute the Prisma CLI. Without a global
# node binary, it falls back to nodeenv which downloads Node.js from the internet — breaking
# airgapped builds. Installing nodejs here ensures prisma works offline.
RUN if command -v apt-get >/dev/null 2>&1; then \
        apt-get update -y && apt-get upgrade -y && apt-get install -y gcc g++ make procps nodejs libatomic1 && rm -rf /var/lib/apt/lists/*; \
    elif command -v yum >/dev/null 2>&1; then \
        yum install -y gcc gcc-c++ make procps-ng nodejs libatomic && yum clean all; \
    elif command -v apk >/dev/null 2>&1; then \
        apk add --no-cache gcc g++ make musl-dev procps nodejs libatomic; \
    fi

# Apply SSH security hardening - disable weak ciphers (3DES-CBC, etc.)
# This runs AFTER apt-get upgrade to avoid conffile conflicts with openssh-client upgrades.
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

# Generate Prisma Python client at build time following LiteLLM's approach:
# 1. Copy LiteLLM's schema.prisma to the working directory
# 2. If PRISMA_CACHE has pre-downloaded engine binaries (for offline/airgap builds),
#    set env vars to point directly at the binaries — this bypasses platform detection
#    and prevents any download attempts from binaries.prisma.sh
# 3. Run prisma generate — this produces the Python client code
# This ensures prisma generate NEVER runs at runtime.
RUN SCHEMA_PATH=$(python3 -c "import litellm, os; print(os.path.join(os.path.dirname(litellm.__file__), 'proxy', 'schema.prisma'))") && \
    echo "LiteLLM schema: ${SCHEMA_PATH}" && \
    cp "${SCHEMA_PATH}" /app/schema.prisma && \
    mkdir -p /root/.cache && \
    if [ -d "/tmp/prisma-cache" ] && [ -n "$(ls -A /tmp/prisma-cache 2>/dev/null | grep -v '^\.gitkeep$')" ]; then \
        echo "Using pre-cached Prisma binaries from host" && \
        cp -r /tmp/prisma-cache/* /root/.cache/ && \
        rm -rf /tmp/prisma-cache && \
        QE=$(find /root/.cache -name 'query-engine-*' -not -name '*.sha256' -type f | head -1) && \
        SE=$(find /root/.cache -name 'schema-engine-*' -not -name '*.sha256' -type f | head -1) && \
        LQE=$(find /root/.cache -name 'libquery_engine-*' -o -name 'libquery-engine' -type f | head -1) && \
        echo "  Query engine: ${QE}" && \
        echo "  Schema engine: ${SE}" && \
        echo "  Lib query engine: ${LQE}" && \
        export PRISMA_QUERY_ENGINE_BINARY="${QE}" && \
        export PRISMA_SCHEMA_ENGINE_BINARY="${SE}" && \
        export PRISMA_QUERY_ENGINE_LIBRARY="${LQE}" && \
        export PRISMA_ENGINES_CHECKSUM_IGNORE_MISSING=1; \
    fi && \
    prisma generate --schema /app/schema.prisma && \
    echo "Prisma client generated successfully" && \
    python3 -c "from prisma import Prisma; print('Prisma client import verified')"

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
