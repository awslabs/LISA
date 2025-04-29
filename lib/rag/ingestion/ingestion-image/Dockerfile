FROM public.ecr.aws/lambda/python:3.11

WORKDIR /workdir

COPY ./requirements.txt /workdir
RUN /var/lang/bin/pip install --no-cache-dir -r /workdir/requirements.txt -t .

COPY ./build /workdir

ENTRYPOINT [ "/var/lang/bin/python" ]
