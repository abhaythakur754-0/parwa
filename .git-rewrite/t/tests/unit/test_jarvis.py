"""
Unit tests for Jarvis API.
Uses mocked database sessions - no Docker required.
"""
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Set environment variables before imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "agent@example.com"
    user.company_id = uuid.uuid4()
    user.role = MagicMock()
    user.role.value = "admin"
    user.is_active = True
    return user


def create_test_app():
    """Create a FastAPI test app with jarvis router."""
    app = FastAPI()

    async def override_get_db():
        return AsyncMock()

    from backend.app.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db

    from backend.api.jarvis import router
    app.include_router(router)

    return app


class TestJarvisEndpoints:
    """Tests for Jarvis API endpoints."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        from backend.api.jarvis import router
        assert router.prefix == "/jarvis"

    def test_router_tags(self):
        """Test that router has correct tags."""
        from backend.api.jarvis import router
        assert "Jarvis" in router.tags

    def test_command_request_schema(self):
        """Test JarvisCommandRequest schema validation."""
        from backend.api.jarvis import JarvisCommandRequest
        from pydantic import ValidationError

        # Valid request
        valid = JarvisCommandRequest(command="Analyze customer sentiment")
        assert valid.command == "Analyze customer sentiment"

        # Missing command
        with pytest.raises(ValidationError):
            JarvisCommandRequest()

        # Empty command
        with pytest.raises(ValidationError):
            JarvisCommandRequest(command="")

    def test_command_request_with_context(self):
        """Test JarvisCommandRequest with context."""
        from backend.api.jarvis import JarvisCommandRequest

        request = JarvisCommandRequest(
            command="Process refund",
            context={"ticket_id": str(uuid.uuid4()), "amount": 99.99}
        )
        assert request.context is not None

    def test_jarvis_response_schema(self):
        """Test JarvisResponse schema."""
        from backend.api.jarvis import JarvisResponse

        response = JarvisResponse(
            command_id=uuid.uuid4(),
            status="accepted",
            message="Command accepted",
            created_at=datetime.now(timezone.utc)
        )
        assert response.status == "accepted"

    def test_status_response_schema(self):
        """Test JarvisStatusResponse schema."""
        from backend.api.jarvis import JarvisStatusResponse

        response = JarvisStatusResponse(
            status="operational",
            version="1.0.0",
            uptime_seconds=86400,
            active_commands=5
        )
        assert response.status == "operational"
        assert response.version == "1.0.0"

    def test_pending_approvals_response_schema(self):
        """Test PendingApprovalsResponse schema."""
        from backend.api.jarvis import PendingApprovalsResponse

        response = PendingApprovalsResponse(
            approvals=[{"id": str(uuid.uuid4()), "action": "refund"}],
            total=1
        )
        assert response.total == 1
        assert len(response.approvals) == 1


class TestEndpointsWithoutAuth:
    """Tests for endpoints without authentication."""

    def test_execute_command_requires_auth(self):
        """Test that execute command requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/jarvis/command",
                json={"command": "test"}
            )

        assert response.status_code in [401, 403]

    def test_get_status_requires_auth(self):
        """Test that get status requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/jarvis/status")

        assert response.status_code in [401, 403]

    def test_get_pending_approvals_requires_auth(self):
        """Test that get pending approvals requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/jarvis/pending-approvals")

        assert response.status_code in [401, 403]

    def test_approve_requires_auth(self):
        """Test that approve requires authentication."""
        app = create_test_app()
        approval_id = uuid.uuid4()

        with TestClient(app) as client:
            response = client.post(f"/jarvis/pending-approvals/{approval_id}/approve")

        assert response.status_code in [401, 403, 422]

    def test_reject_requires_auth(self):
        """Test that reject requires authentication."""
        app = create_test_app()
        approval_id = uuid.uuid4()

        with TestClient(app) as client:
            response = client.post(f"/jarvis/pending-approvals/{approval_id}/reject")

        assert response.status_code in [401, 403, 422]


class TestInvalidUUIDHandling:
    """Tests for invalid UUID handling."""

    def test_approve_invalid_uuid(self):
        """Test approve with invalid UUID."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post("/jarvis/pending-approvals/not-a-uuid/approve")

        assert response.status_code in [401, 403, 422]

    def test_reject_invalid_uuid(self):
        """Test reject with invalid UUID."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post("/jarvis/pending-approvals/not-a-uuid/reject")

        assert response.status_code in [401, 403, 422]


class TestCommandValidation:
    """Tests for command validation."""

    def test_command_too_long(self):
        """Test command with max length validation."""
        from backend.api.jarvis import JarvisCommandRequest
        from pydantic import ValidationError

        # Command too long (max is 1000)
        with pytest.raises(ValidationError):
            JarvisCommandRequest(command="x" * 1001)

    def test_command_exactly_max_length(self):
        """Test command at max length is valid."""
        from backend.api.jarvis import JarvisCommandRequest

        # Command at max length (1000) should be valid
        valid = JarvisCommandRequest(command="x" * 1000)
        assert len(valid.command) == 1000


class TestSchemaFields:
    """Tests for schema field validation."""

    def test_jarvis_response_with_result(self):
        """Test JarvisResponse with optional result."""
        from backend.api.jarvis import JarvisResponse

        response = JarvisResponse(
            command_id=uuid.uuid4(),
            status="completed",
            message="Command completed",
            result={"output": "success", "data": [1, 2, 3]},
            created_at=datetime.now(timezone.utc)
        )
        assert response.result is not None
        assert response.result["output"] == "success"

    def test_jarvis_response_without_result(self):
        """Test JarvisResponse without optional result."""
        from backend.api.jarvis import JarvisResponse

        response = JarvisResponse(
            command_id=uuid.uuid4(),
            status="accepted",
            message="Command accepted",
            created_at=datetime.now(timezone.utc)
        )
        assert response.result is None

    def test_pending_approvals_empty_list(self):
        """Test PendingApprovalsResponse with empty list."""
        from backend.api.jarvis import PendingApprovalsResponse

        response = PendingApprovalsResponse(approvals=[], total=0)
        assert response.total == 0
        assert response.approvals == []

    def test_pending_approvals_multiple_items(self):
        """Test PendingApprovalsResponse with multiple items."""
        from backend.api.jarvis import PendingApprovalsResponse

        approvals = [
            {"id": str(uuid.uuid4()), "action": "refund", "amount": 50.00},
            {"id": str(uuid.uuid4()), "action": "escalate", "ticket_id": str(uuid.uuid4())},
            {"id": str(uuid.uuid4()), "action": "discount", "percentage": 10}
        ]

        response = PendingApprovalsResponse(approvals=approvals, total=3)
        assert response.total == 3
        assert len(response.approvals) == 3
