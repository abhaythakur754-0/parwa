"""
Unit tests for SLA Service.
Uses mocked database sessions - no Docker required.
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.services.sla_service import (
    SLAService,
    SLATier,
    BreachPhase,
    SLAConfig,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def sla_service(mock_db):
    """SLA service instance with mocked DB."""
    company_id = uuid.uuid4()
    return SLAService(mock_db, company_id)


class TestSLAServiceInit:
    """Tests for SLAService initialization."""
    
    def test_init_stores_db_and_company_id(self, mock_db):
        """Test that init stores db and company_id."""
        company_id = uuid.uuid4()
        service = SLAService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id


class TestSLATierEnum:
    """Tests for SLATier enum."""
    
    def test_tier_values(self):
        """Test tier enum values."""
        assert SLATier.MINI.value == "mini"
        assert SLATier.PARWA.value == "parwa"
        assert SLATier.PARWA_HIGH.value == "high"
    
    def test_tier_count(self):
        """Test that we have expected number of tiers."""
        assert len(SLATier) == 3


class TestBreachPhaseEnum:
    """Tests for BreachPhase enum."""
    
    def test_phase_values(self):
        """Test phase enum values."""
        assert BreachPhase.PHASE_1.value == 1
        assert BreachPhase.PHASE_2.value == 2
        assert BreachPhase.PHASE_3.value == 3


class TestSLAConfig:
    """Tests for SLAConfig class."""
    
    def test_config_has_all_tiers(self):
        """Test that config has all tiers."""
        assert SLATier.MINI in SLAConfig.TIERS
        assert SLATier.PARWA in SLAConfig.TIERS
        assert SLATier.PARWA_HIGH in SLAConfig.TIERS
    
    def test_mini_tier_config(self):
        """Test MINI tier configuration."""
        config = SLAConfig.TIERS[SLATier.MINI]
        
        assert config["response_hours"] == 24
        assert config["resolution_hours"] == 72
        assert "email" in config["channels"]
    
    def test_parwa_tier_config(self):
        """Test PARWA tier configuration."""
        config = SLAConfig.TIERS[SLATier.PARWA]
        
        assert config["response_hours"] == 4
        assert config["resolution_hours"] == 24
        assert "chat" in config["channels"]
    
    def test_high_tier_config(self):
        """Test PARWA_HIGH tier configuration."""
        config = SLAConfig.TIERS[SLATier.PARWA_HIGH]
        
        assert config["response_hours"] == 1
        assert config["resolution_hours"] == 4
        assert "phone" in config["channels"]
        assert "video" in config["channels"]


class TestGetSLAConfig:
    """Tests for get_sla_config method."""
    
    @pytest.mark.asyncio
    async def test_get_sla_config_mini(self, sla_service):
        """Test getting MINI tier config."""
        config = await sla_service.get_sla_config(SLATier.MINI)
        
        assert config["response_hours"] == 24
        assert config["resolution_hours"] == 72
    
    @pytest.mark.asyncio
    async def test_get_sla_config_parwa(self, sla_service):
        """Test getting PARWA tier config."""
        config = await sla_service.get_sla_config(SLATier.PARWA)
        
        assert config["response_hours"] == 4
    
    @pytest.mark.asyncio
    async def test_get_sla_config_high(self, sla_service):
        """Test getting HIGH tier config."""
        config = await sla_service.get_sla_config(SLATier.PARWA_HIGH)
        
        assert config["response_hours"] == 1


class TestCheckSLABreach:
    """Tests for check_sla_breach method."""
    
    @pytest.mark.asyncio
    async def test_no_breach_within_sla(self, sla_service):
        """Test no breach when within SLA."""
        ticket_id = uuid.uuid4()
        created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        result = await sla_service.check_sla_breach(
            ticket_id=ticket_id,
            tier=SLATier.PARWA,
            created_at=created_at,
            first_response_at=datetime.now(timezone.utc)
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_response_breach_detected(self, sla_service):
        """Test response breach detection."""
        ticket_id = uuid.uuid4()
        created_at = datetime.now(timezone.utc) - timedelta(hours=5)  # Over 4hr limit
        
        result = await sla_service.check_sla_breach(
            ticket_id=ticket_id,
            tier=SLATier.PARWA,
            created_at=created_at,
            first_response_at=None  # No response yet
        )
        
        assert result is not None
        assert result["breach_type"] == "response"
        assert result["ticket_id"] == str(ticket_id)
    
    @pytest.mark.asyncio
    async def test_resolution_breach_detected(self, sla_service):
        """Test resolution breach detection."""
        ticket_id = uuid.uuid4()
        created_at = datetime.now(timezone.utc) - timedelta(hours=30)  # Over 24hr limit
        
        result = await sla_service.check_sla_breach(
            ticket_id=ticket_id,
            tier=SLATier.PARWA,
            created_at=created_at,
            first_response_at=created_at + timedelta(hours=1),  # Response was fast
            resolved_at=None  # Not resolved
        )
        
        assert result is not None
        assert result["breach_type"] == "resolution"
    
    @pytest.mark.asyncio
    async def test_mini_tier_24hr_response(self, sla_service):
        """Test MINI tier has 24hr response time."""
        ticket_id = uuid.uuid4()
        created_at = datetime.now(timezone.utc) - timedelta(hours=12)  # Within 24hr
        
        result = await sla_service.check_sla_breach(
            ticket_id=ticket_id,
            tier=SLATier.MINI,
            created_at=created_at,
            first_response_at=None
        )
        
        assert result is None  # No breach yet


class TestDetermineBreachPhase:
    """Tests for determine_breach_phase method."""
    
    @pytest.mark.asyncio
    async def test_phase_1_low_overdue(self, sla_service):
        """Test phase 1 for low overdue hours."""
        phase = await sla_service.determine_breach_phase(SLATier.PARWA, 3)
        
        assert phase == BreachPhase.PHASE_1
    
    @pytest.mark.asyncio
    async def test_phase_2_medium_overdue(self, sla_service):
        """Test phase 2 for medium overdue hours."""
        phase = await sla_service.determine_breach_phase(SLATier.PARWA, 5)
        
        assert phase == BreachPhase.PHASE_2
    
    @pytest.mark.asyncio
    async def test_phase_3_high_overdue(self, sla_service):
        """Test phase 3 for high overdue hours."""
        phase = await sla_service.determine_breach_phase(SLATier.PARWA, 15)
        
        assert phase == BreachPhase.PHASE_3


class TestRecordBreach:
    """Tests for record_breach method."""
    
    @pytest.mark.asyncio
    async def test_record_breach_returns_dict(self, sla_service):
        """Test that record_breach returns proper dict."""
        ticket_id = uuid.uuid4()
        
        result = await sla_service.record_breach(
            ticket_id=ticket_id,
            breach_phase=BreachPhase.PHASE_1,
            hours_overdue=2.5,
            notified_to="agent@example.com"
        )
        
        assert "breach_id" in result
        assert result["ticket_id"] == str(ticket_id)
        assert result["breach_phase"] == 1
        assert result["hours_overdue"] == 2.5
        assert result["notified_to"] == "agent@example.com"


class TestResolveBreach:
    """Tests for resolve_breach method."""
    
    @pytest.mark.asyncio
    async def test_resolve_breach_returns_dict(self, sla_service):
        """Test that resolve_breach returns proper dict."""
        breach_id = uuid.uuid4()
        
        result = await sla_service.resolve_breach(breach_id)
        
        assert result["breach_id"] == str(breach_id)
        assert result["resolved"] is True
        assert "resolved_at" in result


class TestGetSLAMetrics:
    """Tests for get_sla_metrics method."""
    
    @pytest.mark.asyncio
    async def test_get_metrics_returns_dict(self, sla_service):
        """Test that get_sla_metrics returns proper dict."""
        result = await sla_service.get_sla_metrics()
        
        assert "company_id" in result
        assert "metrics" in result
        assert "by_tier" in result
    
    @pytest.mark.asyncio
    async def test_get_metrics_with_date_range(self, sla_service):
        """Test get_sla_metrics with date range."""
        start = datetime.now(timezone.utc) - timedelta(days=30)
        end = datetime.now(timezone.utc)
        
        result = await sla_service.get_sla_metrics(start, end)
        
        assert result["period"]["start"] == start.isoformat()
        assert result["period"]["end"] == end.isoformat()


class TestListBreaches:
    """Tests for list_breaches method."""
    
    @pytest.mark.asyncio
    async def test_list_breaches_returns_list(self, sla_service):
        """Test that list_breaches returns list."""
        result = await sla_service.list_breaches()
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_list_breaches_with_filters(self, sla_service):
        """Test list_breaches with filters."""
        ticket_id = uuid.uuid4()
        
        result = await sla_service.list_breaches(
            ticket_id=ticket_id,
            breach_phase=BreachPhase.PHASE_1,
            resolved=False,
            limit=10,
            offset=0
        )
        
        assert isinstance(result, list)


class TestCalculateComplianceRate:
    """Tests for calculate_compliance_rate method."""
    
    @pytest.mark.asyncio
    async def test_compliance_rate_zero_tickets(self, sla_service):
        """Test compliance rate with zero tickets."""
        rate = await sla_service.calculate_compliance_rate()
        
        assert rate == 100.0  # No tickets = 100% compliance


class TestGetEscalationTargets:
    """Tests for get_escalation_targets method."""
    
    @pytest.mark.asyncio
    async def test_phase_1_targets_agent(self, sla_service):
        """Test phase 1 targets agent."""
        targets = await sla_service.get_escalation_targets(SLATier.PARWA, BreachPhase.PHASE_1)
        
        assert "agent" in targets
    
    @pytest.mark.asyncio
    async def test_phase_2_targets_manager(self, sla_service):
        """Test phase 2 targets manager."""
        targets = await sla_service.get_escalation_targets(SLATier.PARWA, BreachPhase.PHASE_2)
        
        assert "manager" in targets
    
    @pytest.mark.asyncio
    async def test_phase_3_targets_admin_and_manager(self, sla_service):
        """Test phase 3 targets admin and manager."""
        targets = await sla_service.get_escalation_targets(SLATier.PARWA, BreachPhase.PHASE_3)
        
        assert "admin" in targets
        assert "manager" in targets


class TestCompanyScoping:
    """Tests for company scoping enforcement."""
    
    @pytest.mark.asyncio
    async def test_all_methods_include_company_id(self, sla_service):
        """Test that methods include company_id in results."""
        ticket_id = uuid.uuid4()
        
        # record_breach
        breach = await sla_service.record_breach(
            ticket_id=ticket_id,
            breach_phase=BreachPhase.PHASE_1,
            hours_overdue=1.0,
            notified_to="agent@example.com"
        )
        assert breach["company_id"] == str(sla_service.company_id)
        
        # get_sla_metrics
        metrics = await sla_service.get_sla_metrics()
        assert metrics["company_id"] == str(sla_service.company_id)
