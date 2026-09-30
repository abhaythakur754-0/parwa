"""
Answer guard — the trust layer. Pure stdlib, ALWAYS available.

Fixes the class of production bugs where tickets were "resolved" with an
empty AI message or a leaked raw <think> block. Exported as pure functions
so any pipeline node can call them without imports of heavy deps.

Rules:
  1. Strip <think>...</think> (and unclosed <think>) blocks.
  2. If the remaining answer is empty/whitespace → invalid.
  3. If the answer is ONLY a thinking fragment (no sentences) → invalid.
  4. Confidence gate: callers may reject answers whose computed
     confidence (answer_quality) is below threshold instead of booking
     savings on garbage.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"</?(?:think|reasoning|thought)>", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"[.!?](?:\s|$)")


def strip_think(text: Optional[str]) -> str:
    """Remove complete and unclosed <think> blocks + stray tags."""
    if not text:
        return ""
    out = _THINK_RE.sub("", text)
    out = _THINK_OPEN_RE.sub("", out)
    out = _TAG_RE.sub("", out)
    return out.strip()


def is_real_answer(text: Optional[str]) -> bool:
    """True when the text contains at least one real sentence worth sending."""
    cleaned = strip_think(text)
    if not cleaned or len(cleaned) < 12:
        return False
    # A real answer has sentence structure; think-fragments often don't.
    if not _SENTENCE_RE.search(cleaned):
        return False
    # Reject answers that are only meta commentary.
    meta = cleaned.lower().strip()
    if meta.startswith(("okay,", "ok,", "hmm", "let me", "wait,")) and len(cleaned) < 60:
        return False
    return True


def answer_quality(text: Optional[str]) -> float:
    """Heuristic 0-1 quality score. Callers gate resolution on this."""
    cleaned = strip_think(text)
    if not cleaned:
        return 0.0
    score = 0.0
    if _SENTENCE_RE.search(cleaned):
        score += 0.4
    if len(cleaned) >= 60:
        score += 0.2
    if re.search(r"\d", cleaned):
        score += 0.15
    if re.search(
        r"\b(policy|refund|order|account|please|thank|days|hours|email|support)\b",
        cleaned,
        re.IGNORECASE,
    ):
        score += 0.15
    if re.search(r"\$\d|\b\d+%\b", cleaned):
        score += 0.1
    return min(1.0, score)


def sanitize(
    text: Optional[str], min_quality: float = 0.35
) -> Tuple[str, bool, float]:
    """Full gate: returns (clean_answer, is_valid, quality).

    Callers: if not is_valid → do NOT resolve the ticket; route to
    review/escalation instead. Never book savings on an invalid answer.
    """
    cleaned = strip_think(text)
    quality = answer_quality(cleaned)
    valid = is_real_answer(cleaned) and quality >= min_quality
    return cleaned, valid, quality
