ARG BASE_IMAGE=python:3.13-slim
FROM ${BASE_IMAGE}

# Apply SSH security hardening - disable weak ciphers (3DES-CBC, etc.)
RUN mkdir -p /etc/ssh && \
    echo "" >> /etc/ssh/ssh_config && \
    echo "# LISA Security Hardening - Disable weak ciphers" >> /etc/ssh/ssh_config && \
    echo "Host *" >> /etc/ssh/ssh_config && \
    echo "    Ciphers aes128-ctr,aes192-ctr,aes256-ctr,aes128-gcm@openssh.com,aes256-gcm@openssh.com,chacha20-poly1305@openssh.com" >> /etc/ssh/ssh_config && \
    echo "    MACs hmac-sha2-256,hmac-sha2-512,hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com" >> /etc/ssh/ssh_config && \
    echo "    KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,ecdh-sha2-nistp256,ecdh-sha2-nistp384,ecdh-sha2-nistp521,diffie-hellman-group-exchange-sha256,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512" >> /etc/ssh/ssh_config && \
    if [ -f /etc/ssh/sshd_config ]; then \
        echo "" >> /etc/ssh/sshd_config && \
        echo "# LISA Security Hardening - Disable weak ciphers" >> /etc/ssh/sshd_config && \
        echo "Ciphers aes128-ctr,aes192-ctr,aes256-ctr,aes128-gcm@openssh.com,aes256-gcm@openssh.com,chacha20-poly1305@openssh.com" >> /etc/ssh/sshd_config && \
        echo "MACs hmac-sha2-256,hmac-sha2-512,hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com" >> /etc/ssh/sshd_config && \
        echo "KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,ecdh-sha2-nistp256,ecdh-sha2-nistp384,ecdh-sha2-nistp521,diffie-hellman-group-exchange-sha256,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512" >> /etc/ssh/sshd_config; \
    fi

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
    pip install --no-cache-dir --upgrade pip && \
    pip install -U --no-cache --upgrade torchserve torch-model-archiver torch-workflow-archiver

ARG LOCAL_CODE_PATH
WORKDIR ${LOCAL_CODE_PATH}

COPY src/inference.py src/requirements.txt ${LOCAL_CODE_PATH}/
COPY src/entrypoint.sh entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
