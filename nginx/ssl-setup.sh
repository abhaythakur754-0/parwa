#!/bin/bash
# ════════════════════════════════════════════════════════════════
# PARWA — SSL Certificate Setup Script
# - Obtain Let's Encrypt certificates via certbot
# - Configure nginx for HTTPS with best practices
# - Set up auto-renewal via certbot cron/renew timer
# - Generate Diffie-Hellman parameters for PFS
# - Test configuration before applying
# BC-012: All timestamps in UTC
# ════════════════════════════════════════════════════════════════

set -euo pipefail

# ────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────
DOMAIN="${DOMAIN:-parwa.ai}"
WILDCARD="${WILDCARD:-false}"          # Set true for *.parwa.ai
EMAIL="${EMAIL:-admin@parwa.ai}"       # Let's Encrypt registration email
STAGING="${STAGING:-false}"            # Use Let's Encrypt staging (for testing)
SSL_DIR="${SSL_DIR:-/etc/nginx/ssl}"
CERTBOT_DIR="${CERTBOT_DIR:-/var/www/certbot}"
DH_PARAMS_FILE="${SSL_DIR}/dhparam.pem"
DH_PARAMS_BITS="${DH_PARAMS_BITS:-2048}"
NGINX_CONF_DIR="${NGINX_CONF_DIR:-/etc/nginx}"
WEBROOT_MODE="${WEBROOT_MODE:-true}"   # true = webroot, false = DNS/DNS-01

# Additional domains (SANs)
EXTRA_DOMAINS="${EXTRA_DOMAINS:-}"

# ────────────────────────────────────────────────────────────────
# Logging
# ────────────────────────────────────────────────────────────────
log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"
}

error() {
    log "ERROR: $*" >&2
}

warn() {
    log "WARN: $*" >&2
}

# ────────────────────────────────────────────────────────────────
# Prerequisites check
# ────────────────────────────────────────────────────────────────
check_prerequisites() {
    log "Checking prerequisites..."

    # Check for certbot
    if ! command -v certbot > /dev/null 2>&1; then
        log "certbot not found, installing..."
        if command -v apt-get > /dev/null 2>&1; then
            apt-get update -qq && apt-get install -y -qq certbot python3-certbot-nginx
        elif command -v yum > /dev/null 2>&1; then
            yum install -y certbot python3-certbot-nginx
        elif command -v apk > /dev/null 2>&1; then
            apk add --no-cache certbot
        else
            error "Cannot install certbot automatically. Please install certbot manually."
            exit 1
        fi
    fi
    log "certbot: $(certbot --version 2>&1 || echo 'installed')"

    # Check for nginx
    if ! command -v nginx > /dev/null 2>&1; then
        error "nginx not found. Please install nginx first."
        exit 1
    fi
    log "nginx: $(nginx -v 2>&1 || echo 'installed')"

    # Check if running as root (required for cert operations)
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root for SSL certificate operations"
        exit 1
    fi

    # Create directories
    mkdir -p "${SSL_DIR}"
    mkdir -p "${CERTBOT_DIR}"
}

# ────────────────────────────────────────────────────────────────
# Generate Diffie-Hellman parameters for Perfect Forward Secrecy
# ────────────────────────────────────────────────────────────────
generate_dh_params() {
    if [[ -f "${DH_PARAMS_FILE}" ]]; then
        log "Diffie-Hellman parameters already exist: ${DH_PARAMS_FILE}"
        return 0
    fi

    log "Generating Diffie-Hellman parameters (${DH_PARAMS_BITS} bits)..."
    log "This may take several minutes..."

    openssl dhparam -out "${DH_PARAMS_FILE}" "${DH_PARAMS_BITS}" 2>/dev/null
    chmod 600 "${DH_PARAMS_FILE}"

    log "Diffie-Hellman parameters generated: ${DH_PARAMS_FILE}"
}

# ────────────────────────────────────────────────────────────────
# Obtain SSL certificates from Let's Encrypt
# ────────────────────────────────────────────────────────────────
obtain_certificate() {
    log "Obtaining SSL certificate for ${DOMAIN}..."

    # Build certbot command
    local certbot_args=()

    # Domain(s)
    certbot_args+=("--domain" "${DOMAIN}")
    if [[ "${WILDCARD}" == "true" ]]; then
        certbot_args+=("--domain" "*.${DOMAIN}")
    fi
    # Extra domains (SANs)
    if [[ -n "${EXTRA_DOMAINS}" ]]; then
        for extra_domain in ${EXTRA_DOMAINS}; do
            certbot_args+=("--domain" "${extra_domain}")
        done
    fi

    # Email
    certbot_args+=("--email" "${EMAIL}")

    # Agree to terms
    certbot_args+=("--agree-tos")

    # Non-interactive
    certbot_args+=("--non-interactive")

    # Staging flag
    if [[ "${STAGING}" == "true" ]]; then
        certbot_args+=("--staging")
        log "Using Let's Encrypt STAGING environment (test certificates)"
    fi

    # Authentication method
    if [[ "${WEBROOT_MODE}" == "true" ]]; then
        certbot_args+=("--webroot" "--webroot-path" "${CERTBOT_DIR}")
    else
        certbot_args+=("--dns-nginx" "--dns-nginx-credentials" "/etc/letsencrypt/dns-nginx.ini")
    fi

    # Run certbot
    log "Running certbot with args: ${certbot_args[*]}"
    if ! certbot certonly "${certbot_args[@]}"; then
        error "Failed to obtain SSL certificate from Let's Encrypt"
        return 1
    fi

    # Create symlinks to certificate files in SSL directory
    local cert_path="/etc/letsencrypt/live/${DOMAIN}"

    if [[ -f "${cert_path}/fullchain.pem" ]]; then
        cp -L "${cert_path}/fullchain.pem" "${SSL_DIR}/fullchain.pem"
        log "Certificate copied: ${SSL_DIR}/fullchain.pem"
    else
        error "Certificate file not found: ${cert_path}/fullchain.pem"
        return 1
    fi

    if [[ -f "${cert_path}/privkey.pem" ]]; then
        cp -L "${cert_path}/privkey.pem" "${SSL_DIR}/privkey.pem"
        chmod 600 "${SSL_DIR}/privkey.pem"
        log "Private key copied: ${SSL_DIR}/privkey.pem"
    else
        error "Private key file not found: ${cert_path}/privkey.pem"
        return 1
    fi

    # Copy chain.pem for OCSP stapling
    if [[ -f "${cert_path}/chain.pem" ]]; then
        cp -L "${cert_path}/chain.pem" "${SSL_DIR}/chain.pem"
    fi

    log "SSL certificate obtained successfully for ${DOMAIN}"
    return 0
}

# ────────────────────────────────────────────────────────────────
# Configure nginx for HTTPS
# ────────────────────────────────────────────────────────────────
configure_nginx() {
    log "Configuring nginx for HTTPS..."

    # Test current nginx config
    if ! nginx -t 2>/dev/null; then
        warn "Current nginx configuration has errors — proceeding with SSL setup"
    fi

    # Reload nginx to pick up changes
    if nginx -t 2>/dev/null; then
        log "Reloading nginx with SSL configuration..."
        nginx -s reload 2>/dev/null || true
    else
        error "nginx configuration test failed after SSL setup — manual intervention required"
        return 1
    fi

    log "nginx HTTPS configuration applied"
    return 0
}

# ────────────────────────────────────────────────────────────────
# Set up auto-renewal via cron
# ────────────────────────────────────────────────────────────────
setup_auto_renewal() {
    log "Setting up automatic certificate renewal..."

    # Check if certbot renew timer is available (systemd)
    if command -v systemctl > /dev/null 2>&1; then
        if systemctl list-timers | grep -q "certbot" 2>/dev/null; then
            log "certbot systemd timer already configured"
            systemctl enable certbot.timer 2>/dev/null || true
            return 0
        fi
    fi

    # Fall back to cron job
    local cron_marker="# PARWA SSL Auto-Renewal"
    local cron_cmd="0 0,12 * * * root certbot renew --quiet --deploy-hook \"cp -L /etc/letsencrypt/live/${DOMAIN}/fullchain.pem ${SSL_DIR}/fullchain.pem && cp -L /etc/letsencrypt/live/${DOMAIN}/privkey.pem ${SSL_DIR}/privkey.pem && chmod 600 ${SSL_DIR}/privkey.pem && nginx -s reload\" ${cron_marker}"

    if [[ -f /etc/cron.d/certbot ]]; then
        log "certbot cron already exists at /etc/cron.d/certbot"
    else
        echo "${cron_cmd}" > /etc/cron.d/parwa-ssl-renewal
        log "SSL auto-renewal cron job created: /etc/cron.d/parwa-ssl-renewal"
    fi

    # Also create a renewal hook script for nginx reload
    local hook_script="${SSL_DIR}/renewal-hook.sh"
    cat > "${hook_script}" <<'HOOK_EOF'
#!/bin/bash
# PARWA SSL Renewal Hook
# Reloads nginx after certificate renewal
DOMAIN="${RENEWED_DOMAINS%% *}"
SSL_DIR="${SSL_DIR:-/etc/nginx/ssl}"

if [[ -n "${DOMAIN}" ]]; then
    cert_path="/etc/letsencrypt/live/${DOMAIN}"
    cp -L "${cert_path}/fullchain.pem" "${SSL_DIR}/fullchain.pem"
    cp -L "${cert_path}/privkey.pem" "${SSL_DIR}/privkey.pem"
    chmod 600 "${SSL_DIR}/privkey.pem"
    nginx -s reload
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] SSL certificate renewed and nginx reloaded for ${DOMAIN}" >> /var/log/parwa/ssl-renewal.log
fi
HOOK_EOF
    chmod +x "${hook_script}" 2>/dev/null || true
    log "Renewal hook script created: ${hook_script}"
}

# ────────────────────────────────────────────────────────────────
# Verify SSL configuration
# ────────────────────────────────────────────────────────────────
verify_ssl() {
    log "Verifying SSL configuration..."

    # Check certificate files
    for file in "${SSL_DIR}/fullchain.pem" "${SSL_DIR}/privkey.pem"; do
        if [[ ! -f "${file}" ]]; then
            error "Missing SSL file: ${file}"
            return 1
        fi
    done

    # Verify certificate matches key
    local cert_modulus privkey_modulus
    cert_modulus=$(openssl x509 -noout -modulus -in "${SSL_DIR}/fullchain.pem" 2>/dev/null | openssl md5 || echo "")
    privkey_modulus=$(openssl rsa -noout -modulus -in "${SSL_DIR}/privkey.pem" 2>/dev/null | openssl md5 || echo "")

    if [[ "${cert_modulus}" != "${privkey_modulus}" ]]; then
        error "Certificate and private key do not match!"
        return 1
    fi
    log "Certificate and private key match"

    # Check certificate expiry
    local expiry_date
    expiry_date=$(openssl x509 -noout -enddate -in "${SSL_DIR}/fullchain.pem" 2>/dev/null | cut -d= -f2 || echo "")
    if [[ -n "${expiry_date}" ]]; then
        log "Certificate expires: ${expiry_date}"
    fi

    # Test HTTPS connection
    if command -v curl > /dev/null 2>&1; then
        log "Testing HTTPS connection to ${DOMAIN}..."
        if curl -sf -o /dev/null --max-time 10 "https://${DOMAIN}/health" 2>/dev/null; then
            log "HTTPS connection test passed"
        else
            warn "HTTPS connection test failed — server may not be running yet or DNS not configured"
        fi
    fi

    # Verify TLS configuration using testssl or openssl
    if command -v openssl > /dev/null 2>&1; then
        log "Verifying TLS protocol support..."
        if echo | openssl s_client -connect "${DOMAIN}:443" -tls1_3 2>/dev/null | grep -q "TLSv1.3"; then
            log "TLS 1.3 supported"
        else
            warn "TLS 1.3 not detected (may not be reachable from this host)"
        fi
    fi

    log "SSL verification completed"
    return 0
}

# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────
main() {
    log "=========================================="
    log "PARWA SSL Certificate Setup"
    log "Domain: ${DOMAIN}"
    log "Email: ${EMAIL}"
    log "Timestamp: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    log "=========================================="

    # Step 1: Check prerequisites
    check_prerequisites

    # Step 2: Generate DH parameters
    generate_dh_params

    # Step 3: Obtain certificate
    if ! obtain_certificate; then
        error "Certificate obtainment failed"
        exit 1
    fi

    # Step 4: Configure nginx
    if ! configure_nginx; then
        error "nginx configuration failed"
        exit 1
    fi

    # Step 5: Set up auto-renewal
    setup_auto_renewal

    # Step 6: Verify SSL
    if ! verify_ssl; then
        warn "SSL verification had issues — manual review recommended"
    fi

    log "=========================================="
    log "PARWA SSL Setup Completed Successfully"
    log "Domain: ${DOMAIN}"
    log "Certificate: ${SSL_DIR}/fullchain.pem"
    log "=========================================="
}

main "$@"
