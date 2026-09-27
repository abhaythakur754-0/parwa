#!/bin/sh
# ────────────────────────────────────────────────────────────────────────
# PARWA Backup Runner — executes a single pg_dump with rotation
# Called by cron every 6 hours
# ────────────────────────────────────────────────────────────────────────
set -e

TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="/backups/parwa_backup_${TIMESTAMP}.sql.gz"
RETENTION="${BACKUP_RETENTION_COUNT:-7}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting backup..."

# Run pg_dump and compress
if pg_dump "${DATABASE_URL}" | gzip > "${BACKUP_FILE}"; then
    SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup created: ${BACKUP_FILE} (${SIZE})"

    # Create checksum for integrity verification
    SHA256=$(sha256sum "${BACKUP_FILE}" | awk '{print $1}')
    echo "${SHA256}  ${BACKUP_FILE}" > "${BACKUP_FILE}.sha256"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SHA-256 checksum saved"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Backup failed"
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Rotation — keep last N backups
BACKUP_COUNT=$(ls -1 /backups/parwa_backup_*.sql.gz 2>/dev/null | wc -l)
if [ "${BACKUP_COUNT}" -gt "${RETENTION}" ]; then
    REMOVE_COUNT=$((BACKUP_COUNT - RETENTION))
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Rotating: removing ${REMOVE_COUNT} old backup(s)"
    ls -1t /backups/parwa_backup_*.sql.gz | tail -n "${REMOVE_COUNT}" | while read -r old_file; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Removing: ${old_file}"
        rm -f "${old_file}" "${old_file}.sha256"
    done
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup complete. ${BACKUP_COUNT} backup(s) retained."
