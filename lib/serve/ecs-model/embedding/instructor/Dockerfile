FROM python:3.11@sha256:1d6131b5d479888b43200645e03a78443c7157efbdb730e6b48129740727c312

#### POINT TO NEW PYPI CONFIG
ARG PYPI_INDEX_URL
ARG PYPI_TRUSTED_HOST
RUN if [ "$PYPI_INDEX_URL" != "" ]; then \
        pip config set global.index-url $PYPI_INDEX_URL && \
        pip config set global.trusted-host $PYPI_TRUSTED_HOST; fi

##### POINT TO DIFFERENT CONDA CONFIGS
ARG CONDA_URL
RUN if [ "$CONDA_URL" != "" ]; then \
        conda config --set channel_alias $CONDA_URL && \
        conda config --add channels defaults && \
        conda config --add default_channels arepo \
            --add default_channels anaconda-patched \
            --add default_channels anaconda \
            --add default_channels msys2-patched \
            --add default_channels msys2 && \
        conda install anaconda-client-config condarc ca-certificates certifi -k \
            -c $CONDA_URL/anaconda-patched \
            -c $CONDA_URL/arepo \
            -c $CONDA_URL/anaconda \
            --override-channels -y; fi

RUN /opt/conda/bin/conda install s5cmd && \
    /opt/conda/bin/conda clean -ya && \
    pip install -U --no-cache --upgrade torchserve torch-model-archiver torch-workflow-archiver

ARG LOCAL_CODE_PATH
WORKDIR ${LOCAL_CODE_PATH}

COPY src/inference.py src/requirements.txt ${LOCAL_CODE_PATH}/
COPY src/entrypoint.sh entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
