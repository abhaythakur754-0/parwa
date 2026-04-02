"""Tests for Paddle webhook handler."""

import backend.app.webhooks.paddle_handler  # noqa: F401
from backend.app.webhooks.paddle_handler import (
    handle_paddle_event,
    handle_subscription_created,
    handle_subscription_updated,
    handle_subscription_cancelled,
    handle_payment_succeeded,
    handle_payment_failed,
    _extract_subscription_data,
    _extract_payment_data,
    REQUIRED_FIELDS,
)

SAMPLE_SUB_EVENT = {
    "event_type": "subscription.created",
    "payload": {
        "data": {
            "subscription": {
                "subscription_id": "sub_123",
                "plan_id": "plan_456",
                "customer_id": "cust_789",
                "status": "active",
                "currency": "USD",
                "quantity": 5,
            },
            "customer": {"id": "cust_789", "email": "test@example.com"},
        }
    },
    "company_id": "comp_1",
    "event_id": "evt_123",
}

SAMPLE_PAY_EVENT = {
    "event_type": "payment.succeeded",
    "payload": {
        "data": {
            "payment": {
                "payment_id": "pay_123",
                "subscription_id": "sub_123",
                "amount": "99.99",
                "currency": "USD",
                "status": "completed",
                "payment_method": "card",
            },
            "billing_details": {"currency": "USD"},
        }
    },
    "company_id": "comp_1",
    "event_id": "evt_456",
}


class TestHandlePaddleEvent:
    def test_dispatches_subscription_created(self):
        result = handle_paddle_event(SAMPLE_SUB_EVENT)
        assert result["status"] == "processed"
        assert result["action"] == "subscription_created"

    def test_dispatches_subscription_updated(self):
        event = {**SAMPLE_SUB_EVENT, "event_type": "subscription.updated"}
        result = handle_paddle_event(event)
        assert result["action"] == "subscription_updated"

    def test_dispatches_subscription_cancelled(self):
        event = {
            **SAMPLE_SUB_EVENT,
            "event_type": "subscription.cancelled",
            "payload": {
                **SAMPLE_SUB_EVENT["payload"],
                "data": {
                    **SAMPLE_SUB_EVENT["payload"]["data"],
                    "cancellation_reason": "user_requested",
                },
            },
        }
        result = handle_paddle_event(event)
        assert result["action"] == "subscription_cancelled"

    def test_dispatches_payment_succeeded(self):
        result = handle_paddle_event(SAMPLE_PAY_EVENT)
        assert result["status"] == "processed"
        assert result["action"] == "payment_succeeded"

    def test_dispatches_payment_failed(self):
        event = {
            **SAMPLE_PAY_EVENT,
            "event_type": "payment.failed",
            "payload": {
                **SAMPLE_PAY_EVENT["payload"],
                "data": {
                    **SAMPLE_PAY_EVENT["payload"]["data"],
                    "payment": {
                        **SAMPLE_PAY_EVENT["payload"]["data"]["payment"],
                        "error_code": "card_declined",
                    },
                },
            },
        }
        result = handle_paddle_event(event)
        assert result["action"] == "payment_failed"

    def test_unknown_event_type_returns_validation_error(self):
        event = {**SAMPLE_SUB_EVENT, "event_type": "unknown.event"}
        result = handle_paddle_event(event)
        assert result["status"] == "validation_error"
        assert "Unknown Paddle event type" in result["error"]

    def test_unknown_event_includes_supported_types(self):
        event = {**SAMPLE_SUB_EVENT, "event_type": "unknown.event"}
        result = handle_paddle_event(event)
        assert "supported_types" in result
        assert len(result["supported_types"]) == 5


class TestSubscriptionCreated:
    def test_returns_processed_status(self):
        result = handle_subscription_created(SAMPLE_SUB_EVENT)
        assert result["status"] == "processed"

    def test_returns_action_subscription_created(self):
        result = handle_subscription_created(SAMPLE_SUB_EVENT)
        assert result["action"] == "subscription_created"

    def test_extracts_subscription_id(self):
        result = handle_subscription_created(SAMPLE_SUB_EVENT)
        assert result["data"]["subscription_id"] == "sub_123"

    def test_extracts_plan_id(self):
        result = handle_subscription_created(SAMPLE_SUB_EVENT)
        assert result["data"]["plan_id"] == "plan_456"

    def test_extracts_customer_id(self):
        result = handle_subscription_created(SAMPLE_SUB_EVENT)
        assert result["data"]["customer_id"] == "cust_789"

    def test_missing_subscription_id_returns_error(self):
        event = {
            **SAMPLE_SUB_EVENT,
            "payload": {
                "data": {
                    "subscription": {"plan_id": "plan_456"},
                    "customer": {"id": "cust_789"},
                }
            },
        }
        result = handle_subscription_created(event)
        assert result["status"] == "validation_error"

    def test_missing_plan_id_returns_error(self):
        event = {
            **SAMPLE_SUB_EVENT,
            "payload": {
                "data": {
                    "subscription": {"subscription_id": "sub_123"},
                    "customer": {"id": "cust_789"},
                }
            },
        }
        result = handle_subscription_created(event)
        assert result["status"] == "validation_error"

    def test_missing_customer_id_returns_error(self):
        event = {
            **SAMPLE_SUB_EVENT,
            "payload": {
                "data": {
                    "subscription": {
                        "subscription_id": "sub_123",
                        "plan_id": "plan_456",
                    },
                    "customer": {"id": ""},
                }
            },
        }
        result = handle_subscription_created(event)
        assert result["status"] == "validation_error"


class TestSubscriptionUpdated:
    def test_returns_processed_status(self):
        event = {**SAMPLE_SUB_EVENT, "event_type": "subscription.updated"}
        result = handle_subscription_updated(event)
        assert result["status"] == "processed"

    def test_returns_action_subscription_updated(self):
        event = {**SAMPLE_SUB_EVENT, "event_type": "subscription.updated"}
        result = handle_subscription_updated(event)
        assert result["action"] == "subscription_updated"

    def test_extracts_quantity(self):
        event = {**SAMPLE_SUB_EVENT, "event_type": "subscription.updated"}
        result = handle_subscription_updated(event)
        assert result["data"]["quantity"] == 5

    def test_default_quantity_is_one(self):
        event = {
            **SAMPLE_SUB_EVENT,
            "event_type": "subscription.updated",
            "payload": {
                "data": {
                    "subscription": {
                        "subscription_id": "sub_1",
                        "plan_id": "plan_1",
                    },
                    "customer": {"id": "c1"},
                }
            },
        }
        result = handle_subscription_updated(event)
        assert result["data"]["quantity"] == 1


class TestSubscriptionCancelled:
    def test_returns_processed_status(self):
        event = {
            **SAMPLE_SUB_EVENT,
            "event_type": "subscription.cancelled",
            "payload": {
                "data": {
                    "subscription": {
                        "subscription_id": "sub_123",
                        "plan_id": "plan_456",
                    },
                    "customer": {"id": "cust_789"},
                    "cancellation_reason": "user_requested",
                }
            },
        }
        result = handle_subscription_cancelled(event)
        assert result["status"] == "processed"

    def test_includes_cancellation_reason(self):
        event = {
            **SAMPLE_SUB_EVENT,
            "event_type": "subscription.cancelled",
            "payload": {
                "data": {
                    "subscription": {
                        "subscription_id": "sub_123",
                        "plan_id": "plan_456",
                    },
                    "customer": {"id": "cust_789"},
                    "cancellation_reason": "user_requested",
                }
            },
        }
        result = handle_subscription_cancelled(event)
        assert result["data"]["cancellation_reason"] == "user_requested"

    def test_default_cancellation_reason(self):
        event = {
            **SAMPLE_SUB_EVENT,
            "event_type": "subscription.cancelled",
            "payload": {
                "data": {
                    "subscription": {
                        "subscription_id": "sub_123",
                        "plan_id": "plan_456",
                    },
                    "customer": {"id": "cust_789"},
                }
            },
        }
        result = handle_subscription_cancelled(event)
        assert result["data"]["cancellation_reason"] == "user_requested"


class TestPaymentSucceeded:
    def test_returns_processed_status(self):
        result = handle_payment_succeeded(SAMPLE_PAY_EVENT)
        assert result["status"] == "processed"

    def test_extracts_payment_id(self):
        result = handle_payment_succeeded(SAMPLE_PAY_EVENT)
        assert result["data"]["payment_id"] == "pay_123"

    def test_extracts_amount(self):
        result = handle_payment_succeeded(SAMPLE_PAY_EVENT)
        assert result["data"]["amount"] == "99.99"

    def test_extracts_currency(self):
        result = handle_payment_succeeded(SAMPLE_PAY_EVENT)
        assert result["data"]["currency"] == "USD"

    def test_missing_payment_id_returns_error(self):
        event = {
            **SAMPLE_PAY_EVENT,
            "payload": {
                "data": {
                    "payment": {
                        "subscription_id": "sub_123",
                        "amount": "99.99",
                        "currency": "USD",
                    }
                }
            },
        }
        result = handle_payment_succeeded(event)
        assert result["status"] == "validation_error"


class TestPaymentFailed:
    def test_returns_processed_status(self):
        event = {
            **SAMPLE_PAY_EVENT,
            "event_type": "payment.failed",
            "payload": {
                "data": {
                    "payment": {
                        "payment_id": "pay_123",
                        "subscription_id": "sub_123",
                        "amount": "99.99",
                        "currency": "USD",
                        "error_code": "card_declined",
                    }
                }
            },
        }
        result = handle_payment_failed(event)
        assert result["status"] == "processed"

    def test_includes_error_code(self):
        event = {
            **SAMPLE_PAY_EVENT,
            "event_type": "payment.failed",
            "payload": {
                "data": {
                    "payment": {
                        "payment_id": "pay_123",
                        "subscription_id": "sub_123",
                        "amount": "99.99",
                        "currency": "USD",
                        "error_code": "card_declined",
                    }
                }
            },
        }
        result = handle_payment_failed(event)
        assert result["data"]["error_code"] == "card_declined"


class TestExtractSubscriptionData:
    def test_extracts_nested_data(self):
        data = _extract_subscription_data(SAMPLE_SUB_EVENT["payload"])
        assert data["subscription_id"] == "sub_123"
        assert data["plan_id"] == "plan_456"

    def test_default_currency_is_usd(self):
        event = {
            "data": {
                "subscription": {"subscription_id": "s1", "plan_id": "p1"},
                "customer": {"id": "c1"},
            }
        }
        data = _extract_subscription_data(event)
        assert data["currency"] == "USD"

    def test_default_quantity_is_one(self):
        event = {
            "data": {
                "subscription": {"subscription_id": "s1", "plan_id": "p1"},
                "customer": {"id": "c1"},
            }
        }
        data = _extract_subscription_data(event)
        assert data["quantity"] == 1


class TestRequiredFields:
    def test_subscription_created_has_required_fields(self):
        fields = REQUIRED_FIELDS["subscription.created"]
        assert "subscription_id" in fields
        assert "plan_id" in fields
        assert "customer_id" in fields

    def test_payment_succeeded_has_required_fields(self):
        fields = REQUIRED_FIELDS["payment.succeeded"]
        assert "payment_id" in fields
        assert "amount" in fields
        assert "currency" in fields

    def test_payment_failed_has_required_fields(self):
        fields = REQUIRED_FIELDS["payment.failed"]
        assert "error_code" in fields
