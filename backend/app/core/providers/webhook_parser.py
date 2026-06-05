"""
PARWA AI — Generic Webhook Parser Registry

Provides a pluggable parser system for incoming webhooks from ANY provider.
Each provider registers a parser function that extracts:
  - event_id
  - event_type
  - company_id
  - occurred_at (timestamp)
  - raw payload normalization

This replaces the scattered if/elif chains in the webhook API route,
following the same pattern as ProviderRegistry for consistency.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parser Protocol
# ---------------------------------------------------------------------------

class WebhookParser(Protocol):
    """Protocol that every webhook parser must satisfy.

    A parser receives the raw JSON payload and returns a normalised dict
    with at least ``event_id``, ``event_type``, ``company_id``, ``occurred_at``.
    """

    def __call__(self, payload: dict) -> dict: ...


# ---------------------------------------------------------------------------
# Built-in Parsers
# ---------------------------------------------------------------------------

def parse_paddle(payload: dict) -> dict:
    """Parse Paddle webhook payload."""
    brevo_event_map = {
        "subscription.created": "subscription.created",
        "subscription.updated": "subscription.updated",
        "subscription.canceled": "subscription.canceled",
        "transaction.completed": "transaction.completed",
        "transaction.paid": "transaction.paid",
        "transaction.payment_failed": "transaction.payment_failed",
    }
    event_type = payload.get("event_type", "paddle.unknown")
    return {
        "event_id": payload.get("event_id", ""),
        "event_type": brevo_event_map.get(event_type, event_type),
        "company_id": payload.get("custom_data", {}).get("company_id") or payload.get("company_id"),
        "occurred_at": payload.get("occurred_at") or payload.get("created_at"),
    }


def parse_shopify(payload: dict) -> dict:
    """Parse Shopify webhook payload."""
    return {
        "event_id": str(payload.get("id", "")),
        "event_type": payload.get("topic", "shopify.unknown"),
        "company_id": payload.get("x_company_id") or payload.get("company_id"),
        "occurred_at": payload.get("created_at") or payload.get("updated_at"),
    }


def parse_twilio(payload: dict) -> dict:
    """Parse Twilio webhook payload."""
    event_type = payload.get("EventType") or "sms.incoming"
    return {
        "event_id": payload.get("MessageSid") or payload.get("CallSid", ""),
        "event_type": f"twilio.{event_type}",
        "company_id": payload.get("AccountSid"),
        "occurred_at": payload.get("Timestamp") or payload.get("DateCreated"),
    }


def parse_brevo(payload: dict) -> dict:
    """Parse Brevo (Sendinblue) webhook payload."""
    event = payload.get("event", "")
    brevo_event_map = {
        "hard_bounce": "bounce",
        "soft_bounce": "bounce",
        "blocked": "bounce",
        "deferred": "bounce",
        "spam": "complaint",
        "request_unsubscribed": "complaint",
        "delivered": "delivered",
        "opened": "opened",
        "clicked": "clicked",
    }
    normalized = brevo_event_map.get(event, event)
    return {
        "event_id": payload.get("event_id") or payload.get("message-id", ""),
        "event_type": f"brevo.{normalized}",
        "company_id": payload.get("company_id"),
        "occurred_at": payload.get("event_time") or payload.get("ts"),
    }


def parse_generic(payload: dict) -> dict:
    """Generic fallback parser for custom/unregistered providers.

    Attempts common field names and falls back gracefully.
    """
    return {
        "event_id": (
            payload.get("event_id")
            or payload.get("id")
            or payload.get("uuid")
            or ""
        ),
        "event_type": (
            payload.get("event_type")
            or payload.get("type")
            or payload.get("action")
            or "custom.unknown"
        ),
        "company_id": (
            payload.get("company_id")
            or payload.get("tenant_id")
            or payload.get("organization_id")
            or payload.get("account_id")
        ),
        "occurred_at": (
            payload.get("occurred_at")
            or payload.get("created_at")
            or payload.get("timestamp")
            or datetime.now(timezone.utc).isoformat()
        ),
    }


# ---------------------------------------------------------------------------
# Parser Registry
# ---------------------------------------------------------------------------

class WebhookParserRegistry:
    """Central registry for webhook parsers.

    Structure::

        {
            "paddle": parse_paddle,
            "shopify": parse_shopify,
            ...
        }

    Usage::

        WebhookParserRegistry.register("stripe", parse_stripe)
        parsed = WebhookParserRegistry.parse("stripe", payload)
    """

    _parsers: Dict[str, WebhookParser] = {}

    @classmethod
    def register(cls, provider: str, parser: WebhookParser) -> None:
        """Register a parser for a given provider name.

        Args:
            provider: Unique provider key (e.g. ``"stripe"``).
            parser:   Callable that takes a dict and returns a normalised dict.
        """
        provider = provider.lower().strip()
        if provider in cls._parsers:
            logger.warning(
                "Overwriting existing webhook parser for provider '%s'",
                provider,
            )
        cls._parsers[provider] = parser
        logger.debug("Registered webhook parser for provider '%s'", provider)

    @classmethod
    def parse(cls, provider: str, payload: dict) -> dict:
        """Parse a webhook payload using the registered parser.

        Falls back to ``parse_generic`` if the provider has no
        registered parser.

        Args:
            provider: Provider name.
            payload:  Raw JSON payload from the webhook request.

        Returns:
            Normalised dict with event_id, event_type, company_id, occurred_at.
        """
        provider = provider.lower().strip()
        parser = cls._parsers.get(provider, parse_generic)
        try:
            result = parser(payload)
        except Exception as exc:
            logger.error(
                "Webhook parser error for provider '%s': %s — falling back to generic",
                provider,
                exc,
            )
            result = parse_generic(payload)

        # Ensure required fields exist
        result.setdefault("event_id", "")
        result.setdefault("event_type", f"{provider}.unknown")
        result.setdefault("company_id", None)
        result.setdefault("occurred_at", datetime.now(timezone.utc).isoformat())
        result["_provider"] = provider
        return result

    @classmethod
    def get_parser(cls, provider: str) -> Optional[WebhookParser]:
        """Return the parser for a provider, or None if not registered."""
        return cls._parsers.get(provider.lower().strip())

    @classmethod
    def list_providers(cls) -> list[str]:
        """Return all registered provider names."""
        return sorted(cls._parsers.keys())

    @classmethod
    def has_parser(cls, provider: str) -> bool:
        """Check if a provider has a registered parser."""
        return provider.lower().strip() in cls._parsers


# ---------------------------------------------------------------------------
# Auto-register built-in parsers
# ---------------------------------------------------------------------------

def _register_defaults():
    """Register all built-in webhook parsers."""
    WebhookParserRegistry.register("paddle", parse_paddle)
    WebhookParserRegistry.register("shopify", parse_shopify)
    WebhookParserRegistry.register("twilio", parse_twilio)
    WebhookParserRegistry.register("brevo", parse_brevo)


_register_defaults()
