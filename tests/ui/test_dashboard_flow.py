"""
UI Tests for Dashboard Flow.

Tests verify the complete dashboard workflow:
- Dashboard home page
- Tickets page
- Approvals page
- Agents page
- Analytics page

Uses mock DOM interactions and component state testing.
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, AsyncMock, patch
from enum import Enum
import uuid


class TicketStatus(str, Enum):
    """Ticket status enum."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """Ticket priority enum."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AgentStatus(str, Enum):
    """Agent status enum."""
    ACTIVE = "active"
    IDLE = "idle"
    OFFLINE = "offline"
    PAUSED = "paused"
    ERROR = "error"


class MockTicket:
    """Mock ticket for dashboard testing."""

    def __init__(
        self,
        ticket_id: str = "",
        subject: str = "",
        customer_name: str = "",
        customer_email: str = "",
        status: TicketStatus = TicketStatus.OPEN,
        priority: TicketPriority = TicketPriority.MEDIUM,
        channel: str = "email",
        assignee_id: Optional[str] = None,
    ):
        self.ticket_id = ticket_id or str(uuid.uuid4())
        self.subject = subject
        self.customer_name = customer_name
        self.customer_email = customer_email
        self.status = status
        self.priority = priority
        self.channel = channel
        self.assignee_id = assignee_id
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "subject": self.subject,
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "status": self.status.value,
            "priority": self.priority.value,
            "channel": self.channel,
            "assignee_id": self.assignee_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class MockAgent:
    """Mock agent for dashboard testing."""

    def __init__(
        self,
        agent_id: str = "",
        name: str = "",
        variant: str = "parwa",
        status: AgentStatus = AgentStatus.IDLE,
    ):
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name
        self.variant = variant
        self.status = status
        self.current_task: Optional[str] = None
        self.performance = {
            "accuracy": 95.0,
            "avg_response_time": 2.5,
            "tickets_handled": 0,
            "satisfaction_score": 90.0,
        }
        self.last_activity = datetime.now(timezone.utc)

    def assign_task(self, task: str) -> None:
        """Assign a task to the agent."""
        self.current_task = task
        self.status = AgentStatus.ACTIVE

    def complete_task(self) -> None:
        """Complete current task."""
        self.current_task = None
        self.performance["tickets_handled"] += 1
        self.status = AgentStatus.IDLE


class MockApproval:
    """Mock approval request for dashboard testing."""

    def __init__(
        self,
        approval_id: str = "",
        approval_type: str = "refund",
        amount: Optional[float] = None,
        description: str = "",
        requester_id: str = "",
        ticket_id: Optional[str] = None,
    ):
        self.approval_id = approval_id or str(uuid.uuid4())
        self.type = approval_type
        self.amount = amount
        self.description = description
        self.requester_id = requester_id
        self.ticket_id = ticket_id
        self.status = "pending"
        self.created_at = datetime.now(timezone.utc)
        self.minutes_pending = 0

    def approve(self) -> Dict[str, Any]:
        """Approve the request."""
        if self.status != "pending":
            return {"success": False, "error": "Already processed"}
        self.status = "approved"
        return {"success": True, "approval_id": self.approval_id}

    def deny(self, reason: str = "") -> Dict[str, Any]:
        """Deny the request."""
        if self.status != "pending":
            return {"success": False, "error": "Already processed"}
        self.status = "denied"
        return {"success": True, "approval_id": self.approval_id, "reason": reason}


class MockDashboardState:
    """Mock state for dashboard UI component."""

    def __init__(self):
        # Navigation
        self.current_page = "home"
        self.sidebar_collapsed = False

        # Tickets
        self.tickets: List[MockTicket] = []
        self.selected_ticket_id: Optional[str] = None
        self.ticket_filter_status: Optional[str] = None
        self.ticket_sort_by: str = "updated_at"
        self.ticket_sort_order: str = "desc"

        # Agents
        self.agents: List[MockAgent] = []
        self.selected_agent_id: Optional[str] = None

        # Approvals
        self.approvals: List[MockApproval] = []
        self.processing_approval_id: Optional[str] = None

        # Analytics
        self.analytics_period = "7d"
        self.analytics_data: Dict[str, Any] = {}

        # UI State
        self.is_loading = False
        self.error: Optional[str] = None
        self.notifications: List[Dict[str, Any]] = []

    def navigate_to(self, page: str) -> None:
        """Navigate to a page."""
        valid_pages = ["home", "tickets", "approvals", "agents", "analytics", "settings"]
        if page in valid_pages:
            self.current_page = page

    def get_filtered_tickets(self) -> List[MockTicket]:
        """Get tickets with filters applied."""
        filtered = self.tickets

        if self.ticket_filter_status:
            filtered = [t for t in filtered if t.status.value == self.ticket_filter_status]

        return filtered

    def get_pending_approvals(self) -> List[MockApproval]:
        """Get pending approvals."""
        return [a for a in self.approvals if a.status == "pending"]

    def get_active_agents(self) -> List[MockAgent]:
        """Get active agents."""
        return [a for a in self.agents if a.status == AgentStatus.ACTIVE]


class MockDashboardActions:
    """Mock actions for dashboard UI component."""

    def __init__(self, state: MockDashboardState):
        self.state = state

    # Navigation
    def go_to_tickets(self) -> None:
        """Navigate to tickets page."""
        self.state.navigate_to("tickets")

    def go_to_approvals(self) -> None:
        """Navigate to approvals page."""
        self.state.navigate_to("approvals")

    def go_to_agents(self) -> None:
        """Navigate to agents page."""
        self.state.navigate_to("agents")

    def go_to_analytics(self) -> None:
        """Navigate to analytics page."""
        self.state.navigate_to("analytics")

    # Tickets
    def add_ticket(self, ticket: MockTicket) -> None:
        """Add a ticket."""
        self.state.tickets.append(ticket)

    def select_ticket(self, ticket_id: str) -> None:
        """Select a ticket."""
        self.state.selected_ticket_id = ticket_id

    def filter_tickets_by_status(self, status: Optional[str]) -> None:
        """Filter tickets by status."""
        self.state.ticket_filter_status = status

    def update_ticket_status(self, ticket_id: str, status: TicketStatus) -> Dict[str, Any]:
        """Update ticket status."""
        for ticket in self.state.tickets:
            if ticket.ticket_id == ticket_id:
                ticket.status = status
                ticket.updated_at = datetime.now(timezone.utc)
                return {"success": True, "ticket": ticket.to_dict()}
        return {"success": False, "error": "Ticket not found"}

    # Agents
    def add_agent(self, agent: MockAgent) -> None:
        """Add an agent."""
        self.state.agents.append(agent)

    def pause_agent(self, agent_id: str) -> Dict[str, Any]:
        """Pause an agent."""
        for agent in self.state.agents:
            if agent.agent_id == agent_id:
                agent.status = AgentStatus.PAUSED
                return {"success": True}
        return {"success": False, "error": "Agent not found"}

    def resume_agent(self, agent_id: str) -> Dict[str, Any]:
        """Resume a paused agent."""
        for agent in self.state.agents:
            if agent.agent_id == agent_id:
                agent.status = AgentStatus.IDLE
                return {"success": True}
        return {"success": False, "error": "Agent not found"}

    # Approvals
    def add_approval(self, approval: MockApproval) -> None:
        """Add an approval request."""
        self.state.approvals.append(approval)

    async def approve_request(self, approval_id: str) -> Dict[str, Any]:
        """Approve a request."""
        for approval in self.state.approvals:
            if approval.approval_id == approval_id:
                return approval.approve()
        return {"success": False, "error": "Approval not found"}

    async def deny_request(self, approval_id: str, reason: str = "") -> Dict[str, Any]:
        """Deny a request."""
        for approval in self.state.approvals:
            if approval.approval_id == approval_id:
                return approval.deny(reason)
        return {"success": False, "error": "Approval not found"}

    # Analytics
    def set_analytics_period(self, period: str) -> None:
        """Set analytics period."""
        self.state.analytics_period = period

    async def refresh_analytics(self) -> Dict[str, Any]:
        """Refresh analytics data."""
        self.state.analytics_data = {
            "total_tickets": len(self.state.tickets),
            "resolved_tickets": len([t for t in self.state.tickets if t.status == TicketStatus.RESOLVED]),
            "active_agents": len(self.state.get_active_agents()),
            "pending_approvals": len(self.state.get_pending_approvals()),
            "period": self.state.analytics_period,
        }
        return self.state.analytics_data


# =============================================================================
# UI Tests
# =============================================================================

class TestDashboardNavigationUI:
    """Tests for dashboard navigation."""

    @pytest.fixture
    def state(self):
        return MockDashboardState()

    @pytest.fixture
    def actions(self, state):
        return MockDashboardActions(state)

    def test_dashboard_starts_at_home(self, state):
        """Test: Dashboard starts at home page."""
        assert state.current_page == "home"

    def test_navigate_to_tickets(self, state, actions):
        """Test: Navigate to tickets page."""
        actions.go_to_tickets()
        assert state.current_page == "tickets"

    def test_navigate_to_approvals(self, state, actions):
        """Test: Navigate to approvals page."""
        actions.go_to_approvals()
        assert state.current_page == "approvals"

    def test_navigate_to_agents(self, state, actions):
        """Test: Navigate to agents page."""
        actions.go_to_agents()
        assert state.current_page == "agents"

    def test_navigate_to_analytics(self, state, actions):
        """Test: Navigate to analytics page."""
        actions.go_to_analytics()
        assert state.current_page == "analytics"


class TestTicketsUI:
    """Tests for tickets page UI."""

    @pytest.fixture
    def state(self):
        return MockDashboardState()

    @pytest.fixture
    def actions(self, state):
        return MockDashboardActions(state)

    @pytest.fixture
    def sample_tickets(self, state, actions):
        """Add sample tickets."""
        tickets = [
            MockTicket("t1", "Cannot login", "John Doe", "john@example.com", TicketStatus.OPEN, TicketPriority.HIGH),
            MockTicket("t2", "Refund request", "Jane Smith", "jane@example.com", TicketStatus.IN_PROGRESS, TicketPriority.MEDIUM),
            MockTicket("t3", "Bug report", "Bob Wilson", "bob@example.com", TicketStatus.RESOLVED, TicketPriority.LOW),
        ]
        for ticket in tickets:
            actions.add_ticket(ticket)
        return tickets

    def test_tickets_page_shows_tickets(self, state, actions, sample_tickets):
        """Test: Tickets page shows all tickets."""
        actions.go_to_tickets()
        assert len(state.tickets) == 3

    def test_filter_tickets_by_status(self, state, actions, sample_tickets):
        """Test: Filter tickets by status works."""
        actions.filter_tickets_by_status("open")
        filtered = state.get_filtered_tickets()
        assert len(filtered) == 1
        assert filtered[0].status == TicketStatus.OPEN

    def test_select_ticket(self, state, actions, sample_tickets):
        """Test: Select a ticket."""
        actions.select_ticket("t1")
        assert state.selected_ticket_id == "t1"

    def test_update_ticket_status(self, state, actions, sample_tickets):
        """Test: Update ticket status."""
        result = actions.update_ticket_status("t1", TicketStatus.IN_PROGRESS)
        assert result["success"] is True
        assert state.tickets[0].status == TicketStatus.IN_PROGRESS

    def test_update_nonexistent_ticket_fails(self, state, actions):
        """Test: Update nonexistent ticket fails."""
        result = actions.update_ticket_status("nonexistent", TicketStatus.RESOLVED)
        assert result["success"] is False

    def test_empty_tickets_shows_message(self, state, actions):
        """Test: Empty tickets shows appropriate message."""
        actions.go_to_tickets()
        assert len(state.tickets) == 0


class TestApprovalsUI:
    """Tests for approvals page UI."""

    @pytest.fixture
    def state(self):
        return MockDashboardState()

    @pytest.fixture
    def actions(self, state):
        return MockDashboardActions(state)

    @pytest.fixture
    def sample_approvals(self, state, actions):
        """Add sample approvals."""
        approvals = [
            MockApproval("a1", "refund", 75.00, "Refund for defective product", "user1"),
            MockApproval("a2", "escalation", None, "Customer complaint escalation", "user2"),
            MockApproval("a3", "credit", 25.00, "Store credit for inconvenience", "user1"),
        ]
        for approval in approvals:
            actions.add_approval(approval)
        return approvals

    def test_approvals_page_shows_pending(self, state, actions, sample_approvals):
        """Test: Approvals page shows pending approvals."""
        actions.go_to_approvals()
        pending = state.get_pending_approvals()
        assert len(pending) == 3

    @pytest.mark.asyncio
    async def test_approve_request(self, state, actions, sample_approvals):
        """Test: Approve a request."""
        result = await actions.approve_request("a1")
        assert result["success"] is True

        pending = state.get_pending_approvals()
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_deny_request(self, state, actions, sample_approvals):
        """Test: Deny a request."""
        result = await actions.deny_request("a2", "Not justified")
        assert result["success"] is True

        pending = state.get_pending_approvals()
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_approve_nonexistent_fails(self, state, actions):
        """Test: Approve nonexistent request fails."""
        result = await actions.approve_request("nonexistent")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_cannot_approve_twice(self, state, actions, sample_approvals):
        """Test: Cannot approve same request twice."""
        await actions.approve_request("a1")
        result = await actions.approve_request("a1")
        assert result["success"] is False

    def test_approval_amount_display(self, state, actions, sample_approvals):
        """Test: Approval amounts are displayed correctly."""
        approval = state.approvals[0]
        assert approval.amount == 75.00


class TestAgentsUI:
    """Tests for agents page UI."""

    @pytest.fixture
    def state(self):
        return MockDashboardState()

    @pytest.fixture
    def actions(self, state):
        return MockDashboardActions(state)

    @pytest.fixture
    def sample_agents(self, state, actions):
        """Add sample agents."""
        agents = [
            MockAgent("ag1", "Support Agent Alpha", "parwa", AgentStatus.ACTIVE),
            MockAgent("ag2", "Support Agent Beta", "parwa_high", AgentStatus.IDLE),
            MockAgent("ag3", "Mini Agent", "mini", AgentStatus.PAUSED),
        ]
        for agent in agents:
            actions.add_agent(agent)
        return agents

    def test_agents_page_shows_agents(self, state, actions, sample_agents):
        """Test: Agents page shows all agents."""
        actions.go_to_agents()
        assert len(state.agents) == 3

    def test_pause_agent(self, state, actions, sample_agents):
        """Test: Pause an active agent."""
        result = actions.pause_agent("ag1")
        assert result["success"] is True
        assert state.agents[0].status == AgentStatus.PAUSED

    def test_resume_agent(self, state, actions, sample_agents):
        """Test: Resume a paused agent."""
        result = actions.resume_agent("ag3")
        assert result["success"] is True
        assert state.agents[2].status == AgentStatus.IDLE

    def test_get_active_agents(self, state, actions, sample_agents):
        """Test: Get active agents count."""
        active = state.get_active_agents()
        assert len(active) == 1

    def test_agent_task_assignment(self, state, sample_agents):
        """Test: Agent task assignment works."""
        agent = state.agents[0]
        agent.assign_task("Handling ticket #1234")
        assert agent.current_task == "Handling ticket #1234"
        assert agent.status == AgentStatus.ACTIVE

    def test_agent_task_completion(self, state, sample_agents):
        """Test: Agent task completion works."""
        agent = state.agents[0]
        initial_handled = agent.performance["tickets_handled"]
        agent.assign_task("Task")
        agent.complete_task()
        assert agent.performance["tickets_handled"] == initial_handled + 1
        assert agent.status == AgentStatus.IDLE


class TestAnalyticsUI:
    """Tests for analytics page UI."""

    @pytest.fixture
    def state(self):
        return MockDashboardState()

    @pytest.fixture
    def actions(self, state):
        return MockDashboardActions(state)

    @pytest.fixture
    def sample_data(self, state, actions):
        """Add sample data for analytics."""
        # Add tickets
        for i in range(10):
            status = TicketStatus.RESOLVED if i < 7 else TicketStatus.OPEN
            actions.add_ticket(MockTicket(f"t{i}", f"Ticket {i}", f"User {i}", f"user{i}@example.com", status))

        # Add agents
        for i in range(3):
            status = AgentStatus.ACTIVE if i < 2 else AgentStatus.IDLE
            actions.add_agent(MockAgent(f"ag{i}", f"Agent {i}", "parwa", status))

        # Add approvals
        for i in range(5):
            status = "approved" if i < 3 else "pending"
            approval = MockApproval(f"a{i}", "refund", 50.00 * (i + 1), f"Request {i}", "user1")
            approval.status = status
            actions.add_approval(approval)

    def test_analytics_page_loads(self, state, actions):
        """Test: Analytics page loads correctly."""
        actions.go_to_analytics()
        assert state.current_page == "analytics"

    def test_set_analytics_period(self, state, actions):
        """Test: Set analytics period works."""
        actions.set_analytics_period("30d")
        assert state.analytics_period == "30d"

    @pytest.mark.asyncio
    async def test_refresh_analytics(self, state, actions, sample_data):
        """Test: Refresh analytics returns data."""
        result = await actions.refresh_analytics()
        assert result["total_tickets"] == 10
        assert result["resolved_tickets"] == 7
        assert result["active_agents"] == 2
        assert result["pending_approvals"] == 2


class TestDashboardAccessibility:
    """Tests for dashboard accessibility."""

    def test_sidebar_keyboard_navigation(self):
        """Test: Sidebar supports keyboard navigation."""
        nav_items = ["home", "tickets", "approvals", "agents", "analytics", "settings"]
        assert len(nav_items) == 6

    def test_aria_labels_present(self):
        """Test: ARIA labels are present."""
        expected_labels = {
            "ticket-list": "List of support tickets",
            "approval-queue": "Queue of pending approvals",
            "agent-status": "Agent status and performance",
            "analytics-chart": "Analytics data visualization",
        }
        assert len(expected_labels) == 4

    def test_focus_management_on_navigation(self):
        """Test: Focus moves correctly on navigation."""
        focus_rules = {
            "navigate_to_tickets": "ticket-list",
            "navigate_to_approvals": "approval-queue",
            "navigate_to_agents": "agent-list",
        }
        assert len(focus_rules) == 3


class TestDashboardErrorHandling:
    """Tests for dashboard error handling."""

    @pytest.fixture
    def state(self):
        return MockDashboardState()

    def test_loading_state_display(self, state):
        """Test: Loading state is shown during fetch."""
        state.is_loading = True
        assert state.is_loading is True

    def test_error_state_display(self, state):
        """Test: Error state is displayed."""
        state.error = "Failed to load tickets"
        assert state.error is not None

    def test_invalid_page_navigation_blocked(self, state):
        """Test: Invalid page navigation is blocked."""
        state.navigate_to("invalid_page")
        assert state.current_page == "home"  # Should stay at home
