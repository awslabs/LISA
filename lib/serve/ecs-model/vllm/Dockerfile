ARG BASE_IMAGE=python:3.13-slim
FROM ${BASE_IMAGE}

# Apply SSH security hardening
COPY scripts/docker/harden-ssh.sh /tmp/harden-ssh.sh
RUN chmod +x /tmp/harden-ssh.sh && /tmp/harden-ssh.sh && rm /tmp/harden-ssh.sh

##### DOWNLOAD MOUNTPOINTS S3
ARG MOUNTS3_DEB_URL
ARG MOUNTS3_DEB_SHA256
RUN if command -v apt-get >/dev/null 2>&1; then \
        apt update -y && apt install -y wget rsync && \
        wget ${MOUNTS3_DEB_URL} && apt install -y ./mount-s3.deb && \
        rm mount-s3.deb && rm -rf /var/lib/apt/lists/*; \
    elif command -v yum >/dev/null 2>&1; then \
        yum install -y wget rsync && wget ${MOUNTS3_DEB_URL} && \
        yum install -y ./mount-s3.rpm && yum clean all && rm mount-s3.rpm; \
    elif command -v apk >/dev/null 2>&1; then \
        apk add --no-cache wget rsync && wget ${MOUNTS3_DEB_URL} && \
        apk add --allow-untrusted ./mount-s3.apk && rm mount-s3.apk; \
    fi

COPY src/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
