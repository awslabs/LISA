ARG BASE_IMAGE=public.ecr.aws/deep-learning-containers/vllm:0.15-gpu-py312-ec2
FROM ${BASE_IMAGE}

# Apply SSH security hardening - disable weak ciphers (3DES-CBC, etc.)
COPY ssh-hardening.sh /tmp/ssh-hardening.sh
RUN chmod +x /tmp/ssh-hardening.sh && /tmp/ssh-hardening.sh && rm /tmp/ssh-hardening.sh

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

COPY src/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
