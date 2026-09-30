"""
OSS Stack — free open-source components bolted onto PARWA's pipeline.

Each module is OPTIONAL and degrades gracefully:
  - If the library is not installed, the module reports `available=False`
    and callers fall back to existing PARWA behaviour.
  - Nothing here can crash the pipeline: every public function catches.

Modules:
  embeddings  — local ONNX sentence embeddings (fastembed, 384-dim MiniLM).
                No torch, ~150MB RAM. Fixes "KB chunks have no embeddings".
  docparse    — PDF/DOCX → text via MarkItDown. Fixes "PDF uploads are
                decoded as raw UTF-8 garbage".
  pii         — Presidio PII redaction (regex fallback built-in).
  intent      — zero-shot intent/urgency classification (GLiClass if
                installed, else embedding-similarity over labels).
  entities    — GLiNER entity extraction if installed, else regex for
                order numbers / emails / phones / amounts.
  guard       — answer sanitizer: strip <think> blocks, reject empty or
                think-only answers. Pure stdlib, always available.
  structured  — Instructor-based structured extraction (optional).
  llm_router  — LiteLLM wrapper: fallback chains + per-call budget (optional).
  channels    — email (imap-tools) + telegram (aiogram) pollers, env-gated.

Env flags (all default to safe values):
  OSS_EMBEDDINGS=1    enable local embeddings (opt-in; ~150-300MB RAM — OFF by
                          default, OOM-killed the 512MB free instance)
  OSS_DOCPARSE=1      enable MarkItDown parsing of PDF/DOCX uploads
  OSS_PII=0           enable Presidio redaction before prompts/logs (off until tested)
  OSS_INTENT=0        enable local zero-shot triage (off until wired to UI)
  OSS_LITELLM=0       route LLM calls through LiteLLM fallback chain (off by default)

Verification:
  python scripts/verify_oss_stack.py   → PASS/FAIL table for every module
"""

from __future__ import annotations

import importlib.util
import os


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


def _flag(name: str, default: bool) -> bool:
    return os.environ.get(name, "1" if default else "0").strip() in ("1", "true", "yes", "on")


def availability() -> dict:
    """Report which OSS components are installed and enabled. Used by verify script."""
    return {
        "fastembed": {"installed": _has("fastembed"), "enabled": _flag("OSS_EMBEDDINGS", False)},
        "markitdown": {"installed": _has("markitdown"), "enabled": _flag("OSS_DOCPARSE", True)},
        "presidio": {
            "installed": _has("presidio_analyzer") and _has("presidio_anonymizer"),
            "enabled": _flag("OSS_PII", False),
        },
        "gliclass": {"installed": _has("gliclass"), "enabled": _flag("OSS_INTENT", False)},
        "gliner": {"installed": _has("gliner"), "enabled": _flag("OSS_INTENT", False)},
        "instructor": {"installed": _has("instructor")},
        "litellm": {"installed": _has("litellm"), "enabled": _flag("OSS_LITELLM", False)},
        "rank_bm25": {"installed": _has("rank_bm25")},
        "rapidfuzz": {"installed": _has("rapidfuzz")},
        "imap_tools": {"installed": _has("imap_tools")},
        "aiogram": {"installed": _has("aiogram")},
        # Always-available (stdlib) modules:
        "guard": {"installed": True, "enabled": True},
    }
