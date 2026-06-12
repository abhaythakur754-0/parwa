"""PARWA Phase 3 Ingestion — Category-first ingestion orchestrator.

The orchestrator is the single entry point for all incoming webhook payloads.
It determines the channel category, selects the best normalizer (specific →
generic → ultimate fallback), normalizes the payload into an IncomingMessage,
deduplicates, and returns the result.

Routing priority:
    1. Provider-specific normalizer (if registered for this provider_type)
    2. Category-specific generic normalizer (fallback)
    3. GenericWebhookNormalizer (ultimate fallback)

Business constraints enforced:
    BC-001: All queries scoped to company_id
    BC-003: Deduplication via message_id tracking (per company)
    BC-008: Never crash — all normalizers wrapped in try/except;
            ingestion failure NEVER breaks existing webhook processing
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import (
    ChannelCategory,
    IngestionStatus,
    IncomingMessage,
    MessagePriority,
    MessageSentiment,
)
from .normalizers import (
    BaseNormalizer,
    GenericChatNormalizer,
    GenericEmailNormalizer,
    GenericSMSNormalizer,
    GenericVoiceNormalizer,
    GenericWebhookNormalizer,
)

logger = logging.getLogger(__name__)


class IngestionOrchestrator:
    """Category-first ingestion orchestrator.

    Usage::

        orchestrator = IngestionOrchestrator()
        result = orchestrator.ingest(
            payload={"Body": "Hello", "From": "+1234567890"},
            provider_type="twilio_sms",
            company_id="comp_abc123",
        )
        # result = {"status": "ingested", "message": IncomingMessage(...), ...}
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self):
        # Provider-specific normalizers: provider_type → normalizer instance
        self._normalizers: Dict[str, BaseNormalizer] = {}

        # Category-specific generic normalizers: category → normalizer instance
        self._generic_normalizers: Dict[str, BaseNormalizer] = {}

        # Dedup tracking: "company_id:message_id" → epoch timestamp
        # BC-003: dedup is scoped per company
        self._seen_messages: Dict[str, float] = {}

        # Configuration
        self._dedup_ttl_seconds: int = 86400  # 24 hours default

        # Ingestion statistics
        self._stats: Dict[str, int] = {
            "total_ingested": 0,
            "total_duplicates": 0,
            "total_errors": 0,
            "total_validation_errors": 0,
        }

        # Register built-in generic normalizers
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register the five category-level generic fallback normalizers."""
        generic_map = {
            ChannelCategory.EMAIL: GenericEmailNormalizer(),
            ChannelCategory.SMS: GenericSMSNormalizer(),
            ChannelCategory.VOICE: GenericVoiceNormalizer(),
            ChannelCategory.CHAT: GenericChatNormalizer(),
            ChannelCategory.WEBHOOK: GenericWebhookNormalizer(),
        }
        for category, normalizer in generic_map.items():
            self._generic_normalizers[category.value] = normalizer
            logger.info(
                "Registered generic normalizer: category=%s, class=%s",
                category.value,
                normalizer.__class__.__name__,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(
        self,
        payload: dict,
        provider_type: str,
        company_id: str = "",
    ) -> dict:
        """Ingest a raw webhook payload.

        1. Determine category from provider_type
        2. Find matching normalizer (specific → generic → webhook)
        3. Normalize payload into IncomingMessage
        4. Deduplicate
        5. Return result

        Never raises (BC-008).  Always returns a dict with at minimum:
            {"status": IngestionStatus, "error": str | None}

        Args:
            payload: Raw webhook payload (dict).
            provider_type: Provider identifier, e.g. "twilio_sms", "sendgrid",
                           "shopify", or any arbitrary string.
            company_id: Mandatory company scope (BC-001).

        Returns:
            dict with keys: status, message (IncomingMessage if successful),
            error (str if failed), provider_type, category.
        """
        result: Dict[str, Any] = {
            "status": IngestionStatus.ERROR,
            "message": None,
            "error": None,
            "provider_type": provider_type,
            "category": None,
        }

        try:
            # BC-001: company_id is required
            if not company_id or not str(company_id).strip():
                result["status"] = IngestionStatus.VALIDATION_ERROR
                result["error"] = "company_id is required (BC-001)"
                self._stats["total_validation_errors"] += 1
                logger.warning("Ingestion rejected: missing company_id")
                return result

            # Validate payload
            if not isinstance(payload, dict):
                result["status"] = IngestionStatus.VALIDATION_ERROR
                result["error"] = f"payload must be a dict, got {type(payload).__name__}"
                self._stats["total_validation_errors"] += 1
                logger.warning("Ingestion rejected: payload is not a dict")
                return result

            # Step 1: Detect category
            category = self._detect_category(provider_type)
            result["category"] = category

            # Step 2: Get best normalizer
            normalizer = self._get_normalizer(provider_type, category)
            if normalizer is None:
                # Ultimate fallback — this should never happen because
                # GenericWebhookNormalizer is always registered
                result["status"] = IngestionStatus.ERROR
                result["error"] = f"No normalizer found for provider_type={provider_type}, category={category}"
                self._stats["total_errors"] += 1
                logger.error("No normalizer found: provider=%s, category=%s", provider_type, category)
                return result

            # Step 3: Normalize (BC-008: normalizer.normalize() never raises)
            normalized = normalizer.normalize(payload, company_id)

            # Check if normalizer itself reported an error
            if normalized.get("status") == "error":
                result["status"] = IngestionStatus.ERROR
                result["error"] = normalized.get("error", "Normalizer returned error status")
                result["category"] = normalized.get("category", category)
                self._stats["total_errors"] += 1
                logger.error(
                    "Normalizer error: provider=%s, error=%s",
                    provider_type,
                    result["error"],
                )
                return result

            # Step 4: Build IncomingMessage from normalized dict
            normalized["company_id"] = company_id  # Enforce BC-001
            message = IncomingMessage.from_dict(normalized)

            # Step 5: Deduplicate (BC-003)
            dedup_key = f"{company_id}:{message.message_id}"
            if self._deduplicate(message.message_id, company_id):
                result["status"] = IngestionStatus.DUPLICATE
                result["message"] = message
                result["error"] = f"Duplicate message_id: {message.message_id}"
                self._stats["total_duplicates"] += 1
                logger.info(
                    "Duplicate detected: company=%s, message_id=%s",
                    company_id,
                    message.message_id,
                )
                return result

            # Mark as seen
            self._seen_messages[dedup_key] = time.time()

            # Step 6: Success
            result["status"] = IngestionStatus.INGESTED
            result["message"] = message
            self._stats["total_ingested"] += 1
            logger.info(
                "Ingested: company=%s, provider=%s, category=%s, message_id=%s",
                company_id,
                provider_type,
                category,
                message.message_id,
            )
            return result

        except Exception as exc:
            # BC-008: NEVER crash
            result["status"] = IngestionStatus.ERROR
            result["error"] = f"Unexpected ingestion error: {exc}"
            self._stats["total_errors"] += 1
            logger.exception(
                "Unexpected ingestion error: provider=%s, company=%s",
                provider_type,
                company_id,
            )
            return result

    def register_normalizer(self, provider_type: str, normalizer: BaseNormalizer) -> None:
        """Register a provider-specific normalizer.

        Args:
            provider_type: Unique provider identifier, e.g. "twilio_sms".
            normalizer: A BaseNormalizer subclass instance.
        """
        if not isinstance(normalizer, BaseNormalizer):
            logger.warning(
                "Ignoring non-BaseNormalizer registration for provider=%s",
                provider_type,
            )
            return

        self._normalizers[provider_type] = normalizer
        logger.info(
            "Registered provider normalizer: provider=%s, class=%s",
            provider_type,
            normalizer.__class__.__name__,
        )

    def get_stats(self) -> Dict[str, int]:
        """Return ingestion statistics."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset ingestion statistics to zero."""
        for key in self._stats:
            self._stats[key] = 0

    def clear_dedup_cache(self) -> None:
        """Clear the deduplication cache."""
        self._seen_messages.clear()
        logger.info("Dedup cache cleared")

    def cleanup_dedup_cache(self) -> int:
        """Remove expired entries from the dedup cache.

        Returns the number of entries removed.
        """
        now = time.time()
        cutoff = now - self._dedup_ttl_seconds
        expired_keys = [k for k, ts in self._seen_messages.items() if ts < cutoff]
        for key in expired_keys:
            del self._seen_messages[key]
        if expired_keys:
            logger.info("Cleaned %d expired dedup entries", len(expired_keys))
        return len(expired_keys)

    # ------------------------------------------------------------------
    # Category detection
    # ------------------------------------------------------------------

    def _detect_category(self, provider_type: str) -> str:
        """Detect channel category from provider_type string.

        Uses keyword heuristics to map provider names to categories.
        Unknown providers default to "webhook".

        Examples:
            "twilio_sms"   → "sms"
            "sendgrid"     → "email"
            "slack"        → "chat"
            "twilio_voice" → "voice"
            "shopify"      → "webhook"
            "unknown_xyz"  → "webhook"
        """
        pt_lower = provider_type.lower().strip()

        # Direct category matches
        if pt_lower in ("email", "mail"):
            return ChannelCategory.EMAIL.value
        if pt_lower in ("sms", "text"):
            return ChannelCategory.SMS.value
        if pt_lower in ("voice", "phone", "call", "telephony"):
            return ChannelCategory.VOICE.value
        if pt_lower in ("chat", "im", "messaging"):
            return ChannelCategory.CHAT.value
        if pt_lower in ("webhook", "event", "callback"):
            return ChannelCategory.WEBHOOK.value

        # Provider-specific heuristics
        # SMS providers
        sms_keywords = ["sms", "twilio_sms", "vonage_sms", "nexmo", "messagebird",
                         "sns_sms", "sins", "textmagic", "clicksend", "bulk"]
        for kw in sms_keywords:
            if kw in pt_lower:
                return ChannelCategory.SMS.value

        # Email providers
        email_keywords = ["email", "mail", "sendgrid", "mailgun", "postmark",
                           "ses", "smtp", "mandrill", "sparkpost", "mailjet",
                           "brevo", "resend"]
        for kw in email_keywords:
            if kw in pt_lower:
                return ChannelCategory.EMAIL.value

        # Voice providers
        voice_keywords = ["voice", "call", "phone", "telephony", "sip",
                          "twilio_voice", "vonage_voice", "nexmo_voice",
                          "connect", "ringcentral", "dialpad"]
        for kw in voice_keywords:
            if kw in pt_lower:
                return ChannelCategory.VOICE.value

        # Chat providers
        chat_keywords = ["chat", "slack", "discord", "teams", "whatsapp",
                          "telegram", "intercom", "messenger", "line",
                          "wechat", "viber", "zendesk_chat", "freshchat"]
        for kw in chat_keywords:
            if kw in pt_lower:
                return ChannelCategory.CHAT.value

        # Webhook / business-event providers
        webhook_keywords = ["shopify", "stripe", "github", "hubspot",
                            "zendesk", "jira", "notion", "airtable",
                            "zapier", "webhook", "event", "callback"]
        for kw in webhook_keywords:
            if kw in pt_lower:
                return ChannelCategory.WEBHOOK.value

        # Default: webhook (the ultimate fallback)
        logger.info(
            "Could not detect category for provider_type=%s, defaulting to webhook",
            provider_type,
        )
        return ChannelCategory.WEBHOOK.value

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _deduplicate(self, message_id: str, company_id: str) -> bool:
        """Check if message was already ingested.

        BC-001: Dedup is scoped to company_id so the same message_id
        in different companies is NOT a duplicate.

        Returns True if duplicate (already seen).
        """
        if not message_id or not message_id.strip():
            return False

        dedup_key = f"{company_id}:{message_id}"
        return dedup_key in self._seen_messages

    # ------------------------------------------------------------------
    # Normalizer selection
    # ------------------------------------------------------------------

    def _get_normalizer(
        self,
        provider_type: str,
        category: str,
    ) -> Optional[BaseNormalizer]:
        """Get the best normalizer for this provider/category combo.

        Priority:
            1. Provider-specific normalizer (if registered)
            2. Category-specific generic normalizer
            3. GenericWebhookNormalizer (ultimate fallback)

        Returns None only if absolutely no normalizer is available
        (which should never happen since builtins are always registered).
        """
        # Priority 1: Provider-specific
        normalizer = self._normalizers.get(provider_type)
        if normalizer is not None:
            logger.debug("Using provider-specific normalizer: %s", provider_type)
            return normalizer

        # Priority 2: Category-specific generic
        normalizer = self._generic_normalizers.get(category)
        if normalizer is not None:
            logger.debug("Using generic normalizer: category=%s", category)
            return normalizer

        # Priority 3: GenericWebhookNormalizer (ultimate fallback)
        webhook_normalizer = self._generic_normalizers.get(ChannelCategory.WEBHOOK.value)
        if webhook_normalizer is not None:
            logger.debug("Using ultimate fallback: GenericWebhookNormalizer")
            return webhook_normalizer

        # This should never happen
        logger.error("No normalizer available at all!")
        return None

    # ------------------------------------------------------------------
    # Batch ingestion
    # ------------------------------------------------------------------

    def ingest_batch(
        self,
        payloads: List[dict],
        provider_type: str,
        company_id: str = "",
    ) -> List[dict]:
        """Ingest a batch of payloads.

        Each payload is processed independently so that a failure in one
        NEVER breaks the others (BC-008).

        Returns a list of result dicts, one per payload, in order.
        """
        results: List[dict] = []
        for i, payload in enumerate(payloads):
            try:
                result = self.ingest(payload, provider_type, company_id)
                results.append(result)
            except Exception as exc:
                # BC-008: Individual failure never breaks batch
                results.append({
                    "status": IngestionStatus.ERROR,
                    "message": None,
                    "error": f"Batch item {i} failed: {exc}",
                    "provider_type": provider_type,
                    "category": None,
                })
                logger.exception(
                    "Batch item %d failed: provider=%s, company=%s",
                    i, provider_type, company_id,
                )
        return results
