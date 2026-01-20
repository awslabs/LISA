ARG BASE_IMAGE=python:3.13-slim
FROM ${BASE_IMAGE}

ARG RCLONE_VERSION=v1.71.0
ARG RCLONE_ARCH=amd64
ARG S6_OVERLAY_VERSION=3.1.6.2
ARG S6_OVERLAY_ARCH=x86_64

ARG S6_OVERLAY_NOARCH_SOURCE="https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz"
ENV S6_OVERLAY_NOARCH_SOURCE=$S6_OVERLAY_NOARCH_SOURCE
ARG S6_OVERLAY_ARCH_SOURCE="https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_OVERLAY_ARCH}.tar.xz"
ENV S6_OVERLAY_ARCH_SOURCE=$S6_OVERLAY_ARCH_SOURCE
ARG RCLONE_SOURCE="https://github.com/rclone/rclone/releases/download/${RCLONE_VERSION}/rclone-${RCLONE_VERSION}-linux-${RCLONE_ARCH}.zip"
ENV RCLONE_SOURCE=$RCLONE_SOURCE

WORKDIR /workspace

RUN apt-get update && apt-get install -y \
    curl \
    fuse3 \
    unzip \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for running the application
# Note: rclone FUSE mount still requires root, but mcpworkbench app runs as lisa
RUN groupadd -r lisa && useradd -r -g lisa -d /workspace -s /sbin/nologin lisa

# Configure FUSE to allow non-root users to access mounts created by root
RUN echo "user_allow_other" >> /etc/fuse.conf

# Install s6-overlay
ADD $S6_OVERLAY_NOARCH_SOURCE /tmp/
ADD $S6_OVERLAY_ARCH_SOURCE /tmp/
RUN if [ -f "/tmp/$(basename $S6_OVERLAY_NOARCH_SOURCE)" ]; then tar -C / -Jxpf "/tmp/$(basename $S6_OVERLAY_NOARCH_SOURCE)"; fi && \
    if [ -f "/tmp/$(basename $S6_OVERLAY_ARCH_SOURCE)" ]; then tar -C / -Jxpf "/tmp/$(basename $S6_OVERLAY_ARCH_SOURCE)"; fi && \
    (rm /tmp/s6-overlay-*.tar.xz || true)

# Install rclone
ADD $RCLONE_SOURCE /tmp
RUN unzip -d /tmp /tmp/$(basename $RCLONE_SOURCE) && \
    install --owner root --group root --mode 755 /tmp/$(basename ${RCLONE_SOURCE%.*})/rclone /usr/bin/ && \
    rm -rf /tmp/rclone-*

# Copy and install the MCP workbench package
COPY . /workspace/mcpworkbench-src/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e /workspace/mcpworkbench-src/

# Install additional requirements
COPY requirements.txt /workspace/
RUN pip install --no-cache-dir -r /workspace/requirements.txt

# Copy s6-overlay service definitions
COPY s6-overlay/services.d /etc/services.d
RUN chmod +x /etc/services.d/mcpworkbench/run
# RUN ln -s ../supervise/notify /etc/services.d/s3mount/notification-fd

# Create tools directory
RUN mkdir -p /workspace/tools

# Set ownership of workspace to non-root user
RUN chown -R lisa:lisa /workspace

# Set default environment variables
ENV TOOLS_DIR=/workspace/tools
ENV HOST=0.0.0.0
ENV PORT=8000
ENV MCP_ROUTE=/v2/mcp
ENV CORS_ORIGINS=*
ENV LOG_LEVEL=info

EXPOSE 8000

# Note: s6-overlay init must run as root to manage services,
# but individual services drop privileges appropriately:
# - rclone mount runs as root (required for FUSE)
# - mcpworkbench app runs as lisa (non-root)
ENTRYPOINT ["/init"]
