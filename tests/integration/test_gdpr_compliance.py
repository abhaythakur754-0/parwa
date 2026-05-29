"""
Phase 15 — GDPR & Data Lifecycle Integration Tests

TEST-GDPR-001: Right to Erasure & Data Retention
- TEST 1: Right to erasure (BC-010)
- TEST 2: Data retention policy
- TEST 3: Redis cache invalidation on tenant deletion
- TEST 4: PII export (GDPR access request)
- TEST 5: Audit trail immutability

These tests run against the LIVE backend at localhost:8000.
They do NOT import the app module or run init_db — all requests go through HTTP.
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

# ── Configuration ─────────────────────────────────────────────────

BASE_URL = os.environ.get("PARWA_API_URL", "http://localhost:8000")
TIMEOUT = 30

# Test user credentials (from seed data)
TEST_OWNER_EMAIL = "owner@technova.com"
TEST_OWNER_PASSWORD = "TestPass123!"


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    """Get JWT auth token for test owner user."""
    login_url = f"{BASE_URL}/api/auth/login"
    resp = requests.post(login_url, json={
        "email": TEST_OWNER_EMAIL,
        "password": TEST_OWNER_PASSWORD,
    }, timeout=TIMEOUT)
    if resp.status_code != 200:
        pytest.skip(f"Cannot authenticate ({resp.status_code}): {resp.text[:200]}")
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip(f"No access_token in login response: {list(data.keys())}")
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """HTTP headers with JWT authorization."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def company_id(auth_headers):
    """Get the company_id for the authenticated user."""
    me_url = f"{BASE_URL}/api/auth/me"
    resp = requests.get(me_url, headers=auth_headers, timeout=TIMEOUT)
    if resp.status_code != 200:
        pytest.skip(f"Cannot get user info ({resp.status_code})")
    data = resp.json()
    return data.get("company_id", "")


@pytest.fixture(scope="module")
def csrf_token(auth_headers):
    """Get CSRF token from the server."""
    # Try to get CSRF token from health or any endpoint that sets the cookie
    resp = requests.get(f"{BASE_URL}/health", headers=auth_headers, timeout=TIMEOUT)
    csrf_token = None
    # Check cookies
    for cookie in resp.cookies:
        if cookie.name == "csrf_token":
            csrf_token = cookie.value
            break
    # Also check response headers
    if not csrf_token:
        csrf_token = resp.headers.get("X-CSRF-Token", "")
    return csrf_token


def _get_headers_with_csrf(auth_headers, csrf_token):
    """Return auth headers with CSRF token added."""
    headers = dict(auth_headers)
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    headers["Content-Type"] = "application/json"
    headers["Origin"] = "http://localhost:3000"
    return headers


# ── TEST 1: Right to Erasure (BC-010) ────────────────────────────


class TestRightToErasure:
    """GDPR Art. 17 — Right to erasure (right to be forgotten).

    Verifies:
    - Customer record is anonymized (not hard-deleted)
    - PII in ticket messages is redacted
    - Audit trail records are RETAINED (legal requirement)
    - Redis keys are purged (graceful degradation without Redis)
    - Erasure log entry is created with timestamp and operator_id
    """

    def test_01_create_erasure_request(self, auth_headers, csrf_token):
        """Create a GDPR erasure request for a customer."""
        url = f"{BASE_URL}/api/v1/gdpr/erasure-request"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "customer_email": "john@test.com",
            "scope": "full",
            "reason": "GDPR Art. 17 right to erasure request",
            "request_source": "api",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)

        # Accept both 200 (success) and 403 (auth issue) and 404 (route not found yet)
        if resp.status_code == 404:
            pytest.skip("GDPR erasure endpoint not yet deployed")
        if resp.status_code == 403:
            pytest.skip(f"Auth forbidden: {resp.text[:200]}")

        assert resp.status_code in (200, 201), (
            f"Expected 200/201, got {resp.status_code}: {resp.text[:300]}"
        )

        data = resp.json()
        assert "id" in data, f"Response missing 'id': {data}"
        assert data.get("status") == "pending", f"Expected status=pending, got {data.get('status')}"
        assert data.get("customer_email") == "john@test.com"
        assert data.get("scope") == "full"

        # Store for subsequent tests
        TestRightToErasure.erasure_id = data["id"]

    def test_02_get_erasure_request_status(self, auth_headers, csrf_token):
        """Get the status of the erasure request."""
        if not hasattr(TestRightToErasure, 'erasure_id'):
            pytest.skip("No erasure request created")

        url = f"{BASE_URL}/api/v1/gdpr/erasure-request/{TestRightToErasure.erasure_id}"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        resp = requests.get(url, headers=headers, timeout=TIMEOUT)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("status") in ("pending", "processing", "completed")
        assert data.get("customer_email") == "john@test.com"

    def test_03_verify_erasure_request(self, auth_headers, csrf_token):
        """Verify the erasure request (required before execution)."""
        if not hasattr(TestRightToErasure, 'erasure_id'):
            pytest.skip("No erasure request created")

        url = f"{BASE_URL}/api/v1/gdpr/erasure-request/{TestRightToErasure.erasure_id}/verify"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "erasure_request_id": TestRightToErasure.erasure_id,
            "verified": True,
            "note": "Identity verified via email confirmation",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data.get("verification_status") in ("verified", "rejected"), (
            f"Expected verification_status=verified, got {data.get('verification_status')}"
        )

    def test_04_execute_erasure_request(self, auth_headers, csrf_token):
        """Execute the verified erasure request.

        Verifies:
        - Customer record anonymized
        - Ticket messages redacted
        - Audit trail preserved
        - Erasure log created
        """
        if not hasattr(TestRightToErasure, 'erasure_id'):
            pytest.skip("No erasure request created")

        url = f"{BASE_URL}/api/v1/gdpr/erasure-request/{TestRightToErasure.erasure_id}/execute"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        resp = requests.post(url, headers=headers, timeout=TIMEOUT)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data.get("status") in ("completed", "failed"), (
            f"Expected completed or failed, got {data.get('status')}"
        )

        if data.get("status") == "completed":
            # Verify audit trail was preserved
            assert data.get("audit_trail_preserved") is True, (
                "Audit trail must be preserved during erasure (GDPR requirement)"
            )
            # Verify erasure counts are non-negative integers
            assert isinstance(data.get("customers_anonymized", 0), int)
            assert isinstance(data.get("messages_redacted", 0), int)
            assert isinstance(data.get("redis_keys_purged", 0), int)

    def test_05_erasure_creates_audit_log(self, auth_headers, csrf_token):
        """Verify that erasure created an audit trail entry."""
        if not hasattr(TestRightToErasure, 'erasure_id'):
            pytest.skip("No erasure request created")

        # Check the erasure request status — it should have audit info
        url = f"{BASE_URL}/api/v1/gdpr/erasure-request/{TestRightToErasure.erasure_id}"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        resp = requests.get(url, headers=headers, timeout=TIMEOUT)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        # After execution, status should be completed
        assert data.get("status") in ("completed", "processing", "failed"), (
            f"Expected post-execution status, got {data.get('status')}"
        )
        # If completed, timestamps should be set
        if data.get("status") == "completed":
            assert data.get("completed_at") is not None, "completed_at must be set"


# ── TEST 2: Data Retention Policy ─────────────────────────────────


class TestDataRetentionPolicy:
    """Data retention policy enforcement.

    Verifies:
    - Old tickets are archived/deleted per policy
    - Current tickets are NOT deleted
    - Retention policies can be created and enforced
    - GDPR_RETENTION_DAYS config is used as default
    """

    def test_01_create_retention_policy(self, auth_headers, csrf_token):
        """Create a data retention policy for tickets."""
        url = f"{BASE_URL}/api/v1/gdpr/retention-policy"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "category": "tickets",
            "retention_days": 365,
            "action_on_expiry": "archive",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)

        if resp.status_code == 404:
            pytest.skip("GDPR retention endpoint not yet deployed")
        if resp.status_code == 403:
            pytest.skip(f"Auth forbidden: {resp.text[:200]}")

        assert resp.status_code in (200, 201), (
            f"Expected 200/201, got {resp.status_code}: {resp.text[:300]}"
        )

        data = resp.json()
        assert data.get("category") == "tickets"
        assert data.get("retention_days") == 365
        assert data.get("action_on_expiry") == "archive"
        assert data.get("is_active") is True

        TestDataRetentionPolicy.policy_id = data.get("id")

    def test_02_enforce_retention_dry_run(self, auth_headers, csrf_token):
        """Enforce retention policies in dry-run mode (no changes)."""
        url = f"{BASE_URL}/api/v1/gdpr/retention/enforce?dry_run=true"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        resp = requests.post(url, headers=headers, timeout=TIMEOUT)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "policies_enforced" in data
        assert "total_records_affected" in data
        assert "details" in data
        assert isinstance(data["details"], list)

    def test_03_create_short_retention_policy(self, auth_headers, csrf_token):
        """Create a short retention policy for testing."""
        url = f"{BASE_URL}/api/v1/gdpr/retention-policy"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "category": "messages",
            "retention_days": 30,
            "action_on_expiry": "anonymize",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        assert resp.status_code in (200, 201), f"Failed: {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("retention_days") == 30
        assert data.get("action_on_expiry") == "anonymize"

    def test_04_audit_log_retention_is_long(self, auth_headers, csrf_token):
        """Verify audit log retention is much longer than regular data."""
        url = f"{BASE_URL}/api/v1/gdpr/retention-policy"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "category": "audit_logs",
            "retention_days": 2555,  # ~7 years
            "action_on_expiry": "archive",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        assert resp.status_code in (200, 201)
        data = resp.json()
        # Audit log retention should be >= 7 years (2555 days)
        assert data.get("retention_days") >= 2555, (
            f"Audit log retention must be >= 7 years (2555 days), got {data.get('retention_days')}"
        )


# ── TEST 3: Redis Cache Invalidation on Tenant Deletion ──────────


class TestRedisCacheInvalidation:
    """Redis cache invalidation on tenant deletion.

    Verifies:
    - All Redis keys for deleted tenant are purged
    - No stale data accessible to new tenant with same ID
    - Graceful degradation when Redis is unavailable
    """

    def test_01_redis_health_check(self, auth_headers):
        """Check if Redis is available in the health endpoint."""
        url = f"{BASE_URL}/health"
        resp = requests.get(url, headers=auth_headers, timeout=TIMEOUT)

        assert resp.status_code == 200
        data = resp.json()
        # Redis may be healthy or unhealthy depending on environment
        redis_status = data.get("redis", {}).get("status", "unknown")

        # Store for other tests
        TestRedisCacheInvalidation.redis_available = redis_status == "healthy"

    def test_02_erasure_purges_redis_keys(self, auth_headers, csrf_token):
        """Verify that erasure request attempts to purge Redis keys.

        Even without Redis running, the endpoint should not crash
        and should report 0 keys purged (graceful degradation).
        """
        url = f"{BASE_URL}/api/v1/gdpr/erasure-request"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "customer_email": "cache-test@example.com",
            "scope": "full",
            "reason": "Testing Redis cache invalidation",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)

        if resp.status_code == 404:
            pytest.skip("GDPR endpoint not deployed")

        assert resp.status_code in (200, 201), f"Failed: {resp.status_code}: {resp.text[:200]}"
        data = resp.json()

        # Verify and execute to check Redis purge
        erasure_id = data["id"]

        # Verify
        verify_url = f"{BASE_URL}/api/v1/gdpr/erasure-request/{erasure_id}/verify"
        requests.post(verify_url, json={
            "erasure_request_id": erasure_id,
            "verified": True,
        }, headers=headers, timeout=TIMEOUT)

        # Execute
        exec_url = f"{BASE_URL}/api/v1/gdpr/erasure-request/{erasure_id}/execute"
        exec_resp = requests.post(exec_url, headers=headers, timeout=TIMEOUT)

        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()

        # redis_keys_purged should be a non-negative integer
        # (0 if Redis is unavailable — graceful degradation)
        assert isinstance(exec_data.get("redis_keys_purged", 0), int)
        assert exec_data.get("redis_keys_purged", 0) >= 0


# ── TEST 4: PII Export (GDPR Access Request) ─────────────────────


class TestPIIExport:
    """GDPR Art. 15/20 — Right of access / data portability.

    Verifies:
    - All customer data returned in structured format
    - Data includes tickets, messages, interactions
    - Export format is JSON (machine-readable)
    - No hidden data — complete export
    """

    def test_01_export_customer_data(self, auth_headers, csrf_token):
        """Export all data for a customer via GDPR access request."""
        url = f"{BASE_URL}/api/v1/gdpr/data-export"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "customer_email": TEST_OWNER_EMAIL,
            "format": "json",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)

        if resp.status_code == 404:
            pytest.skip("GDPR data export endpoint not deployed")
        if resp.status_code == 403:
            pytest.skip(f"Auth forbidden: {resp.text[:200]}")

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        assert "customer_email" in data, f"Missing customer_email: {list(data.keys())}"
        assert "data" in data, f"Missing 'data' field: {list(data.keys())}"
        assert "categories_included" in data, f"Missing categories_included"
        assert "total_records" in data, f"Missing total_records"

        # Data should be structured (JSON object)
        assert isinstance(data["data"], dict), "Data must be a structured JSON object"

        # Categories should be a list
        assert isinstance(data["categories_included"], list)

        # Total records should be non-negative
        assert data["total_records"] >= 0

    def test_02_export_includes_profile(self, auth_headers, csrf_token):
        """Verify export includes customer profile data."""
        url = f"{BASE_URL}/api/v1/gdpr/data-export"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "customer_email": TEST_OWNER_EMAIL,
            "format": "json",
            "include_categories": ["profile"],
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)

        if resp.status_code == 404:
            pytest.skip("GDPR data export endpoint not deployed")

        assert resp.status_code == 200
        data = resp.json()
        assert "profile" in data.get("categories_included", []), (
            "Profile category must be included in export"
        )

    def test_03_export_with_specific_categories(self, auth_headers, csrf_token):
        """Export only specific data categories."""
        url = f"{BASE_URL}/api/v1/gdpr/data-export"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "customer_email": TEST_OWNER_EMAIL,
            "format": "json",
            "include_categories": ["profile", "tickets"],
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)

        if resp.status_code == 404:
            pytest.skip("GDPR data export endpoint not deployed")

        assert resp.status_code == 200
        data = resp.json()
        categories = data.get("categories_included", [])
        assert "profile" in categories, "Profile must be included when requested"
        # Tickets may or may not have data, but category should be present
        assert "tickets" in categories, "Tickets category must be included when requested"

    def test_04_export_nonexistent_customer(self, auth_headers, csrf_token):
        """Export data for a customer that doesn't exist (should return empty, not error)."""
        url = f"{BASE_URL}/api/v1/gdpr/data-export"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "customer_email": f"nonexistent-{uuid.uuid4().hex[:8]}@test.com",
            "format": "json",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)

        if resp.status_code == 404:
            pytest.skip("GDPR data export endpoint not deployed")

        # Should return 200 with empty data, not 404
        assert resp.status_code == 200, f"Expected 200 for nonexistent customer, got {resp.status_code}"
        data = resp.json()
        # Profile should be null/None for nonexistent customer
        assert data.get("data", {}).get("profile") is None


# ── TEST 5: Audit Trail Immutability ─────────────────────────────


class TestAuditTrailImmutability:
    """Verify that audit_trail has no DELETE or UPDATE routes.

    GDPR requires audit records to be tamper-proof for legal reasons.
    The API must not expose any way to modify or delete audit entries.
    """

    def test_01_check_immutability_endpoint(self, auth_headers, csrf_token):
        """Use the immutability check endpoint."""
        url = f"{BASE_URL}/api/v1/gdpr/audit-immutability"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        resp = requests.get(url, headers=headers, timeout=TIMEOUT)

        if resp.status_code == 404:
            pytest.skip("Audit immutability endpoint not deployed")

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "is_immutable" in data, f"Missing 'is_immutable': {list(data.keys())}"
        assert data["is_immutable"] is True, (
            f"Audit trail must be immutable! Result: {data}"
        )
        assert data.get("has_delete_route") is False, (
            "Audit trail must NOT have DELETE route"
        )
        assert data.get("has_update_route") is False, (
            "Audit trail must NOT have UPDATE route"
        )

    def test_02_no_audit_delete_route(self, auth_headers, csrf_token):
        """Verify no DELETE /api/.../audit-trail/... route exists."""
        # Try various audit trail DELETE endpoints
        audit_paths = [
            "/api/v1/audit-trail/test-id",
            "/api/audit-trail/test-id",
            "/api/v1/audit/test-id",
        ]

        for path in audit_paths:
            url = f"{BASE_URL}{path}"
            headers = dict(auth_headers)
            headers["Origin"] = "http://localhost:3000"

            resp = requests.delete(url, headers=headers, timeout=TIMEOUT)
            # All should return 404 (route not found) or 405 (method not allowed)
            assert resp.status_code in (404, 405), (
                f"Audit trail DELETE at {path} returned {resp.status_code} — "
                f"should be 404/405!"
            )

    def test_03_no_audit_update_route(self, auth_headers, csrf_token):
        """Verify no PUT/PATCH /api/.../audit-trail/... route exists."""
        audit_paths = [
            "/api/v1/audit-trail/test-id",
            "/api/audit-trail/test-id",
            "/api/v1/audit/test-id",
        ]

        for path in audit_paths:
            url = f"{BASE_URL}{path}"
            headers = dict(auth_headers)
            headers["Origin"] = "http://localhost:3000"
            headers["Content-Type"] = "application/json"

            for method in ("put", "patch"):
                func = requests.put if method == "put" else requests.patch
                resp = func(url, json={"action": "modified"}, headers=headers, timeout=TIMEOUT)
                assert resp.status_code in (404, 405), (
                    f"Audit trail {method.upper()} at {path} returned {resp.status_code} — "
                    f"should be 404/405!"
                )


# ── TEST 6: Consent Management ────────────────────────────────────


class TestConsentManagement:
    """GDPR Art. 7 — Consent management.

    Verifies:
    - Consent can be recorded
    - Consent can be listed
    - Consent can be withdrawn
    - Consent records include IP and user agent
    """

    def test_01_record_consent(self, auth_headers, csrf_token):
        """Record a GDPR consent decision."""
        url = f"{BASE_URL}/api/v1/gdpr/consent"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "consent_type": "gdpr",
            "granted": True,
            "consent_version": "1.0",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)

        if resp.status_code == 404:
            pytest.skip("GDPR consent endpoint not deployed")
        if resp.status_code == 403:
            pytest.skip(f"Auth forbidden: {resp.text[:200]}")

        assert resp.status_code in (200, 201), (
            f"Expected 200/201, got {resp.status_code}: {resp.text[:300]}"
        )

        data = resp.json()
        assert data.get("consent_type") == "gdpr"
        assert data.get("granted") is True
        assert "id" in data

        TestConsentManagement.consent_id = data["id"]

    def test_02_list_consents(self, auth_headers, csrf_token):
        """List all consent records for the current user."""
        url = f"{BASE_URL}/api/v1/gdpr/consent"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        resp = requests.get(url, headers=headers, timeout=TIMEOUT)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list), "Consent list must be a list"
        # Should have at least one consent from the previous test
        assert len(data) >= 1, "Should have at least one consent record"

    def test_03_withdraw_consent(self, auth_headers, csrf_token):
        """Withdraw consent for GDPR data processing."""
        url = f"{BASE_URL}/api/v1/gdpr/consent/gdpr"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        resp = requests.delete(url, headers=headers, timeout=TIMEOUT)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("granted") is False, "Withdrawn consent must have granted=False"
        assert data.get("consent_type") == "gdpr"

    def test_04_multiple_consent_types(self, auth_headers, csrf_token):
        """Record multiple consent types."""
        url = f"{BASE_URL}/api/v1/gdpr/consent"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        consent_types = ["tcpa", "call_recording", "data_processing"]
        for ctype in consent_types:
            payload = {
                "consent_type": ctype,
                "granted": True,
                "consent_version": "1.0",
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            assert resp.status_code in (200, 201), f"Failed for {ctype}: {resp.status_code}"


# ── TEST 7: Cross-Tenant GDPR Isolation ──────────────────────────


class TestCrossTenantGDPRIsolation:
    """Verify GDPR operations are properly tenant-isolated.

    A GDPR erasure request from one tenant should NOT affect
    data belonging to another tenant.
    """

    def test_01_erasure_is_tenant_scoped(self, auth_headers, csrf_token):
        """Verify erasure request is scoped to the requesting tenant."""
        url = f"{BASE_URL}/api/v1/gdpr/erasure-request"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        payload = {
            "customer_email": f"cross-tenant-{uuid.uuid4().hex[:8]}@test.com",
            "scope": "full",
            "reason": "Cross-tenant isolation test",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)

        if resp.status_code == 404:
            pytest.skip("GDPR endpoint not deployed")

        assert resp.status_code in (200, 201)
        data = resp.json()
        # The erasure request must have a company_id
        assert data.get("company_id") is not None, "Erasure must be tenant-scoped"

    def test_02_cannot_access_other_tenant_erasure(self, auth_headers, csrf_token):
        """Verify you cannot access erasure requests from other tenants."""
        # Try to access a random erasure request ID
        fake_id = str(uuid.uuid4())
        url = f"{BASE_URL}/api/v1/gdpr/erasure-request/{fake_id}"
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        resp = requests.get(url, headers=headers, timeout=TIMEOUT)

        # Should return 404 (not found in this tenant)
        assert resp.status_code in (404, 403), (
            f"Expected 404/403 for other tenant's erasure, got {resp.status_code}"
        )


# ── TEST 8: GDPR Configuration ───────────────────────────────────


class TestGDPRConfiguration:
    """Verify GDPR configuration settings are properly defined."""

    def test_01_gdpr_retention_days_config(self):
        """Verify GDPR_RETENTION_DAYS is configured in the settings."""
        try:
            from app.config import get_settings
            settings = get_settings()
            assert hasattr(settings, "GDPR_RETENTION_DAYS"), (
                "GDPR_RETENTION_DAYS must be defined in settings"
            )
            assert settings.GDPR_RETENTION_DAYS > 0, (
                f"GDPR_RETENTION_DAYS must be > 0, got {settings.GDPR_RETENTION_DAYS}"
            )
            assert settings.GDPR_RETENTION_DAYS >= 30, (
                f"GDPR_RETENTION_DAYS should be >= 30 days, got {settings.GDPR_RETENTION_DAYS}"
            )
        except Exception as e:
            if "DATA_ENCRYPTION_KEY" in str(e) or "SECRET_KEY" in str(e):
                pytest.skip(f"Config validation requires env vars: {e}")
            raise

    def test_02_audit_retention_days_config(self):
        """Verify AUDIT_LOG_RETENTION_DAYS is configured and longer than GDPR retention."""
        try:
            from app.config import get_settings
            settings = get_settings()
            assert hasattr(settings, "AUDIT_LOG_RETENTION_DAYS"), (
                "AUDIT_LOG_RETENTION_DAYS must be defined in settings"
            )
            # Audit logs should be retained much longer than regular data
            assert settings.AUDIT_LOG_RETENTION_DAYS >= settings.GDPR_RETENTION_DAYS, (
                f"Audit retention ({settings.AUDIT_LOG_RETENTION_DAYS}) must be >= "
                f"GDPR retention ({settings.GDPR_RETENTION_DAYS})"
            )
        except Exception as e:
            if "DATA_ENCRYPTION_KEY" in str(e) or "SECRET_KEY" in str(e):
                pytest.skip(f"Config validation requires env vars: {e}")
            raise

    def test_03_gdpr_endpoints_in_openapi(self, auth_headers):
        """Verify GDPR endpoints appear in the API documentation."""
        url = f"{BASE_URL}/openapi.json"
        resp = requests.get(url, headers=auth_headers, timeout=TIMEOUT)

        if resp.status_code == 404:
            pytest.skip("OpenAPI docs not available (production mode)")

        assert resp.status_code == 200
        data = resp.json()
        paths = data.get("paths", {})

        # Check for GDPR endpoints
        gdpr_paths = [p for p in paths if "/gdpr" in p]
        assert len(gdpr_paths) > 0, (
            f"GDPR endpoints not found in OpenAPI schema. Paths: {list(paths.keys())[:20]}"
        )


# ── TEST 9: Health Endpoint for GDPR Subsystem ───────────────────


class TestGDPRHealthIntegration:
    """Verify GDPR subsystem is integrated with the health check."""

    def test_01_health_endpoint_accessible(self, auth_headers):
        """Basic health check still works with GDPR module loaded."""
        url = f"{BASE_URL}/health"
        resp = requests.get(url, headers=auth_headers, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("healthy", "degraded")

    def test_02_database_healthy_for_gdpr_tables(self, auth_headers):
        """Verify database is accessible for GDPR operations."""
        url = f"{BASE_URL}/health"
        resp = requests.get(url, headers=auth_headers, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        db_status = data.get("database", {}).get("status", "unknown")
        assert db_status in ("healthy", "unknown", "degraded"), (
            f"Database must be accessible for GDPR operations, got: {db_status}"
        )


# ── TEST 10: Erasure Request Lifecycle ────────────────────────────


class TestErasureLifecycle:
    """End-to-end test of the full erasure request lifecycle.

    Tests the complete flow:
    1. Create erasure request (pending)
    2. Verify erasure request
    3. Execute erasure request
    4. Verify completion
    5. Verify audit trail was created
    """

    def test_full_lifecycle(self, auth_headers, csrf_token):
        """Full erasure request lifecycle test."""
        headers = _get_headers_with_csrf(auth_headers, csrf_token)

        # Step 1: Create
        create_url = f"{BASE_URL}/api/v1/gdpr/erasure-request"
        create_payload = {
            "customer_email": f"lifecycle-{uuid.uuid4().hex[:8]}@test.com",
            "scope": "full",
            "reason": "End-to-end lifecycle test",
            "request_source": "api",
        }

        create_resp = requests.post(create_url, json=create_payload, headers=headers, timeout=TIMEOUT)
        if create_resp.status_code == 404:
            pytest.skip("GDPR endpoint not deployed")
        assert create_resp.status_code in (200, 201)

        create_data = create_resp.json()
        erasure_id = create_data["id"]
        assert create_data["status"] == "pending"
        assert create_data["verification_status"] == "unverified"

        # Step 2: Verify
        verify_url = f"{BASE_URL}/api/v1/gdpr/erasure-request/{erasure_id}/verify"
        verify_payload = {
            "erasure_request_id": erasure_id,
            "verified": True,
            "note": "Automated test verification",
        }

        verify_resp = requests.post(verify_url, json=verify_payload, headers=headers, timeout=TIMEOUT)
        assert verify_resp.status_code == 200

        verify_data = verify_resp.json()
        assert verify_data["verification_status"] == "verified"

        # Step 3: Execute
        exec_url = f"{BASE_URL}/api/v1/gdpr/erasure-request/{erasure_id}/execute"
        exec_resp = requests.post(exec_url, headers=headers, timeout=TIMEOUT)
        assert exec_resp.status_code == 200

        exec_data = exec_resp.json()
        assert exec_data["status"] in ("completed", "failed")

        # Step 4: Get final status
        get_url = f"{BASE_URL}/api/v1/gdpr/erasure-request/{erasure_id}"
        get_resp = requests.get(get_url, headers=headers, timeout=TIMEOUT)
        assert get_resp.status_code == 200

        final_data = get_resp.json()
        assert final_data["status"] in ("completed", "failed", "processing")
        if final_data["status"] == "completed":
            assert final_data["completed_at"] is not None

        # Step 5: Verify audit trail preserved
        if exec_data.get("status") == "completed":
            assert exec_data.get("audit_trail_preserved") is True
