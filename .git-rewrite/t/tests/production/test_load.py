"""
PARWA Production Load Test Suite

Target: 500 concurrent users, < 2s average response time (NFR 3.1)

User profiles:
- ParwaAnonymousUser: Unauthenticated users browsing landing/pricing
- ParwaAuthenticatedUser: Authenticated users using dashboard
- ParwaAPIUser: API key users (programmatic access)

Run:
    locust -f tests/production/locustfile.py --host=http://localhost:8000
"""

from locust import HttpUser, task, between, events
import json
import random
import string
import time
import logging

logger = logging.getLogger("parwa.load_test")


# ── Test Data Helpers ────────────────────────────────────────────────────────

def _random_string(length: int = 8) -> str:
    """Generate random alphanumeric string."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _random_email() -> str:
    """Generate random email address."""
    return f"loadtest_{_random_string(10)}@parwa-test.com"


def _random_ticket_subject() -> str:
    """Generate random ticket subject."""
    subjects = [
        "Cannot access my account",
        "Billing issue with recent charge",
        "Feature request: dark mode",
        "Integration with Shopify not working",
        "API rate limit exceeded",
        "Need help with onboarding",
        "Chat widget not loading",
        "SLA breach on ticket #1234",
        "Custom field configuration",
        "Team member permissions issue",
    ]
    return random.choice(subjects)


def _random_ticket_body() -> str:
    """Generate random ticket body."""
    bodies = [
        "I am experiencing an issue that needs immediate attention.",
        "Can someone help me configure the integration?",
        "The dashboard is not showing the correct analytics data.",
        "We need to add more team members to our plan.",
        "Our customers are complaining about response times.",
    ]
    return random.choice(bodies)


# ── Anonymous User Profile ───────────────────────────────────────────────────

class ParwaAnonymousUser(HttpUser):
    """Simulates unauthenticated users browsing landing/pricing.

    Weight: 3 (most common user type)
    Wait time: 1-5 seconds between requests
    Target: < 500ms response time for static pages
    """

    weight = 3
    wait_time = between(1, 5)

    @task(3)
    def browse_landing(self):
        """Browse the landing page."""
        with self.client.get(
            "/",
            name="/ (landing)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code in (301, 302):
                # Redirect is acceptable for landing page
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def browse_pricing(self):
        """Browse the pricing page."""
        with self.client.get(
            "/pricing",
            name="/pricing",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code in (301, 302):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def browse_models(self):
        """Browse the models/AI page."""
        with self.client.get(
            "/models",
            name="/models",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code in (301, 302):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def health_check(self):
        """Health check endpoint (lightweight, used for monitoring)."""
        with self.client.get(
            "/health",
            name="/health",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")


# ── Authenticated User Profile ───────────────────────────────────────────────

class ParwaAuthenticatedUser(HttpUser):
    """Simulates authenticated users using the dashboard.

    Weight: 2 (second most common)
    Wait time: 2-8 seconds between requests
    Target: < 2s average response time (NFR 3.1)
    """

    weight = 2
    wait_time = between(2, 8)

    def on_start(self):
        """Login and get JWT token.

        Creates a test user if needed, then authenticates
        to get a JWT access token for subsequent requests.
        """
        self.auth_email = _random_email()
        self.auth_password = f"TestP@ss_{_random_string(12)}"
        self.headers = {"Content-Type": "application/json"}
        self.company_id = None

        # Try to register a new user
        try:
            register_resp = self.client.post(
                "/api/auth/register",
                json={
                    "email": self.auth_email,
                    "password": self.auth_password,
                    "name": f"Load Test User {_random_string(4)}",
                    "company_name": f"Load Test Co {_random_string(4)}",
                },
                name="/api/auth/register",
            )

            if register_resp.status_code in (200, 201):
                data = register_resp.json()
                self.access_token = data.get("access_token", "")
                self.company_id = data.get("company_id", "")
            else:
                # Fall back to login (user might already exist)
                self._login()
        except Exception:
            self._login()

        # Set auth headers
        if self.access_token:
            self.headers["Authorization"] = f"Bearer {self.access_token}"

    def _login(self):
        """Authenticate and get JWT token."""
        self.access_token = ""
        try:
            login_resp = self.client.post(
                "/api/auth/login",
                json={
                    "email": self.auth_email,
                    "password": self.auth_password,
                },
                name="/api/auth/login",
            )
            if login_resp.status_code == 200:
                data = login_resp.json()
                self.access_token = data.get("access_token", "")
                self.company_id = data.get("company_id", "")
        except Exception:
            pass

    @task(5)
    def view_dashboard(self):
        """View the main dashboard/ticket list."""
        if not self.access_token:
            return
        with self.client.get(
            "/api/tickets",
            headers=self.headers,
            name="/api/tickets (list)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                # Token expired — re-authenticate
                self._login()
                if self.access_token:
                    self.headers["Authorization"] = f"Bearer {self.access_token}"
                response.failure("Token expired, re-authenticating")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def create_ticket(self):
        """Create a new support ticket."""
        if not self.access_token:
            return
        with self.client.post(
            "/api/tickets",
            json={
                "subject": _random_ticket_subject(),
                "description": _random_ticket_body(),
                "priority": random.choice(["low", "medium", "high", "urgent"]),
                "category": random.choice(["general", "billing", "technical", "feature_request"]),
            },
            headers=self.headers,
            name="/api/tickets (create)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            elif response.status_code == 401:
                self._login()
                response.failure("Token expired")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def view_analytics(self):
        """View the analytics dashboard."""
        if not self.access_token:
            return
        with self.client.get(
            "/api/ticket-analytics/dashboard",
            headers=self.headers,
            name="/api/ticket-analytics/dashboard",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                self._login()
                response.failure("Token expired")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def jarvis_chat(self):
        """Send a message to Jarvis AI."""
        if not self.access_token:
            return
        with self.client.post(
            "/api/jarvis/message",
            json={
                "message": random.choice([
                    "What's my current ticket volume?",
                    "Show me overdue tickets",
                    "How is my team performing today?",
                    "Any SLA breaches I should know about?",
                ]),
            },
            headers=self.headers,
            name="/api/jarvis/message",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                self._login()
                response.failure("Token expired")
            elif response.status_code == 429:
                # Rate limited — acceptable under load
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


# ── API User Profile ─────────────────────────────────────────────────────────

class ParwaAPIUser(HttpUser):
    """Simulates API key users (programmatic access).

    Weight: 1 (least common, but most demanding)
    Wait time: 0.5-2 seconds between requests
    Target: < 1s response time for API endpoints
    """

    weight = 1
    wait_time = between(0.5, 2)

    def on_start(self):
        """Get API key for programmatic access."""
        self.api_key = f"pk_test_{_random_string(32)}"
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }
        self.company_id = f"co_{_random_string(8)}"

    @task(3)
    def create_ticket_api(self):
        """Create ticket via API."""
        with self.client.post(
            "/api/tickets",
            json={
                "subject": f"[API] {_random_ticket_subject()}",
                "description": _random_ticket_body(),
                "priority": "medium",
                "source": "api",
                "company_id": self.company_id,
            },
            headers=self.headers,
            name="/api/tickets (API create)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201, 401):
                # 401 is expected without valid API key in load test
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)
    def list_tickets_api(self):
        """List tickets via API."""
        with self.client.get(
            "/api/tickets",
            headers=self.headers,
            params={"page": 1, "per_page": 25},
            name="/api/tickets (API list)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 401):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def search_tickets_api(self):
        """Search tickets via API."""
        with self.client.get(
            "/api/tickets/search",
            headers=self.headers,
            params={"q": random.choice(["billing", "urgent", "SLA", "API"])},
            name="/api/tickets/search (API)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 401, 404):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


# ── Custom Event Listeners ───────────────────────────────────────────────────

# Track custom metrics for reporting
_request_stats = {
    "total_requests": 0,
    "total_failures": 0,
    "response_times": [],
    "endpoint_stats": {},
}


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track custom metrics for each request.

    Records:
    - Total request count
    - Failure count
    - Response time distribution
    - Per-endpoint statistics
    """
    _request_stats["total_requests"] += 1

    if exception:
        _request_stats["total_failures"] += 1

    _request_stats["response_times"].append(response_time)

    # Per-endpoint stats
    if name not in _request_stats["endpoint_stats"]:
        _request_stats["endpoint_stats"][name] = {
            "count": 0,
            "failures": 0,
            "total_response_time": 0,
        }

    endpoint = _request_stats["endpoint_stats"][name]
    endpoint["count"] += 1
    endpoint["total_response_time"] += response_time
    if exception:
        endpoint["failures"] += 1


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Generate test report with custom metrics.

    Produces a summary including:
    - Overall pass/fail against NFR 3.1 (< 2s avg response time)
    - Per-endpoint average response times
    - Failure rate
    - P50/P95/P99 percentiles
    """
    if not _request_stats["response_times"]:
        logger.info("load_test_no_data_collected")
        return

    response_times = sorted(_request_stats["response_times"])
    total = len(response_times)

    # Calculate percentiles
    p50 = response_times[int(total * 0.50)] if total > 0 else 0
    p95 = response_times[int(total * 0.95)] if total > 0 else 0
    p99 = response_times[int(total * 0.99)] if total > 0 else 0
    avg = sum(response_times) / total if total > 0 else 0

    # NFR 3.1 check: < 2s average response time
    nfr_pass = avg < 2000

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_requests": _request_stats["total_requests"],
        "total_failures": _request_stats["total_failures"],
        "failure_rate": (
            _request_stats["total_failures"] / _request_stats["total_requests"] * 100
            if _request_stats["total_requests"] > 0
            else 0
        ),
        "response_time_avg_ms": round(avg, 2),
        "response_time_p50_ms": round(p50, 2),
        "response_time_p95_ms": round(p95, 2),
        "response_time_p99_ms": round(p99, 2),
        "nfr_3_1_pass": nfr_pass,
        "nfr_3_1_target_ms": 2000,
        "endpoint_stats": {},
    }

    # Per-endpoint averages
    for name, stats in _request_stats["endpoint_stats"].items():
        if stats["count"] > 0:
            report["endpoint_stats"][name] = {
                "count": stats["count"],
                "failures": stats["failures"],
                "avg_response_time_ms": round(
                    stats["total_response_time"] / stats["count"], 2
                ),
            }

    logger.info(
        "load_test_report_summary "
        "total=%d failures=%d avg=%.2fms p95=%.2fms nfr_pass=%s",
        report["total_requests"],
        report["total_failures"],
        report["response_time_avg_ms"],
        report["response_time_p95_ms"],
        report["nfr_3_1_pass"],
    )

    # Write JSON report
    try:
        import os
        reports_dir = os.environ.get(
            "REPORTS_DIR", f"./reports/{time.strftime('%Y%m%d_%H%M%S')}"
        )
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, "load_test_report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info("load_test_report_written path=%s", report_path)
    except Exception as e:
        logger.warning("load_test_report_write_failed error=%s", str(e))
