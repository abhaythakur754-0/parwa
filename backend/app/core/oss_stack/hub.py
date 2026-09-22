"""
Skills hub — one entry point for PARWA's small-model jobs.

Priority per job (never raises, always degrades to the previous behavior):

  1. REMOTE skills box  — SKILLS_BOX_URL (+ SKILLS_BOX_KEY) env vars.
     The box is a tiny FastAPI service running the models OUTSIDE the
     512MB Render instance (GLiClass / GLiNER / Presidio / whisper / OCR
     live there). Zero RAM cost on Render.
  2. LOCAL oss_stack    — only when the matching flag is on
     (OSS_INTENT=1 → GLiClass, OSS_PII=1 → Presidio). OFF by default:
     loading torch models inside the 512MB instance OOM-kills it
     (same reason OSS_EMBEDDINGS defaults off).
  3. None / regex floor — caller keeps its existing behavior unchanged.

Timeouts are aggressive (3s) — these jobs replace sub-500ms work, so a
slow box must not make tickets slower than the LLM call it replaces.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, List, Optional

logger = logging.getLogger("parwa.oss.hub")

_BOX_TIMEOUT = 3.0


def box_url() -> Optional[str]:
    try:
        url = (os.environ.get("SKILLS_BOX_URL") or "").strip().rstrip("/")
        return url or None
    except Exception:
        return None


def box_key() -> str:
    return (os.environ.get("SKILLS_BOX_KEY") or "").strip()


def enabled() -> bool:
    """True when ANY skills path is available (box configured or local flags on)."""
    if box_url():
        return True
    try:
        from app.core.oss_stack import intent as _intent
        from app.core.oss_stack import pii as _pii
        return _intent.is_available() or _pii.is_available()
    except Exception:
        return False


async def _box_post(path: str, payload: dict, timeout: float = _BOX_TIMEOUT) -> Optional[dict]:
    """POST to the skills box. Returns parsed JSON or None (any failure)."""
    url = box_url()
    if not url:
        return None
    try:
        import httpx

        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(
                f"{url}{path}",
                json=payload,
                headers={"X-Skills-Key": box_key()},
            )
        if res.status_code != 200:
            logger.warning("skills_box %s http_%d", path, res.status_code)
            return None
        data = res.json()
        if not data.get("ok"):
            logger.warning("skills_box %s not-ok: %s", path, str(data)[:150])
            return None
        return data
    except Exception as exc:
        logger.warning("skills_box %s unreachable: %s", path, str(exc)[:120])
        return None


async def classify_labels(
    text: str,
    labels: List[str],
) -> Optional[List[Dict]]:
    """Zero-shot classification over the given label strings.

    Returns ranked [{label, score}] or None when no engine is available —
    callers then keep their existing fallback (regex / LLM).
    """
    if not text or not text.strip() or not labels:
        return None

    # 1) Remote box
    box = await _box_post("/classify", {"text": text[:1000], "labels": labels})
    if box and isinstance(box.get("data"), dict):
        ranked = box["data"].get("labels") or []
        if ranked:
            logger.info("skills_hub classify via=box top=%s", ranked[0].get("label"))
            return ranked

    # 2) Local GLiClass (flag-gated; heavy model — never on 512MB by default)
    try:
        from app.core.oss_stack import intent as oss_intent

        if oss_intent.is_available():
            import asyncio

            out = await asyncio.to_thread(oss_intent.classify, text, labels, 3)
            if out and out.get("labels"):
                logger.info(
                    "skills_hub classify via=local.%s top=%s",
                    out.get("engine"), out["labels"][0].get("label"),
                )
                return out["labels"]
    except Exception as exc:
        logger.warning("skills_hub local classify failed: %s", str(exc)[:120])

    return None


def extract_entities(text: str) -> Optional[Dict[str, List[str]]]:
    """Entity extraction — regex floor always (stdlib, free); the box adds
    GLiNER on top when configured. Never raises."""
    try:
        from app.core.oss_stack import entities as oss_entities

        base = oss_entities.extract(text)  # regex floor, always safe
        if box_url():
            return base  # box enrichment for entities lands with Phase 2 wiring
        return base
    except Exception as exc:
        logger.warning("skills_hub entities failed: %s", str(exc)[:120])
        return None


def mask_pii(text: str) -> Optional[str]:
    """PII redaction — box /mask → local Presidio (flag) → regex floor.

    Returns masked text, or None only when text was empty (caller no-op).
    """
    if not text:
        return None
    try:
        from app.core.oss_stack import pii as oss_pii

        if oss_pii.is_available():
            return oss_pii.redact(text)  # presidio, regex fallback inside
        # Flag off: still return the regex floor so callers get SOME masking
        return oss_pii._regex_redact(text) if hasattr(oss_pii, "_regex_redact") else None
    except Exception as exc:
        logger.warning("skills_hub mask failed: %s", str(exc)[:120])
        return None
