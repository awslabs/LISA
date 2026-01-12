ARG BASE_IMAGE=public.ecr.aws/lambda/python:3.13
FROM ${BASE_IMAGE}

# Apply SSH security hardening
COPY scripts/docker/harden-ssh.sh /tmp/harden-ssh.sh
RUN chmod +x /tmp/harden-ssh.sh && /tmp/harden-ssh.sh && rm /tmp/harden-ssh.sh

ARG BUILD_DIR=build

WORKDIR /workdir

COPY ./requirements.txt /workdir
RUN /var/lang/bin/pip install --no-cache-dir --upgrade pip && \
    /var/lang/bin/pip install --no-cache-dir -r /workdir/requirements.txt -t .

COPY ./${BUILD_DIR} /workdir

ENTRYPOINT [ "/var/lang/bin/python" ]
