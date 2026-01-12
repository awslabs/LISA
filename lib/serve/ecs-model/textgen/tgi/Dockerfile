ARG BASE_IMAGE=ghcr.io/huggingface/text-generation-inference:latest
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

##### DOWNLOAD MOUNTPOINTS S3
ARG MOUNTS3_DEB_URL
RUN apt update -y && apt install -y wget rsync && \
    wget ${MOUNTS3_DEB_URL} && \
    apt install -y ./mount-s3.deb && \
    rm mount-s3.deb

COPY src/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
