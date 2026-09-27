#!/usr/bin/env bash
# =============================================================================
# PARWA PostgreSQL Backup Script (CROSS-18)
# =============================================================================
# Production-ready backup utility for the Parwa PostgreSQL database.
# Supports daily full backups with gzip compression, retention management,
# post-backup integrity verification, and restore capabilities.
#
# Usage:
#   ./backup.sh                  # Run a full backup
#   ./backup.sh --verify <file>  # Verify backup integrity without restoring
#   ./backup.sh --restore <file> # Restore from a backup file
#
# Environment Variables:
#   PGHOST              - PostgreSQL host        (default: localhost)
#   PGPORT              - PostgreSQL port        (default: 5432)
#   PGDATABASE          - Database name          (default: parwa)
#   PGUSER              - Database user          (default: parwa)
#   PGPASSWORD          - Database password      (default: parwa)
#   BACKUP_DIR          - Backup directory       (default: /backups)
#   BACKUP_RETAIN_DAYS  - Days to retain backups (default: 7)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Connection defaults (match docker-compose)
export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"
export PGDATABASE="${PGDATABASE:-parwa}"
export PGUSER="${PGUSER:-parwa}"
export PGPASSWORD="${PGPASSWORD:-parwa}"

# Backup settings
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-7}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/parwa_backup_${TIMESTAMP}.sql.gz"
LOG_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.log"

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

log() {
    local level="$1"; shift
    local message="$*"
    local ts
    ts=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[${ts}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_info()  { log "INFO"  "$@"; }
log_warn()  { log "WARN"  "$@"; }
log_error() { log "ERROR" "$@"; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

preflight() {
    log_info "Starting pre-flight checks..."

    # Ensure backup directory exists
    if [[ ! -d "${BACKUP_DIR}" ]]; then
        log_info "Creating backup directory: ${BACKUP_DIR}"
        mkdir -p "${BACKUP_DIR}"
    fi

    # Verify pg_dump is available
    if ! command -v pg_dump &>/dev/null; then
        log_error "pg_dump not found. Please install postgresql-client."
        exit 1
    fi

    # Verify pg_restore is available (used for integrity checks)
    if ! command -v pg_restore &>/dev/null; then
        log_error "pg_restore not found. Please install postgresql-client."
        exit 1
    fi

    # Verify gzip is available
    if ! command -v gzip &>/dev/null; then
        log_error "gzip not found. Please install gzip."
        exit 1
    fi

    # Verify database connectivity
    log_info "Testing database connectivity (host=${PGHOST}, port=${PGPORT}, db=${PGDATABASE})..."
    if ! psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c "SELECT 1;" &>/dev/null; then
        log_error "Cannot connect to PostgreSQL. Check connection parameters."
        exit 1
    fi

    log_info "Pre-flight checks passed."
}

# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

run_backup() {
    log_info "=========================================="
    log_info "Starting backup: ${BACKUP_FILE}"
    log_info "=========================================="

    local start_time
    start_time=$(date +%s)

    # Perform the backup: pg_dump | gzip
    if pg_dump \
        -h "${PGHOST}" \
        -p "${PGPORT}" \
        -U "${PGUSER}" \
        -d "${PGDATABASE}" \
        --format=plain \
        --no-owner \
        --no-privileges \
        --clean \
        --if-exists \
        --verbose \
        2>>"${LOG_FILE}" \
    | gzip > "${BACKUP_FILE}"; then

        local end_time
        end_time=$(date +%s)
        local duration=$(( end_time - start_time ))
        local file_size
        file_size=$(du -h "${BACKUP_FILE}" | cut -f1)

        log_info "Backup completed successfully in ${duration}s"
        log_info "File: ${BACKUP_FILE} (size: ${file_size})"

        # Run integrity check
        verify_backup "${BACKUP_FILE}"

        # Prune old backups
        prune_old_backups

        log_info "=========================================="
        log_info "Backup finished successfully"
        log_info "=========================================="
    else
        log_error "Backup FAILED. Check log: ${LOG_FILE}"
        # Clean up partial backup file
        rm -f "${BACKUP_FILE}"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Integrity Verification
# ---------------------------------------------------------------------------

verify_backup() {
    local backup_file="$1"

    if [[ ! -f "${backup_file}" ]]; then
        log_error "Backup file not found: ${backup_file}"
        return 1
    fi

    log_info "Running integrity check on: ${backup_file}"

    # Decompress and pipe through pg_restore --list to verify the dump
    # pg_restore --list reads the TOC (Table of Contents) and validates structure
    if gzip -dc "${backup_file}" | pg_restore --list --format=plain /dev/stdin &>>"${LOG_FILE}"; then
        log_info "Integrity check PASSED for: ${backup_file}"
        return 0
    else
        # For plain-format SQL dumps, pg_restore --list may not produce a TOC.
        # Fall back to a basic sanity check: ensure the file decompresses and
        # contains valid SQL statements.
        log_warn "pg_restore TOC check not applicable for plain SQL format."

        if gzip -t "${backup_file}" 2>>"${LOG_FILE}"; then
            log_info "Gzip integrity PASSED"

            # Verify the decompressed content starts with PostgreSQL dump headers
            local header
            header=$(gzip -dc "${backup_file}" 2>/dev/null | head -5)
            if echo "${header}" | grep -qiE "^(--|PostgreSQL|SET|CREATE|DROP)"; then
                log_info "SQL content header verification PASSED"
                return 0
            else
                log_error "SQL content header verification FAILED - file may be corrupted"
                return 1
            fi
        else
            log_error "Gzip integrity check FAILED - backup file is corrupted"
            return 1
        fi
    fi
}

# ---------------------------------------------------------------------------
# Retention / Pruning
# ---------------------------------------------------------------------------

prune_old_backups() {
    log_info "Pruning backups older than ${BACKUP_RETAIN_DAYS} days..."

    local count=0
    while IFS= read -r -d '' old_file; do
        log_info "Removing old backup: ${old_file}"
        rm -f "${old_file}"
        count=$((count + 1))
    done < <(find "${BACKUP_DIR}" -name "parwa_backup_*.sql.gz" -type f \
             -mtime "+${BACKUP_RETAIN_DAYS}" -print0 2>/dev/null)

    if [[ ${count} -eq 0 ]]; then
        log_info "No old backups to remove."
    else
        log_info "Removed ${count} old backup(s)."
    fi
}

# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

run_restore() {
    local restore_file="$1"

    if [[ ! -f "${restore_file}" ]]; then
        log_error "Restore file not found: ${restore_file}"
        exit 1
    fi

    log_warn "=========================================="
    log_warn "WARNING: Restoring from backup will OVERWRITE"
    log_warn "the current database: ${PGDATABASE}@${PGHOST}:${PGPORT}"
    log_warn "File: ${restore_file}"
    log_warn "=========================================="

    # Safety prompt (skip if non-interactive)
    if [[ -t 0 ]]; then
        read -rp "Type 'YES' to confirm restore: " confirmation
        if [[ "${confirmation}" != "YES" ]]; then
            log_info "Restore cancelled by user."
            exit 0
        fi
    fi

    log_info "Starting restore..."

    local start_time
    start_time=$(date +%s)

    # Decompress and restore via psql
    if gzip -dc "${restore_file}" | psql \
        -h "${PGHOST}" \
        -p "${PGPORT}" \
        -U "${PGUSER}" \
        -d "${PGDATABASE}" \
        --set ON_ERROR_STOP=1 \
        -v ON_ERROR_STOP=1 \
        2>&1 | tee -a "${LOG_FILE}"; then

        local end_time
        end_time=$(date +%s)
        local duration=$(( end_time - start_time ))

        log_info "Restore completed successfully in ${duration}s"
    else
        log_error "Restore FAILED. Check log: ${LOG_FILE}"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

usage() {
    cat <<EOF
PARWA PostgreSQL Backup Script (CROSS-18)

Usage:
  $(basename "$0")                  Run a full database backup
  $(basename "$0") --verify <file>  Verify backup integrity (no restore)
  $(basename "$0") --restore <file> Restore database from a backup file

Environment Variables:
  PGHOST              PostgreSQL host              (default: localhost)
  PGPORT              PostgreSQL port              (default: 5432)
  PGDATABASE          Database name                (default: parwa)
  PGUSER              Database user                (default: parwa)
  PGPASSWORD          Database password            (default: parwa)
  BACKUP_DIR          Backup output directory      (default: /backups)
  BACKUP_RETAIN_DAYS  Days to retain backups       (default: 7)

Examples:
  # Run a backup with defaults
  BACKUP_DIR=/data/backups ./backup.sh

  # Verify a backup file
  ./backup.sh --verify /backups/parwa_backup_20250115_030000.sql.gz

  # Restore from a backup
  ./backup.sh --restore /backups/parwa_backup_20250115_030000.sql.gz
EOF
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    local action="backup"

    case "${1:-}" in
        --restore)
            if [[ -z "${2:-}" ]]; then
                log_error "--restore requires a file path argument."
                usage
                exit 1
            fi
            action="restore"
            # Initialize log for restore
            LOG_FILE="${BACKUP_DIR}/restore_$(date +"%Y%m%d_%H%M%S").log"
            ;;
        --verify)
            if [[ -z "${2:-}" ]]; then
                log_error "--verify requires a file path argument."
                usage
                exit 1
            fi
            action="verify"
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        "")
            # Default action: backup
            ;;
        *)
            log_error "Unknown argument: $1"
            usage
            exit 1
            ;;
    esac

    case "${action}" in
        backup)
            preflight
            run_backup
            ;;
        verify)
            verify_backup "$2"
            if [[ $? -eq 0 ]]; then
                log_info "Backup verification PASSED."
                exit 0
            else
                log_error "Backup verification FAILED."
                exit 1
            fi
            ;;
        restore)
            preflight
            run_restore "$2"
            ;;
    esac
}

main "$@"
