#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════
# PARWA Backend — Start script (NO Docker, SQLite, no Redis)
# ════════════════════════════════════════════════════════════════════
#
# Starts the PARWA FastAPI backend in development mode with:
#   - SQLite database (./parwa_dev.db)
#   - No Redis (rate limiting falls back to in-memory)
#   - No Celery (task queue unavailable)
#   - No PostgreSQL (uses SQLite instead)
#
# Usage:
#   ./start_backend.sh          # Start on port 8000
#   ./start_backend.sh 9000     # Start on port 9000
#
# ════════════════════════════════════════════════════════════════════

set -euo pipefail

# Resolve the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Port (default 8000)
PORT="${1:-8000}"

# Python interpreter
PYTHON="${PYTHON:-$(command -v python3 || echo python3)}"

# Ensure we're in the repo root (contains .env, backend/, database/)
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found in $SCRIPT_DIR"
    echo "Copy .env.example to .env and configure your API keys."
    exit 1
fi

if [ ! -d "backend/app" ]; then
    echo "ERROR: backend/app/ directory not found in $SCRIPT_DIR"
    exit 1
fi

echo "╔══════════════════════════════════════════════════╗"
echo "║  PARWA Backend — Development Mode (no Docker)   ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Port:       $PORT"
echo "║  Database:   SQLite (./parwa_dev.db)"
echo "║  Redis:      DISABLED (in-memory rate limiting)"
echo "║  Celery:     DISABLED (no task queue)"
echo "║  Docs:       http://localhost:$PORT/docs"
echo "║  Health:     http://localhost:$PORT/health"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Export environment
export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/backend"
export ENVIRONMENT="development"
export DEBUG="true"
export DATABASE_URL="sqlite:////home/z/my-project/db/parwa_manual_test.db"
export REDIS_URL=""

# Load .env file (overriding only vars not already set)
set -a
source .env
set +a

# Re-apply our overrides (they take precedence)
export ENVIRONMENT="development"
export DEBUG="true"
export DATABASE_URL="sqlite:////home/z/my-project/db/parwa_manual_test.db"
export REDIS_URL=""

# Start uvicorn (no --reload to avoid double-process issues)
exec "$PYTHON" -m uvicorn backend.app.main:app \
    --host 127.0.0.1 \
    --port "$PORT" \
    --log-level info
