#!/bin/bash
# ════════════════════════════════════════════════════════════════
# PARWA — Developer Database Reset Script
# ════════════════════════════════════════════════════════════════

set -e

echo "⚠️ ATTENTION: This will DESTROY all data in your local PARWA PostgreSQL database."
read -p "Are you sure you want to continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborting."
    exit 1
fi

echo "🛑 Stopping PARWA database and redis containers..."
docker-compose stop db redis

echo "🗑️ Removing database and redis volumes..."
docker-compose rm -f db redis
docker volume rm parwa_postgres_data || true
docker volume rm parwa_redis_data || true

echo "🟢 Recreating and starting core infrastructure..."
docker-compose up -d db redis

echo "⏳ Waiting 10 seconds for PostgreSQL to initialize (including schema.sql mount)..."
sleep 10

echo "✅ Database has been rebuilt from scratch."

if [ -f "venv/bin/activate" ]; then
    echo "🌱 Running database migrations and seeds..."
    source venv/bin/activate
    python3 infra/scripts/seed_db.py
else
    echo "⚠️ Python virtual environment not found. Please run setup.sh first."
fi

echo "🎉 Reset Complete!"
