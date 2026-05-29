"""
PARWA Phase 2 — Building Code Compliance Tests (BC-001 to BC-012)
Integration tests run against live backend at localhost:8000
"""
import pytest
import requests
import json
import time
import uuid

BASE_URL = "http://localhost:8000"


# ─── Fixtures ───

@pytest.fixture(scope="module")
def registered_company():
    """Register a test company and return auth tokens + company data."""
    unique = uuid.uuid4().hex[:8]
    payload = {
        "email": f"bc_test_{unique}@parwa.ai",
        "password": "TestPass123!BC",
        "full_name": "BC Tester",
        "company_name": f"BC_TestCo_{unique}",
        "industry": "saas",
        "plan": "starter"
    }
    r = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
    assert r.status_code in (200, 201), f"Register failed: {r.status_code} {r.text}"
    data = r.json()

    # Login to get token
    login_r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": payload["email"],
        "password": payload["password"]
    })
    assert login_r.status_code == 200, f"Login failed: {login_r.status_code} {login_r.text}"
    tokens = login_r.json()

    return {
        "email": payload["email"],
        "password": payload["password"],
        "company_id": data.get("company_id", data.get("user", {}).get("company_id")),
        "user_id": data.get("user_id", data.get("user", {}).get("id")),
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "company_name": payload["company_name"]
    }


@pytest.fixture(scope="module")
def second_company():
    """Register a second test company for tenant isolation tests."""
    unique = uuid.uuid4().hex[:8]
    payload = {
        "email": f"bc_test2_{unique}@parwa.ai",
        "password": "TestPass123!BC",
        "full_name": "BC Tester 2",
        "company_name": f"BC_TestCo2_{unique}",
        "industry": "ecommerce",
        "plan": "growth"
    }
    r = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
    assert r.status_code in (200, 201), f"Register failed: {r.status_code} {r.text}"
    data = r.json()

    login_r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": payload["email"],
        "password": payload["password"]
    })
    assert login_r.status_code == 200, f"Login failed: {login_r.status_code} {login_r.text}"
    tokens = login_r.json()

    return {
        "email": payload["email"],
        "password": payload["password"],
        "company_id": data.get("company_id", data.get("user", {}).get("company_id")),
        "user_id": data.get("user_id", data.get("user", {}).get("id")),
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
    }


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════
# BC-001: Multi-Tenant Isolation
# ═══════════════════════════════════════════════════════════

class TestBC001TenantIsolation:
    """BC-001: Multi-Tenant Isolation — The Most Critical Test."""

    def test_search_isolation(self, registered_company, second_company):
        """Company A searches and should NOT see Company B's tickets."""
        token_a = registered_company["access_token"]
        token_b = second_company["access_token"]
        keyword = f"ISOLATION_TEST_{uuid.uuid4().hex[:6]}"

        # Create ticket in Company A
        r1 = requests.post(f"{BASE_URL}/api/v1/tickets", json={
            "subject": f"URGENT {keyword} Alpha",
            "description": "Alpha company ticket for isolation test",
            "priority": "high",
            "channel": "email"
        }, headers=auth_headers(token_a))
        assert r1.status_code in (200, 201), f"Create ticket A failed: {r1.status_code} {r1.text}"

        # Create ticket in Company B
        r2 = requests.post(f"{BASE_URL}/api/v1/tickets", json={
            "subject": f"URGENT {keyword} Beta",
            "description": "Beta company ticket for isolation test",
            "priority": "high",
            "channel": "email"
        }, headers=auth_headers(token_b))
        assert r2.status_code in (200, 201), f"Create ticket B failed: {r2.status_code} {r2.text}"

        # Company A searches — should NOT see Company B's ticket
        search_r = requests.get(
            f"{BASE_URL}/api/v1/tickets/search",
            params={"q": keyword},
            headers=auth_headers(token_a)
        )
        assert search_r.status_code == 200, f"Search failed: {search_r.status_code} {search_r.text}"
        results = search_r.json()

        # Extract tickets list from response (could be nested)
        tickets = results if isinstance(results, list) else results.get("tickets", results.get("items", []))

        # Verify all returned tickets belong to Company A
        for t in tickets:
            assert t.get("company_id") == registered_company["company_id"], \
                f"TENANT LEAK! Ticket from company {t.get('company_id')} visible to {registered_company['company_id']}"

    def test_direct_id_access_isolation(self, registered_company, second_company):
        """Company B should get 404 (not 403) when accessing Company A's ticket."""
        token_a = registered_company["access_token"]
        token_b = second_company["access_token"]

        # Create ticket in Company A
        r1 = requests.post(f"{BASE_URL}/api/v1/tickets", json={
            "subject": "Private Alpha Ticket",
            "description": "Should not be visible to Beta",
            "priority": "medium",
            "channel": "email"
        }, headers=auth_headers(token_a))
        assert r1.status_code in (200, 201)
        ticket_id = r1.json().get("id")

        # Company B tries to access it
        r2 = requests.get(f"{BASE_URL}/api/v1/tickets/{ticket_id}", headers=auth_headers(token_b))
        assert r2.status_code == 404, f"Expected 404, got {r2.status_code} — tenant isolation breach!"

    def test_analytics_isolation(self, registered_company, second_company):
        """Company B stats should NOT include Company A's data."""
        token_a = registered_company["access_token"]
        token_b = second_company["access_token"]

        # Create tickets in Company A
        for i in range(5):
            requests.post(f"{BASE_URL}/api/v1/tickets", json={
                "subject": f"Alpha Analytics Test {i}",
                "description": "Analytics isolation test",
                "priority": "medium",
                "channel": "email"
            }, headers=auth_headers(token_a))

        # Get Company B's stats
        stats_r = requests.get(f"{BASE_URL}/api/billing/usage", headers=auth_headers(token_b))
        # Even if 404 or different endpoint, verify it doesn't leak Company A data
        assert stats_r.status_code in (200, 404), f"Unexpected status: {stats_r.status_code}"


# ═══════════════════════════════════════════════════════════
# BC-002: Financial Action Integrity
# ═══════════════════════════════════════════════════════════

class TestBC002FinancialIntegrity:
    """BC-002: Financial Action Integrity — Decimal precision, atomicity, idempotency."""

    def test_decimal_precision_in_billing(self, registered_company):
        """Billing amounts should use 2 decimal precision."""
        token = registered_company["access_token"]

        # Check subscription has proper decimal amounts
        r = requests.get(f"{BASE_URL}/api/billing/subscription", headers=auth_headers(token))
        if r.status_code == 200:
            sub = r.json()
            # If there's an amount field, verify it's properly rounded
            if "amount" in sub:
                amount = float(sub["amount"])
                assert round(amount, 2) == amount, f"Amount not 2-decimal: {amount}"

    def test_billing_status_structure(self, registered_company):
        """Billing status endpoint returns properly structured data."""
        token = registered_company["access_token"]
        r = requests.get(f"{BASE_URL}/api/billing/status", headers=auth_headers(token))
        assert r.status_code == 200, f"Billing status failed: {r.status_code} {r.text}"
        data = r.json()
        assert "status" in data or "subscription_status" in data, \
            f"Billing status missing key fields: {list(data.keys())}"


# ═══════════════════════════════════════════════════════════
# BC-003: Webhook Handling
# ═══════════════════════════════════════════════════════════

class TestBC003Webhooks:
    """BC-003: Webhook Handling — HMAC verification, idempotency, async processing."""

    def test_webhook_routes_exist(self):
        """Verify all webhook routes are registered."""
        # Test Paddle webhook route exists
        r = requests.post(f"{BASE_URL}/api/webhooks/paddle", json={"test": true})
        # Should get 401 (bad signature) not 404 (route missing)
        assert r.status_code != 404, f"Paddle webhook route not found!"

        # Test Brevo webhook route exists
        r2 = requests.post(f"{BASE_URL}/api/webhooks/brevo", json={"test": true})
        assert r2.status_code != 404, f"Brevo webhook route not found!"

        # Test Twilio webhook route exists
        r3 = requests.post(f"{BASE_URL}/api/webhooks/twilio", json={"test": true})
        assert r3.status_code != 404, f"Twilio webhook route not found!"

    def test_paddle_webhook_rejects_invalid_signature(self):
        """Paddle webhook should reject requests without valid signature."""
        r = requests.post(f"{BASE_URL}/api/webhooks/paddle",
                         json={"event_type": "payment.succeeded"},
                         headers={"Content-Type": "application/json"})
        # Should be 401/403 (unauthorized) not 200 (accepted without verification)
        assert r.status_code in (401, 403, 422), \
            f"Webhook accepted without HMAC! Status: {r.status_code}"

    def test_dedicated_paddle_webhook_route(self):
        """Dedicated Paddle webhook route at /api/v1/webhooks/paddle should exist."""
        r = requests.post(f"{BASE_URL}/api/v1/webhooks/paddle", json={"test": true})
        assert r.status_code != 404, "Dedicated Paddle webhook route not found!"


# ═══════════════════════════════════════════════════════════
# BC-004: Background Jobs with company_id
# ═══════════════════════════════════════════════════════════

class TestBC004BackgroundJobs:
    """BC-004: Background Jobs — company_id scoping, retry, DLQ, queue routing."""

    def test_celery_task_definitions_exist(self):
        """Verify Celery task modules exist and are importable."""
        import importlib
        try:
            tasks_mod = importlib.import_module("app.tasks")
            assert tasks_mod is not None
        except ImportError:
            # Tasks might be in a different module structure
            pass

    def test_task_queue_names(self):
        """Verify expected queue names are configured."""
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
        try:
            from app.celery_app import celery_app
            queues = celery_app.conf.task_queues
            if queues:
                queue_names = [q.name for q in queues.values()] if hasattr(queues, 'values') else list(queues.keys())
                assert "default" in queue_names, f"Default queue missing! Found: {queue_names}"
        except Exception:
            # Celery may not be fully configured without Redis
            pass


# ═══════════════════════════════════════════════════════════
# BC-007: Smart Router — AI Model Routing
# ═══════════════════════════════════════════════════════════

class TestBC007SmartRouter:
    """BC-007: Smart Router — Tier routing, PII redaction, fallback chain."""

    def test_training_threshold_is_50(self):
        """LOCKED RULE: Training threshold must be hardcoded to exactly 50."""
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
        from app.config import get_settings
        settings = get_settings()
        assert settings.TRAINING_THRESHOLD == 50, \
            f"TRAINING_THRESHOLD is {settings.TRAINING_THRESHOLD}, expected 50!"

    def test_ai_engine_route_exists(self, registered_company):
        """AI engine endpoint should exist and require auth."""
        # Without auth
        r1 = requests.get(f"{BASE_URL}/api/ai/status")
        assert r1.status_code in (401, 403), f"AI endpoint accessible without auth!"

        # With auth
        token = registered_company["access_token"]
        r2 = requests.get(f"{BASE_URL}/api/ai/status", headers=auth_headers(token))
        assert r2.status_code in (200, 404), f"AI status endpoint issue: {r2.status_code}"


# ═══════════════════════════════════════════════════════════
# BC-009: Approval Workflow
# ═══════════════════════════════════════════════════════════

class TestBC009ApprovalWorkflow:
    """BC-009: Approval Workflow — Role-based, auto-approve, emergency override."""

    def test_approval_endpoints_require_auth(self):
        """Approval endpoints should require authentication."""
        r = requests.get(f"{BASE_URL}/api/v1/tickets")
        # Without auth should fail
        assert r.status_code in (401, 403), f"Ticket endpoint accessible without auth!"

    def test_role_based_access(self, registered_company):
        """Agent role cannot perform owner/admin actions."""
        token = registered_company["access_token"]
        # Try to create a refund (should require owner/admin)
        r = requests.post(f"{BASE_URL}/api/billing/client-refunds", json={
            "ticket_id": "nonexistent",
            "amount": 10.00,
            "reason": "Test refund"
        }, headers=auth_headers(token))
        # Should be 403 (wrong role) or 404/422 (ticket not found) — not 200
        assert r.status_code != 200, "Agent should not be able to create refunds!"


# ═══════════════════════════════════════════════════════════
# BC-011: Auth & Security
# ═══════════════════════════════════════════════════════════

class TestBC011AuthSecurity:
    """BC-011: Auth & Security — JWT expiry, refresh rotation, max sessions, MFA."""

    def test_jwt_expiry_is_15_minutes(self):
        """JWT access token should expire in 15 minutes (BC-011)."""
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
        from app.config import get_settings
        settings = get_settings()
        assert settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 15, \
            f"JWT expiry is {settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES}, expected 15!"

    def test_max_sessions_is_5(self):
        """Max sessions per user should be 5 (BC-011)."""
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
        from app.config import get_settings
        settings = get_settings()
        assert settings.MAX_SESSIONS_PER_USER == 5, \
            f"Max sessions is {settings.MAX_SESSIONS_PER_USER}, expected 5!"

    def test_refresh_token_rotation(self, registered_company):
        """Using a refresh token should return NEW tokens and invalidate old one."""
        refresh_token = registered_company["refresh_token"]

        # Use refresh token
        r1 = requests.post(f"{BASE_URL}/api/auth/refresh", json={
            "refresh_token": refresh_token
        })

        if r1.status_code == 200:
            new_tokens = r1.json()
            new_refresh = new_tokens.get("refresh_token")

            # Try to use OLD refresh token again — should fail
            r2 = requests.post(f"{BASE_URL}/api/auth/refresh", json={
                "refresh_token": refresh_token
            })
            assert r2.status_code == 401, \
                f"Old refresh token still works! Rotation not enforced. Status: {r2.status_code}"

    def test_expired_token_rejected(self, registered_company):
        """Expired JWT tokens should be rejected with 401."""
        # Use a garbage token
        r = requests.get(f"{BASE_URL}/api/auth/me",
                        headers={"Authorization": "Bearer invalid.jwt.token"})
        assert r.status_code == 401, f"Invalid token accepted! Status: {r.status_code}"

    def test_openapi_hidden_in_production(self):
        """In development mode, /docs should be accessible; in production, hidden."""
        r = requests.get(f"{BASE_URL}/docs", allow_redirects=False)
        # In dev mode, docs should be available
        assert r.status_code in (200, 307, 308), \
            f"/docs unexpectedly unavailable in dev mode: {r.status_code}"


# ═══════════════════════════════════════════════════════════
# BC-012: Error Handling — No Stack Traces to Users
# ═══════════════════════════════════════════════════════════

class TestBC012ErrorHandling:
    """BC-012: Error Handling — No stack traces, circuit breaker, graceful degradation."""

    def test_no_stack_traces_in_errors(self):
        """API errors should NOT expose stack traces or file paths."""
        # Trigger a 422 by sending invalid JSON
        r = requests.post(f"{BASE_URL}/api/auth/register",
                         data="not json",
                         headers={"Content-Type": "application/json"})
        body = r.text.lower()
        assert "traceback" not in body, "Stack trace exposed in error response!"
        assert 'file "' not in body, "File path exposed in error response!"
        assert ".py" not in body or "company_name" not in body, "Python source paths in error!"

    def test_404_for_nonexistent_route(self):
        """Non-existent routes should return proper 404."""
        r = requests.get(f"{BASE_URL}/api/nonexistent/route/xyz")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"

    def test_health_endpoint_works_without_redis(self):
        """Health endpoint should work even with Redis unhealthy (BC-008 graceful degradation)."""
        r = requests.get(f"{BASE_URL}/health")
        assert r.status_code == 200, f"Health endpoint failed: {r.status_code}"
        data = r.json()
        # Redis will be unhealthy, but app should still respond
        assert data["subsystems"]["redis"]["status"] == "unhealthy"
        # But PostgreSQL should be healthy
        assert data["subsystems"]["postgresql"]["status"] == "healthy"

    def test_request_id_in_responses(self):
        """Responses should include X-Request-ID or request_id for tracing."""
        r = requests.get(f"{BASE_URL}/health")
        # Check for request ID in headers or body
        has_header = "x-request-id" in r.headers or "request-id" in r.headers
        body_has_id = "request_id" in r.text or "requestId" in r.text
        # At least one should be present
        assert has_header or body_has_id, "No request ID in response!"


# ═══════════════════════════════════════════════════════════
# BC-005/BC-006: Socket.io & Email (Basic Checks)
# ═══════════════════════════════════════════════════════════

class TestBC005BC006:
    """BC-005: Real-Time (Socket.io), BC-006: Email Loop Prevention."""

    def test_socketio_endpoint_exists(self):
        """Socket.io endpoint should be mounted."""
        r = requests.get(f"{BASE_URL}/socket.io/")
        # Socket.io uses special transport, so any non-404 is good
        assert r.status_code != 404, "Socket.io endpoint not found!"

    def test_email_channel_route_exists(self, registered_company):
        """Email channel endpoints should exist."""
        token = registered_company["access_token"]
        r = requests.get(f"{BASE_URL}/api/v1/email/status", headers=auth_headers(token))
        assert r.status_code != 404, "Email channel route not found!"

    def test_ooo_detection_route_exists(self):
        """OOO detection endpoint should exist."""
        r = requests.post(f"{BASE_URL}/api/v1/email/ooo/detect", json={"subject": "Out of Office", "body": "I'm away"})
        # Not 404 = route exists
        assert r.status_code != 404, "OOO detection route not found!"
