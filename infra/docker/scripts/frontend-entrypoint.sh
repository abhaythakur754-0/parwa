#!/bin/bash
set -e

echo "═══════════════════════════════════════════"
echo " PARWA Frontend — Starting Production"
echo "═══════════════════════════════════════════"

# In production standalone mode, Next.js server.js is the entry point
# The build step already happened in the Dockerfile

PORT=${PORT:-3000}
HOSTNAME=${HOSTNAME:-"0.0.0.0"}

echo "[start] Starting Next.js standalone server on ${HOSTNAME}:${PORT}..."

exec node server.js
