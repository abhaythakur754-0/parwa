"""
PII redaction — Microsoft Presidio (optional) with a strong stdlib fallback.

Purpose: before ticket text goes to an LLM, a log line, or an analytics
table, strip card numbers / emails / phones / SSN-Aadhaar-like IDs.
Default OFF in production until enabled (OSS_PII=1) — regex fallback is
always importable and dependency-free.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import re
from typing import List, Tuple

logger = logging.getLogger("parwa.oss.pii")

# (name, compiled_regex, replacement) — fallback engine
_FALLBACK_RULES: List[Tuple[str, re.Pattern, str]] = [
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "<CREDIT_CARD>"),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b"), "<EMAIL>"),
    ("PHONE", re.compile(r"(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b"), "<PHONE>"),
    ("AADHAAR", re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b"), "<GOVT_ID>"),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "<GOVT_ID>"),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"), "<IBAN>"),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<IP>"),
]

_analyzer = None
_tried = False


def is_available() -> bool:
    try:
        ok = (
            importlib.util.find_spec("presidio_analyzer") is not None
            and importlib.util.find_spec("presidio_anonymizer") is not None
        )
        return ok and os.environ.get("OSS_PII", "0").strip() in ("1", "true", "yes", "on")
    except Exception:
        return False


def _get_analyzer():
    global _analyzer, _tried
    if _tried:
        return _analyzer
    _tried = True
    try:
        from presidio_analyzer import AnalyzerEngine

        _analyzer = AnalyzerEngine()
        logger.info("oss_pii: presidio analyzer ready")
    except Exception as exc:
        logger.warning("oss_pii: presidio unavailable (%s) — regex fallback active", str(exc)[:120])
        _analyzer = None
    return _analyzer


def _regex_redact(text: str) -> str:
    out = text
    for _name, pattern, repl in _FALLBACK_RULES:
        out = pattern.sub(repl, out)
    return out


def redact(text: str, language: str = "en") -> str:
    """Redact PII. Uses Presidio when enabled+installed, else regex rules.
    Never raises."""
    if not text:
        return text or ""
    if is_available():
        try:
            analyzer = _get_analyzer()
            if analyzer is not None:
                results = analyzer.analyze(text=text, language=language)
                # Replace from end to keep offsets valid
                out = text
                for r in sorted(results, key=lambda x: x.start, reverse=True):
                    out = out[: r.start] + f"<{r.entity_type}>" + out[r.end :]
                return out
        except Exception as exc:
            logger.warning("oss_pii presidio failed: %s — regex fallback", str(exc)[:150])
    try:
        return _regex_redact(text)
    except Exception:
        return text
