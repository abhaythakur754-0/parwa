"""PARWA Phase 3 Ingestion — Base normalizer for all channels.

Category-first design: normalizers are organized by CHANNEL CATEGORY
(email, sms, voice, chat, webhook), NOT by provider.  A provider-specific
normalizer overrides PROVIDER; a generic fallback leaves it as "generic".
"""

from typing import Any, Dict


class BaseNormalizer:
    """Base class for all channel normalizers.

    Subclasses MUST override:
        CATEGORY  — the ChannelCategory string (e.g. "email", "sms")
        PROVIDER  — the provider name (e.g. "twilio", "sendgrid") or "generic"
        _extract_fields() — provider-specific field extraction logic

    The public ``normalize()`` method wraps _extract_fields in a try/except
    so that a broken normalizer NEVER crashes the pipeline (BC-008).
    """

    CATEGORY: str = ""   # Override in subclass — e.g. "email"
    PROVIDER: str = ""   # Override in subclass — e.g. "twilio_sms" or "generic"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize(self, payload: dict, company_id: str = "") -> dict:
        """Normalize a raw webhook payload into IncomingMessage-compatible dict.

        Returns dict with keys matching IncomingMessage dataclass.
        Never raises (BC-008) — returns error dict on failure.
        """
        try:
            result = self._extract_fields(payload, company_id)
            # Guarantee category & provider are stamped
            result.setdefault("channel", self.CATEGORY)
            result.setdefault("provider", self.PROVIDER)
            result.setdefault("company_id", company_id)
            return result
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "provider": self.PROVIDER,
                "category": self.CATEGORY,
                "company_id": company_id,
                "channel": self.CATEGORY,
            }

    # ------------------------------------------------------------------
    # Override points
    # ------------------------------------------------------------------

    def _extract_fields(self, payload: dict, company_id: str) -> dict:
        """Override in subclass to extract provider-specific fields.

        Must return a dict whose keys are a subset of IncomingMessage fields.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _extract_fields()"
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _sanitize_field(self, value: Any, max_length: int = 10000) -> str:
        """Sanitize a field value: strip whitespace, limit length."""
        if value is None:
            return ""
        text = str(value).strip()
        return text[:max_length] if len(text) > max_length else text

    def _detect_priority(self, payload: dict) -> str:
        """Detect message priority from payload.

        Checks common priority / importance flags across providers.
        Returns one of: "low", "normal", "high", "urgent".
        """
        # Check explicit priority/importance fields
        for key in ("priority", "importance", "urgency", "X-Priority"):
            val = payload.get(key)
            if val is not None:
                val_lower = str(val).lower().strip()
                if val_lower in ("urgent", "emergency", "1", "highest", "critical"):
                    return "urgent"
                if val_lower in ("high", "important", "2"):
                    return "high"
                if val_lower in ("low", "5", "lowest"):
                    return "low"

        # Check headers dict if present
        headers = payload.get("headers") or payload.get("Headers") or {}
        if isinstance(headers, dict):
            for hdr_key in ("X-Priority", "Importance", "X-MSMail-Priority"):
                hdr_val = headers.get(hdr_key, "")
                if hdr_val:
                    return self._detect_priority({hdr_key: hdr_val})

        return "normal"

    def _detect_sentiment(self, text: str) -> str:
        """Detect basic sentiment from text content.

        Uses keyword heuristics — not ML — for zero-dependency operation.
        Returns one of: "positive", "neutral", "negative", "angry".
        """
        if not text:
            return "neutral"

        text_lower = text.lower()

        # Angry — strongest signal, checked first
        angry_words = [
            "angry", "furious", "unacceptable", "terrible", "worst",
            "hate", "refund now", "speak to manager", "ripoff", "scam",
            "lawyer", "sue", "complaint", "disgusted", "outraged",
        ]
        for word in angry_words:
            if word in text_lower:
                return "angry"

        # Negative
        negative_words = [
            "disappointed", "frustrated", "bad", "poor", "broken",
            "failed", "error", "problem", "issue", "bug", "not working",
            "doesn't work", "never", "unhappy", "dissatisfied",
        ]
        neg_count = sum(1 for w in negative_words if w in text_lower)
        if neg_count >= 2:
            return "negative"

        # Positive
        positive_words = [
            "great", "awesome", "excellent", "love", "amazing",
            "thank you", "perfect", "wonderful", "fantastic", "appreciate",
        ]
        pos_count = sum(1 for w in positive_words if w in text_lower)
        if pos_count >= 2:
            return "positive"

        # If mixed or neutral
        if neg_count > pos_count:
            return "negative"
        if pos_count > neg_count:
            return "positive"

        return "neutral"

    def _generate_message_id(self, payload: dict, company_id: str) -> str:
        """Generate a stable message ID when the payload doesn't provide one.

        Uses a hash of key fields so the same payload always produces the
        same ID — important for deduplication.
        """
        import hashlib
        import json

        # Try to find something unique in the payload
        id_candidates = []
        for key in ("id", "message_id", "MessageSid", "CallSid", "event_id",
                     "event.ts", "sg_message_id"):
            val = payload.get(key)
            if val:
                id_candidates.append(str(val))

        # Fallback: hash the whole payload
        if not id_candidates:
            raw = json.dumps(payload, sort_keys=True, default=str)
            digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
            id_candidates.append(digest)

        raw_str = f"{company_id}:{':'.join(id_candidates)}"
        return hashlib.sha256(raw_str.encode()).hexdigest()[:32]

    def _extract_timestamp(self, payload: dict) -> str:
        """Extract or generate an ISO-8601 timestamp from payload."""
        from datetime import datetime, timezone

        for key in ("timestamp", "created_at", "date", "DateSent",
                     "StartTime", "received_at", "sent_at", "time"):
            val = payload.get(key)
            if val:
                return str(val)

        return datetime.now(timezone.utc).isoformat()

    def can_handle(self, payload: dict) -> bool:
        """Check if this normalizer can handle the given payload.

        Provider-specific normalizers override this to inspect the payload
        for provider signatures.  Generic normalizers always return True.
        """
        return True
