"""Regex PII floor — always available, zero dependencies.

Used when Presidio+spaCy cannot load. Same spirit as Parwa's node_4
`_PII_RE` floor so masking output stays predictable.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("EMAIL_ADDRESS", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("PHONE_NUMBER", re.compile(r"\b(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{3}[\s.-]?\d{3}[\s.-]?\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")),
    ("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
]


def redact(text: str, entities: List[str] | None = None) -> Tuple[str, List[Dict]]:
    """Return (masked_text, found_list). found: [{label, text}] without spans."""
    masked = text
    found: List[Dict] = []
    wanted = set(entities or [label for label, _ in _PATTERNS])
    for label, pattern in _PATTERNS:
        if label not in wanted:
            continue
        matches = pattern.findall(masked)
        for m in matches:
            fragment = m if isinstance(m, str) else (m[0] if m else "")
            if fragment:
                found.append({"label": label, "text": fragment})
        masked = pattern.sub(f"[REDACTED_{label}]", masked)
    return masked, found
