ARG BASE_IMAGE
FROM ${BASE_IMAGE}

##### POINT TO DIFFERENT PYPI CONFIGS
ARG PYPI_INDEX_URL
ARG PYPI_TRUSTED_HOST

RUN if [ "$PYPI_INDEX_URL" != "" ]; then \
       pip config set global.index-url $PYPI_INDEX_URL && \
       pip config set global.trusted-host $PYPI_TRUSTED_HOST;fi

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
            --override-channels -y;fi

##### DOWNLOAD MOUNTPOINTS S3
ARG MOUNTS3_DEB_URL
RUN if [ "$MOUNTS3_DEB_URL" != "" ]; then \
        apt update -y && apt install -y wget rsync && \
        wget ${MOUNTS3_DEB_URL} && \
        apt install -y ./mount-s3.deb && \
        rm mount-s3.deb; \
    else \
        mamba install -c conda-forge s5cmd -y; \
    fi

COPY src/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
