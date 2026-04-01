ARG BASE_IMAGE=ghcr.io/huggingface/text-embeddings-inference:latest
FROM ${BASE_IMAGE}

# Apply SSH security hardening - disable weak ciphers (3DES-CBC, etc.)
COPY ssh-hardening.sh /tmp/ssh-hardening.sh
RUN chmod +x /tmp/ssh-hardening.sh && /tmp/ssh-hardening.sh && rm /tmp/ssh-hardening.sh

##### DOWNLOAD MOUNTPOINTS S3
ARG MOUNTS3_DEB_URL
ARG MOUNTS3_DEB_SHA256
RUN apt-get update -y && apt-get upgrade -y && apt-get install -y wget rsync && \
    wget ${MOUNTS3_DEB_URL} -O mount-s3.deb && \
    if [ -n "${MOUNTS3_DEB_SHA256}" ]; then \
        echo "${MOUNTS3_DEB_SHA256}  mount-s3.deb" | sha256sum -c; \
    fi && \
    apt-get install -y ./mount-s3.deb && \
    rm mount-s3.deb && \
    rm -rf /var/lib/apt/lists/*

COPY src/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
