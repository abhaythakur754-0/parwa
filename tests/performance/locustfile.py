"""
Locust Load Test File for PARWA Performance Optimization.

Week 26 - Builder 5: Performance Monitoring + Load Testing
Target: P95 <300ms at 500 concurrent users, 10 users/second spawn rate

User behavior simulation:
- Ticket creation flow
- Ticket listing flow
- Dashboard load flow
- Agent response flow
"""

import random
import string
from locust import HttpUser, TaskSet, task, between
import json


def random_string(length=10):
    """Generate random string."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def random_email():
    """Generate random email."""
    return f"test_{random_string(8)}@example.com"


class TicketFlow(TaskSet):
    """Task set for ticket-related flows."""

    def on_start(self):
        """Run on user start - authenticate."""
        self.client_id = "test_client_001"
        self.headers = {
            "X-Client-ID": self.client_id,
            "Content-Type": "application/json",
        }

    @task(5)
    def list_tickets(self):
        """List tickets - most common operation."""
        params = {
            "status": random.choice(["open", "pending_approval", "resolved"]),
            "page": 1,
            "limit": 20,
        }
        self.client.get(
            "/api/v1/tickets",
            params=params,
            headers=self.headers,
            name="/api/v1/tickets [list]",
        )

    @task(3)
    def create_ticket(self):
        """Create a new ticket."""
        ticket_data = {
            "subject": f"Test ticket {random_string(8)}",
            "body": f"This is a test ticket body. {random_string(50)}",
            "category": random.choice(["refund", "inquiry", "complaint", "feedback"]),
            "customer_email": random_email(),
        }
        self.client.post(
            "/api/v1/tickets",
            json=ticket_data,
            headers=self.headers,
            name="/api/v1/tickets [create]",
        )

    @task(4)
    def view_ticket(self):
        """View a single ticket."""
        ticket_id = random_string(8)  # Simulated ticket ID
        self.client.get(
            f"/api/v1/tickets/{ticket_id}",
            headers=self.headers,
            name="/api/v1/tickets/{id} [view]",
        )

    @task(2)
    def update_ticket(self):
        """Update ticket status."""
        ticket_id = random_string(8)
        update_data = {
            "status": random.choice(["pending_approval", "resolved", "escalated"]),
            "notes": f"Updated by load test. {random_string(20)}",
        }
        self.client.put(
            f"/api/v1/tickets/{ticket_id}",
            json=update_data,
            headers=self.headers,
            name="/api/v1/tickets/{id} [update]",
        )


class DashboardFlow(TaskSet):
    """Task set for dashboard-related flows."""

    def on_start(self):
        """Run on user start."""
        self.client_id = "test_client_001"
        self.headers = {
            "X-Client-ID": self.client_id,
            "Content-Type": "application/json",
        }

    @task(5)
    def view_dashboard(self):
        """View main dashboard."""
        self.client.get(
            "/api/v1/dashboard",
            headers=self.headers,
            name="/api/v1/dashboard [view]",
        )

    @task(3)
    def view_analytics(self):
        """View analytics page."""
        params = {
            "period": random.choice(["day", "week", "month"]),
        }
        self.client.get(
            "/api/v1/analytics",
            params=params,
            headers=self.headers,
            name="/api/v1/analytics [view]",
        )

    @task(2)
    def view_approvals(self):
        """View approvals queue."""
        self.client.get(
            "/api/v1/approvals",
            headers=self.headers,
            name="/api/v1/approvals [view]",
        )


class AgentFlow(TaskSet):
    """Task set for agent interaction flows."""

    def on_start(self):
        """Run on user start."""
        self.client_id = "test_client_001"
        self.headers = {
            "X-Client-ID": self.client_id,
            "Content-Type": "application/json",
        }

    @task(3)
    def get_ai_response(self):
        """Get AI response for a query."""
        query_data = {
            "query": f"Help me with {random.choice(['refund', 'order', 'shipping', 'product'])}",
            "context": {"session_id": random_string(12)},
        }
        self.client.post(
            "/api/v1/agent/respond",
            json=query_data,
            headers=self.headers,
            name="/api/v1/agent/respond",
        )

    @task(2)
    def submit_feedback(self):
        """Submit feedback on AI response."""
        feedback_data = {
            "response_id": random_string(12),
            "rating": random.choice([1, 2, 3, 4, 5]),
            "comment": f"Test feedback. {random_string(20)}",
        }
        self.client.post(
            "/api/v1/agent/feedback",
            json=feedback_data,
            headers=self.headers,
            name="/api/v1/agent/feedback",
        )


class ParwaUser(HttpUser):
    """
    Main Locust user class for PARWA load testing.

    Simulates realistic user behavior with weighted tasks.
    """
    tasks = {
        TicketFlow: 5,      # 50% - Ticket operations
        DashboardFlow: 3,   # 30% - Dashboard viewing
        AgentFlow: 2,       # 20% - AI interactions
    }
    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks

    def on_start(self):
        """Initialize user session."""
        self.client_id = f"test_client_{random.randint(1, 10):03d}"
        self.environment.events.request.add_listener(self.on_request)

    def on_request(self, request_type, name, response_time, response_length, exception, **kwargs):
        """Track request metrics."""
        # Log slow requests
        if response_time > 300:
            print(f"SLOW REQUEST: {name} took {response_time:.0f}ms")


# Additional user classes for specific load scenarios


class HeavyParwaUser(HttpUser):
    """
    Heavy user that performs more intensive operations.
    Used for stress testing.
    """
    tasks = {
        TicketFlow: 3,
        DashboardFlow: 1,
        AgentFlow: 2,
    }
    wait_time = between(0.5, 2)


class LightParwaUser(HttpUser):
    """
    Light user that performs mostly read operations.
    Used for testing cache effectiveness.
    """
    tasks = {
        DashboardFlow: 3,
        TicketFlow: 1,  # Only list tickets, no writes
    }
    wait_time = between(3, 10)


# Custom task sets for specific testing scenarios


class ReadOnlyFlow(TaskSet):
    """Task set for read-only operations (cache testing)."""

    def on_start(self):
        """Run on user start."""
        self.headers = {"X-Client-ID": "test_client_001"}

    @task(10)
    def list_tickets(self):
        """List tickets - cacheable."""
        self.client.get(
            "/api/v1/tickets",
            params={"status": "open", "page": 1},
            headers=self.headers,
        )

    @task(5)
    def view_dashboard(self):
        """View dashboard - cacheable."""
        self.client.get("/api/v1/dashboard", headers=self.headers)

    @task(3)
    def view_analytics(self):
        """View analytics - cacheable."""
        self.client.get(
            "/api/v1/analytics",
            params={"period": "week"},
            headers=self.headers,
        )


class WriteOnlyFlow(TaskSet):
    """Task set for write operations (cache invalidation testing)."""

    def on_start(self):
        """Run on user start."""
        self.headers = {
            "X-Client-ID": "test_client_001",
            "Content-Type": "application/json",
        }

    @task
    def create_ticket(self):
        """Create tickets to trigger cache invalidation."""
        self.client.post(
            "/api/v1/tickets",
            json={
                "subject": f"Load test {random_string(8)}",
                "body": random_string(100),
                "category": "inquiry",
                "customer_email": random_email(),
            },
            headers=self.headers,
        )
