"""
PARWA Sentry Integration

Initializes Sentry for error monitoring and performance tracing.
Only active when SENTRY_DSN is configured (no-op otherwise).
"""

import logging
import os

logger = logging.getLogger("parwa.sentry")

_sentry_initialized = False


def init_sentry() -> bool:
    """Initialize Sentry SDK if SENTRY_DSN is configured.

    Returns True if Sentry was initialized, False otherwise.
    Safe to call multiple times (idempotent).
    """
    global _sentry_initialized
    if _sentry_initialized:
        return True

    dsn = os.environ.get("SENTRY_DSN", "")
    environment = os.environ.get("ENVIRONMENT", "production")

    if not dsn:
        logger.info("Sentry DSN not configured — skipping initialization")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=0.1 if environment == "production" else 1.0,
            profiles_sample_rate=0.1 if environment == "production" else 1.0,
            send_default_pii=False,  # BC-012: No PII in Sentry
            attach_stacktrace=True,
            max_breadcrumbs=50,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                ),
            ],
            before_send=before_send_handler,
            before_breadcrumb=before_breadcrumb_handler,
        )

        _sentry_initialized = True
        logger.info("sentry_initialized", environment=environment)
        return True
    except Exception as exc:
        logger.warning("sentry_init_failed", error=str(exc))
        return False


def before_send_handler(event, hint):
    """Filter events before sending to Sentry.

    - Strip PII from request headers
    - Filter out expected errors
    - Add PARWA-specific context
    """
    if event is None:
        return None

    # Filter out health check noise
    request = event.get("request", {})
    url = request.get("url", "")
    if "/health" in url or "/ready" in url:
        return None

    # Strip sensitive headers
    headers = request.get("headers", {})
    for key in ["authorization", "cookie", "x-api-key", "x-csrf-token"]:
        if key in headers:
            headers[key] = "[FILTERED]"

    # Add user context without PII
    if "user" in event:
        user = event["user"]
        # Keep id and role, remove email/IP
        if "email" in user:
            user["email"] = None
        if "ip_address" in user:
            user["ip_address"] = None

    return event


def before_breadcrumb_handler(crumb, hint):
    """Filter breadcrumbs — exclude noisy ones."""
    if crumb is None:
        return None

    # Skip health check breadcrumbs
    url = crumb.get("data", {}).get("url", "")
    if "/health" in url:
        return None

    return crumb


def capture_exception(exc: Exception, extra: dict = None):
    """Manually capture an exception to Sentry."""
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
        if extra:
            sentry_sdk.set_context("extra", extra)
    except Exception:
        pass  # Never let Sentry break the app


def capture_message(message: str, level: str = "info"):
    """Manually capture a message to Sentry."""
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.capture_message(message, level=level)
    except Exception:
        pass
