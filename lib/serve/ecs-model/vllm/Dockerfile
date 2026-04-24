ARG BASE_IMAGE=public.ecr.aws/deep-learning-containers/vllm:0.17-gpu-py312-ec2
FROM ${BASE_IMAGE}

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

##### DOWNLOAD MOUNTPOINTS S3
ARG MOUNTS3_DEB_URL
ARG MOUNTS3_DEB_SHA256
RUN if command -v apt-get >/dev/null 2>&1; then \
        apt-get update -y && apt-get upgrade -y && apt-get install -y wget rsync && \
        wget ${MOUNTS3_DEB_URL} -O mount-s3.deb && \
        if [ -n "${MOUNTS3_DEB_SHA256}" ]; then \
            echo "${MOUNTS3_DEB_SHA256}  mount-s3.deb" | sha256sum -c; \
        fi && \
        apt-get install -y ./mount-s3.deb && \
        rm mount-s3.deb && rm -rf /var/lib/apt/lists/*; \
    elif command -v yum >/dev/null 2>&1; then \
        MOUNTS3_RPM_URL=$(echo ${MOUNTS3_DEB_URL} | sed 's/\.deb$/.rpm/') && \
        yum update -y && yum install -y wget rsync && \
        wget ${MOUNTS3_RPM_URL} -O mount-s3.rpm && \
        yum install -y ./mount-s3.rpm && yum clean all && rm mount-s3.rpm; \
    elif command -v apk >/dev/null 2>&1; then \
        apk add --no-cache wget rsync && wget ${MOUNTS3_DEB_URL} && \
        apk add --allow-untrusted ./mount-s3.apk && rm mount-s3.apk; \
    fi

##### OFFLINE MODE FOR LOCAL MODEL LOADING
# Prevents vLLM/HuggingFace Hub from attempting network calls when loading local models.
# Replaces the deprecated --repo-type CLI flag removed in newer vLLM versions.
ENV HF_HUB_OFFLINE=1

##### PRE-DOWNLOAD TIKTOKEN CACHE FOR OFFLINE/AIRGAPPED DEPLOYMENTS
# This fixes the "error downloading or loading vocab file" issue for OpenAI models
# Reference: https://huggingface.co/openai/gpt-oss-120b/discussions/39
ENV TIKTOKEN_CACHE_DIR=/root/.cache/tiktoken
ENV TIKTOKEN_RS_CACHE_DIR=$TIKTOKEN_CACHE_DIR

# Download all tiktoken encodings for offline use
RUN mkdir -p ${TIKTOKEN_CACHE_DIR} && \
    TIKTOKEN_CACHE_DIR=${TIKTOKEN_CACHE_DIR} python3 -c "\
import tiktoken; \
[tiktoken.get_encoding(enc) for enc in tiktoken.list_encoding_names()]" && \
    chmod -R 755 ${TIKTOKEN_CACHE_DIR}

# Metrics publisher for CloudWatch (scrapes Prometheus /metrics endpoint)
COPY metrics_publisher.py /opt/metrics_publisher.py

COPY vllm/src/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
