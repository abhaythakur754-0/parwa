import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.responses import JSONResponse

from app.api import chat_widget


def _request(company_id=None):
    return SimpleNamespace(state=SimpleNamespace(company_id=company_id))


def test_visitor_message_cannot_impersonate_agent(monkeypatch):
    db = MagicMock()
    service = MagicMock()
    service.verify_visitor_token.return_value = True
    service.send_message.return_value = {"status": "sent"}
    monkeypatch.setattr(chat_widget, "_get_db", lambda request: db)
    monkeypatch.setattr(
        "app.services.chat_widget_service.ChatWidgetService",
        lambda session, company_id=None: service,
    )
    body = chat_widget.SendMessageRequest(
        content="hello",
        role="agent",
        sender_id="victim-user",
        sender_name="Administrator",
        visitor_token="valid-token",
        company_id="visitor-company",
    )

    result = asyncio.run(
        chat_widget.send_chat_message(
            body, _request("different-jwt-company"), "session-1", None
        )
    )

    assert result == {"status": "sent"}
    service.verify_visitor_token.assert_called_once_with(
        "session-1", "visitor-company", "valid-token"
    )
    sent = service.send_message.call_args.kwargs
    assert sent["company_id"] == "visitor-company"
    assert sent["role"] == "visitor"
    assert sent["sender_id"] is None
    assert sent["sender_name"] is None


def test_invalid_visitor_token_does_not_fall_back_to_jwt_tenant(monkeypatch):
    db = MagicMock()
    service = MagicMock()
    service.verify_visitor_token.return_value = False
    monkeypatch.setattr(chat_widget, "_get_db", lambda request: db)
    monkeypatch.setattr(
        "app.services.chat_widget_service.ChatWidgetService",
        lambda session, company_id=None: service,
    )
    body = chat_widget.SendMessageRequest(
        content="hello",
        visitor_token="invalid-token",
        company_id="visitor-company",
    )

    result = asyncio.run(
        chat_widget.send_chat_message(
            body, _request("authenticated-company"), "session-1", None
        )
    )

    assert isinstance(result, JSONResponse)
    assert result.status_code == 401
    service.send_message.assert_not_called()


def test_staff_message_uses_verified_user_identity(monkeypatch):
    db = MagicMock()
    service = MagicMock()
    service.send_message.return_value = {"status": "sent"}
    monkeypatch.setattr(chat_widget, "_get_db", lambda request: db)
    monkeypatch.setattr(
        "app.services.chat_widget_service.ChatWidgetService",
        lambda session, company_id=None: service,
    )
    user = SimpleNamespace(
        id="verified-user",
        company_id="verified-company",
        role="agent",
        full_name="Verified Agent",
    )
    body = chat_widget.SendMessageRequest(
        content="staff reply",
        role="visitor",
        sender_id="forged-user",
        sender_name="Forged Name",
    )

    result = asyncio.run(
        chat_widget.send_chat_message(
            body, _request("untrusted-request-state"), "session-1", user
        )
    )

    assert result == {"status": "sent"}
    sent = service.send_message.call_args.kwargs
    assert sent["company_id"] == "verified-company"
    assert sent["role"] == "agent"
    assert sent["sender_id"] == "verified-user"
    assert sent["sender_name"] == "Verified Agent"
