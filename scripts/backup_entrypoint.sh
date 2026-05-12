#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────
# PARWA Backup Container Entrypoint (DEPLOY-01)
# Week 8 — Production Deployment
#
# Entry point for the automated backup container.
# Sets up the cron schedule, runs an immediate initial backup,
# and starts the cron daemon. Handles SIGTERM for graceful shutdown.
# ────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Color helpers ──────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[BACKUP]${NC} $(date '+%Y-%m-%d %H:%M:%S') $*"; }
log_ok()    { echo -e "${GREEN}[BACKUP]${NC} $(date '+%Y-%m-%d %H:%M:%S') $*"; }
log_warn()  { echo -e "${YELLOW}[BACKUP]${NC} $(date '+%Y-%m-%d %H:%M:%S') $*"; }
log_error() { echo -e "${RED}[BACKUP]${NC} $(date '+%Y-%m-%d %H:%M:%S') $*"; }

# ── Graceful shutdown handler ──────────────────────────────────────────
SHUTDOWN_REQUESTED=false

shutdown_handler() {
    log_info "SIGTERM received — shutting down gracefully..."
    SHUTDOWN_REQUESTED=true

    # Kill cron daemon
    if [[ -n "${CRON_PID:-}" ]] && kill -0 "${CRON_PID}" 2>/dev/null; then
        log_info "Stopping cron daemon (PID: ${CRON_PID})..."
        kill -TERM "${CRON_PID}" 2>/dev/null || true
        wait "${CRON_PID}" 2>/dev/null || true
    fi

    log_ok "Backup container stopped cleanly"
    exit 0
}

trap shutdown_handler SIGTERM SIGINT SIGQUIT

# ── Validate environment ──────────────────────────────────────────────
validate_env() {
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log_error "DATABASE_URL is not set. Cannot run backups."
        exit 1
    fi

    # Test database connectivity
    if ! pg_dump --list "${DATABASE_URL}" &>/dev/null; then
        log_error "Cannot connect to database using DATABASE_URL"
        exit 1
    fi

    log_ok "Database connectivity verified"
}

# ── Run initial backup ─────────────────────────────────────────────────
run_initial_backup() {
    log_info "Running initial backup (this may take a while)..."

    if /usr/local/bin/run_backup.sh; then
        log_ok "Initial backup completed successfully"
    else
        log_error "Initial backup failed — check DATABASE_URL and database connectivity"
        # Don't exit — cron may succeed later
        log_warn "Continuing with cron schedule despite initial backup failure"
    fi
}

# ── Start cron daemon ──────────────────────────────────────────────────
start_cron() {
    log_info "Setting up cron schedule (every 6 hours)..."
    log_info "  Schedule: 00:00, 06:00, 12:00, 18:00 UTC"

    # Ensure log file exists
    touch /var/log/backup.log

    # Start crond in foreground, capture PID
    crond -f -l 2 &
    CRON_PID=$!
    log_ok "Cron daemon started (PID: ${CRON_PID})"
}

# ── Main ───────────────────────────────────────────────────────────────
main() {
    log_info "PARWA Backup Container starting..."
    log_info "Retention: ${BACKUP_RETENTION_COUNT:-7} backups"
    log_info "Backup directory: /backups"
    echo ""

    validate_env
    echo ""

    run_initial_backup
    echo ""

    start_cron

    log_ok "PARWA Backup Container is running"
    log_info "Backups will run every 6 hours via cron"
    log_info "Logs: tail -f /var/log/backup.log"

    # Wait for shutdown signal
    while ! ${SHUTDOWN_REQUESTED}; do
        sleep 30 &
        wait $! 2>/dev/null || true
    done
}

main "$@"
