"""
Unit tests for PARWA Dashboard API.
Tests cover stats, activity feed, metrics, ticket summary, and team performance endpoints.
Uses FastAPI dependency injection for mocking database and services.
"""
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Set environment before imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-characters-for-testing!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "development")


# --- Fixtures ---

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_user_dict():
    """Create mock user data."""
    return {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "password_hash": "$2b$12$test_hash",
        "role": "viewer",
        "company_id": uuid.uuid4(),
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    app = FastAPI()

    # Mock get_db dependency
    async def override_get_db():
        yield AsyncMock()

    # Import and include router
    from backend.api.dashboard import router
    app.include_router(router)

    # Override the dependency
    from backend.app.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# --- Tests ---

class TestDashboardEndpointsAuthRequired:
    """Test dashboard endpoints require authentication."""

    def test_stats_missing_auth(self, client):
        """Test stats endpoint without auth returns 401 or 403."""
        response = client.get("/dashboard/stats")
        assert response.status_code in (401, 403)

    def test_activity_missing_auth(self, client):
        """Test activity endpoint without auth returns 401 or 403."""
        response = client.get("/dashboard/activity")
        assert response.status_code in (401, 403)

    def test_metrics_missing_auth(self, client):
        """Test metrics endpoint without auth returns 401 or 403."""
        response = client.get("/dashboard/metrics")
        assert response.status_code in (401, 403)

    def test_ticket_summary_missing_auth(self, client):
        """Test ticket summary endpoint without auth returns 401 or 403."""
        response = client.get("/dashboard/tickets/summary")
        assert response.status_code in (401, 403)

    def test_team_performance_missing_auth(self, client):
        """Test team performance endpoint without auth returns 401 or 403."""
        response = client.get("/dashboard/team/performance")
        assert response.status_code in (401, 403)


class TestDashboardInputValidation:
    """Test dashboard endpoint input validation - auth runs first."""

    def test_activity_valid_pagination_params(self, client):
        """Test activity endpoint accepts valid pagination parameters."""
        # Will fail auth, but validation params are accepted
        response = client.get("/dashboard/activity?page=1&page_size=50")
        assert response.status_code in (401, 403)  # Auth runs first

    def test_activity_valid_date_filter(self, client):
        """Test activity endpoint accepts valid date filter parameters."""
        response = client.get("/dashboard/activity?start_date=2024-01-01T00:00:00Z&end_date=2024-12-31T23:59:59Z")
        assert response.status_code in (401, 403)  # Auth runs first


class TestDashboardStatsWithAuth:
    """Test dashboard stats endpoint with authentication."""

    @patch("backend.api.dashboard.is_token_blacklisted")
    @patch("backend.api.dashboard.decode_access_token")
    def test_get_stats_company_not_found(
        self,
        mock_decode_token,
        mock_is_blacklisted,
        mock_db,
        mock_user_dict
    ):
        """Test stats when company not found returns 404."""
        from fastapi import FastAPI
        from backend.api.dashboard import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload
        mock_is_blacklisted.return_value = False

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        # First call: user lookup, Second call: company lookup (returns None)
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user
        
        mock_company_result = MagicMock()
        mock_company_result.scalar_one_or_none.return_value = None
        
        mock_db.execute.side_effect = [mock_user_result, mock_company_result]

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as client:
            response = client.get(
                "/dashboard/stats",
                headers={"Authorization": "Bearer valid.token"}
            )

        assert response.status_code == 404


class TestActivityFeedWithAuth:
    """Test activity feed endpoint with authentication."""

    @patch("backend.api.dashboard.is_token_blacklisted")
    @patch("backend.api.dashboard.decode_access_token")
    def test_get_activity_empty_result(
        self,
        mock_decode_token,
        mock_is_blacklisted,
        mock_db,
        mock_user_dict
    ):
        """Test activity feed returns empty list when no tickets."""
        from fastapi import FastAPI
        from backend.api.dashboard import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload
        mock_is_blacklisted.return_value = False

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        # Setup mock_db - return user, then empty tickets
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user
        
        mock_tickets_result = MagicMock()
        mock_tickets_result.scalars.return_value.all.return_value = []
        
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_db.execute.side_effect = [mock_user_result, mock_tickets_result, mock_count_result]

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as client:
            response = client.get(
                "/dashboard/activity",
                headers={"Authorization": "Bearer valid.token"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total_count"] == 0


class TestKPIMetricsWithAuth:
    """Test KPI metrics endpoint with authentication."""

    @patch("backend.api.dashboard.is_token_blacklisted")
    @patch("backend.api.dashboard.decode_access_token")
    def test_get_metrics_empty_data(
        self,
        mock_decode_token,
        mock_is_blacklisted,
        mock_db,
        mock_user_dict
    ):
        """Test KPI metrics returns zeros when no data."""
        from fastapi import FastAPI
        from backend.api.dashboard import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload
        mock_is_blacklisted.return_value = False

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        # Setup mock results
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user
        
        # No tickets
        mock_counts_result = MagicMock()
        mock_counts_result.first.return_value = MagicMock(total=0, resolved=0)
        
        mock_resolution_result = MagicMock()
        mock_resolution_result.first.return_value = MagicMock(avg_hours=None)
        
        mock_sentiment_result = MagicMock()
        mock_sentiment_result.__iter__ = lambda self: iter([])
        
        mock_ai_result = MagicMock()
        mock_ai_result.scalar.return_value = None

        mock_db.execute.side_effect = [
            mock_user_result,
            mock_counts_result,
            mock_resolution_result,
            mock_sentiment_result,
            mock_ai_result
        ]

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as client:
            response = client.get(
                "/dashboard/metrics",
                headers={"Authorization": "Bearer valid.token"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["resolution_rate"] == 0.0


class TestTicketSummaryWithAuth:
    """Test ticket summary endpoint with authentication."""

    @patch("backend.api.dashboard.is_token_blacklisted")
    @patch("backend.api.dashboard.decode_access_token")
    def test_get_summary_empty_data(
        self,
        mock_decode_token,
        mock_is_blacklisted,
        mock_db,
        mock_user_dict
    ):
        """Test ticket summary returns empty dicts when no data."""
        from fastapi import FastAPI
        from backend.api.dashboard import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload
        mock_is_blacklisted.return_value = False

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        # Setup mock results
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user
        
        mock_status_result = MagicMock()
        mock_status_result.__iter__ = lambda self: iter([])
        
        mock_sentiment_result = MagicMock()
        mock_sentiment_result.__iter__ = lambda self: iter([])
        
        mock_channel_result = MagicMock()
        mock_channel_result.__iter__ = lambda self: iter([])

        mock_db.execute.side_effect = [
            mock_user_result,
            mock_status_result,
            mock_sentiment_result,
            mock_channel_result
        ]

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as client:
            response = client.get(
                "/dashboard/tickets/summary",
                headers={"Authorization": "Bearer valid.token"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["by_status"] == {}
        assert data["by_sentiment"] == {}
        assert data["by_channel"] == {}


class TestTeamPerformanceWithAuth:
    """Test team performance endpoint with authentication."""

    @patch("backend.api.dashboard.is_token_blacklisted")
    @patch("backend.api.dashboard.decode_access_token")
    def test_get_team_performance_empty(
        self,
        mock_decode_token,
        mock_is_blacklisted,
        mock_db,
        mock_user_dict
    ):
        """Test team performance returns empty list when no team."""
        from fastapi import FastAPI
        from backend.api.dashboard import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload
        mock_is_blacklisted.return_value = False

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        # Setup mock results
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user
        
        mock_users_result = MagicMock()
        mock_users_result.scalars.return_value.all.return_value = []
        
        mock_assigned_result = MagicMock()
        mock_assigned_result.__iter__ = lambda self: iter([])
        
        mock_resolved_result = MagicMock()
        mock_resolved_result.__iter__ = lambda self: iter([])
        
        mock_resolution_result = MagicMock()
        mock_resolution_result.__iter__ = lambda self: iter([])

        mock_db.execute.side_effect = [
            mock_user_result,
            mock_users_result,
            mock_assigned_result,
            mock_resolved_result,
            mock_resolution_result
        ]

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as client:
            response = client.get(
                "/dashboard/team/performance",
                headers={"Authorization": "Bearer valid.token"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["team_members"] == []
        assert data["team_resolution_rate"] == 0.0


class TestDateFiltering:
    """Test date range filtering."""

    @patch("backend.api.dashboard.is_token_blacklisted")
    @patch("backend.api.dashboard.decode_access_token")
    def test_activity_with_date_filter(
        self,
        mock_decode_token,
        mock_is_blacklisted,
        mock_db,
        mock_user_dict
    ):
        """Test activity feed with date filtering."""
        from fastapi import FastAPI
        from backend.api.dashboard import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload
        mock_is_blacklisted.return_value = False

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user
        
        mock_tickets_result = MagicMock()
        mock_tickets_result.scalars.return_value.all.return_value = []
        
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_db.execute.side_effect = [mock_user_result, mock_tickets_result, mock_count_result]

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: mock_db

        start_date = "2024-01-01T00:00:00Z"
        end_date = "2024-12-31T23:59:59Z"

        with TestClient(app) as client:
            response = client.get(
                f"/dashboard/activity?start_date={start_date}&end_date={end_date}",
                headers={"Authorization": "Bearer valid.token"}
            )

        assert response.status_code == 200


# --- Helper Function Tests ---

@pytest.mark.asyncio
async def test_is_token_blacklisted_helper():
    """Test is_token_blacklisted helper function."""
    with patch("shared.utils.cache.Cache") as mock_cache_class:
        mock_cache = AsyncMock()
        mock_cache.exists.return_value = True
        mock_cache.close = AsyncMock()
        mock_cache_class.return_value = mock_cache

        from backend.api.dashboard import is_token_blacklisted
        result = await is_token_blacklisted("blacklisted.token")

        assert result is True
        mock_cache.exists.assert_called_once()


@pytest.mark.asyncio
async def test_is_token_blacklisted_error():
    """Test is_token_blacklisted handles errors gracefully."""
    with patch("shared.utils.cache.Cache") as mock_cache_class:
        mock_cache = AsyncMock()
        mock_cache.exists.side_effect = Exception("Redis error")
        mock_cache.close = AsyncMock()
        mock_cache_class.return_value = mock_cache

        from backend.api.dashboard import is_token_blacklisted
        result = await is_token_blacklisted("any.token")

        # Should return False on error (fail open)
        assert result is False
