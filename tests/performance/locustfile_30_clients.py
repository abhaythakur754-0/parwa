"""Locust file for 30-client load testing."""

from locust import HttpUser, task, between


class ClientUser(HttpUser):
    """Simulates a user from one of 30 clients."""
    wait_time = between(1, 5)

    @task
    def create_ticket(self):
        """Simulate ticket creation."""
        pass

    @task
    def get_tickets(self):
        """Simulate ticket retrieval."""
        pass
