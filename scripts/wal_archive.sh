#!/usr/bin/env bash
# =============================================================================
# PARWA WAL Archiving Script (CROSS-18)
# =============================================================================
# Companion to backup.sh for Write-Ahead Log (WAL) archiving and
# point-in-time recovery (PITR) setup.
#
# Modes:
#   --setup    Configure PostgreSQL for WAL archiving (run once)
#   --archive  Archive a WAL file (called by PostgreSQL archive_command)
#
# Setup configures:
#   - wal_level = replica
#   - archive_mode = on
#   - archive_command (points to this script with --archive)
#   - restore_command (for PITR recovery)
#
# Environment Variables:
#   PGHOST              - PostgreSQL host        (default: localhost)
#   PGPORT              - PostgreSQL port        (default: 5432)
#   PGDATABASE          - Database name          (default: parwa)
#   PGUSER              - Database user          (default: parwa)
#   PGPASSWORD          - Database password      (default: parwa)
#   WAL_ARCHIVE_DIR     - WAL archive directory  (default: /backups/wal_archive)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"
export PGDATABASE="${PGDATABASE:-parwa}"
export PGUSER="${PGUSER:-parwa}"
export PGPASSWORD="${PGPASSWORD:-parwa}"

WAL_ARCHIVE_DIR="${WAL_ARCHIVE_DIR:-/backups/wal_archive}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

log() {
    local level="$1"; shift
    local message="$*"
    local ts
    ts=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[${ts}] [${level}] ${message}"
}

log_info()  { log "INFO"  "$@"; }
log_warn()  { log "WARN"  "$@"; }
log_error() { log "ERROR" "$@"; }

# ---------------------------------------------------------------------------
# Setup mode: Configure PostgreSQL for WAL archiving
# ---------------------------------------------------------------------------

setup_wal_archiving() {
    log_info "=========================================="
    log_info "Setting up WAL archiving for PostgreSQL"
    log_info "=========================================="

    # Verify psql is available
    if ! command -v psql &>/dev/null; then
        log_error "psql not found. Please install postgresql-client."
        exit 1
    fi

    # Verify database connectivity
    log_info "Testing database connectivity (host=${PGHOST}, port=${PGPORT}, db=${PGDATABASE})..."
    if ! psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c "SELECT 1;" &>/dev/null; then
        log_error "Cannot connect to PostgreSQL. Check connection parameters."
        exit 1
    fi

    # Determine superuser status (ALTER SYSTEM requires superuser)
    local is_superuser
    is_superuser=$(psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc \
        "SELECT current_setting('is_superuser');" 2>/dev/null || echo "off")

    if [[ "${is_superuser}" != "on" ]]; then
        log_error "WAL archiving setup requires superuser privileges."
        log_error "Current user '${PGUSER}' is not a superuser."
        log_error "Run this script as the postgres superuser, or manually set:"
        log_error "  wal_level = replica"
        log_error "  archive_mode = on"
        log_error "  archive_command = '$(readlink -f "$0") --archive %p'"
        log_error "  restore_command = 'cp ${WAL_ARCHIVE_DIR}/%f %p'"
        exit 1
    fi

    # Create WAL archive directory
    if [[ ! -d "${WAL_ARCHIVE_DIR}" ]]; then
        log_info "Creating WAL archive directory: ${WAL_ARCHIVE_DIR}"
        mkdir -p "${WAL_ARCHIVE_DIR}"
        chmod 750 "${WAL_ARCHIVE_DIR}"
    fi

    local script_path
    script_path="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

    # Configure PostgreSQL WAL settings via ALTER SYSTEM
    log_info "Configuring PostgreSQL WAL settings..."

    psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" <<EOF
-- Enable WAL archiving
ALTER SYSTEM SET wal_level = 'replica';
ALTER SYSTEM SET archive_mode = 'on';
ALTER SYSTEM SET archive_timeout = '300';  -- Force archive every 5 minutes max
ALTER SYSTEM SET max_wal_size = '2GB';
ALTER SYSTEM SET min_wal_size = '512MB';

-- Set archive command: copy WAL files to the archive directory
-- %p = path to the WAL file being archived
-- %f = filename of the WAL file
ALTER SYSTEM SET archive_command = '${script_path} --archive %p';

-- Set restore command for point-in-time recovery
-- This is used when starting PostgreSQL in recovery mode (recovery_target_time, etc.)
ALTER SYSTEM SET restore_command = 'cp ${WAL_ARCHIVE_DIR}/%f %p';
EOF

    log_info "WAL archiving configuration written to postgresql.auto.conf."
    log_info ""
    log_info "IMPORTANT: PostgreSQL must be restarted for WAL changes to take effect."
    log_info "  sudo systemctl restart postgresql"
    log_info "  -- OR (Docker) --"
    log_info "  docker restart <postgres_container>"
    log_info ""
    log_info "After restart, verify with:"
    log_info "  psql -c \"SHOW archive_mode;\""
    log_info "  psql -c \"SHOW archive_command;\""
    log_info ""
    log_info "For point-in-time recovery:"
    log_info "  1. Stop PostgreSQL"
    log_info "  2. Restore the base backup (from backup.sh) to the data directory"
    log_info "  3. Create recovery.signal in the data directory"
    log_info "  4. Set recovery_target_time in postgresql.conf or via ALTER SYSTEM"
    log_info "  5. Start PostgreSQL — it will replay WAL files up to the target time"

    log_info "=========================================="
    log_info "WAL archiving setup completed successfully"
    log_info "=========================================="
}

# ---------------------------------------------------------------------------
# Archive mode: Copy a single WAL file to the archive directory
# (Called by PostgreSQL's archive_command)
# ---------------------------------------------------------------------------

archive_wal_file() {
    local wal_file="$1"

    # Validate the WAL file path exists
    if [[ ! -f "${wal_file}" ]]; then
        log_error "WAL file not found: ${wal_file}"
        return 1
    fi

    # Ensure archive directory exists
    if [[ ! -d "${WAL_ARCHIVE_DIR}" ]]; then
        mkdir -p "${WAL_ARCHIVE_DIR}"
    fi

    local wal_filename
    wal_filename=$(basename "${wal_file}")

    # Copy the WAL file (cp returns 0 on success, which is what PostgreSQL requires)
    if cp "${wal_file}" "${WAL_ARCHIVE_DIR}/${wal_filename}"; then
        log_info "Archived WAL segment: ${wal_filename}"
        return 0
    else
        log_error "Failed to archive WAL segment: ${wal_filename}"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

usage() {
    cat <<EOF
PARWA WAL Archiving Script (CROSS-18)

Usage:
  $(basename "$0") --setup          Configure PostgreSQL for WAL archiving
  $(basename "$0") --archive <file> Archive a WAL file (called by archive_command)

Environment Variables:
  PGHOST              PostgreSQL host              (default: localhost)
  PGPORT              PostgreSQL port              (default: 5432)
  PGDATABASE          Database name                (default: parwa)
  PGUSER              Database user                (default: parwa)
  PGPASSWORD          Database password            (default: parwa)
  WAL_ARCHIVE_DIR     WAL archive directory        (default: /backups/wal_archive)

Examples:
  # Initial setup (run once as superuser)
  PGUSER=postgres ./wal_archive.sh --setup

  # Archive a WAL file (usually called automatically by PostgreSQL)
  ./wal_archive.sh --archive /var/lib/postgresql/data/pg_wal/000000010000000000000001
EOF
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    case "${1:-}" in
        --setup)
            setup_wal_archiving
            ;;
        --archive)
            if [[ -z "${2:-}" ]]; then
                log_error "--archive requires a WAL file path argument."
                usage
                exit 1
            fi
            archive_wal_file "$2"
            # PostgreSQL archive_command expects exit code 0 for success
            exit $?
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown argument: ${1:-<none>}"
            usage
            exit 1
            ;;
    esac
}

main "$@"
