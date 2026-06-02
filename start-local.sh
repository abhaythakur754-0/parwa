#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# PARWA — Local Development Startup Script (No Docker)
# ═══════════════════════════════════════════════════════════════
# This script starts all 3 services needed for local testing:
#   1. LLM Proxy (port 3001) — ZAI SDK for AI capabilities
#   2. Backend (port 8000)  — FastAPI Python server
#   3. Frontend (port 3000) — Next.js web app
#
# Prerequisites:
#   - Python 3.12+
#   - Node.js 18+
#   - npm
#
# Usage:
#   chmod +x start-local.sh
#   ./start-local.sh          # Start all services
#   ./start-local.sh stop     # Stop all services
# ═══════════════════════════════════════════════════════════════

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$PROJECT_DIR/.pids"

stop_services() {
  echo "Stopping all services..."
  for pid_file in "$PID_DIR"/*.pid; do
    if [ -f "$pid_file" ]; then
      PID=$(cat "$pid_file")
      if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null
        echo "  Stopped PID $PID"
      fi
      rm "$pid_file"
    fi
  done
  echo "All services stopped."
}

if [ "$1" = "stop" ]; then
  stop_services
  exit 0
fi

mkdir -p "$PID_DIR" "$PROJECT_DIR/db"

# ─── 1. LLM Proxy (ZAI SDK) ─────────────────────────────────
echo ""
echo "═══ Starting LLM Proxy (ZAI SDK) on port 3001 ═══"
cd "$PROJECT_DIR"
node llm-proxy.mjs > /tmp/parwa_llm_proxy.log 2>&1 &
echo $! > "$PID_DIR/llm_proxy.pid"
echo "  PID: $(cat "$PID_DIR/llm_proxy.pid")"
sleep 3

# Verify LLM proxy
if curl -s http://localhost:3001/ > /dev/null 2>&1; then
  echo "  ✓ LLM Proxy is running"
else
  echo "  ✗ LLM Proxy failed to start. Check /tmp/parwa_llm_proxy.log"
  exit 1
fi

# ─── 2. Backend (FastAPI) ────────────────────────────────────
echo ""
echo "═══ Starting Backend (FastAPI) on port 8000 ═══"
cd "$PROJECT_DIR"

# Create venv if needed
if [ ! -d "venv" ]; then
  echo "  Creating Python venv..."
  python3 -m venv venv
  source venv/bin/activate
  pip install -q -r requirements.txt
else
  source venv/bin/activate
fi

export PYTHONPATH="$PROJECT_DIR:$PROJECT_DIR/backend"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > /tmp/parwa_backend.log 2>&1 &
echo $! > "$PID_DIR/backend.pid"
echo "  PID: $(cat "$PID_DIR/backend.pid")"
sleep 6

# Verify backend
if curl -s -o /dev/null http://localhost:8000/openapi.json 2>&1; then
  echo "  ✓ Backend is running"
else
  echo "  ✗ Backend failed to start. Check /tmp/parwa_backend.log"
  exit 1
fi

# ─── 3. Frontend (Next.js) ──────────────────────────────────
echo ""
echo "═══ Starting Frontend (Next.js) on port 3000 ═══"
cd "$PROJECT_DIR"

# Install deps if needed
if [ ! -d "node_modules" ]; then
  echo "  Installing npm dependencies..."
  npm install --legacy-peer-deps
fi

npm run dev > /tmp/parwa_frontend.log 2>&1 &
echo $! > "$PID_DIR/frontend.pid"
echo "  PID: $(cat "$PID_DIR/frontend.pid")"
echo "  Waiting for Next.js to compile (this takes ~10-15s)..."
sleep 15

# Verify frontend
if curl -s -o /dev/null http://localhost:3000/ 2>&1; then
  echo "  ✓ Frontend is running"
else
  echo "  ⚠ Frontend may still be compiling. Check /tmp/parwa_frontend.log"
fi

# ─── Summary ────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  PARWA is running!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "  🌐 Frontend:  http://localhost:3000"
echo "  🔧 Backend:   http://localhost:8000"
echo "  📖 API Docs:  http://localhost:8000/docs"
echo "  🤖 LLM Proxy: http://localhost:3001"
echo ""
echo "  To stop: ./start-local.sh stop"
echo "  Logs:    /tmp/parwa_*.log"
echo ""
