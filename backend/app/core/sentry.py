"""
PARWA Sentry Error Monitoring Integration (Phase 6)

Initializes Sentry SDK on app startup when SENTRY_DSN is configured.
Provides:
- Automatic unhandled exception capture
- Tenant context (company_id) on every Sentry event
- Request correlation ID on every Sentry event
- PII scrubbing (email addresses, phone numbers) for GDPR compliance
- Environment-aware sample rates (higher in dev, lower in production)
- Health check reporting for Sentry status
- Wrapper for sentry_sdk.capture_exception with context

BC-001: company_id first — tenant context added to all events.
BC-008: Never crash — Sentry init failure is caught and logged.
BC-012: UTC timestamps — all timestamps in ISO-8601 UTC.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.logger import get_logger

logger = get_logger("sentry")

# Module-level flag tracking initialization state
_sentry_initialized: bool = False


def _get_settings():
    """Lazy import settings to avoid circular imports."""
    from app.config import get_settings
    return get_settings()


def _is_dev_environment(environment: str) -> bool:
    """Check if the environment is a development-like environment."""
    return environment in ("development", "test")


def _get_sample_rates(environment: str) -> Dict[str, float]:
    """Get sample rates based on environment.

    Production: lower rates to reduce cost/noise.
    Dev/Test: full rates for better visibility during development.
    """
    if _is_dev_environment(environment):
        return {
            "traces_sample_rate": 1.0,
            "profiles_sample_rate": 1.0,
        }
    return {
        "traces_sample_rate": 0.1,
        "profiles_sample_rate": 0.1,
    }


# ── PII Scrubbing ───────────────────────────────────────────────

# Email regex: matches user@domain.tld patterns
_EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE,
)

# Phone number regex: matches various international formats
# E.164, dashes, dots, spaces, parentheses
_PHONE_PATTERN = re.compile(
    r'(?:\+?\d{1,3}[\s.\-]?)?'       # country code
    r'(?:\(?\d{2,4}\)?[\s.\-]?)?'     # area code
    r'\d{3,4}[\s.\-]?'                # exchange
    r'\d{3,4}'                         # subscriber
    r'(?:[\s.\-]?\d{1,4})?',          # extension
    re.IGNORECASE,
)

# Replacement text for scrubbed PII
_PII_REDACTED = "[REDACTED]"


def scrub_pii(event: Dict[str, Any], hint: Dict[str, Any]) -> Dict[str, Any]:
    """Scrub PII (email addresses, phone numbers) from Sentry events.

    Called as a before_send hook on every Sentry event to ensure
    GDPR compliance by removing personally identifiable information.

    Args:
        event: The Sentry event dict.
        hint: The Sentry hint dict (contains exception info).

    Returns:
        The modified event dict with PII redacted.
    """
    try:
        event = _scrub_dict(event)
    except Exception:
        # BC-008: Never crash — if scrubbing fails, return original event
        pass
    return event


def _scrub_dict(data: Any) -> Any:
    """Recursively scrub PII from a dict/list/string structure."""
    if isinstance(data, dict):
        return {k: _scrub_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_scrub_dict(item) for item in data]
    elif isinstance(data, str):
        # Scrub emails first, then phone numbers
        result = _EMAIL_PATTERN.sub(_PII_REDACTED, data)
        # Only scrub phone numbers that look like actual phone numbers
        # (at least 7 digits to avoid false positives on short numbers)
        result = _scrub_phone_numbers(result)
        return result
    return data


def _scrub_phone_numbers(text: str) -> str:
    """Scrub phone numbers from text, with false-positive guards."""
    # Find all potential phone matches and validate them
    def _replace_match(match: re.Match) -> str:
        matched = match.group(0)
        # Count digits in the match
        digit_count = sum(c.isdigit() for c in matched)
        # Only redact if it looks like a real phone number (7+ digits)
        if digit_count >= 7:
            return _PII_REDACTED
        return matched

    return _PHONE_PATTERN.sub(_replace_match, text)


# ── Tenant Context ──────────────────────────────────────────────


def add_tenant_context(event: Dict[str, Any], hint: Dict[str, Any]) -> Dict[str, Any]:
    """Add tenant context (company_id) and correlation ID to Sentry events.

    Called as a before_send hook to enrich events with:
    - company_id from the current tenant context (BC-001)
    - correlation_id from the request context
    - timestamp in UTC (BC-012)

    Args:
        event: The Sentry event dict.
        hint: The Sentry hint dict.

    Returns:
        The modified event dict with tenant context.
    """
    try:
        # Add tenant context
        from app.core.tenant_context import get_tenant_context
        company_id = get_tenant_context()
        if company_id:
            # Set as tag for easy filtering in Sentry UI
            if "tags" not in event:
                event["tags"] = {}
            event["tags"]["company_id"] = company_id

            # Also add to extra context for full details
            if "extra" not in event:
                event["extra"] = {}
            event["extra"]["company_id"] = company_id

        # Add correlation ID if available
        try:
            from app.core.tenant_context import _tenant_ctx_var
            # Try to get from request state if available
            import contextvars
            correlation_id_var: Optional[contextvars.ContextVar] = None
            try:
                correlation_id_var = contextvars.ContextVar(
                    "correlation_id", default=None
                )
                corr_id = correlation_id_var.get()
                if corr_id:
                    if "tags" not in event:
                        event["tags"] = {}
                    event["tags"]["correlation_id"] = corr_id
                    if "extra" not in event:
                        event["extra"] = {}
                    event["extra"]["correlation_id"] = corr_id
            except LookupError:
                pass
        except Exception:
            pass

        # Ensure timestamp is UTC (BC-012)
        if "extra" not in event:
            event["extra"] = {}
        event["extra"]["captured_at_utc"] = datetime.now(
            timezone.utc
        ).isoformat() + "Z"

    except Exception:
        # BC-008: Never crash — context enrichment failure shouldn't
        # prevent the event from being sent
        pass

    return event


def _combined_before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Dict[str, Any]:
    """Combined before_send hook: PII scrubbing + tenant context.

    Order matters: add context first, then scrub PII.
    This ensures tenant context tags are present but PII in
    event messages/breadcrumbs is still redacted.
    """
    # First add context
    event = add_tenant_context(event, hint)
    # Then scrub PII
    event = scrub_pii(event, hint)
    return event


# ── Initialization ──────────────────────────────────────────────


def init_sentry() -> bool:
    """Initialize Sentry SDK if SENTRY_DSN is configured.

    BC-008: Never crash — if initialization fails, the app continues
    running without Sentry. The return value indicates success.

    Returns:
        True if Sentry was initialized, False otherwise.
    """
    global _sentry_initialized

    if _sentry_initialized:
        logger.info("sentry_already_initialized")
        return True

    try:
        settings = _get_settings()
        dsn = settings.SENTRY_DSN

        if not dsn:
            logger.info("sentry_skipped_no_dsn")
            return False

        # Determine environment
        environment = (
            settings.SENTRY_ENVIRONMENT
            if settings.SENTRY_ENVIRONMENT
            else settings.ENVIRONMENT
        )

        # Get environment-aware sample rates
        sample_rates = _get_sample_rates(environment)

        # Allow explicit overrides from settings
        traces_sample_rate = (
            settings.SENTRY_TRACES_SAMPLE_RATE
            if settings.SENTRY_TRACES_SAMPLE_RATE is not None
            else sample_rates["traces_sample_rate"]
        )
        profiles_sample_rate = (
            settings.SENTRY_PROFILES_SAMPLE_RATE
            if settings.SENTRY_PROFILES_SAMPLE_RATE is not None
            else sample_rates["profiles_sample_rate"]
        )

        # Import Sentry SDK integrations
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.redis import RedisIntegration

        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            integrations=[
                FastApiIntegration(),
                CeleryIntegration(),
                RedisIntegration(),
            ],
            # Sample rates
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            # GDPR compliance: never send default PII
            send_default_pii=False,
            # Before send hook: add context + scrub PII
            before_send=_combined_before_send,
            # Attach stack traces to all log messages
            attach_stacktrace=True,
            # Send client reports for dropped events
            send_client_reports=True,
        )

        _sentry_initialized = True

        logger.info(
            "sentry_initialized",
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            send_default_pii=False,
        )
        return True

    except Exception as exc:
        # BC-008: Never crash — log warning and continue
        logger.warning(
            "sentry_init_failed",
            error=str(exc),
        )
        return False


# ── Public API ──────────────────────────────────────────────────


def capture_exception(exc: Exception, **kwargs: Any) -> Optional[str]:
    """Capture an exception in Sentry with optional context.

    Wrapper around sentry_sdk.capture_exception that adds:
    - company_id tag if tenant context is available
    - Arbitrary extra context via kwargs

    BC-008: Never crash — if Sentry capture fails, just log.

    Args:
        exc: The exception to capture.
        **kwargs: Additional context to attach (tags, extra, etc.).

    Returns:
        The Sentry event ID, or None if capture failed.
    """
    try:
        import sentry_sdk

        if not _sentry_initialized:
            return None

        # Add tenant context if available
        from app.core.tenant_context import get_tenant_context
        company_id = get_tenant_context()

        with sentry_sdk.push_scope() as scope:
            if company_id:
                scope.set_tag("company_id", company_id)
                scope.set_extra("company_id", company_id)

            # Add any extra context from kwargs
            for key, value in kwargs.items():
                scope.set_extra(key, value)

            event_id = sentry_sdk.capture_exception(exc)
            return event_id

    except Exception as capture_exc:
        # BC-008: Never crash
        logger.warning(
            "sentry_capture_exception_failed",
            error=str(capture_exc),
        )
        return None


def capture_message(message: str, level: str = "info", **kwargs: Any) -> Optional[str]:
    """Capture a message in Sentry with optional context.

    BC-008: Never crash — if Sentry capture fails, just log.

    Args:
        message: The message to capture.
        level: Log level (debug, info, warning, error, fatal).
        **kwargs: Additional context to attach.

    Returns:
        The Sentry event ID, or None if capture failed.
    """
    try:
        import sentry_sdk

        if not _sentry_initialized:
            return None

        from app.core.tenant_context import get_tenant_context
        company_id = get_tenant_context()

        with sentry_sdk.push_scope() as scope:
            if company_id:
                scope.set_tag("company_id", company_id)
                scope.set_extra("company_id", company_id)

            for key, value in kwargs.items():
                scope.set_extra(key, value)

            event_id = sentry_sdk.capture_message(message, level=level)
            return event_id

    except Exception as capture_exc:
        # BC-008: Never crash
        logger.warning(
            "sentry_capture_message_failed",
            error=str(capture_exc),
        )
        return None


def is_initialized() -> bool:
    """Check if Sentry has been initialized.

    Returns:
        True if Sentry SDK is initialized and active.
    """
    return _sentry_initialized


def get_sentry_status() -> Dict[str, Any]:
    """Get Sentry status for health check reporting.

    Returns a dict with initialization status, DSN presence,
    environment, and sample rates. No sensitive data exposed.

    Returns:
        Dict with Sentry status information.
    """
    try:
        settings = _get_settings()
        environment = (
            settings.SENTRY_ENVIRONMENT
            if settings.SENTRY_ENVIRONMENT
            else settings.ENVIRONMENT
        )
        sample_rates = _get_sample_rates(environment)

        return {
            "initialized": _sentry_initialized,
            "dsn_configured": bool(settings.SENTRY_DSN),
            "environment": environment,
            "traces_sample_rate": (
                settings.SENTRY_TRACES_SAMPLE_RATE
                if settings.SENTRY_TRACES_SAMPLE_RATE is not None
                else sample_rates["traces_sample_rate"]
            ),
            "profiles_sample_rate": (
                settings.SENTRY_PROFILES_SAMPLE_RATE
                if settings.SENTRY_PROFILES_SAMPLE_RATE is not None
                else sample_rates["profiles_sample_rate"]
            ),
            "send_default_pii": False,
        }
    except Exception:
        return {
            "initialized": False,
            "dsn_configured": False,
            "error": "status_check_failed",
        }


def flush(timeout: float = 2.0) -> None:
    """Flush pending Sentry events.

    Call during shutdown to ensure all queued events are sent.

    Args:
        timeout: Maximum time in seconds to wait for flush.
    """
    try:
        if _sentry_initialized:
            import sentry_sdk
            client = sentry_sdk.Hub.current.client
            if client:
                client.flush(timeout=timeout)
                logger.info("sentry_flushed")
    except Exception as exc:
        logger.warning("sentry_flush_failed", error=str(exc))
