#!/bin/bash
# ════════════════════════════════════════════════════════════════
# PARWA — Backup Cron Wrapper
# Runs backup.sh with retry logic and persistent failure notification.
# Designed to be called from cron every 6 hours (configurable).
# BC-012: All timestamps in UTC
# ════════════════════════════════════════════════════════════════

set -euo pipefail

# ────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup.sh"
MAX_RETRIES=${BACKUP_MAX_RETRIES:-1}     # Number of retries (1 = retry once)
RETRY_DELAY=${BACKUP_RETRY_DELAY:-60}    # Seconds between retries
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"
LOCK_FILE="/tmp/parwa_backup_cron.lock"
LOG_FILE="${LOG_FILE:-/var/log/parwa/backup_cron.log}"

# ────────────────────────────────────────────────────────────────
# Logging
# ────────────────────────────────────────────────────────────────
log() {
    local msg="[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"
    echo "${msg}"
    # Append to log file if writable
    mkdir -p "$(dirname "${LOG_FILE}")" 2>/dev/null || true
    echo "${msg}" >> "${LOG_FILE}" 2>/dev/null || true
}

error() {
    log "ERROR: $*" >&2
}

# ────────────────────────────────────────────────────────────────
# Persistent failure notification
# ────────────────────────────────────────────────────────────────
notify_persistent_failure() {
    local attempts="$1"
    local last_error="$2"

    log "NOTIFICATION: Persistent backup failure after ${attempts} attempt(s)"

    if [[ -n "${SLACK_WEBHOOK}" ]]; then
        local payload
        payload=$(cat <<EOF
{
    "text": ":red_circle: PARWA PERSISTENT BACKUP FAILURE",
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":red_circle: *PERSISTENT BACKUP FAILURE*\n\nDatabase backup has failed after *${attempts} attempt(s)*.\n\n*Last Error:*\n\`\`\`${last_error}\`\`\`\n\n_This requires immediate attention._"
            }
        }
    ]
}
EOF
)
        curl -sf -X POST -H 'Content-Type: application/json' \
            --data "${payload}" "${SLACK_WEBHOOK}" > /dev/null 2>&1 || true
    fi
}

# ────────────────────────────────────────────────────────────────
# Run backup with retry
# ────────────────────────────────────────────────────────────────
run_backup() {
    local attempt=0
    local max_attempts=$((MAX_RETRIES + 1))  # Initial attempt + retries
    local last_error=""

    while [[ ${attempt} -lt ${max_attempts} ]]; do
        attempt=$((attempt + 1))
        log "Backup attempt ${attempt}/${max_attempts}"

        if [[ ${attempt} -gt 1 ]]; then
            log "Waiting ${RETRY_DELAY} seconds before retry..."
            sleep "${RETRY_DELAY}"
        fi

        # Run the backup script, capturing output
        if bash "${BACKUP_SCRIPT}" 2>&1; then
            log "Backup attempt ${attempt} succeeded"
            return 0
        else
            last_error="Backup script exited with code $?"
            log "Backup attempt ${attempt} failed: ${last_error}"
        fi
    done

    # All attempts failed
    notify_persistent_failure "${max_attempts}" "${last_error}"
    return 1
}

# ────────────────────────────────────────────────────────────────
# Lock management (prevent overlapping cron runs)
# ────────────────────────────────────────────────────────────────
acquire_lock() {
    if [[ -f "${LOCK_FILE}" ]]; then
        local lock_age
        lock_age=$(( $(date +%s) - $(stat -c %Y "${LOCK_FILE}" 2>/dev/null || echo 0) ))
        # If lock is older than 2 hours, it's stale
        if [[ ${lock_age} -gt 7200 ]]; then
            log "Stale cron lock file detected (${lock_age}s old), removing"
            rm -f "${LOCK_FILE}"
        else
            log "Another backup cron is already running, exiting"
            exit 0
        fi
    fi
    echo $$ > "${LOCK_FILE}"
    trap 'rm -f "${LOCK_FILE}"' EXIT
}

# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────
main() {
    log "=========================================="
    log "PARWA Backup Cron Starting"
    log "Timestamp: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    log "Max retries: ${MAX_RETRIES}"
    log "=========================================="

    # Verify backup script exists
    if [[ ! -f "${BACKUP_SCRIPT}" ]]; then
        error "Backup script not found: ${BACKUP_SCRIPT}"
        exit 1
    fi

    if [[ ! -x "${BACKUP_SCRIPT}" ]]; then
        log "Making backup script executable..."
        chmod +x "${BACKUP_SCRIPT}"
    fi

    # Acquire lock
    acquire_lock

    # Run backup with retries
    if run_backup; then
        log "=========================================="
        log "PARWA Backup Cron Completed Successfully"
        log "=========================================="
        rm -f "${LOCK_FILE}"
        exit 0
    else
        log "=========================================="
        log "PARWA Backup Cron FAILED — all retries exhausted"
        log "=========================================="
        rm -f "${LOCK_FILE}"
        exit 1
    fi
}

main "$@"
