FROM python:3.12-slim

ARG RCLONE_VERSION=v1.71.0
ARG RCLONE_ARCH=amd64
ARG S6_OVERLAY_VERSION=3.1.6.2
ARG S6_OVERLAY_ARCH=x86_64

ENV S6_OVERLAY_NOARCH_SOURCE="https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz"
ENV S6_OVERLAY_ARCH_SOURCE="https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_OVERLAY_ARCH}.tar.xz"
ENV RCLONE_SOURCE="https://github.com/rclone/rclone/releases/download/${RCLONE_VERSION}/rclone-${RCLONE_VERSION}-linux-${RCLONE_ARCH}.zip"

WORKDIR /workspace

RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Install s6-overlay
ADD $S6_OVERLAY_NOARCH_SOURCE /tmp
ADD $S6_OVERLAY_ARCH_SOURCE /tmp
RUN tar -C / -Jxpf /tmp/$(basename $S6_OVERLAY_NOARCH_SOURCE) && \
    tar -C / -Jxpf /tmp/$(basename $S6_OVERLAY_ARCH_SOURCE) && \
    rm /tmp/s6-overlay-*.tar.xz

# Install rclone
ADD $RCLONE_SOURCE /tmp
RUN unzip -d /tmp /tmp/$(basename $RCLONE_SOURCE) && \
    install --owner root --group root --mode 755 /tmp/$(basename ${RCLONE_SOURCE%.*})/rclone /usr/bin/ && \
    rm -rf /tmp/rclone-*

# Copy and install the MCP workbench package
COPY . /workspace/mcpworkbench-src/
RUN pip install -e /workspace/mcpworkbench-src/

# Copy s6-overlay service definitions
COPY s6-overlay/s6-rc.d /etc/s6-overlay/s6-rc.d/
RUN chmod +x /etc/s6-overlay/s6-rc.d/mcpworkbench/run

# Create tools directory
RUN mkdir -p /workspace/tools

# Set default environment variables
ENV TOOLS_DIR=/workspace/tools
ENV HOST=0.0.0.0
ENV PORT=8000
ENV MCP_ROUTE=/mcp
ENV CORS_ORIGINS=*
ENV LOG_LEVEL=info

EXPOSE 8000

ENTRYPOINT ["/init"]
