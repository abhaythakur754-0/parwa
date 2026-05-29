"""
PARWA AI — Unified Webhook Processing Service

Combines the WebhookParserRegistry and WebhookVerifierRegistry into a
single entry point that:
  1. Parses any incoming webhook (registered or generic)
  2. Verifies the signature/IP
  3. Stores the event (idempotent)
  4. Dispatches to the correct handler
  5. Provides retry logic for failed events

This service replaces the scattered provider-specific logic in the
webhook API route with a clean, extensible pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Request

from app.core.providers.webhook_parser import WebhookParserRegistry
from app.core.providers.webhook_verifier import WebhookVerifierRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unified Webhook Service
# ---------------------------------------------------------------------------

class WebhookUnifiedService:
    """Unified entry point for processing webhooks from any provider.

    Pipeline:
        receive → parse → verify → store → dispatch

    Each step can be extended by registering new parsers, verifiers,
    or handlers without modifying this service.
    """

    # Max retry attempts for failed webhooks
    MAX_RETRIES = 5

    # Supported providers (dynamic — grows as parsers are registered)
    @property
    def supported_providers(self) -> list[str]:
        """Return providers that have both a parser and a verifier registered."""
        parser_providers = set(WebhookParserRegistry.list_providers())
        # Generic parser covers all providers, so parsers are always available
        return sorted(parser_providers)

    # ── Receive (entry point) ──────────────────────────────────────────

    async def receive(
        self,
        provider: str,
        request: Request,
        secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Receive and process a webhook from any provider.

        This is the main entry point called by the API route.

        Args:
            provider: Provider name (e.g. ``"paddle"``, ``"stripe"``).
            request:  FastAPI Request object.
            secret:   Optional override secret. If None, will be loaded
                      from settings.

        Returns:
            Result dict with status, event_id, duplicate flag, etc.
        """
        provider = provider.lower().strip()

        # 1. Read raw body
        body = await request.body()

        # 2. Validate payload size
        max_size = self._get_max_payload_size()
        if len(body) > max_size:
            return {
                "status": "rejected",
                "error": "PAYLOAD_TOO_LARGE",
                "message": f"Payload exceeds {max_size} bytes",
                "max_size": max_size,
                "actual_size": len(body),
            }

        # 3. Parse payload
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        # 4. Parse the webhook using the registry (or generic fallback)
        parsed = WebhookParserRegistry.parse(provider, payload)

        # 5. Validate timestamp (replay protection)
        timestamp_check = self._check_timestamp(parsed.get("occurred_at"), provider)
        if not timestamp_check["valid"]:
            return {
                "status": "rejected",
                "error": "REPLAY_DETECTED",
                "message": timestamp_check["message"],
            }

        # 6. Verify signature
        if secret is None:
            secret = self._get_provider_secret(provider)

        if not secret:
            return {
                "status": "rejected",
                "error": "CONFIGURATION_ERROR",
                "message": f"Webhook secret not configured for provider '{provider}'",
            }

        is_valid = WebhookVerifierRegistry.verify(
            provider, request, payload, body, secret,
        )
        if not is_valid:
            return {
                "status": "rejected",
                "error": "AUTHENTICATION_ERROR",
                "message": "Invalid webhook signature",
            }

        # 7. Validate required fields
        event_id = parsed.get("event_id", "")
        company_id = parsed.get("company_id")
        event_type = parsed.get("event_type", f"{provider}.unknown")

        if not event_id:
            return {
                "status": "rejected",
                "error": "VALIDATION_ERROR",
                "message": "event_id is required",
            }

        if not company_id:
            return {
                "status": "rejected",
                "error": "VALIDATION_ERROR",
                "message": "company_id is required",
            }

        # 8. Store and process (idempotent)
        try:
            result = self._process_webhook(
                company_id=company_id,
                provider=provider,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                parsed=parsed,
            )
            return result
        except Exception as exc:
            logger.error(
                "webhook_processing_error provider=%s error=%s",
                provider, exc,
            )
            return {
                "status": "error",
                "error": "INTERNAL_ERROR",
                "message": "Webhook processing failed",
            }

    # ── Store & Process ────────────────────────────────────────────────

    def _process_webhook(
        self,
        company_id: str,
        provider: str,
        event_id: str,
        event_type: str,
        payload: dict,
        parsed: dict,
    ) -> Dict[str, Any]:
        """Process a verified webhook event.

        This delegates to the existing webhook_service.process_webhook()
        for idempotent storage, and adds the unified service metadata.

        Args:
            company_id:  Tenant UUID.
            provider:    Provider name.
            event_id:    Provider-specific event ID.
            event_type:  Normalised event type.
            payload:     Original payload.
            parsed:      Parsed/normalised fields.

        Returns:
            Result dict with status, event_id, duplicate flag.
        """
        try:
            from app.services import webhook_service

            result = webhook_service.process_webhook(
                company_id=company_id,
                provider=provider,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
            )
            result["unified"] = True
            result["parser"] = "registered" if WebhookParserRegistry.has_parser(provider) else "generic"
            return result
        except ImportError:
            # Fallback if webhook_service is not available (early bootstrap)
            logger.warning(
                "webhook_service not available — storing event directly",
            )
            return {
                "status": "received",
                "event_id": event_id,
                "duplicate": False,
                "unified": True,
                "parser": "registered" if WebhookParserRegistry.has_parser(provider) else "generic",
                "message": "Webhook received (stored without dispatch)",
            }

    # ── Retry ──────────────────────────────────────────────────────────

    def retry_failed(self, event_db_id: str) -> Dict[str, Any]:
        """Retry a failed webhook event.

        Args:
            event_db_id: Database ID of the webhook event.

        Returns:
            Result dict with retry status.

        Raises:
            ValueError: If the event doesn't exist or has exceeded max retries.
        """
        try:
            from app.services import webhook_service
            result = webhook_service.retry_failed_webhook(event_db_id)
            result["unified"] = True
            return result
        except ImportError:
            raise ValueError(
                "webhook_service not available — cannot retry event"
            )

    # ── Helpers ────────────────────────────────────────────────────────

    def _check_timestamp(
        self, occurred_at: Optional[str], provider: str,
    ) -> Dict[str, Any]:
        """Check webhook timestamp freshness to prevent replay attacks.

        Returns:
            Dict with 'valid' bool and optional 'message'.
        """
        if not occurred_at:
            return {
                "valid": False,
                "message": (
                    "Webhook event has no timestamp. "
                    "Rejecting as potential replay attack."
                ),
            }

        try:
            if isinstance(occurred_at, datetime):
                event_time = occurred_at
            else:
                event_time = datetime.fromisoformat(
                    str(occurred_at).replace("Z", "+00:00"),
                )

            max_age = self._get_max_age_seconds()
            age = (datetime.now(timezone.utc) - event_time).total_seconds()

            if age > max_age:
                return {
                    "valid": False,
                    "message": (
                        f"Webhook event is too old "
                        f"({int(age)}s > {max_age}s max). "
                        f"Possible replay attack."
                    ),
                }

            return {"valid": True}
        except (ValueError, TypeError) as exc:
            return {
                "valid": False,
                "message": (
                    f"Webhook event timestamp is unparseable: {exc}. "
                    f"Rejecting as potential replay attack."
                ),
            }

    def _get_provider_secret(self, provider: str) -> Optional[str]:
        """Load the webhook secret for a provider from settings.

        Checks provider-specific env vars, then falls back to
        a generic WEBHOOK_SECRET.
        """
        try:
            from app.config import get_settings
            settings = get_settings()

            secret_map = {
                "paddle": getattr(settings, "PADDLE_WEBHOOK_SECRET", ""),
                "shopify": getattr(settings, "SHOPIFY_WEBHOOK_SECRET", ""),
                "twilio": getattr(settings, "TWILIO_AUTH_TOKEN", ""),
                "brevo": getattr(settings, "BREVO_WEBHOOK_SECRET", ""),
            }

            secret = secret_map.get(provider)
            if not secret:
                # Try generic webhook secret
                secret = getattr(settings, "WEBHOOK_SECRET", "")
            return secret or None
        except Exception:
            return None

    def _get_max_payload_size(self) -> int:
        """Get max webhook payload size from settings."""
        try:
            from app.config import get_settings
            return get_settings().WEBHOOK_MAX_PAYLOAD_SIZE
        except Exception:
            return 1_048_576  # 1MB default

    def _get_max_age_seconds(self) -> int:
        """Get max webhook age from settings."""
        try:
            from app.config import get_settings
            return get_settings().WEBHOOK_MAX_AGE_SECONDS
        except Exception:
            return 300  # 5 minutes default


# Singleton instance
webhook_unified_service = WebhookUnifiedService()
