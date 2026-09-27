"""POST /classify — GLiClass zero-shot intent classification.

Replaces one paid LLM call per ticket. Request:
  {"text": "...", "labels": ["order status", "refund", ...],
   "multilabel": false, "threshold": 0.0}
Response data: {"labels": [{"label": "...", "score": 0.87}, ...], "model": "..."}
"""
from __future__ import annotations

import logging
import threading
from typing import List

from core import config
from core.registry import registry

log = logging.getLogger("skills.classify")
_infer_lock = threading.Lock()


def _load():
    import torch  # noqa: F401  (ensures torch present before gliclass)
    from gliclass import GLiClassModel, ZeroShotClassificationPipeline
    from transformers import AutoTokenizer

    model = GLiClassModel.from_pretrained(config.GLICLASS_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(config.GLICLASS_MODEL)
    # single-label = softmax over labels + full ranked list — matches the
    # score>=0.5 threshold Parwa's hub applies. (multi-label needs a 2nd
    # pipeline = 2x RAM; not worth it on a 4GB box.)
    return ZeroShotClassificationPipeline(
        model, tokenizer, classification_type="single-label", device="cpu"
    )


registry.register("classify", _load)


def _flatten(results) -> list:
    """Normalize pipeline output to [{label, score}]."""
    if results and isinstance(results[0], list):
        results = results[0]
    return [r for r in results if isinstance(r, dict)]


def classify(text: str, labels: List[str], multilabel: bool = False,
             threshold: float = 0.0) -> dict:
    text = (text or "")[: config.MAX_TEXT_CHARS].strip()
    if not text:
        raise ValueError("text is empty")
    if not labels or not isinstance(labels, list):
        raise ValueError("labels must be a non-empty list")

    model = registry.get("classify")
    if model is None:  # defensive: should not happen post-registry-fix
        raise RuntimeError("classify model unavailable — retry shortly")
    with _infer_lock:
        results = model(text, [str(l) for l in labels])

    ranked = sorted(_flatten(results), key=lambda r: float(r.get("score", 0)), reverse=True)
    if threshold and threshold > 0:
        ranked = [r for r in ranked if float(r.get("score", 0)) >= threshold]
    return {
        "labels": [
            {"label": str(r.get("label")), "score": round(float(r.get("score", 0)), 4)}
            for r in ranked
        ],
        "model": config.GLICLASS_MODEL,
    }
