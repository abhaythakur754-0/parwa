"""
E2E Test Configuration and Fixtures.

Provides common fixtures for E2E testing:
- browser_context fixture
- authenticated_session fixture
- test_user fixture
- mock_paddle fixture
- screenshot_on_failure
- video_recording
- trace_on_failure
"""
import pytest
from typing import Dict, Any, AsyncGenerator
from datetime import datetime, timezone
import uuid


class MockBrowserContext:
    """Mock browser context for E2E testing."""

    def __init__(self) -> None:
        self._cookies: Dict[str, str] = {}
        self._storage: Dict[str, Any] = {}
        self._pages: list = []

    async def set_cookie(self, name: str, value: str) -> None:
        """Set a cookie."""
        self._cookies[name] = value

    async def get_cookie(self, name: str) -> str:
        """Get a cookie."""
        return self._cookies.get(name)

    async def clear_cookies(self) -> None:
        """Clear all cookies."""
        self._cookies = {}

    async def set_storage(self, key: str, value: Any) -> None:
        """Set local storage item."""
        self._storage[key] = value

    async def get_storage(self, key: str) -> Any:
        """Get local storage item."""
        return self._storage.get(key)


class MockPaddleClient:
    """Mock Paddle client for E2E testing."""

    def __init__(self) -> None:
        self._refund_calls: list = []
        self._call_count = 0

    async def process_refund(
        self,
        order_id: str,
        amount: float,
        reason: str
    ) -> Dict[str, Any]:
        """Process a Paddle refund."""
        self._call_count += 1
        record = {
            "call_number": self._call_count,
            "order_id": order_id,
            "amount": amount,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "processed",
        }
        self._refund_calls.append(record)
        return record

    def get_call_count(self) -> int:
        """Get number of refund calls."""
        return self._call_count

    def reset(self) -> None:
        """Reset the mock."""
        self._refund_calls = []
        self._call_count = 0


class TestUser:
    """Test user for E2E testing."""

    def __init__(
        self,
        user_id: str,
        email: str,
        name: str,
        role: str = "admin"
    ) -> None:
        self.user_id = user_id
        self.email = email
        self.name = name
        self.role = role
        self.created_at = datetime.now(timezone.utc)


@pytest.fixture
def browser_context():
    """Create mock browser context fixture."""
    return MockBrowserContext()


@pytest.fixture
async def authenticated_session(browser_context):
    """Create authenticated session fixture."""
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    await browser_context.set_cookie("session_id", session_id)
    await browser_context.set_storage("auth_token", f"token_{uuid.uuid4().hex[:16]}")
    yield browser_context
    await browser_context.clear_cookies()


@pytest.fixture
def test_user():
    """Create test user fixture."""
    return TestUser(
        user_id=f"u_{uuid.uuid4().hex[:8]}",
        email="test@example.com",
        name="Test User",
        role="admin",
    )


@pytest.fixture
def mock_paddle():
    """Create mock Paddle client fixture."""
    return MockPaddleClient()


@pytest.fixture
def screenshot_on_failure(request):
    """Fixture for taking screenshot on failure."""
    screenshots = []

    def take_screenshot(name: str) -> None:
        screenshots.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    yield take_screenshot

    # Take screenshot on failure
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        take_screenshot(f"failure_{request.node.name}")


@pytest.fixture
def video_recording():
    """Fixture for video recording."""
    recordings = []

    def start_recording(name: str) -> None:
        recordings.append({
            "name": name,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

    def stop_recording() -> None:
        if recordings:
            recordings[-1]["stopped_at"] = datetime.now(timezone.utc).isoformat()

    yield {"start": start_recording, "stop": stop_recording, "recordings": recordings}


@pytest.fixture
def trace_on_failure(request):
    """Fixture for tracing on failure."""
    traces = []

    def start_trace(name: str) -> None:
        traces.append({
            "name": name,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

    def stop_trace() -> None:
        if traces:
            traces[-1]["stopped_at"] = datetime.now(timezone.utc).isoformat()

    yield {"start": start_trace, "stop": stop_trace, "traces": traces}


@pytest.fixture
def e2e_settings():
    """E2E test settings."""
    return {
        "base_url": "http://localhost:3000",
        "api_url": "http://localhost:8000",
        "timeout": 30000,
        "slow_mo": 0,
        "headless": True,
    }


# Pytest hooks
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to get test result for screenshot on failure."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
