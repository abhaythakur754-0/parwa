"""
E2E tests for Mini Parwa ticket service.

Tests:
  - create_ticket -> returns ticket_id and response
  - solve_ticket -> re-processes and returns updated response
  - classify_ticket -> returns classification without response
  - Ticket with PII -> PII is redacted
  - Ticket with emergency -> emergency flag set, escalation response
  - Multiple tickets for same company -> isolation
"""

import os
import sys
import types
from unittest.mock import MagicMock, AsyncMock

import pytest

# ── Setup: Ensure paths and env vars ──────────────────────────────────
_backend_dir = os.path.join(os.path.dirname(__file__), "..")
if _backend_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_backend_dir))

_project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _project_root not in sys.path:
    sys.path.insert(0, os.path.abspath(_project_root))

# Set required env vars
for var, default in {
    "SECRET_KEY": "test-secret-key-for-testing-only-32c",
    "DATABASE_URL": "sqlite:///test.db",
    "JWT_SECRET_KEY": "test-jwt-secret-key-for-testing-32c",
    "DATA_ENCRYPTION_KEY": "test-encryption-key-for-testing-32",
    "ENVIRONMENT": "test",
}.items():
    os.environ.setdefault(var, default)

# ── Mock external modules ────────────────────────────────────────────
_fake_redis_module = types.ModuleType("app.core.redis")
_fake_redis_module.get_redis = AsyncMock(return_value=MagicMock())
_fake_redis_module.make_key = lambda *args: ":".join(str(a) for a in args)
sys.modules.setdefault("app.core.redis", _fake_redis_module)

_fake_exceptions = types.ModuleType("app.exceptions")
_fake_exceptions.InternalError = type("InternalError", (Exception,), {})
sys.modules.setdefault("app.exceptions", _fake_exceptions)

if "app.logger" not in sys.modules or not hasattr(sys.modules["app.logger"], "get_logger"):
    _fake_logger = types.ModuleType("app.logger")
    _mock_logger_instance = MagicMock()
    _fake_logger.get_logger = lambda name: _mock_logger_instance
    sys.modules["app.logger"] = _fake_logger

for mod_name in [
    "database", "database.base", "database.models",
    "database.models.core", "database.models.jarvis",
    "database.models.onboarding", "database.models.tickets",
    "database.models.email_channel", "database.models.outbound_email",
    "database.models.email_delivery_event", "database.models.ooo_detection",
    "database.models.email_bounces", "database.models.chat_widget",
    "database.models.sms_channel",
]:
    sys.modules.setdefault(mod_name, MagicMock())

for mod_name in [
    "shared", "shared.knowledge_base", "shared.knowledge_base.manager",
    "shared.knowledge_base.retriever", "shared.knowledge_base.vector_search",
    "shared.knowledge_base.chunker", "shared.knowledge_base.reindexing",
]:
    sys.modules.setdefault(mod_name, MagicMock())

# Now import
from app.core.mini_parwa.ticket_service import MiniParwaTicketService


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def ticket_service():
    """Create a MiniParwaTicketService instance."""
    return MiniParwaTicketService()


COMPANY_ID = "comp_test_123"


# ══════════════════════════════════════════════════════════════════
# TESTS: create_ticket
# ══════════════════════════════════════════════════════════════════


class TestCreateTicket:
    """Tests for the create_ticket method."""

    @pytest.mark.asyncio
    async def test_returns_ticket_id(self, ticket_service):
        """create_ticket should return a ticket_id."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="I need help with my order",
        )
        assert result["ticket_id"] != ""
        assert result["ticket_id"].startswith("tkt_")

    @pytest.mark.asyncio
    async def test_returns_response(self, ticket_service):
        """create_ticket should return a response."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="I need a refund",
        )
        assert result["response"] != ""
        assert isinstance(result["response"], str)

    @pytest.mark.asyncio
    async def test_returns_classification(self, ticket_service):
        """create_ticket should return classification."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="I want a refund for my order",
        )
        assert "classification" in result
        assert result["classification"]["intent"] != ""

    @pytest.mark.asyncio
    async def test_returns_pipeline_status(self, ticket_service):
        """create_ticket should return pipeline_status."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="Hello",
        )
        assert result["pipeline_status"] in ("success", "partial", "failed")

    @pytest.mark.asyncio
    async def test_company_id_in_result(self, ticket_service):
        """create_ticket should include company_id in result."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="Help me",
        )
        assert result["company_id"] == COMPANY_ID

    @pytest.mark.asyncio
    async def test_pii_detected_field(self, ticket_service):
        """create_ticket should include pii_detected field."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="My email is test@example.com",
        )
        assert "pii_detected" in result

    @pytest.mark.asyncio
    async def test_empathy_score_field(self, ticket_service):
        """create_ticket should include empathy_score field."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="I am frustrated!",
        )
        assert "empathy_score" in result


# ══════════════════════════════════════════════════════════════════
# TESTS: solve_ticket
# ══════════════════════════════════════════════════════════════════


class TestSolveTicket:
    """Tests for the solve_ticket method."""

    @pytest.mark.asyncio
    async def test_solve_existing_ticket(self, ticket_service):
        """solve_ticket should re-process an existing ticket."""
        # First create a ticket
        create_result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="I need help",
        )
        ticket_id = create_result["ticket_id"]

        # Then solve it
        solve_result = await ticket_service.solve_ticket(
            ticket_id=ticket_id,
            company_id=COMPANY_ID,
        )
        assert solve_result["ticket_id"] == ticket_id
        assert solve_result["response"] != ""

    @pytest.mark.asyncio
    async def test_solve_nonexistent_ticket(self, ticket_service):
        """solve_ticket should handle non-existent tickets."""
        result = await ticket_service.solve_ticket(
            ticket_id="tkt_nonexistent",
            company_id=COMPANY_ID,
        )
        assert result.get("error") == "ticket_not_found"

    @pytest.mark.asyncio
    async def test_solve_wrong_company(self, ticket_service):
        """solve_ticket should reject wrong company_id (isolation)."""
        # Create with one company
        create_result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="I need help",
        )
        ticket_id = create_result["ticket_id"]

        # Try to solve with different company
        solve_result = await ticket_service.solve_ticket(
            ticket_id=ticket_id,
            company_id="comp_other_456",
        )
        assert solve_result.get("error") == "ticket_company_mismatch"


# ══════════════════════════════════════════════════════════════════
# TESTS: classify_ticket
# ══════════════════════════════════════════════════════════════════


class TestClassifyTicket:
    """Tests for the classify_ticket method."""

    @pytest.mark.asyncio
    async def test_classify_returns_intent(self, ticket_service):
        """classify_ticket should return intent classification."""
        result = await ticket_service.classify_ticket(
            company_id=COMPANY_ID,
            query="I want a refund",
        )
        assert "classification" in result
        assert result["classification"]["intent"] != ""

    @pytest.mark.asyncio
    async def test_classify_no_generation(self, ticket_service):
        """classify_ticket should not include a generated response."""
        result = await ticket_service.classify_ticket(
            company_id=COMPANY_ID,
            query="I need a refund",
        )
        # classify_ticket should not have a response field (only classification)
        assert "response" not in result or result.get("response") is None

    @pytest.mark.asyncio
    async def test_classify_refund_intent(self, ticket_service):
        """classify_ticket should detect refund intent."""
        result = await ticket_service.classify_ticket(
            company_id=COMPANY_ID,
            query="I want my money back, give me a refund!",
        )
        assert result["classification"]["intent"] == "refund"

    @pytest.mark.asyncio
    async def test_classify_technical_intent(self, ticket_service):
        """classify_ticket should detect technical intent."""
        result = await ticket_service.classify_ticket(
            company_id=COMPANY_ID,
            query="The app is broken and not working",
        )
        assert result["classification"]["intent"] == "technical"

    @pytest.mark.asyncio
    async def test_classify_with_industry(self, ticket_service):
        """classify_ticket should accept industry parameter."""
        result = await ticket_service.classify_ticket(
            company_id=COMPANY_ID,
            query="Where is my order?",
            industry="ecommerce",
        )
        assert "classification" in result

    @pytest.mark.asyncio
    async def test_classify_pii_detected(self, ticket_service):
        """classify_ticket should detect PII in query."""
        result = await ticket_service.classify_ticket(
            company_id=COMPANY_ID,
            query="My email is test@example.com and I need help",
        )
        assert result.get("pii_detected") is True


# ══════════════════════════════════════════════════════════════════
# TESTS: PII redaction in tickets
# ══════════════════════════════════════════════════════════════════


class TestPIIInTickets:
    """Tests for PII redaction in ticket processing."""

    @pytest.mark.asyncio
    async def test_ticket_with_email_pii(self, ticket_service):
        """Ticket with email PII should be redacted."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="Contact me at user@example.com about my order",
        )
        assert result["pii_detected"] is True

    @pytest.mark.asyncio
    async def test_ticket_without_pii(self, ticket_service):
        """Ticket without PII should not be flagged."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="I need help with my order please",
        )
        assert result["pii_detected"] is False


# ══════════════════════════════════════════════════════════════════
# TESTS: Emergency handling in tickets
# ══════════════════════════════════════════════════════════════════


class TestEmergencyInTickets:
    """Tests for emergency handling in ticket processing."""

    @pytest.mark.asyncio
    async def test_ticket_with_legal_threat(self, ticket_service):
        """Ticket with legal threat should set emergency flag."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="I will sue your company for this!",
        )
        assert result["emergency_flag"] is True

    @pytest.mark.asyncio
    async def test_ticket_with_safety_threat(self, ticket_service):
        """Ticket with safety threat should set emergency flag."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="I want to hurt myself",
        )
        assert result["emergency_flag"] is True

    @pytest.mark.asyncio
    async def test_emergency_ticket_has_response(self, ticket_service):
        """Emergency ticket should still produce a response."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="I will take legal action against your company!",
        )
        assert result["response"] != ""

    @pytest.mark.asyncio
    async def test_normal_ticket_no_emergency(self, ticket_service):
        """Normal ticket should not set emergency flag."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="I need help with my account",
        )
        assert result["emergency_flag"] is False


# ══════════════════════════════════════════════════════════════════
# TESTS: Multi-tenant isolation
# ══════════════════════════════════════════════════════════════════


class TestMultiTenantIsolation:
    """Tests for multi-tenant ticket isolation."""

    @pytest.mark.asyncio
    async def test_multiple_companies_separate_tickets(self, ticket_service):
        """Tickets from different companies should be isolated."""
        # Create tickets for two different companies
        result1 = await ticket_service.create_ticket(
            company_id="comp_aaa",
            query="Company A needs help",
        )
        result2 = await ticket_service.create_ticket(
            company_id="comp_bbb",
            query="Company B needs help",
        )

        ticket_id_a = result1["ticket_id"]
        ticket_id_b = result2["ticket_id"]

        # Each company should only see their own tickets
        tickets_a = ticket_service.list_tickets("comp_aaa")
        tickets_b = ticket_service.list_tickets("comp_bbb")

        assert all(t["company_id"] == "comp_aaa" for t in tickets_a)
        assert all(t["company_id"] == "comp_bbb" for t in tickets_b)

    @pytest.mark.asyncio
    async def test_cannot_solve_other_company_ticket(self, ticket_service):
        """Cannot solve a ticket belonging to another company."""
        result = await ticket_service.create_ticket(
            company_id="comp_owner",
            query="Owner's ticket",
        )
        ticket_id = result["ticket_id"]

        # Try to solve with wrong company
        solve_result = await ticket_service.solve_ticket(
            ticket_id=ticket_id,
            company_id="comp_impostor",
        )
        assert solve_result.get("error") == "ticket_company_mismatch"

    @pytest.mark.asyncio
    async def test_get_ticket_isolation(self, ticket_service):
        """get_ticket should enforce company isolation."""
        result = await ticket_service.create_ticket(
            company_id="comp_x",
            query="Company X ticket",
        )
        ticket_id = result["ticket_id"]

        # Same company can access
        ticket = ticket_service.get_ticket(ticket_id, "comp_x")
        assert ticket is not None

        # Different company cannot access
        ticket = ticket_service.get_ticket(ticket_id, "comp_y")
        assert ticket is None


# ══════════════════════════════════════════════════════════════════
# TESTS: BC-008 error handling
# ══════════════════════════════════════════════════════════════════


class TestTicketServiceBC008:
    """BC-008: Ticket service should never crash."""

    @pytest.mark.asyncio
    async def test_create_ticket_empty_query(self, ticket_service):
        """create_ticket with empty query should not crash."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="",
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_create_ticket_special_characters(self, ticket_service):
        """create_ticket with special characters should not crash."""
        result = await ticket_service.create_ticket(
            company_id=COMPANY_ID,
            query="!@#$%^&*(){}[]|\\:;\"'<>,.?/~",
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_classify_ticket_empty_query(self, ticket_service):
        """classify_ticket with empty query should not crash."""
        result = await ticket_service.classify_ticket(
            company_id=COMPANY_ID,
            query="",
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_solve_ticket_empty_id(self, ticket_service):
        """solve_ticket with empty ID should not crash."""
        result = await ticket_service.solve_ticket(
            ticket_id="",
            company_id=COMPANY_ID,
        )
        assert isinstance(result, dict)
