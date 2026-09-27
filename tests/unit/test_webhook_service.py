"""
Tests for Webhook Service (BC-003, BC-001)

Tests cover:
- Idempotency: duplicate event_id returns same result
- Company_id validation (BC-001)
- Status transitions: pending -> processed, pending -> failed
- Payload storage and retrieval
- Error message on failure
"""

import pytest

from backend.app.services.webhook_service import (
    get_webhook_event,
    mark_webhook_processed,
    process_webhook,
    _validate_company_id,
)
from database.base import SessionLocal


class TestValidateCompanyId:
    """BC-001: company_id validation tests."""

    def test_valid_company_id(self):
        """Normal UUID company_id passes."""
        assert _validate_company_id(
            "550e8400-e29b-41d4-a716-446655440000",
        ) is True

    def test_empty_company_id(self):
        """Empty string fails."""
        assert _validate_company_id("") is False

    def test_none_company_id(self):
        """None fails."""
        assert _validate_company_id(None) is False

    def test_whitespace_only_company_id(self):
        """Whitespace-only fails."""
        assert _validate_company_id("   ") is False

    def test_too_long_company_id(self):
        """Over 128 chars fails."""
        long_id = "a" * 129
        assert _validate_company_id(long_id) is False

    def test_max_length_company_id(self):
        """Exactly 128 chars passes."""
        valid_id = "a" * 128
        assert _validate_company_id(valid_id) is True

    def test_control_characters(self):
        """Control characters fail."""
        assert _validate_company_id("id\x00bad") is False
        assert _validate_company_id("id\tbad") is False
        assert _validate_company_id("id\nbad") is False

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is OK."""
        assert _validate_company_id("  valid_id  ") is True


class TestProcessWebhook:
    """Webhook event processing tests."""

    def _clean_db(self):
        """Clean up webhook_events table."""
        db = SessionLocal()
        try:
            from database.models.webhook_event import WebhookEvent
            db.query(WebhookEvent).delete()
            db.commit()
        finally:
            db.close()

    def test_process_new_event(self):
        """New webhook event is created with pending status."""
        self._clean_db()
        result = process_webhook(
            provider="paddle",
            event_id="evt_001",
            event_type="payment.completed",
            payload={"amount": 100},
            company_id="comp_001",
        )
        assert result["status"] == "pending"
        assert result["duplicate"] is False
        assert "id" in result

    def test_idempotency_duplicate_event(self):
        """Duplicate (provider, event_id) returns existing record."""
        self._clean_db()
        r1 = process_webhook(
            provider="paddle",
            event_id="evt_dup",
            event_type="payment.completed",
            payload={"amount": 100},
            company_id="comp_001",
        )
        r2 = process_webhook(
            provider="paddle",
            event_id="evt_dup",
            event_type="payment.completed",
            payload={"amount": 200},  # different payload
            company_id="comp_001",
        )
        assert r1["duplicate"] is False
        assert r2["duplicate"] is True
        assert r1["id"] == r2["id"]

    def test_different_provider_same_event_id(self):
        """Same event_id but different provider creates new record."""
        self._clean_db()
        r1 = process_webhook(
            provider="paddle",
            event_id="evt_001",
            event_type="payment.completed",
            payload={},
            company_id="comp_001",
        )
        r2 = process_webhook(
            provider="shopify",
            event_id="evt_001",
            event_type="order.created",
            payload={},
            company_id="comp_001",
        )
        assert r1["duplicate"] is False
        assert r2["duplicate"] is False
        assert r1["id"] != r2["id"]

    def test_invalid_company_id_raises(self):
        """Invalid company_id raises ValueError."""
        self._clean_db()
        with pytest.raises(ValueError, match="company_id"):
            process_webhook(
                provider="paddle",
                event_id="evt_002",
                event_type="test",
                payload={},
                company_id="",
            )

    def test_missing_required_fields_raises(self):
        """Missing provider raises ValueError."""
        self._clean_db()
        with pytest.raises(ValueError, match="Invalid provider"):
            process_webhook(
                provider="",
                event_id="evt_002",
                event_type="test",
                payload={},
                company_id="comp_001",
            )


class TestGetWebhookEvent:
    """Webhook event retrieval tests."""

    def _clean_db(self):
        db = SessionLocal()
        try:
            from database.models.webhook_event import WebhookEvent
            db.query(WebhookEvent).delete()
            db.commit()
        finally:
            db.close()

    def test_get_existing_event(self):
        """Can retrieve a previously created event."""
        self._clean_db()
        created = process_webhook(
            provider="paddle",
            event_id="evt_get",
            event_type="test",
            payload={"key": "value"},
            company_id="comp_001",
        )
        event = get_webhook_event(created["id"])
        assert event["provider"] == "paddle"
        assert event["event_id"] == "evt_get"
        assert event["payload"] == {"key": "value"}
        assert event["company_id"] == "comp_001"

    def test_get_nonexistent_event_raises(self):
        """Non-existent event raises ValueError."""
        self._clean_db()
        with pytest.raises(ValueError, match="not found"):
            get_webhook_event("nonexistent-id")


class TestMarkWebhookProcessed:
    """Webhook event status transition tests."""

    def _clean_db(self):
        db = SessionLocal()
        try:
            from database.models.webhook_event import WebhookEvent
            db.query(WebhookEvent).delete()
            db.commit()
        finally:
            db.close()

    def test_mark_processed(self):
        """Event transitions from pending to processed."""
        self._clean_db()
        created = process_webhook(
            provider="paddle",
            event_id="evt_proc",
            event_type="test",
            payload={},
            company_id="comp_001",
        )
        result = mark_webhook_processed(
            created["id"], "processed",
        )
        assert result["status"] == "processed"
        assert result["completed_at"] is not None

    def test_mark_failed_with_error(self):
        """Event transitions from pending to failed with error."""
        self._clean_db()
        created = process_webhook(
            provider="paddle",
            event_id="evt_fail",
            event_type="test",
            payload={},
            company_id="comp_001",
        )
        result = mark_webhook_processed(
            created["id"], "failed",
            error="Connection timeout",
        )
        assert result["status"] == "failed"
        assert result["error_message"] == "Connection timeout"
        assert result["completed_at"] is not None

    def test_invalid_status_raises(self):
        """Invalid status raises ValueError."""
        self._clean_db()
        with pytest.raises(ValueError, match="status must be"):
            mark_webhook_processed("any-id", "invalid")
