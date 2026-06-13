"""
PARWA Email Service (BC-006, C4)

Brevo email client for sending transactional emails.
- Uses Brevo SDK (sib-api-v3-sdk) with httpx fallback
- Circuit breaker pattern (BC-012)
- All emails use Jinja2 templates (BC-006 Rule 2)
- Rate: 3 per email per hour for verification/resend

CH-03 FIX: Circuit breaker is now per-tenant. Each company_id gets
its own isolated circuit breaker state, so one tenant's email issues
cannot trip the breaker for other tenants. The breaker thresholds
are configurable via EMAIL_CB_FAILURE_THRESHOLD and EMAIL_CB_RESET_SECONDS
in config.py.

NOTE: Celery async dispatch comes in Week 3 (BC-004).
Currently synchronous — will be wrapped in Celery task later.
"""

import time
from typing import Optional

import httpx
from httpx import HTTPError, TimeoutException

try:
    import sib_api_v3_sdk
    from sib_api_v3_sdk.api import TransactionalEmailsApi
    from sib_api_v3_sdk.models import SendSmtpEmail, SendSmtpEmailTo, SendSmtpEmailSender
    from sib_api_v3_sdk.configuration import Configuration
    _BREVO_SDK_AVAILABLE = True
except ImportError:
    sib_api_v3_sdk = None
    TransactionalEmailsApi = None  # type: ignore[assignment,misc]
    SendSmtpEmail = None  # type: ignore[assignment,misc]
    SendSmtpEmailTo = None  # type: ignore[assignment,misc]
    SendSmtpEmailSender = None  # type: ignore[assignment,misc]
    Configuration = None  # type: ignore[assignment,misc]
    _BREVO_SDK_AVAILABLE = False

from app.config import get_settings
from app.core.email_renderer import render_email_template
from app.logger import get_logger

logger = get_logger("email_service")

# CH-03 FIX: Per-tenant circuit breaker state
# Each tenant (company_id) gets its own isolated breaker, so one
# tenant's email failures don't trip the breaker for everyone.

import threading


class TenantCircuitBreaker:
    """Per-tenant circuit breaker for email sending.

    CH-03 FIX: Instead of a single global _cb_state dict shared by
    all tenants, each company_id gets its own isolated circuit breaker.
    This prevents the "noisy neighbor" problem where one tenant's
    email failures (e.g., invalid Brevo config, rate-limited account)
    would block email delivery for ALL other tenants.

    Thread-safe: uses a lock for concurrent access.

    The failure threshold and reset time are configurable via
    EMAIL_CB_FAILURE_THRESHOLD and EMAIL_CB_RESET_SECONDS in config.py.
    """

    def __init__(self):
        self._tenants: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _get_tenant_state(self, company_id: str) -> dict:
        """Get or create circuit breaker state for a tenant.

        Uses hardcoded defaults (threshold=3, reset_seconds=60) when
        settings are unavailable (e.g., test environments without full
        env config). This prevents get_settings() validation errors
        from crashing the circuit breaker in isolated unit tests.
        """
        if company_id not in self._tenants:
            try:
                settings = get_settings()
                threshold = settings.EMAIL_CB_FAILURE_THRESHOLD
                reset_seconds = settings.EMAIL_CB_RESET_SECONDS
            except Exception:
                threshold = 3
                reset_seconds = 60
            self._tenants[company_id] = {
                "failures": 0,
                "last_failure": 0.0,
                "is_open": False,
                "threshold": threshold,
                "reset_seconds": reset_seconds,
            }
        return self._tenants[company_id]

    def is_open(self, company_id: str) -> bool:
        """Check if circuit breaker is open for a specific tenant."""
        with self._lock:
            state = self._get_tenant_state(company_id)
            if not state["is_open"]:
                return False
            elapsed = time.time() - state["last_failure"]
            if elapsed >= state["reset_seconds"]:
                state["is_open"] = False
                state["failures"] = 0
                logger.info("circuit_breaker_half_open", company_id=company_id)
                return False
            return True

    def record_success(self, company_id: str) -> None:
        """Reset circuit breaker on success for a specific tenant."""
        with self._lock:
            state = self._get_tenant_state(company_id)
            if state["failures"] > 0:
                state["failures"] = 0
                state["is_open"] = False

    def record_failure(self, company_id: str) -> None:
        """Record failure and possibly open circuit for a specific tenant."""
        with self._lock:
            state = self._get_tenant_state(company_id)
            state["failures"] += 1
            state["last_failure"] = time.time()
            if state["failures"] >= state["threshold"]:
                state["is_open"] = True
                logger.warning(
                    "circuit_breaker_open",
                    company_id=company_id,
                    failures=state["failures"],
                )

    def reset(self, company_id: str = None) -> None:
        """Reset circuit breaker state (for testing).

        Args:
            company_id: If provided, reset only that tenant's breaker.
                If None, reset all tenants.
        """
        with self._lock:
            if company_id:
                if company_id in self._tenants:
                    self._tenants[company_id] = {
                        "failures": 0,
                        "last_failure": 0.0,
                        "is_open": False,
                        "threshold": self._tenants[company_id]["threshold"],
                        "reset_seconds": self._tenants[company_id]["reset_seconds"],
                    }
            else:
                self._tenants.clear()

    def get_tenant_state(self, company_id: str) -> dict:
        """Get a copy of tenant state (for testing/monitoring)."""
        with self._lock:
            state = self._get_tenant_state(company_id)
            return dict(state)

    @property
    def tenant_count(self) -> int:
        """Number of tenants with breaker state."""
        with self._lock:
            return len(self._tenants)


# Global per-tenant circuit breaker instance
_cb = TenantCircuitBreaker()

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

# Lazy SDK client (BC-008)
_brevo_api_client = None


def _get_brevo_client():
    """Lazily initialise and return the Brevo SDK client.

    Returns the cached client or creates a new one on first call.
    Returns None if the SDK is not installed or initialisation fails (BC-008).
    """
    global _brevo_api_client
    if not _BREVO_SDK_AVAILABLE:
        return None
    if _brevo_api_client is not None:
        return _brevo_api_client
    try:
        settings = get_settings()
        configuration = Configuration(api_key={"api-key": settings.BREVO_API_KEY})
        api_client = sib_api_v3_sdk.ApiClient(configuration)
        _brevo_api_client = TransactionalEmailsApi(api_client)
        return _brevo_api_client
    except Exception as exc:  # pragma: no cover — defensive (BC-008)
        logger.warning("brevo_sdk_init_failed", error=str(exc))
        return None


def _is_circuit_open(company_id: str) -> bool:
    """Check if circuit breaker is open for a specific tenant.

    CH-03 FIX: Now takes company_id to check the per-tenant breaker.
    Falls back to the global breaker if company_id is not provided.
    """
    return _cb.is_open(company_id)


def _record_success(company_id: str) -> None:
    """Reset circuit breaker on success for a specific tenant.

    CH-03 FIX: Now takes company_id to reset the per-tenant breaker.
    """
    _cb.record_success(company_id)


def _record_failure(company_id: str) -> None:
    """Record failure and possibly open circuit for a specific tenant.

    CH-03 FIX: Now takes company_id to record against the per-tenant breaker.
    """
    _cb.record_failure(company_id)


def send_email(
    to: str,
    subject: str,
    html_content: str,
    reply_to_message_id: Optional[str] = None,
    references: Optional[str] = None,
    company_id: Optional[str] = None,
) -> bool:
    """Send an email via Brevo REST API.

    BC-006: All outbound emails use Brevo.
    BC-012: Circuit breaker on failures (now per-tenant, CH-03).

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_content: HTML body of the email.
        reply_to_message_id: Message-ID of the email being replied to.
            Sets the In-Reply-To header for proper email threading.
        references: The References header chain (space-separated Message-IDs).
            Used for multi-hop email threading.
        company_id: Optional tenant ID for per-tenant circuit breaker (CH-03).

    Returns:
        True if sent successfully, False otherwise.
    """
    return _do_send_email(
        to=to,
        subject=subject,
        html_content=html_content,
        reply_to_message_id=reply_to_message_id,
        references=references,
        company_id=company_id,
    ).get("success", False)


def send_email_tracked(
    to: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    reply_to_message_id: Optional[str] = None,
    references: Optional[str] = None,
    attachments: Optional[list] = None,
    company_id: Optional[str] = None,
) -> dict:
    """Send an email via Brevo with tracking details.

    Extended version of send_email() that returns Brevo message_id,
    supports plain-text content, and attachments.

    CH-03 FIX: Now accepts company_id for per-tenant circuit breaker.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_content: HTML body of the email.
        text_content: Optional plain-text body (accessibility).
        reply_to_message_id: Message-ID being replied to.
        references: References header chain.
        attachments: List of attachment dicts, each with:
            - name: filename (str)
            - content: base64-encoded content (str)
            - content_type: MIME type, e.g. "application/pdf" (str)
        company_id: Optional tenant ID for per-tenant circuit breaker (CH-03).

    Returns:
        Dict with keys:
        - success: bool
        - message_id: str | None (Brevo message-id)
        - error: str | None
    """
    return _do_send_email(
        to=to,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        reply_to_message_id=reply_to_message_id,
        references=references,
        attachments=attachments,
        company_id=company_id,
    )


def _do_send_email(
    to: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    reply_to_message_id: Optional[str] = None,
    references: Optional[str] = None,
    attachments: Optional[list] = None,
    company_id: Optional[str] = None,
) -> dict:
    """Internal: send email via Brevo, return tracking dict.

    CH-03 FIX: Now accepts company_id for per-tenant circuit breaker.
    Falls back to "__global__" if company_id is not provided (backwards compat).

    Returns:
        {"success": bool, "message_id": str|None, "error": str|None}
    """
    _result = {"success": False, "message_id": None, "error": None}
    _tenant = company_id or "__global__"

    if _is_circuit_open(_tenant):
        logger.error(
            "email_send_skipped",
            reason="circuit_breaker_open",
            to=to,
        )
        _result["error"] = "circuit_breaker_open"
        return _result

    settings = get_settings()
    if not settings.BREVO_API_KEY:
        logger.error(
            "email_send_skipped", reason="no_api_key"
        )
        _result["error"] = "no_api_key"
        return _result

    # Build email headers for threading
    email_headers = {}
    if reply_to_message_id:
        email_headers["In-Reply-To"] = reply_to_message_id
    if references:
        email_headers["References"] = references
    # If only In-Reply-To is set without References, copy it
    if reply_to_message_id and not references:
        email_headers["References"] = reply_to_message_id

    # Build attachment list for Brevo API
    brevo_attachments = None
    if attachments:
        brevo_attachments = []
        for att in attachments[:10]:  # Max 10 attachments per email
            if not isinstance(att, dict):
                continue
            name = att.get("name", "attachment")
            content = att.get("content", "")
            brevo_attachments.append({
                "name": name,
                "content": content,
            })

    # --- SDK path (preferred) ---
    if _BREVO_SDK_AVAILABLE:
        try:
            client = _get_brevo_client()
            if client:
                send_email_obj = SendSmtpEmail(
                    sender=SendSmtpEmailSender(name="PARWA", email=settings.FROM_EMAIL),
                    to=[SendSmtpEmailTo(email=to)],
                    subject=subject,
                    html_content=html_content,
                    headers=email_headers if email_headers else None,
                )
                # SDK supports text_content and attachment
                if text_content:
                    send_email_obj.text_content = text_content  # type: ignore[attr-defined]
                if brevo_attachments:
                    send_email_obj.attachment = brevo_attachments  # type: ignore[attr-defined]

                result = client.send_transac_email(send_email_obj)
                if result and hasattr(result, 'message_id'):
                    _record_success(_tenant)
                    logger.info(
                        "email_sent_sdk",
                        to=to,
                        message_id=result.message_id,
                        reply_to=reply_to_message_id,
                    )
                    return {
                        "success": True,
                        "message_id": result.message_id,
                        "error": None,
                    }
        except Exception as exc:  # BC-008
            logger.warning(
                "email_sdk_failed",
                error=str(exc),
                to=to,
            )
            # Fall through to httpx fallback

    # --- httpx fallback ---
    payload = {
        "sender": {
            "name": "PARWA",
            "email": settings.FROM_EMAIL,
        },
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html_content,
    }
    # Add plain-text content
    if text_content:
        payload["textContent"] = text_content
    # Add threading headers
    if email_headers:
        payload["headers"] = email_headers
    # Add attachments
    if brevo_attachments:
        payload["attachment"] = brevo_attachments

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
            _record_success(_tenant)
            # Extract Brevo message_id from response
            brevo_msg_id = None
            try:
                body = resp.json()
                brevo_msg_id = body.get("messageId")
            except Exception:
                pass
            logger.info(
                "email_sent",
                to=to,
                template=subject,
                brevo_message_id=brevo_msg_id,
            )
            return {
                "success": True,
                "message_id": brevo_msg_id,
                "error": None,
            }
        logger.error(
            "email_send_failed",
            status=resp.status_code,
            to=to,
            body=resp.text[:200],
        )
        _record_failure(_tenant)
        _result["error"] = f"brevo_{resp.status_code}"
        return _result
    except TimeoutException:
        logger.error(
            "email_send_timeout", to=to
        )
        _record_failure(_tenant)
        _result["error"] = "timeout"
        return _result
    except HTTPError as exc:
        logger.error(
            "email_send_error",
            to=to,
            error=str(exc),
        )
        _record_failure(_tenant)
        _result["error"] = str(exc)[:200]
        return _result


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


def send_welcome_email(
    user_email: str,
    user_name: str,
    dashboard_url: str,
) -> bool:
    """Send welcome email to a new user.

    Uses Jinja2 template welcome_email.html.

    Args:
        user_email: User's email address.
        user_name: User's display name.
        dashboard_url: URL to the user's dashboard.

    Returns:
        True if sent successfully.
    """
    html = render_email_template(
        "welcome_email.html",
        {
            "user_name": user_name,
            "dashboard_url": dashboard_url,
        },
    )
    return send_email(
        to=user_email,
        subject="Welcome to PARWA AI Workforce",
        html_content=html,
    )


def send_payment_confirmation_email(
    user_email: str,
    user_name: str,
    plan_name: str,
    amount: str,
    dashboard_url: str,
) -> bool:
    """Send payment confirmation email after successful subscription.

    Args:
        user_email: User's email address.
        user_name: User's display name.
        plan_name: Name of the subscribed plan.
        amount: Formatted payment amount.
        dashboard_url: URL to the user's dashboard.

    Returns:
        True if sent successfully.
    """
    html = render_email_template(
        "payment_confirmation.html",
        {
            "user_name": user_name,
            "plan_name": plan_name,
            "amount": amount,
            "dashboard_url": dashboard_url,
        },
    )
    return send_email(
        to=user_email,
        subject="Payment Confirmed - PARWA Subscription",
        html_content=html,
    )


def send_payment_failed_email(
    user_email: str,
    user_name: str,
    amount: str,
    reason: str = "Your card was declined",
) -> bool:
    """Send payment failure notification.

    Args:
        user_email: User's email address.
        user_name: User's display name.
        amount: Formatted payment amount.
        reason: Human-readable failure reason.

    Returns:
        True if sent successfully.
    """
    html = render_email_template(
        "payment_failed.html",
        {
            "user_name": user_name,
            "amount": amount,
            "reason": reason,
        },
    )
    return send_email(
        to=user_email,
        subject="Payment Failed - PARWA Subscription",
        html_content=html,
    )


def send_subscription_canceled_email(
    user_email: str,
    user_name: str,
    plan_name: str,
    effective_date: str,
) -> bool:
    """Send subscription cancellation confirmation.

    Args:
        user_email: User's email address.
        user_name: User's display name.
        plan_name: Name of the canceled plan.
        effective_date: Date when cancellation takes effect.

    Returns:
        True if sent successfully.
    """
    html = render_email_template(
        "subscription_canceled.html",
        {
            "user_name": user_name,
            "plan_name": plan_name,
            "effective_date": effective_date,
        },
    )
    return send_email(
        to=user_email,
        subject="Subscription Canceled - PARWA",
        html_content=html,
    )


def get_circuit_breaker() -> TenantCircuitBreaker:
    """Get the per-tenant circuit breaker instance (for testing/monitoring)."""
    return _cb


def reset_circuit_breaker(company_id: str = None) -> None:
    """Reset circuit breaker state (for testing).

    CH-03 FIX: Now supports resetting a specific tenant's breaker
    or all tenants (if company_id is None).

    Args:
        company_id: If provided, reset only that tenant's breaker.
            If None, reset all tenants.
    """
    _cb.reset(company_id)
