#!/bin/bash
# ════════════════════════════════════════════════════════════════
# PARWA — Database Restore Script
# - Verify backup integrity before restoring
# - Point-in-time recovery support
# - Safety confirmations (require --force in non-interactive mode)
# - Pre-restore backup of current state
# BC-012: All timestamps in UTC
# ════════════════════════════════════════════════════════════════

set -euo pipefail

# ────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-parwa_db}"
DB_USER="${DB_USER:-parwa}"
DB_PASSWORD="${DB_PASSWORD:-}"

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RESTORE_FILE=""           # Will be set from args or latest backup
PRE_RESTORE_BACKUP=true   # Create backup of current state before restoring
FORCE="${FORCE:-false}"   # Skip confirmation prompts
DRY_RUN="${DRY_RUN:-false}"  # Show what would happen without doing it
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)  # BC-012: UTC
APP_STOP_COMMAND="${APP_STOP_COMMAND:-}"
APP_START_COMMAND="${APP_START_COMMAND:-}"

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
# Usage
# ────────────────────────────────────────────────────────────────
usage() {
    cat <<EOF
Usage: $0 [OPTIONS] [BACKUP_FILE]

Restore PARWA database from a backup file.

Options:
  -f, --file FILE       Specific backup file to restore (gzip compressed SQL)
  -l, --latest          Use the most recent backup file
  -d, --date YYYYMMDD   Use the most recent backup from a specific date
  -n, --dry-run         Show what would happen without making changes
  --force               Skip confirmation prompts (for automated restores)
  --no-pre-backup       Skip creating a pre-restore backup
  --s3 S3_PATH          Download backup from S3 before restoring
  -t, --tables TABLES   Comma-separated list of tables for partial restore
  -h, --help            Show this help message

Examples:
  $0 --latest                              # Restore from latest backup
  $0 --date 20240115                       # Restore from backup on Jan 15
  $0 -f /backups/parwa_20240115_060000.sql.gz  # Restore specific file
  $0 --latest --force --no-pre-backup      # Automated restore (CI/CD)

EOF
    exit "${1:-1}"
}

# ────────────────────────────────────────────────────────────────
# Parse arguments
# ────────────────────────────────────────────────────────────────
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -f|--file)
                RESTORE_FILE="$2"
                shift 2
                ;;
            -l|--latest)
                RESTORE_FILE=$(find "${BACKUP_DIR}" -name "parwa_*.sql.gz" -type f -print0 2>/dev/null | \
                    xargs -0 ls -t 2>/dev/null | head -1 || echo "")
                if [[ -z "${RESTORE_FILE}" ]]; then
                    error "No backup files found in ${BACKUP_DIR}"
                    exit 1
                fi
                shift
                ;;
            -d|--date)
                local target_date="$2"
                RESTORE_FILE=$(find "${BACKUP_DIR}" -name "parwa_${target_date}_*.sql.gz" -type f -print0 2>/dev/null | \
                    xargs -0 ls -t 2>/dev/null | head -1 || echo "")
                if [[ -z "${RESTORE_FILE}" ]]; then
                    error "No backup found for date ${target_date} in ${BACKUP_DIR}"
                    exit 1
                fi
                shift 2
                ;;
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --no-pre-backup)
                PRE_RESTORE_BACKUP=false
                shift
                ;;
            --s3)
                S3_PATH="$2"
                # Download from S3 to local temp file
                RESTORE_FILE="${BACKUP_DIR}/s3_restore_${TIMESTAMP}.sql.gz"
                download_from_s3 "${S3_PATH}" "${RESTORE_FILE}"
                shift 2
                ;;
            -t|--tables)
                RESTORE_TABLES="$2"
                shift 2
                ;;
            -h|--help)
                usage 0
                ;;
            *)
                # Positional argument: backup file path
                if [[ -z "${RESTORE_FILE}" ]]; then
                    RESTORE_FILE="$1"
                else
                    error "Unknown option: $1"
                    usage 1
                fi
                shift
                ;;
        esac
    done

    # Validate we have a backup file
    if [[ -z "${RESTORE_FILE}" ]]; then
        error "No backup file specified. Use --latest, --date, or --file"
        usage 1
    fi

    if [[ ! -f "${RESTORE_FILE}" ]]; then
        error "Backup file not found: ${RESTORE_FILE}"
        exit 1
    fi
}

# ────────────────────────────────────────────────────────────────
# Verify backup integrity
# ────────────────────────────────────────────────────────────────
verify_backup_file() {
    local file="$1"
    log "Verifying backup file integrity: ${file}"

    # Check file exists and is non-empty
    if [[ ! -f "${file}" ]]; then
        error "Backup file not found: ${file}"
        return 1
    fi

    local file_size
    file_size=$(stat -c %s "${file}" 2>/dev/null || echo 0)
    if [[ ${file_size} -eq 0 ]]; then
        error "Backup file is empty: ${file}"
        return 1
    fi

    # Verify gzip integrity
    if ! gzip -t "${file}" 2>/dev/null; then
        error "Backup file gzip integrity check failed: ${file}"
        return 1
    fi

    # Check SHA-256 checksum if available
    local checksum_file="${file}.sha256"
    if [[ -f "${checksum_file}" ]]; then
        log "Verifying SHA-256 checksum..."
        if ! sha256sum -c "${checksum_file}" > /dev/null 2>&1; then
            error "SHA-256 checksum verification failed: ${file}"
            return 1
        fi
        log "SHA-256 checksum verified"
    else
        warn "No checksum file found (${checksum_file}) — skipping checksum verification"
    fi

    # Verify SQL content
    local sql_check
    sql_check=$(zcat "${file}" 2>/dev/null | head -50 | grep -c "PostgreSQL\|CREATE\|INSERT\|COPY" || true)
    if [[ ${sql_check} -eq 0 ]]; then
        error "Backup does not appear to contain valid SQL content"
        return 1
    fi

    log "Backup integrity verification passed (size: ${file_size} bytes)"
    return 0
}

# ────────────────────────────────────────────────────────────────
# Create pre-restore backup (safety net)
# ────────────────────────────────────────────────────────────────
create_pre_restore_backup() {
    if [[ "${PRE_RESTORE_BACKUP}" != "true" ]]; then
        log "Pre-restore backup skipped (--no-pre-backup)"
        return 0
    fi

    local pre_backup_file="${BACKUP_DIR}/parwa_prerestore_${TIMESTAMP}.sql.gz"
    log "Creating pre-restore backup of current database state..."

    export PGPASSWORD="${DB_PASSWORD}"

    if ! pg_dump \
        -h "${DB_HOST}" \
        -p "${DB_PORT}" \
        -U "${DB_USER}" \
        -d "${DB_NAME}" \
        --format=plain \
        --no-owner \
        --no-acl \
        2>"${pre_backup_file}.err" | gzip -9 > "${pre_backup_file}"; then
        error "Pre-restore backup failed!"
        if [[ -f "${pre_backup_file}.err" ]]; then
            error "$(cat "${pre_backup_file}.err")"
            rm -f "${pre_backup_file}.err"
        fi
        unset PGPASSWORD
        return 1
    fi

    rm -f "${pre_backup_file}.err"
    unset PGPASSWORD

    # Generate checksum for pre-restore backup
    sha256sum "${pre_backup_file}" > "${pre_backup_file}.sha256" 2>/dev/null || true

    log "Pre-restore backup created: ${pre_backup_file}"
    return 0
}

# ────────────────────────────────────────────────────────────────
# Safety confirmation
# ────────────────────────────────────────────────────────────────
confirm_restore() {
    if [[ "${FORCE}" == "true" ]]; then
        log "Force mode — skipping confirmation"
        return 0
    fi

    if [[ "${DRY_RUN}" == "true" ]]; then
        log "Dry run — no confirmation needed"
        return 0
    fi

    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  ⚠️  DATABASE RESTORE WARNING                           ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║  This will REPLACE all data in:                         ║"
    echo "║  Database: ${DB_NAME}                                   ║"
    echo "║  Host: ${DB_HOST}:${DB_PORT}                             ║"
    echo "║                                                         ║"
    echo "║  Restoring from: ${RESTORE_FILE}                        ║"
    echo "║  Pre-restore backup: ${PRE_RESTORE_BACKUP}              ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    read -rp "Type 'RESTORE' to confirm: " confirmation

    if [[ "${confirmation}" != "RESTORE" ]]; then
        log "Restore cancelled by user"
        exit 0
    fi
}

# ────────────────────────────────────────────────────────────────
# Application stop/start around restore
# ────────────────────────────────────────────────────────────────
stop_application() {
    log "Stopping application connections to database..."
    # Signal application to stop using database (can be overridden via env)
    if [[ -n "${APP_STOP_COMMAND}" ]]; then
        log "Running app stop command: ${APP_STOP_COMMAND}"
        eval "${APP_STOP_COMMAND}" || warn "App stop command failed"
    elif command -v docker > /dev/null 2>&1; then
        # Try to pause Docker containers that connect to this database
        docker ps --filter "label=parwa.service" --format '{{.Names}}' 2>/dev/null | while read -r container; do
            log "Pausing container: ${container}"
            docker pause "${container}" 2>/dev/null || true
        done
    fi
}

start_application() {
    log "Restarting application connections to database..."
    if [[ -n "${APP_START_COMMAND}" ]]; then
        log "Running app start command: ${APP_START_COMMAND}"
        eval "${APP_START_COMMAND}" || warn "App start command failed"
    elif command -v docker > /dev/null 2>&1; then
        docker ps --filter "label=parwa.service" --format '{{.Names}}' --filter "status=paused" 2>/dev/null | while read -r container; do
            log "Unpausing container: ${container}"
            docker unpause "${container}" 2>/dev/null || true
        done
    fi
}

# ────────────────────────────────────────────────────────────────
# Download backup from S3
# ────────────────────────────────────────────────────────────────
download_from_s3() {
    local s3_path="$1"
    local local_file="$2"

    if ! command -v aws > /dev/null 2>&1; then
        error "AWS CLI not found — cannot download from S3"
        return 1
    fi

    log "Downloading backup from S3: ${s3_path}"
    if ! aws s3 cp "${s3_path}" "${local_file}" --no-progress; then
        error "Failed to download backup from S3"
        return 1
    fi

    log "S3 download completed: ${local_file}"
    return 0
}

# ────────────────────────────────────────────────────────────────
# Perform the restore
# ────────────────────────────────────────────────────────────────
perform_restore() {
    local file="$1"

    log "Starting database restore from: ${file}"
    log "Target: ${DB_NAME}@${DB_HOST}:${DB_PORT}"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log "[DRY RUN] Would restore ${file} to ${DB_NAME}@${DB_HOST}:${DB_PORT}"
        log "[DRY RUN] Would terminate active connections to ${DB_NAME}"
        log "[DRY RUN] Would run: zcat ${file} | psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME}"
        return 0
    fi

    export PGPASSWORD="${DB_PASSWORD}"

    # Terminate existing connections to the database (except our own)
    log "Terminating existing connections to ${DB_NAME}..."
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid() AND usename NOT IN ('postgres_exporter', 'monitoring', 'pg_readonly');" \
        > /dev/null 2>&1 || warn "Could not terminate all existing connections"

    # Perform the restore
    log "Restoring database..."
    if [[ -n "${RESTORE_TABLES:-}" ]]; then
        log "Performing partial restore for tables: ${RESTORE_TABLES}"
        # Convert comma-separated to pipe-separated for grep
        local table_filter
        table_filter=$(echo "${RESTORE_TABLES}" | tr ',' '|')
        zcat "${file}" | grep -E "(^COPY .*(${table_filter}) |^INSERT INTO .*(${table_filter})|^CREATE TABLE .*(${table_filter})|^ALTER TABLE .*(${table_filter})|^-- Name: .*(${table_filter}))" | \
            psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 --quiet 2>"${BACKUP_DIR}/restore_${TIMESTAMP}.err"
        local restore_rc=$?
        if [[ ${restore_rc} -ne 0 ]]; then
            error "Partial database restore failed!"
            if [[ -f "${BACKUP_DIR}/restore_${TIMESTAMP}.err" ]]; then
                error "$(tail -50 "${BACKUP_DIR}/restore_${TIMESTAMP}.err")"
            fi
            unset PGPASSWORD
            return 1
        fi
    else
        if ! zcat "${file}" | psql \
            -h "${DB_HOST}" \
            -p "${DB_PORT}" \
            -U "${DB_USER}" \
            -d "${DB_NAME}" \
            -v ON_ERROR_STOP=1 \
            --quiet \
            2>"${BACKUP_DIR}/restore_${TIMESTAMP}.err"; then
            error "Database restore failed!"
            if [[ -f "${BACKUP_DIR}/restore_${TIMESTAMP}.err" ]]; then
                error "$(tail -50 "${BACKUP_DIR}/restore_${TIMESTAMP}.err")"
            fi
            unset PGPASSWORD
            return 1
        fi
    fi

    unset PGPASSWORD
    rm -f "${BACKUP_DIR}/restore_${TIMESTAMP}.err"

    # Verify database is accessible after restore
    log "Verifying database accessibility after restore..."
    export PGPASSWORD="${DB_PASSWORD}"
    if ! psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1;" > /dev/null 2>&1; then
        error "Database is not accessible after restore!"
        unset PGPASSWORD
        return 1
    fi
    unset PGPASSWORD

    log "Database restore completed successfully"
    return 0
}

# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────
main() {
    log "=========================================="
    log "PARWA Database Restore Starting"
    log "Timestamp: ${TIMESTAMP} UTC"
    log "=========================================="

    parse_args "$@"

    # Step 1: Verify backup integrity
    if ! verify_backup_file "${RESTORE_FILE}"; then
        error "Backup integrity verification failed — aborting restore"
        exit 1
    fi

    # Step 2: Safety confirmation
    confirm_restore

    # Step 3: Create pre-restore backup
    if ! create_pre_restore_backup; then
        error "Pre-restore backup failed — aborting restore for safety"
        exit 1
    fi

    # Step 4: Stop application before restore
    stop_application

    # Ensure application is restarted even if restore fails
    trap 'start_application' EXIT

    # Step 5: Perform the restore
    if ! perform_restore "${RESTORE_FILE}"; then
        error "Restore failed — pre-restore backup is available in ${BACKUP_DIR}"
        start_application
        exit 1
    fi

    # Step 6: Restart application after restore
    start_application

    # Clear the trap since we've already started the application
    trap - EXIT

    log "=========================================="
    log "PARWA Database Restore Completed Successfully"
    log "Restored from: ${RESTORE_FILE}"
    log "=========================================="
}

# Run main with error handling
if ! main "$@"; then
    exit_code=$?
    log "Restore failed with exit code ${exit_code}"
    exit ${exit_code}
fi
