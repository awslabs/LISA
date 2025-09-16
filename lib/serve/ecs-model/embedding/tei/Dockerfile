ARG BASE_IMAGE=ghcr.io/huggingface/text-embeddings-inference:1.2.3@sha256:ad6a9a4f80be66604962893bf24d6820b952ce5b5a67bce31c4fbb47a317e25a
FROM ${BASE_IMAGE}

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
