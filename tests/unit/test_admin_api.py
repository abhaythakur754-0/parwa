"""
Day 12: Admin API Endpoint Tests

Tests for /api/admin/* routes: client management, subscriptions,
API providers, health.

All admin endpoints require owner role.
"""

from tests.conftest import *  # noqa: F401, F403

_counter = 0


def _unique_email():
    """Generate unique email for test isolation."""
    global _counter
    _counter += 1
    return f"admin{_counter}@d12test.parwa.local"


def _register_owner(client, email=None):
    """Helper: register an owner user."""
    if email is None:
        email = _unique_email()
    resp = client.post("/api/auth/register", json={
        "email": email,
        "password": "StrongPass1!",
        "confirm_password": "StrongPass1!",
        "full_name": "Admin User",
        "company_name": "Admin Co",
        "industry": "technology",
    })
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    return data["tokens"]["access_token"], data["user"]


def _auth_headers(token):
    """Helper: build auth headers."""
    return {"Authorization": f"Bearer {token}"}


class TestListClients:
    """Tests for GET /api/admin/clients."""

    def test_list_clients(self, client):
        """Owner can list all clients."""
        token, _ = _register_owner(client)
        resp = client.get(
            "/api/admin/clients",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1
        assert data["page"] == 1
        assert "total_pages" in data

    def test_list_clients_with_search(self, client):
        """Can search clients by name."""
        token, _ = _register_owner(client)
        resp = client.get(
            "/api/admin/clients",
            headers=_auth_headers(token),
            params={"search": "Admin Co"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_admin_unauthorized_role(self, client):
        """Non-owner gets 403 on admin endpoints."""
        from database.models.core import User
        from database.base import SessionLocal
        from shared.utils.security import hash_password
        from backend.app.core.auth import (
            create_access_token as _cat,
        )

        _, owner = _register_owner(client)

        db = SessionLocal()
        agent_email = _unique_email()
        agent = User(
            email=agent_email,
            password_hash=hash_password("StrongPass1!"),
            full_name="Agent Admin",
            role="agent",
            company_id=owner["company_id"],
            is_active=True,
            is_verified=True,
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        agent_token = _cat(
            user_id=agent.id,
            company_id=owner["company_id"],
            email=agent.email,
            role="agent",
        )
        db.close()

        resp = client.get(
            "/api/admin/clients",
            headers=_auth_headers(agent_token),
        )
        assert resp.status_code == 403


class TestGetClientDetail:
    """Tests for GET /api/admin/clients/{company_id}."""

    def test_get_client_detail(self, client):
        """Get single client detail with user count."""
        token, owner = _register_owner(client)
        resp = client.get(
            f"/api/admin/clients/{owner['company_id']}",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == owner["company_id"]
        assert "user_count" in data
        assert data["user_count"] >= 1

    def test_get_client_not_found(self, client):
        """Non-existent client returns 404."""
        token, _ = _register_owner(client)
        resp = client.get(
            "/api/admin/clients/nonexistent-id",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 404


class TestUpdateClient:
    """Tests for PUT /api/admin/clients/{company_id}."""

    def test_update_client(self, client):
        """Admin can update client details."""
        token, owner = _register_owner(client)
        resp = client.put(
            f"/api/admin/clients/{owner['company_id']}",
            headers=_auth_headers(token),
            json={"name": "Updated Name", "industry": "health"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["industry"] == "health"


class TestUpdateSubscription:
    """Tests for PUT /api/admin/clients/{company_id}/subscription."""

    def test_update_client_subscription(self, client):
        """Admin can change subscription tier and status."""
        token, owner = _register_owner(client)
        resp = client.put(
            f"/api/admin/clients/{owner['company_id']}"
            f"/subscription",
            headers=_auth_headers(token),
            json={"tier": "growth", "status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subscription_tier"] == "growth"
        assert data["subscription_status"] == "active"


class TestAdminHealth:
    """Tests for GET /api/admin/health."""

    def test_admin_health(self, client):
        """Admin health returns ok."""
        token, _ = _register_owner(client)
        resp = client.get(
            "/api/admin/health",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestAPIProviders:
    """Tests for /api/admin/api-providers."""

    def test_list_api_providers(self, client):
        """List API providers returns items list."""
        token, _ = _register_owner(client)
        resp = client.get(
            "/api/admin/api-providers",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_create_api_provider(self, client):
        """Create a new API provider."""
        token, _ = _register_owner(client)
        resp = client.post(
            "/api/admin/api-providers",
            headers=_auth_headers(token),
            json={
                "name": f"Test Provider {_unique_email()}",
                "provider_type": "llm",
                "description": "A test provider",
                "required_fields": ["api_key", "model"],
                "default_endpoint": "https://api.test.com",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_type"] == "llm"
        assert data["is_active"] is True
        assert data["required_fields"] == ["api_key", "model"]

    def test_update_api_provider(self, client):
        """Update an API provider."""
        token, _ = _register_owner(client)

        # Create first
        create_resp = client.post(
            "/api/admin/api-providers",
            headers=_auth_headers(token),
            json={
                "name": f"Updatable {_unique_email()}",
                "provider_type": "email",
            },
        )
        provider_id = create_resp.json()["id"]

        # Update
        resp = client.put(
            f"/api/admin/api-providers/{provider_id}",
            headers=_auth_headers(token),
            json={"description": "Updated description"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    def test_delete_api_provider(self, client):
        """Soft-delete an API provider (is_active=False)."""
        token, _ = _register_owner(client)

        # Create first
        create_resp = client.post(
            "/api/admin/api-providers",
            headers=_auth_headers(token),
            json={
                "name": f"Deletable {_unique_email()}",
                "provider_type": "sms",
            },
        )
        provider_id = create_resp.json()["id"]

        # Delete (soft)
        resp = client.delete(
            f"/api/admin/api-providers/{provider_id}",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        assert "successfully" in resp.json()["message"].lower()

        # Verify it's soft-deleted (no longer in active list)
        list_resp = client.get(
            "/api/admin/api-providers",
            headers=_auth_headers(token),
        )
        ids = [p["id"] for p in list_resp.json()["items"]]
        assert provider_id not in ids
