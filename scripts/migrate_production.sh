#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────
# PARWA Production Migration Script (DEPLOY-03)
# Week 8 — Production Deployment
#
# Runs Alembic migrations against the production database with safety
# guards: prerequisite checks, automatic backup, verification, and
# rollback on failure.
#
# Usage:
#   ./migrate_production.sh                   # Full migration
#   ./migrate_production.sh --dry-run         # Preview mode (no changes)
#
# Exit Codes:
#   0  Success
#   1  Migration failure (rollback attempted)
#   2  Prerequisite failure
#   3  Verification failure
# ────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Color helpers ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $(date '+%Y-%m-%d %H:%M:%S')  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $(date '+%Y-%m-%d %H:%M:%S')  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $(date '+%Y-%m-%d %H:%M:%S')  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S')  $*"; }

# ── Globals ────────────────────────────────────────────────────────────
DRY_RUN=false
EXPECTED_MIGRATION_COUNT=18
ALEMBIC_CONFIG="${ALEMBIC_CONFIG:-/app/alembic.ini}"
BACKUP_FILE=""

# ── Parse arguments ────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            log_error "Unknown argument: $1"
            echo "Usage: $0 [--dry-run]"
            exit 2
            ;;
    esac
done

# ── Pre-migration row counts (for verification) ───────────────────────
declare -A ROW_COUNTS_BEFORE=()

get_row_counts() {
    local tables
    tables=$(psql "${DATABASE_URL}" -t -A -c \
        "SELECT table_name FROM information_schema.tables
         WHERE table_schema = 'public'
         ORDER BY table_name;" 2>/dev/null) || {
        log_error "Failed to list tables from database"
        return 1
    }

    local table
    for table in ${tables}; do
        local count
        count=$(psql "${DATABASE_URL}" -t -A -c \
            "SELECT COUNT(*) FROM \"${table}\";" 2>/dev/null) || count="ERROR"
        ROW_COUNTS_BEFORE["${table}"]="${count}"
    done
    log_ok "Captured row counts for ${#ROW_COUNTS_BEFORE[@]} tables"
}

# ── Functions ──────────────────────────────────────────────────────────

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check DATABASE_URL
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log_error "DATABASE_URL environment variable is not set"
        log_error "Export it before running this script:"
        log_error "  export DATABASE_URL='postgresql://user:pass@host:5432/dbname'"
        exit 2
    fi
    log_ok "DATABASE_URL is set"

    # Check psql
    if ! command -v psql &>/dev/null; then
        log_error "psql is not installed or not in PATH"
        log_error "Install it: apt-get install postgresql-client (Debian) or brew install libpq (macOS)"
        exit 2
    fi
    log_ok "psql found: $(command -v psql)"

    # Check alembic
    if ! command -v alembic &>/dev/null; then
        log_error "alembic is not installed or not in PATH"
        log_error "Install it: pip install alembic"
        exit 2
    fi
    log_ok "alembic found: $(command -v alembic)"

    # Check alembic config exists
    if [[ ! -f "${ALEMBIC_CONFIG}" ]]; then
        log_error "Alembic config not found at ${ALEMBIC_CONFIG}"
        exit 2
    fi
    log_ok "Alembic config found at ${ALEMBIC_CONFIG}"

    # Check database connectivity
    log_info "Testing database connectivity..."
    if ! psql "${DATABASE_URL}" -c "SELECT 1;" &>/dev/null; then
        log_error "Cannot connect to database using DATABASE_URL"
        exit 2
    fi
    log_ok "Database connection successful"

    log_ok "All prerequisites satisfied"
}

backup_database() {
    log_info "Creating database backup..."

    local timestamp
    timestamp=$(date '+%Y%m%d_%H%M%S')
    BACKUP_FILE="/tmp/parwa_pre_migration_${timestamp}.sql.gz"

    if [[ "${DRY_RUN}" == true ]]; then
        log_warn "[DRY-RUN] Would create backup: ${BACKUP_FILE}"
        return 0
    fi

    if pg_dump "${DATABASE_URL}" | gzip > "${BACKUP_FILE}"; then
        local size
        size=$(du -h "${BACKUP_FILE}" | cut -f1)
        log_ok "Backup created: ${BACKUP_FILE} (${size})"
    else
        log_error "Database backup failed"
        exit 1
    fi
}

run_migration() {
    log_info "Running Alembic migrations..."

    if [[ "${DRY_RUN}" == true ]]; then
        log_warn "[DRY-RUN] Would run: alembic -c ${ALEMBIC_CONFIG} upgrade head"
        # Show current state
        local current_rev
        current_rev=$(alembic -c "${ALEMBIC_CONFIG}" current 2>/dev/null || echo "unknown")
        log_info "Current migration revision: ${current_rev}"
        local heads
        heads=$(alembic -c "${ALEMBIC_CONFIG}" heads 2>/dev/null || echo "unknown")
        log_info "Target head revision(s): ${heads}"
        log_warn "[DRY-RUN] No changes were made"
        return 0
    fi

    if alembic -c "${ALEMBIC_CONFIG}" upgrade head; then
        log_ok "Alembic migration completed successfully"
    else
        log_error "Alembic migration failed"
        log_info "Initiating rollback..."
        rollback
        exit 1
    fi
}

verify_migration() {
    log_info "Verifying migration..."

    if [[ "${DRY_RUN}" == true ]]; then
        log_warn "[DRY-RUN] Skipping verification"
        return 0
    fi

    # Check that all 18 migrations are applied
    local applied_count
    applied_count=$(alembic -c "${ALEMBIC_CONFIG}" history --verbose 2>/dev/null \
        | grep -c "^[0-9a-f]\{4,\}" || echo "0")

    local total_revisions
    total_revisions=$(alembic -c "${ALEMBIC_CONFIG}" history 2>/dev/null \
        | wc -l | tr -d ' ')

    # Check current matches head
    local current
    current=$(alembic -c "${ALEMBIC_CONFIG}" current 2>/dev/null | head -1 | awk '{print $1}')
    local head
    head=$(alembic -c "${ALEMBIC_CONFIG}" heads 2>/dev/null | head -1 | awk '{print $1}')

    if [[ "${current}" != "${head}" ]]; then
        log_error "Migration verification failed: current (${current}) != head (${head})"
        exit 3
    fi

    log_ok "Current revision matches head: ${head}"

    # Check total migration count
    if [[ "${total_revisions}" -lt "${EXPECTED_MIGRATION_COUNT}" ]]; then
        log_warn "Expected ${EXPECTED_MIGRATION_COUNT} migrations but found ${total_revisions}"
        log_warn "This may be normal if new migrations haven't been added yet"
    else
        log_ok "Migration count: ${total_revisions} (expected >= ${EXPECTED_MIGRATION_COUNT})"
    fi

    # Compare row counts before/after
    local tables
    tables=$(psql "${DATABASE_URL}" -t -A -c \
        "SELECT table_name FROM information_schema.tables
         WHERE table_schema = 'public'
         ORDER BY table_name;" 2>/dev/null) || {
        log_error "Failed to list tables for row count verification"
        exit 3
    }

    local mismatches=0
    local table
    for table in ${tables}; do
        local before="${ROW_COUNTS_BEFORE[${table}]:-0}"
        local after
        after=$(psql "${DATABASE_URL}" -t -A -c \
            "SELECT COUNT(*) FROM \"${table}\";" 2>/dev/null) || after="ERROR"

        if [[ "${before}" != "ERROR" && "${after}" != "ERROR" && "${before}" != "${after}" ]]; then
            log_warn "Row count changed for '${table}': before=${before}, after=${after}"
            mismatches=$((mismatches + 1))
        fi
    done

    if [[ "${mismatches}" -gt 0 ]]; then
        log_warn "${mismatches} table(s) had row count changes (may be expected from migration DML)"
    fi

    log_ok "Migration verification passed"
}

rollback() {
    log_info "Starting rollback..."

    if [[ -z "${BACKUP_FILE}" || ! -f "${BACKUP_FILE}" ]]; then
        log_error "No backup file available for rollback"
        log_error "Manual intervention required — check Alembic downgrade commands"
        return 1
    fi

    log_info "Restoring from backup: ${BACKUP_FILE}"

    # Drop all connections before restore
    psql "${DATABASE_URL}" -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
         WHERE datname = current_database() AND pid <> pg_backend_pid();" 2>/dev/null || true

    if gunzip -c "${BACKUP_FILE}" | psql "${DATABASE_URL}" 2>&1; then
        log_ok "Rollback completed successfully from backup"
    else
        log_error "Rollback failed — database may be in an inconsistent state"
        log_error "Manual intervention required"
        return 1
    fi
}

# ── Main ───────────────────────────────────────────────────────────────
main() {
    echo "========================================================"
    echo "  PARWA Production Migration Script"
    echo "  Date: $(date '+%Y-%m-%d %H:%M:%S')"
    if [[ "${DRY_RUN}" == true ]]; then
        echo "  Mode: DRY-RUN (no changes will be made)"
    fi
    echo "========================================================"
    echo ""

    check_prerequisites
    echo ""

    get_row_counts
    echo ""

    backup_database
    echo ""

    run_migration
    echo ""

    verify_migration
    echo ""

    echo "========================================================"
    log_ok "Production migration completed successfully!"
    if [[ "${DRY_RUN}" == true ]]; then
        log_warn "This was a dry-run — no changes were made"
    else
        log_info "Backup retained at: ${BACKUP_FILE}"
    fi
    echo "========================================================"

    exit 0
}

main "$@"
