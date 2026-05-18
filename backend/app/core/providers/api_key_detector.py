"""
PARWA AI — API Key Auto-Detection

Examines an API key string and attempts to determine which provider it belongs
to based on known prefix, length, and regex patterns.  Returns a confidence
score so the caller can decide whether to accept the detection.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .base import ProviderCategory


# ---------------------------------------------------------------------------
# Provider key patterns
# ---------------------------------------------------------------------------

PROVIDER_KEY_PATTERNS: Dict[str, Dict[str, Any]] = {
    # ── E-mail ───────────────────────────────────────────────────────────
    "brevo": {
        "prefix": ["xkeysib-"],
        "length": None,
        "regex": r"^xkeysib-[a-zA-Z0-9]+$",
        "category": ProviderCategory.EMAIL,
    },
    "sendgrid": {
        "prefix": ["SG."],
        "length": None,
        "regex": r"^SG\.[a-zA-Z0-9._-]+$",
        "category": ProviderCategory.EMAIL,
    },
    "aws_ses": {
        "prefix": ["AKIA"],
        "length": 20,
        "regex": r"^AKIA[A-Z0-9]{16}$",
        "category": ProviderCategory.EMAIL,
    },
    "mailgun": {
        "prefix": ["key-"],
        "length": None,
        "regex": r"^key-[a-zA-Z0-9]+$",
        "category": ProviderCategory.EMAIL,
    },
    "postmark": {
        "prefix": [],
        "length": None,
        "regex": r"^[a-f0-9\-]{36}$",
        "category": ProviderCategory.EMAIL,
    },
    # ── SMS ──────────────────────────────────────────────────────────────
    "twilio": {
        "prefix": ["AC"],
        "length": 34,
        "regex": r"^AC[a-f0-9]{32}$",
        "category": ProviderCategory.SMS,
    },
    "vonage": {
        "prefix": [],
        "length": None,
        "regex": r"^[a-f0-9]{32}$",
        "category": ProviderCategory.SMS,
    },
    "messagebird": {
        "prefix": [],
        "length": None,
        "regex": r"^[a-zA-Z0-9]{25}$",
        "category": ProviderCategory.SMS,
    },
    "aws_sns": {
        "prefix": ["AKIA"],
        "length": 20,
        "regex": r"^AKIA[A-Z0-9]{16}$",
        "category": ProviderCategory.SMS,
    },
    # ── Payment ──────────────────────────────────────────────────────────
    "paddle": {
        "prefix": ["pdl_"],
        "length": None,
        "regex": r"^pdl_[a-zA-Z0-9_]+$",
        "category": ProviderCategory.PAYMENT,
    },
    "stripe": {
        "prefix": ["sk_live_", "sk_test_"],
        "length": None,
        "regex": r"^sk_(live|test)_[a-zA-Z0-9]+$",
        "category": ProviderCategory.PAYMENT,
    },
    "razorpay": {
        "prefix": ["rzp_live_", "rzp_test_"],
        "length": None,
        "regex": r"^rzp_(live|test)_[a-zA-Z0-9]+$",
        "category": ProviderCategory.PAYMENT,
    },
}


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class ApiKeyDetector:
    """Stateless utility that matches an API key against known patterns."""

    @staticmethod
    def detect(api_key: str) -> Dict[str, Any]:
        """Auto-detect the provider from an API key string.

        Returns:
            A dict with keys:
                - ``provider_type``: best-guess provider key (or ``"unknown"``)
                - ``category``: :class:`ProviderCategory` value (or ``None``)
                - ``confidence``: float 0–1 indicating match certainty
                - ``matches``: list of all provider types that matched

        The confidence heuristic works as follows:

        * **Prefix match + regex + length** → 1.0
        * **Prefix match + regex** → 0.95
        * **Regex + length** → 0.85
        * **Regex only** → 0.7
        * **Prefix only** → 0.5
        * **Length only** → 0.2
        * No match → 0.0
        """
        if not api_key or not isinstance(api_key, str):
            return {
                "provider_type": "unknown",
                "category": None,
                "confidence": 0.0,
                "matches": [],
            }

        api_key = api_key.strip()
        candidates: List[Dict[str, Any]] = []

        for provider_type, pattern in PROVIDER_KEY_PATTERNS.items():
            prefix_match = any(api_key.startswith(p) for p in pattern["prefix"])
            regex_match = bool(re.match(pattern["regex"], api_key)) if pattern.get("regex") else False
            length_match = len(api_key) == pattern["length"] if pattern.get("length") else False

            # Compute confidence score ------------------------------------
            score = 0.0
            if prefix_match and regex_match and length_match:
                score = 1.0
            elif prefix_match and regex_match:
                score = 0.95
            elif regex_match and length_match:
                score = 0.85
            elif regex_match:
                score = 0.7
            elif prefix_match:
                score = 0.5
            elif length_match:
                score = 0.2

            if score > 0:
                candidates.append(
                    {
                        "provider_type": provider_type,
                        "category": pattern["category"],
                        "confidence": score,
                    }
                )

        if not candidates:
            return {
                "provider_type": "unknown",
                "category": None,
                "confidence": 0.0,
                "matches": [],
            }

        # Sort by confidence descending; break ties by specificity (prefix
        # matches are more specific than length-only matches).
        candidates.sort(key=lambda c: c["confidence"], reverse=True)
        best = candidates[0]

        # If the top two candidates have the same confidence and share the
        # same prefix (e.g. aws_ses vs aws_sns both match "AKIA…"), we flag
        # ambiguity but still return the first alphabetical match.
        if len(candidates) > 1 and candidates[0]["confidence"] == candidates[1]["confidence"]:
            best["confidence"] = max(best["confidence"] - 0.05, 0.0)

        return {
            "provider_type": best["provider_type"],
            "category": best["category"].value if best["category"] else None,
            "confidence": best["confidence"],
            "matches": [c["provider_type"] for c in candidates],
        }

    @staticmethod
    def detect_category(api_key: str) -> Optional[str]:
        """Convenience wrapper — returns just the detected category string."""
        result = ApiKeyDetector.detect(api_key)
        return result["category"]
