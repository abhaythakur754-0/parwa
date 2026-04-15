#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════
# PARWA — Generate Self-Signed SSL Certificates for PostgreSQL
# ════════════════════════════════════════════════════════════════
#
# E1: This script generates self-signed certificates that enable
#     TLS encryption between PostgreSQL and application containers.
#
# Usage:
#   chmod +x generate-ssl-certs.sh
#   ./generate-ssl-certs.sh /var/lib/postgresql
#
# The output files are:
#   <DIR>/ca.crt          — CA certificate
#   <DIR>/server.crt      — Server certificate (signed by CA)
#   <DIR>/server.key      — Server private key (chmod 600)
#
# Place this script in docker-entrypoint-initdb.d/ or run it
# before starting PostgreSQL for the first time.
# ════════════════════════════════════════════════════════════════
set -euo pipefail

CERT_DIR="${1:-/var/lib/postgresql}"
DAYS="${SSL_CERT_DAYS:-3650}"  # Default: 10 years
COMMON_NAME="${SSL_CERT_CN:-parwa-postgres}"

echo "[PARWA SSL] Generating self-signed certificates in ${CERT_DIR}..."

# ── 1. Generate CA key + certificate ─────────────────────────
openssl req -new -x509 -nodes \
    -days "${DAYS}" \
    -newkey rsa:4096 \
    -keyout "${CERT_DIR}/ca.key" \
    -out "${CERT_DIR}/ca.crt" \
    -subj "/CN=${COMMON_NAME}-CA/O=PARWA" \
    2>/dev/null

# ── 2. Generate server private key ────────────────────────────
openssl genrsa -out "${CERT_DIR}/server.key" 4096 2>/dev/null

# ── 3. Generate CSR (Certificate Signing Request) ─────────────
openssl req -new -key "${CERT_DIR}/server.key" \
    -out "${CERT_DIR}/server.csr" \
    -subj "/CN=${COMMON_NAME}/O=PARWA" \
    2>/dev/null

# ── 4. Sign server cert with CA ──────────────────────────────
#      Include SAN extensions so both hostname and IP work.
cat > "${CERT_DIR}/server.ext" <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=@alt_names

[alt_names]
DNS.1=${COMMON_NAME}
DNS.2=localhost
DNS.3=db
IP.1=127.0.0.1
EOF

openssl x509 -req -in "${CERT_DIR}/server.csr" \
    -CA "${CERT_DIR}/ca.crt" \
    -CAkey "${CERT_DIR}/ca.key" \
    -CAcreateserial \
    -out "${CERT_DIR}/server.crt" \
    -days "${DAYS}" \
    -sha256 \
    -extfile "${CERT_DIR}/server.ext" \
    2>/dev/null

# ── 5. Set restrictive permissions ───────────────────────────
chmod 600 "${CERT_DIR}/server.key"
chmod 644 "${CERT_DIR}/server.crt"
chmod 644 "${CERT_DIR}/ca.crt"

# ── 6. Clean up intermediate files ───────────────────────────
rm -f "${CERT_DIR}/server.csr" "${CERT_DIR}/server.ext" "${CERT_DIR}/ca.srl"

echo "[PARWA SSL] Done. Files created:"
echo "  ${CERT_DIR}/ca.crt     (CA certificate)"
echo "  ${CERT_DIR}/server.crt (server certificate)"
echo "  ${CERT_DIR}/server.key (server private key, mode 600)"
echo "[PARWA SSL] PostgreSQL SSL is ready (ssl = on)."
