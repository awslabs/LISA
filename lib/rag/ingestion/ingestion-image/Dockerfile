FROM public.ecr.aws/lambda/python:3.11

ARG BUILD_DIR=build

WORKDIR /workdir

COPY ./requirements.txt /workdir
RUN /var/lang/bin/pip install --no-cache-dir -r /workdir/requirements.txt -t .

COPY ./${BUILD_DIR} /workdir

ENTRYPOINT [ "/var/lang/bin/python" ]
