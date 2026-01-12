ARG BASE_IMAGE=ghcr.io/huggingface/text-embeddings-inference:latest
FROM ${BASE_IMAGE}

# Apply SSH security hardening
COPY scripts/docker/harden-ssh.sh /tmp/harden-ssh.sh
RUN chmod +x /tmp/harden-ssh.sh && /tmp/harden-ssh.sh && rm /tmp/harden-ssh.sh

##### DOWNLOAD MOUNTPOINTS S3
ARG MOUNTS3_DEB_URL
ARG MOUNTS3_DEB_SHA256
RUN apt update -y && apt install -y wget rsync && \
    wget ${MOUNTS3_DEB_URL} -O mount-s3.deb && \
    if [ -n "${MOUNTS3_DEB_SHA256}" ]; then \
        echo "${MOUNTS3_DEB_SHA256}  mount-s3.deb" | sha256sum -c; \
    fi && \
    apt install -y ./mount-s3.deb && \
    rm mount-s3.deb

COPY src/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
