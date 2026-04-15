"""
Webhook API Endpoints (BC-003, BC-012)

Generic webhook receiver for multiple providers:
- POST /api/webhooks/{provider} — Receive webhook
- GET /api/webhooks/status/{event_db_id} — Check event status
- POST /api/webhooks/retry/{event_db_id} — Retry failed event

All endpoints:
- Verify HMAC signature per provider
- Extract event_id and event_type from provider payload
- Call process_webhook() for immediate storage
- Return 200 immediately (BC-003: under 3 seconds)
- Structured JSON error responses (BC-012)
- Payload size validation (max 1MB per BC-003)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.schemas.webhook import (
    WebhookResponse,
)
from app.services import webhook_service
from database.models.core import User

logger = logging.getLogger("parwa.webhook_api")

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

# Supported webhook providers
SUPPORTED_PROVIDERS = {"paddle", "twilio", "shopify", "brevo"}

# Maximum webhook payload size: 1MB (BC-003)
MAX_WEBHOOK_PAYLOAD_SIZE = 1 * 1024 * 1024


def _get_company_id_from_payload(
    provider: str, payload: dict,
) -> Optional[str]:
    """Extract company_id from provider-specific payload.

    Each provider has a different field name for the
    tenant/company identifier.
    """
    if provider == "paddle":
        return payload.get(
            "custom_data", {},
        ).get("company_id") or payload.get("company_id")
    if provider == "shopify":
        return payload.get(
            "x_company_id",
        ) or payload.get("company_id")
    if provider == "twilio":
        return payload.get(
            "AccountSid",
        )  # Twilio uses AccountSid as tenant
    if provider == "brevo":
        return payload.get("company_id")
    return payload.get("company_id")


def _get_event_id_from_payload(
    provider: str, payload: dict,
) -> Optional[str]:
    """Extract provider-specific event ID."""
    if provider == "paddle":
        return payload.get("event_id")
    if provider == "shopify":
        return payload.get("id") or str(
            payload.get("id", ""),
        )
    if provider == "twilio":
        return payload.get(
            "MessageSid",
        ) or payload.get("CallSid")
    if provider == "brevo":
        return payload.get("event_id")
    return payload.get("event_id")


def _get_event_type_from_payload(
    provider: str, payload: dict,
) -> Optional[str]:
    """Extract event type from provider payload."""
    if provider == "paddle":
        return payload.get("event_type")
    if provider == "shopify":
        return payload.get("topic")
    if provider == "twilio":
        return payload.get("EventType") or "sms.incoming"
    if provider == "brevo":
        event = payload.get("event", "")
        # Normalize Brevo event types (F-124 Day 3)
        brevo_event_map = {
            "hard_bounce": "bounce",
            "soft_bounce": "bounce",
            "blocked": "bounce",
            "deferred": "bounce",
            "spam": "complaint",
            "request_unsubscribed": "complaint",
        }
        return brevo_event_map.get(event, event)
    return payload.get("event_type")


def _verify_provider_signature(
    provider: str,
    request: Request,
    payload: dict,
    body: bytes,
) -> bool:
    """Verify HMAC signature per provider.

    Returns True if verification passes or is not required,
    False if verification fails.

    SECURITY NOTE (BC-011):
    - HMAC verification is skipped ONLY when ENVIRONMENT=test.
    - In all other environments, verification is ENFORCED.
    - Each provider has its own verification method:
        * Paddle: HMAC-SHA256 with PADDLE_WEBHOOK_SECRET
        * Shopify: HMAC-SHA256 with SHOPIFY_WEBHOOK_SECRET
        * Twilio: URL+params signed with TWILIO_AUTH_TOKEN
        * Brevo: IP allowlist verification
    """
    import os

    # Skip verification ONLY in test environment.
    # SECURITY: In staging/production, this is always enforced.
    if os.environ.get("ENVIRONMENT") == "test":
        return True

    try:
        if provider == "paddle":
            from app.security.hmac_verification import (
                verify_paddle_signature,
            )
            from app.config import get_settings
            settings = get_settings()
            signature = request.headers.get(
                "paddle-signature", "",
            )
            result = verify_paddle_signature(
                body, signature,
                settings.PADDLE_WEBHOOK_SECRET,
            )
            if not result:
                logger.warning(
                    "webhook_paddle_signature_invalid",
                )
            return result

        if provider == "shopify":
            from app.security.hmac_verification import (
                verify_shopify_hmac,
            )
            from app.config import get_settings
            settings = get_settings()
            signature = request.headers.get(
                "x-shopify-hmac-sha256", "",
            )
            # FIX L27: Use config.SHOPIFY_WEBHOOK_SECRET
            # instead of raw os.environ
            result = verify_shopify_hmac(
                body, signature,
                settings.SHOPIFY_WEBHOOK_SECRET,
            )
            if not result:
                logger.warning(
                    "webhook_shopify_signature_invalid",
                )
            return result

        if provider == "twilio":
            from app.security.hmac_verification import (
                verify_twilio_signature,
            )
            from app.config import get_settings
            settings = get_settings()
            signature = request.headers.get(
                "x-twilio-signature", "",
            )
            result = verify_twilio_signature(
                str(request.url),
                payload,
                signature,
                settings.TWILIO_AUTH_TOKEN,
            )
            if not result:
                logger.warning(
                    "webhook_twilio_signature_invalid",
                )
            return result

        if provider == "brevo":
            from app.security.hmac_verification import (
                verify_brevo_ip,
            )
            from app.config import get_settings
            settings = get_settings()
            forwarded = request.headers.get(
                "x-forwarded-for", "",
            )
            client_ip = (
                forwarded.split(",")[0].strip()
                if forwarded
                else request.client.host
                if request.client
                else ""
            )
            # Use configured IPs if set, otherwise use defaults
            custom_ips = None
            if settings.BREVO_INBOUND_IPS:
                custom_ips = [
                    cidr.strip()
                    for cidr in settings.BREVO_INBOUND_IPS.split(",")
                    if cidr.strip()
                ]
            result = verify_brevo_ip(client_ip, allowed_ips=custom_ips)
            if not result:
                logger.warning(
                    "webhook_brevo_ip_blocked client_ip=%s",
                    client_ip,
                )
            return result

        # Unknown provider — block in production
        logger.warning(
            "webhook_unknown_provider_verification provider=%s",
            provider,
        )
        return False

    except Exception as exc:
        logger.error(
            "webhook_signature_verification_error "
            "provider=%s error=%s",
            provider, exc,
        )
        return False


@router.post(
    "/{provider}",
    response_model=WebhookResponse,
    status_code=200,
)
async def receive_webhook(
    provider: str,
    request: Request,
):
    """Receive a webhook from a third-party provider.

    Flow:
        1. Validate provider is supported
        2. Verify HMAC signature per provider
        3. Extract event_id, event_type, company_id
        4. Call process_webhook() (idempotent, async dispatch)
        5. Return 200 immediately (BC-003)

    Args:
        provider: Webhook provider name.

    Returns:
        WebhookResponse with status and event ID.
    """
    # Validate provider
    if provider not in SUPPORTED_PROVIDERS:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": (
                        f"Unsupported provider: {provider}"
                    ),
                    "details": {
                        "supported": sorted(
                            SUPPORTED_PROVIDERS,
                        ),
                    },
                }
            },
        )

    # Read raw body
    body = await request.body()

    # FIX L28: Validate payload size (max 1MB per BC-003)
    if len(body) > MAX_WEBHOOK_PAYLOAD_SIZE:
        logger.warning(
            "webhook_payload_too_large provider=%s size=%s",
            provider, len(body),
        )
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": (
                        f"Webhook payload exceeds maximum "
                        f"size of {MAX_WEBHOOK_PAYLOAD_SIZE} bytes"
                    ),
                    "details": {
                        "max_size": MAX_WEBHOOK_PAYLOAD_SIZE,
                        "actual_size": len(body),
                    },
                }
            },
        )

    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        # E5: Return 400 for invalid JSON instead of silently defaulting to {}
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "INVALID_JSON",
                    "message": "Request body is not valid JSON",
                    "details": None,
                }
            },
        )

    # Verify signature (BC-011, BC-003)
    if not _verify_provider_signature(
        provider, request, payload, body,
    ):
        logger.warning(
            "webhook_signature_rejected provider=%s event_id=%s",
            provider,
            _get_event_id_from_payload(provider, payload),
        )
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": (
                        "Invalid webhook signature"
                    ),
                    "details": None,
                }
            },
        )

    # Extract event fields from payload
    event_id = _get_event_id_from_payload(
        provider, payload,
    )
    event_type = _get_event_type_from_payload(
        provider, payload,
    )
    company_id = _get_company_id_from_payload(
        provider, payload,
    )

    # Validate required fields
    if not event_id:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "event_id is required",
                    "details": None,
                }
            },
        )

    if not company_id:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": (
                        "company_id is required (BC-001)"
                    ),
                    "details": None,
                }
            },
        )

    if not event_type:
        event_type = f"{provider}.unknown"

    # Process webhook (idempotent, dispatches to Celery)
    try:
        result = webhook_service.process_webhook(
            company_id=company_id,
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
        return WebhookResponse(
            status=result["status"],
            message=(
                "Webhook received and queued"
                if not result["duplicate"]
                else "Duplicate event"
            ),
            event_id=result["id"],
            duplicate=result["duplicate"],
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(exc),
                    "details": None,
                }
            },
        )
    except Exception as exc:
        logger.error(
            "webhook_processing_error provider=%s error=%s",
            provider, exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": (
                        "Webhook processing failed"
                    ),
                    "details": None,
                }
            },
        )


@router.get(
    "/status/{event_db_id}",
)
async def get_webhook_status(
    event_db_id: str,
    user: User = Depends(get_current_user),
):
    """Check the processing status of a webhook event.

    Args:
        event_db_id: Webhook event database record ID.

    Returns:
        Event details with current status.
    """
    try:
        event = webhook_service.get_webhook_event(
            event_db_id,
        )
        return event
    except ValueError as exc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": str(exc),
                    "details": None,
                }
            },
        )


@router.post(
    "/retry/{event_db_id}",
    response_model=WebhookResponse,
)
async def retry_webhook(
    event_db_id: str,
    user: User = Depends(get_current_user),
):
    """Retry a failed webhook event.

    Resets the event to 'pending' and re-dispatches
    to the Celery webhook queue.

    Args:
        event_db_id: Webhook event database record ID.

    Returns:
        Updated event status.
    """
    try:
        result = webhook_service.retry_failed_webhook(
            event_db_id,
        )
        return WebhookResponse(
            status=result["status"],
            message="Webhook queued for retry",
            event_id=result["id"],
            duplicate=result["duplicate"],
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(exc),
                    "details": None,
                }
            },
        )
    except Exception as exc:
        logger.error(
            "webhook_retry_error event_db_id=%s error=%s",
            event_db_id, exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Retry failed",
                    "details": None,
                }
            },
        )
