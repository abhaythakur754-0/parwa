"""
Zero-shot intent / urgency classification — GLiClass if installed, else
local embedding similarity over label descriptions (fastembed).

Replaces: one paid LLM call per ticket in triage. Runs on CPU in
milliseconds at zero marginal cost. Default OFF (OSS_INTENT=0) until the
triage node is wired to consume it — importing and calling is safe today.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import re
from typing import Dict, List, Optional

logger = logging.getLogger("parwa.oss.intent")

DEFAULT_LABELS = [
    "refund_request",
    "order_status",
    "billing_issue",
    "technical_bug",
    "account_access",
    "product_question",
    "complaint",
    "cancellation",
    "shipping_issue",
    "general_inquiry",
]

URGENCY_LABELS = ["urgent", "normal", "low"]
_URGENCY_CUES = re.compile(
    r"\b(asap|immediately|urgent|emergency|angry|furious|cancel|lawyer|legal|escalate|unacceptable)\b",
    re.IGNORECASE,
)

_gliclass_model = None


def is_available() -> bool:
    try:
        return os.environ.get("OSS_INTENT", "0").strip() in ("1", "true", "yes", "on")
    except Exception:
        return False


def _try_gliclass(text: str, labels: List[str]) -> Optional[List[Dict]]:
    """GLiClass path (torch). Only attempted when installed + enabled."""
    global _gliclass_model
    if importlib.util.find_spec("gliclass") is None:
        return None
    try:
        if _gliclass_model is None:
            import gliclass  # type: ignore

            _gliclass_model = gliclass.ZeroShotClassificationPipeline(
                model_name_or_path="knowledgator/gliclass-base-0"
            )
        results = _gliclass_model(text, labels)
        return [
            {"label": r["label"], "score": float(r["score"])} for r in results[: len(labels)]
        ]
    except Exception as exc:
        logger.warning("oss_intent gliclass failed: %s — embedding fallback", str(exc)[:150])
        return None


def _embedding_path(text: str, labels: List[str], top_k: int) -> Optional[List[Dict]]:
    """Embedding-similarity zero-shot: embed label descriptions + text,
    rank by cosine. Decent quality, no torch needed."""
    try:
        from app.core.oss_stack import embeddings as emb

        if not emb.is_available():
            return None
        label_prompts = {
            lbl: f"Customer support ticket about: {lbl.replace('_', ' ')}" for lbl in labels
        }
        q = emb.embed(text)
        if q is None:
            return None
        scored = []
        for lbl, prompt in label_prompts.items():
            v = emb.embed(prompt)
            if v is None:
                continue
            scored.append({"label": lbl, "score": emb.cosine(q, v)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
    except Exception as exc:
        logger.warning("oss_intent embedding path failed: %s", str(exc)[:150])
        return None


def classify(
    text: str,
    labels: Optional[List[str]] = None,
    top_k: int = 3,
) -> Dict:
    """Classify ticket text. Returns:
    {labels: [{label, score}], urgency: 'urgent'|'normal'|'low', engine: str}
    Never raises; on total failure returns empty labels with engine='none'.
    """
    labels = labels or DEFAULT_LABELS
    out = {"labels": [], "urgency": "normal", "engine": "none"}
    if not text or not text.strip():
        return out

    engine = "none"
    ranked = _try_gliclass(text, labels) if is_available() else None
    if ranked:
        engine = "gliclass"
    else:
        ranked = _embedding_path(text, labels, top_k)
        if ranked:
            engine = "embeddings"
    out["labels"] = ranked
    out["engine"] = engine

    # Urgency: cheap rule layer (beats a model for this in v1)
    if _URGENCY_CUES.search(text or ""):
        out["urgency"] = "urgent"
    return out
