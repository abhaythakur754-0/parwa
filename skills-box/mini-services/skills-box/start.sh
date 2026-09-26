#!/usr/bin/env bash
# Parwa Skills Box — start script (idempotent).
# Installs deps if missing, pre-downloads models, serves on port 8055.
set -euo pipefail
cd "$(dirname "$0")"

export PYTHONUNBUFFERED=1
export SKILLS_PORT="${SKILLS_PORT:-8055}"
# RAM guard: 3000 (not 3200) so a load spike never triggers an OS OOM-kill
# on a 4GB box (Ubuntu + cloudflared also need ~500MB). Guard checks every 2s.
export SKILLS_RAM_LIMIT_MB="${SKILLS_RAM_LIMIT_MB:-3000}"
export SKILLS_GUARD_INTERVAL_S="${SKILLS_GUARD_INTERVAL_S:-2}"

# secrets + extra env (e.g. SKILLS_MEM_DB_URL for Supabase) live in skills.env,
# which is gitignored — never commit it:
if [ -f skills.env ]; then set -a; . ./skills.env; set +a; fi

# ── pick python: reuse an active venv, else create a local one ────
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
  PY="${VIRTUAL_ENV}/bin/python"
  PIP="${VIRTUAL_ENV}/bin/pip"
else
  if [ ! -x ".venv/bin/python" ]; then
    echo "[start] creating .venv ..."
    python3 -m venv .venv
  fi
  PY="$PWD/.venv/bin/python"
  PIP="$PWD/.venv/bin/pip"
fi

"$PIP" install --upgrade pip wheel >/dev/null

# ── torch CPU first (avoids 2GB+ CUDA wheels) ─────────────────────
if ! "$PY" -c "import torch" >/dev/null 2>&1; then
  echo "[start] installing torch (CPU) ..."
  "$PIP" install torch --index-url https://download.pytorch.org/whl/cpu
fi

# ── everything else ───────────────────────────────────────────────
if ! "$PY" -c "import fastapi, gliclass, gliner, presidio_analyzer, faster_whisper, paddleocr, argostranslate" >/dev/null 2>&1; then
  echo "[start] installing requirements ..."
  "$PIP" install -r requirements.txt
fi
# memory (/remember) needs psycopg for Supabase Postgres mode — cheap wheel,
# install now so switching to postgres later needs no reinstall
"$PY" -c "import psycopg" >/dev/null 2>&1 || "$PIP" install 'psycopg[binary]>=3.1' || true

# ── spacy model for Presidio (mask falls back to regex without it) ─
"$PY" -c "import en_core_web_sm" >/dev/null 2>&1 || \
  "$PY" -m spacy download en_core_web_sm || echo "[start] WARN: spacy model failed — /mask uses regex floor"

# ── pre-download models (idempotent; failures are soft) ───────────
"$PY" download_models.py || echo "[start] WARN: some downloads failed — they retry lazily on first request"

echo "[start] serving on 0.0.0.0:${SKILLS_PORT}  (key file: $PWD/.skills_key)"
exec "$PY" -m uvicorn main:app --host 0.0.0.0 --port "${SKILLS_PORT}"
