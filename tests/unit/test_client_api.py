"""
Day 12: Client API Endpoint Tests

Tests for /api/client/* routes: profile, settings, password,
team management.

BC-001: All queries filtered by company_id.
BC-011: JWT auth required.
BC-012: Structured JSON responses.
"""

from tests.conftest import *  # noqa: F401, F403

_counter = 0


def _unique_email():
    """Generate unique email for test isolation."""
    global _counter
    _counter += 1
    return f"user{_counter}@d12test.parwa.local"


def _register_user(client, email=None, name="Test User"):
    """Helper: register a user and return (access_token, user_data)."""
    if email is None:
        email = _unique_email()
    resp = client.post("/api/auth/register", json={
        "email": email,
        "password": "StrongPass1!",
        "confirm_password": "StrongPass1!",
        "full_name": name,
        "company_name": "Test Co",
        "industry": "technology",
    })
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    return data["tokens"]["access_token"], data["user"]


def _auth_headers(token):
    """Helper: build auth headers."""
    return {"Authorization": f"Bearer {token}"}


class TestGetProfile:
    """Tests for GET /api/client/profile."""

    def test_get_profile_success(self, client):
        """Valid token returns company profile."""
        token, user = _register_user(client)
        resp = client.get(
            "/api/client/profile",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Co"
        assert data["industry"] == "technology"
        assert data["subscription_tier"] == "starter"
        assert data["mode"] == "shadow"
        assert "id" in data
        assert "created_at" in data

    def test_get_profile_unauthorized(self, client):
        """No auth header returns 401."""
        resp = client.get("/api/client/profile")
        assert resp.status_code == 401


class TestUpdateProfile:
    """Tests for PUT /api/client/profile."""

    def test_update_profile_success(self, client):
        """Update name and industry."""
        token, _ = _register_user(client)
        resp = client.put(
            "/api/client/profile",
            headers=_auth_headers(token),
            json={"name": "Updated Co", "industry": "finance"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Co"
        assert data["industry"] == "finance"

    def test_update_profile_partial(self, client):
        """Update only name, industry stays same."""
        token, _ = _register_user(client)
        resp = client.put(
            "/api/client/profile",
            headers=_auth_headers(token),
            json={"name": "Partial Co"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Partial Co"
        assert data["industry"] == "technology"


class TestGetSettings:
    """Tests for GET /api/client/settings."""

    def test_get_settings_auto_creates(self, client):
        """Settings auto-created with defaults when not found."""
        token, _ = _register_user(client)
        resp = client.get(
            "/api/client/settings",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ooo_status"] == "inactive"
        assert data["top_k"] == 5
        assert data["similarity_threshold"] == 0.70
        assert data["prohibited_phrases"] == []
        assert data["pii_patterns"] == []
        assert "id" in data
        assert "company_id" in data

    def test_get_settings_unauthorized(self, client):
        """No auth header returns 401."""
        resp = client.get("/api/client/settings")
        assert resp.status_code == 401


class TestUpdateSettings:
    """Tests for PUT /api/client/settings."""

    def test_update_settings_success(self, client):
        """Update brand_voice and ooo_status."""
        token, _ = _register_user(client)
        resp = client.put(
            "/api/client/settings",
            headers=_auth_headers(token),
            json={
                "brand_voice": "Professional and helpful",
                "ooo_status": "active",
                "ooo_message": "Out of office",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["brand_voice"] == "Professional and helpful"
        assert data["ooo_status"] == "active"
        assert data["ooo_message"] == "Out of office"

    def test_update_settings_lists(self, client):
        """Update list fields (prohibited_phrases, etc.)."""
        token, _ = _register_user(client)
        resp = client.put(
            "/api/client/settings",
            headers=_auth_headers(token),
            json={
                "prohibited_phrases": ["no way", "impossible"],
                "intent_labels": ["refund", "support"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prohibited_phrases"] == [
            "no way", "impossible",
        ]
        assert data["intent_labels"] == ["refund", "support"]


class TestChangePassword:
    """Tests for PUT /api/client/password."""

    def test_change_password_success(self, client):
        """Correct current password changes password."""
        token, user = _register_user(client)
        resp = client.put(
            "/api/client/password",
            headers=_auth_headers(token),
            json={
                "current_password": "StrongPass1!",
                "new_password": "NewStrong2@",
            },
        )
        assert resp.status_code == 200
        assert "successfully" in resp.json()["message"].lower()

        # Old password should no longer work
        login_resp = client.post("/api/auth/login", json={
            "email": user["email"],
            "password": "StrongPass1!",
        })
        assert login_resp.status_code == 401

        # New password should work
        login_resp = client.post("/api/auth/login", json={
            "email": user["email"],
            "password": "NewStrong2@",
        })
        assert login_resp.status_code == 200

    def test_change_password_wrong_current(self, client):
        """Wrong current password returns validation error."""
        token, _ = _register_user(client)
        resp = client.put(
            "/api/client/password",
            headers=_auth_headers(token),
            json={
                "current_password": "WrongPassword1!",
                "new_password": "NewStrong2@",
            },
        )
        assert resp.status_code == 422

    def test_change_password_weak_new(self, client):
        """Weak new password returns 422."""
        token, _ = _register_user(client)
        resp = client.put(
            "/api/client/password",
            headers=_auth_headers(token),
            json={
                "current_password": "StrongPass1!",
                "new_password": "weak",
            },
        )
        assert resp.status_code == 422


class TestGetTeam:
    """Tests for GET /api/client/team."""

    def test_get_team_success(self, client):
        """List team members returns owner."""
        token, _ = _register_user(client)
        resp = client.get(
            "/api/client/team",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert data["items"][0]["role"] == "owner"
        assert "password_hash" not in str(data)
        assert "mfa_secret" not in str(data)

    def test_get_team_unauthorized_role(self, client):
        """Viewer cannot list team (403)."""
        from database.models.core import User
        from database.base import SessionLocal
        from shared.utils.security import hash_password
        from backend.app.core.auth import (
            create_access_token as _cat,
        )

        _, user = _register_user(
            client, email=_unique_email(),
        )

        db = SessionLocal()
        viewer_email = _unique_email()
        viewer = User(
            email=viewer_email,
            password_hash=hash_password("StrongPass1!"),
            full_name="Viewer User",
            role="viewer",
            company_id=user["company_id"],
            is_active=True,
            is_verified=True,
        )
        db.add(viewer)
        db.commit()
        db.refresh(viewer)

        viewer_token = _cat(
            user_id=viewer.id,
            company_id=user["company_id"],
            email=viewer.email,
            role="viewer",
        )
        db.close()

        resp = client.get(
            "/api/client/team",
            headers=_auth_headers(viewer_token),
        )
        assert resp.status_code == 403

    def test_get_team_pagination(self, client):
        """Pagination params work correctly."""
        token, _ = _register_user(client)
        resp = client.get(
            "/api/client/team",
            headers=_auth_headers(token),
            params={"page": 1, "per_page": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["per_page"] == 5
        assert data["total"] >= 1
        assert data["total_pages"] >= 1


class TestUpdateTeamMember:
    """Tests for PUT /api/client/team/{user_id}."""

    def test_update_team_member_role(self, client):
        """Admin can change agent role to viewer."""
        from database.models.core import User
        from database.base import SessionLocal
        from shared.utils.security import hash_password

        token, owner = _register_user(
            client, email=_unique_email(),
        )

        db = SessionLocal()
        agent_email = _unique_email()
        agent = User(
            email=agent_email,
            password_hash=hash_password("StrongPass1!"),
            full_name="Agent User",
            role="agent",
            company_id=owner["company_id"],
            is_active=True,
            is_verified=True,
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        db.close()

        resp = client.put(
            f"/api/client/team/{agent.id}",
            headers=_auth_headers(token),
            json={"role": "viewer"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    def test_update_team_member_cannot_remove_last_owner(self, client):
        """Cannot demote the last owner."""
        token, _ = _register_user(
            client, email=_unique_email(),
        )

        # Try to change own role (the only owner)
        me_resp = client.get(
            "/api/auth/me", headers=_auth_headers(token),
        )
        user_id = me_resp.json()["id"]

        resp = client.put(
            f"/api/client/team/{user_id}",
            headers=_auth_headers(token),
            json={"role": "admin"},
        )
        assert resp.status_code == 422


class TestRemoveTeamMember:
    """Tests for DELETE /api/client/team/{user_id}."""

    def test_remove_team_member_success(self, client):
        """Owner can remove an agent."""
        from database.models.core import User
        from database.base import SessionLocal
        from shared.utils.security import hash_password

        token, owner = _register_user(
            client, email=_unique_email(),
        )

        db = SessionLocal()
        agent_email = _unique_email()
        agent = User(
            email=agent_email,
            password_hash=hash_password("StrongPass1!"),
            full_name="Remove Me",
            role="agent",
            company_id=owner["company_id"],
            is_active=True,
            is_verified=True,
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        db.close()

        resp = client.delete(
            f"/api/client/team/{agent.id}",
            headers=_auth_headers(token),
        )
        assert resp.status_code == 200
        assert "successfully" in resp.json()["message"].lower()
