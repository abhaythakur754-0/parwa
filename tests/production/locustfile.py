"""
PARWA Locust Load Test Entry Point

Thin wrapper that imports from test_load.py for easy locust invocation.

Usage:
    # Basic smoke test
    locust -f tests/production/locustfile.py --host=http://localhost:8000

    # Headless mode with specific user count
    locust -f tests/production/locustfile.py --host=http://localhost:8000 \
        --headless --users 100 --spawn-rate 10 --run-time 5m

    # With HTML report
    locust -f tests/production/locustfile.py --host=http://localhost:8000 \
        --headless --users 500 --spawn-rate 20 --run-time 10m \
        --html=reports/load_test.html
"""

from test_load import (
    ParwaAnonymousUser,
    ParwaAuthenticatedUser,
    ParwaAPIUser,
)

# Re-export for locust discovery
__all__ = [
    "ParwaAnonymousUser",
    "ParwaAuthenticatedUser",
    "ParwaAPIUser",
]
