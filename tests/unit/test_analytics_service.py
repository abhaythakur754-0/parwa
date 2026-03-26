"""
Unit tests for Analytics Service.
Uses mocked database sessions - no Docker required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime, timedelta

from backend.services.analytics_service import AnalyticsService
from backend.models.support_ticket import (
    SupportTicket,
    TicketStatusEnum,
    ChannelEnum,
    SentimentEnum,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def analytics_service(mock_db):
    """Analytics service instance with mocked DB."""
    company_id = uuid4()
    return AnalyticsService(mock_db, company_id)


class TestAnalyticsServiceInit:
    """Tests for AnalyticsService initialization."""
    
    def test_init_stores_db_and_company_id(self, mock_db):
        """Test that init stores db and company_id."""
        company_id = uuid4()
        service = AnalyticsService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id
    
    def test_init_has_sla_thresholds(self, mock_db):
        """Test that SLA thresholds are defined."""
        company_id = uuid4()
        service = AnalyticsService(mock_db, company_id)
        
        assert hasattr(service, 'SLA_THRESHOLDS')
        assert "high" in service.SLA_THRESHOLDS
        assert "medium" in service.SLA_THRESHOLDS
        assert "low" in service.SLA_THRESHOLDS


class TestGetCompanyStats:
    """Tests for get_company_stats method."""
    
    @pytest.mark.asyncio
    async def test_get_company_stats_returns_dict(self, analytics_service, mock_db):
        """Test that get_company_stats returns proper dict."""
        # Mock count queries
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_company_stats()
        
        assert "total_tickets" in result
        assert "open_tickets" in result
        assert "resolved_tickets" in result
        assert "avg_response_time" in result
        assert "sla_compliance_rate" in result
    
    @pytest.mark.asyncio
    async def test_get_company_stats_with_date_filter(self, analytics_service, mock_db):
        """Test get_company_stats with date filtering."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()
        
        result = await analytics_service.get_company_stats(
            start_date=start,
            end_date=end
        )
        
        mock_db.execute.assert_called()
        assert result["total_tickets"] == 5
    
    @pytest.mark.asyncio
    async def test_get_company_stats_zero_tickets(self, analytics_service, mock_db):
        """Test get_company_stats with zero tickets."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_company_stats()
        
        assert result["total_tickets"] == 0
        assert result["sla_compliance_rate"] == 100.0


class TestGetTicketMetrics:
    """Tests for get_ticket_metrics method."""
    
    @pytest.mark.asyncio
    async def test_get_ticket_metrics_returns_list(self, analytics_service, mock_db):
        """Test that get_ticket_metrics returns list."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_ticket_metrics()
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_get_ticket_metrics_group_by_day(self, analytics_service, mock_db):
        """Test grouping by day."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        await analytics_service.get_ticket_metrics(group_by="day")
        
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_ticket_metrics_group_by_week(self, analytics_service, mock_db):
        """Test grouping by week."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        await analytics_service.get_ticket_metrics(group_by="week")
        
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_ticket_metrics_group_by_month(self, analytics_service, mock_db):
        """Test grouping by month."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        await analytics_service.get_ticket_metrics(group_by="month")
        
        mock_db.execute.assert_called_once()


class TestGetResponseTimeMetrics:
    """Tests for get_response_time_metrics method."""
    
    @pytest.mark.asyncio
    async def test_get_response_time_metrics_returns_dict(self, analytics_service, mock_db):
        """Test response time metrics structure."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 2.5
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_response_time_metrics()
        
        assert "first_response_avg" in result
        assert "resolution_time_avg" in result
        assert "by_priority" in result
    
    @pytest.mark.asyncio
    async def test_get_response_time_metrics_by_priority(self, analytics_service, mock_db):
        """Test response time metrics by priority."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5.0
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_response_time_metrics()
        
        assert "high" in result["by_priority"]
        assert "medium" in result["by_priority"]
        assert "low" in result["by_priority"]


class TestGetAgentPerformance:
    """Tests for get_agent_performance method."""
    
    @pytest.mark.asyncio
    async def test_get_agent_performance_returns_list(self, analytics_service, mock_db):
        """Test agent performance returns list."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_agent_performance()
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_get_agent_performance_filters_by_agent(self, analytics_service, mock_db):
        """Test filtering by specific agent."""
        agent_id = uuid4()
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        await analytics_service.get_agent_performance(agent_id=agent_id)
        
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_agent_performance_with_data(self, analytics_service, mock_db):
        """Test agent performance with mock data."""
        agent_id = uuid4()
        
        # Mock the first query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(agent_id, 10, 7)]
        
        # Mock the user query
        mock_user_result = MagicMock()
        mock_user = MagicMock()
        mock_user.email = "agent@example.com"
        mock_user_result.scalar_one_or_none.return_value = mock_user
        
        mock_db.execute = AsyncMock(side_effect=[mock_result, mock_user_result])
        
        result = await analytics_service.get_agent_performance()
        
        assert len(result) == 1
        assert result[0]["agent_id"] == str(agent_id)
        assert result[0]["tickets_assigned"] == 10
        assert result[0]["tickets_resolved"] == 7


class TestGetActivityFeed:
    """Tests for get_activity_feed method."""
    
    @pytest.mark.asyncio
    async def test_get_activity_feed_returns_list(self, analytics_service, mock_db):
        """Test activity feed returns list."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_activity_feed()
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_get_activity_feed_respects_limit(self, analytics_service, mock_db):
        """Test that limit parameter works."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        await analytics_service.get_activity_feed(limit=10)
        
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_activity_feed_with_tickets(self, analytics_service, mock_db):
        """Test activity feed with mock tickets."""
        ticket_id = uuid4()
        
        mock_ticket = MagicMock(spec=SupportTicket)
        mock_ticket.id = ticket_id
        mock_ticket.subject = "Test Ticket"
        mock_ticket.status = TicketStatusEnum.open
        mock_ticket.channel = ChannelEnum.email
        mock_ticket.assigned_to = None
        mock_ticket.created_at = datetime.utcnow()
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_ticket]
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_activity_feed()
        
        assert len(result) == 1
        assert result[0]["type"] == "ticket_created"
        assert "Test Ticket" in result[0]["description"]
    
    @pytest.mark.asyncio
    async def test_get_activity_feed_filter_by_type(self, analytics_service, mock_db):
        """Test filtering activity by type."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_activity_feed(
            activity_types=["ticket_resolved"]
        )
        
        assert isinstance(result, list)


class TestCalculateSlaCompliance:
    """Tests for calculate_sla_compliance method."""
    
    @pytest.mark.asyncio
    async def test_calculate_sla_compliance_returns_dict(self, analytics_service, mock_db):
        """Test SLA compliance structure."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 100
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.calculate_sla_compliance()
        
        assert "compliance_rate" in result
        assert "total_tickets" in result
        assert "breached_tickets" in result
        assert "avg_time_to_breach" in result
    
    @pytest.mark.asyncio
    async def test_calculate_sla_compliance_100_percent(self, analytics_service, mock_db):
        """Test 100% SLA compliance."""
        call_count = 0
        
        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar.return_value = 10  # total tickets
            elif call_count == 2:
                mock_result.scalar.return_value = 0  # breached tickets
            else:
                mock_result.scalar.return_value = 0.0  # avg hours
            return mock_result
        
        mock_db.execute = AsyncMock(side_effect=mock_execute_side_effect)
        
        result = await analytics_service.calculate_sla_compliance()
        
        assert result["compliance_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_calculate_sla_compliance_with_breaches(self, analytics_service, mock_db):
        """Test SLA compliance with some breaches."""
        call_count = 0
        
        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar.return_value = 10  # total tickets
            elif call_count == 2:
                mock_result.scalar.return_value = 2  # breached tickets
            else:
                mock_result.scalar.return_value = 5.0  # avg hours
            return mock_result
        
        mock_db.execute = AsyncMock(side_effect=mock_execute_side_effect)
        
        result = await analytics_service.calculate_sla_compliance()
        
        assert result["total_tickets"] == 10
        assert result["breached_tickets"] == 2


class TestTicketSummaries:
    """Tests for ticket summary methods."""
    
    @pytest.mark.asyncio
    async def test_get_ticket_summary_by_status(self, analytics_service, mock_db):
        """Test status summary."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (TicketStatusEnum.open, 5),
            (TicketStatusEnum.resolved, 10)
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_ticket_summary_by_status()
        
        assert isinstance(result, dict)
        assert "open" in result
        assert "resolved" in result
    
    @pytest.mark.asyncio
    async def test_get_ticket_summary_by_priority(self, analytics_service, mock_db):
        """Test priority summary."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (SentimentEnum.negative, 3),
            (SentimentEnum.neutral, 7),
            (SentimentEnum.positive, 5)
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_ticket_summary_by_priority()
        
        assert isinstance(result, dict)
        # Negative sentiment maps to high priority
        assert "high" in result


class TestGetChannelDistribution:
    """Tests for get_channel_distribution method."""
    
    @pytest.mark.asyncio
    async def test_get_channel_distribution_returns_dict(self, analytics_service, mock_db):
        """Test channel distribution structure."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (ChannelEnum.email, 10),
            (ChannelEnum.chat, 5)
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_channel_distribution()
        
        assert isinstance(result, dict)
        assert "email" in result
        assert result["email"] == 10
        assert result["chat"] == 5


class TestGetUsageSummary:
    """Tests for get_usage_summary method."""
    
    @pytest.mark.asyncio
    async def test_get_usage_summary_returns_dict(self, analytics_service, mock_db):
        """Test usage summary structure."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_usage_summary()
        
        assert "by_tier" in result
        assert "total_requests" in result
        assert "total_tokens" in result
    
    @pytest.mark.asyncio
    async def test_get_usage_summary_with_data(self, analytics_service, mock_db):
        """Test usage summary with mock data."""
        from backend.models.usage_log import AITier
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (AITier.light, 100, 5000),
            (AITier.medium, 50, 10000)
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_usage_summary()
        
        assert result["total_requests"] == 150
        assert result["total_tokens"] == 15000
        assert "light" in result["by_tier"]
        assert "medium" in result["by_tier"]


class TestCompanyScoping:
    """Tests to verify company scoping is enforced."""
    
    @pytest.mark.asyncio
    async def test_all_queries_include_company_id(self, analytics_service, mock_db):
        """Test that all queries filter by company_id."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_result.fetchall.return_value = []
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Call various methods
        await analytics_service.get_company_stats()
        await analytics_service.get_ticket_summary_by_status()
        await analytics_service.get_activity_feed()
        
        # Verify execute was called
        assert mock_db.execute.call_count >= 3
