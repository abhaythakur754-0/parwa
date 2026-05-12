#!/bin/bash
# ════════════════════════════════════════════════════════════════
# PARWA — Database Backup Script
# Production-ready backup with compression, S3 upload, rotation,
# integrity verification, and Slack/email notification on failure.
# BC-012: All timestamps in UTC
# ════════════════════════════════════════════════════════════════

set -euo pipefail

# ────────────────────────────────────────────────────────────────
# Configuration (override via environment variables)
# ────────────────────────────────────────────────────────────────
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-parwa_db}"
DB_USER="${DB_USER:-parwa}"
DB_PASSWORD="${DB_PASSWORD:-}"
PGPASSWORD="${DB_PASSWORD}"  # Used by pg_dump

BACKUP_DIR="${BACKUP_DIR:-/backups}"
S3_BUCKET="${S3_BUCKET:-}"       # Optional: s3://bucket-name/path
RETENTION_DAYS="${RETENTION_DAYS:-7}"
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"  # Optional: Slack webhook URL
EMAIL_NOTIFY="${EMAIL_NOTIFY:-}"    # Optional: email address for notifications

TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)  # BC-012: UTC timestamp
BACKUP_FILE="${BACKUP_DIR}/parwa_${TIMESTAMP}.sql.gz"
BACKUP_CHECKSUM="${BACKUP_FILE}.sha256"
LOCK_FILE="${BACKUP_DIR}/.backup.lock"
LOCK_TIMEOUT=3600  # 1 hour max lock

# ────────────────────────────────────────────────────────────────
# Logging (UTC timestamps per BC-012)
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
# Notification
# ────────────────────────────────────────────────────────────────
notify_failure() {
    local subject="PARWA Backup FAILED: ${DB_NAME} at ${TIMESTAMP}"
    local message="$1"

    log "NOTIFICATION: ${subject} — ${message}"

    # Slack notification
    if [[ -n "${SLACK_WEBHOOK}" ]]; then
        local payload
        payload=$(cat <<EOF
{
    "text": ":rotating_light: ${subject}",
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":rotating_light: *Database Backup Failed*\n\n*Database:* \`${DB_NAME}\`\n*Host:* \`${DB_HOST}\`\n*Timestamp:* ${TIMESTAMP} UTC\n\n*Error:*\n\`\`\`${message}\`\`\`"
            }
        }
    ]
}
EOF
)
        if curl -sf -X POST -H 'Content-Type: application/json' \
            --data "${payload}" "${SLACK_WEBHOOK}" > /dev/null 2>&1; then
            log "Slack notification sent successfully"
        else
            warn "Failed to send Slack notification"
        fi
    fi

    # Email notification (uses mail command if available)
    if [[ -n "${EMAIL_NOTIFY}" ]] && command -v mail > /dev/null 2>&1; then
        echo "${message}" | mail -s "${subject}" "${EMAIL_NOTIFY}" 2>/dev/null || \
            warn "Failed to send email notification"
    fi
}

notify_success() {
    local size
    size=$(du -h "${BACKUP_FILE}" 2>/dev/null | cut -f1 || echo "unknown")
    local subject="PARWA Backup SUCCESS: ${DB_NAME} at ${TIMESTAMP}"

    if [[ -n "${SLACK_WEBHOOK}" ]]; then
        local payload
        payload=$(cat <<EOF
{
    "text": ":white_check_mark: ${subject}",
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":white_check_mark: *Database Backup Completed*\n\n*Database:* \`${DB_NAME}\`\n*Host:* \`${DB_HOST}\`\n*Timestamp:* ${TIMESTAMP} UTC\n*Size:* ${size}\n*File:* \`${BACKUP_FILE}\`"
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
# Lock management (prevent concurrent backups)
# ────────────────────────────────────────────────────────────────
acquire_lock() {
    if [[ -f "${LOCK_FILE}" ]]; then
        local lock_age
        lock_age=$(( $(date +%s) - $(stat -c %Y "${LOCK_FILE}" 2>/dev/null || echo 0) ))
        if [[ ${lock_age} -gt ${LOCK_TIMEOUT} ]]; then
            warn "Stale lock file detected (${lock_age}s old), removing"
            rm -f "${LOCK_FILE}"
        else
            error "Another backup is already running (lock file: ${LOCK_FILE})"
            exit 1
        fi
    fi
    echo $$ > "${LOCK_FILE}"
    trap 'rm -f "${LOCK_FILE}"' EXIT
}

release_lock() {
    rm -f "${LOCK_FILE}"
}

# ────────────────────────────────────────────────────────────────
# Integrity verification
# ────────────────────────────────────────────────────────────────
verify_backup() {
    log "Verifying backup integrity..."

    # Check file exists and is non-empty
    if [[ ! -f "${BACKUP_FILE}" ]]; then
        error "Backup file not found: ${BACKUP_FILE}"
        return 1
    fi

    local file_size
    file_size=$(stat -c %s "${BACKUP_FILE}" 2>/dev/null || echo 0)
    if [[ ${file_size} -eq 0 ]]; then
        error "Backup file is empty: ${BACKUP_FILE}"
        return 1
    fi

    # Verify gzip integrity
    if ! gzip -t "${BACKUP_FILE}" 2>/dev/null; then
        error "Backup file gzip integrity check failed: ${BACKUP_FILE}"
        return 1
    fi

    # Generate SHA-256 checksum
    sha256sum "${BACKUP_FILE}" > "${BACKUP_CHECKSUM}"
    log "Checksum generated: $(cat "${BACKUP_CHECKSUM}")"

    # Verify the backup contains actual SQL content
    local sql_check
    sql_check=$(zcat "${BACKUP_FILE}" 2>/dev/null | head -20 | grep -c "PostgreSQL\|CREATE\|INSERT\|COPY" || true)
    if [[ ${sql_check} -eq 0 ]]; then
        warn "Backup may not contain valid SQL content — manual verification recommended"
    fi

    log "Backup integrity verification passed (size: ${file_size} bytes)"
    return 0
}

# ────────────────────────────────────────────────────────────────
# Cleanup old backups (local rotation)
# ────────────────────────────────────────────────────────────────
cleanup_old_backups() {
    log "Cleaning up backups older than ${RETENTION_DAYS} days..."

    local deleted=0
    while IFS= read -r old_file; do
        if [[ -n "${old_file}" ]]; then
            rm -f "${old_file}" "${old_file}.sha256"
            deleted=$((deleted + 1))
            log "Deleted old backup: ${old_file}"
        fi
    done < <(find "${BACKUP_DIR}" -name "parwa_*.sql.gz" -type f -mtime +${RETENTION_DAYS} 2>/dev/null || true)

    log "Cleanup complete: ${deleted} old backup(s) removed"
}

# ────────────────────────────────────────────────────────────────
# S3 upload
# ────────────────────────────────────────────────────────────────
upload_to_s3() {
    if [[ -z "${S3_BUCKET}" ]]; then
        log "S3 upload skipped (S3_BUCKET not configured)"
        return 0
    fi

    log "Uploading backup to S3: ${S3_BUCKET}"

    if ! command -v aws > /dev/null 2>&1; then
        error "AWS CLI not found — cannot upload to S3"
        return 1
    fi

    # Upload backup file
    if ! aws s3 cp "${BACKUP_FILE}" "${S3_BUCKET}/parwa_${TIMESTAMP}.sql.gz" --no-progress; then
        error "Failed to upload backup to S3"
        return 1
    fi

    # Upload checksum
    if ! aws s3 cp "${BACKUP_CHECKSUM}" "${S3_BUCKET}/parwa_${TIMESTAMP}.sql.gz.sha256" --no-progress; then
        error "Failed to upload checksum to S3"
        return 1
    fi

    log "S3 upload completed successfully"

    # Cleanup old S3 backups
    local s3_retention_date
    s3_retention_date=$(date -u -d "-${RETENTION_DAYS} days" +%Y%m%d 2>/dev/null || \
                        date -u -v-${RETENTION_DAYS}d +%Y%m%d 2>/dev/null || echo "")

    if [[ -n "${s3_retention_date}" ]]; then
        log "Cleaning up S3 backups older than ${RETENTION_DAYS} days..."
        aws s3 ls "${S3_BUCKET}/parwa_" --recursive 2>/dev/null | while read -r _ _ _ key; do
            # Extract date from filename parwa_YYYYMMDD_HHMMSS.sql.gz
            local file_date
            file_date=$(echo "${key}" | grep -oP 'parwa_\K\d{8}' || true)
            if [[ -n "${file_date}" ]] && [[ "${file_date}" < "${s3_retention_date}" ]]; then
                aws s3 rm "s3://${key}" > /dev/null 2>&1 || true
                log "Deleted old S3 backup: ${key}"
            fi
        done
    fi

    return 0
}

# ────────────────────────────────────────────────────────────────
# Main backup procedure
# ────────────────────────────────────────────────────────────────
main() {
    log "=========================================="
    log "PARWA Database Backup Starting"
    log "Database: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
    log "Timestamp: ${TIMESTAMP} UTC"
    log "=========================================="

    # Ensure backup directory exists
    mkdir -p "${BACKUP_DIR}"

    # Acquire lock to prevent concurrent backups
    acquire_lock

    # Export PGPASSWORD for pg_dump (avoid prompting)
    export PGPASSWORD="${DB_PASSWORD}"

    # Verify database connectivity
    log "Verifying database connectivity..."
    if ! pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" > /dev/null 2>&1; then
        error "Database is not reachable at ${DB_HOST}:${DB_PORT}"
        notify_failure "Database not reachable at ${DB_HOST}:${DB_PORT}"
        exit 1
    fi
    log "Database connectivity confirmed"

    # Perform pg_dump with compression
    log "Starting pg_dump of ${DB_NAME}..."
    if ! pg_dump \
        -h "${DB_HOST}" \
        -p "${DB_PORT}" \
        -U "${DB_USER}" \
        -d "${DB_NAME}" \
        --format=plain \
        --no-owner \
        --no-acl \
        --clean \
        --if-exists \
        --serializable-deferrable \
        --quote-all-identifiers \
        2>"${BACKUP_FILE}.err" | gzip -9 > "${BACKUP_FILE}"; then
        error "pg_dump failed. Error output:"
        if [[ -f "${BACKUP_FILE}.err" ]]; then
            error "$(cat "${BACKUP_FILE}.err")"
            notify_failure "pg_dump failed: $(cat "${BACKUP_FILE}.err")"
            rm -f "${BACKUP_FILE}.err"
        else
            notify_failure "pg_dump failed with unknown error"
        fi
        exit 1
    fi

    # Clean up error file (empty = no errors)
    rm -f "${BACKUP_FILE}.err"

    # Unset PGPASSWORD for security
    unset PGPASSWORD

    log "pg_dump completed: ${BACKUP_FILE}"

    # Verify backup integrity
    if ! verify_backup; then
        notify_failure "Backup integrity verification failed"
        exit 1
    fi

    # Upload to S3 (optional)
    if ! upload_to_s3; then
        warn "S3 upload failed — local backup is still available"
    fi

    # Cleanup old backups
    cleanup_old_backups

    # Release lock
    release_lock

    log "=========================================="
    log "PARWA Database Backup Completed Successfully"
    log "File: ${BACKUP_FILE}"
    log "=========================================="

    # Send success notification
    notify_success
}

# Run main function with error handling
if ! main; then
    exit_code=$?
    release_lock 2>/dev/null || true
    log "Backup failed with exit code ${exit_code}"
    exit ${exit_code}
fi
