"""POST /entities — GLiNER zero-shot entity extraction.

Request:  {"text": "...", "labels": [...optional...], "threshold": 0.4}
Response data: {"entities": [{"text","label","score","start","end"}], "model": "..."}
"""
from __future__ import annotations

import logging
import threading
from typing import List, Optional

from core import config
from core.registry import registry

log = logging.getLogger("skills.entities")
_infer_lock = threading.Lock()

DEFAULT_LABELS = [
    "order number", "order id", "email", "person name", "client name",
    "amount of money", "price", "phone number", "date", "address",
    "product name", "invoice number", "tracking number", "credit card",
    "iban", "url",
]


def _load():
    from gliner import GLiNER

    return GLiNER.from_pretrained(config.GLINER_MODEL)


registry.register("entities", _load)


def extract(text: str, labels: Optional[List[str]] = None,
            threshold: float = 0.4) -> dict:
    text = (text or "")[: config.MAX_TEXT_CHARS]
    if not text.strip():
        raise ValueError("text is empty")

    model = registry.get("entities")
    use_labels = [l.lower() for l in (labels or DEFAULT_LABELS)]
    with _infer_lock:
        raw = model.predict_entities(text, use_labels, threshold=float(threshold))

    return {
        "entities": [
            {
                "text": e.get("text", ""),
                "label": e.get("label", ""),
                "score": round(float(e.get("score", 0)), 4),
                "start": int(e.get("start", 0)),
                "end": int(e.get("end", 0)),
            }
            for e in raw or []
        ],
        "model": config.GLINER_MODEL,
    }
