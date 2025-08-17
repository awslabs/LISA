#### DOWNLOAD NLTK ARTIFACTS
ARG ALPINE_IMAGE

FROM ${ALPINE_IMAGE} as downloader
ARG PYPI_INDEX_URL
RUN apk --update add --no-cache wget unzip
WORKDIR /downloads
RUN if [ "$PYPI_INDEX_URL" != "" ]; then \
    wget -k https://github.com/nltk/nltk_data/raw/gh-pages/packages/taggers/averaged_perceptron_tagger_eng.zip && \
    mkdir -p nltk_data/taggers && \
    unzip averaged_perceptron_tagger_eng.zip -d nltk_data/taggers && \
    rm -f averaged_perceptron_tagger_eng.zip && \
    wget -k https://github.com/nltk/nltk_data/raw/gh-pages/packages/tokenizers/punkt_tab.zip && \
    mkdir -p nltk_data/tokenizers && \
    unzip punkt_tab.zip -d nltk_data/tokenizers && \
    rm -f punkt_tab.zip; \
    fi

FROM public.ecr.aws/lambda/python:3.11

ARG BUILD_DIR=build

#### POINT TO NEW PYPI CONFIG
ARG PYPI_INDEX_URL
ARG PYPI_TRUSTED_HOST
RUN if [ "$PYPI_INDEX_URL" != "" ]; then \
        pip config set global.index-url $PYPI_INDEX_URL && \
        pip config set global.trusted-host $PYPI_TRUSTED_HOST; \
    fi

WORKDIR /workdir

COPY ./requirements.txt /workdir
RUN /var/lang/bin/pip install --no-cache-dir -r /workdir/requirements.txt -t .

ENV NLTK_DATA=${LAMBDA_TASK_ROOT}/nltk_data
RUN if [ "$PYPI_INDEX_URL" == "" ]; then \
        PYTHONPATH=/asset-output /var/lang/bin/python -m nltk.downloader -d $NLTK_DATA punkt_tab averaged_perceptron_tagger_eng; \
    fi
COPY --from=downloader /downloads/nltk_data* ${NLTK_DATA}

COPY ./${BUILD_DIR} /workdir

ENTRYPOINT [ "/var/lang/bin/python" ]
