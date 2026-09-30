"""
Entity extraction — GLiNER (torch, optional) else stdlib regex.

Pulls structured values from raw ticket text so variants can call tools
with clean inputs: order numbers, emails, phones, money amounts, dates.
GLiNER catches open-domain entities when installed; the regex layer always
runs as the floor.
"""

from __future__ import annotations

import importlib.util
import logging
import re
from typing import Dict, List

logger = logging.getLogger("parwa.oss.entities")

_ORDER_RE = re.compile(
    r"\b(?:order|booking|ticket|invoice|ref(?:erence)?)\s*(?:#|no\.?|number|id)?\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{3,20})\b",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(r"(?:(?:\$|₹|€|£)\s?\d[\d,]*(?:\.\d{1,2})?)|(?:\b\d[\d,]*(?:\.\d{1,2})?\s?(?:usd|inr|rs\.?|rupees|dollars|euros?)\b)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b")
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,?\s+\d{4})?)\b",
    re.IGNORECASE,
)

_gliner_model = None


def _try_gliner(text: str) -> Dict[str, List[str]]:
    if importlib.util.find_spec("gliner") is None:
        return {}
    global _gliner_model
    try:
        if _gliner_model is None:
            from gliner import GLiNER  # type: ignore

            _gliner_model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
        labels = ["order number", "money amount", "person", "organization", "date", "product"]
        entities = _gliner_model.predict_entities(text, labels, threshold=0.5)
        out: Dict[str, List[str]] = {}
        for e in entities:
            out.setdefault(e["label"], []).append(e["text"])
        return out
    except Exception as exc:
        logger.warning("oss_entities gliner failed: %s — regex only", str(exc)[:150])
        return {}


def extract(text: str) -> Dict[str, List[str]]:
    """Extract entities. Regex floor always runs; GLiNER adds on top.
    Never raises."""
    result: Dict[str, List[str]] = {
        "order_numbers": [],
        "amounts": [],
        "emails": [],
        "phones": [],
        "dates": [],
    }
    if not text:
        return result
    try:
        if _ORDER_RE:
            seen = set()
            for m in _ORDER_RE.finditer(text):
                v = m.group(1)
                if v.upper() not in seen:
                    seen.add(v.upper())
                    result["order_numbers"].append(v)
        result["amounts"] = [m.group(0) for m in _MONEY_RE.finditer(text)][:5]
        result["emails"] = [m.group(0) for m in _EMAIL_RE.finditer(text)][:5]
        result["phones"] = [m.group(0) for m in _PHONE_RE.finditer(text)][:5]
        result["dates"] = [m.group(0) for m in _DATE_RE.finditer(text)][:5]
    except Exception as exc:
        logger.warning("oss_entities regex failed: %s", str(exc)[:150])

    try:
        gl = _try_gliner(text)
        for lbl, values in gl.items():
            key = {
                "order number": "order_numbers",
                "money amount": "amounts",
                "date": "dates",
                "person": "people",
                "organization": "organizations",
                "product": "products",
            }.get(lbl)
            if key:
                merged = list(dict.fromkeys(result.get(key, []) + values))
                result[key] = merged[:8]
    except Exception:
        pass
    return result
