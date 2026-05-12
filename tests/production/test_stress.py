"""
PARWA Stress Test Suite

Scenarios:
- Spike: 50→500 users in 30 seconds
- Soak: 200 users for 2 hours
- Breakpoint: 0→1000 users, +50/min
- Chaos: Load with simulated infra failures

These tests go beyond normal load testing to identify:
- System breaking points
- Memory leaks under sustained load
- Recovery behavior after failures
- Resource exhaustion thresholds

Run individual scenarios:
    locust -f tests/production/test_stress.py --host=http://localhost:8000 \\
        SpikeTestUser --headless --users 500 --spawn-rate 15

    locust -f tests/production/test_stress.py --host=http://localhost:8000 \\
        SoakTestUser --headless --users 200 --run-time 2h
"""

from locust import HttpUser, task, between, events, tag
import json
import random
import string
import time
import logging
import threading

logger = logging.getLogger("parwa.stress_test")


def _random_string(length: int = 8) -> str:
    """Generate random alphanumeric string."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


# ── Spike Test User ──────────────────────────────────────────────────────────

class SpikeTestUser(HttpUser):
    """Spike Test: Sudden traffic increase from 50 to 500 users.

    Simulates a marketing event or viral content driving sudden traffic.

    Run:
        locust -f tests/production/test_stress.py SpikeTestUser \\
            --headless --users 500 --spawn-rate 15 --run-time 5m

    Success criteria:
    - System remains responsive (p95 < 5s) during spike
    - No 5xx errors > 1%
    - Recovery to < 2s avg within 60 seconds of spike peak
    """

    wait_time = between(0.5, 3)

    @task(4)
    def browse_pages(self):
        """Browse various pages during spike."""
        page = random.choice(["/", "/pricing", "/models", "/health"])
        with self.client.get(page, name=f"{page} (spike)", catch_response=True) as response:
            if response.status_code < 500:
                response.success()
            else:
                response.failure(f"Server error during spike: {response.status_code}")

    @task(3)
    def api_requests(self):
        """Make API requests during spike."""
        endpoint = random.choice([
            "/api/tickets",
            "/api/ticket-analytics/dashboard",
            "/health",
        ])
        with self.client.get(
            endpoint,
            name=f"{endpoint} (spike)",
            catch_response=True,
        ) as response:
            if response.status_code < 500:
                response.success()
            else:
                response.failure(f"Server error during spike: {response.status_code}")

    @task(1)
    def create_ticket_during_spike(self):
        """Create a ticket during traffic spike."""
        with self.client.post(
            "/api/tickets",
            json={
                "subject": f"[Spike Test] Ticket {_random_string(6)}",
                "description": "Auto-generated during spike test",
                "priority": "medium",
            },
            name="/api/tickets (spike create)",
            catch_response=True,
        ) as response:
            if response.status_code < 500:
                response.success()
            else:
                response.failure(f"Server error during spike: {response.status_code}")


# ── Soak Test User ───────────────────────────────────────────────────────────

class SoakTestUser(HttpUser):
    """Soak Test: Sustained load at 70% capacity for 2 hours.

    Detects:
    - Memory leaks (response time degradation over time)
    - Connection pool exhaustion
    - Database connection leaks
    - Cache invalidation issues

    Run:
        locust -f tests/production/test_stress.py SoakTestUser \\
            --headless --users 200 --spawn-rate 5 --run-time 2h

    Success criteria:
    - Response time remains stable (no > 50% degradation)
    - No 5xx errors
    - Memory usage stable (no linear growth)
    """

    wait_time = between(3, 10)
    _request_count = 0
    _lock = threading.Lock()

    def on_start(self):
        """Track request count for degradation detection."""
        with SoakTestUser._lock:
            SoakTestUser._request_count += 1
        self.user_id = SoakTestUser._request_count

    @task(5)
    def view_dashboard(self):
        """View dashboard — most common action during soak."""
        with self.client.get(
            "/api/tickets",
            name="/api/tickets (soak)",
            catch_response=True,
        ) as response:
            if response.status_code < 500:
                response.success()
            else:
                response.failure(f"Soak test server error: {response.status_code}")

    @task(3)
    def view_analytics(self):
        """View analytics during sustained load."""
        with self.client.get(
            "/api/ticket-analytics/dashboard",
            name="/api/ticket-analytics/dashboard (soak)",
            catch_response=True,
        ) as response:
            if response.status_code < 500:
                response.success()
            else:
                response.failure(f"Soak test server error: {response.status_code}")

    @task(2)
    def create_and_view_ticket(self):
        """Create a ticket and then view it — exercises write + read path."""
        with self.client.post(
            "/api/tickets",
            json={
                "subject": f"[Soak Test] User {self.user_id} Ticket {_random_string(4)}",
                "description": "Auto-generated during soak test",
                "priority": random.choice(["low", "medium", "high"]),
            },
            name="/api/tickets (soak create)",
            catch_response=True,
        ) as response:
            if response.status_code < 500:
                response.success()
            else:
                response.failure(f"Soak test server error: {response.status_code}")

    @task(1)
    def health_check(self):
        """Health check — monitors service stability."""
        with self.client.get(
            "/health",
            name="/health (soak)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed during soak: {response.status_code}")


# ── Breakpoint Test User ─────────────────────────────────────────────────────

class BreakpointTestUser(HttpUser):
    """Breakpoint Test: Gradually increase load until failure.

    Identifies the maximum throughput and the breaking point.

    Run:
        locust -f tests/production/test_stress.py BreakpointTestUser \\
            --headless --users 1000 --spawn-rate 1 --run-time 30m

    Success criteria:
    - Identify max sustainable RPS
    - Document failure mode at breakpoint
    - Verify graceful degradation (not hard crash)
    """

    wait_time = between(0.1, 1)

    @task(3)
    def rapid_api_calls(self):
        """Rapid API calls to push system to breakpoint."""
        endpoint = random.choice(["/api/tickets", "/health", "/api/ticket-analytics/dashboard"])
        with self.client.get(
            endpoint,
            name=f"{endpoint} (breakpoint)",
            catch_response=True,
        ) as response:
            if response.status_code < 500:
                response.success()
            elif response.status_code == 429:
                # Rate limited — expected at breakpoint
                response.success()
            elif response.status_code == 503:
                # Service unavailable — breakpoint reached
                response.failure(f"Breakpoint reached: {response.status_code}")
            else:
                response.failure(f"Unexpected: {response.status_code}")

    @task(1)
    def write_operation(self):
        """Write operations stress the database."""
        with self.client.post(
            "/api/tickets",
            json={
                "subject": f"[Breakpoint] {_random_string(8)}",
                "description": "Stress testing write path",
                "priority": "low",
            },
            name="/api/tickets (breakpoint write)",
            catch_response=True,
        ) as response:
            if response.status_code < 500:
                response.success()
            else:
                response.failure(f"Write path failure: {response.status_code}")


# ── Chaos Test User ──────────────────────────────────────────────────────────

class ChaosTestUser(HttpUser):
    """Chaos Test: Load with simulated infrastructure failures.

    Combines normal traffic with deliberately problematic requests:
    - Malformed payloads
    - Extremely large payloads
    - Invalid authentication
    - Concurrent conflicting operations
    - Slow connections (simulated via large responses)

    Run:
        locust -f tests/production/test_stress.py ChaosTestUser \\
            --headless --users 100 --spawn-rate 5 --run-time 10m

    Success criteria:
    - System never crashes (BC-008: never crash)
    - Error responses are proper (not 500 for bad input)
    - Recovery after simulated failures
    """

    wait_time = between(1, 5)

    @task(5)
    def normal_traffic(self):
        """Normal traffic mixed with chaos."""
        with self.client.get(
            "/api/tickets",
            name="/api/tickets (chaos normal)",
            catch_response=True,
        ) as response:
            if response.status_code < 500:
                response.success()
            else:
                response.failure(f"Unexpected 5xx during chaos: {response.status_code}")

    @task(2)
    def malformed_payload(self):
        """Send malformed JSON to test error handling."""
        with self.client.post(
            "/api/tickets",
            data="this is not json {{{",
            headers={"Content-Type": "application/json"},
            name="/api/tickets (chaos malformed)",
            catch_response=True,
        ) as response:
            # Should get 400/422, NOT 500
            if response.status_code in (400, 422):
                response.success()
            elif response.status_code == 500:
                response.failure("Server crashed on malformed input (BC-008 violation)")
            else:
                response.success()

    @task(2)
    def invalid_auth(self):
        """Test with invalid authentication."""
        with self.client.get(
            "/api/tickets",
            headers={"Authorization": "Bearer invalid_token_12345"},
            name="/api/tickets (chaos bad auth)",
            catch_response=True,
        ) as response:
            if response.status_code in (401, 403):
                response.success()
            elif response.status_code == 500:
                response.failure("Server crashed on invalid auth (BC-008 violation)")
            else:
                response.success()

    @task(1)
    def oversized_payload(self):
        """Send an oversized payload."""
        with self.client.post(
            "/api/tickets",
            json={
                "subject": "X" * 10000,
                "description": "Y" * 50000,
                "priority": "medium",
            },
            name="/api/tickets (chaos oversized)",
            catch_response=True,
        ) as response:
            # Should get 400/413/422, NOT 500
            if response.status_code in (400, 413, 422):
                response.success()
            elif response.status_code == 200:
                # Some systems accept large payloads — acceptable
                response.success()
            elif response.status_code == 500:
                response.failure("Server crashed on oversized payload (BC-008 violation)")
            else:
                response.success()

    @task(1)
    def sql_injection_attempt(self):
        """Test SQL injection protection."""
        with self.client.get(
            "/api/tickets/search",
            params={"q": "'; DROP TABLE tickets; --"},
            name="/api/tickets/search (chaos sqli)",
            catch_response=True,
        ) as response:
            # Should NOT crash
            if response.status_code < 500:
                response.success()
            else:
                response.failure("Server crashed on SQL injection attempt (BC-008 violation)")

    @task(1)
    def concurrent_conflicting_operations(self):
        """Simulate concurrent conflicting writes."""
        ticket_id = f"chaos_{_random_string(8)}"
        # Fire multiple updates to the same hypothetical ticket
        with self.client.patch(
            f"/api/tickets/{ticket_id}",
            json={
                "priority": random.choice(["low", "medium", "high", "urgent"]),
                "status": random.choice(["open", "in_progress", "resolved"]),
            },
            name="/api/tickets/{id} (chaos conflict)",
            catch_response=True,
        ) as response:
            if response.status_code < 500:
                response.success()
            else:
                response.failure(f"Server error on conflict: {response.status_code}")


# ── Stress Test Event Listeners ──────────────────────────────────────────────

_stress_stats = {
    "start_time": None,
    "five_xx_count": 0,
    "total_count": 0,
    "degradation_windows": [],
}


@events.test_start.add_listener
def on_stress_test_start(environment, **kwargs):
    """Record test start time."""
    _stress_stats["start_time"] = time.time()
    logger.info("stress_test_started users=%d", environment.runner.target_user_count or 0)


@events.request.add_listener
def on_stress_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track 5xx errors and degradation during stress tests."""
    _stress_stats["total_count"] += 1
    if exception:
        _stress_stats["five_xx_count"] += 1


@events.test_stop.add_listener
def on_stress_test_stop(environment, **kwargs):
    """Generate stress test report."""
    elapsed = time.time() - _stress_stats["start_time"] if _stress_stats["start_time"] else 0
    total = _stress_stats["total_count"]
    errors = _stress_stats["five_xx_count"]

    error_rate = (errors / total * 100) if total > 0 else 0

    report = {
        "test_type": "stress",
        "duration_seconds": round(elapsed, 2),
        "total_requests": total,
        "five_xx_errors": errors,
        "error_rate_pct": round(error_rate, 2),
        "bc_008_pass": error_rate < 1.0,  # < 1% 5xx errors
    }

    logger.info(
        "stress_test_report duration=%.1fs requests=%d errors=%d error_rate=%.2f%% bc008=%s",
        elapsed,
        total,
        errors,
        error_rate,
        report["bc_008_pass"],
    )

    # Write report
    try:
        import os
        reports_dir = os.environ.get(
            "REPORTS_DIR", f"./reports/{time.strftime('%Y%m%d_%H%M%S')}"
        )
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, "stress_test_report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
    except Exception as e:
        logger.warning("stress_test_report_write_failed error=%s", str(e))
