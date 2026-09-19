"""
Shared Email Utility Functions — Week 13 Day 2

Common helpers used across outbound email service, channel dispatcher,
and email tasks. Avoids code duplication.
"""

import asyncio
import logging
import re
from typing import Optional

logger = logging.getLogger("parwa.email_utils")


def strip_html(html: str) -> str:
    """Strip HTML tags and return plain text.

    Collapses whitespace and trims leading/trailing spaces.
    Returns empty string for falsy input.

    Args:
        html: HTML string to strip.

    Returns:
        Plain-text string.
    """
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def run_async_coro(coro) -> None:
    """Safely run an async coroutine from a synchronous context.

    If a running event loop exists (e.g. inside FastAPI/uvicorn),
    schedules the coroutine via ``asyncio.ensure_future``.
    Otherwise, creates a temporary loop with ``asyncio.run``.

    This is the canonical way to fire-and-forget async events
    (Socket.io, etc.) from sync Celery tasks or services.

    Args:
        coro: An awaitable coroutine object.
    """
    if coro is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Inside an existing async context — schedule for later
        asyncio.ensure_future(coro)
    else:
        # Standalone sync context (Celery worker, script)
        try:
            asyncio.run(coro)
        except RuntimeError:
            pass  # Loop already closing / torn down


def validate_email_address(email: str) -> bool:
    """Basic email address validation.

    Checks for the presence of '@', a domain with at least one dot,
    and overall length constraints (RFC 5321: max 254 chars).

    Args:
        email: Email address string.

    Returns:
        True if the address looks valid.
    """
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if len(email) > 254 or len(email) < 3:
        return False
    if "@" not in email or email.count("@") > 1:
        return False
    local, _, domain = email.partition("@")
    if not local or not domain:
        return False
    if "." not in domain:
        return False
    return True


def sanitize_subject(subject: str, max_length: int = 500) -> str:
    """Sanitize an email subject line.

    Strips control characters, collapses whitespace, and truncates.

    Args:
        subject: Raw subject string.
        max_length: Maximum allowed length.

    Returns:
        Sanitized subject string.
    """
    if not subject:
        return ""
    cleaned = "".join(
        c for c in str(subject) if ord(c) >= 32 or c in "\n\r\t"
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_length]


def strip_reasoning(text: str) -> str:
    """Remove model chain-of-thought (<think>...</think>) from a response.

    Reasoning models can emit their internal thinking as <think> blocks.
    Those must never reach a customer: this strips paired blocks AND an
    unclosed trailing block (model cut off mid-think), then trims the
    leftover leading whitespace. Applied before persisting AI messages
    and before customer delivery.

    Args:
        text: Raw model output (may be None/empty).

    Returns:
        Clean customer-safe text.
    """
    if not text:
        return text or ""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<think>.*\Z", "", cleaned, flags=re.DOTALL)
    return cleaned.lstrip() if cleaned != text else cleaned


# Internal workflow headers the quality node asks the model to write.
# Live bug 2026-09-18: CRP's "Write the IMPROVED response" prompt made the
# model prefix its reply with "**IMPROVED RESPONSE:**" and that marker was
# delivered to the customer verbatim.
_HEADER_WORDS = {"IMPROVED", "REVISED", "FINAL"}
_HEADER_NOUNS = {"RESPONSE", "ANSWER", "VERSION", "REPLY", "DRAFT"}
_DECORATION_RE = re.compile(r"[\*#_:`\-]")
_INLINE_HEADER_RE = re.compile(
    r"^[\*#_\s]*((?:IMPROVED|REVISED|FINAL)\s+(?:RESPONSE|ANSWER|VERSION|REPLY|DRAFT))"
    r"[\*#_\s]*:[\*#_\s]*(.*)$",
    re.IGNORECASE,
)

# 2026-09-19 live bug: the model answered the revision prompt
# conversationally — "Here's the **slightly refined** version of your
# response while preserving its strength…" — and that preamble was
# delivered to the customer. Any opening line that TALKS ABOUT the
# response instead of BEING the response is workflow chatter.
_REFINED_PREAMBLE_RE = re.compile(
    r"^\W*(?:here[\u2019']?s|here is|below is)\s+the\s+"
    r".{0,120}?\b(?:refined|revised|improved|polished)\b.{0,60}?"
    r"\b(?:version|draft|response|reply)\b",
    re.IGNORECASE,
)

# Trailing self-rating annotations, e.g. '**QUALITY: 10/10**',
# 'QUALITY SCORE: 9/10', 'Quality: 10/10' — never customer-facing.
_QUALITY_TAIL_RE = re.compile(
    r"^[\*#_\s]*(?:quality(?:\s+score)?|overall\s+quality)"
    r"[\*#_\s:]*\s*\d+\s*/\s*10[\*#_\s!.]*$",
    re.IGNORECASE,
)
_SEPARATOR_RE = re.compile(r"^\s*-{3,}\s*$")


def _is_bare_header_line(line: str) -> bool:
    """True when a line is ONLY a meta header, e.g. '**IMPROVED RESPONSE:**'
    or '## FINAL ANSWER' — decorations stripped, exactly header words left."""
    core = _DECORATION_RE.sub(" ", line)
    words = re.sub(r"\s+", " ", core).strip().upper().split()
    return (
        len(words) == 2
        and words[0] in _HEADER_WORDS
        and words[1] in _HEADER_NOUNS
    )


def strip_meta_headers(text: str) -> str:
    """Remove quality-node workflow chatter from a customer reply.

    Handles:
      - bare headers            '**IMPROVED RESPONSE:**'
      - inline headers          '**REVISED RESPONSE:* Thank you…'
      - refined preambles       "Here's the **slightly refined** version of your response…"
      - trailing self-ratings   '**QUALITY: 10/10**'
      - orphan '---' separators left behind by the above
    Applied at the revision source AND at the delivery node so no leak
    path reaches a customer.
    """
    if not text:
        return text or ""
    cleaned = text.strip()
    for _ in range(4):  # tolerate a couple of stacked header lines
        first, sep, rest = cleaned.partition("\n")
        if _is_bare_header_line(first):
            cleaned = rest.strip() if sep else ""
            continue
        # Inline form: '**REVISED RESPONSE:* Thank you…' — header words
        # at the very start of the line, then a colon, then the reply.
        m = _INLINE_HEADER_RE.match(first)
        if m:
            tail = m.group(2).strip()
            if sep:
                cleaned = (tail + "\n" + rest) if tail else rest
            else:
                cleaned = tail
            continue
        # Conversational preamble: "Here's the slightly refined version…"
        if _REFINED_PREAMBLE_RE.match(first):
            cleaned = rest.strip() if sep else ""
            continue
        break

    # ── Tail pass: trailing QUALITY self-ratings + orphan separators ──
    lines = cleaned.split("\n")
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if _QUALITY_TAIL_RE.match(last) or _is_bare_header_line(last) or _SEPARATOR_RE.match(last):
            lines.pop()
            continue
        break
    cleaned = "\n".join(lines).rstrip()

    # Collapse separator runs ('---' directly after a stripped preamble).
    cleaned = re.sub(r"\n\s*-{3,}\s*\n\s*-{3,}\s*\n", "\n\n", cleaned)
    cleaned = re.sub(r"^(?:\s*-{3,}\s*\n)+", "", cleaned)
    return cleaned.strip()
