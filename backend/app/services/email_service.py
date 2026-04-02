"""
PARWA Email Service (BC-006, C4)

Brevo email client for sending transactional emails.
- Uses Brevo REST API via httpx
- Circuit breaker pattern (BC-012)
- All emails use Jinja2 templates (BC-006 Rule 2)
- Rate: 3 per email per hour for verification/resend

NOTE: Celery async dispatch comes in Week 3 (BC-004).
Currently synchronous — will be wrapped in Celery task later.
"""

import time

import httpx
from httpx import HTTPError, TimeoutException

from backend.app.config import get_settings
from backend.app.core.email_renderer import render_email_template
from backend.app.logger import get_logger

logger = get_logger("email_service")

# Circuit breaker state
_cb_state = {
    "failures": 0,
    "last_failure": 0.0,
    "is_open": False,
    "threshold": 3,
    "reset_seconds": 60,
}

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _is_circuit_open() -> bool:
    """Check if circuit breaker is open."""
    if not _cb_state["is_open"]:
        return False
    elapsed = time.time() - _cb_state["last_failure"]
    if elapsed >= _cb_state["reset_seconds"]:
        _cb_state["is_open"] = False
        _cb_state["failures"] = 0
        logger.info("circuit_breaker_half_open")
        return False
    return True


def _record_success() -> None:
    """Reset circuit breaker on success."""
    if _cb_state["failures"] > 0:
        _cb_state["failures"] = 0
        _cb_state["is_open"] = False


def _record_failure() -> None:
    """Record failure and possibly open circuit."""
    _cb_state["failures"] += 1
    _cb_state["last_failure"] = time.time()
    if _cb_state["failures"] >= _cb_state["threshold"]:
        _cb_state["is_open"] = True
        logger.warning(
            "circuit_breaker_open",
            failures=_cb_state["failures"],
        )


def send_email(
    to: str,
    subject: str,
    html_content: str,
) -> bool:
    """Send an email via Brevo REST API.

    BC-006: All outbound emails use Brevo.
    BC-012: Circuit breaker on failures.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_content: HTML body of the email.

    Returns:
        True if sent successfully, False otherwise.
    """
    if _is_circuit_open():
        logger.error(
            "email_send_skipped",
            reason="circuit_breaker_open",
            to=to,
        )
        return False

    settings = get_settings()
    if not settings.BREVO_API_KEY:
        logger.error(
            "email_send_skipped", reason="no_api_key"
        )
        return False

    payload = {
        "sender": {
            "name": "PARWA",
            "email": settings.FROM_EMAIL,
        },
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html_content,
    }

    headers = {
        "api-key": settings.BREVO_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        resp = httpx.post(
            BREVO_API_URL,
            json=payload,
            headers=headers,
            timeout=10.0,
        )
        if resp.status_code in (200, 201):
            _record_success()
            logger.info(
                "email_sent",
                to=to,
                template=subject,
            )
            return True
        logger.error(
            "email_send_failed",
            status=resp.status_code,
            to=to,
            body=resp.text[:200],
        )
        _record_failure()
        return False
    except TimeoutException:
        logger.error(
            "email_send_timeout", to=to
        )
        _record_failure()
        return False
    except HTTPError as exc:
        logger.error(
            "email_send_error",
            to=to,
            error=str(exc),
        )
        _record_failure()
        return False


def send_verification_email(
    user_email: str,
    user_name: str,
    verification_url: str,
) -> bool:
    """Send email verification link.

    F-012: Verification email via Brevo.
    Uses Jinja2 template verification_email.html.

    Args:
        user_email: User's email address.
        user_name: User's display name.
        verification_url: Full verification URL.

    Returns:
        True if sent successfully.
    """
    html = render_email_template(
        "verification_email.html",
        {
            "user_name": user_name,
            "verification_url": verification_url,
        },
    )
    return send_email(
        to=user_email,
        subject="Verify your PARWA account",
        html_content=html,
    )


def send_password_reset_email(
    user_email: str,
    user_name: str,
    reset_url: str,
) -> bool:
    """Send password reset link.

    F-014: Password reset email via Brevo.
    Uses Jinja2 template password_reset_email.html.

    Args:
        user_email: User's email address.
        user_name: User's display name.
        reset_url: Full password reset URL.

    Returns:
        True if sent successfully.
    """
    html = render_email_template(
        "password_reset_email.html",
        {
            "user_name": user_name,
            "reset_url": reset_url,
        },
    )
    return send_email(
        to=user_email,
        subject="Reset your PARWA password",
        html_content=html,
    )


def reset_circuit_breaker() -> None:
    """Reset circuit breaker state (for testing)."""
    _cb_state["failures"] = 0
    _cb_state["last_failure"] = 0.0
    _cb_state["is_open"] = False
