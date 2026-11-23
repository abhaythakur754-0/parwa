import pytest
from fastapi import HTTPException

from app.api.flexpay import _ensure_company_plan_access


class UserStub:
    company_id = "company-123"


class PlanStub:
    id = "plan-123"
    company_id = "company-123"


class FakeQuery:
    def __init__(self, result):
        self.result = result
        self.criteria = ()

    def filter(self, *criteria):
        self.criteria = criteria
        return self

    def first(self):
        return self.result


class FakeDB:
    def __init__(self, result):
        self.query_result = FakeQuery(result)

    def query(self, _model):
        return self.query_result


def test_flexpay_access_allows_plan_from_authenticated_company():
    plan = PlanStub()
    db = FakeDB(plan)

    assert _ensure_company_plan_access(db, "plan-123", UserStub()) is plan
    # The SQL filter must include both the requested plan ID and company ID.
    assert len(db.query_result.criteria) == 2


def test_flexpay_access_hides_foreign_company_plan():
    db = FakeDB(None)

    with pytest.raises(HTTPException) as exc:
        _ensure_company_plan_access(db, "foreign-plan", UserStub())

    assert exc.value.status_code == 404


def test_flexpay_access_rejects_users_without_company():
    user = UserStub()
    user.company_id = None

    with pytest.raises(HTTPException) as exc:
        _ensure_company_plan_access(FakeDB(None), "plan-123", user)

    assert exc.value.status_code == 403
