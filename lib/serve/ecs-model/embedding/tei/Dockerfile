ARG BASE_IMAGE=ghcr.io/huggingface/text-embeddings-inference:latest
FROM ${BASE_IMAGE}

# Apply SSH security hardening - disable weak ciphers (3DES-CBC, etc.)
COPY ssh-hardening.sh /tmp/ssh-hardening.sh
RUN chmod +x /tmp/ssh-hardening.sh && /tmp/ssh-hardening.sh && rm /tmp/ssh-hardening.sh

##### Download S3 mountpoints and boto3
ARG MOUNTS3_DEB_URL
ARG MOUNTS3_DEB_SHA256
RUN apt-get update -y && apt-get upgrade -y && \
    apt-get install -y wget rsync python3 python3-pip && \
    wget ${MOUNTS3_DEB_URL} -O mount-s3.deb && \
    if [ -n "${MOUNTS3_DEB_SHA256}" ]; then \
        echo "${MOUNTS3_DEB_SHA256}  mount-s3.deb" | sha256sum -c; \
    fi && \
    apt-get install -y ./mount-s3.deb && \
    pip3 install --no-cache-dir --break-system-packages boto3 && \
    rm mount-s3.deb && \
    rm -rf /var/lib/apt/lists/*

# Metrics publisher for CloudWatch (scrapes Prometheus /metrics endpoint)
COPY metrics_publisher.py /opt/metrics_publisher.py

COPY embedding/tei/src/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
