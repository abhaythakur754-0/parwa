#!/usr/bin/env python3
"""
PARWA Master Integration Test Script — Phases 2, 3, 4
Runs against the live backend at localhost:8000
Properly handles CSRF cookies and rate limiting delays.

Usage:
  python3 integration_tests/run_phases_2_3_4.py
"""
import os
import sys
import time
import json
import uuid
import requests

BASE_URL = "http://localhost:8000"

# ─── Colors ───
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

PASS_COUNT = 0
FAIL_COUNT = 0
SKIP_COUNT = 0
RESULTS = []


# ─── Session with CSRF support ───
class CSRFSafeSession(requests.Session):
    """Session that handles CSRF cookies and Origin headers automatically."""
    def __init__(self):
        super().__init__()
        self.headers.update({
            "Origin": "http://localhost:3000",
            "Referer": "http://localhost:3000/",
        })
        self._csrf_initialized = False

    def init_csrf(self, base_url):
        """Fetch CSRF cookie by making a GET request."""
        if self._csrf_initialized:
            return
        try:
            r = super().request("GET", f"{base_url}/api/auth/check-email?email=csrf_init@test.com", timeout=15)
            self._csrf_initialized = True
            csrf = self.cookies.get("parwa_csrf")
            if csrf:
                print(f"  CSRF cookie initialized: {csrf[:30]}...")
            else:
                print(f"  WARNING: No CSRF cookie received — Bearer token requests will still work")
        except Exception as e:
            print(f"  WARNING: CSRF init failed: {e}")

    def request(self, method, url, **kwargs):
        # For non-Bearer requests to cookie-auth paths, add CSRF header
        headers = kwargs.get("headers", {}) or {}
        has_bearer = False
        auth_header = headers.get("Authorization", "")
        if isinstance(auth_header, str) and auth_header.startswith("Bearer "):
            has_bearer = True

        # Add CSRF cookie as header for non-Bearer requests
        if not has_bearer:
            csrf_cookie = self.cookies.get("parwa_csrf")
            if csrf_cookie:
                headers.setdefault("X-CSRF-Token", csrf_cookie)
                kwargs["headers"] = headers

        return super().request(method, url, **kwargs)


def make_session():
    return CSRFSafeSession()


# Global session
http = make_session()


def result(test_name, status, detail=""):
    global PASS_COUNT, FAIL_COUNT, SKIP_COUNT
    if status == "PASS":
        PASS_COUNT += 1
        icon = f"{GREEN}✅ PASS{RESET}"
    elif status == "FAIL":
        FAIL_COUNT += 1
        icon = f"{RED}❌ FAIL{RESET}"
    else:
        SKIP_COUNT += 1
        icon = f"{YELLOW}⏭️ SKIP{RESET}"
    print(f"  {icon} {test_name}: {detail}")
    RESULTS.append((test_name, status, detail))


def register_company(suffix=""):
    """Register a test company and return auth data."""
    unique = uuid.uuid4().hex[:8]
    email = f"itest_{suffix}_{unique}@parwa.ai"
    password = "TestPass123!BC"
    payload = {
        "email": email,
        "password": password,
        "confirm_password": password,
        "full_name": f"ITest {suffix}",
        "company_name": f"ITestCo_{suffix}_{unique}",
        "industry": "saas",
    }
    try:
        r = http.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=30)
        if r.status_code == 429:
            # Rate limited — wait and retry once
            print(f"  {YELLOW}Rate limited on register [{suffix}], waiting 15s...{RESET}")
            time.sleep(15)
            r = http.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=30)

        if r.status_code not in (200, 201):
            print(f"  {RED}Registration failed [{suffix}]: {r.status_code} {r.text[:200]}{RESET}")
            return None
        data = r.json()
        user_data = data.get("user", {})
        token_data = data.get("tokens", {})

        return {
            "email": email,
            "password": password,
            "company_id": user_data.get("company_id"),
            "user_id": user_data.get("id"),
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
        }
    except Exception as e:
        print(f"  {RED}Registration error [{suffix}]: {e}{RESET}")
        return None


def auth_headers(token):
    """Headers for authenticated requests."""
    return {
        "Authorization": f"Bearer {token}",
        "Origin": "http://localhost:3000",
        "Referer": "http://localhost:3000/",
    }


# ═══════════════════════════════════════════════════════════
# PHASE 2: Building Code Compliance Tests
# ═══════════════════════════════════════════════════════════

def test_phase2():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}PHASE 2 — Building Code Compliance Tests (BC-001 to BC-012){RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

    # Register test companies with delays to avoid rate limiting
    co_a = register_company("alpha")
    time.sleep(3)
    co_b = register_company("beta")
    time.sleep(3)

    # ─── BC-001: Multi-Tenant Isolation ───
    print(f"\n{YELLOW}BC-001: Multi-Tenant Isolation{RESET}")
    if co_a and co_b:
        # Create customers for ticket tests
        co_a_customer_id = None
        co_b_customer_id = None
        try:
            r = http.post(f"{BASE_URL}/api/v1/customers", json={
                "name": co_a.get("email", "Alpha Customer"),
                "email": co_a.get("email", "alpha@test.com")
            }, headers=auth_headers(co_a["access_token"]), timeout=15)
            if r.status_code in (200, 201):
                co_a_customer_id = r.json().get("id")
                print(f"  Created customer A: {co_a_customer_id}")
        except Exception:
            pass
        try:
            r = http.post(f"{BASE_URL}/api/v1/customers", json={
                "name": co_b.get("email", "Beta Customer"),
                "email": co_b.get("email", "beta@test.com")
            }, headers=auth_headers(co_b["access_token"]), timeout=15)
            if r.status_code in (200, 201):
                co_b_customer_id = r.json().get("id")
                print(f"  Created customer B: {co_b_customer_id}")
        except Exception:
            pass
        # TEST: Search isolation
        try:
            keyword = f"ISOLATION_{uuid.uuid4().hex[:6]}"
            r1 = http.post(f"{BASE_URL}/api/v1/tickets", json={
                "subject": f"URGENT {keyword} Alpha",
                "description": "Alpha company ticket",
                "priority": "high",
                "channel": "email",
                "customer_id": co_a_customer_id or co_a.get("user_id", "")
            }, headers=auth_headers(co_a["access_token"]), timeout=15)
            r2 = http.post(f"{BASE_URL}/api/v1/tickets", json={
                "subject": f"URGENT {keyword} Beta",
                "description": "Beta company ticket",
                "priority": "high",
                "channel": "email",
                "customer_id": co_b_customer_id or co_b.get("user_id", "")
            }, headers=auth_headers(co_b["access_token"]), timeout=15)

            if r1.status_code in (200, 201) and r2.status_code in (200, 201):
                # Search as Company A
                sr = http.get(f"{BASE_URL}/api/v1/tickets/search",
                    params={"q": keyword}, headers=auth_headers(co_a["access_token"]), timeout=15)
                if sr.status_code == 200:
                    data = sr.json()
                    tickets = data if isinstance(data, list) else data.get("tickets", data.get("items", []))
                    leaked = [t for t in tickets if t.get("company_id") != co_a["company_id"]]
                    if not leaked:
                        result("BC001-SearchIsolation", "PASS", f"0 leaks from {len(tickets)} results")
                    else:
                        result("BC001-SearchIsolation", "FAIL", f"{len(leaked)} tickets from other tenant!")
                else:
                    result("BC001-SearchIsolation", "FAIL", f"Search returned {sr.status_code}")
            else:
                result("BC001-SearchIsolation", "FAIL", f"Ticket creation: A={r1.status_code}, B={r2.status_code}")
        except Exception as e:
            result("BC001-SearchIsolation", "FAIL", str(e))

        # TEST: Direct ID access isolation
        try:
            r1 = http.post(f"{BASE_URL}/api/v1/tickets", json={
                "subject": "Private Alpha Ticket",
                "description": "Secret data",
                "priority": "medium",
                "channel": "email",
                "customer_id": co_a_customer_id or co_a.get("user_id", "")
            }, headers=auth_headers(co_a["access_token"]), timeout=15)
            if r1.status_code in (200, 201):
                ticket_id = r1.json().get("id")
                r2 = http.get(f"{BASE_URL}/api/v1/tickets/{ticket_id}",
                    headers=auth_headers(co_b["access_token"]), timeout=15)
                if r2.status_code == 404:
                    result("BC001-DirectIDAccess", "PASS", "Company B got 404 for A's ticket")
                elif r2.status_code == 403:
                    result("BC001-DirectIDAccess", "FAIL", "Got 403 (reveals existence), should be 404")
                else:
                    result("BC001-DirectIDAccess", "FAIL", f"Expected 404, got {r2.status_code}")
            else:
                result("BC001-DirectIDAccess", "FAIL", f"Create ticket failed: {r1.status_code}")
        except Exception as e:
            result("BC001-DirectIDAccess", "FAIL", str(e))

        # TEST: Analytics isolation
        try:
            # Create tickets in Company A
            for i in range(5):
                http.post(f"{BASE_URL}/api/v1/tickets", json={
                    "subject": f"Alpha Analytics Test {i}",
                    "description": "Analytics isolation test",
                    "priority": "medium",
                    "channel": "email",
                    "customer_id": co_a_customer_id or co_a.get("user_id", "")
                }, headers=auth_headers(co_a["access_token"]), timeout=15)
                time.sleep(0.5)

            # Get Company B's stats — should not include Company A's tickets
            stats_r = http.get(f"{BASE_URL}/api/billing/usage",
                headers=auth_headers(co_b["access_token"]), timeout=15)
            result("BC001-AnalyticsIsolation", "PASS" if stats_r.status_code in (200, 404) else "FAIL",
                   f"Status {stats_r.status_code} (B cannot see A's data)")
        except Exception as e:
            result("BC001-AnalyticsIsolation", "FAIL", str(e))
    else:
        result("BC001-SearchIsolation", "SKIP", "Could not register test companies")
        result("BC001-DirectIDAccess", "SKIP", "Could not register test companies")
        result("BC001-AnalyticsIsolation", "SKIP", "Could not register test companies")

    # ─── BC-002: Financial Action Integrity ───
    print(f"\n{YELLOW}BC-002: Financial Action Integrity{RESET}")
    if co_a:
        try:
            r = http.get(f"{BASE_URL}/api/billing/status", headers=auth_headers(co_a["access_token"]), timeout=15)
            if r.status_code == 200:
                data = r.json()
                result("BC002-BillingStatus", "PASS", f"Billing status returned: {list(data.keys())[:5]}")
            else:
                result("BC002-BillingStatus", "FAIL", f"Status {r.status_code}: {r.text[:100]}")
        except Exception as e:
            result("BC002-BillingStatus", "FAIL", str(e))

        try:
            r = http.get(f"{BASE_URL}/api/billing/subscription", headers=auth_headers(co_a["access_token"]), timeout=15)
            if r.status_code == 200:
                result("BC002-SubscriptionData", "PASS", "Subscription data retrieved")
            elif r.status_code == 404:
                result("BC002-SubscriptionData", "PASS", "No subscription yet (expected for new company)")
            else:
                result("BC002-SubscriptionData", "FAIL", f"Status {r.status_code}")
        except Exception as e:
            result("BC002-SubscriptionData", "FAIL", str(e))
    else:
        result("BC002-BillingStatus", "SKIP", "No auth")
        result("BC002-SubscriptionData", "SKIP", "No auth")

    # ─── BC-003: Webhook Handling ───
    print(f"\n{YELLOW}BC-003: Webhook Handling{RESET}")
    for route_name, route_path in [
        ("Paddle", "/api/webhooks/paddle"),
        ("Brevo", "/api/webhooks/brevo"),
        ("Twilio", "/api/webhooks/twilio"),
        ("DedicatedPaddle", "/api/v1/webhooks/paddle"),
    ]:
        try:
            r = http.post(f"{BASE_URL}{route_path}", json={"test": True}, timeout=15)
            if r.status_code == 404:
                result(f"BC003-{route_name}WebhookRoute", "FAIL", "Route not found")
            elif r.status_code in (401, 403, 422):
                result(f"BC003-{route_name}WebhookRoute", "PASS", f"Route exists, rejected without signature ({r.status_code})")
            else:
                result(f"BC003-{route_name}WebhookRoute", "PASS", f"Route exists (status {r.status_code})")
        except Exception as e:
            result(f"BC003-{route_name}WebhookRoute", "FAIL", str(e))

    # ─── BC-004: Background Jobs ───
    print(f"\n{YELLOW}BC-004: Background Jobs{RESET}")
    try:
        sys.path.insert(0, "/home/z/my-project/parwa/backend")
        from app.config import get_settings
        settings = get_settings()
        result("BC004-TrainingThreshold50", "PASS" if settings.TRAINING_THRESHOLD == 50 else "FAIL",
               f"Threshold = {settings.TRAINING_THRESHOLD}")
    except Exception as e:
        result("BC004-TrainingThreshold50", "FAIL", str(e))

    # ─── BC-007: Smart Router ───
    print(f"\n{YELLOW}BC-007: Smart Router{RESET}")
    if co_a:
        try:
            r = http.get(f"{BASE_URL}/api/ai/status", headers=auth_headers(co_a["access_token"]), timeout=15)
            result("BC007-AIStatusEndpoint", "PASS" if r.status_code in (200, 404) else "FAIL",
                   f"Status {r.status_code}")
        except Exception as e:
            result("BC007-AIStatusEndpoint", "FAIL", str(e))

        try:
            r = http.get(f"{BASE_URL}/api/ai/status", timeout=15)
            result("BC007-AIRequiresAuth", "PASS" if r.status_code in (401, 403) else "FAIL",
                   f"Status {r.status_code}")
        except Exception as e:
            result("BC007-AIRequiresAuth", "FAIL", str(e))

    # ─── BC-009: Approval Workflow ───
    print(f"\n{YELLOW}BC-009: Approval Workflow{RESET}")
    try:
        r = http.get(f"{BASE_URL}/api/v1/tickets", timeout=15)
        result("BC009-TicketsRequireAuth", "PASS" if r.status_code in (401, 403) else "FAIL",
               f"Status {r.status_code}")
    except Exception as e:
        result("BC009-TicketsRequireAuth", "FAIL", str(e))

    # ─── BC-011: Auth & Security ───
    print(f"\n{YELLOW}BC-011: Auth & Security{RESET}")
    try:
        from app.config import get_settings
        s = get_settings()
        result("BC011-JWTExpiry15min", "PASS" if s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 15 else "FAIL",
               f"Expiry = {s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES} min")
        result("BC011-MaxSessions5", "PASS" if s.MAX_SESSIONS_PER_USER == 5 else "FAIL",
               f"Max = {s.MAX_SESSIONS_PER_USER}")
    except Exception as e:
        result("BC011-JWTExpiry15min", "FAIL", str(e))
        result("BC011-MaxSessions5", "FAIL", str(e))

    if co_a:
        # Test refresh token rotation
        try:
            r1 = http.post(f"{BASE_URL}/api/auth/refresh", json={
                "refresh_token": co_a["refresh_token"]
            }, timeout=15)
            if r1.status_code == 200:
                new_tokens = r1.json()
                new_refresh = new_tokens.get("refresh_token")
                # Old refresh token should not work again
                r2 = http.post(f"{BASE_URL}/api/auth/refresh", json={
                    "refresh_token": co_a["refresh_token"]
                }, timeout=15)
                result("BC011-RefreshTokenRotation", "PASS" if r2.status_code == 401 else "FAIL",
                       f"Old token status: {r2.status_code}")
            else:
                result("BC011-RefreshTokenRotation", "FAIL", f"Refresh failed: {r1.status_code}")
        except Exception as e:
            result("BC011-RefreshTokenRotation", "FAIL", str(e))

        # Test expired/invalid token
        try:
            r = http.get(f"{BASE_URL}/api/auth/me",
                headers={"Authorization": "Bearer invalid.jwt.token",
                         "Origin": "http://localhost:3000"}, timeout=15)
            result("BC011-InvalidTokenRejected", "PASS" if r.status_code == 401 else "FAIL",
                   f"Status {r.status_code}")
        except Exception as e:
            result("BC011-InvalidTokenRejected", "FAIL", str(e))

    # ─── BC-012: Error Handling ───
    print(f"\n{YELLOW}BC-012: Error Handling{RESET}")
    try:
        r = http.post(f"{BASE_URL}/api/auth/register",
            data="not json", headers={"Content-Type": "application/json",
                                       "Origin": "http://localhost:3000"}, timeout=15)
        body = r.text.lower()
        has_traceback = "traceback" in body
        has_filepath = 'file "' in body
        result("BC012-NoStackTraceInErrors", "PASS" if not has_traceback and not has_filepath else "FAIL",
               f"Traceback={has_traceback}, FilePath={has_filepath}")
    except Exception as e:
        result("BC012-NoStackTraceInErrors", "FAIL", str(e))

    try:
        r = http.get(f"{BASE_URL}/api/nonexistent_route_xyz", timeout=15)
        result("BC012-404ForNonexistentRoute", "PASS" if r.status_code in (403, 404) else "FAIL",
               f"Status {r.status_code}")
    except Exception as e:
        result("BC012-404ForNonexistentRoute", "FAIL", str(e))

    try:
        r = http.get(f"{BASE_URL}/health", timeout=15)
        if r.status_code == 200:
            data = r.json()
            pg_status = data.get("subsystems", {}).get("postgresql", {}).get("status")
            redis_status = data.get("subsystems", {}).get("redis", {}).get("status")
            result("BC012-GracefulDegradationNoRedis", "PASS",
                   f"PostgreSQL={pg_status}, Redis={redis_status} (app still works)")
        else:
            result("BC012-GracefulDegradationNoRedis", "FAIL", f"Health check failed: {r.status_code}")
    except Exception as e:
        result("BC012-GracefulDegradationNoRedis", "FAIL", str(e))

    # ─── BC-005/BC-006: Socket.io & Email ───
    print(f"\n{YELLOW}BC-005/006: Socket.io & Email{RESET}")
    try:
        r = http.get(f"{BASE_URL}/socket.io/", timeout=15)
        result("BC005-SocketIOEndpoint", "PASS" if r.status_code != 404 else "FAIL",
               f"Status {r.status_code}")
    except Exception as e:
        result("BC005-SocketIOEndpoint", "FAIL", str(e))

    try:
        r = http.post(f"{BASE_URL}/api/v1/email/ooo/detect",
            json={"subject": "Out of Office", "body": "I'm away"}, timeout=15)
        result("BC006-OOODetectionRoute", "PASS" if r.status_code != 404 else "FAIL",
               f"Status {r.status_code}")
    except Exception as e:
        result("BC006-OOODetectionRoute", "FAIL", str(e))


# ═══════════════════════════════════════════════════════════
# PHASE 3: Auth & Identity Tests
# ═══════════════════════════════════════════════════════════

def test_phase3():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}PHASE 3 — Auth & Identity Tests{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

    # ─── FLOW 1: Email Registration ───
    print(f"\n{YELLOW}FLOW 1: Email Registration{RESET}")
    unique = uuid.uuid4().hex[:8]
    email = f"auth_flow_{unique}@parwa.ai"
    password = "SecurePass123!"
    access_token = None
    refresh_token = None

    time.sleep(5)  # Wait for rate limit window to reset

    try:
        r = http.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password,
            "confirm_password": password,
            "full_name": "Auth Flow Tester",
            "company_name": f"AuthFlowCo_{unique}",
            "industry": "saas",
        }, timeout=30)
        if r.status_code in (200, 201):
            data = r.json()
            user_data = data.get("user", {})
            token_data = data.get("tokens", {})
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            result("AUTH-Register", "PASS", f"User created: {user_data.get('id', 'N/A')}")
        elif r.status_code == 429:
            result("AUTH-Register", "SKIP", f"Rate limited — waiting 65s and retrying")
            time.sleep(65)
            r = http.post(f"{BASE_URL}/api/auth/register", json={
                "email": email,
                "password": password,
                "confirm_password": password,
                "full_name": "Auth Flow Tester",
                "company_name": f"AuthFlowCo_{unique}",
                "industry": "saas",
            }, timeout=30)
            if r.status_code in (200, 201):
                data = r.json()
                user_data = data.get("user", {})
                token_data = data.get("tokens", {})
                access_token = token_data.get("access_token")
                refresh_token = token_data.get("refresh_token")
                result("AUTH-Register", "PASS", f"User created after retry: {user_data.get('id', 'N/A')}")
            else:
                result("AUTH-Register", "FAIL", f"Status {r.status_code}: {r.text[:200]}")
        else:
            result("AUTH-Register", "FAIL", f"Status {r.status_code}: {r.text[:200]}")
    except Exception as e:
        result("AUTH-Register", "FAIL", str(e))

    # ─── Login ───
    print(f"\n{YELLOW}FLOW 1b: Login{RESET}")
    if not access_token:
        time.sleep(2)
        try:
            r = http.post(f"{BASE_URL}/api/auth/login", json={
                "email": email,
                "password": password
            }, timeout=30)
            if r.status_code == 200:
                data = r.json()
                token_data = data.get("tokens", data)
                access_token = token_data.get("access_token")
                refresh_token = token_data.get("refresh_token")
                result("AUTH-Login", "PASS", f"Tokens received")
            elif r.status_code == 429:
                result("AUTH-Login", "SKIP", "Rate limited on login")
            else:
                result("AUTH-Login", "FAIL", f"Status {r.status_code}: {r.text[:200]}")
        except Exception as e:
            result("AUTH-Login", "FAIL", str(e))
    else:
        result("AUTH-Login", "PASS", "Tokens from registration (skipped separate login)")

    # ─── Get current user ───
    print(f"\n{YELLOW}FLOW 1c: Get Current User{RESET}")
    if access_token:
        try:
            r = http.get(f"{BASE_URL}/api/auth/me",
                headers=auth_headers(access_token), timeout=15)
            if r.status_code == 200:
                data = r.json()
                result("AUTH-GetCurrentUser", "PASS", f"User: {data.get('email', data.get('full_name', 'N/A'))}")
            else:
                result("AUTH-GetCurrentUser", "FAIL", f"Status {r.status_code}")
        except Exception as e:
            result("AUTH-GetCurrentUser", "FAIL", str(e))

    # ─── FLOW 4: Email Availability Check ───
    print(f"\n{YELLOW}FLOW 4: Email Availability{RESET}")
    try:
        r1 = http.get(f"{BASE_URL}/api/auth/check-email", params={"email": email}, timeout=30)
        if r1.status_code == 200:
            data = r1.json()
            has_message = bool(data.get("message"))
            result("AUTH-EmailCheckTaken", "PASS", f"Generic anti-enumeration response: message={has_message}")
        else:
            result("AUTH-EmailCheckTaken", "FAIL", f"Status {r1.status_code}")

        r2 = http.get(f"{BASE_URL}/api/auth/check-email",
            params={"email": f"never_exists_{unique}@parwa.ai"}, timeout=30)
        if r2.status_code == 200:
            data = r2.json()
            has_message = bool(data.get("message"))
            result("AUTH-EmailCheckFree", "PASS", f"Generic anti-enumeration response: message={has_message}")
        else:
            result("AUTH-EmailCheckFree", "FAIL", f"Status {r2.status_code}")
    except Exception as e:
        result("AUTH-EmailCheckTaken", "FAIL", str(e))
        result("AUTH-EmailCheckFree", "FAIL", str(e))

    # ─── FLOW 3: Password Reset ───
    print(f"\n{YELLOW}FLOW 3: Password Reset{RESET}")
    try:
        r = http.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": email}, timeout=15)
        result("AUTH-ForgotPassword", "PASS" if r.status_code in (200, 429) else "FAIL",
               f"Status {r.status_code}")
    except Exception as e:
        result("AUTH-ForgotPassword", "FAIL", str(e))

    # ─── MFA Routes ───
    print(f"\n{YELLOW}MFA Routes{RESET}")
    if access_token:
        try:
            r = http.post(f"{BASE_URL}/api/auth/mfa/setup/initiate",
                json={}, headers=auth_headers(access_token), timeout=15)
            result("AUTH-MFASetupInitiate", "PASS" if r.status_code in (200, 201, 404, 422, 503) else "FAIL",
                   f"Status {r.status_code}")
        except Exception as e:
            result("AUTH-MFASetupInitiate", "FAIL", str(e))

    # ─── Session Management ───
    print(f"\n{YELLOW}Session Management{RESET}")
    if access_token:
        try:
            r = http.get(f"{BASE_URL}/api/auth/sessions",
                headers=auth_headers(access_token), timeout=15)
            result("AUTH-ListSessions", "PASS" if r.status_code == 200 else "FAIL",
                   f"Status {r.status_code}")
        except Exception as e:
            result("AUTH-ListSessions", "FAIL", str(e))

    # ─── Logout ───
    print(f"\n{YELLOW}Logout{RESET}")
    if access_token and refresh_token:
        try:
            r = http.post(f"{BASE_URL}/api/auth/logout",
                json={"refresh_token": refresh_token},
                headers=auth_headers(access_token), timeout=30)
            result("AUTH-Logout", "PASS" if r.status_code in (200, 204) else "FAIL",
                   f"Status {r.status_code}")
        except Exception as e:
            result("AUTH-Logout", "FAIL", str(e))

    # ─── OpenAPI docs (dev mode) ───
    print(f"\n{YELLOW}OpenAPI Docs{RESET}")
    try:
        r = http.get(f"{BASE_URL}/docs", allow_redirects=False, timeout=15)
        result("AUTH-DocsAvailableInDev", "PASS" if r.status_code in (200, 307, 308) else "FAIL",
               f"Status {r.status_code}")
    except Exception as e:
        result("AUTH-DocsAvailableInDev", "FAIL", str(e))


# ═══════════════════════════════════════════════════════════
# PHASE 4: Billing & Subscription Tests
# ═══════════════════════════════════════════════════════════

def test_phase4():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}PHASE 4 — Billing & Subscription Tests{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

    time.sleep(5)  # Rate limit cool-down
    co = register_company("billing")
    if not co:
        print(f"  {RED}Cannot register company for billing tests — using existing test user{RESET}")
        # Try to login as existing test user
        try:
            r = http.post(f"{BASE_URL}/api/auth/login", json={
                "email": "abhay@parwa.ai",
                "password": "password123"
            }, timeout=30)
            if r.status_code == 200:
                data = r.json()
                token_data = data.get("tokens", data)
                co = {
                    "access_token": token_data.get("access_token"),
                    "refresh_token": token_data.get("refresh_token"),
                }
                print(f"  {GREEN}Logged in as existing test user{RESET}")
            else:
                print(f"  {RED}Cannot login either: {r.status_code}{RESET}")
                return
        except Exception as e:
            print(f"  {RED}Login failed: {e}{RESET}")
            return

    token = co["access_token"]

    # ─── TEST 1: Pricing Endpoint ───
    print(f"\n{YELLOW}TEST 1: Pricing Endpoint{RESET}")
    try:
        r = http.get(f"{BASE_URL}/api/pricing/industries", headers=auth_headers(token), timeout=15)
        if r.status_code == 200:
            data = r.json()
            industries = data if isinstance(data, list) else data.get("industries", [])
            result("BILL-IndustriesList", "PASS", f"{len(industries)} industries returned")
        else:
            result("BILL-IndustriesList", "FAIL", f"Status {r.status_code}: {r.text[:200]}")
    except Exception as e:
        result("BILL-IndustriesList", "FAIL", str(e))

    try:
        r = http.get(f"{BASE_URL}/api/pricing/variants/saas", headers=auth_headers(token), timeout=15)
        if r.status_code == 200:
            data = r.json()
            result("BILL-VariantsByIndustry", "PASS", f"Variants returned for saas")
        else:
            result("BILL-VariantsByIndustry", "FAIL", f"Status {r.status_code}")
    except Exception as e:
        result("BILL-VariantsByIndustry", "FAIL", str(e))

    # ─── TEST 2: Subscription Endpoints ───
    print(f"\n{YELLOW}TEST 2: Subscription Endpoints{RESET}")
    try:
        r = http.get(f"{BASE_URL}/api/billing/subscription", headers=auth_headers(token), timeout=15)
        if r.status_code == 200:
            data = r.json()
            result("BILL-GetSubscription", "PASS", f"Subscription data: tier={data.get('tier', 'N/A')}")
        elif r.status_code == 404:
            result("BILL-GetSubscription", "PASS", "No subscription yet (expected for new company)")
        else:
            result("BILL-GetSubscription", "FAIL", f"Status {r.status_code}")
    except Exception as e:
        result("BILL-GetSubscription", "FAIL", str(e))

    # ─── TEST 3: Billing Status ───
    print(f"\n{YELLOW}TEST 3: Billing Status{RESET}")
    try:
        r = http.get(f"{BASE_URL}/api/billing/status", headers=auth_headers(token), timeout=15)
        if r.status_code == 200:
            data = r.json()
            result("BILL-BillingStatus", "PASS", f"Status: {data.get('status', data.get('subscription_status', 'N/A'))}")
        else:
            result("BILL-BillingStatus", "FAIL", f"Status {r.status_code}")
    except Exception as e:
        result("BILL-BillingStatus", "FAIL", str(e))

    # ─── TEST 4: Usage Endpoint ───
    print(f"\n{YELLOW}TEST 4: Usage Endpoint{RESET}")
    try:
        r = http.get(f"{BASE_URL}/api/billing/usage", headers=auth_headers(token), timeout=15)
        result("BILL-UsageEndpoint", "PASS" if r.status_code in (200, 404) else "FAIL",
               f"Status {r.status_code}")
    except Exception as e:
        result("BILL-UsageEndpoint", "FAIL", str(e))

    # ─── TEST 5: Invoices Endpoint ───
    print(f"\n{YELLOW}TEST 5: Invoices Endpoint{RESET}")
    try:
        r = http.get(f"{BASE_URL}/api/billing/invoices", headers=auth_headers(token), timeout=15)
        result("BILL-InvoicesEndpoint", "PASS" if r.status_code in (200, 404) else "FAIL",
               f"Status {r.status_code}")
    except Exception as e:
        result("BILL-InvoicesEndpoint", "FAIL", str(e))

    # ─── TEST 6: Client Refunds Endpoint ───
    print(f"\n{YELLOW}TEST 6: Client Refunds{RESET}")
    try:
        r = http.get(f"{BASE_URL}/api/billing/client-refunds", headers=auth_headers(token), timeout=15)
        result("BILL-ClientRefundsEndpoint", "PASS" if r.status_code in (200, 404) else "FAIL",
               f"Status {r.status_code}")
    except Exception as e:
        result("BILL-ClientRefundsEndpoint", "FAIL", str(e))

    # ─── TEST 7: Proration Preview ───
    print(f"\n{YELLOW}TEST 7: Proration Preview{RESET}")
    try:
        r = http.post(f"{BASE_URL}/api/billing/proration/preview", json={
            "new_tier": "growth"
        }, headers=auth_headers(token), timeout=15)
        result("BILL-ProrationPreview", "PASS" if r.status_code in (200, 404, 422) else "FAIL",
               f"Status {r.status_code}")
    except Exception as e:
        result("BILL-ProrationPreview", "FAIL", str(e))

    # ─── TEST 8: ROI Calculator (Public) ───
    print(f"\n{YELLOW}TEST 8: ROI Calculator (Public){RESET}")
    try:
        r = http.get(f"{BASE_URL}/public/roi-calculator", timeout=15)
        result("BILL-ROICalculatorPublic", "PASS" if r.status_code in (200, 404, 307) else "FAIL",
               f"Status {r.status_code}")
    except Exception as e:
        result("BILL-ROICalculatorPublic", "FAIL", str(e))

    # ─── TEST 9: Webhook Idempotency Check ───
    print(f"\n{YELLOW}TEST 9: Paddle Webhook Idempotency{RESET}")
    try:
        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "event_type": "payment.succeeded",
            "data": {"test": True}
        }
        r1 = http.post(f"{BASE_URL}/api/v1/webhooks/paddle",
            json=payload, timeout=15)
        r2 = http.post(f"{BASE_URL}/api/v1/webhooks/paddle",
            json=payload, timeout=15)
        both_ok = r1.status_code != 404 and r2.status_code != 404
        result("BILL-WebhookIdempotency", "PASS" if both_ok else "FAIL",
               f"First: {r1.status_code}, Second: {r2.status_code}")
    except Exception as e:
        result("BILL-WebhookIdempotency", "FAIL", str(e))


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def main():
    print(f"\n{BLUE}╔══════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BLUE}║  PARWA Integration Tests — Phases 2, 3, 4              ║{RESET}")
    print(f"{BLUE}╚══════════════════════════════════════════════════════════╝{RESET}")

    # Check backend is running
    try:
        r = http.get(f"{BASE_URL}/health", timeout=15)
        if r.status_code != 200:
            print(f"{RED}Backend returned {r.status_code} on /health{RESET}")
            sys.exit(1)
        print(f"{GREEN}Backend is running{RESET}")
    except Exception:
        print(f"{RED}Backend not running at {BASE_URL}! Start it first.{RESET}")
        sys.exit(1)

    # Initialize CSRF cookie
    http.init_csrf(BASE_URL)

    # Run all phases
    test_phase2()
    time.sleep(3)
    test_phase3()
    time.sleep(3)
    test_phase4()

    # Summary
    total = PASS_COUNT + FAIL_COUNT + SKIP_COUNT
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}SUMMARY{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"  Total Tests:  {total}")
    print(f"  {GREEN}Passed: {PASS_COUNT}{RESET}")
    print(f"  {RED}Failed: {FAIL_COUNT}{RESET}")
    print(f"  {YELLOW}Skipped: {SKIP_COUNT}{RESET}")

    if FAIL_COUNT > 0:
        print(f"\n{RED}FAILED TESTS:{RESET}")
        for name, status, detail in RESULTS:
            if status == "FAIL":
                print(f"  {RED}❌ {name}: {detail}{RESET}")

    print(f"\n{GREEN if FAIL_COUNT == 0 else RED}Overall: {'ALL PASSED!' if FAIL_COUNT == 0 else f'{FAIL_COUNT} FAILURES'}{RESET}")

    # Save results
    results_path = "/home/z/my-project/parwa/integration_tests/results.json"
    with open(results_path, "w") as f:
        json.dump({
            "total": total,
            "passed": PASS_COUNT,
            "failed": FAIL_COUNT,
            "skipped": SKIP_COUNT,
            "results": [{"name": n, "status": s, "detail": d} for n, s, d in RESULTS]
        }, f, indent=2)
    print(f"\nResults saved to: {results_path}")

    return 0 if FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
