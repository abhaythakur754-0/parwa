"""PARWA Phase 3 Ingestion — Configurable field extraction.

FieldMapping maps provider-specific JSON paths (dot-notation) to the
universal IncomingMessage field names.  This allows ANY provider — even
ones we've never seen — to be ingested by simply providing a mapping,
without writing a custom normalizer class.

The PROVIDER_FIELD_MAPPINGS dict ships with pre-built mappings for
well-known providers (Twilio, SendGrid, Shopify, Slack, etc.).
"""

from typing import Any, Dict, List, Optional


class FieldMapping:
    """Configurable field extraction for ANY provider.

    Usage::

        mapping = FieldMapping({
            "message_id": "MessageSid",
            "sender_phone": "From",
            "body": "Body",
        })
        fields = mapping.extract_all(payload)
    """

    # Universal field names that map to IncomingMessage attributes
    UNIVERSAL_FIELDS: List[str] = [
        "message_id", "company_id", "sender_id", "sender_name",
        "sender_email", "sender_phone", "recipient_id", "subject",
        "body", "conversation_id", "timestamp",
    ]

    def __init__(self, mapping: Optional[Dict[str, str]] = None):
        """
        Args:
            mapping: Dict of {universal_field_name: provider_field_path}.
                     Paths support dot-notation for nested objects,
                     e.g. "customer.email" → payload["customer"]["email"].
        """
        self.mapping: Dict[str, str] = mapping or {}

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract(self, payload: dict, field_name: str, default: Any = "") -> Any:
        """Extract a single field from payload using the configured mapping.

        If *field_name* has a mapping, the mapped path is used.
        Otherwise, *field_name* itself is used as the path (direct key).
        """
        source_path = self.mapping.get(field_name, field_name)
        return self._get_nested(payload, source_path, default)

    def extract_all(self, payload: dict) -> Dict[str, Any]:
        """Extract all mapped fields from payload.

        Returns a dict keyed by UNIVERSAL_FIELDS with extracted values.
        Missing values default to empty string.
        """
        result: Dict[str, Any] = {}
        for field_name in self.UNIVERSAL_FIELDS:
            result[field_name] = self.extract(payload, field_name)
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_nested(self, data: dict, path: str, default: Any = "") -> Any:
        """Get a value from nested dict using dot-notation path.

        Examples::

            _get_nested({"a": {"b": 1}}, "a.b")       → 1
            _get_nested({"a": {"b": 1}}, "a.c", "x")  → "x"
            _get_nested({"x": 5}, "x")                 → 5
        """
        keys = str(path).split(".")
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return default
            if current is None:
                return default
        return current


# ----------------------------------------------------------------------
# Pre-built mappings for known providers
# ----------------------------------------------------------------------

PROVIDER_FIELD_MAPPINGS: Dict[str, Dict[str, str]] = {
    # ── SMS providers ──────────────────────────────────────────────────
    "twilio_sms": {
        "message_id": "MessageSid",
        "sender_phone": "From",
        "recipient_id": "To",
        "body": "Body",
        "timestamp": "DateSent",
    },
    "vonage_sms": {
        "message_id": "messageId",
        "sender_phone": "msisdn",
        "recipient_id": "to",
        "body": "text",
        "timestamp": "message-timestamp",
    },
    "messagebird_sms": {
        "message_id": "id",
        "sender_phone": "originator",
        "recipient_id": "recipients.items.0.recipient",
        "body": "body",
        "timestamp": "createdDatetime",
    },

    # ── Voice providers ────────────────────────────────────────────────
    "twilio_voice": {
        "message_id": "CallSid",
        "sender_phone": "From",
        "recipient_id": "To",
        "body": "SpeechResult",
        "conversation_id": "CallSid",
        "timestamp": "StartTime",
    },
    "vonage_voice": {
        "message_id": "conversation_uuid",
        "sender_phone": "from",
        "recipient_id": "to",
        "body": "speech.results.0.text",
        "conversation_id": "conversation_uuid",
        "timestamp": "timestamp",
    },

    # ── Email providers ────────────────────────────────────────────────
    "sendgrid": {
        "message_id": "sg_message_id",
        "sender_email": "from",
        "recipient_id": "to",
        "subject": "subject",
        "body": "text",
    },
    "mailgun": {
        "message_id": "message-headers.1.1",
        "sender_email": "sender",
        "recipient_id": "recipient",
        "subject": "subject",
        "body": "stripped-text",
        "timestamp": "timestamp",
    },
    "postmark": {
        "message_id": "MessageID",
        "sender_email": "From",
        "recipient_id": "To",
        "subject": "Subject",
        "body": "TextBody",
        "timestamp": "Date",
    },
    "ses": {
        "message_id": "mail.messageId",
        "sender_email": "mail.source",
        "recipient_id": "mail.destination.0",
        "subject": "mail.commonHeaders.subject",
        "body": "content",
        "timestamp": "mail.commonHeaders.date",
    },

    # ── Chat providers ─────────────────────────────────────────────────
    "slack": {
        "message_id": "event.ts",
        "sender_id": "event.user",
        "body": "event.text",
        "conversation_id": "event.channel",
        "timestamp": "event.ts",
    },
    "discord": {
        "message_id": "id",
        "sender_id": "author.id",
        "sender_name": "author.username",
        "body": "content",
        "conversation_id": "channel_id",
        "timestamp": "timestamp",
    },
    "teams": {
        "message_id": "id",
        "sender_id": "from.id",
        "sender_name": "from.name",
        "body": "text",
        "conversation_id": "conversation.id",
        "timestamp": "timestamp",
    },
    "whatsapp": {
        "message_id": "messages.0.id",
        "sender_phone": "contacts.0.wa_id",
        "sender_name": "contacts.0.profile.name",
        "body": "messages.0.text.body",
        "conversation_id": "messages.0.id",
        "timestamp": "messages.0.timestamp",
    },

    # ── Webhook / business-event providers ─────────────────────────────
    "shopify": {
        "message_id": "id",
        "sender_email": "customer.email",
        "sender_name": "customer.first_name",
        "body": "note",
        "timestamp": "created_at",
    },
    "stripe": {
        "message_id": "id",
        "sender_email": "data.object.customer_email",
        "body": "type",
        "timestamp": "created",
    },
    "github": {
        "message_id": "action",
        "sender_id": "sender.id",
        "sender_name": "sender.login",
        "body": "action",
        "timestamp": "repository.updated_at",
    },
    "hubspot": {
        "message_id": "objectId",
        "sender_email": "properties.email.value",
        "sender_name": "properties.firstname.value",
        "body": "properties.message.value",
        "timestamp": "occurredAt",
    },
    "zendesk": {
        "message_id": "id",
        "sender_email": "requester.email",
        "sender_name": "requester.name",
        "subject": "subject",
        "body": "description",
        "timestamp": "created_at",
    },
}
