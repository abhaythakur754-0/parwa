"""PARWA Phase 3 Ingestion — Generic fallback normalizers.

Five category-level normalizers that work with ANY provider in their
category.  Each uses FieldMapping with best-effort field extraction
and heuristics so that unknown providers are handled gracefully.

Fallback chain (orchestrator):
    1. Provider-specific normalizer  (if registered)
    2. Category-specific generic     (these classes)
    3. GenericWebhookNormalizer      (ultimate fallback)

BC-008: All normalizers wrap their logic in try/except so a failure
        NEVER crashes the pipeline.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseNormalizer
from .field_mapping import FieldMapping, PROVIDER_FIELD_MAPPINGS


# ======================================================================
# Helper — shared across all generic normalizers
# ======================================================================

def _best_effort_extract(
    payload: dict,
    candidates: List[str],
    default: str = "",
) -> str:
    """Try each candidate key in order; return the first non-empty value."""
    for key in candidates:
        val = payload.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return default


def _generate_stable_id(payload: dict, company_id: str) -> str:
    """Produce a stable hash-based ID for dedup when no native ID exists."""
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(f"{company_id}:{raw}".encode()).hexdigest()[:32]


# ======================================================================
# GenericEmailNormalizer
# ======================================================================

class GenericEmailNormalizer(BaseNormalizer):
    """Fallback normalizer for ANY email provider.

    Tries common email field names in a priority order, then falls back
    to FieldMapping if a known provider mapping exists, and finally to
    brute-force extraction heuristics.
    """

    CATEGORY = "email"
    PROVIDER = "generic"

    # Common field names across email providers (checked in order)
    _ID_FIELDS = ["message_id", "Message-ID", "sg_message_id", "id", "mail.messageId"]
    _FROM_FIELDS = ["from", "sender", "From", "envelope.from", "mail.source"]
    _TO_FIELDS = ["to", "recipient", "To", "envelope.to", "mail.destination"]
    _SUBJECT_FIELDS = ["subject", "Subject", "mail.commonHeaders.subject"]
    _BODY_FIELDS = ["text", "body", "Body", "TextBody", "stripped-text", "html", "content"]
    _TIMESTAMP_FIELDS = ["timestamp", "date", "Date", "created_at", "mail.commonHeaders.date"]

    def _extract_fields(self, payload: dict, company_id: str) -> dict:
        # Try known provider mapping first (if we can identify the provider)
        mapping_result = self._try_known_mapping(payload)
        if mapping_result:
            return self._finalize(mapping_result, payload, company_id)

        # Brute-force best-effort extraction
        sender_email = _best_effort_extract(payload, self._FROM_FIELDS)
        subject = _best_effort_extract(payload, self._SUBJECT_FIELDS)
        body = _best_effort_extract(payload, self._BODY_FIELDS)

        result = {
            "message_id": _best_effort_extract(payload, self._ID_FIELDS) or _generate_stable_id(payload, company_id),
            "company_id": company_id,
            "channel": self.CATEGORY,
            "provider": self.PROVIDER,
            "sender_email": self._sanitize_field(sender_email),
            "sender_name": self._sanitize_field(payload.get("from_name", "")),
            "recipient_id": self._sanitize_field(_best_effort_extract(payload, self._TO_FIELDS)),
            "subject": self._sanitize_field(subject, max_length=500),
            "body": self._sanitize_field(body),
            "timestamp": _best_effort_extract(payload, self._TIMESTAMP_FIELDS) or datetime.now(timezone.utc).isoformat(),
            "raw_payload": payload,
        }
        return self._finalize(result, payload, company_id)

    def _try_known_mapping(self, payload: dict) -> Optional[dict]:
        """Try all known email provider mappings to see if one fits."""
        email_providers = ["sendgrid", "mailgun", "postmark", "ses"]
        for provider_key in email_providers:
            mapping_def = PROVIDER_FIELD_MAPPINGS.get(provider_key)
            if not mapping_def:
                continue
            fm = FieldMapping(mapping_def)
            # Quick heuristic: if the mapping extracts a message_id, it's a match
            msg_id = fm.extract(payload, "message_id")
            if msg_id and str(msg_id).strip():
                extracted = fm.extract_all(payload)
                extracted["provider"] = provider_key
                return extracted
        return None

    def _finalize(self, result: dict, payload: dict, company_id: str) -> dict:
        """Fill in missing fields and compute sentiment/priority."""
        result.setdefault("message_id", _generate_stable_id(payload, company_id))
        result.setdefault("company_id", company_id)
        result.setdefault("channel", self.CATEGORY)
        result.setdefault("provider", self.PROVIDER)
        result.setdefault("sender_email", "")
        result.setdefault("sender_name", "")
        result.setdefault("sender_phone", "")
        result.setdefault("sender_id", "")
        result.setdefault("recipient_id", "")
        result.setdefault("subject", "")
        result.setdefault("body", "")
        result.setdefault("conversation_id", "")
        result.setdefault("raw_payload", payload)
        result.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        # Detect priority & sentiment
        body_text = str(result.get("body", "")) + " " + str(result.get("subject", ""))
        result["priority"] = self._detect_priority(payload)
        result["sentiment"] = self._detect_sentiment(body_text)
        result["metadata"] = result.get("metadata", {})

        return result


# ======================================================================
# GenericSMSNormalizer
# ======================================================================

class GenericSMSNormalizer(BaseNormalizer):
    """Fallback normalizer for ANY SMS provider.

    Twilio, Vonage/Nexmo, MessageBird, or any unknown SMS gateway.
    """

    CATEGORY = "sms"
    PROVIDER = "generic"

    _ID_FIELDS = ["MessageSid", "messageId", "id", "message_id", "Sid"]
    _FROM_FIELDS = ["From", "from", "msisdn", "originator", "sender"]
    _TO_FIELDS = ["To", "to", "recipient", "destination"]
    _BODY_FIELDS = ["Body", "body", "text", "message", "content"]
    _TIMESTAMP_FIELDS = ["DateSent", "message-timestamp", "createdDatetime", "timestamp", "date"]

    def _extract_fields(self, payload: dict, company_id: str) -> dict:
        # Try known SMS provider mappings
        mapping_result = self._try_known_mapping(payload)
        if mapping_result:
            return self._finalize(mapping_result, payload, company_id)

        sender_phone = _best_effort_extract(payload, self._FROM_FIELDS)
        body = _best_effort_extract(payload, self._BODY_FIELDS)

        result = {
            "message_id": _best_effort_extract(payload, self._ID_FIELDS) or _generate_stable_id(payload, company_id),
            "company_id": company_id,
            "channel": self.CATEGORY,
            "provider": self.PROVIDER,
            "sender_phone": self._sanitize_field(sender_phone),
            "sender_name": self._sanitize_field(payload.get("FromName", payload.get("from_name", ""))),
            "recipient_id": self._sanitize_field(_best_effort_extract(payload, self._TO_FIELDS)),
            "body": self._sanitize_field(body),
            "timestamp": _best_effort_extract(payload, self._TIMESTAMP_FIELDS) or datetime.now(timezone.utc).isoformat(),
            "raw_payload": payload,
        }
        return self._finalize(result, payload, company_id)

    def _try_known_mapping(self, payload: dict) -> Optional[dict]:
        sms_providers = ["twilio_sms", "vonage_sms", "messagebird_sms"]
        for provider_key in sms_providers:
            mapping_def = PROVIDER_FIELD_MAPPINGS.get(provider_key)
            if not mapping_def:
                continue
            fm = FieldMapping(mapping_def)
            msg_id = fm.extract(payload, "message_id")
            if msg_id and str(msg_id).strip():
                extracted = fm.extract_all(payload)
                extracted["provider"] = provider_key
                return extracted
        return None

    def _finalize(self, result: dict, payload: dict, company_id: str) -> dict:
        result.setdefault("message_id", _generate_stable_id(payload, company_id))
        result.setdefault("company_id", company_id)
        result.setdefault("channel", self.CATEGORY)
        result.setdefault("provider", self.PROVIDER)
        result.setdefault("sender_phone", "")
        result.setdefault("sender_name", "")
        result.setdefault("sender_email", "")
        result.setdefault("sender_id", "")
        result.setdefault("recipient_id", "")
        result.setdefault("subject", "")
        result.setdefault("body", "")
        result.setdefault("conversation_id", "")
        result.setdefault("raw_payload", payload)
        result.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        body_text = str(result.get("body", ""))
        result["priority"] = self._detect_priority(payload)
        result["sentiment"] = self._detect_sentiment(body_text)
        result["metadata"] = result.get("metadata", {})

        # SMS-specific: detect urgency keywords
        if result["priority"] == "normal" and result["sentiment"] == "angry":
            result["priority"] = "high"

        return result


# ======================================================================
# GenericVoiceNormalizer
# ======================================================================

class GenericVoiceNormalizer(BaseNormalizer):
    """Fallback normalizer for ANY voice/telephony provider.

    Twilio Voice, Vonage Voice, Amazon Connect, etc.
    """

    CATEGORY = "voice"
    PROVIDER = "generic"

    _ID_FIELDS = ["CallSid", "call_id", "id", "conversation_uuid", "message_id"]
    _FROM_FIELDS = ["From", "from", "caller_id", "caller", "ani"]
    _TO_FIELDS = ["To", "to", "dialed_number", "dnis", "destination"]
    _TRANSCRIPT_FIELDS = ["SpeechResult", "transcript", "Transcript", "speech.results.0.text", "body"]
    _TIMESTAMP_FIELDS = ["StartTime", "timestamp", "start_time", "created_at", "date"]

    def _extract_fields(self, payload: dict, company_id: str) -> dict:
        mapping_result = self._try_known_mapping(payload)
        if mapping_result:
            return self._finalize(mapping_result, payload, company_id)

        sender_phone = _best_effort_extract(payload, self._FROM_FIELDS)
        transcript = _best_effort_extract(payload, self._TRANSCRIPT_FIELDS)
        call_id = _best_effort_extract(payload, self._ID_FIELDS)

        result = {
            "message_id": call_id or _generate_stable_id(payload, company_id),
            "company_id": company_id,
            "channel": self.CATEGORY,
            "provider": self.PROVIDER,
            "sender_phone": self._sanitize_field(sender_phone),
            "sender_name": self._sanitize_field(payload.get("CallerName", payload.get("caller_name", ""))),
            "recipient_id": self._sanitize_field(_best_effort_extract(payload, self._TO_FIELDS)),
            "body": self._sanitize_field(transcript),
            "conversation_id": call_id or "",
            "timestamp": _best_effort_extract(payload, self._TIMESTAMP_FIELDS) or datetime.now(timezone.utc).isoformat(),
            "raw_payload": payload,
        }
        return self._finalize(result, payload, company_id)

    def _try_known_mapping(self, payload: dict) -> Optional[dict]:
        voice_providers = ["twilio_voice", "vonage_voice"]
        for provider_key in voice_providers:
            mapping_def = PROVIDER_FIELD_MAPPINGS.get(provider_key)
            if not mapping_def:
                continue
            fm = FieldMapping(mapping_def)
            msg_id = fm.extract(payload, "message_id")
            if msg_id and str(msg_id).strip():
                extracted = fm.extract_all(payload)
                extracted["provider"] = provider_key
                return extracted
        return None

    def _finalize(self, result: dict, payload: dict, company_id: str) -> dict:
        result.setdefault("message_id", _generate_stable_id(payload, company_id))
        result.setdefault("company_id", company_id)
        result.setdefault("channel", self.CATEGORY)
        result.setdefault("provider", self.PROVIDER)
        result.setdefault("sender_phone", "")
        result.setdefault("sender_name", "")
        result.setdefault("sender_email", "")
        result.setdefault("sender_id", "")
        result.setdefault("recipient_id", "")
        result.setdefault("subject", "")
        result.setdefault("body", "")
        result.setdefault("conversation_id", result.get("message_id", ""))
        result.setdefault("raw_payload", payload)
        result.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        body_text = str(result.get("body", ""))
        result["priority"] = self._detect_priority(payload)
        result["sentiment"] = self._detect_sentiment(body_text)

        # Voice-specific: calls with no transcript are low priority
        if not body_text.strip() and result["priority"] == "normal":
            result["priority"] = "low"

        # Voice metadata
        result["metadata"] = result.get("metadata", {})
        for meta_key in ("CallDuration", "duration", "RecordingUrl", "recording_url",
                          "CallStatus", "status", "Direction", "direction"):
            val = payload.get(meta_key)
            if val is not None:
                result["metadata"][meta_key] = val

        return result


# ======================================================================
# GenericChatNormalizer
# ======================================================================

class GenericChatNormalizer(BaseNormalizer):
    """Fallback normalizer for ANY chat/messaging provider.

    Slack, Discord, Microsoft Teams, WhatsApp, Telegram, Intercom, etc.
    """

    CATEGORY = "chat"
    PROVIDER = "generic"

    _ID_FIELDS = ["event.ts", "id", "message_id", "event_id", "messages.0.id"]
    _USER_FIELDS = ["event.user", "user", "author.id", "from.id", "sender_id", "messages.0.from"]
    _NAME_FIELDS = ["author.username", "from.name", "user_name", "sender_name", "contacts.0.profile.name"]
    _BODY_FIELDS = ["event.text", "text", "content", "body", "message", "messages.0.text.body"]
    _CHANNEL_FIELDS = ["event.channel", "channel_id", "conversation.id", "channel", "chat_id"]
    _TIMESTAMP_FIELDS = ["event.ts", "timestamp", "created_at", "date", "messages.0.timestamp"]

    def _extract_fields(self, payload: dict, company_id: str) -> dict:
        mapping_result = self._try_known_mapping(payload)
        if mapping_result:
            return self._finalize(mapping_result, payload, company_id)

        # Best-effort extraction using candidate lists
        msg_id = self._extract_nested_any(payload, self._ID_FIELDS)
        sender_id = self._extract_nested_any(payload, self._USER_FIELDS)
        sender_name = self._extract_nested_any(payload, self._NAME_FIELDS)
        body = self._extract_nested_any(payload, self._BODY_FIELDS)
        conversation_id = self._extract_nested_any(payload, self._CHANNEL_FIELDS)
        timestamp = self._extract_nested_any(payload, self._TIMESTAMP_FIELDS)

        result = {
            "message_id": msg_id or _generate_stable_id(payload, company_id),
            "company_id": company_id,
            "channel": self.CATEGORY,
            "provider": self.PROVIDER,
            "sender_id": self._sanitize_field(sender_id),
            "sender_name": self._sanitize_field(sender_name),
            "body": self._sanitize_field(body),
            "conversation_id": self._sanitize_field(conversation_id),
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "raw_payload": payload,
        }
        return self._finalize(result, payload, company_id)

    def _try_known_mapping(self, payload: dict) -> Optional[dict]:
        chat_providers = ["slack", "discord", "teams", "whatsapp"]
        for provider_key in chat_providers:
            mapping_def = PROVIDER_FIELD_MAPPINGS.get(provider_key)
            if not mapping_def:
                continue
            fm = FieldMapping(mapping_def)
            msg_id = fm.extract(payload, "message_id")
            if msg_id and str(msg_id).strip():
                extracted = fm.extract_all(payload)
                extracted["provider"] = provider_key
                return extracted
        return None

    def _extract_nested_any(self, payload: dict, candidates: List[str]) -> str:
        """Try each candidate (supports dot-notation) and return first match."""
        for path in candidates:
            keys = path.split(".")
            current = payload
            found = True
            for key in keys:
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    found = False
                    break
                if current is None:
                    found = False
                    break
            if found and current is not None and str(current).strip():
                return str(current).strip()
        return ""

    def _finalize(self, result: dict, payload: dict, company_id: str) -> dict:
        result.setdefault("message_id", _generate_stable_id(payload, company_id))
        result.setdefault("company_id", company_id)
        result.setdefault("channel", self.CATEGORY)
        result.setdefault("provider", self.PROVIDER)
        result.setdefault("sender_id", "")
        result.setdefault("sender_name", "")
        result.setdefault("sender_email", "")
        result.setdefault("sender_phone", "")
        result.setdefault("recipient_id", "")
        result.setdefault("subject", "")
        result.setdefault("body", "")
        result.setdefault("conversation_id", "")
        result.setdefault("raw_payload", payload)
        result.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        body_text = str(result.get("body", ""))
        result["priority"] = self._detect_priority(payload)
        result["sentiment"] = self._detect_sentiment(body_text)

        # Chat-specific metadata
        result["metadata"] = result.get("metadata", {})
        for meta_key in ("thread_ts", "parent_user_id", "subtype",
                          "channel_type", "team_id", "bot_id"):
            val = payload.get(meta_key)
            if val is not None:
                result["metadata"][meta_key] = val
        # Also check event.* metadata for Slack-style payloads
        event = payload.get("event") or {}
        if isinstance(event, dict):
            for meta_key in ("thread_ts", "parent_user_id", "subtype",
                              "channel_type", "bot_id"):
                val = event.get(meta_key)
                if val is not None:
                    result["metadata"][meta_key] = val

        return result


# ======================================================================
# GenericWebhookNormalizer
# ======================================================================

class GenericWebhookNormalizer(BaseNormalizer):
    """Ultimate fallback normalizer for ANY business-event webhook.

    Shopify, Stripe, GitHub, HubSpot, Zendesk, or any unknown provider.
    This is the last line of defense — it will ALWAYS produce a valid
    IncomingMessage dict, even for completely unknown payloads.

    BC-008: This normalizer MUST NEVER raise.
    """

    CATEGORY = "webhook"
    PROVIDER = "generic"

    _ID_FIELDS = ["id", "object_id", "event_id", "objectId", "message_id"]
    _EMAIL_FIELDS = ["email", "customer.email", "data.object.customer_email",
                      "sender", "from", "requester.email"]
    _NAME_FIELDS = ["name", "customer.first_name", "sender.login",
                     "from.name", "requester.name", "username"]
    _BODY_FIELDS = ["note", "body", "text", "message", "description",
                     "content", "type", "action", "event"]
    _TIMESTAMP_FIELDS = ["created_at", "timestamp", "occurredAt",
                          "updated_at", "date", "repository.updated_at"]

    def _extract_fields(self, payload: dict, company_id: str) -> dict:
        mapping_result = self._try_known_mapping(payload)
        if mapping_result:
            return self._finalize(mapping_result, payload, company_id)

        # Brute-force extraction
        message_id = _best_effort_extract(payload, self._ID_FIELDS)
        sender_email = _best_effort_extract(payload, self._EMAIL_FIELDS)
        sender_name = _best_effort_extract(payload, self._NAME_FIELDS)
        body = _best_effort_extract(payload, self._BODY_FIELDS)
        timestamp = _best_effort_extract(payload, self._TIMESTAMP_FIELDS)

        # If body is empty, serialize the whole payload as the body
        if not body.strip():
            body = json.dumps(payload, default=str, indent=2)[:2000]

        # Try to infer a subject from event type
        subject = self._infer_subject(payload)

        result = {
            "message_id": message_id or _generate_stable_id(payload, company_id),
            "company_id": company_id,
            "channel": self.CATEGORY,
            "provider": self.PROVIDER,
            "sender_email": self._sanitize_field(sender_email),
            "sender_name": self._sanitize_field(sender_name),
            "body": self._sanitize_field(body),
            "subject": self._sanitize_field(subject, max_length=500),
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "raw_payload": payload,
        }
        return self._finalize(result, payload, company_id)

    def _try_known_mapping(self, payload: dict) -> Optional[dict]:
        webhook_providers = ["shopify", "stripe", "github", "hubspot", "zendesk"]
        for provider_key in webhook_providers:
            mapping_def = PROVIDER_FIELD_MAPPINGS.get(provider_key)
            if not mapping_def:
                continue
            fm = FieldMapping(mapping_def)
            msg_id = fm.extract(payload, "message_id")
            if msg_id and str(msg_id).strip():
                extracted = fm.extract_all(payload)
                extracted["provider"] = provider_key
                return extracted
        return None

    def _infer_subject(self, payload: dict) -> str:
        """Infer a subject line from webhook event type or action."""
        # Check common event-type fields
        for key in ("event", "type", "action", "topic", "event_type",
                     "webhook_type", "X-GitHub-Event"):
            val = payload.get(key)
            if val and str(val).strip():
                return f"[Webhook] {val}"

        # Check nested headers
        headers = payload.get("headers") or {}
        if isinstance(headers, dict):
            for key in ("X-GitHub-Event", "X-Shopify-Topic", "X-Stripe-Event"):
                val = headers.get(key)
                if val and str(val).strip():
                    return f"[Webhook] {val}"

        return "[Webhook] Unstructured Event"

    def _finalize(self, result: dict, payload: dict, company_id: str) -> dict:
        result.setdefault("message_id", _generate_stable_id(payload, company_id))
        result.setdefault("company_id", company_id)
        result.setdefault("channel", self.CATEGORY)
        result.setdefault("provider", self.PROVIDER)
        result.setdefault("sender_email", "")
        result.setdefault("sender_name", "")
        result.setdefault("sender_id", "")
        result.setdefault("sender_phone", "")
        result.setdefault("recipient_id", "")
        result.setdefault("subject", "[Webhook] Event")
        result.setdefault("body", "")
        result.setdefault("conversation_id", "")
        result.setdefault("raw_payload", payload)
        result.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        body_text = str(result.get("body", "")) + " " + str(result.get("subject", ""))
        result["priority"] = self._detect_priority(payload)
        result["sentiment"] = self._detect_sentiment(body_text)

        # Webhook-specific metadata
        result["metadata"] = result.get("metadata", {})
        for meta_key in ("event", "type", "action", "topic", "version",
                          "webhook_id", "delivery_id", "live_mode"):
            val = payload.get(meta_key)
            if val is not None:
                result["metadata"][meta_key] = val

        return result
