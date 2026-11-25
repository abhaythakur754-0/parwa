import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.jarvis_onboarding import enforce_onboarding_identity


class UserStub:
    id = "user-123"
    company_id = "company-456"


class FakeQuery:
    def __init__(self, result=None):
        self.result = result

    def filter(self, *criteria):
        self.criteria = criteria
        return self

    def first(self):
        return self.result


class FakeDB:
    def __init__(self, result=None):
        self.result = result

    def query(self, _model):
        return FakeQuery(self.result)


class SessionStub:
    id = "session-789"
    company_id = "company-456"
    user_id = "user-123"
    type = "onboarding"


def make_request(method: str, body=None, query_string: bytes = b"") -> Request:
    payload = json.dumps(body or {}).encode()

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": "/api/jarvis/onboarding/session",
            "raw_path": b"/api/jarvis/onboarding/session",
            "query_string": query_string,
            "headers": [(b"content-type", b"application/json")],
            "server": ("testserver", 80),
            "client": ("testclient", 1234),
        },
        receive,
    )


@pytest.mark.asyncio
async def test_onboarding_identity_accepts_matching_tenant_and_user():
    request = make_request(
        "POST",
        {"company_id": "company-456", "user_id": "user-123"},
    )
    user = await enforce_onboarding_identity(request, FakeDB(), UserStub())
    assert user.id == "user-123"


@pytest.mark.asyncio
async def test_onboarding_identity_rejects_cross_tenant_body():
    request = make_request("POST", {"company_id": "another-company"})
    with pytest.raises(HTTPException) as exc:
        await enforce_onboarding_identity(request, FakeDB(), UserStub())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_onboarding_identity_rejects_spoofed_user_id():
    request = make_request(
        "POST",
        {"company_id": "company-456", "user_id": "another-user"},
    )
    with pytest.raises(HTTPException) as exc:
        await enforce_onboarding_identity(request, FakeDB(), UserStub())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_onboarding_identity_rejects_cross_tenant_query():
    request = make_request("GET", query_string=b"company_id=another-company")
    with pytest.raises(HTTPException) as exc:
        await enforce_onboarding_identity(request, FakeDB(), UserStub())
    assert exc.value.status_code == 403



@pytest.mark.asyncio
async def test_onboarding_identity_accepts_session_owned_by_authenticated_user():
    request = make_request(
        "POST",
        {"company_id": "company-456", "user_id": "user-123", "session_id": "session-789"},
    )
    user = await enforce_onboarding_identity(request, FakeDB(SessionStub()), UserStub())
    assert user.id == "user-123"


@pytest.mark.asyncio
async def test_onboarding_identity_rejects_session_owned_by_another_user():
    foreign_session = SessionStub()
    foreign_session.user_id = "another-user"
    request = make_request(
        "POST",
        {"company_id": "company-456", "session_id": "session-789"},
    )
    with pytest.raises(HTTPException) as exc:
        await enforce_onboarding_identity(request, FakeDB(foreign_session), UserStub())
    assert exc.value.status_code == 404
