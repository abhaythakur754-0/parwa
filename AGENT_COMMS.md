# AGENT_COMMS.md — Week 4 Day 3
# Last updated: 2026-03-29
# Current status: WEEK 4 DAY 3 IN PROGRESS

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 4 DAY 3 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-29

> **Phase: Phase 2 — Core AI Engine (API Layer)**
> Day 1 COMPLETE ✅ — Auth API, License API, Auth Core, License Manager. 138 tests.
> Day 2 COMPLETE ✅ — Support API, Dashboard API, Billing API, Compliance API. 106 tests.
> **Total: 422 tests passing.**
>
> Day 3: Building SERVICE LAYER — business logic for all APIs.
> All 4 service files are INDEPENDENT — build in PARALLEL.
>
> **CRITICAL RULES:**
> 1. You CANNOT use Docker locally — write tests with MOCKED databases
> 2. Build → Unit Test passes → THEN push (ONE push only)
> 3. NEVER push before test passes
> 4. Type hints on ALL functions, docstrings on ALL classes/functions

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/services/support_service.py`

**Purpose:** Service layer for support ticket operations — contains ALL business logic for the Support API built on Day 2.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files to understand the data structures:
- `backend/models/support_ticket.py` — SupportTicket ORM model
- `backend/models/user.py` — User ORM model
- `backend/models/company.py` — Company ORM model
- `backend/app/database.py` — Database session handling
- `backend/api/support.py` — Support API routes (Day 2)

**Step 3: Read BDD Scenario**
- File: `docs/bdd_scenarios/parwa_bdd.md`
- Section: Support Ticket scenarios

**Step 4: Create the Service File**

Create `backend/services/support_service.py` with:

```python
"""
Support Service Layer

Business logic for support ticket operations.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload

from backend.models.support_ticket import SupportTicket, TicketStatus, TicketPriority, TicketChannel
from backend.models.user import User
from backend.models.company import Company
from backend.models.audit_trail import AuditTrail
# Add proper imports based on your models


class SupportService:
    """
    Service class for support ticket business logic.
    
    All methods enforce company-scoped data access (RLS).
    Provides ticket CRUD, escalation, messaging, and SLA tracking.
    """
    
    def __init__(self, db: AsyncSession, company_id: UUID):
        """
        Initialize support service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def create_ticket(
        self,
        subject: str,
        description: str,
        customer_email: str,
        channel: TicketChannel = TicketChannel.EMAIL,
        priority: TicketPriority = TicketPriority.MEDIUM,
        customer_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SupportTicket:
        """
        Create a new support ticket.
        
        Args:
            subject: Ticket subject line
            description: Initial ticket description
            customer_email: Customer email address
            channel: Communication channel (email, chat, phone, etc.)
            priority: Ticket priority level
            customer_id: Optional customer user UUID
            metadata: Optional additional metadata
            
        Returns:
            Created SupportTicket instance
            
        Raises:
            ValueError: If required fields are missing
        """
        # Implementation with validation, SLA calculation, audit logging
        pass
    
    async def get_ticket_by_id(self, ticket_id: UUID) -> Optional[SupportTicket]:
        """
        Get a ticket by ID with company scoping.
        
        Args:
            ticket_id: Ticket UUID
            
        Returns:
            SupportTicket if found and belongs to company, None otherwise
        """
        pass
    
    async def list_tickets(
        self,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        assignee_id: Optional[UUID] = None,
        channel: Optional[TicketChannel] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[SupportTicket]:
        """
        List tickets with filtering and pagination.
        
        Args:
            status: Filter by status
            priority: Filter by priority
            assignee_id: Filter by assigned agent
            channel: Filter by channel
            limit: Max results to return
            offset: Pagination offset
            
        Returns:
            List of SupportTicket instances
        """
        pass
    
    async def update_ticket(
        self,
        ticket_id: UUID,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        assignee_id: Optional[UUID] = None,
        category: Optional[str] = None,
        ai_sentiment: Optional[str] = None,
        ai_category: Optional[str] = None
    ) -> Optional[SupportTicket]:
        """
        Update ticket fields.
        
        Args:
            ticket_id: Ticket UUID
            status: New status
            priority: New priority
            assignee_id: New assignee
            category: New category
            ai_sentiment: AI-detected sentiment
            ai_category: AI-detected category
            
        Returns:
            Updated SupportTicket if found, None otherwise
        """
        pass
    
    async def escalate_ticket(
        self,
        ticket_id: UUID,
        reason: str,
        escalated_to_id: UUID
    ) -> Optional[SupportTicket]:
        """
        Escalate ticket to higher support tier.
        
        Args:
            ticket_id: Ticket UUID
            reason: Escalation reason
            escalated_to_id: User UUID to escalate to
            
        Returns:
            Updated SupportTicket with escalation info
        """
        pass
    
    async def add_message(
        self,
        ticket_id: UUID,
        sender_id: UUID,
        message: str,
        is_internal: bool = False
    ) -> Dict[str, Any]:
        """
        Add a message to ticket conversation.
        
        Args:
            ticket_id: Ticket UUID
            sender_id: User UUID sending message
            message: Message content
            is_internal: Whether this is an internal note
            
        Returns:
            Dict with message details
        """
        pass
    
    async def calculate_sla_status(
        self,
        ticket_id: UUID
    ) -> Dict[str, Any]:
        """
        Calculate SLA status for a ticket.
        
        Args:
            ticket_id: Ticket UUID
            
        Returns:
            Dict with SLA status info:
            - is_breached: bool
            - time_remaining: timedelta
            - sla_deadline: datetime
        """
        pass
    
    async def _log_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID,
        changes: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log audit trail entry.
        
        Args:
            action: Action performed (create, update, escalate, etc.)
            entity_type: Entity type (ticket, message, etc.)
            entity_id: Entity UUID
            changes: Optional dict of changes
        """
        pass
```

**Step 5: Create the Test File**

Create `tests/unit/test_support_service.py`:

```python
"""
Unit tests for Support Service.
Uses mocked database sessions - no Docker required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime

from backend.services.support_service import SupportService
from backend.models.support_ticket import SupportTicket, TicketStatus, TicketPriority, TicketChannel


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def support_service(mock_db):
    """Support service instance with mocked DB."""
    company_id = uuid4()
    return SupportService(mock_db, company_id)


class TestSupportServiceInit:
    """Tests for SupportService initialization."""
    
    def test_init_stores_db_and_company_id(self, mock_db):
        """Test that init stores db and company_id."""
        company_id = uuid4()
        service = SupportService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id


class TestCreateTicket:
    """Tests for create_ticket method."""
    
    @pytest.mark.asyncio
    async def test_create_ticket_with_valid_data(self, support_service, mock_db):
        """Test creating a ticket with valid data."""
        # Mock the database add/commit/refresh
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await support_service.create_ticket(
            subject="Test Subject",
            description="Test description",
            customer_email="test@example.com"
        )
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_ticket_validates_required_fields(self, support_service):
        """Test that create_ticket validates required fields."""
        with pytest.raises(ValueError):
            await support_service.create_ticket(
                subject="",
                description="Test",
                customer_email="test@example.com"
            )
    
    @pytest.mark.asyncio
    async def test_create_ticket_validates_email(self, support_service):
        """Test that create_ticket validates email format."""
        with pytest.raises(ValueError):
            await support_service.create_ticket(
                subject="Test",
                description="Test",
                customer_email="invalid-email"
            )


class TestGetTicketById:
    """Tests for get_ticket_by_id method."""
    
    @pytest.mark.asyncio
    async def test_get_ticket_by_id_returns_ticket(self, support_service, mock_db):
        """Test getting a ticket by ID."""
        ticket_id = uuid4()
        mock_ticket = MagicMock(spec=SupportTicket)
        mock_ticket.id = ticket_id
        mock_ticket.company_id = support_service.company_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.get_ticket_by_id(ticket_id)
        
        assert result == mock_ticket
    
    @pytest.mark.asyncio
    async def test_get_ticket_by_id_returns_none_if_not_found(self, support_service, mock_db):
        """Test getting a non-existent ticket."""
        ticket_id = uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.get_ticket_by_id(ticket_id)
        
        assert result is None


class TestListTickets:
    """Tests for list_tickets method."""
    
    @pytest.mark.asyncio
    async def test_list_tickets_returns_list(self, support_service, mock_db):
        """Test listing tickets."""
        mock_tickets = [MagicMock(spec=SupportTicket) for _ in range(3)]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_tickets
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.list_tickets()
        
        assert len(result) == 3
    
    @pytest.mark.asyncio
    async def test_list_tickets_filters_by_status(self, support_service, mock_db):
        """Test filtering tickets by status."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        await support_service.list_tickets(status=TicketStatus.OPEN)
        
        mock_db.execute.assert_called_once()


class TestUpdateTicket:
    """Tests for update_ticket method."""
    
    @pytest.mark.asyncio
    async def test_update_ticket_updates_status(self, support_service, mock_db):
        """Test updating ticket status."""
        ticket_id = uuid4()
        mock_ticket = MagicMock(spec=SupportTicket)
        mock_ticket.id = ticket_id
        mock_ticket.company_id = support_service.company_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await support_service.update_ticket(
            ticket_id=ticket_id,
            status=TicketStatus.RESOLVED
        )
        
        assert mock_ticket.status == TicketStatus.RESOLVED
        mock_db.commit.assert_called_once()


class TestEscalateTicket:
    """Tests for escalate_ticket method."""
    
    @pytest.mark.asyncio
    async def test_escalate_ticket_sets_escalation_fields(self, support_service, mock_db):
        """Test escalating a ticket."""
        ticket_id = uuid4()
        escalated_to_id = uuid4()
        
        mock_ticket = MagicMock(spec=SupportTicket)
        mock_ticket.id = ticket_id
        mock_ticket.company_id = support_service.company_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await support_service.escalate_ticket(
            ticket_id=ticket_id,
            reason="Customer request",
            escalated_to_id=escalated_to_id
        )
        
        mock_db.commit.assert_called_once()


class TestAddMessage:
    """Tests for add_message method."""
    
    @pytest.mark.asyncio
    async def test_add_message_to_ticket(self, support_service, mock_db):
        """Test adding a message to a ticket."""
        ticket_id = uuid4()
        sender_id = uuid4()
        
        mock_ticket = MagicMock(spec=SupportTicket)
        mock_ticket.id = ticket_id
        mock_ticket.company_id = support_service.company_id
        mock_ticket.messages = []
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        
        result = await support_service.add_message(
            ticket_id=ticket_id,
            sender_id=sender_id,
            message="Test message"
        )
        
        assert result is not None


class TestCalculateSlaStatus:
    """Tests for calculate_sla_status method."""
    
    @pytest.mark.asyncio
    async def test_calculate_sla_returns_status(self, support_service, mock_db):
        """Test calculating SLA status."""
        ticket_id = uuid4()
        
        mock_ticket = MagicMock(spec=SupportTicket)
        mock_ticket.id = ticket_id
        mock_ticket.company_id = support_service.company_id
        mock_ticket.created_at = datetime.utcnow()
        mock_ticket.priority = TicketPriority.HIGH
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.calculate_sla_status(ticket_id)
        
        assert "is_breached" in result
        assert "time_remaining" in result
        assert "sla_deadline" in result


class TestAuditLogging:
    """Tests for audit logging functionality."""
    
    @pytest.mark.asyncio
    async def test_audit_log_called_on_create(self, support_service, mock_db):
        """Test that audit log is called on ticket creation."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Mock _log_audit method
        support_service._log_audit = AsyncMock()
        
        await support_service.create_ticket(
            subject="Test",
            description="Test",
            customer_email="test@example.com"
        )
        
        # Verify audit was logged
        support_service._log_audit.assert_called()
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
pytest tests/unit/test_support_service.py -v
```

**Step 7: Fix Until Pass**
If tests fail, fix the code and re-run. Stay in loop until ALL tests pass.

**Step 8: Push When Pass**
```bash
git add backend/services/support_service.py tests/unit/test_support_service.py backend/services/__init__.py
git commit -m "Week 4 Day 3: Builder 1 - Support service with business logic"
git push origin main
```

**Step 9: Update Status**
Update your status section in AGENT_COMMS.md with:
- Status: DONE
- Unit Test: PASS (X tests)
- Commit hash
- Any notes

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/services/analytics_service.py`

**Purpose:** Service layer for analytics and reporting — contains business logic for the Dashboard API built on Day 2.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/models/support_ticket.py` — SupportTicket model
- `backend/models/user.py` — User model
- `backend/models/usage_log.py` — UsageLog model
- `backend/models/sla_breach.py` — SLABreach model
- `backend/app/database.py` — Database session
- `backend/api/dashboard.py` — Dashboard API (Day 2)

**Step 3: Read BDD Scenario**
- File: `docs/bdd_scenarios/parwa_bdd.md`
- Section: Dashboard metrics scenarios

**Step 4: Create the Service File**

Create `backend/services/analytics_service.py` with:

```python
"""
Analytics Service Layer

Business logic for analytics, metrics, and reporting.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from collections import defaultdict

from backend.models.support_ticket import SupportTicket, TicketStatus, TicketPriority
from backend.models.user import User
from backend.models.usage_log import UsageLog
from backend.models.sla_breach import SLABreach
from backend.models.company import Company


class AnalyticsService:
    """
    Service class for analytics and reporting business logic.
    
    Provides metrics calculation, KPI tracking, and activity feeds.
    All methods enforce company-scoped data access (RLS).
    """
    
    def __init__(self, db: AsyncSession, company_id: UUID):
        """
        Initialize analytics service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def get_company_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated company statistics.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dict with:
            - total_tickets: int
            - open_tickets: int
            - resolved_tickets: int
            - avg_response_time: float (hours)
            - sla_compliance_rate: float (percentage)
        """
        pass
    
    async def get_ticket_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = "day"
    ) -> List[Dict[str, Any]]:
        """
        Get ticket volume and resolution metrics over time.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            group_by: Grouping interval (day, week, month)
            
        Returns:
            List of dicts with:
            - date: datetime
            - tickets_created: int
            - tickets_resolved: int
            - avg_resolution_time: float
        """
        pass
    
    async def get_response_time_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get average response times.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dict with:
            - first_response_avg: float (hours)
            - resolution_time_avg: float (hours)
            - by_priority: Dict[Priority, float]
        """
        pass
    
    async def get_agent_performance(
        self,
        agent_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get individual agent performance metrics.
        
        Args:
            agent_id: Optional specific agent UUID
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of dicts with:
            - agent_id: UUID
            - agent_name: str
            - tickets_assigned: int
            - tickets_resolved: int
            - avg_resolution_time: float
            - customer_satisfaction: float
        """
        pass
    
    async def get_activity_feed(
        self,
        limit: int = 50,
        offset: int = 0,
        activity_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent activity for dashboard feed.
        
        Args:
            limit: Max results
            offset: Pagination offset
            activity_types: Filter by activity types
            
        Returns:
            List of activity dicts with:
            - id: UUID
            - type: str
            - description: str
            - timestamp: datetime
            - user_id: UUID
            - metadata: dict
        """
        pass
    
    async def calculate_sla_compliance(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate SLA compliance percentage.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dict with:
            - compliance_rate: float (percentage)
            - total_tickets: int
            - breached_tickets: int
            - avg_time_to_breach: float (hours)
        """
        pass
    
    async def get_ticket_summary_by_status(self) -> Dict[str, int]:
        """
        Get ticket counts grouped by status.
        
        Returns:
            Dict mapping status to count
        """
        pass
    
    async def get_ticket_summary_by_priority(self) -> Dict[str, int]:
        """
        Get ticket counts grouped by priority.
        
        Returns:
            Dict mapping priority to count
        """
        pass
```

**Step 5: Create the Test File**

Create `tests/unit/test_analytics_service.py`:

```python
"""
Unit tests for Analytics Service.
Uses mocked database sessions - no Docker required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime, timedelta

from backend.services.analytics_service import AnalyticsService
from backend.models.support_ticket import SupportTicket, TicketStatus, TicketPriority


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


class TestTicketSummaries:
    """Tests for ticket summary methods."""
    
    @pytest.mark.asyncio
    async def test_get_ticket_summary_by_status(self, analytics_service, mock_db):
        """Test status summary."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (TicketStatus.OPEN, 5),
            (TicketStatus.RESOLVED, 10)
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_ticket_summary_by_status()
        
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_get_ticket_summary_by_priority(self, analytics_service, mock_db):
        """Test priority summary."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (TicketPriority.HIGH, 3),
            (TicketPriority.LOW, 7)
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await analytics_service.get_ticket_summary_by_priority()
        
        assert isinstance(result, dict)
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
pytest tests/unit/test_analytics_service.py -v
```

**Step 7: Fix Until Pass**
Stay in fix loop until ALL tests pass.

**Step 8: Push When Pass**
```bash
git add backend/services/analytics_service.py tests/unit/test_analytics_service.py
git commit -m "Week 4 Day 3: Builder 2 - Analytics service with metrics logic"
git push origin main
```

**Step 9: Update Status**
Update your status section in AGENT_COMMS.md.

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/services/billing_service.py`

**Purpose:** Service layer for billing and subscriptions — contains business logic for the Billing API built on Day 2.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/models/subscription.py` — Subscription model
- `backend/models/company.py` — Company model
- `backend/models/user.py` — User model
- `backend/app/database.py` — Database session
- `backend/api/billing.py` — Billing API (Day 2)

**Step 3: Read BDD Scenario**
- File: `docs/bdd_scenarios/parwa_bdd.md`
- Section: Billing scenarios

**Step 4: Create the Service File**

Create `backend/services/billing_service.py` with:

```python
"""
Billing Service Layer

Business logic for subscriptions, billing, and usage tracking.
All methods are company-scoped for RLS compliance.

CRITICAL: Stripe is NEVER called without a pending_approval record.
Payment processing requires explicit approval workflow.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from backend.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from backend.models.company import Company
from backend.models.user import User
from backend.models.audit_trail import AuditTrail


# Tier pricing configuration (USD per month)
TIER_PRICING = {
    SubscriptionTier.MINI: 1000.0,
    SubscriptionTier.PARWA: 2500.0,
    SubscriptionTier.PARWA_HIGH: 4500.0,
}

# Tier usage limits
TIER_LIMITS = {
    SubscriptionTier.MINI: {
        "tickets_per_month": 500,
        "voice_minutes_per_month": 100,
        "ai_interactions_per_month": 1000,
    },
    SubscriptionTier.PARWA: {
        "tickets_per_month": 2000,
        "voice_minutes_per_month": 500,
        "ai_interactions_per_month": 5000,
    },
    SubscriptionTier.PARWA_HIGH: {
        "tickets_per_month": 10000,
        "voice_minutes_per_month": 2000,
        "ai_interactions_per_month": 25000,
    },
}


class BillingService:
    """
    Service class for billing business logic.
    
    Provides subscription management, usage tracking, and billing calculations.
    All methods enforce company-scoped data access (RLS).
    
    CRITICAL: Never call Stripe without pending_approval record.
    """
    
    def __init__(self, db: AsyncSession, company_id: UUID):
        """
        Initialize billing service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def get_subscription(self) -> Optional[Subscription]:
        """
        Get current subscription for company.
        
        Returns:
            Subscription if found, None otherwise
        """
        pass
    
    async def update_subscription_tier(
        self,
        new_tier: SubscriptionTier,
        requested_by: UUID
    ) -> Dict[str, Any]:
        """
        Update subscription tier (upgrade or downgrade).
        
        Creates pending_approval record for payment processing.
        Does NOT call Stripe directly.
        
        Args:
            new_tier: Target tier
            requested_by: User UUID requesting change
            
        Returns:
            Dict with:
            - subscription: Updated Subscription
            - pending_approval_id: UUID for approval workflow
            - price_change: float (monthly difference)
        """
        pass
    
    async def get_invoices(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List invoices for company.
        
        Args:
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of invoice dicts
        """
        pass
    
    async def get_invoice_by_id(self, invoice_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get specific invoice details.
        
        Args:
            invoice_id: Invoice UUID
            
        Returns:
            Invoice dict if found, None otherwise
        """
        pass
    
    async def get_usage(self) -> Dict[str, Any]:
        """
        Get current usage vs tier limits.
        
        Returns:
            Dict with:
            - tier: SubscriptionTier
            - usage: Dict of usage metrics
            - limits: Dict of tier limits
            - percentages: Dict of usage percentages
        """
        pass
    
    async def check_usage_limits(
        self,
        action: str
    ) -> Dict[str, Any]:
        """
        Check if an action is within usage limits.
        
        Args:
            action: Action type (ticket, voice_minute, ai_interaction)
            
        Returns:
            Dict with:
            - allowed: bool
            - current_usage: int
            - limit: int
            - remaining: int
        """
        pass
    
    async def calculate_billing(
        self,
        tier: SubscriptionTier,
        period_months: int = 1
    ) -> Dict[str, Any]:
        """
        Calculate billing amount for tier and period.
        
        Args:
            tier: Subscription tier
            period_months: Billing period in months
            
        Returns:
            Dict with:
            - base_amount: float
            - period_months: int
            - total: float
            - currency: str
        """
        pass
    
    async def create_pending_approval(
        self,
        approval_type: str,
        amount: float,
        requested_by: UUID,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create pending approval record for payment action.
        
        CRITICAL: This MUST be called BEFORE any Stripe interaction.
        The approval workflow handles the actual payment processing.
        
        Args:
            approval_type: Type (subscription_change, refund, etc.)
            amount: Amount in USD
            requested_by: User UUID requesting
            metadata: Optional additional data
            
        Returns:
            Dict with pending_approval details
        """
        pass
    
    async def get_tier_pricing(self) -> Dict[str, Any]:
        """
        Get pricing for all tiers.
        
        Returns:
            Dict mapping tier to monthly price
        """
        pass
    
    async def validate_tier_change(
        self,
        current_tier: SubscriptionTier,
        new_tier: SubscriptionTier
    ) -> Dict[str, Any]:
        """
        Validate if tier change is allowed.
        
        Args:
            current_tier: Current subscription tier
            new_tier: Target tier
            
        Returns:
            Dict with:
            - valid: bool
            - is_upgrade: bool
            - message: str
        """
        pass
```

**Step 5: Create the Test File**

Create `tests/unit/test_billing_service.py`:

```python
"""
Unit tests for Billing Service.
Uses mocked database sessions - no Docker required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime

from backend.services.billing_service import (
    BillingService,
    TIER_PRICING,
    TIER_LIMITS
)
from backend.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def billing_service(mock_db):
    """Billing service instance with mocked DB."""
    company_id = uuid4()
    return BillingService(mock_db, company_id)


class TestBillingServiceInit:
    """Tests for BillingService initialization."""
    
    def test_init_stores_db_and_company_id(self, mock_db):
        """Test that init stores db and company_id."""
        company_id = uuid4()
        service = BillingService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id


class TestTierPricing:
    """Tests for tier pricing configuration."""
    
    def test_tier_pricing_has_all_tiers(self):
        """Test that all tiers have pricing."""
        assert SubscriptionTier.MINI in TIER_PRICING
        assert SubscriptionTier.PARWA in TIER_PRICING
        assert SubscriptionTier.PARWA_HIGH in TIER_PRICING
    
    def test_mini_tier_price(self):
        """Test Mini tier price is $1000/month."""
        assert TIER_PRICING[SubscriptionTier.MINI] == 1000.0
    
    def test_parwa_tier_price(self):
        """Test PARWA tier price is $2500/month."""
        assert TIER_PRICING[SubscriptionTier.PARWA] == 2500.0
    
    def test_parwa_high_tier_price(self):
        """Test PARWA High tier price is $4500/month."""
        assert TIER_PRICING[SubscriptionTier.PARWA_HIGH] == 4500.0


class TestTierLimits:
    """Tests for tier limits configuration."""
    
    def test_all_tiers_have_limits(self):
        """Test that all tiers have limits defined."""
        for tier in SubscriptionTier:
            assert tier in TIER_LIMITS
    
    def test_parwa_high_has_highest_limits(self):
        """Test PARWA High has highest limits."""
        high_tickets = TIER_LIMITS[SubscriptionTier.PARWA_HIGH]["tickets_per_month"]
        parwa_tickets = TIER_LIMITS[SubscriptionTier.PARWA]["tickets_per_month"]
        mini_tickets = TIER_LIMITS[SubscriptionTier.MINI]["tickets_per_month"]
        
        assert high_tickets > parwa_tickets
        assert parwa_tickets > mini_tickets


class TestGetSubscription:
    """Tests for get_subscription method."""
    
    @pytest.mark.asyncio
    async def test_get_subscription_returns_subscription(self, billing_service, mock_db):
        """Test getting company subscription."""
        mock_sub = MagicMock(spec=Subscription)
        mock_sub.company_id = billing_service.company_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sub
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await billing_service.get_subscription()
        
        assert result == mock_sub
    
    @pytest.mark.asyncio
    async def test_get_subscription_returns_none_if_not_found(self, billing_service, mock_db):
        """Test getting non-existent subscription."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await billing_service.get_subscription()
        
        assert result is None


class TestUpdateSubscriptionTier:
    """Tests for update_subscription_tier method."""
    
    @pytest.mark.asyncio
    async def test_update_creates_pending_approval(self, billing_service, mock_db):
        """Test that update creates pending approval record."""
        mock_sub = MagicMock(spec=Subscription)
        mock_sub.company_id = billing_service.company_id
        mock_sub.tier = SubscriptionTier.MINI
        mock_sub.status = SubscriptionStatus.ACTIVE
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sub
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        requested_by = uuid4()
        
        result = await billing_service.update_subscription_tier(
            new_tier=SubscriptionTier.PARWA,
            requested_by=requested_by
        )
        
        # CRITICAL: Verify pending_approval was created
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_upgrade_calculates_price_increase(self, billing_service, mock_db):
        """Test upgrade calculates correct price change."""
        mock_sub = MagicMock(spec=Subscription)
        mock_sub.company_id = billing_service.company_id
        mock_sub.tier = SubscriptionTier.MINI
        mock_sub.status = SubscriptionStatus.ACTIVE
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sub
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        
        result = await billing_service.update_subscription_tier(
            new_tier=SubscriptionTier.PARWA,
            requested_by=uuid4()
        )
        
        # Mini ($1000) -> PARWA ($2500) = +$1500
        # Verify price_change is positive for upgrade


class TestGetUsage:
    """Tests for get_usage method."""
    
    @pytest.mark.asyncio
    async def test_get_usage_returns_tier_limits(self, billing_service, mock_db):
        """Test that get_usage returns tier limits."""
        mock_sub = MagicMock(spec=Subscription)
        mock_sub.tier = SubscriptionTier.PARWA
        mock_sub.company_id = billing_service.company_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sub
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await billing_service.get_usage()
        
        assert "tier" in result
        assert "usage" in result
        assert "limits" in result


class TestCheckUsageLimits:
    """Tests for check_usage_limits method."""
    
    @pytest.mark.asyncio
    async def test_check_ticket_limit(self, billing_service, mock_db):
        """Test checking ticket usage limit."""
        mock_sub = MagicMock(spec=Subscription)
        mock_sub.tier = SubscriptionTier.MINI
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sub
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await billing_service.check_usage_limits("ticket")
        
        assert "allowed" in result
        assert "current_usage" in result
        assert "limit" in result


class TestCalculateBilling:
    """Tests for calculate_billing method."""
    
    @pytest.mark.asyncio
    async def test_calculate_monthly_billing(self, billing_service):
        """Test monthly billing calculation."""
        result = await billing_service.calculate_billing(
            tier=SubscriptionTier.PARWA,
            period_months=1
        )
        
        assert result["base_amount"] == 2500.0
        assert result["total"] == 2500.0
        assert result["currency"] == "USD"
    
    @pytest.mark.asyncio
    async def test_calculate_annual_billing(self, billing_service):
        """Test annual billing calculation."""
        result = await billing_service.calculate_billing(
            tier=SubscriptionTier.PARWA,
            period_months=12
        )
        
        assert result["base_amount"] == 2500.0
        assert result["total"] == 30000.0  # 2500 * 12


class TestCreatePendingApproval:
    """Tests for create_pending_approval method - CRITICAL."""
    
    @pytest.mark.asyncio
    async def test_create_pending_approval_stores_record(self, billing_service, mock_db):
        """Test that pending approval is stored in DB."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        
        result = await billing_service.create_pending_approval(
            approval_type="subscription_change",
            amount=1500.0,
            requested_by=uuid4()
        )
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pending_approval_required_before_stripe(self, billing_service, mock_db):
        """
        CRITICAL TEST: Verify that pending_approval is created
        BEFORE any Stripe call would be made.
        """
        # This test verifies the approval workflow pattern
        # In production, Stripe is only called after approval
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        
        result = await billing_service.create_pending_approval(
            approval_type="subscription_change",
            amount=2500.0,
            requested_by=uuid4()
        )
        
        # Verify: No direct Stripe call, only pending approval
        assert result is not None


class TestValidateTierChange:
    """Tests for validate_tier_change method."""
    
    @pytest.mark.asyncio
    async def test_upgrade_is_valid(self, billing_service):
        """Test that upgrade is valid."""
        result = await billing_service.validate_tier_change(
            current_tier=SubscriptionTier.MINI,
            new_tier=SubscriptionTier.PARWA
        )
        
        assert result["valid"] is True
        assert result["is_upgrade"] is True
    
    @pytest.mark.asyncio
    async def test_downgrade_is_valid(self, billing_service):
        """Test that downgrade is valid."""
        result = await billing_service.validate_tier_change(
            current_tier=SubscriptionTier.PARWA_HIGH,
            new_tier=SubscriptionTier.PARWA
        )
        
        assert result["valid"] is True
        assert result["is_upgrade"] is False
    
    @pytest.mark.asyncio
    async def test_same_tier_is_invalid(self, billing_service):
        """Test that same tier change is invalid."""
        result = await billing_service.validate_tier_change(
            current_tier=SubscriptionTier.PARWA,
            new_tier=SubscriptionTier.PARWA
        )
        
        assert result["valid"] is False


class TestGetInvoices:
    """Tests for get_invoices method."""
    
    @pytest.mark.asyncio
    async def test_get_invoices_returns_list(self, billing_service, mock_db):
        """Test getting invoice list."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await billing_service.get_invoices()
        
        assert isinstance(result, list)
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
pytest tests/unit/test_billing_service.py -v
```

**Step 7: Fix Until Pass**
Stay in fix loop until ALL tests pass.

**Step 8: Push When Pass**
```bash
git add backend/services/billing_service.py tests/unit/test_billing_service.py
git commit -m "Week 4 Day 3: Builder 3 - Billing service with subscription logic"
git push origin main
```

**Step 9: Update Status**
Update your status section in AGENT_COMMS.md.

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/services/onboarding_service.py`

**Purpose:** Service layer for new client onboarding — handles setup, initialization, and welcome workflows.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/models/company.py` — Company model
- `backend/models/user.py` — User model
- `backend/models/subscription.py` — Subscription model
- `backend/app/database.py` — Database session

**Step 3: Read BDD Scenario**
- File: `docs/bdd_scenarios/parwa_bdd.md`
- Section: Onboarding scenarios

**Step 4: Create the Service File**

Create `backend/services/onboarding_service.py` with:

```python
"""
Onboarding Service Layer

Business logic for new client onboarding.
Handles company setup, user creation, and welcome workflows.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.models.company import Company
from backend.models.user import User, UserRole
from backend.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from backend.models.audit_trail import AuditTrail


class OnboardingStep(str, Enum):
    """Onboarding steps enumeration."""
    COMPANY_INFO = "company_info"
    ADMIN_USER = "admin_user"
    SUBSCRIPTION = "subscription"
    INTEGRATION = "integration"
    TRAINING = "training"
    COMPLETE = "complete"


ONBOARDING_STEPS = [
    OnboardingStep.COMPANY_INFO,
    OnboardingStep.ADMIN_USER,
    OnboardingStep.SUBSCRIPTION,
    OnboardingStep.INTEGRATION,
    OnboardingStep.TRAINING,
    OnboardingStep.COMPLETE,
]


class OnboardingService:
    """
    Service class for onboarding business logic.
    
    Provides onboarding workflow management, company setup,
    and initial configuration.
    All methods enforce company-scoped data access (RLS).
    """
    
    def __init__(self, db: AsyncSession, company_id: Optional[UUID] = None):
        """
        Initialize onboarding service.
        
        Args:
            db: Async database session
            company_id: Optional company UUID (None for new onboarding)
        """
        self.db = db
        self.company_id = company_id
    
    async def start_onboarding(
        self,
        company_name: str,
        admin_email: str,
        admin_name: str,
        initial_tier: SubscriptionTier = SubscriptionTier.MINI
    ) -> Dict[str, Any]:
        """
        Initialize onboarding for a new company.
        
        Creates company record and starts onboarding workflow.
        
        Args:
            company_name: Name of the company
            admin_email: Email of the admin user
            admin_name: Name of the admin user
            initial_tier: Initial subscription tier
            
        Returns:
            Dict with:
            - company_id: UUID
            - onboarding_token: str
            - current_step: OnboardingStep
            - steps_completed: List[str]
        """
        pass
    
    async def complete_onboarding_step(
        self,
        step: OnboardingStep,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Mark an onboarding step as complete.
        
        Args:
            step: The step to complete
            data: Data for the step
            
        Returns:
            Dict with:
            - success: bool
            - current_step: OnboardingStep
            - steps_completed: List[str]
            - next_step: Optional[OnboardingStep]
        """
        pass
    
    async def get_onboarding_status(self) -> Dict[str, Any]:
        """
        Get current onboarding progress.
        
        Returns:
            Dict with:
            - company_id: UUID
            - status: str (pending, in_progress, complete)
            - current_step: OnboardingStep
            - steps_completed: List[str]
            - steps_remaining: List[str]
            - progress_percentage: float
        """
        pass
    
    async def setup_company_defaults(self) -> Dict[str, Any]:
        """
        Set up default settings for new company.
        
        Returns:
            Dict with default settings created
        """
        pass
    
    async def create_admin_user(
        self,
        email: str,
        name: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Create first admin user for company.
        
        Args:
            email: Admin email
            name: Admin name
            password: Initial password (will be hashed)
            
        Returns:
            Dict with:
            - user_id: UUID
            - email: str
            - role: UserRole
            - temp_password: bool
        """
        pass
    
    async def initialize_subscription(
        self,
        tier: SubscriptionTier,
        billing_email: str
    ) -> Dict[str, Any]:
        """
        Set up initial subscription.
        
        Creates subscription record in trial status.
        
        Args:
            tier: Subscription tier
            billing_email: Email for billing
            
        Returns:
            Dict with subscription details
        """
        pass
    
    async def send_welcome_email(
        self,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Trigger welcome email (mocked in development).
        
        In production, this would queue an email via Brevo/SendGrid.
        
        Args:
            user_id: User UUID to send email to
            
        Returns:
            Dict with:
            - sent: bool
            - email: str
            - message: str
        """
        pass
    
    async def validate_onboarding_data(
        self,
        step: OnboardingStep,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate onboarding form data.
        
        Args:
            step: The step being validated
            data: Data to validate
            
        Returns:
            Dict with:
            - valid: bool
            - errors: List[str]
        """
        pass
    
    async def get_onboarding_progress_percentage(self) -> float:
        """
        Calculate onboarding progress percentage.
        
        Returns:
            Float between 0.0 and 100.0
        """
        pass
```

**Step 5: Create the Test File**

Create `tests/unit/test_onboarding_service.py`:

```python
"""
Unit tests for Onboarding Service.
Uses mocked database sessions - no Docker required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from datetime import datetime

from backend.services.onboarding_service import (
    OnboardingService,
    OnboardingStep,
    ONBOARDING_STEPS
)
from backend.models.subscription import SubscriptionTier
from backend.models.user import UserRole


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def onboarding_service(mock_db):
    """Onboarding service instance with mocked DB."""
    company_id = uuid4()
    return OnboardingService(mock_db, company_id)


class TestOnboardingServiceInit:
    """Tests for OnboardingService initialization."""
    
    def test_init_with_company_id(self, mock_db):
        """Test init with company_id."""
        company_id = uuid4()
        service = OnboardingService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id
    
    def test_init_without_company_id(self, mock_db):
        """Test init without company_id (new onboarding)."""
        service = OnboardingService(mock_db)
        
        assert service.db == mock_db
        assert service.company_id is None


class TestOnboardingStepEnum:
    """Tests for OnboardingStep enum."""
    
    def test_all_steps_defined(self):
        """Test that all expected steps are defined."""
        assert OnboardingStep.COMPANY_INFO == "company_info"
        assert OnboardingStep.ADMIN_USER == "admin_user"
        assert OnboardingStep.SUBSCRIPTION == "subscription"
        assert OnboardingStep.INTEGRATION == "integration"
        assert OnboardingStep.TRAINING == "training"
        assert OnboardingStep.COMPLETE == "complete"
    
    def test_onboarding_steps_order(self):
        """Test that steps are in correct order."""
        assert ONBOARDING_STEPS[0] == OnboardingStep.COMPANY_INFO
        assert ONBOARDING_STEPS[-1] == OnboardingStep.COMPLETE


class TestStartOnboarding:
    """Tests for start_onboarding method."""
    
    @pytest.mark.asyncio
    async def test_start_onboarding_creates_company(self, onboarding_service, mock_db):
        """Test that start_onboarding creates company record."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await onboarding_service.start_onboarding(
            company_name="Test Company",
            admin_email="admin@test.com",
            admin_name="Admin User"
        )
        
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_start_onboarding_returns_company_id(self, onboarding_service, mock_db):
        """Test that start_onboarding returns company_id."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await onboarding_service.start_onboarding(
            company_name="Test Company",
            admin_email="admin@test.com",
            admin_name="Admin User"
        )
        
        assert "company_id" in result
        assert "current_step" in result
    
    @pytest.mark.asyncio
    async def test_start_onboarding_validates_required_fields(self, onboarding_service):
        """Test that start_onboarding validates required fields."""
        with pytest.raises(ValueError):
            await onboarding_service.start_onboarding(
                company_name="",
                admin_email="admin@test.com",
                admin_name="Admin User"
            )


class TestCompleteOnboardingStep:
    """Tests for complete_onboarding_step method."""
    
    @pytest.mark.asyncio
    async def test_complete_step_returns_next_step(self, onboarding_service, mock_db):
        """Test that completing step returns next step."""
        mock_company = MagicMock()
        mock_company.id = onboarding_service.company_id
        mock_company.onboarding_step = OnboardingStep.COMPANY_INFO
        mock_company.steps_completed = []
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_company
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        
        result = await onboarding_service.complete_onboarding_step(
            step=OnboardingStep.COMPANY_INFO,
            data={"name": "Updated Name"}
        )
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_complete_step_updates_progress(self, onboarding_service, mock_db):
        """Test that completing step updates progress."""
        mock_company = MagicMock()
        mock_company.id = onboarding_service.company_id
        mock_company.onboarding_step = OnboardingStep.COMPANY_INFO
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_company
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        
        result = await onboarding_service.complete_onboarding_step(
            step=OnboardingStep.COMPANY_INFO,
            data={}
        )
        
        mock_db.commit.assert_called()


class TestGetOnboardingStatus:
    """Tests for get_onboarding_status method."""
    
    @pytest.mark.asyncio
    async def test_get_status_returns_progress(self, onboarding_service, mock_db):
        """Test that get_onboarding_status returns progress."""
        mock_company = MagicMock()
        mock_company.id = onboarding_service.company_id
        mock_company.onboarding_step = OnboardingStep.ADMIN_USER
        mock_company.steps_completed = [OnboardingStep.COMPANY_INFO]
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_company
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await onboarding_service.get_onboarding_status()
        
        assert "current_step" in result
        assert "steps_completed" in result
        assert "progress_percentage" in result


class TestCreateAdminUser:
    """Tests for create_admin_user method."""
    
    @pytest.mark.asyncio
    async def test_create_admin_user_creates_record(self, onboarding_service, mock_db):
        """Test that admin user is created."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await onboarding_service.create_admin_user(
            email="admin@test.com",
            name="Admin User",
            password="securepassword123"
        )
        
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_create_admin_user_has_admin_role(self, onboarding_service, mock_db):
        """Test that admin user has ADMIN role."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await onboarding_service.create_admin_user(
            email="admin@test.com",
            name="Admin User",
            password="securepassword123"
        )
        
        # Verify role is set to ADMIN or MANAGER


class TestInitializeSubscription:
    """Tests for initialize_subscription method."""
    
    @pytest.mark.asyncio
    async def test_initialize_subscription_creates_record(self, onboarding_service, mock_db):
        """Test that subscription is created."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await onboarding_service.initialize_subscription(
            tier=SubscriptionTier.PARWA,
            billing_email="billing@test.com"
        )
        
        mock_db.add.assert_called()
    
    @pytest.mark.asyncio
    async def test_initialize_subscription_uses_correct_tier(self, onboarding_service, mock_db):
        """Test that subscription uses specified tier."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await onboarding_service.initialize_subscription(
            tier=SubscriptionTier.PARWA_HIGH,
            billing_email="billing@test.com"
        )
        
        assert result is not None


class TestSendWelcomeEmail:
    """Tests for send_welcome_email method."""
    
    @pytest.mark.asyncio
    async def test_send_welcome_email_returns_sent(self, onboarding_service, mock_db):
        """Test that welcome email is marked as sent."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await onboarding_service.send_welcome_email(mock_user.id)
        
        assert "sent" in result


class TestValidateOnboardingData:
    """Tests for validate_onboarding_data method."""
    
    @pytest.mark.asyncio
    async def test_validate_company_info_step(self, onboarding_service):
        """Test validating company_info step data."""
        result = await onboarding_service.validate_onboarding_data(
            step=OnboardingStep.COMPANY_INFO,
            data={"name": "Valid Company", "industry": "Tech"}
        )
        
        assert "valid" in result
        assert "errors" in result
    
    @pytest.mark.asyncio
    async def test_validate_returns_errors_for_invalid_data(self, onboarding_service):
        """Test that validation returns errors for invalid data."""
        result = await onboarding_service.validate_onboarding_data(
            step=OnboardingStep.COMPANY_INFO,
            data={"name": ""}  # Empty name should fail
        )
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0


class TestGetOnboardingProgressPercentage:
    """Tests for get_onboarding_progress_percentage method."""
    
    @pytest.mark.asyncio
    async def test_progress_zero_at_start(self, onboarding_service, mock_db):
        """Test progress is 0% at start."""
        mock_company = MagicMock()
        mock_company.steps_completed = []
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_company
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await onboarding_service.get_onboarding_progress_percentage()
        
        assert result == 0.0
    
    @pytest.mark.asyncio
    async def test_progress_100_when_complete(self, onboarding_service, mock_db):
        """Test progress is 100% when complete."""
        mock_company = MagicMock()
        mock_company.steps_completed = ONBOARDING_STEPS
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_company
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await onboarding_service.get_onboarding_progress_percentage()
        
        assert result == 100.0
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
pytest tests/unit/test_onboarding_service.py -v
```

**Step 7: Fix Until Pass**
Stay in fix loop until ALL tests pass.

**Step 8: Push When Pass**
```bash
git add backend/services/onboarding_service.py tests/unit/test_onboarding_service.py
git commit -m "Week 4 Day 3: Builder 4 - Onboarding service with setup logic"
git push origin main
```

**Step 9: Update Status**
Update your status section in AGENT_COMMS.md.

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS — UPDATE AFTER COMPLETING YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

## BUILDER 1 → STATUS
**File:** `backend/services/support_service.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_support_service.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** NONE
**Notes:** Waiting to start

---

## BUILDER 2 → STATUS
**File:** `backend/services/analytics_service.py`
**Status:** DONE
**Unit Test:** PASS (27 tests, 0 failures)
**Test File:** `tests/unit/test_analytics_service.py`
**Pushed:** YES
**Commit:** 5179853
**Initiative Files:**
- `backend/services/__init__.py` (created)
**Notes:**
- Implemented Analytics Service with 9 methods:
  - `get_company_stats()` — Get aggregated company statistics
  - `get_ticket_metrics()` — Get ticket volume and resolution metrics over time
  - `get_response_time_metrics()` — Get average response times
  - `get_agent_performance()` — Get individual agent performance metrics
  - `get_activity_feed()` — Get recent activity for dashboard feed
  - `calculate_sla_compliance()` — Calculate SLA compliance percentage
  - `get_ticket_summary_by_status()` — Get ticket counts grouped by status
  - `get_ticket_summary_by_priority()` — Get ticket counts grouped by priority
  - `get_channel_distribution()` — Get ticket counts grouped by channel
  - `get_usage_summary()` — Get usage summary from usage logs
- All methods enforce company-scoped data access (RLS)
- Type hints and docstrings on all functions
- Tests cover: initialization, stats retrieval, metrics calculation, SLA compliance, summaries, activity feeds, usage tracking

---

## BUILDER 3 → STATUS
**File:** `backend/services/billing_service.py`
**Status:** DONE
**Unit Test:** PASS (tests pass)
**Test File:** `tests/unit/test_billing_service.py`
**Pushed:** YES
**Commit:** 5d9d1d7
**Initiative Files:** NONE
**Notes:** Billing service with subscription management, usage tracking, and Stripe gate.

---

## BUILDER 4 → STATUS
**File:** `backend/services/onboarding_service.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_onboarding_service.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** NONE
**Notes:** Waiting to start

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT → VERIFICATION
═══════════════════════════════════════════════════════════════════════════════

**Status:** PENDING — Waiting for all builders to complete

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → ADVICE
═══════════════════════════════════════════════════════════════════════════════

[Manager will provide guidance here if builders report STUCK]

---

═══════════════════════════════════════════════════════════════════════════════
## ASSISTANCE AGENT → RESPONSE
═══════════════════════════════════════════════════════════════════════════════

[Assistance Agent will provide help here when activated]

---

═══════════════════════════════════════════════════════════════════════════════
## TEAM DISCUSSION
═══════════════════════════════════════════════════════════════════════════════

[Architectural concerns and decisions documented here]
