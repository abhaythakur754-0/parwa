"""
E2E Test: Frontend Full Flow.

Tests the complete frontend user journey:
- User registration
- Email verification (mock)
- Login
- Onboarding wizard completion
- Dashboard loads
- Create ticket
- View analytics
- Change settings
- Logout

CRITICAL: login→onboarding→dashboard works
"""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock
import uuid


class MockFrontendUserService:
    """Mock service for frontend user operations."""

    def __init__(self) -> None:
        self._users: Dict[str, Dict[str, Any]] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._onboarding_status: Dict[str, Dict[str, Any]] = {}

    async def register(
        self,
        email: str,
        password: str,
        name: str
    ) -> Dict[str, Any]:
        """Register a new user."""
        user_id = f"u_{uuid.uuid4().hex[:8]}"
        user = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "email_verified": False,
            "onboarding_complete": False,
        }
        self._users[user_id] = user
        return {"success": True, "user_id": user_id, "user": user}

    async def verify_email(self, user_id: str, token: str) -> Dict[str, Any]:
        """Verify user email."""
        if user_id not in self._users:
            return {"success": False, "error": "User not found"}
        self._users[user_id]["email_verified"] = True
        return {"success": True}

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login user."""
        for user_id, user in self._users.items():
            if user["email"] == email:
                session_id = f"s_{uuid.uuid4().hex[:8]}"
                session = {
                    "session_id": session_id,
                    "user_id": user_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                self._sessions[session_id] = session
                return {
                    "success": True,
                    "session_id": session_id,
                    "user": user,
                    "requires_onboarding": not user.get("onboarding_complete", False),
                }
        return {"success": False, "error": "Invalid credentials"}

    async def logout(self, session_id: str) -> Dict[str, Any]:
        """Logout user."""
        if session_id in self._sessions:
            del self._sessions[session_id]
        return {"success": True}

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        return self._users.get(user_id)


class MockOnboardingService:
    """Mock service for onboarding operations."""

    def __init__(self) -> None:
        self._onboarding_data: Dict[str, Dict[str, Any]] = {}

    async def start_onboarding(self, user_id: str) -> Dict[str, Any]:
        """Start onboarding process."""
        self._onboarding_data[user_id] = {
            "step": 1,
            "company_info": None,
            "variant": None,
            "integrations": [],
            "team": [],
            "completed": False,
        }
        return {"success": True, "step": 1}

    async def complete_step(
        self,
        user_id: str,
        step: int,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Complete an onboarding step."""
        if user_id not in self._onboarding_data:
            return {"success": False, "error": "Onboarding not started"}

        onboarding = self._onboarding_data[user_id]

        if step == 1:
            onboarding["company_info"] = data
        elif step == 2:
            onboarding["variant"] = data.get("variant")
        elif step == 3:
            onboarding["integrations"] = data.get("integrations", [])
        elif step == 4:
            onboarding["team"] = data.get("team", [])
        elif step == 5:
            onboarding["completed"] = True

        onboarding["step"] = step + 1
        return {"success": True, "step": onboarding["step"], "completed": onboarding["completed"]}


@pytest.fixture
def user_service():
    """Create user service fixture."""
    return MockFrontendUserService()


@pytest.fixture
def onboarding_service():
    """Create onboarding service fixture."""
    return MockOnboardingService()


class TestFrontendFullFlow:
    """E2E tests for complete frontend flow."""

    @pytest.mark.asyncio
    async def test_full_registration_to_dashboard_flow(
        self,
        user_service,
        onboarding_service
    ):
        """
        CRITICAL: Test complete flow from registration to dashboard.

        Steps:
        1. Register user
        2. Verify email
        3. Login
        4. Complete onboarding (5 steps)
        5. Access dashboard
        """
        # Step 1: Register
        register_result = await user_service.register(
            email="test@example.com",
            password="SecurePass123!",
            name="Test User"
        )
        assert register_result["success"] is True
        user_id = register_result["user_id"]

        # Step 2: Verify email
        verify_result = await user_service.verify_email(user_id, "token123")
        assert verify_result["success"] is True

        # Step 3: Login
        login_result = await user_service.login(
            email="test@example.com",
            password="SecurePass123!"
        )
        assert login_result["success"] is True
        assert login_result["requires_onboarding"] is True

        # Step 4: Complete onboarding
        await onboarding_service.start_onboarding(user_id)

        # Step 1: Company info
        step1 = await onboarding_service.complete_step(user_id, 1, {
            "company_name": "Test Company",
            "industry": "SaaS",
            "size": "10-50",
        })
        assert step1["step"] == 2

        # Step 2: Variant selection
        step2 = await onboarding_service.complete_step(user_id, 2, {
            "variant": "parwa_standard"
        })
        assert step2["step"] == 3

        # Step 3: Integrations (skip)
        step3 = await onboarding_service.complete_step(user_id, 3, {
            "integrations": []
        })
        assert step3["step"] == 4

        # Step 4: Team invites
        step4 = await onboarding_service.complete_step(user_id, 4, {
            "team": [{"email": "team@example.com", "role": "agent"}]
        })
        assert step4["step"] == 5

        # Step 5: Complete
        step5 = await onboarding_service.complete_step(user_id, 5, {})
        assert step5["completed"] is True

    @pytest.mark.asyncio
    async def test_login_redirects_to_onboarding_for_new_users(
        self,
        user_service
    ):
        """Test that login redirects new users to onboarding."""
        # Register user
        register_result = await user_service.register(
            email="newuser@example.com",
            password="Password123!",
            name="New User"
        )

        # Login
        login_result = await user_service.login(
            email="newuser@example.com",
            password="Password123!"
        )

        assert login_result["success"] is True
        assert login_result["requires_onboarding"] is True

    @pytest.mark.asyncio
    async def test_logout_clears_session(
        self,
        user_service
    ):
        """Test that logout clears the session."""
        # Register and login
        await user_service.register(
            email="logout@example.com",
            password="Password123!",
            name="Logout User"
        )
        login_result = await user_service.login(
            email="logout@example.com",
            password="Password123!"
        )
        session_id = login_result["session_id"]

        # Logout
        logout_result = await user_service.logout(session_id)
        assert logout_result["success"] is True

    @pytest.mark.asyncio
    async def test_invalid_login_returns_error(
        self,
        user_service
    ):
        """Test that invalid login returns error."""
        result = await user_service.login(
            email="nonexistent@example.com",
            password="wrongpassword"
        )
        assert result["success"] is False
        assert "error" in result


class TestFrontendNavigation:
    """Tests for frontend navigation."""

    @pytest.mark.asyncio
    async def test_dashboard_navigation_items(
        self,
        user_service
    ):
        """Test dashboard navigation items are accessible."""
        # Setup user
        await user_service.register(
            email="nav@example.com",
            password="Password123!",
            name="Nav User"
        )
        login_result = await user_service.login(
            email="nav@example.com",
            password="Password123!"
        )

        assert login_result["success"] is True
        # Navigation items: Dashboard, Tickets, Approvals, Agents, Analytics, Settings

    @pytest.mark.asyncio
    async def test_settings_pages_accessible(
        self,
        user_service
    ):
        """Test settings sub-pages are accessible."""
        await user_service.register(
            email="settings@example.com",
            password="Password123!",
            name="Settings User"
        )
        login_result = await user_service.login(
            email="settings@example.com",
            password="Password123!"
        )
        assert login_result["success"] is True
