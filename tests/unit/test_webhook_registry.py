"""Tests for webhook handler registry."""

import backend.app.webhooks.paddle_handler  # noqa: F401
import backend.app.webhooks.brevo_handler  # noqa: F401
import backend.app.webhooks.twilio_handler  # noqa: F401
import backend.app.webhooks.shopify_handler  # noqa: F401

from backend.app.webhooks import (
    register_handler,
    get_handler,
    dispatch_event,
    validate_event_type,
    get_supported_event_types,
    get_registered_providers,
    PROVIDER_EVENT_TYPES,
    _HANDLER_REGISTRY,
)


class TestRegisterHandler:
    def test_registers_handler_for_provider(self):
        @register_handler("_test_provider")
        def _test_handler(event):
            return {"status": "ok"}

        handler = get_handler("_test_provider")
        assert handler is not None
        assert handler.__name__ == "_test_handler"

    def test_registering_duplicate_provider_overwrites(self):
        call_count = [0]

        @register_handler("_dup_provider")
        def _handler_v1(event):
            call_count[0] += 1
            return {"v": 1}

        @register_handler("_dup_provider")
        def _handler_v2(event):
            call_count[0] += 1
            return {"v": 2}

        result = get_handler("_dup_provider")({"payload": {}})
        assert result["v"] == 2

    def test_decorator_returns_original_function(self):
        @register_handler("_return_test")
        def _original(event):
            return {"ok": True}

        assert _original({"payload": {}})["ok"] is True


class TestGetHandler:
    def test_returns_handler_for_paddle(self):
        handler = get_handler("paddle")
        assert handler is not None
        assert callable(handler)

    def test_returns_handler_for_brevo(self):
        handler = get_handler("brevo")
        assert handler is not None
        assert callable(handler)

    def test_returns_handler_for_twilio(self):
        handler = get_handler("twilio")
        assert handler is not None
        assert callable(handler)

    def test_returns_handler_for_shopify(self):
        handler = get_handler("shopify")
        assert handler is not None
        assert callable(handler)

    def test_returns_none_for_unknown_provider(self):
        handler = get_handler("unknown_provider")
        assert handler is None

    def test_returns_none_for_empty_string(self):
        handler = get_handler("")
        assert handler is None


class TestDispatchEvent:
    def test_dispatches_to_paddle_handler(self):
        event = {
            "event_type": "subscription.created",
            "payload": {
                "data": {
                    "subscription": {
                        "subscription_id": "sub_1",
                        "plan_id": "plan_1",
                        "customer_id": "cust_1",
                    },
                    "customer": {"id": "cust_1"},
                }
            },
        }
        result = dispatch_event("paddle", event)
        assert result["status"] == "processed"
        assert result["action"] == "subscription_created"

    def test_dispatches_to_brevo_handler(self):
        event = {
            "event_type": "inbound_email",
            "payload": {
                "sender": {"email": "a@b.com"},
                "recipient": {"email": "c@d.com"},
                "subject": "Test",
                "body_html": "<p>Hi</p>",
            },
        }
        result = dispatch_event("brevo", event)
        assert result["status"] == "processed"

    def test_dispatches_to_twilio_handler(self):
        event = {
            "event_type": "sms.incoming",
            "payload": {
                "MessageSid": "SM1",
                "From": "+123",
                "To": "+456",
                "Body": "Hello",
            },
        }
        result = dispatch_event("twilio", event)
        assert result["status"] == "processed"

    def test_dispatches_to_shopify_handler(self):
        event = {
            "event_type": "orders.create",
            "payload": {
                "order": {
                    "id": 1,
                    "email": "a@b.com",
                    "total_price": "10",
                    "currency": "USD",
                },
            },
        }
        result = dispatch_event("shopify", event)
        assert result["status"] == "processed"

    def test_raises_value_error_for_unknown_provider(self):
        import pytest
        with pytest.raises(ValueError, match="No handler registered"):
            dispatch_event("nonexistent", {})

    def test_raises_value_error_with_provider_name(self):
        import pytest
        with pytest.raises(ValueError, match="unknown_provider_xyz"):
            dispatch_event("unknown_provider_xyz", {})


class TestValidateEventType:
    def test_paddle_subscription_created_is_valid(self):
        assert validate_event_type("paddle", "subscription.created") is True

    def test_paddle_payment_succeeded_is_valid(self):
        assert validate_event_type("paddle", "payment.succeeded") is True

    def test_paddle_unknown_is_invalid(self):
        assert validate_event_type("paddle", "refund.created") is False

    def test_brevo_inbound_email_is_valid(self):
        assert validate_event_type("brevo", "inbound_email") is True

    def test_brevo_unknown_is_invalid(self):
        assert validate_event_type("brevo", "email.sent") is False

    def test_twilio_sms_incoming_is_valid(self):
        assert validate_event_type("twilio", "sms.incoming") is True

    def test_twilio_voice_events_are_valid(self):
        assert validate_event_type("twilio", "voice.call.started") is True
        assert validate_event_type("twilio", "voice.call.ended") is True

    def test_shopify_orders_create_is_valid(self):
        assert validate_event_type("shopify", "orders.create") is True

    def test_unknown_provider_returns_false(self):
        assert validate_event_type("unknown", "anything") is False

    def test_empty_event_type_for_known_provider(self):
        assert validate_event_type("paddle", "") is False


class TestGetSupportedEventTypes:
    def test_paddle_has_5_event_types(self):
        types = get_supported_event_types("paddle")
        assert len(types) == 5

    def test_brevo_has_1_event_type(self):
        types = get_supported_event_types("brevo")
        assert len(types) == 1
        assert "inbound_email" in types

    def test_twilio_has_3_event_types(self):
        types = get_supported_event_types("twilio")
        assert len(types) == 3

    def test_shopify_has_2_event_types(self):
        types = get_supported_event_types("shopify")
        assert len(types) == 2

    def test_unknown_provider_returns_empty_list(self):
        types = get_supported_event_types("unknown")
        assert types == []


class TestGetRegisteredProviders:
    def test_all_4_providers_registered(self):
        providers = get_registered_providers()
        assert "paddle" in providers
        assert "brevo" in providers
        assert "twilio" in providers
        assert "shopify" in providers

    def test_at_least_4_providers(self):
        providers = get_registered_providers()
        assert len(providers) >= 4


class TestProviderEventTypes:
    def test_paddle_event_types_include_all_5(self):
        expected = [
            "subscription.created", "subscription.updated",
            "subscription.cancelled", "payment.succeeded",
            "payment.failed",
        ]
        for evt in expected:
            assert evt in PROVIDER_EVENT_TYPES["paddle"]

    def test_twilio_event_types_include_all_3(self):
        expected = ["sms.incoming", "voice.call.started", "voice.call.ended"]
        for evt in expected:
            assert evt in PROVIDER_EVENT_TYPES["twilio"]

    def test_shopify_event_types_include_both(self):
        assert "orders.create" in PROVIDER_EVENT_TYPES["shopify"]
        assert "customers.create" in PROVIDER_EVENT_TYPES["shopify"]

    def test_has_4_providers(self):
        assert len(PROVIDER_EVENT_TYPES) == 4
