#!/bin/bash
# PARWA Local Development Startup Script
# Runs without Docker using SQLite + no-op Redis

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Export all vars from .env file (ignore comments and empty lines)
set -a
while IFS='=' read -r key value; do
    # Skip comments and empty lines
    [[ "$key" =~ ^#.*$ ]] && continue
    [[ -z "$key" ]] && continue
    # Remove surrounding quotes from value
    value="${value%\"}"
    value="${value#\"}"
    export "$key"="$value"
done < .env
set +a

# Override for local dev (no Docker)
export DATABASE_URL="sqlite:///./db/parwa_dev.db"
export REDIS_URL=""
export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/../"

echo "=========================================="
echo "  PARWA Backend - Local Development"
echo "=========================================="
echo "  DATABASE_URL: $DATABASE_URL"
echo "  LLM_PROVIDER: $LLM_PROVIDER"
echo "  REDIS_URL: (empty - no-op mode)"
echo "=========================================="

exec "$SCRIPT_DIR/venv/bin/uvicorn" app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --no-access-log
