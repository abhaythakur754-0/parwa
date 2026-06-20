#!/bin/bash
set -e

echo "═══════════════════════════════════════════"
echo " PARWA Worker — Starting Production"
echo "═══════════════════════════════════════════"

# Wait for Redis (broker)
echo "[wait] Checking Redis connection..."
until redis-cli -h ${REDIS_HOST:-redis} -p ${REDIS_PORT:-6379} -a "${REDIS_PASSWORD:-}" ping 2>/dev/null | grep -q PONG; do
  echo "[wait] Redis not ready, retrying in 2s..."
  sleep 2
done
echo "[ready] Redis is up!"

# Wait for PostgreSQL
echo "[wait] Checking PostgreSQL connection..."
MAX_RETRIES=30
RETRY_COUNT=0
until python -c "import psycopg2; psycopg2.connect('${DATABASE_URL}')" 2>/dev/null; do
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "[error] PostgreSQL not ready after $MAX_RETRIES retries. Exiting."
    exit 1
  fi
  echo "[wait] PostgreSQL not ready, retrying in 2s... ($RETRY_COUNT/$MAX_RETRIES)"
  sleep 2
done
echo "[ready] PostgreSQL is up!"

# Start Celery worker
echo "[start] Starting Celery worker..."
exec celery -A backend.worker.main worker \
  --loglevel=info \
  --concurrency=${CELERY_CONCURRENCY:-2} \
  --max-tasks-per-child=100 \
  --without-heartbeat
