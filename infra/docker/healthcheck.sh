#!/bin/sh
# ────────────────────────────────────────────────────────────────────────
# PARWA Backup Health Check
# Verifies that the most recent backup is less than 7 hours old
# Returns 0 if healthy, 1 if unhealthy
# ────────────────────────────────────────────────────────────────────────

MAX_AGE_SECONDS=25200  # 7 hours

# Find the most recent backup file
LATEST=$(ls -1t /backups/parwa_backup_*.sql.gz 2>/dev/null | head -1)

if [ -z "${LATEST}" ]; then
    echo "ERROR: No backup files found in /backups/"
    exit 1
fi

# Check file age in seconds (works on Alpine busybox)
CURRENT_EPOCH=$(date +%s)
FILE_EPOCH=$(stat -c %Y "${LATEST}" 2>/dev/null || stat -f %m "${LATEST}" 2>/dev/null)
if [ -z "${FILE_EPOCH}" ]; then
    echo "ERROR: Cannot determine backup file timestamp"
    exit 1
fi

AGE=$((CURRENT_EPOCH - FILE_EPOCH))

if [ "${AGE}" -gt "${MAX_AGE_SECONDS}" ]; then
    HOURS=$((AGE / 3600))
    echo "ERROR: Latest backup is ${HOURS} hours old (max: 7 hours)"
    echo "Latest backup: ${LATEST}"
    exit 1
fi

# Check file is non-empty
if [ ! -s "${LATEST}" ]; then
    echo "ERROR: Latest backup file is empty: ${LATEST}"
    exit 1
fi

# Optional: verify gzip integrity
if ! gzip -t "${LATEST}" 2>/dev/null; then
    echo "ERROR: Latest backup fails gzip integrity test: ${LATEST}"
    exit 1
fi

HOURS=$((AGE / 3600))
MINUTES=$(((AGE % 3600) / 60))
echo "OK: Latest backup is ${HOURS}h ${MINUTES}m old — ${LATEST}"
exit 0
