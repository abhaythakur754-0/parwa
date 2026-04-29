"""
Shared Email Utility Functions — Week 13 Day 2

Common helpers used across outbound email service, channel dispatcher,
and email tasks. Avoids code duplication.
"""

import asyncio
import logging
import re

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
    cleaned = "".join(c for c in str(subject) if ord(c) >= 32 or c in "\n\r\t")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_length]
