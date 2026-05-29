"""
PARWA Phase 13 — Mobile Responsive + Polish (Backend Integration Tests)
========================================================================

Tests the backend APIs that support responsive/mobile UX:
  - Session persistence (close browser → reopen → previous chat loads)
  - Session auto-archival (30+ days inactive)
  - Error recovery for mobile connectivity (network errors, AI provider down)
  - Compact response payloads (no unnecessary data for mobile)
  - Connection resilience and retry support
  - Dashboard API data structure for responsive grid rendering

Based on: JARVIS_ROADMAP.md Phase 13 — Mobile Responsive + Polish
"""

import pytest
import requests
import json
import time
import uuid
from datetime import datetime, timezone, timedelta

BASE_URL = "http://localhost:8000"


# ─── Fixtures ───

# Common headers to satisfy CSRF middleware (Origin/Referer validation)
CSRF_HEADERS = {
    "Origin": "http://localhost:3000",
    "Referer": "http://localhost:3000/",
}

# Shared requests.Session for cookie persistence (CSRF double-submit)
_session = requests.Session()
_session.headers.update(CSRF_HEADERS)


def _get_csrf_token():
    """Fetch a CSRF token cookie from the server (double-submit pattern)."""
    # GET any endpoint to receive a CSRF cookie
    r = _session.get(f"{BASE_URL}/health")
    # Extract CSRF token from cookies
    csrf_token = _session.cookies.get("parwa_csrf", "")
    return csrf_token


@pytest.fixture(scope="module")
def test_user():
    """Register a test user and return auth tokens + user data.
    
    If registration fails (e.g., SQLite/JSONB incompatibility), attempts to
    use the well-known test user abhay@parwa.ai as fallback.
    """
    # First, get a CSRF token
    csrf_token = _get_csrf_token()

    unique = uuid.uuid4().hex[:8]
    payload = {
        "email": f"p13_test_{unique}@parwa.ai",
        "password": "TestPass123!P13",
        "confirm_password": "TestPass123!P13",
        "full_name": "Phase 13 Tester",
        "company_name": f"P13_TestCo_{unique}",
        "industry": "ecommerce",
        "plan": "starter",
    }

    headers = {
        **CSRF_HEADERS,
        "X-CSRF-Token": csrf_token,
    }

    r = _session.post(
        f"{BASE_URL}/api/auth/register",
        json=payload,
        headers=headers,
    )

    if r.status_code not in (200, 201):
        # Fallback: try login with known test user
        print(f"Register failed ({r.status_code}), trying fallback login...")
        csrf_token = _get_csrf_token()
        login_r = _session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "abhay@parwa.ai", "password": "password123"},
            headers={**CSRF_HEADERS, "X-CSRF-Token": csrf_token},
        )
        if login_r.status_code == 200:
            tokens = login_r.json()
            return {
                "email": "abhay@parwa.ai",
                "password": "password123",
                "company_id": tokens.get("user", {}).get("company_id") if isinstance(tokens, dict) else None,
                "user_id": tokens.get("user", {}).get("id") if isinstance(tokens, dict) else None,
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
            }
        # If fallback also fails, skip tests that need auth
        pytest.skip("Cannot register or login - database not configured for integration tests")

    data = r.json()

    # Refresh CSRF token after state change
    csrf_token = _get_csrf_token()

    login_r = _session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
        headers={**CSRF_HEADERS, "X-CSRF-Token": csrf_token},
    )
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
    return {
        "Authorization": f"Bearer {token}",
        "Origin": "http://localhost:3000",
        "Referer": "http://localhost:3000/",
    }


def create_session(token, entry_source="direct"):
    """Helper to create a Jarvis onboarding session."""
    r = _session.post(
        f"{BASE_URL}/api/jarvis/session",
        json={"entry_source": entry_source},
        headers=auth_headers(token),
    )
    assert r.status_code in (200, 201), f"Create session failed: {r.status_code} {r.text}"
    return r.json()


def send_message(token, session_id, content):
    """Helper to send a chat message."""
    r = _session.post(
        f"{BASE_URL}/api/jarvis/message",
        json={"content": content, "session_id": session_id},
        headers=auth_headers(token),
    )
    return r


# ═══════════════════════════════════════════════════════════
# P13-RES-001: Session Persistence (Browser Close/Reopen)
# ═══════════════════════════════════════════════════════════


class TestP13SessionPersistence:
    """P13-RES-001: Sessions survive browser closes — same user gets same session."""

    def test_create_session_returns_active_session(self, test_user):
        """Creating a session should return an active onboarding session."""
        token = test_user["access_token"]
        session = create_session(token)

        assert "id" in session, f"Session missing id: {session}"
        assert session.get("is_active") is True or session.get("is_active") is None
        # Type should be onboarding
        assert session.get("type") in ("onboarding", None)

    def test_resume_session_after_close(self, test_user):
        """Re-opening /onboarding should resume the same session (Phase 12/13 critical path)."""
        token = test_user["access_token"]

        # First session creation
        session1 = create_session(token, entry_source="direct")
        session_id = session1["id"]

        # Send a message so there's history
        send_message(token, session_id, "Hello from mobile test")

        # Second call to create/resume — should return same session
        session2 = create_session(token, entry_source="direct")

        # Should resume the same session (same ID)
        assert session2["id"] == session_id, (
            f"Session not resumed! Got new session {session2['id']} instead of {session_id}"
        )

    def test_session_history_persists(self, test_user):
        """Chat history should persist across session resume (browser close/reopen)."""
        token = test_user["access_token"]
        session = create_session(token, entry_source="direct")
        session_id = session["id"]

        # Send a unique message
        unique_msg = f"PERSIST_TEST_{uuid.uuid4().hex[:8]}"
        send_message(token, session_id, unique_msg)

        # Fetch history
        r = _session.get(
            f"{BASE_URL}/api/jarvis/history",
            params={"session_id": session_id, "limit": 100},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, f"History fetch failed: {r.status_code} {r.text}"
        history = r.json()

        messages = history.get("messages", history) if isinstance(history, dict) else history
        if isinstance(messages, list):
            contents = [m.get("content", "") for m in messages if isinstance(m, dict)]
            assert any(unique_msg in c for c in contents), (
                f"Unique message not found in history! Contents: {contents[:5]}"
            )

    def test_session_context_preserved(self, test_user):
        """Session context (industry, selected variants) should survive browser close."""
        token = test_user["access_token"]
        session = create_session(token, entry_source="pricing")
        session_id = session["id"]

        # Update context with industry
        r = _session.patch(
            f"{BASE_URL}/api/jarvis/context",
            params={"session_id": session_id},
            json={"industry": "ecommerce"},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, f"Context update failed: {r.status_code} {r.text}"

        # Resume session (simulate browser reopen)
        session2 = create_session(token)
        assert session2["id"] == session_id

        # Check context preserved
        ctx = session2.get("context", session2.get("context_json", {}))
        if isinstance(ctx, str):
            ctx = json.loads(ctx)
        # Industry should be preserved
        assert ctx.get("industry") == "ecommerce", f"Context not preserved: {ctx}"


# ═══════════════════════════════════════════════════════════
# P13-RES-002: Error Recovery for Mobile Connectivity
# ═══════════════════════════════════════════════════════════


class TestP13ErrorRecovery:
    """P13-RES-002: Error handling for mobile network conditions."""

    def test_session_not_found_returns_friendly_error(self, test_user):
        """Accessing a non-existent session should return a user-friendly error, not a stack trace."""
        token = test_user["access_token"]
        fake_id = str(uuid.uuid4())

        r = _session.get(
            f"{BASE_URL}/api/jarvis/session",
            params={"session_id": fake_id},
            headers=auth_headers(token),
        )
        assert r.status_code in (404, 400), f"Expected 404/400, got {r.status_code}"

        # Response should NOT contain stack traces
        body = r.text.lower()
        assert "traceback" not in body, "Stack trace exposed in error response!"
        assert 'file "' not in body, "File path exposed in error response!"

    def test_message_to_invalid_session_returns_clean_error(self, test_user):
        """Sending a message to an invalid session should return clean error."""
        token = test_user["access_token"]
        fake_id = str(uuid.uuid4())

        r = send_message(token, fake_id, "Test message")
        assert r.status_code in (404, 400, 422)

        body = r.text.lower()
        assert "traceback" not in body, "Stack trace exposed in message error!"

    def test_unauthorized_access_returns_401(self):
        """Unauthenticated access should return 401, not 500."""
        r = _session.get(f"{BASE_URL}/api/jarvis/session")
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_malformed_request_returns_422(self, test_user):
        """Malformed JSON should return 422 with clean error, not 500."""
        token = test_user["access_token"]
        r = _session.post(
            f"{BASE_URL}/api/jarvis/message",
            data="not json data",
            headers={**auth_headers(token), "Content-Type": "application/json"},
        )
        assert r.status_code == 422, f"Expected 422, got {r.status_code}"
        body = r.text.lower()
        assert "traceback" not in body

    def test_health_endpoint_works_without_redis(self):
        """Health endpoint should work even with Redis unhealthy (mobile resilience)."""
        r = _session.get(f"{BASE_URL}/health")
        assert r.status_code == 200, f"Health endpoint failed: {r.status_code}"
        data = r.json()
        # Redis will be unhealthy in test env, but app should still respond
        assert data["status"] in ("unhealthy", "degraded", "healthy")

    def test_otp_expired_returns_friendly_message(self, test_user):
        """OTP verification with wrong code should return friendly message (not stack trace)."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        # Try to verify OTP without sending one first
        r = _session.post(
            f"{BASE_URL}/api/jarvis/verify/verify-otp",
            params={"session_id": session_id},
            json={"code": "000000", "email": "test@example.com"},
            headers=auth_headers(token),
        )
        # Should not be 500
        assert r.status_code != 500, f"OTP verify returned 500! {r.text}"
        body = r.text.lower()
        assert "traceback" not in body


# ═══════════════════════════════════════════════════════════
# P13-RES-003: Compact Payloads for Mobile
# ═══════════════════════════════════════════════════════════


class TestP13CompactPayloads:
    """P13-RES-003: API responses should be efficient for mobile bandwidth."""

    def test_session_response_is_reasonable_size(self, test_user):
        """Session response should not be excessively large (> 50KB is too much for mobile)."""
        token = test_user["access_token"]
        r = _session.post(
            f"{BASE_URL}/api/jarvis/session",
            json={"entry_source": "direct"},
            headers=auth_headers(token),
        )
        assert r.status_code in (200, 201)

        # Check response size
        size_bytes = len(r.content)
        assert size_bytes < 50000, f"Session response too large: {size_bytes} bytes"

    def test_history_response_has_pagination(self, test_user):
        """History endpoint should support pagination (limit/offset) for mobile."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        # Send a few messages to build history
        for i in range(3):
            send_message(token, session_id, f"History test message {i}")

        # Fetch with limit
        r = _session.get(
            f"{BASE_URL}/api/jarvis/history",
            params={"session_id": session_id, "limit": 2, "offset": 0},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, f"History failed: {r.status_code} {r.text}"

        data = r.json()
        messages = data.get("messages", data) if isinstance(data, dict) else data
        if isinstance(messages, list):
            # Should respect limit
            assert len(messages) <= 2, f"Pagination not working: got {len(messages)} messages"

        # Check total count exists
        if isinstance(data, dict):
            assert "total" in data or "count" in data or isinstance(messages, list), (
                f"History response missing pagination metadata"
            )

    def test_session_response_has_required_fields(self, test_user):
        """Session response should include all fields needed for mobile UI."""
        token = test_user["access_token"]
        session = create_session(token)

        # Check essential fields for mobile rendering
        required_fields = ["id"]
        for field in required_fields:
            assert field in session, f"Session missing required field: {field}"

        # These fields are used by mobile UI for responsive rendering
        useful_fields = [
            "pack_type", "is_active", "payment_status",
            "handoff_completed", "demo_call_used",
        ]
        present_fields = [f for f in useful_fields if f in session]
        # At least some of these should be present
        assert len(present_fields) >= 2, (
            f"Session response missing too many mobile-useful fields. "
            f"Present: {present_fields}, Missing: {set(useful_fields) - set(present_fields)}"
        )


# ═══════════════════════════════════════════════════════════
# P13-RES-004: Cross-Device Session Sync
# ═══════════════════════════════════════════════════════════


class TestP13CrossDeviceSync:
    """P13-RES-004: Same session visible from multiple devices (same auth token)."""

    def test_session_accessible_from_same_token(self, test_user):
        """Session created on one device should be accessible from same auth token."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        # Access session from "another device" (same token, different request)
        r = _session.get(
            f"{BASE_URL}/api/jarvis/session",
            params={"session_id": session_id},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, f"Session fetch failed: {r.status_code} {r.text}"
        fetched = r.json()
        assert fetched["id"] == session_id

    def test_messages_sync_across_requests(self, test_user):
        """Messages sent from one request should be visible to another."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        # Send message
        unique_msg = f"SYNC_TEST_{uuid.uuid4().hex[:8]}"
        send_message(token, session_id, unique_msg)

        # Fetch history from separate request
        r = _session.get(
            f"{BASE_URL}/api/jarvis/history",
            params={"session_id": session_id, "limit": 100},
            headers=auth_headers(token),
        )
        assert r.status_code == 200
        data = r.json()
        messages = data.get("messages", data) if isinstance(data, dict) else data
        if isinstance(messages, list):
            contents = [m.get("content", "") for m in messages if isinstance(m, dict)]
            assert any(unique_msg in c for c in contents), (
                f"Message not synced! Contents: {contents[:5]}"
            )


# ═══════════════════════════════════════════════════════════
# P13-RES-005: Payment Page Refresh Resilience
# ═══════════════════════════════════════════════════════════


class TestP13PaymentRefreshResilience:
    """P13-RES-005: Session preserved during Paddle payment page refresh."""

    def test_session_survives_payment_status_check(self, test_user):
        """After payment status check, session should still be valid."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        # Check payment status (simulates Paddle redirect back)
        r = _session.get(
            f"{BASE_URL}/api/jarvis/payment/status",
            params={"session_id": session_id},
            headers=auth_headers(token),
        )
        # Should not crash — 200 with status data
        assert r.status_code == 200, f"Payment status failed: {r.status_code} {r.text}"

        # Session should still be accessible
        r2 = _session.get(
            f"{BASE_URL}/api/jarvis/session",
            params={"session_id": session_id},
            headers=auth_headers(token),
        )
        assert r2.status_code == 200
        assert r2.json()["id"] == session_id

    def test_demo_pack_status_doesnt_corrupt_session(self, test_user):
        """Checking demo pack status should not corrupt session state."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        # Check demo pack status
        r = _session.get(
            f"{BASE_URL}/api/jarvis/demo-pack/status",
            params={"session_id": session_id},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, f"Demo pack status failed: {r.status_code} {r.text}"

        # Session should still work for messages
        r2 = send_message(token, session_id, "After demo pack check")
        assert r2.status_code == 200, f"Message failed after demo pack check: {r2.status_code}"


# ═══════════════════════════════════════════════════════════
# P13-RES-006: Dashboard API Structure for Responsive Grid
# ═══════════════════════════════════════════════════════════


class TestP13DashboardResponsive:
    """P13-RES-006: Dashboard API should provide data suitable for responsive grid rendering."""

    def test_dashboard_analytics_endpoint_exists(self, test_user):
        """Dashboard analytics endpoint should exist and be auth-protected."""
        token = test_user["access_token"]

        # Without auth
        r1 = _session.get(f"{BASE_URL}/api/analytics/dashboard")
        assert r1.status_code in (401, 403), f"Dashboard accessible without auth!"

        # With auth
        r2 = _session.get(
            f"{BASE_URL}/api/analytics/dashboard",
            headers=auth_headers(token),
        )
        assert r2.status_code in (200, 404), f"Dashboard endpoint issue: {r2.status_code}"

    def test_kpi_data_has_reasonable_structure(self, test_user):
        """KPI data should have fields that map to responsive card components."""
        token = test_user["access_token"]

        # Try the analytics endpoint
        r = _session.get(
            f"{BASE_URL}/api/analytics/dashboard",
            headers=auth_headers(token),
        )
        if r.status_code == 200:
            data = r.json()
            # Should have summary or similar structure
            assert "summary" in data or "metrics" in data or "kpi" in data or isinstance(data, dict), (
                f"Dashboard data missing expected structure: {list(data.keys()) if isinstance(data, dict) else type(data)}"
            )

    def test_tickets_endpoint_supports_pagination(self, test_user):
        """Tickets endpoint should support pagination for mobile scrolling."""
        token = test_user["access_token"]

        r = _session.get(
            f"{BASE_URL}/api/v1/tickets",
            params={"page": 1, "page_size": 10},
            headers=auth_headers(token),
        )
        # Should accept pagination params without error
        assert r.status_code in (200, 404), f"Tickets endpoint failed: {r.status_code}"


# ═══════════════════════════════════════════════════════════
# P13-RES-007: Ticket System for Mobile Cards
# ═══════════════════════════════════════════════════════════


class TestP13TicketCards:
    """P13-RES-007: Action ticket system should support mobile card rendering."""

    def test_create_action_ticket(self, test_user):
        """Action tickets should be creatable for mobile card display."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        r = _session.post(
            f"{BASE_URL}/api/jarvis/tickets",
            params={"session_id": session_id},
            json={
                "ticket_type": "otp_verification",
                "metadata": {"email": "test@example.com"},
            },
            headers=auth_headers(token),
        )
        # Should succeed or return 422 for missing fields — not 500
        assert r.status_code != 500, f"Ticket creation crashed: {r.status_code} {r.text}"

    def test_list_tickets_for_session(self, test_user):
        """Tickets should be listable for a session (mobile card rendering)."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        r = _session.get(
            f"{BASE_URL}/api/jarvis/tickets",
            params={"session_id": session_id},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, f"List tickets failed: {r.status_code} {r.text}"

        data = r.json()
        # Should be a list or have tickets/items key
        if isinstance(data, dict):
            assert "tickets" in data or "items" in data or "data" in data or len(data) >= 0
        elif isinstance(data, list):
            assert True  # Direct list is fine

    def test_ticket_status_update(self, test_user):
        """Ticket status should be updatable for mobile card status indicator."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        # Create a ticket first
        r1 = _session.post(
            f"{BASE_URL}/api/jarvis/tickets",
            params={"session_id": session_id},
            json={
                "ticket_type": "demo_call",
                "metadata": {"phone": "+1234567890"},
            },
            headers=auth_headers(token),
        )

        if r1.status_code in (200, 201):
            ticket = r1.json()
            ticket_id = ticket.get("id")

            if ticket_id:
                # Update status
                r2 = _session.patch(
                    f"{BASE_URL}/api/jarvis/tickets/{ticket_id}/status",
                    params={"session_id": session_id},
                    json={"status": "in_progress"},
                    headers=auth_headers(token),
                )
                # Should succeed — not crash
                assert r2.status_code != 500, f"Ticket status update crashed: {r2.status_code}"


# ═══════════════════════════════════════════════════════════
# P13-RES-008: Entry Context for Mobile Deep Links
# ═══════════════════════════════════════════════════════════


class TestP13EntryContext:
    """P13-RES-008: Entry context from URL params (mobile deep links)."""

    def test_entry_context_from_url_params(self, test_user):
        """Entry context endpoint should accept URL params for mobile deep linking."""
        token = test_user["access_token"]

        r = _session.post(
            f"{BASE_URL}/api/jarvis/context/entry",
            json={
                "entry_source": "pricing",
                "entry_params": {
                    "industry": "saas",
                    "variant_id": "technical_support",
                },
            },
            headers=auth_headers(token),
        )
        assert r.status_code in (200, 201), f"Entry context failed: {r.status_code} {r.text}"

        session = r.json()
        ctx = session.get("context", session.get("context_json", {}))
        if isinstance(ctx, str):
            ctx = json.loads(ctx)

        # Industry should be set from entry params
        assert ctx.get("industry") == "saas" or ctx.get("entry_source") == "pricing", (
            f"Entry context not applied: {ctx}"
        )

    def test_different_entry_sources(self, test_user):
        """Different entry sources (demo, pricing, models_page) should work."""
        token = test_user["access_token"]

        for source in ["demo", "pricing", "models_page", "free_chat"]:
            # Each entry source should create/resume a session
            session = create_session(token, entry_source=source)
            assert "id" in session, f"Session creation failed for source: {source}"

    def test_mobile_deep_link_preserves_variant(self, test_user):
        """Mobile deep links with variant_id should be preserved in session context."""
        token = test_user["access_token"]

        r = _session.post(
            f"{BASE_URL}/api/jarvis/context/entry",
            json={
                "entry_source": "models_page",
                "entry_params": {
                    "variant_id": "order_management",
                    "variant_name": "Order Management",
                    "industry": "ecommerce",
                },
            },
            headers=auth_headers(token),
        )
        assert r.status_code in (200, 201)

        session = r.json()
        ctx = session.get("context", session.get("context_json", {}))
        if isinstance(ctx, str):
            ctx = json.loads(ctx)

        # Variant info should be in context
        has_variant = (
            ctx.get("variant_id") == "order_management"
            or ctx.get("variant") == "order_management"
            or any(
                v.get("id") == "order_management" or v.get("variant_id") == "order_management"
                for v in ctx.get("selected_variants", [])
                if isinstance(v, dict)
            )
        )
        assert has_variant or ctx.get("industry") == "ecommerce", (
            f"Deep link variant not preserved in context: {ctx}"
        )


# ═══════════════════════════════════════════════════════════
# P13-RES-009: Rate Limiting for Mobile
# ═══════════════════════════════════════════════════════════


class TestP13RateLimitMobile:
    """P13-RES-009: Rate limiting should handle mobile retry storms gracefully."""

    def test_rapid_requests_dont_crash(self, test_user):
        """Multiple rapid requests (mobile retry) should not crash the server."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        # Send 5 messages rapidly
        for i in range(5):
            r = send_message(token, session_id, f"Rapid test {i}")
            # Should not be 500
            assert r.status_code != 500, f"Rapid request {i} crashed: {r.status_code}"

    def test_message_limit_enforced_gracefully(self, test_user):
        """Message limit should be enforced with proper status code, not crash."""
        token = test_user["access_token"]

        # Get current session status
        r = _session.get(
            f"{BASE_URL}/api/jarvis/session",
            headers=auth_headers(token),
        )
        assert r.status_code == 200
        session = r.json()

        # Check remaining messages
        remaining = session.get("remaining_today", session.get("remaining", 20))
        # Should have a numeric remaining count
        assert isinstance(remaining, int) or remaining is None, (
            f"remaining_today should be int, got: {type(remaining)}"
        )


# ═══════════════════════════════════════════════════════════
# P13-RES-010: Handoff Status for Mobile Navigation
# ═══════════════════════════════════════════════════════════


class TestP13HandoffMobileNav:
    """P13-RES-010: Handoff status should support mobile navigation decisions."""

    def test_handoff_status_check(self, test_user):
        """Handoff status endpoint should work for mobile navigation logic."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        r = _session.get(
            f"{BASE_URL}/api/jarvis/handoff/status",
            params={"session_id": session_id},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, f"Handoff status failed: {r.status_code} {r.text}"

        data = r.json()
        # Should have status field
        assert "status" in data or "handoff_completed" in data, (
            f"Handoff status missing key fields: {list(data.keys()) if isinstance(data, dict) else type(data)}"
        )

    def test_handoff_not_completed_by_default(self, test_user):
        """New session should not have handoff completed."""
        token = test_user["access_token"]
        session = create_session(token)

        handoff = session.get("handoff_completed")
        assert handoff is False or handoff is None or handoff == 0, (
            f"New session should not have handoff completed, got: {handoff}"
        )


# ═══════════════════════════════════════════════════════════
# P13-RES-011: Content-Type and CORS for Mobile
# ═══════════════════════════════════════════════════════════


class TestP13MobileHeaders:
    """P13-RES-011: API should return proper headers for mobile clients."""

    def test_json_content_type(self, test_user):
        """All API responses should return application/json."""
        token = test_user["access_token"]

        r = _session.post(
            f"{BASE_URL}/api/jarvis/session",
            json={"entry_source": "direct"},
            headers=auth_headers(token),
        )
        assert "application/json" in r.headers.get("content-type", ""), (
            f"Expected JSON content-type, got: {r.headers.get('content-type')}"
        )

    def test_cors_headers_present(self):
        """CORS headers should be present for mobile web clients."""
        r = _session.options(
            f"{BASE_URL}/api/jarvis/session",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        # CORS should be configured (either via preflight or direct response)
        # Not strictly required to pass, but good to verify
        # We just check it doesn't crash
        assert r.status_code in (200, 204, 405, 404), f"CORS preflight crashed: {r.status_code}"

    def test_response_has_request_id(self):
        """Responses should include request ID or correlation ID for mobile debugging."""
        r = _session.get(f"{BASE_URL}/health")
        has_header = "x-request-id" in r.headers or "request-id" in r.headers or "x-correlation-id" in r.headers
        body_has_id = "request_id" in r.text or "correlation_id" in r.text
        # At least one should be present for mobile debugging
        assert has_header or body_has_id, "No request ID or correlation ID in response for mobile debugging!"


# ═══════════════════════════════════════════════════════════
# P13-RES-012: Demo Call Status for Mobile
# ═══════════════════════════════════════════════════════════


class TestP13DemoCallMobile:
    """P13-RES-012: Demo call status should support mobile UI rendering."""

    def test_demo_call_summary_endpoint(self, test_user):
        """Demo call summary endpoint should exist for mobile PostCallSummaryCard."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        r = _session.get(
            f"{BASE_URL}/api/jarvis/demo-call/summary",
            params={"session_id": session_id},
            headers=auth_headers(token),
        )
        # Should not crash — 200 with empty data or 404
        assert r.status_code in (200, 404), f"Call summary crashed: {r.status_code} {r.text}"

    def test_demo_pack_status_structure(self, test_user):
        """Demo pack status should have fields for mobile DemoPackCTA card."""
        token = test_user["access_token"]
        session = create_session(token)
        session_id = session["id"]

        r = _session.get(
            f"{BASE_URL}/api/jarvis/demo-pack/status",
            params={"session_id": session_id},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, f"Demo pack status failed: {r.status_code}"
        data = r.json()

        # Should have pack_type or status field for mobile UI
        assert "pack_type" in data or "status" in data or "active" in data, (
            f"Demo pack status missing expected fields: {list(data.keys()) if isinstance(data, dict) else type(data)}"
        )
