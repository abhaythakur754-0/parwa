"""
Day 13: Week 2 Cross-Day Integration Tests

End-to-end tests that exercise features working TOGETHER across
Days 1-12. Validates multi-tenant isolation, auth flows, audit
trail, role enforcement, enum validation, and loophole fixes.

Each test is independent and creates its own data.
"""

import uuid

from database.base import SessionLocal  # noqa: F401
from database.models.core import Company, User
from shared.utils.security import hash_password
from backend.app.core.auth import create_access_token

from tests.conftest import *  # noqa: F401, F403

_counter = 0


def _unique_email():
    """Generate unique email for test isolation."""
    global _counter
    _counter += 1
    return f"w2integ{_counter}@d13test.parwa.local"


def _register_user(client, email=None, name="Test User",
                   company_name="Test Co"):
    """Helper: register a user and return (access_token, user_data)."""
    if email is None:
        email = _unique_email()
    resp = client.post("/api/auth/register", json={
        "email": email,
        "password": "StrongPass1!",
        "confirm_password": "StrongPass1!",
        "full_name": name,
        "company_name": company_name,
        "industry": "technology",
    })
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    return data["tokens"]["access_token"], data["user"]


def _auth_headers(token):
    """Helper: build auth headers."""
    return {"Authorization": f"Bearer {token}"}


# ── Helper functions for direct DB manipulation ─────────────────────


def _create_company(db, name="Test Corp"):
    """Create a company directly in DB."""
    company = Company(
        id=str(uuid.uuid4()),
        name=name,
        industry="technology",
        subscription_tier="mini_parwa",
        mode="shadow",
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _create_user(db, company_id, email, role="owner",
                 password="TestPass1!"):
    """Create a user directly in DB."""
    user = User(
        id=str(uuid.uuid4()),
        company_id=company_id,
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_token(user, company):
    """Create a JWT access token for a user."""
    return create_access_token(
        user_id=user.id,
        company_id=company.id,
        email=user.email,
        role=user.role,
        plan=company.subscription_tier,
    )


def _auth_header(token):
    """Build Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}


# ── Test 1: Full User Lifecycle ─────────────────────────────────────


def test_full_user_lifecycle(client):
    """Register -> Login -> Profile -> Update -> Change password
    -> Login with new password -> List team."""
    # Step 1: Register
    token, user = _register_user(
        client, email=_unique_email(),
        company_name="Lifecycle Co",
    )
    assert token is not None

    # Step 2: Login (separate session)
    login_resp = client.post("/api/auth/login", json={
        "email": user["email"],
        "password": "StrongPass1!",
    })
    assert login_resp.status_code == 200
    login_token = login_resp.json()["tokens"]["access_token"]

    # Step 3: Get profile
    resp = client.get(
        "/api/client/profile",
        headers=_auth_headers(login_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Lifecycle Co"
    assert data["industry"] == "technology"

    # Step 4: Update profile
    resp = client.put(
        "/api/client/profile",
        headers=_auth_headers(login_token),
        json={"name": "Updated Co", "industry": "finance"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Co"
    assert resp.json()["industry"] == "finance"

    # Step 5: Change password
    resp = client.put(
        "/api/client/password",
        headers=_auth_headers(login_token),
        json={
            "current_password": "StrongPass1!",
            "new_password": "NewSecure2@",
        },
    )
    assert resp.status_code == 200

    # Step 6: Login with new password
    login_resp = client.post("/api/auth/login", json={
        "email": user["email"],
        "password": "NewSecure2@",
    })
    assert login_resp.status_code == 200
    new_token = login_resp.json()["tokens"]["access_token"]

    # Step 7: List team
    resp = client.get(
        "/api/client/team",
        headers=_auth_headers(new_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(m["email"] == user["email"] for m in data["items"])


# ── Test 2: Cross-Tenant Isolation ──────────────────────────────────


def test_cross_tenant_isolation(client):
    """Two companies cannot see each other's data."""
    from database.base import SessionLocal as _SL
    db = _SL()

    # Create Company A
    comp_a = _create_company(db, name="Company A")
    user_a = _create_user(
        db, comp_a.id, _unique_email(), role="owner",
    )
    token_a = _get_token(user_a, comp_a)

    # Create Company B with a team member
    comp_b = _create_company(db, name="Company B")
    user_b = _create_user(
        db, comp_b.id, _unique_email(), role="owner",
    )
    agent_b = _create_user(
        db, comp_b.id, _unique_email(), role="agent",
    )
    token_b = _get_token(user_b, comp_b)

    # Capture emails before closing session (avoid DetachedInstance)
    email_a = user_a.email
    email_b = user_b.email
    email_agent_b = agent_b.email
    db.close()

    # Company A lists team -> should only see their own
    resp = client.get(
        "/api/client/team",
        headers=_auth_header(token_a),
    )
    assert resp.status_code == 200
    a_team = resp.json()
    assert a_team["total"] == 1
    assert a_team["items"][0]["email"] == email_a
    team_emails = [m["email"] for m in a_team["items"]]
    assert email_b not in team_emails
    assert email_agent_b not in team_emails

    # Company A updates their settings
    resp = client.put(
        "/api/client/settings",
        headers=_auth_header(token_a),
        json={"brand_voice": "Company A voice"},
    )
    assert resp.status_code == 200

    # Company B settings should still have defaults (no brand_voice)
    resp = client.get(
        "/api/client/settings",
        headers=_auth_header(token_b),
    )
    assert resp.status_code == 200
    assert resp.json()["brand_voice"] is None


# ── Test 3: Auth → Settings Auto-Create → Update ────────────────────


def test_auth_to_settings_flow(client):
    """Registration auto-creates settings, then update persists."""
    token, user = _register_user(
        client, email=_unique_email(),
    )

    # GET settings → should return defaults (auto-created)
    resp = client.get(
        "/api/client/settings",
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ooo_status"] == "inactive"
    assert data["top_k"] == 5
    assert data["similarity_threshold"] == 0.70
    assert data["brand_voice"] is None
    assert data["id"] is not None
    assert data["company_id"] is not None

    # PUT settings with brand_voice and ooo_status
    resp = client.put(
        "/api/client/settings",
        headers=_auth_headers(token),
        json={
            "brand_voice": "Professional and helpful",
            "ooo_status": "active",
            "ooo_message": "Out of office until Monday",
        },
    )
    assert resp.status_code == 200

    # GET settings again → verify updates persisted
    resp = client.get(
        "/api/client/settings",
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["brand_voice"] == "Professional and helpful"
    assert data["ooo_status"] == "active"
    assert data["ooo_message"] == "Out of office until Monday"
    # Unchanged fields should remain at defaults
    assert data["top_k"] == 5
    assert data["similarity_threshold"] == 0.70


# ── Test 4: Team Management Flow ────────────────────────────────────


def test_team_management_flow(client):
    """Register -> Add team member -> Update role -> Remove."""
    from database.base import SessionLocal as _SL
    db = _SL()

    # Register company with owner
    token, owner = _register_user(
        client, email=_unique_email(),
        company_name="Team Co",
    )

    # Create a second user directly in DB for same company
    agent = _create_user(
        db, owner["company_id"], _unique_email(), role="agent",
    )
    db.close()

    # List team -> should see both users
    resp = client.get(
        "/api/client/team",
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    emails = [m["email"] for m in data["items"]]
    assert owner["email"] in emails
    assert agent.email in emails

    # Update second user's role to "agent" (already agent, test
    # update path works)
    resp = client.put(
        f"/api/client/team/{agent.id}",
        headers=_auth_headers(token),
        json={"role": "viewer"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "viewer"

    # Remove second user (soft delete)
    resp = client.delete(
        f"/api/client/team/{agent.id}",
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    assert "successfully" in resp.json()["message"].lower()

    # List team -> second user still visible but is_active=False
    resp = client.get(
        "/api/client/team",
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    removed = [m for m in data["items"] if m["id"] == agent.id]
    assert len(removed) == 1
    assert removed[0]["is_active"] is False


# ── Test 5: Audit Trail Persisted ───────────────────────────────────


def test_audit_trail_persisted(client):
    """log_audit with db= writes to audit_trail table."""
    from database.base import SessionLocal as _SL
    from database.models.integration import AuditTrail

    # Create company + user + get JWT via direct DB
    db = _SL()
    comp = _create_company(db, name="Audit Co")
    user = _create_user(
        db, comp.id, _unique_email(), role="owner",
    )
    token = _get_token(user, comp)
    db.close()

    # Call PUT /api/client/profile to trigger audit log
    resp = client.put(
        "/api/client/profile",
        headers=_auth_header(token),
        json={"name": "Audit Updated"},
    )
    assert resp.status_code == 200

    # Query audit_trail table directly
    db = SessionLocal()
    entries = db.query(AuditTrail).filter(
        AuditTrail.company_id == comp.id,
    ).all()
    db.close()

    assert len(entries) >= 1
    entry = entries[0]
    assert entry.company_id == comp.id
    assert entry.action == "update"
    assert entry.resource_type == "company"
    assert entry.resource_id == comp.id
    assert entry.actor_id == user.id
    assert entry.actor_type == "user"


# ── Test 6: JWT Error No Leak ───────────────────────────────────────


def test_jwt_error_no_leak(client_no_raise):
    """L21: JWT error response doesn't leak internal details."""
    # Send request with malformed JWT token
    resp = client_no_raise.get(
        "/api/client/profile",
        headers={"Authorization": "Bearer this.is.invalid.jwt"},
    )

    # Should return 401
    assert resp.status_code == 401

    body = resp.text
    # Response should say "Invalid or expired token"
    assert "Invalid or expired token" in body

    # Response must NOT contain jose/python-jose error strings
    assert "Signature verification failed" not in body
    assert "ExpiredSignatureError" not in body
    assert "DecodeError" not in body
    assert "jose" not in body.lower()
    assert "python-jose" not in body.lower()
    assert "jwt" not in body.lower() or "jwt" not in body


# ── Test 7: Password Validation Cross-Day ───────────────────────────


def test_password_validation_cross_day(client):
    """L02 password rules work in password change too."""
    token, _ = _register_user(
        client, email=_unique_email(),
    )

    # Try to change password to "weak" (no special char) -> 422
    resp = client.put(
        "/api/client/password",
        headers=_auth_headers(token),
        json={
            "current_password": "StrongPass1!",
            "new_password": "weak",
        },
    )
    assert resp.status_code == 422

    # Try to change password with no uppercase -> 422
    resp = client.put(
        "/api/client/password",
        headers=_auth_headers(token),
        json={
            "current_password": "StrongPass1!",
            "new_password": "lowercase1!",
        },
    )
    assert resp.status_code == 422

    # Try to change password with no digit -> 422
    resp = client.put(
        "/api/client/password",
        headers=_auth_headers(token),
        json={
            "current_password": "StrongPass1!",
            "new_password": "NoDigits!!",
        },
    )
    assert resp.status_code == 422

    # Change to a valid strong password -> 200
    resp = client.put(
        "/api/client/password",
        headers=_auth_headers(token),
        json={
            "current_password": "StrongPass1!",
            "new_password": "StrongPass1!",
        },
    )
    assert resp.status_code == 200


# ── Test 8: Admin API Provider Flow ─────────────────────────────────


def test_admin_api_provider_flow(client):
    """Admin CRUD on API providers."""
    from database.base import SessionLocal as _SL
    db = _SL()
    comp = _create_company(db, name="Admin Provider Co")
    user = _create_user(
        db, comp.id, _unique_email(), role="owner",
    )
    token = _get_token(user, comp)
    db.close()

    # POST -> create provider
    resp = client.post(
        "/api/admin/api-providers",
        headers=_auth_header(token),
        json={
            "name": f"Test LLM {uuid.uuid4().hex[:6]}",
            "provider_type": "llm",
            "description": "Test LLM provider",
            "required_fields": ["api_key"],
            "default_endpoint": "https://api.test.com/v1",
        },
    )
    assert resp.status_code == 200
    provider = resp.json()
    provider_id = provider["id"]
    assert provider["provider_type"] == "llm"
    assert provider["is_active"] is True

    # GET -> verify in list
    resp = client.get(
        "/api/admin/api-providers",
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    found = [p for p in items if p["id"] == provider_id]
    assert len(found) == 1

    # PUT -> update
    resp = client.put(
        f"/api/admin/api-providers/{provider_id}",
        headers=_auth_header(token),
        json={
            "name": f"Updated LLM {uuid.uuid4().hex[:6]}",
            "description": "Updated description",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated description"

    # DELETE -> soft delete
    resp = client.delete(
        f"/api/admin/api-providers/{provider_id}",
        headers=_auth_header(token),
    )
    assert resp.status_code == 200

    # GET -> verify NOT in list (is_active=False)
    resp = client.get(
        "/api/admin/api-providers",
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    found = [p for p in items if p["id"] == provider_id]
    assert len(found) == 0


# ── Test 9: Role Hierarchy Enforcement ──────────────────────────────


def test_role_hierarchy_enforcement(client):
    """Viewer cannot access team, admin can."""
    from database.base import SessionLocal as _SL
    db = _SL()

    # Create company with owner
    comp = _create_company(db, name="Role Co")
    owner = _create_user(
        db, comp.id, _unique_email(), role="owner",
    )

    # Create user with role="viewer"
    viewer = _create_user(
        db, comp.id, _unique_email(), role="viewer",
    )

    # Create user with role="admin"
    admin = _create_user(
        db, comp.id, _unique_email(), role="admin",
    )

    owner_token = _get_token(owner, comp)
    viewer_token = _get_token(viewer, comp)
    admin_token = _get_token(admin, comp)
    db.close()

    # Viewer tries GET /api/client/team -> 403
    resp = client.get(
        "/api/client/team",
        headers=_auth_header(viewer_token),
    )
    assert resp.status_code == 403

    # Owner tries GET /api/client/team -> 200
    resp = client.get(
        "/api/client/team",
        headers=_auth_header(owner_token),
    )
    assert resp.status_code == 200

    # Admin tries GET /api/client/team -> 200
    resp = client.get(
        "/api/client/team",
        headers=_auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 3


# ── Test 10: Subscription Enum Validation ───────────────────────────


def test_subscription_enum_validation(client):
    """L23 fix: Subscription enums enforced."""
    from database.base import SessionLocal as _SL
    db = _SL()

    comp = _create_company(db, name="Enum Co")
    user = _create_user(
        db, comp.id, _unique_email(), role="owner",
    )
    token = _get_token(user, comp)
    db.close()

    # Try PUT /api/admin/clients/{id} with invalid subscription_tier
    resp = client.put(
        f"/api/admin/clients/{comp.id}",
        headers=_auth_header(token),
        json={"subscription_tier": "invalid_tier"},
    )
    assert resp.status_code == 422

    # Try PUT /api/admin/clients/{id}/subscription with valid enum
    resp = client.put(
        f"/api/admin/clients/{comp.id}/subscription",
        headers=_auth_header(token),
        json={"tier": "parwa", "status": "active"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["subscription_tier"] == "parwa"

    # Try with another valid tier
    resp = client.put(
        f"/api/admin/clients/{comp.id}/subscription",
        headers=_auth_header(token),
        json={"tier": "enterprise"},
    )
    assert resp.status_code == 200
    assert resp.json()["subscription_tier"] == "enterprise"

    # Try with an invalid status enum
    resp = client.put(
        f"/api/admin/clients/{comp.id}/subscription",
        headers=_auth_header(token),
        json={"status": "not_a_real_status"},
    )
    assert resp.status_code == 422
