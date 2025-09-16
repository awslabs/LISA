ARG BASE_IMAGE=python:3.11@sha256:1d6131b5d479888b43200645e03a78443c7157efbdb730e6b48129740727c312
FROM ${BASE_IMAGE}

##### DOWNLOAD MOUNTPOINTS S3
ARG MOUNTS3_DEB_URL
ARG MOUNTS3_DEB_SHA256
RUN apt update -y && apt install -y wget rsync && \
    wget ${MOUNTS3_DEB_URL} && \
    apt install -y ./mount-s3.deb && \
    rm mount-s3.deb

COPY src/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
