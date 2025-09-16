ARG BASE_IMAGE=ghcr.io/huggingface/text-generation-inference:2.0.1@sha256:cabd2a49a3afa7106aaa0bb3458c11904007fcd0369a83fcc1fa2fab76d444b4
FROM ${BASE_IMAGE}

##### DOWNLOAD MOUNTPOINTS S3
ARG MOUNTS3_DEB_URL
RUN apt update -y && apt install -y wget rsync && \
    wget ${MOUNTS3_DEB_URL} && \
    apt install -y ./mount-s3.deb && \
    rm mount-s3.deb

COPY src/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
