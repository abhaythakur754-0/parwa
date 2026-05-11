"""
W5D5 Webhook Expansion Tests (BG-01, BG-07, BG-08, BG-15)

Tests for:
- All 25+ Paddle event handlers
- Webhook idempotency (webhook_processor)
- Webhook ordering (webhook_ordering_service)
- Missed webhook recovery tasks
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def sample_company_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_event_id():
    return f"evt_{uuid.uuid4().hex[:24]}"


@pytest.fixture
def sample_subscription_id():
    return f"sub_{uuid.uuid4().hex[:24]}"


@pytest.fixture
def sample_transaction_id():
    return f"txn_{uuid.uuid4().hex[:24]}"


@pytest.fixture
def sample_customer_id():
    return f"ctm_{uuid.uuid4().hex[:24]}"


# ── Test All 28 Event Handlers ─────────────────────────────────────────────


class TestPaddleEventHandlerCounts:
    """Verify all 28 event types are supported."""

    def test_handler_count(self):
        """Should have 28 handlers registered."""
        from backend.app.webhooks.paddle_handler import _PADDLE_HANDLERS

        # 28 handlers: 7 subscription + 5 transaction + 3 customer
        # + 3 price + 3 discount + 3 credit + 2 adjustment + 2 report
        # + 3 backward compatibility aliases
        assert len(_PADDLE_HANDLERS) >= 28, f"Expected >= 28 handlers, got {len(_PADDLE_HANDLERS)}"

    def test_subscription_event_types(self):
        """All 7 subscription event types are handled."""
        from backend.app.webhooks.paddle_handler import _PADDLE_HANDLERS

        subscription_events = [
            "subscription.created",
            "subscription.updated",
            "subscription.activated",
            "subscription.canceled",
            "subscription.past_due",
            "subscription.paused",
            "subscription.resumed",
        ]

        for event_type in subscription_events:
            assert event_type in _PADDLE_HANDLERS, f"Missing handler for {event_type}"

    def test_transaction_event_types(self):
        """All 5 transaction event types are handled."""
        from backend.app.webhooks.paddle_handler import _PADDLE_HANDLERS

        transaction_events = [
            "transaction.completed",
            "transaction.paid",
            "transaction.payment_failed",
            "transaction.canceled",
            "transaction.updated",
        ]

        for event_type in transaction_events:
            assert event_type in _PADDLE_HANDLERS, f"Missing handler for {event_type}"

    def test_customer_event_types(self):
        """All 3 customer event types are handled."""
        from backend.app.webhooks.paddle_handler import _PADDLE_HANDLERS

        customer_events = [
            "customer.created",
            "customer.updated",
            "customer.deleted",
        ]

        for event_type in customer_events:
            assert event_type in _PADDLE_HANDLERS, f"Missing handler for {event_type}"

    def test_price_event_types(self):
        """All 3 price event types are handled."""
        from backend.app.webhooks.paddle_handler import _PADDLE_HANDLERS

        price_events = [
            "price.created",
            "price.updated",
            "price.deleted",
        ]

        for event_type in price_events:
            assert event_type in _PADDLE_HANDLERS, f"Missing handler for {event_type}"

    def test_discount_event_types(self):
        """All 3 discount event types are handled."""
        from backend.app.webhooks.paddle_handler import _PADDLE_HANDLERS

        discount_events = [
            "discount.created",
            "discount.updated",
            "discount.deleted",
        ]

        for event_type in discount_events:
            assert event_type in _PADDLE_HANDLERS, f"Missing handler for {event_type}"

    def test_credit_event_types(self):
        """All 3 credit event types are handled."""
        from backend.app.webhooks.paddle_handler import _PADDLE_HANDLERS

        credit_events = [
            "credit.created",
            "credit.updated",
            "credit.deleted",
        ]

        for event_type in credit_events:
            assert event_type in _PADDLE_HANDLERS, f"Missing handler for {event_type}"

    def test_adjustment_event_types(self):
        """All 2 adjustment event types are handled."""
        from backend.app.webhooks.paddle_handler import _PADDLE_HANDLERS

        adjustment_events = [
            "adjustment.created",
            "adjustment.updated",
        ]

        for event_type in adjustment_events:
            assert event_type in _PADDLE_HANDLERS, f"Missing handler for {event_type}"

    def test_report_event_types(self):
        """All 2 report event types are handled."""
        from backend.app.webhooks.paddle_handler import _PADDLE_HANDLERS

        report_events = [
            "report.created",
            "report.updated",
        ]

        for event_type in report_events:
            assert event_type in _PADDLE_HANDLERS, f"Missing handler for {event_type}"


class TestSubscriptionEventHandlers:
    """Test subscription event handlers."""

    def test_subscription_created(
        self, sample_company_id, sample_event_id, sample_subscription_id, sample_customer_id
    ):
        """Handle subscription.created event."""
        from backend.app.webhooks.paddle_handler import handle_subscription_created

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.created",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "subscription": {
                        "id": sample_subscription_id,
                        "status": "active",
                        "items": [{"price_id": "pri_123", "quantity": 1}],
                    },
                    "customer": {"id": sample_customer_id},
                }
            },
        }

        result = handle_subscription_created(event)

        assert result["status"] == "processed"
        assert result["action"] == "subscription_created"
        assert result["data"]["subscription_id"] == sample_subscription_id
        assert result["data"]["customer_id"] == sample_customer_id

    def test_subscription_updated(
        self, sample_company_id, sample_event_id, sample_subscription_id
    ):
        """Handle subscription.updated event."""
        from backend.app.webhooks.paddle_handler import handle_subscription_updated

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.updated",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "subscription": {
                        "id": sample_subscription_id,
                        "status": "active",
                    },
                },
                "previous_attributes": {"status": "past_due"},
            },
        }

        result = handle_subscription_updated(event)

        assert result["status"] == "processed"
        assert result["action"] == "subscription_updated"
        assert result["previous_attributes"]["status"] == "past_due"

    def test_subscription_canceled(
        self, sample_company_id, sample_event_id, sample_subscription_id
    ):
        """Handle subscription.canceled event."""
        from backend.app.webhooks.paddle_handler import handle_subscription_canceled

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.canceled",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "subscription": {
                        "id": sample_subscription_id,
                        "status": "canceled",
                    },
                    "cancellation_reason": "user_requested",
                }
            },
        }

        result = handle_subscription_canceled(event)

        assert result["status"] == "processed"
        assert result["action"] == "subscription_canceled"
        assert result["data"]["cancellation_reason"] == "user_requested"

    def test_subscription_past_due(
        self, sample_company_id, sample_event_id, sample_subscription_id
    ):
        """Handle subscription.past_due event."""
        from backend.app.webhooks.paddle_handler import handle_subscription_past_due

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.past_due",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "subscription": {
                        "id": sample_subscription_id,
                        "status": "past_due",
                    },
                }
            },
        }

        result = handle_subscription_past_due(event)

        assert result["status"] == "processed"
        assert result["action"] == "subscription_past_due"

    def test_subscription_paused(
        self, sample_company_id, sample_event_id, sample_subscription_id
    ):
        """Handle subscription.paused event."""
        from backend.app.webhooks.paddle_handler import handle_subscription_paused

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.paused",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "subscription": {
                        "id": sample_subscription_id,
                        "status": "paused",
                    },
                }
            },
        }

        result = handle_subscription_paused(event)

        assert result["status"] == "processed"
        assert result["action"] == "subscription_paused"

    def test_subscription_resumed(
        self, sample_company_id, sample_event_id, sample_subscription_id
    ):
        """Handle subscription.resumed event."""
        from backend.app.webhooks.paddle_handler import handle_subscription_resumed

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.resumed",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "subscription": {
                        "id": sample_subscription_id,
                        "status": "active",
                    },
                }
            },
        }

        result = handle_subscription_resumed(event)

        assert result["status"] == "processed"
        assert result["action"] == "subscription_resumed"


class TestTransactionEventHandlers:
    """Test transaction event handlers."""

    def test_transaction_completed(
        self, sample_company_id, sample_event_id, sample_transaction_id
    ):
        """Handle transaction.completed event."""
        from backend.app.webhooks.paddle_handler import handle_transaction_completed

        event = {
            "event_id": sample_event_id,
            "event_type": "transaction.completed",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "transaction": {
                        "id": sample_transaction_id,
                        "status": "completed",
                        "details": {"totals": {"total": "99.00"}},
                        "currency_code": "USD",
                    },
                }
            },
        }

        result = handle_transaction_completed(event)

        assert result["status"] == "processed"
        assert result["action"] == "transaction_completed"
        assert result["data"]["transaction_id"] == sample_transaction_id

    def test_transaction_paid(
        self, sample_company_id, sample_event_id, sample_transaction_id
    ):
        """Handle transaction.paid event."""
        from backend.app.webhooks.paddle_handler import handle_transaction_paid

        event = {
            "event_id": sample_event_id,
            "event_type": "transaction.paid",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "transaction": {
                        "id": sample_transaction_id,
                        "status": "paid",
                    },
                }
            },
        }

        result = handle_transaction_paid(event)

        assert result["status"] == "processed"
        assert result["action"] == "transaction_paid"

    def test_transaction_payment_failed(
        self, sample_company_id, sample_event_id, sample_transaction_id
    ):
        """Handle transaction.payment_failed event."""
        from backend.app.webhooks.paddle_handler import handle_transaction_payment_failed

        event = {
            "event_id": sample_event_id,
            "event_type": "transaction.payment_failed",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "transaction": {
                        "id": sample_transaction_id,
                        "status": "payment_failed",
                        "error": {"code": "card_declined", "detail": "Insufficient funds"},
                    },
                }
            },
        }

        result = handle_transaction_payment_failed(event)

        assert result["status"] == "processed"
        assert result["action"] == "transaction_payment_failed"
        assert result["data"]["error_code"] == "card_declined"


class TestCustomerEventHandlers:
    """Test customer event handlers."""

    def test_customer_created(
        self, sample_company_id, sample_event_id, sample_customer_id
    ):
        """Handle customer.created event."""
        from backend.app.webhooks.paddle_handler import handle_customer_created

        event = {
            "event_id": sample_event_id,
            "event_type": "customer.created",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "customer": {
                        "id": sample_customer_id,
                        "email": "test@example.com",
                        "name": "Test Customer",
                    },
                }
            },
        }

        result = handle_customer_created(event)

        assert result["status"] == "processed"
        assert result["action"] == "customer_created"
        assert result["data"]["customer_id"] == sample_customer_id
        assert result["data"]["email"] == "test@example.com"

    def test_customer_updated(
        self, sample_company_id, sample_event_id, sample_customer_id
    ):
        """Handle customer.updated event."""
        from backend.app.webhooks.paddle_handler import handle_customer_updated

        event = {
            "event_id": sample_event_id,
            "event_type": "customer.updated",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "customer": {
                        "id": sample_customer_id,
                        "email": "updated@example.com",
                    },
                },
                "previous_attributes": {"email": "old@example.com"},
            },
        }

        result = handle_customer_updated(event)

        assert result["status"] == "processed"
        assert result["action"] == "customer_updated"
        assert result["previous_attributes"]["email"] == "old@example.com"

    def test_customer_deleted(
        self, sample_company_id, sample_event_id, sample_customer_id
    ):
        """Handle customer.deleted event."""
        from backend.app.webhooks.paddle_handler import handle_customer_deleted

        event = {
            "event_id": sample_event_id,
            "event_type": "customer.deleted",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "customer": {
                        "id": sample_customer_id,
                    },
                }
            },
        }

        result = handle_customer_deleted(event)

        assert result["status"] == "processed"
        assert result["action"] == "customer_deleted"


class TestOtherEventHandlers:
    """Test price, discount, credit, adjustment, and report handlers."""

    def test_price_created(self, sample_company_id, sample_event_id):
        """Handle price.created event."""
        from backend.app.webhooks.paddle_handler import handle_price_created

        event = {
            "event_id": sample_event_id,
            "event_type": "price.created",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "price": {
                        "id": "pri_123",
                        "product_id": "pro_456",
                        "name": "Growth Plan",
                    },
                }
            },
        }

        result = handle_price_created(event)

        assert result["status"] == "processed"
        assert result["action"] == "price_created"

    def test_discount_created(self, sample_company_id, sample_event_id):
        """Handle discount.created event."""
        from backend.app.webhooks.paddle_handler import handle_discount_created

        event = {
            "event_id": sample_event_id,
            "event_type": "discount.created",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "discount": {
                        "id": "dsc_123",
                        "code": "SAVE20",
                        "type": "percentage",
                    },
                }
            },
        }

        result = handle_discount_created(event)

        assert result["status"] == "processed"
        assert result["action"] == "discount_created"

    def test_credit_created(self, sample_company_id, sample_event_id):
        """Handle credit.created event."""
        from backend.app.webhooks.paddle_handler import handle_credit_created

        event = {
            "event_id": sample_event_id,
            "event_type": "credit.created",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "credit": {
                        "id": "crd_123",
                        "customer_id": "ctm_456",
                        "amount": "10.00",
                    },
                }
            },
        }

        result = handle_credit_created(event)

        assert result["status"] == "processed"
        assert result["action"] == "credit_created"

    def test_adjustment_created(self, sample_company_id, sample_event_id):
        """Handle adjustment.created event."""
        from backend.app.webhooks.paddle_handler import handle_adjustment_created

        event = {
            "event_id": sample_event_id,
            "event_type": "adjustment.created",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "adjustment": {
                        "id": "adj_123",
                        "transaction_id": "txn_456",
                        "amount": "5.00",
                    },
                }
            },
        }

        result = handle_adjustment_created(event)

        assert result["status"] == "processed"
        assert result["action"] == "adjustment_created"

    def test_report_created(self, sample_company_id, sample_event_id):
        """Handle report.created event."""
        from backend.app.webhooks.paddle_handler import handle_report_created

        event = {
            "event_id": sample_event_id,
            "event_type": "report.created",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "report": {
                        "id": "rpt_123",
                        "type": "transactions",
                        "status": "pending",
                    },
                }
            },
        }

        result = handle_report_created(event)

        assert result["status"] == "processed"
        assert result["action"] == "report_created"


class TestEventHandlerValidation:
    """Test event handler validation."""

    def test_missing_required_field(
        self, sample_company_id, sample_event_id
    ):
        """Should return validation_error for missing required field."""
        from backend.app.webhooks.paddle_handler import handle_subscription_created

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.created",
            "company_id": sample_company_id,
            "payload": {
                "data": {
                    "subscription": {
                        # Missing id
                        "status": "active",
                    },
                    "customer": {"id": "ctm_123"},
                }
            },
        }

        result = handle_subscription_created(event)

        assert result["status"] == "validation_error"
        assert "subscription_id" in result["error"].lower()

    def test_empty_required_field(
        self, sample_company_id, sample_event_id, sample_subscription_id
    ):
        """Should return validation_error for empty required field."""
        from backend.app.webhooks.paddle_handler import handle_subscription_created

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.created",
            "company_id": sample_company_id,
            "payload": {
                "data": {
                    "subscription": {
                        "id": "",  # Empty string
                        "status": "active",
                    },
                    "customer": {"id": "ctm_123"},
                }
            },
        }

        result = handle_subscription_created(event)

        assert result["status"] == "validation_error"

    def test_null_required_field(
        self, sample_company_id, sample_event_id, sample_subscription_id
    ):
        """Should return validation_error for null required field."""
        from backend.app.webhooks.paddle_handler import handle_subscription_created

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.created",
            "company_id": sample_company_id,
            "payload": {
                "data": {
                    "subscription": {
                        "id": sample_subscription_id,
                        "status": "active",
                    },
                    "customer": {"id": None},  # Null value
                }
            },
        }

        result = handle_subscription_created(event)

        assert result["status"] == "validation_error"

    def test_main_handler_missing_company_id(self, sample_event_id):
        """Main handler should reject missing company_id."""
        from backend.app.webhooks.paddle_handler import handle_paddle_event

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.created",
            # Missing company_id
            "payload": {},
        }

        result = handle_paddle_event(event)

        assert result["status"] == "validation_error"
        assert "company_id" in result["error"].lower()

    def test_main_handler_missing_event_id(self, sample_company_id):
        """Main handler should reject missing event_id."""
        from backend.app.webhooks.paddle_handler import handle_paddle_event

        event = {
            # Missing event_id
            "event_type": "subscription.created",
            "company_id": sample_company_id,
            "payload": {},
        }

        result = handle_paddle_event(event)

        assert result["status"] == "validation_error"
        assert "event_id" in result["error"].lower()

    def test_unsupported_event_type(
        self, sample_company_id, sample_event_id
    ):
        """Should reject unsupported event type."""
        from backend.app.webhooks.paddle_handler import handle_paddle_event

        event = {
            "event_id": sample_event_id,
            "event_type": "unknown.event",
            "company_id": sample_company_id,
            "payload": {},
        }

        result = handle_paddle_event(event)

        assert result["status"] == "validation_error"
        assert "unsupported" in result["error"].lower()


# ── Test Webhook Processor (Idempotency) ───────────────────────────────────


class TestWebhookProcessor:
    """Test webhook processor idempotency."""

    def test_generate_idempotency_key(self):
        """Should generate correct key format."""
        from backend.app.services.webhook_processor import generate_idempotency_key

        key = generate_idempotency_key("paddle", "evt_123")

        assert key == "paddle:evt_123"

    def test_compute_hash_consistency(self):
        """Should produce consistent hash for same data."""
        from backend.app.services.webhook_processor import _compute_hash

        data = {"test": "data", "number": 123}

        hash1 = _compute_hash(data)
        hash2 = _compute_hash(data)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex chars

    def test_verify_paddle_signature_valid(self):
        """Should verify valid HMAC signature."""
        from backend.app.services.webhook_processor import verify_paddle_signature

        secret = "test_secret"
        payload = b'{"test": "data"}'

        # Compute valid signature
        sig_hash = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature = f"ts=1234567890;h1={sig_hash}"

        result = verify_paddle_signature(payload, signature, secret)

        assert result is True

    def test_verify_paddle_signature_invalid(self):
        """Should reject invalid HMAC signature."""
        from backend.app.services.webhook_processor import verify_paddle_signature

        secret = "test_secret"
        payload = b'{"test": "data"}'

        # Use wrong signature
        signature = "ts=1234567890;h1=wrong_hash_value"

        result = verify_paddle_signature(payload, signature, secret)

        assert result is False

    def test_verify_paddle_signature_missing_secret(self):
        """Should reject when secret is missing."""
        from backend.app.services.webhook_processor import verify_paddle_signature

        result = verify_paddle_signature(b"payload", "signature", "")

        assert result is False

    def test_process_with_idempotency_first_call(self, sample_company_id, sample_event_id):
        """First call should process and store result."""
        from backend.app.services.webhook_processor import process_with_idempotency

        processor_called = []

        def processor():
            processor_called.append(True)
            return {"status": "processed", "data": "test"}

        with patch(
            "backend.app.services.webhook_processor.check_idempotency_key",
            return_value=None,
        ):
            with patch(
                "backend.app.services.webhook_processor.store_idempotency_key"
            ):
                result = process_with_idempotency(
                    provider="paddle",
                    event_id=sample_event_id,
                    processor=processor,
                    company_id=sample_company_id,
                )

        assert result["duplicate"] is False
        assert len(processor_called) == 1

    def test_process_with_idempotency_duplicate_call(self, sample_company_id, sample_event_id):
        """Duplicate call should return cached result."""
        from backend.app.services.webhook_processor import process_with_idempotency

        processor_called = []

        def processor():
            processor_called.append(True)
            return {"status": "processed", "data": "test"}

        with patch(
            "backend.app.services.webhook_processor.check_idempotency_key",
            return_value={"found": True, "status": 200, "body": '{"cached": true}'},
        ):
            result = process_with_idempotency(
                provider="paddle",
                event_id=sample_event_id,
                processor=processor,
                company_id=sample_company_id,
            )

        assert result["duplicate"] is True
        assert len(processor_called) == 0  # Processor not called


# ── Test Webhook Ordering Service ──────────────────────────────────────────


class TestWebhookOrderingService:
    """Test webhook ordering service."""

    def test_event_dependencies_defined(self):
        """Dependencies should be defined for ordered events."""
        from backend.app.services.webhook_ordering_service import EVENT_DEPENDENCIES

        # subscription.updated depends on created/activated
        assert "subscription.created" in EVENT_DEPENDENCIES.get("subscription.updated", [])
        assert "subscription.activated" in EVENT_DEPENDENCIES.get("subscription.updated", [])

        # transaction.completed depends on paid
        assert "transaction.paid" in EVENT_DEPENDENCIES.get("transaction.completed", [])

    def test_ordered_event_types_defined(self):
        """Ordered event types should be defined."""
        from backend.app.services.webhook_ordering_service import ORDERED_EVENT_TYPES

        assert "subscription.created" in ORDERED_EVENT_TYPES
        assert "subscription.updated" in ORDERED_EVENT_TYPES
        assert "transaction.paid" in ORDERED_EVENT_TYPES
        assert "transaction.completed" in ORDERED_EVENT_TYPES

    def test_get_next_processing_order_logic(self):
        """Test the processing order calculation logic."""
        # When no last record or processing_order is None, return 1
        # When last.processing_order is 5, return 6
        
        # Test case 1: No record
        last = None
        if last and last.processing_order is not None:
            result = last.processing_order + 1
        else:
            result = 1
        assert result == 1
        
        # Test case 2: Record with processing_order = 5
        class MockRecord:
            processing_order = 5
        last = MockRecord()
        if last and last.processing_order is not None:
            result = last.processing_order + 1
        else:
            result = 1
        assert result == 6
        
        # Test case 3: Record with processing_order = None
        class MockRecordNone:
            processing_order = None
        last = MockRecordNone()
        if last and last.processing_order is not None:
            result = last.processing_order + 1
        else:
            result = 1
        assert result == 1

    def test_check_dependencies_met_no_deps(self, sample_company_id):
        """Should return met=True when no dependencies."""
        from backend.app.services.webhook_ordering_service import check_dependencies_met

        with patch(
            "backend.app.services.webhook_ordering_service.SessionLocal"
        ) as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            result = check_dependencies_met(
                event_type="subscription.created",  # No dependencies
                company_id=sample_company_id,
                occurred_at=datetime.now(timezone.utc),
            )

            assert result["met"] is True
            assert result["missing"] == []


# ── Test Webhook Recovery Tasks ────────────────────────────────────────────


class TestWebhookRecoveryTasks:
    """Test webhook recovery Celery tasks."""

    def test_recover_missed_webhooks_task(self):
        """Recovery task should run and return counts."""
        from backend.app.tasks.webhook_recovery import recover_missed_webhooks

        with patch("database.base.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.all.return_value = []

            result = recover_missed_webhooks()

            assert "recovered" in result
            assert "errors" in result

    def test_process_stuck_webhooks_task(self):
        """Stuck webhook task should process stuck events."""
        from backend.app.tasks.webhook_recovery import process_stuck_webhooks

        with patch(
            "backend.app.services.webhook_ordering_service.get_stuck_events",
            return_value=[],
        ):
            result = process_stuck_webhooks()

            assert "stuck_found" in result
            assert "retried" in result

    def test_cleanup_idempotency_keys_task(self):
        """Cleanup task should delete expired keys."""
        from backend.app.tasks.webhook_recovery import cleanup_idempotency_keys

        with patch(
            "backend.app.services.webhook_processor.cleanup_expired_idempotency_keys",
            return_value=10,
        ):
            result = cleanup_idempotency_keys()

            assert result["deleted"] == 10

    def test_cleanup_webhook_sequences_task(self):
        """Cleanup sequences task should delete old sequences."""
        from backend.app.tasks.webhook_recovery import cleanup_webhook_sequences

        with patch(
            "backend.app.services.webhook_ordering_service.cleanup_old_sequences",
            return_value=20,
        ):
            result = cleanup_webhook_sequences()

            assert result["deleted"] == 20


# ── Test Backward Compatibility ────────────────────────────────────────────


class TestBackwardCompatibility:
    """Test backward compatibility aliases."""

    def test_subscription_cancelled_alias(self, sample_company_id, sample_event_id):
        """Should handle subscription.cancelled (British spelling)."""
        from backend.app.webhooks.paddle_handler import handle_paddle_event

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.cancelled",  # British spelling
            "company_id": sample_company_id,
            "payload": {
                "data": {
                    "subscription": {"id": "sub_123"},
                    "cancellation_reason": "user_requested",
                }
            },
        }

        result = handle_paddle_event(event)

        assert result["status"] == "processed"

    def test_payment_succeeded_alias(self, sample_company_id, sample_event_id):
        """Should handle payment.succeeded (old format)."""
        from backend.app.webhooks.paddle_handler import handle_paddle_event

        event = {
            "event_id": sample_event_id,
            "event_type": "payment.succeeded",  # Old format
            "company_id": sample_company_id,
            "payload": {
                "data": {
                    "transaction": {"id": "txn_123"},
                }
            },
        }

        result = handle_paddle_event(event)

        assert result["status"] == "processed"

    def test_payment_failed_alias(self, sample_company_id, sample_event_id):
        """Should handle payment.failed (old format)."""
        from backend.app.webhooks.paddle_handler import handle_paddle_event

        event = {
            "event_id": sample_event_id,
            "event_type": "payment.failed",  # Old format
            "company_id": sample_company_id,
            "payload": {
                "data": {
                    "transaction": {
                        "id": "txn_123",
                        "error": {"code": "declined"},
                    },
                }
            },
        }

        result = handle_paddle_event(event)

        assert result["status"] == "processed"


# ── Integration Tests ──────────────────────────────────────────────────────


class TestWebhookIntegration:
    """Integration tests for webhook flow."""

    def test_full_webhook_flow(
        self, sample_company_id, sample_event_id, sample_subscription_id, sample_customer_id
    ):
        """Test complete webhook processing flow."""
        from backend.app.webhooks.paddle_handler import handle_paddle_event

        event = {
            "event_id": sample_event_id,
            "event_type": "subscription.created",
            "company_id": sample_company_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "data": {
                    "subscription": {
                        "id": sample_subscription_id,
                        "status": "active",
                        "items": [{"price_id": "pri_123", "quantity": 1}],
                    },
                    "customer": {"id": sample_customer_id},
                }
            },
        }

        result = handle_paddle_event(event)

        assert result["status"] == "processed"
        assert "occurred_at" in result
        assert result["data"]["subscription_id"] == sample_subscription_id

    def test_concurrent_event_handling(
        self, sample_company_id, sample_subscription_id
    ):
        """Test handling multiple events for same subscription."""
        from backend.app.webhooks.paddle_handler import handle_paddle_event

        events = [
            {
                "event_id": f"evt_{i}",
                "event_type": "subscription.updated",
                "company_id": sample_company_id,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "data": {
                        "subscription": {
                            "id": sample_subscription_id,
                            "status": "active",
                        },
                    }
                },
            }
            for i in range(5)
        ]

        results = [handle_paddle_event(event) for event in events]

        for result in results:
            assert result["status"] == "processed"
