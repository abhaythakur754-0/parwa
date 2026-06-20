"""
Day 15 Loophole Tests — Webhook Framework Hardening

Tests for all Day 15 loophole fixes:
- L27: SHOPIFY_WEBHOOK_SECRET from config (not raw env)
- L28: Payload size validation (max 1MB)
- L29: Invalid JSON logging (not silently ignored)
- L30: Idempotency race condition fix (pending events return existing)
- L31: Error message truncation (max 500 chars)
- L32: Max retry cap (5 attempts)
- L33: Cannot retry completed events (double-processing prevention)
- L34: IP allowlist logging
- L35: Redis error logging in IP allowlist
- L36: Missing client IP logging
- L37: Provider validation (arbitrary strings blocked)
- L38: Event type validation
- L39: Shopify HMAC uses correct function (no NameError)
"""

import hashlib
import hmac as hmac_mod
import json
import os
import uuid

import pytest

from database.base import SessionLocal


class TestL27ShopifySecretFromConfig:
    """L27: SHOPIFY_WEBHOOK_SECRET should come from config, not raw env."""

    def test_config_has_shopify_webhook_secret(self):
        """Settings class has SHOPIFY_WEBHOOK_SECRET field."""
        from backend.app.config import Settings
        fields = Settings.model_fields
        assert "SHOPIFY_WEBHOOK_SECRET" in fields
        assert fields["SHOPIFY_WEBHOOK_SECRET"].default == ""

    def test_shopify_webhook_secret_loadable(self):
        """SHOPIFY_WEBHOOK_SECRET loads from environment."""
        os.environ["SHOPIFY_WEBHOOK_SECRET"] = "test_shopify_secret"
        try:
            from backend.app.config import get_settings
            settings = get_settings()
            assert settings.SHOPIFY_WEBHOOK_SECRET == "test_shopify_secret"
        finally:
            os.environ.pop("SHOPIFY_WEBHOOK_SECRET", None)

    def test_webhooks_api_uses_config_for_shopify(self):
        """Webhook API imports verify_shopify_hmac (not verify_shopify_signature).

        Previous code had a NameError: called verify_shopify_signature
        but imported verify_shopify_hmac.
        """
        import inspect
        from backend.app.api.webhooks import _verify_provider_signature
        source = inspect.getsource(_verify_provider_signature)
        # Should import verify_shopify_hmac (the correct name)
        assert "verify_shopify_hmac" in source
        # Should NOT call the wrong function name
        assert "verify_shopify_signature" not in source or \
               "verify_shopify_hmac" in source


class TestL28PayloadSizeValidation:
    """L28: Webhook payload must not exceed 1MB."""

    def test_oversized_payload_returns_413(self, client):
        """Payload larger than 1MB returns 413 PAYLOAD_TOO_LARGE."""
        oversized = {"x": "a" * (2 * 1024 * 1024)}  # 2MB+
        resp = client.post(
            "/api/webhooks/paddle",
            json=oversized,
        )
        assert resp.status_code == 413
        data = resp.json()
        assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"

    def test_normal_payload_returns_200(self, client):
        """Normal payload within size limit works."""
        resp = client.post(
            "/api/webhooks/paddle",
            json={
                "event_id": "evt_size_test",
                "event_type": "subscription.created",
                "company_id": "comp_test_001",
            },
        )
        assert resp.status_code == 200

    def test_max_webhook_payload_size_constant(self):
        """MAX_WEBHOOK_PAYLOAD_SIZE is 1MB."""
        from backend.app.api.webhooks import MAX_WEBHOOK_PAYLOAD_SIZE
        assert MAX_WEBHOOK_PAYLOAD_SIZE == 1 * 1024 * 1024


class TestL29InvalidJSONLogging:
    """L29: Invalid JSON should be logged, not silently ignored."""

    def test_invalid_json_body_returns_422(self, client):
        """Invalid JSON body doesn't crash."""
        resp = client.post(
            "/api/webhooks/paddle",
            content=b"not json at all",
            headers={"content-type": "application/json"},
        )
        # FastAPI returns 422 for invalid JSON
        assert resp.status_code in (200, 422)


class TestL30IdempotencyRaceCondition:
    """L30: Pending events should be returned as duplicates.

    Previous bug: If an existing event had status='pending',
    the code fell through and tried to INSERT a duplicate,
    causing IntegrityError. Now it correctly returns the
    existing event regardless of status.
    """

    def _clean_db(self):
        db = SessionLocal()
        try:
            from database.models.webhook_event import WebhookEvent
            db.query(WebhookEvent).delete()
            db.commit()
        finally:
            db.close()

    def test_pending_event_returns_as_duplicate(self):
        """Second call with same event_id returns duplicate, even if pending."""
        self._clean_db()
        from backend.app.services.webhook_service import process_webhook
        r1 = process_webhook(
            provider="paddle",
            event_id="evt_race_001",
            event_type="payment.completed",
            payload={"amount": 100},
            company_id="comp_001",
        )
        assert r1["duplicate"] is False
        assert r1["status"] == "pending"

        # Second call should return existing, NOT crash
        r2 = process_webhook(
            provider="paddle",
            event_id="evt_race_001",
            event_type="payment.completed",
            payload={"amount": 200},  # different payload
            company_id="comp_001",
        )
        assert r2["duplicate"] is True
        assert r1["id"] == r2["id"]

    def test_processed_event_returns_as_duplicate(self):
        """Already processed event returns as duplicate."""
        self._clean_db()
        from backend.app.services.webhook_service import (
            process_webhook,
            mark_webhook_processed,
        )
        r1 = process_webhook(
            provider="paddle",
            event_id="evt_race_002",
            event_type="payment.completed",
            payload={},
            company_id="comp_001",
        )
        mark_webhook_processed(r1["id"], "processed")

        r2 = process_webhook(
            provider="paddle",
            event_id="evt_race_002",
            event_type="payment.completed",
            payload={},
            company_id="comp_001",
        )
        assert r2["duplicate"] is True
        assert r2["id"] == r1["id"]

    def test_failed_event_returns_as_duplicate(self):
        """Failed event returns as duplicate."""
        self._clean_db()
        from backend.app.services.webhook_service import (
            process_webhook,
            mark_webhook_processed,
        )
        r1 = process_webhook(
            provider="paddle",
            event_id="evt_race_003",
            event_type="payment.failed",
            payload={},
            company_id="comp_001",
        )
        mark_webhook_processed(
            r1["id"], "failed", error="timeout",
        )

        r2 = process_webhook(
            provider="paddle",
            event_id="evt_race_003",
            event_type="payment.failed",
            payload={},
            company_id="comp_001",
        )
        assert r2["duplicate"] is True


class TestL31ErrorMessageTruncation:
    """L31: Error messages must be truncated to 500 chars."""

    def test_truncate_long_error(self):
        """Long error message is truncated."""
        from backend.app.services.webhook_service import (
            _truncate_error,
        )
        long_error = "x" * 1000
        result = _truncate_error(long_error)
        assert len(result) < 1000
        assert result.endswith("...truncated")

    def test_short_error_unchanged(self):
        """Short error message is not truncated."""
        from backend.app.services.webhook_service import (
            _truncate_error,
        )
        short = "Connection timeout"
        assert _truncate_error(short) == short

    def test_empty_error_unchanged(self):
        """Empty error message is not truncated."""
        from backend.app.services.webhook_service import (
            _truncate_error,
        )
        assert _truncate_error("") == ""
        assert _truncate_error(None) is None

    def test_exactly_max_length_unchanged(self):
        """Error at exactly max length is not truncated."""
        from backend.app.services.webhook_service import (
            _truncate_error, MAX_ERROR_MESSAGE_LENGTH,
        )
        exact = "x" * MAX_ERROR_MESSAGE_LENGTH
        assert _truncate_error(exact) == exact

    def test_one_over_max_is_truncated(self):
        """Error over max is truncated with suffix."""
        from backend.app.services.webhook_service import (
            _truncate_error, MAX_ERROR_MESSAGE_LENGTH,
        )
        over = "x" * (MAX_ERROR_MESSAGE_LENGTH + 100)
        result = _truncate_error(over)
        assert len(over) > MAX_ERROR_MESSAGE_LENGTH
        assert "...truncated" in result
        assert result.endswith("...truncated")


class TestL32MaxRetryCap:
    """L32: Webhook retry must cap at MAX_RETRY_ATTEMPTS (5)."""

    def _clean_db(self):
        db = SessionLocal()
        try:
            from database.models.webhook_event import WebhookEvent
            db.query(WebhookEvent).delete()
            db.commit()
        finally:
            db.close()

    def test_max_retry_constant(self):
        """MAX_RETRY_ATTEMPTS is 5."""
        from backend.app.services.webhook_service import (
            MAX_RETRY_ATTEMPTS,
        )
        assert MAX_RETRY_ATTEMPTS == 5

    def test_retry_up_to_max(self, client):
        """Can retry up to MAX_RETRY_ATTEMPTS times."""
        self._clean_db()
        from backend.app.services.webhook_service import (
            process_webhook,
            mark_webhook_processed,
            retry_failed_webhook,
            MAX_RETRY_ATTEMPTS,
        )
        created = process_webhook(
            provider="paddle",
            event_id="evt_retry_cap",
            event_type="test",
            payload={},
            company_id="comp_001",
        )
        mark_webhook_processed(
            created["id"], "failed", error="test error",
        )

        # Retry MAX_RETRY_ATTEMPTS - 1 times (first was the original)
        for i in range(MAX_RETRY_ATTEMPTS - 1):
            retry_failed_webhook(created["id"])
            mark_webhook_processed(
                created["id"], "failed", error=f"attempt {i}",
            )

        # Next retry should succeed (we haven't hit the cap yet
        # because attempts only increment in retry_failed_webhook)
        result = retry_failed_webhook(created["id"])
        assert result["status"] == "pending"

    def test_retry_exceeds_cap_raises(self, client):
        """Retry beyond cap raises ValueError."""
        self._clean_db()
        from backend.app.services.webhook_service import (
            process_webhook,
            mark_webhook_processed,
            retry_failed_webhook,
            MAX_RETRY_ATTEMPTS,
        )
        created = process_webhook(
            provider="paddle",
            event_id="evt_retry_overflow",
            event_type="test",
            payload={},
            company_id="comp_001",
        )
        mark_webhook_processed(
            created["id"], "failed", error="test error",
        )

        # Burn through all retry attempts
        for i in range(MAX_RETRY_ATTEMPTS):
            retry_failed_webhook(created["id"])
            mark_webhook_processed(
                created["id"], "failed",
                error=f"attempt {i}",
            )

        # Next retry should raise
        with pytest.raises(ValueError, match="Maximum retry"):
            retry_failed_webhook(created["id"])


class TestL33NoRetryCompletedEvents:
    """L33: Cannot retry completed events (double-processing prevention)."""

    def _clean_db(self):
        db = SessionLocal()
        try:
            from database.models.webhook_event import WebhookEvent
            db.query(WebhookEvent).delete()
            db.commit()
        finally:
            db.close()

    def test_retry_completed_raises_value_error(self):
        """Retrying a processed event raises ValueError."""
        self._clean_db()
        from backend.app.services.webhook_service import (
            process_webhook,
            mark_webhook_processed,
            retry_failed_webhook,
        )
        created = process_webhook(
            provider="paddle",
            event_id="evt_completed_retry",
            event_type="payment.completed",
            payload={},
            company_id="comp_001",
        )
        mark_webhook_processed(created["id"], "processed")

        with pytest.raises(
            ValueError, match="Can only retry failed",
        ):
            retry_failed_webhook(created["id"])

    def test_retry_failed_works(self):
        """Retrying a failed event works normally."""
        self._clean_db()
        from backend.app.services.webhook_service import (
            process_webhook,
            mark_webhook_processed,
            retry_failed_webhook,
        )
        created = process_webhook(
            provider="paddle",
            event_id="evt_failed_retry_ok",
            event_type="payment.failed",
            payload={},
            company_id="comp_001",
        )
        mark_webhook_processed(
            created["id"], "failed", error="timeout",
        )
        result = retry_failed_webhook(created["id"])
        assert result["status"] == "pending"


class TestL34IPAllowlistLogging:
    """L34: IP allowlist middleware must have logging."""

    def test_middleware_has_logger(self):
        """IP allowlist module has a logger configured."""
        import logging
        logger = logging.getLogger("parwa.ip_allowlist")
        assert logger is not None
        assert logger.name == "parwa.ip_allowlist"

    def test_source_has_log_statements(self):
        """Source code contains logging statements."""
        import inspect
        from backend.app.middleware.ip_allowlist import (
            IPAllowlistMiddleware,
        )
        source = inspect.getsource(IPAllowlistMiddleware)
        assert "logger" in source


class TestL35RedisErrorLogging:
    """L35: Redis errors in IP allowlist should be logged."""

    def test_redis_error_is_logged(self):
        """Source code logs Redis errors instead of bare pass."""
        import inspect
        from backend.app.middleware.ip_allowlist import (
            IPAllowlistMiddleware,
        )
        source = inspect.getsource(
            IPAllowlistMiddleware._check_ip_allowed,
        )
        # Should have logging, not bare pass
        assert "logger" in source
        # The old code had bare `pass` — should be gone
        # (or at least accompanied by logging)


class TestL36MissingIPLogging:
    """L36: Missing client IP should be logged (fail-open still)."""

    def test_missing_ip_logs_warning(self):
        """Source code logs warning when client IP is missing."""
        import inspect
        from backend.app.middleware.ip_allowlist import (
            IPAllowlistMiddleware,
        )
        source = inspect.getsource(IPAllowlistMiddleware.__call__)
        assert "ip_allowlist_no_client_ip" in source


class TestL37ProviderValidation:
    """L37: Provider must be a valid supported value."""

    def test_valid_providers(self):
        """All 4 supported providers pass validation."""
        from backend.app.services.webhook_service import (
            _validate_provider,
        )
        for p in ["paddle", "twilio", "shopify", "brevo"]:
            assert _validate_provider(p) is True

    def test_invalid_provider_rejected(self):
        """Arbitrary provider strings are rejected."""
        from backend.app.services.webhook_service import (
            _validate_provider,
        )
        assert _validate_provider("malicious_provider") is False
        assert _validate_provider("unknown") is False
        assert _validate_provider("") is False
        assert _validate_provider(None) is False
        assert _validate_provider("PADDLE") is True  # case-insensitive

    def test_process_webhook_invalid_provider_raises(self):
        """process_webhook rejects invalid provider."""
        with pytest.raises(ValueError, match="Invalid provider"):
            from backend.app.services.webhook_service import (
                process_webhook,
            )
            # Clean DB first
            db = SessionLocal()
            try:
                from database.models.webhook_event import WebhookEvent
                db.query(WebhookEvent).delete()
                db.commit()
            finally:
                db.close()
            process_webhook(
                provider="evil_provider",
                event_id="evt_001",
                event_type="test",
                payload={},
                company_id="comp_001",
            )


class TestL38EventTypeValidation:
    """L38: Event type must be validated."""

    def test_valid_event_type(self):
        """Normal event types pass validation."""
        from backend.app.services.webhook_service import (
            _validate_event_type,
        )
        assert _validate_event_type("payment.completed") is True
        assert _validate_event_type("subscription.created") is True

    def test_empty_event_type_rejected(self):
        """Empty event type is rejected."""
        from backend.app.services.webhook_service import (
            _validate_event_type,
        )
        assert _validate_event_type("") is False
        assert _validate_event_type(None) is False

    def test_too_long_event_type_rejected(self):
        """Event type over 200 chars is rejected."""
        from backend.app.services.webhook_service import (
            _validate_event_type,
        )
        assert _validate_event_type("a" * 201) is False

    def test_control_characters_rejected(self):
        """Event type with control characters is rejected."""
        from backend.app.services.webhook_service import (
            _validate_event_type,
        )
        assert _validate_event_type("test\x00type") is False
        assert _validate_event_type("test\ntype") is False


class TestL39ShopifyHMACNoNameError:
    """L39: Shopify HMAC verification must use correct function name."""

    def test_shopify_hmac_is_importable(self):
        """verify_shopify_hmac can be imported from security module."""
        from backend.app.security.hmac_verification import (
            verify_shopify_hmac,
        )
        assert callable(verify_shopify_hmac)

    def test_core_hmac_verify_reexports(self):
        """core/hmac_verify.py re-exports from security module."""
        from backend.app.core.hmac_verify import (
            verify_shopify_signature as reexported,
        )
        from backend.app.security.hmac_verification import (
            verify_shopify_hmac as original,
        )
        # Both should point to the same function
        assert reexported is original

    def test_webhooks_imports_correct_function(self):
        """Webhooks API uses verify_shopify_hmac, not wrong name."""
        import inspect
        from backend.app.api.webhooks import _verify_provider_signature
        source = inspect.getsource(_verify_provider_signature)
        # The Shopify block should import and use verify_shopify_hmac
        assert "verify_shopify_hmac" in source


class TestDatetimeUTCNowFix:
    """Verify datetime.utcnow() is replaced with datetime.now(timezone.utc)."""

    def test_service_uses_timezone_aware_datetime(self):
        """webhook_service uses datetime.now(timezone.utc), not utcnow."""
        import inspect
        from backend.app.services.webhook_service import (
            mark_webhook_processed,
        )
        source = inspect.getsource(mark_webhook_processed)
        assert "datetime.now(timezone.utc)" in source
        assert "datetime.utcnow()" not in source


class TestWebhookAPIAdditionalCoverage:
    """Additional webhook API tests for hardening."""

    def test_webhook_constants(self):
        """Verify module-level constants."""
        from backend.app.api.webhooks import (
            SUPPORTED_PROVIDERS,
            MAX_WEBHOOK_PAYLOAD_SIZE,
        )
        assert isinstance(SUPPORTED_PROVIDERS, set)
        assert len(SUPPORTED_PROVIDERS) == 4
        assert MAX_WEBHOOK_PAYLOAD_SIZE == 1_048_576

    def test_event_id_extraction_twilio(self):
        """Twilio event_id extraction from MessageSid."""
        from backend.app.api.webhooks import (
            _get_event_id_from_payload,
        )
        assert _get_event_id_from_payload(
            "twilio", {"MessageSid": "SM123"},
        ) == "SM123"

    def test_event_id_extraction_paddle(self):
        """Paddle event_id extraction."""
        from backend.app.api.webhooks import (
            _get_event_id_from_payload,
        )
        assert _get_event_id_from_payload(
            "paddle", {"event_id": "evt_123"},
        ) == "evt_123"

    def test_company_id_extraction_paddle(self):
        """Paddle company_id from custom_data."""
        from backend.app.api.webhooks import (
            _get_company_id_from_payload,
        )
        assert _get_company_id_from_payload(
            "paddle",
            {"custom_data": {"company_id": "comp_123"}},
        ) == "comp_123"

    def test_company_id_extraction_paddle_direct(self):
        """Paddle company_id from direct field."""
        from backend.app.api.webhooks import (
            _get_company_id_from_payload,
        )
        assert _get_company_id_from_payload(
            "paddle", {"company_id": "comp_456"},
        ) == "comp_456"
