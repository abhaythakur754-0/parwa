"""
Tests for F-019 API Key API Endpoints.

Integration tests for /api/api-keys CRUD endpoints.
Uses the shared test DB from conftest.py.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from database.base import engine, get_db


@pytest.fixture(scope="function")
def app_client():
    """Create a test client with DB override.

    Uses a session that does NOT auto-commit so tests
    don't pollute each other.
    """
    from backend.app.main import app as _app

    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.commit()

    _app.dependency_overrides[get_db] = override_get_db
    with TestClient(_app) as c:
        yield c
    _app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers(app_client):
    """Register a user and return auth headers."""
    import uuid
    unique = uuid.uuid4().hex[:8]
    resp = app_client.post("/api/auth/register", json={
        "email": f"apikeytest{unique}@test.com",
        "password": "StrongPass1!",
        "confirm_password": "StrongPass1!",
        "full_name": "API Key Tester",
        "company_name": f"API Test Co {unique}",
        "industry": "technology",
    })
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    token = resp.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestListKeys:
    """Tests for GET /api/api-keys."""

    def test_list_empty(self, app_client, auth_headers):
        resp = app_client.get(
            "/api/api-keys", headers=auth_headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_after_create(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={"name": "Test Key", "scopes": ["read"]},
        )
        assert resp.status_code == 201

        resp = app_client.get(
            "/api/api-keys", headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["name"] == "Test Key"

    def test_list_no_hash_exposed(self, app_client, auth_headers):
        app_client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={"name": "No Hash", "scopes": ["read"]},
        )
        resp = app_client.get(
            "/api/api-keys", headers=auth_headers,
        )
        for key in resp.json():
            assert "key_hash" not in key


class TestCreateKey:
    """Tests for POST /api/api-keys."""

    def test_create_success(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={"name": "New Key", "scopes": ["read"]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "key" in data
        assert data["key"].startswith("parwa_live_")
        assert data["api_key"]["name"] == "New Key"

    def test_create_with_expiration(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={
                "name": "Expiring",
                "scopes": ["read"],
                "expires_days": 30,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["api_key"]["expires_at"] is not None

    def test_create_invalid_scope(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={"name": "Bad", "scopes": ["superadmin"]},
        )
        assert resp.status_code == 422

    def test_create_max_keys(self, app_client, auth_headers):
        for i in range(10):
            resp = app_client.post(
                "/api/api-keys",
                headers=auth_headers,
                json={
                    "name": f"Key {i}",
                    "scopes": ["read"],
                },
            )
            assert resp.status_code == 201, (
                f"Key {i} creation failed: {resp.text}"
            )

        resp = app_client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={"name": "11th", "scopes": ["read"]},
        )
        assert resp.status_code == 400
        assert "Maximum" in resp.json()["detail"]

    def test_create_unauthorized(self, app_client):
        resp = app_client.post(
            "/api/api-keys",
            json={"name": "No Auth", "scopes": ["read"]},
        )
        assert resp.status_code in (401, 403)


class TestRotateKey:
    """Tests for POST /api/api-keys/{id}/rotate."""

    def test_rotate_success(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={"name": "Rotate Me", "scopes": ["read"]},
        )
        assert resp.status_code == 201
        key_id = resp.json()["api_key"]["id"]

        resp = app_client.post(
            f"/api/api-keys/{key_id}/rotate",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"].startswith("parwa_live_")
        assert data["old_key_id"] == key_id
        assert data["grace_period_ends"] is not None

    def test_rotate_not_found(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/api-keys/nonexistent/rotate",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestRevokeKey:
    """Tests for DELETE /api/api-keys/{id}/revoke."""

    def test_revoke_success(self, app_client, auth_headers):
        resp = app_client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={"name": "Revoke Me", "scopes": ["read"]},
        )
        assert resp.status_code == 201
        key_id = resp.json()["api_key"]["id"]

        resp = app_client.delete(
            f"/api/api-keys/{key_id}/revoke",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "revoked"
        assert resp.json()["key_id"] == key_id

    def test_revoke_not_found(self, app_client, auth_headers):
        resp = app_client.delete(
            "/api/api-keys/nonexistent/revoke",
            headers=auth_headers,
        )
        assert resp.status_code == 404
