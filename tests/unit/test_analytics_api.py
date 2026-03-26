"""
Unit tests for PARWA Analytics API.
Tests cover stats, ticket metrics, response time, agent performance, activity feed, and SLA compliance endpoints.
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
        "email": "analytics_test@example.com",
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
    from backend.api.analytics import router
    app.include_router(router)

    # Override the dependency
    from backend.app.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# --- Tests ---

class TestAnalyticsEndpointsAuthRequired:
    """Test analytics endpoints require authentication."""

    def test_stats_missing_auth(self, client):
        """Test stats endpoint without auth returns 401 or 403."""
        response = client.get("/analytics/stats")
        assert response.status_code in (401, 403)

    def test_ticket_metrics_missing_auth(self, client):
        """Test ticket metrics endpoint without auth returns 401 or 403."""
        response = client.get("/analytics/metrics/tickets")
        assert response.status_code in (401, 403)

    def test_response_time_missing_auth(self, client):
        """Test response time endpoint without auth returns 401 or 403."""
        response = client.get("/analytics/metrics/response-time")
        assert response.status_code in (401, 403)

    def test_agent_performance_missing_auth(self, client):
        """Test agent performance endpoint without auth returns 401 or 403."""
        response = client.get("/analytics/metrics/agent-performance")
        assert response.status_code in (401, 403)

    def test_activity_feed_missing_auth(self, client):
        """Test activity feed endpoint without auth returns 401 or 403."""
        response = client.get("/analytics/activity-feed")
        assert response.status_code in (401, 403)

    def test_sla_compliance_missing_auth(self, client):
        """Test SLA compliance endpoint without auth returns 401 or 403."""
        response = client.get("/analytics/sla-compliance")
        assert response.status_code in (401, 403)


class TestAnalyticsInputValidation:
    """Test analytics endpoint input validation - auth runs first."""

    def test_ticket_metrics_valid_group_by(self, client):
        """Test ticket metrics accepts valid group_by parameter."""
        # Will fail auth, but validation params are accepted
        response = client.get("/analytics/metrics/tickets?group_by=day")
        assert response.status_code in (401, 403)  # Auth runs first

    def test_ticket_metrics_valid_group_by_week(self, client):
        """Test ticket metrics accepts week grouping."""
        response = client.get("/analytics/metrics/tickets?group_by=week")
        assert response.status_code in (401, 403)

    def test_ticket_metrics_valid_group_by_month(self, client):
        """Test ticket metrics accepts month grouping."""
        response = client.get("/analytics/metrics/tickets?group_by=month")
        assert response.status_code in (401, 403)

    def test_activity_feed_valid_pagination(self, client):
        """Test activity feed accepts valid pagination."""
        response = client.get("/analytics/activity-feed?limit=10&offset=0")
        assert response.status_code in (401, 403)

    def test_activity_feed_valid_activity_types(self, client):
        """Test activity feed accepts activity types filter."""
        response = client.get("/analytics/activity-feed?activity_types=ticket_created,ticket_resolved")
        assert response.status_code in (401, 403)


class TestAnalyticsStatsWithAuth:
    """Test analytics stats endpoint with authentication."""

    @patch("backend.api.analytics.decode_access_token")
    def test_get_stats_success(
        self,
        mock_decode_token,
        mock_db,
        mock_user_dict
    ):
        """Test stats endpoint returns company stats."""
        from fastapi import FastAPI
        from backend.api.analytics import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.return_value = mock_user_result

        # Mock AnalyticsService.get_company_stats
        with patch("backend.api.analytics.AnalyticsService") as MockService:
            mock_service_instance = MagicMock()
            mock_service_instance.get_company_stats = AsyncMock(return_value={
                "total_tickets": 100,
                "open_tickets": 25,
                "resolved_tickets": 75,
                "avg_response_time": 4.5,
                "sla_compliance_rate": 95.5,
            })
            MockService.return_value = mock_service_instance

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db] = lambda: mock_db

            with TestClient(app) as client:
                response = client.get(
                    "/analytics/stats",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["total_tickets"] == 100
            assert data["open_tickets"] == 25
            assert data["resolved_tickets"] == 75
            assert data["avg_response_time"] == 4.5
            assert data["sla_compliance_rate"] == 95.5


class TestTicketMetricsWithAuth:
    """Test ticket metrics endpoint with authentication."""

    @patch("backend.api.analytics.decode_access_token")
    def test_get_ticket_metrics_success(
        self,
        mock_decode_token,
        mock_db,
        mock_user_dict
    ):
        """Test ticket metrics endpoint returns metrics."""
        from fastapi import FastAPI
        from backend.api.analytics import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.return_value = mock_user_result

        # Mock AnalyticsService.get_ticket_metrics
        with patch("backend.api.analytics.AnalyticsService") as MockService:
            mock_service_instance = MagicMock()
            mock_service_instance.get_ticket_metrics = AsyncMock(return_value=[
                {
                    "date": "2024-01-15T00:00:00",
                    "tickets_created": 10,
                    "tickets_resolved": 8,
                    "avg_resolution_time": 2.5,
                },
                {
                    "date": "2024-01-14T00:00:00",
                    "tickets_created": 15,
                    "tickets_resolved": 12,
                    "avg_resolution_time": 3.0,
                },
            ])
            MockService.return_value = mock_service_instance

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db] = lambda: mock_db

            with TestClient(app) as client:
                response = client.get(
                    "/analytics/metrics/tickets",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data["metrics"]) == 2
            assert data["group_by"] == "day"
            assert data["metrics"][0]["tickets_created"] == 10

    @patch("backend.api.analytics.decode_access_token")
    def test_get_ticket_metrics_invalid_group_by(
        self,
        mock_decode_token,
        mock_db,
        mock_user_dict
    ):
        """Test ticket metrics with invalid group_by returns 400."""
        from fastapi import FastAPI
        from backend.api.analytics import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.return_value = mock_user_result

        with patch("backend.api.analytics.AnalyticsService") as MockService:
            mock_service_instance = MagicMock()
            MockService.return_value = mock_service_instance

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db] = lambda: mock_db

            with TestClient(app) as client:
                response = client.get(
                    "/analytics/metrics/tickets?group_by=invalid",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 400
            assert "group_by must be one of" in response.json()["detail"]


class TestResponseTimeWithAuth:
    """Test response time metrics endpoint with authentication."""

    @patch("backend.api.analytics.decode_access_token")
    def test_get_response_time_success(
        self,
        mock_decode_token,
        mock_db,
        mock_user_dict
    ):
        """Test response time endpoint returns metrics."""
        from fastapi import FastAPI
        from backend.api.analytics import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.return_value = mock_user_result

        # Mock AnalyticsService.get_response_time_metrics
        with patch("backend.api.analytics.AnalyticsService") as MockService:
            mock_service_instance = MagicMock()
            mock_service_instance.get_response_time_metrics = AsyncMock(return_value={
                "first_response_avg": 1.5,
                "resolution_time_avg": 4.2,
                "by_priority": {
                    "high": 2.0,
                    "medium": 4.2,
                    "low": 5.0,
                },
            })
            MockService.return_value = mock_service_instance

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db] = lambda: mock_db

            with TestClient(app) as client:
                response = client.get(
                    "/analytics/metrics/response-time",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["first_response_avg"] == 1.5
            assert data["resolution_time_avg"] == 4.2
            assert data["by_priority"]["high"] == 2.0


class TestAgentPerformanceWithAuth:
    """Test agent performance endpoint with authentication."""

    @patch("backend.api.analytics.decode_access_token")
    def test_get_agent_performance_success(
        self,
        mock_decode_token,
        mock_db,
        mock_user_dict
    ):
        """Test agent performance endpoint returns performance data."""
        from fastapi import FastAPI
        from backend.api.analytics import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.return_value = mock_user_result

        # Mock AnalyticsService.get_agent_performance
        with patch("backend.api.analytics.AnalyticsService") as MockService:
            mock_service_instance = MagicMock()
            mock_service_instance.get_agent_performance = AsyncMock(return_value=[
                {
                    "agent_id": str(uuid.uuid4()),
                    "agent_name": "agent@example.com",
                    "tickets_assigned": 50,
                    "tickets_resolved": 45,
                    "avg_resolution_time": 3.5,
                    "customer_satisfaction": 4.8,
                },
            ])
            MockService.return_value = mock_service_instance

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db] = lambda: mock_db

            with TestClient(app) as client:
                response = client.get(
                    "/analytics/metrics/agent-performance",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data["agents"]) == 1
            assert data["agents"][0]["agent_name"] == "agent@example.com"
            assert data["agents"][0]["tickets_assigned"] == 50

    @patch("backend.api.analytics.decode_access_token")
    def test_get_agent_performance_with_filter(
        self,
        mock_decode_token,
        mock_db,
        mock_user_dict
    ):
        """Test agent performance with agent_id filter."""
        from fastapi import FastAPI
        from backend.api.analytics import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload
        agent_uuid = uuid.uuid4()

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.return_value = mock_user_result

        # Mock AnalyticsService.get_agent_performance
        with patch("backend.api.analytics.AnalyticsService") as MockService:
            mock_service_instance = MagicMock()
            mock_service_instance.get_agent_performance = AsyncMock(return_value=[
                {
                    "agent_id": str(agent_uuid),
                    "agent_name": "specific@example.com",
                    "tickets_assigned": 20,
                    "tickets_resolved": 18,
                    "avg_resolution_time": 2.0,
                    "customer_satisfaction": 4.9,
                },
            ])
            MockService.return_value = mock_service_instance

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db] = lambda: mock_db

            with TestClient(app) as client:
                response = client.get(
                    f"/analytics/metrics/agent-performance?agent_id={agent_uuid}",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data["agents"]) == 1


class TestActivityFeedWithAuth:
    """Test activity feed endpoint with authentication."""

    @patch("backend.api.analytics.decode_access_token")
    def test_get_activity_feed_success(
        self,
        mock_decode_token,
        mock_db,
        mock_user_dict
    ):
        """Test activity feed endpoint returns activities."""
        from fastapi import FastAPI
        from backend.api.analytics import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.return_value = mock_user_result

        # Mock AnalyticsService.get_activity_feed
        with patch("backend.api.analytics.AnalyticsService") as MockService:
            mock_service_instance = MagicMock()
            mock_service_instance.get_activity_feed = AsyncMock(return_value=[
                {
                    "id": str(uuid.uuid4()),
                    "type": "ticket_created",
                    "description": "New ticket: Help needed",
                    "timestamp": "2024-01-15T10:30:00",
                    "user_id": str(uuid.uuid4()),
                    "metadata": {"status": "open", "channel": "email"},
                },
            ])
            MockService.return_value = mock_service_instance

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db] = lambda: mock_db

            with TestClient(app) as client:
                response = client.get(
                    "/analytics/activity-feed",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert len(data["activities"]) == 1
            assert data["activities"][0]["type"] == "ticket_created"

    @patch("backend.api.analytics.decode_access_token")
    def test_get_activity_feed_empty(
        self,
        mock_decode_token,
        mock_db,
        mock_user_dict
    ):
        """Test activity feed returns empty list when no activities."""
        from fastapi import FastAPI
        from backend.api.analytics import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.return_value = mock_user_result

        # Mock AnalyticsService.get_activity_feed
        with patch("backend.api.analytics.AnalyticsService") as MockService:
            mock_service_instance = MagicMock()
            mock_service_instance.get_activity_feed = AsyncMock(return_value=[])
            MockService.return_value = mock_service_instance

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db] = lambda: mock_db

            with TestClient(app) as client:
                response = client.get(
                    "/analytics/activity-feed",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["activities"] == []
            assert data["total"] == 0


class TestSLAComplianceWithAuth:
    """Test SLA compliance endpoint with authentication."""

    @patch("backend.api.analytics.decode_access_token")
    def test_get_sla_compliance_success(
        self,
        mock_decode_token,
        mock_db,
        mock_user_dict
    ):
        """Test SLA compliance endpoint returns metrics."""
        from fastapi import FastAPI
        from backend.api.analytics import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.return_value = mock_user_result

        # Mock AnalyticsService.calculate_sla_compliance
        with patch("backend.api.analytics.AnalyticsService") as MockService:
            mock_service_instance = MagicMock()
            mock_service_instance.calculate_sla_compliance = AsyncMock(return_value={
                "compliance_rate": 92.5,
                "total_tickets": 100,
                "breached_tickets": 8,
                "avg_time_to_breach": 5.2,
            })
            MockService.return_value = mock_service_instance

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db] = lambda: mock_db

            with TestClient(app) as client:
                response = client.get(
                    "/analytics/sla-compliance",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["compliance_rate"] == 92.5
            assert data["total_tickets"] == 100
            assert data["breached_tickets"] == 8
            assert data["avg_time_to_breach"] == 5.2


class TestDateFiltering:
    """Test date range filtering."""

    @patch("backend.api.analytics.decode_access_token")
    def test_stats_with_date_filter(
        self,
        mock_decode_token,
        mock_db,
        mock_user_dict
    ):
        """Test stats endpoint with date filtering."""
        from fastapi import FastAPI
        from backend.api.analytics import router
        from backend.app.dependencies import get_db

        valid_payload = {
            "sub": str(mock_user_dict["id"]),
            "email": mock_user_dict["email"],
            "role": mock_user_dict["role"],
            "company_id": str(mock_user_dict["company_id"]),
        }

        mock_decode_token.return_value = valid_payload

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = mock_user_dict["id"]
        mock_user.company_id = mock_user_dict["company_id"]
        mock_user.is_active = True

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute.return_value = mock_user_result

        with patch("backend.api.analytics.AnalyticsService") as MockService:
            mock_service_instance = MagicMock()
            mock_service_instance.get_company_stats = AsyncMock(return_value={
                "total_tickets": 50,
                "open_tickets": 10,
                "resolved_tickets": 40,
                "avg_response_time": 3.0,
                "sla_compliance_rate": 98.0,
            })
            MockService.return_value = mock_service_instance

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db] = lambda: mock_db

            start_date = "2024-01-01T00:00:00Z"
            end_date = "2024-12-31T23:59:59Z"

            with TestClient(app) as client:
                response = client.get(
                    f"/analytics/stats?start_date={start_date}&end_date={end_date}",
                    headers={"Authorization": "Bearer valid.token"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["total_tickets"] == 50


class TestRouterConfiguration:
    """Test router configuration."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        from backend.api.analytics import router
        assert router.prefix == "/analytics"

    def test_router_tags(self):
        """Test that router has correct tags."""
        from backend.api.analytics import router
        assert "Analytics" in router.tags


class TestSchemaValidation:
    """Test Pydantic schema validation."""

    def test_company_stats_response_schema(self):
        """Test CompanyStatsResponse schema."""
        from backend.api.analytics import CompanyStatsResponse

        response = CompanyStatsResponse(
            total_tickets=100,
            open_tickets=25,
            resolved_tickets=75,
            avg_response_time=4.5,
            sla_compliance_rate=95.5,
        )
        assert response.total_tickets == 100
        assert response.avg_response_time == 4.5

    def test_ticket_metric_item_schema(self):
        """Test TicketMetricItem schema."""
        from backend.api.analytics import TicketMetricItem

        item = TicketMetricItem(
            date="2024-01-15T00:00:00",
            tickets_created=10,
            tickets_resolved=8,
            avg_resolution_time=2.5,
        )
        assert item.tickets_created == 10

    def test_response_time_metrics_schema(self):
        """Test ResponseTimeMetricsResponse schema."""
        from backend.api.analytics import ResponseTimeMetricsResponse

        response = ResponseTimeMetricsResponse(
            first_response_avg=1.5,
            resolution_time_avg=4.2,
            by_priority={"high": 2.0, "medium": 4.2, "low": 5.0},
        )
        assert response.first_response_avg == 1.5
        assert response.by_priority["high"] == 2.0

    def test_agent_performance_item_schema(self):
        """Test AgentPerformanceItem schema."""
        from backend.api.analytics import AgentPerformanceItem

        item = AgentPerformanceItem(
            agent_id=str(uuid.uuid4()),
            agent_name="test@example.com",
            tickets_assigned=50,
            tickets_resolved=45,
            avg_resolution_time=3.5,
            customer_satisfaction=4.8,
        )
        assert item.agent_name == "test@example.com"
        assert item.customer_satisfaction == 4.8

    def test_activity_feed_item_schema(self):
        """Test ActivityFeedItem schema."""
        from backend.api.analytics import ActivityFeedItem

        item = ActivityFeedItem(
            id=str(uuid.uuid4()),
            type="ticket_created",
            description="New ticket created",
            timestamp="2024-01-15T10:00:00",
            user_id=str(uuid.uuid4()),
            metadata={"channel": "email"},
        )
        assert item.type == "ticket_created"

    def test_sla_compliance_response_schema(self):
        """Test SLAComplianceResponse schema."""
        from backend.api.analytics import SLAComplianceResponse

        response = SLAComplianceResponse(
            compliance_rate=92.5,
            total_tickets=100,
            breached_tickets=8,
            avg_time_to_breach=5.2,
        )
        assert response.compliance_rate == 92.5
        assert response.breached_tickets == 8
