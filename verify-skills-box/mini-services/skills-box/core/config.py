"""Central config — env-driven, safe defaults. ONE key for ALL skills."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
KEY_FILE = BASE_DIR / ".skills_key"


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def _str(name: str, default: str) -> str:
    return (os.environ.get(name) or default).strip()


def _load_or_create_key() -> str:
    """SKILLS_BOX_KEY env wins; else reuse .skills_key; else generate + save."""
    env = (os.environ.get("SKILLS_BOX_KEY") or "").strip()
    if env:
        return env
    try:
        if KEY_FILE.exists():
            existing = KEY_FILE.read_text().strip()
            if existing:
                return existing
        key = secrets.token_urlsafe(32)
        KEY_FILE.write_text(key + "\n")
        try:
            KEY_FILE.chmod(0o600)
        except Exception:
            pass
        return key
    except Exception:
        return secrets.token_urlsafe(32)


SKILLS_KEY: str = _load_or_create_key()

# RAM guard — auto-unload LRU models when process RSS crosses this
RAM_LIMIT_MB: int = _int("SKILLS_RAM_LIMIT_MB", 3200)
GUARD_INTERVAL_S: int = _int("SKILLS_GUARD_INTERVAL_S", 5)

# Models (env-overridable)
GLICLASS_MODEL: str = _str("GLICLASS_MODEL", "knowledgator/gliclass-base-v1.0")
GLINER_MODEL: str = _str("GLINER_MODEL", "urchade/gliner_multi-v2.1")
WHISPER_MODEL: str = _str("WHISPER_MODEL", "base")            # base, int8 — safe RAM
WHISPER_COMPUTE: str = _str("WHISPER_COMPUTE", "int8")
PIPER_BIN: str = _str("PIPER_BIN", "")                        # path to piper binary (optional)
PIPER_VOICE: str = _str("PIPER_VOICE", "")                    # path to .onnx voice (optional)
ARGOS_PAIRS: str = _str("ARGOS_PAIRS", "en-de,en-fr,en-es,en-it,en-pt")

# Behavior
MAX_TEXT_CHARS: int = _int("SKILLS_MAX_TEXT_CHARS", 20000)
TRANSCRIBE_TIMEOUT_S: int = _int("TRANSCRIBE_TIMEOUT_S", 30)
BROWSE_TIMEOUT_S: int = _int("BROWSE_TIMEOUT_S", 120)
TORCH_THREADS: int = _int("SKILLS_TORCH_THREADS", max(1, (os.cpu_count() or 2)))
WARMUP: str = _str("SKILLS_WARMUP", "none")  # none | phase1 | all

# Memory (/remember) — Abhay picked DB-backed storage (2026-09-25):
# sqlite default (zero-config), Supabase Postgres free tier = zero local disk.
MEM_STORE: str = _str("SKILLS_MEM_STORE", "sqlite")            # sqlite | postgres
MEM_DB_URL: str = _str("SKILLS_MEM_DB_URL", "")                # postgres DSN (SECRET)
MEM_DB_PATH: str = _str("SKILLS_MEM_DB_PATH", str(BASE_DIR / "data" / "memory.db"))
MEM_MAX_PER_USER: int = _int("SKILLS_MEM_MAX_PER_USER", 500)   # auto-prune oldest

PHASE1_SKILLS = ["classify", "entities", "mask"]
PHASE2_SKILLS = ["ocr", "transcribe"]
PHASE3_SKILLS = ["translate", "speak", "remember", "browse"]
ALL_SKILLS = PHASE1_SKILLS + PHASE2_SKILLS + PHASE3_SKILLS
