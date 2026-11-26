"""Tenant-isolation regression tests for technique configuration routes."""

from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.technique_config import get_config_store, router
from app.exceptions import ParwaBaseError


def make_client(company_id="tenant-a", role="owner", authenticated=True):
    app = FastAPI()
    app.include_router(router)

    @app.exception_handler(ParwaBaseError)
    async def handle_parwa_error(request: Request, exc: ParwaBaseError):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id="test-user", company_id=company_id, role=role
        )
    return TestClient(app)


def test_list_rejects_another_tenant_id():
    with make_client() as client:
        response = client.get(
            "/api/techniques/config", params={"company_id": "tenant-b"}
        )
    assert response.status_code == 403


def test_get_rejects_another_tenant_id():
    with make_client() as client:
        response = client.get(
            "/api/techniques/config/clara", params={"company_id": "tenant-b"}
        )
    assert response.status_code == 403


def test_update_rejects_another_tenant_and_does_not_mutate_it():
    store = get_config_store()
    store._configs.clear()
    with make_client() as client:
        response = client.put(
            "/api/techniques/config/chain_of_thought",
            json={"company_id": "tenant-b", "enabled": False},
        )
    assert response.status_code == 403
    assert store.get_config("tenant-b", "chain_of_thought")["enabled"] is True


def test_owner_can_read_and_update_own_tenant():
    store = get_config_store()
    store._configs.clear()
    with make_client("tenant-a") as client:
        listed = client.get(
            "/api/techniques/config", params={"company_id": "tenant-a"}
        )
        updated = client.put(
            "/api/techniques/config/chain_of_thought",
            json={"company_id": "tenant-a", "enabled": False},
        )
    assert listed.status_code == 200
    assert listed.json()["company_id"] == "tenant-a"
    assert updated.status_code == 200
    assert store.get_config("tenant-a", "chain_of_thought")["enabled"] is False


def test_member_cannot_access_admin_configuration():
    with make_client(role="member") as client:
        response = client.get(
            "/api/techniques/config", params={"company_id": "tenant-a"}
        )
    assert response.status_code == 403


def test_unauthenticated_request_is_rejected():
    with make_client(authenticated=False) as client:
        response = client.get(
            "/api/techniques/config", params={"company_id": "tenant-a"}
        )
    assert response.status_code == 401
