"""Tests for Brevo webhook handler."""

import backend.app.webhooks.brevo_handler  # noqa: F401
from backend.app.webhooks.brevo_handler import (
    handle_brevo_event,
    handle_inbound_email,
    _sanitize_email_field,
    _extract_inbound_email_data,
    _extract_attachments,
    MAX_EMAIL_BODY_SIZE,
)

SAMPLE_BREVO_EVENT = {
    "event_type": "inbound_email",
    "payload": {
        "sender": {"email": "customer@example.com", "name": "John Doe"},
        "recipient": {"email": "support@company.com"},
        "subject": "Help with my order #12345",
        "body_html": "<p>I need help with my order</p>",
        "body_text": "I need help with my order",
        "attachments": [
            {"filename": "receipt.pdf", "content-type": "application/pdf", "size": 1024},
        ],
        "message_id": "msg_123",
    },
    "company_id": "comp_1",
    "event_id": "evt_123",
}


class TestHandleBrevoEvent:
    def test_dispatches_inbound_email(self):
        result = handle_brevo_event(SAMPLE_BREVO_EVENT)
        assert result["status"] == "processed"
        assert result["action"] == "create_ticket_draft"

    def test_unknown_event_type_returns_error(self):
        event = {**SAMPLE_BREVO_EVENT, "event_type": "unknown"}
        result = handle_brevo_event(event)
        assert result["status"] == "validation_error"
        assert "Unknown Brevo event type" in result["error"]

    def test_unknown_event_includes_supported_types(self):
        event = {**SAMPLE_BREVO_EVENT, "event_type": "unknown"}
        result = handle_brevo_event(event)
        assert "supported_types" in result
        assert "inbound_email" in result["supported_types"]


class TestHandleInboundEmail:
    def test_returns_processed_status(self):
        result = handle_inbound_email(SAMPLE_BREVO_EVENT)
        assert result["status"] == "processed"

    def test_returns_create_ticket_draft_action(self):
        result = handle_inbound_email(SAMPLE_BREVO_EVENT)
        assert result["action"] == "create_ticket_draft"

    def test_extracts_sender_email(self):
        result = handle_inbound_email(SAMPLE_BREVO_EVENT)
        assert result["data"]["sender_email"] == "customer@example.com"

    def test_extracts_sender_name(self):
        result = handle_inbound_email(SAMPLE_BREVO_EVENT)
        assert result["data"]["sender_name"] == "John Doe"

    def test_extracts_recipient_email(self):
        result = handle_inbound_email(SAMPLE_BREVO_EVENT)
        assert result["data"]["recipient_email"] == "support@company.com"

    def test_extracts_subject(self):
        result = handle_inbound_email(SAMPLE_BREVO_EVENT)
        assert result["data"]["subject"] == "Help with my order #12345"

    def test_extracts_body_html(self):
        result = handle_inbound_email(SAMPLE_BREVO_EVENT)
        assert "<p>I need help with my order</p>" in result["data"]["body_html"]

    def test_extracts_body_text(self):
        result = handle_inbound_email(SAMPLE_BREVO_EVENT)
        assert result["data"]["body_text"] == "I need help with my order"

    def test_extracts_attachments(self):
        result = handle_inbound_email(SAMPLE_BREVO_EVENT)
        assert len(result["data"]["attachments"]) == 1
        assert result["data"]["attachments"][0]["filename"] == "receipt.pdf"

    def test_extracts_message_id(self):
        result = handle_inbound_email(SAMPLE_BREVO_EVENT)
        assert result["data"]["message_id"] == "msg_123"

    def test_missing_sender_returns_error(self):
        event = {**SAMPLE_BREVO_EVENT, "payload": {**SAMPLE_BREVO_EVENT["payload"], "sender": None}}
        result = handle_inbound_email(event)
        assert result["status"] == "validation_error"

    def test_missing_subject_returns_error(self):
        event = {**SAMPLE_BREVO_EVENT, "payload": {**SAMPLE_BREVO_EVENT["payload"], "subject": ""}}
        result = handle_inbound_email(event)
        assert result["status"] == "validation_error"

    def test_missing_body_html_returns_error(self):
        event = {**SAMPLE_BREVO_EVENT, "payload": {**SAMPLE_BREVO_EVENT["payload"], "body_html": None}}
        result = handle_inbound_email(event)
        assert result["status"] == "validation_error"

    def test_missing_recipient_returns_error(self):
        event = {**SAMPLE_BREVO_EVENT, "payload": {**SAMPLE_BREVO_EVENT["payload"], "recipient": {}}}
        result = handle_inbound_email(event)
        assert result["status"] == "validation_error"

    def test_oversized_body_is_truncated(self):
        event = {
            **SAMPLE_BREVO_EVENT,
            "payload": {
                **SAMPLE_BREVO_EVENT["payload"],
                "body_html": "<p>" + "x" * (MAX_EMAIL_BODY_SIZE + 1000) + "</p>",
            },
        }
        result = handle_inbound_email(event)
        assert result["data"]["body_truncated"] is True
        assert len(result["data"]["body_html"]) <= MAX_EMAIL_BODY_SIZE + 10

    def test_no_attachments_returns_empty_list(self):
        event = {**SAMPLE_BREVO_EVENT, "payload": {**SAMPLE_BREVO_EVENT["payload"], "attachments": []}}
        result = handle_inbound_email(event)
        assert result["data"]["attachments"] == []


class TestSanitizeEmailField:
    def test_strips_control_characters(self):
        result = _sanitize_email_field("hello\x00\x01world")
        assert "\x00" not in result
        assert "\x01" not in result

    def test_truncates_to_max_length(self):
        result = _sanitize_email_field("a" * 1000, max_length=100)
        assert len(result) == 100

    def test_empty_string_returns_empty(self):
        assert _sanitize_email_field("") == ""

    def test_none_returns_empty(self):
        assert _sanitize_email_field(None) == ""

    def test_preserves_newlines_and_tabs(self):
        result = _sanitize_email_field("hello\n\tworld")
        assert "\n" in result
        assert "\t" in result


class TestExtractAttachments:
    def test_limits_to_20_attachments(self):
        atts = [{"filename": f"file{i}.pdf", "content-type": "application/pdf", "size": 100} for i in range(30)]
        result = _extract_attachments(atts)
        assert len(result) == 20

    def test_skips_invalid_attachments(self):
        atts = [{"filename": "ok.pdf", "size": 100}, "not_a_dict", None]
        result = _extract_attachments(atts)
        assert len(result) == 1

    def test_empty_list_returns_empty(self):
        assert _extract_attachments([]) == []

    def test_none_returns_empty(self):
        assert _extract_attachments(None) == []
