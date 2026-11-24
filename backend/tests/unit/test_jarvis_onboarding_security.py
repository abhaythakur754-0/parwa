"""Security regressions for the database-backed Jarvis onboarding API."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.deps import get_current_user
from app.api.jarvis_onboarding import (
    RecordPaymentRequest,
    _require_company_id,
    record_payment,
    router,
)


def test_onboarding_router_requires_authenticated_user():
    assert any(dependency.dependency is get_current_user for dependency in router.dependencies)


def test_company_scope_comes_from_authenticated_user_not_request():
    user = SimpleNamespace(company_id="company-authenticated")
    assert _require_company_id(user) == "company-authenticated"


def test_user_without_company_cannot_access_tenant_onboarding():
    with pytest.raises(HTTPException) as exc:
        _require_company_id(SimpleNamespace(company_id=None))
    assert exc.value.status_code == 403


def test_client_cannot_mark_onboarding_payment_as_completed():
    body = RecordPaymentRequest(
        session_id="session-1",
        company_id="attacker-company",
        payment_data={"status": "completed", "amount": 1},
    )
    with pytest.raises(HTTPException) as exc:
        record_payment(body, current_user=SimpleNamespace(company_id="company-1"))
    assert exc.value.status_code == 410
