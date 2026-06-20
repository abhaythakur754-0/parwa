#!/bin/bash
# PARWA — Backup Container Entrypoint
# Validates environment, runs initial backup test, starts cron daemon

set -euo pipefail

# Validate required environment variables
required_vars=(
    "DATABASE_URL"
    "BACKUP_DIR"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: Required environment variable $var is not set" >&2
        exit 1
    fi
done

# Set defaults
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_RETENTION_COUNT="${BACKUP_RETENTION_COUNT:-7}"
LOG_FILE="${LOG_FILE:-/var/log/backup.log}"

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Backup container starting..."
echo "  BACKUP_DIR: $BACKUP_DIR"
echo "  BACKUP_RETENTION_COUNT: $BACKUP_RETENTION_COUNT"

# Create directories
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Test database connectivity
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Testing database connectivity..."
if pg_isready -d "$DATABASE_URL" >/dev/null 2>&1; then
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Database connection OK"
else
    echo "WARNING: Database not reachable yet. Will retry on schedule."
fi

# Write crontab with environment variables available
cat > /etc/crontabs/root <<EOF
# PARWA Backup Schedule — Every 6 hours
SHELL=/bin/bash
0 */6 * * * /usr/local/bin/run_backup.sh >> ${LOG_FILE} 2>&1
EOF

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Crontab installed. Starting cron daemon..."

# Start cron daemon in foreground
exec crond -f -l 2
