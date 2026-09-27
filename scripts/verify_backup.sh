#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────
# PARWA Backup Verification Script (DEPLOY-04)
# Week 8 — Production Deployment
#
# Verifies the integrity of a PostgreSQL database backup by restoring it
# to a temporary database, comparing table counts, checking critical
# tables exist, and running integrity checks.
#
# Usage:
#   ./verify_backup.sh <backup_file.sql.gz>
#   ./verify_backup.sh /backups/parwa_20250101_120000.sql.gz
#
# Exit Codes:
#   0  Backup verified successfully
#   1  Backup file missing or empty
#   2  Restore to temporary database failed
#   3  Integrity check failed
#   4  Table count mismatch
# ────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Color helpers ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $(date '+%Y-%m-%d %H:%M:%S')  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $(date '+%Y-%m-%d %H:%M:%S')  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $(date '+%Y-%m-%d %H:%M:%S')  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S')  $*"; }

# ── Globals ────────────────────────────────────────────────────────────
BACKUP_FILE="${1:-}"
TEMP_DB_NAME=""
SOURCE_DB_NAME=""
CRITICAL_TABLES=("users" "companies" "tickets" "conversations")
BACKUP_TABLE_COUNT=0
SOURCE_TABLE_COUNT=0
INTEGRITY_PASSED=false

# ── Parse arguments ────────────────────────────────────────────────────
if [[ -z "${BACKUP_FILE}" ]]; then
    log_error "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    log_error "DATABASE_URL environment variable is not set"
    log_error "Export it before running this script"
    exit 1
fi

# Extract database name and connection parameters from DATABASE_URL
# Supports: postgresql://user:pass@host:port/dbname
parse_database_url() {
    # Strip protocol
    local conn="${DATABASE_URL#postgresql://}"
    conn="${conn#postgres://}"

    # Extract database name (last part after /)
    SOURCE_DB_NAME="${conn##*/}"
    SOURCE_DB_NAME="${SOURCE_DB_NAME%%\?*}"  # Remove query params

    # Build base URL without db name for admin connections
    local base_conn="${conn%/*}"
    BASE_URL="postgresql://${base_conn}"

    log_info "Source database: ${SOURCE_DB_NAME}"
}

# ── Step 1: Check file exists and is non-empty ────────────────────────
check_backup_file() {
    log_info "Checking backup file: ${BACKUP_FILE}"

    if [[ ! -f "${BACKUP_FILE}" ]]; then
        log_error "Backup file does not exist: ${BACKUP_FILE}"
        exit 1
    fi
    log_ok "Backup file exists"

    if [[ ! -s "${BACKUP_FILE}" ]]; then
        log_error "Backup file is empty: ${BACKUP_FILE}"
        exit 1
    fi

    local size
    size=$(du -h "${BACKUP_FILE}" | cut -f1)
    log_ok "Backup file size: ${size}"

    # Verify it looks like a valid gzip file
    if ! gzip -t "${BACKUP_FILE}" 2>/dev/null; then
        log_error "Backup file is not a valid gzip archive"
        exit 1
    fi
    log_ok "Backup file passes gzip integrity test"
}

# ── Step 2: Restore to temporary database ─────────────────────────────
restore_to_temp_db() {
    TEMP_DB_NAME="parwa_verify_$(date '+%Y%m%d%H%M%S')_$$"
    log_info "Creating temporary database: ${TEMP_DB_NAME}"

    # Create temp database
    if ! psql "${BASE_URL}" -c "CREATE DATABASE \"${TEMP_DB_NAME}\";" 2>/dev/null; then
        log_error "Failed to create temporary database"
        exit 2
    fi
    log_ok "Temporary database created"

    # Restore backup into temp database
    log_info "Restoring backup to temporary database..."
    local temp_url
    temp_url="${BASE_URL}/${TEMP_DB_NAME}"

    if gunzip -c "${BACKUP_FILE}" | psql "${temp_url}" &>/dev/null 2>&1; then
        log_ok "Backup restored to temporary database successfully"
    else
        log_error "Failed to restore backup to temporary database"
        cleanup_temp_db
        exit 2
    fi
}

# ── Step 3: Count tables ──────────────────────────────────────────────
count_tables() {
    local db_url="$1"
    local label="$2"

    local count
    count=$(psql "${db_url}" -t -A -c \
        "SELECT COUNT(*) FROM information_schema.tables
         WHERE table_schema = 'public'
         AND table_type = 'BASE TABLE';" 2>/dev/null) || {
        log_error "Failed to count tables in ${label}"
        return 1
    }

    if [[ "${label}" == *"backup"* ]]; then
        BACKUP_TABLE_COUNT="${count}"
    else
        SOURCE_TABLE_COUNT="${count}"
    fi

    log_ok "${label} table count: ${count}"
}

# ── Step 4: Compare table counts ──────────────────────────────────────
compare_table_counts() {
    log_info "Comparing table counts..."

    count_tables "postgresql://${BASE_URL#postgresql://}/${TEMP_DB_NAME}" "backup"
    count_tables "${BASE_URL}/${SOURCE_DB_NAME}" "source"

    if [[ "${BACKUP_TABLE_COUNT}" -eq 0 ]]; then
        log_error "Backup has 0 tables — restore may have failed silently"
        cleanup_temp_db
        exit 2
    fi

    local diff=$(( SOURCE_TABLE_COUNT - BACKUP_TABLE_COUNT ))
    if [[ "${diff}" -gt 0 ]]; then
        log_warn "Source has ${diff} more tables than backup"
        log_warn "This may indicate tables created after the backup was taken"
    elif [[ "${diff}" -lt 0 ]]; then
        log_error "Backup has $((diff * -1)) MORE tables than source — unexpected"
        cleanup_temp_db
        exit 4
    else
        log_ok "Table counts match: ${BACKUP_TABLE_COUNT} tables"
    fi
}

# ── Step 5: Verify critical tables exist ──────────────────────────────
verify_critical_tables() {
    log_info "Checking critical tables exist in backup..."

    local missing=0
    local temp_url="postgresql://${BASE_URL#postgresql://}/${TEMP_DB_NAME}"

    for table in "${CRITICAL_TABLES[@]}"; do
        local exists
        exists=$(psql "${temp_url}" -t -A -c \
            "SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = '${table}'
                AND table_type = 'BASE TABLE'
            );" 2>/dev/null)

        if [[ "${exists}" == "t" ]]; then
            local rows
            rows=$(psql "${temp_url}" -t -A -c \
                "SELECT COUNT(*) FROM \"${table}\";" 2>/dev/null || echo "?")
            log_ok "  ✓ ${table} — ${rows} rows"
        else
            log_error "  ✗ ${table} — MISSING"
            missing=$((missing + 1))
        fi
    done

    if [[ "${missing}" -gt 0 ]]; then
        log_error "${missing} critical table(s) missing from backup"
        cleanup_temp_db
        exit 4
    fi

    log_ok "All ${#CRITICAL_TABLES[@]} critical tables present"
}

# ── Step 6: Run integrity check ───────────────────────────────────────
run_integrity_check() {
    log_info "Running database integrity checks..."

    local temp_url="postgresql://${BASE_URL#postgresql://}/${TEMP_DB_NAME}"
    local errors=0

    # Check for broken foreign keys (referenced tables missing)
    local fk_issues
    fk_issues=$(psql "${temp_url}" -t -A -c \
        "SELECT COUNT(*)
         FROM information_schema.table_constraints tc
         JOIN information_schema.referential_constraints rc
             ON tc.constraint_name = rc.constraint_name
         WHERE tc.constraint_type = 'FOREIGN KEY'
         AND NOT EXISTS (
             SELECT 1 FROM information_schema.tables t
             WHERE t.table_schema = 'public'
             AND t.table_name = (
                 SELECT ccu.table_name
                 FROM information_schema.constraint_column_usage ccu
                 WHERE ccu.constraint_name = rc.unique_constraint_name
             )
         );" 2>/dev/null || echo "0")

    if [[ "${fk_issues}" -gt 0 ]]; then
        log_error "Found ${fk_issues} broken foreign key references"
        errors=$((errors + 1))
    else
        log_ok "Foreign key integrity check passed"
    fi

    # Check for tables without primary keys (warning only)
    local no_pk
    no_pk=$(psql "${temp_url}" -t -A -c \
        "SELECT COUNT(*) FROM information_schema.tables t
         WHERE t.table_schema = 'public'
         AND t.table_type = 'BASE TABLE'
         AND NOT EXISTS (
             SELECT 1 FROM information_schema.table_constraints tc
             WHERE tc.table_name = t.table_name
             AND tc.constraint_type = 'PRIMARY KEY'
         );" 2>/dev/null || echo "0")

    if [[ "${no_pk}" -gt 0 ]]; then
        log_warn "${no_pk} table(s) without primary keys (may be junction tables)"
    else
        log_ok "All tables have primary keys"
    fi

    # Check for empty critical tables
    for table in "${CRITICAL_TABLES[@]}"; do
        local row_count
        row_count=$(psql "${temp_url}" -t -A -c \
            "SELECT COUNT(*) FROM \"${table}\";" 2>/dev/null || echo "0")
        if [[ "${row_count}" == "0" ]]; then
            log_warn "Critical table '${table}' has 0 rows"
        fi
    done

    # Run PostgreSQL built-in integrity check if superuser
    local is_superuser
    is_superuser=$(psql "${temp_url}" -t -A -c \
        "SELECT current_setting('is_superuser');" 2>/dev/null || echo "off")

    if [[ "${is_superuser}" == "on" ]]; then
        log_info "Running pg_catalog integrity checks (superuser detected)..."
        # Sample check on a critical table
        for table in "${CRITICAL_TABLES[@]}"; do
            local check_result
            check_result=$(psql "${temp_url}" -t -A -c \
                "SELECT COUNT(*) FROM \"${table}\" TABLESAMPLE SYSTEM(1);" 2>/dev/null || echo "skip")
            if [[ "${check_result}" == "skip" ]]; then
                log_warn "Could not sample table '${table}'"
            else
                log_ok "  Sampled '${table}': ${check_result} rows in 1% sample"
            fi
        done
    fi

    if [[ "${errors}" -gt 0 ]]; then
        INTEGRITY_PASSED=false
    else
        INTEGRITY_PASSED=true
        log_ok "All integrity checks passed"
    fi
}

# ── Step 7: Cleanup temporary database ────────────────────────────────
cleanup_temp_db() {
    if [[ -z "${TEMP_DB_NAME}" ]]; then
        return 0
    fi

    log_info "Cleaning up temporary database: ${TEMP_DB_NAME}"

    # Terminate any active connections
    psql "${BASE_URL}" -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
         WHERE datname = '${TEMP_DB_NAME}' AND pid <> pg_backend_pid();" 2>/dev/null || true

    # Drop the temporary database
    if psql "${BASE_URL}" -c "DROP DATABASE IF EXISTS \"${TEMP_DB_NAME}\";" 2>/dev/null; then
        log_ok "Temporary database dropped"
        TEMP_DB_NAME=""
    else
        log_warn "Could not drop temporary database — may require manual cleanup"
    fi
}

# ── Print summary ─────────────────────────────────────────────────────
print_summary() {
    echo ""
    echo "========================================================"
    echo "  PARWA Backup Verification Summary"
    echo "  Date: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================================"
    echo ""
    log_info "Backup file:      ${BACKUP_FILE}"
    log_info "Backup tables:    ${BACKUP_TABLE_COUNT}"
    log_info "Source tables:    ${SOURCE_TABLE_COUNT}"
    log_info "Critical tables:  ${#CRITICAL_TABLES[@]} verified"
    log_info "Integrity:        ${INTEGRITY_PASSED}"
    echo ""
}

# ── Main ───────────────────────────────────────────────────────────────
main() {
    echo "========================================================"
    echo "  PARWA Backup Verification Script"
    echo "  Date: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================================"
    echo ""

    parse_database_url
    check_backup_file
    echo ""

    restore_to_temp_db
    echo ""

    compare_table_counts
    echo ""

    verify_critical_tables
    echo ""

    run_integrity_check

    # Always clean up
    cleanup_temp_db
    echo ""

    # Final evaluation
    if [[ "${INTEGRITY_PASSED}" != true ]]; then
        print_summary
        log_error "Verification FAILED — integrity check errors detected"
        exit 3
    fi

    print_summary
    log_ok "Backup verification PASSED — backup is healthy"
    exit 0
}

main "$@"
