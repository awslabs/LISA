ARG BASE_IMAGE=public.ecr.aws/sam/build-python3.11
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
