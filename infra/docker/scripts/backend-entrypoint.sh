#!/bin/bash
set -e

echo "═══════════════════════════════════════════"
echo " PARWA Backend — Starting Production"
echo "═══════════════════════════════════════════"

# Wait for PostgreSQL
echo "[wait] Checking PostgreSQL connection..."
until pg_isready -h ${DB_HOST:-db} -p ${DB_PORT:-5432} -U ${POSTGRES_USER:-parwa} -q 2>/dev/null || \
      python -c "import psycopg2; psycopg2.connect('${DATABASE_URL}')" 2>/dev/null; do
  echo "[wait] PostgreSQL not ready, retrying in 2s..."
  sleep 2
done
echo "[ready] PostgreSQL is up!"

# Wait for Redis
echo "[wait] Checking Redis connection..."
until redis-cli -h ${REDIS_HOST:-redis} -p ${REDIS_PORT:-6379} -a "${REDIS_PASSWORD:-}" ping 2>/dev/null | grep -q PONG; do
  echo "[wait] Redis not ready, retrying in 2s..."
  sleep 2
done
echo "[ready] Redis is up!"

# Run database migrations
echo "[migrate] Running Alembic migrations..."
cd /app/backend
alembic upgrade head 2>/dev/null || {
  echo "[warn] Alembic migration failed — continuing anyway (may be first run)"
}
echo "[migrate] Migrations complete"

# Start the application
echo "[start] Starting FastAPI with Uvicorn..."
exec uvicorn backend.app.main:app \
  --host 0.0.0.0 \
  --port ${PORT:-8000} \
  --workers ${UVICORN_WORKERS:-2} \
  --loop uvloop \
  --no-access-log
