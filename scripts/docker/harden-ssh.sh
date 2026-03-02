#!/bin/sh
# LISA Security Hardening Script
# Disables weak SSH ciphers (3DES-CBC, etc.) to address security vulnerabilities
# This script is distribution-agnostic and works with any Linux base image

set -e

echo "Applying SSH security hardening..."

# Ensure /etc/ssh directory exists
mkdir -p /etc/ssh

# Define strong cipher suites (no 3DES-CBC, no weak algorithms)
STRONG_CIPHERS="aes128-ctr,aes192-ctr,aes256-ctr,aes128-gcm@openssh.com,aes256-gcm@openssh.com,chacha20-poly1305@openssh.com"
STRONG_MACS="hmac-sha2-256,hmac-sha2-512,hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com"
STRONG_KEX="curve25519-sha256,curve25519-sha256@libssh.org,ecdh-sha2-nistp256,ecdh-sha2-nistp384,ecdh-sha2-nistp521,diffie-hellman-group-exchange-sha256,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512"

# Configure SSH client
cat >> /etc/ssh/ssh_config <<EOF

# LISA Security Hardening - Disable weak ciphers
Host *
    Ciphers ${STRONG_CIPHERS}
    MACs ${STRONG_MACS}
    KexAlgorithms ${STRONG_KEX}
EOF

# Configure SSH server if config exists
if [ -f /etc/ssh/sshd_config ]; then
    cat >> /etc/ssh/sshd_config <<EOF

# LISA Security Hardening - Disable weak ciphers
Ciphers ${STRONG_CIPHERS}
MACs ${STRONG_MACS}
KexAlgorithms ${STRONG_KEX}
EOF
    echo "SSH server configuration hardened"
fi

echo "SSH security hardening complete"
