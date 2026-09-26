#!/usr/bin/env bash
# ============================================================================
# setup_skills_box.sh — ONE-FILE installer for Abhay's Ubuntu 4GB box.
#
# What it does (idempotent — safe to re-run any time):
#   1. installs system deps (python3, venv, pip, curl, cloudflared)
#   2. copies the skills-box service to ~/skills-box (or $1)
#   3. creates the venv + installs all python deps (torch CPU first)
#   4. pre-downloads every model
#   5. prints the exact next-step commands (start, key, tunnel, Render env)
#
# Usage:
#   bash setup_skills_box.sh [TARGET_DIR]
#   (default TARGET_DIR = $HOME/skills-box)
#   The script expects the `skills-box` folder (or this repo's
#   mini-services/skills-box) to exist NEXT TO this file, or pass its
#   path as the 2nd argument:  bash setup_skills_box.sh ~/skills-box ./skills-box
# ============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-$HOME/skills-box}"
SRC_DIR="${2:-}"
PORT="${SKILLS_PORT:-8055}"

# find the source folder automatically if not given
if [ -z "$SRC_DIR" ]; then
  for cand in "$SCRIPT_DIR/skills-box" "$SCRIPT_DIR/mini-services/skills-box" "$PWD/skills-box"; do
    if [ -f "$cand/main.py" ]; then SRC_DIR="$cand"; break; fi
  done
fi

echo "==> Parwa Skills Box setup"
echo "    target: $TARGET_DIR"
[ -n "$SRC_DIR" ] && echo "    source: $SRC_DIR" || echo "    source: NOT FOUND (pass as 2nd arg)"

# ── 1. system deps ──────────────────────────────────────────────────────────
if command -v apt-get >/dev/null 2>&1; then
  echo "==> [1/5] installing system packages (apt)"
  sudo apt-get update -y || true
  sudo apt-get install -y python3 python3-venv python3-pip curl ca-certificates tar || true
else
  echo "==> [1/5] apt not found — assuming python3/curl already present"
fi
command -v python3 >/dev/null 2>&1 || { echo "FATAL: python3 missing"; exit 1; }

# ── 2. copy service ─────────────────────────────────────────────────────────
echo "==> [2/5] copying service to $TARGET_DIR"
if [ -n "$SRC_DIR" ] && [ -f "$SRC_DIR/main.py" ]; then
  mkdir -p "$TARGET_DIR"
  cp -r "$SRC_DIR/." "$TARGET_DIR/"
  # never overwrite an existing key on re-run
  if [ -f "$SRC_DIR/.skills_key" ] && [ ! -f "$TARGET_DIR/.skills_key" ]; then
    cp "$SRC_DIR/.skills_key" "$TARGET_DIR/.skills_key"
  fi
elif [ -f "$TARGET_DIR/main.py" ]; then
  echo "    target already has main.py — keeping it"
else
  echo "FATAL: no source folder with main.py found. Put skills-box next to this script"
  echo "       or run: bash setup_skills_box.sh $TARGET_DIR /path/to/skills-box"
  exit 1
fi
cd "$TARGET_DIR"
chmod +x start.sh 2>/dev/null || true

# ── 3. venv + python deps ───────────────────────────────────────────────────
echo "==> [3/5] venv + python deps (torch CPU first — this is the big download)"
if [ ! -x ".venv/bin/python" ]; then python3 -m venv .venv; fi
PY="$PWD/.venv/bin/python"
PIP="$PWD/.venv/bin/pip"
"$PIP" install --upgrade pip wheel >/dev/null
"$PY" -c "import torch" >/dev/null 2>&1 || \
  "$PIP" install torch --index-url https://download.pytorch.org/whl/cpu
"$PIP" install -r requirements.txt

# ── 4. models ───────────────────────────────────────────────────────────────
echo "==> [4/5] pre-downloading models (idempotent — skips cached ones)"
"$PY" -c "import en_core_web_sm" >/dev/null 2>&1 || \
  "$PY" -m spacy download en_core_web_sm || echo "WARN: spacy model failed — /mask uses regex floor"
"$PY" download_models.py || echo "WARN: some downloads failed — they retry lazily on first request"

# ── 5. cloudflared + next steps ─────────────────────────────────────────────
echo "==> [5/5] cloudflared"
if ! command -v cloudflared >/dev/null 2>&1; then
  ARCH="$(uname -m)"
  case "$ARCH" in
    x86_64) CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" ;;
    aarch64) CF_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64" ;;
  esac
  if sudo curl -fsSL "$CF_URL" -o /usr/local/bin/cloudflared 2>/dev/null; then
    sudo chmod +x /usr/local/bin/cloudflared
  else
    curl -fsSL "$CF_URL" -o "$HOME/.local/bin/cloudflared" 2>/dev/null && chmod +x "$HOME/.local/bin/cloudflared" || \
      echo "WARN: cloudflared download failed — install it later (see README)"
  fi
fi
command -v cloudflared >/dev/null 2>&1 && echo "    cloudflared: $(cloudflared --version 2>/dev/null | head -1)" || true

# key: generate now so the printed next steps can reference it
if [ ! -f ".skills_key" ]; then
  "$PY" -c "import core.config" >/dev/null 2>&1 && true
fi
KEY="$("$PY" -c "
import os
os.environ.setdefault('SKILLS_BOX_KEY','')
from core import config
print(config.SKILLS_KEY)
" 2>/dev/null || cat .skills_key 2>/dev/null || echo 'GENERATED-ON-FIRST-START')"

cat <<EOF

============================================================
 SETUP DONE. Next steps (copy-paste):
============================================================

 1) Start the box (survives logout):
      cd $TARGET_DIR
      nohup ./start.sh > box.log 2>&1 &
      sleep 5 && tail -5 box.log

 2) Your ONE key (all 9 skills, header X-Skills-Key):
      $KEY

 3) Quick tunnel (5 min, URL changes on restart):
      cloudflared tunnel --url http://localhost:$PORT
      → copy the printed https://xxxx.trycloudflare.com URL

 4) PROVE it is global (run on THIS box — it goes out to Cloudflare and back):
      curl -s https://YOUR-URL/health
      curl -s https://YOUR-URL/classify -H "X-Skills-Key: $KEY" \\
        -H 'Content-Type: application/json' \\
        -d '{"text":"where is my order 123","labels":["order status","refund"]}'

 5) Permanent tunnel (skills.parwa.buzz — needs Cloudflare dashboard):
      cloudflared tunnel login
      cloudflared tunnel create parwa-skills
      cloudflared tunnel route dns parwa-skills skills.parwa.buzz
      cloudflared tunnel run parwa-skills &
      (or use the Zero-Trust dashboard token method)

 6) After the proof, set these on Render (backend-parwa → Environment):
      SKILLS_BOX_URL = https://skills.parwa.buzz   (or the trycloudflare URL)
      SKILLS_BOX_KEY = $KEY
      OSS_SKILLS_BOX = 1

 7) OPTIONAL — customer memory in a FREE cloud DB (zero disk on this box):
      create a free project at supabase.com → Project Settings → Database
      → copy the "Session pooler" connection string, then:
      cat > $TARGET_DIR/skills.env <<'ENV'
      SKILLS_MEM_STORE=postgres
      SKILLS_MEM_DB_URL=postgresql://postgres.xxx:PASSWORD@aws-0-xx-x.pooler.supabase.com:5432/postgres
      ENV
      (skills.env is gitignored; without it memory uses local SQLite — fine too)
============================================================
EOF
