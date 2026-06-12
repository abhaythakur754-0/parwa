"""PARWA Phase 3 Ingestion System — Category-first webhook ingestion.

Exports the key classes that external modules need:

    IncomingMessage       — Universal data model for all incoming messages
    IngestionOrchestrator — Single entry point for all webhook ingestion

Design principles:
    - Category-first, not provider-first: routing is by channel category
      (email, sms, voice, chat, webhook), not by provider name.
    - Unknown providers work via generic fallback normalizers.
    - BC-001: All queries scoped to company_id
    - BC-008: Never crash — all normalizers in try/except
    - Ingestion failure NEVER breaks existing webhook processing

Usage::

    from app.core.ingestion import IngestionOrchestrator, IncomingMessage

    orchestrator = IngestionOrchestrator()

    # Register a custom provider-specific normalizer (optional)
    orchestrator.register_normalizer("my_custom_provider", MyCustomNormalizer())

    # Ingest a payload
    result = orchestrator.ingest(
        payload={"Body": "Hello", "From": "+1234567890"},
        provider_type="twilio_sms",
        company_id="comp_abc123",
    )

    if result["status"] == "ingested":
        message: IncomingMessage = result["message"]
        print(f"Ingested: {message.message_id} from {message.sender_phone}")
    elif result["status"] == "duplicate":
        print(f"Duplicate: {result['error']}")
    else:
        print(f"Error: {result['error']}")
"""

from .models import (
    ChannelCategory,
    IngestionStatus,
    IncomingMessage,
    MessagePriority,
    MessageSentiment,
)
from .orchestrator import IngestionOrchestrator

__all__ = [
    # Primary exports
    "IncomingMessage",
    "IngestionOrchestrator",
    # Supporting enums (useful for callers)
    "ChannelCategory",
    "IngestionStatus",
    "MessagePriority",
    "MessageSentiment",
]
