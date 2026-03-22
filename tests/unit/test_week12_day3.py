"""
Unit tests for Week 12 Day 3 files.

Tests for:
- Twilio webhook handler (HMAC validation, 401 on bad HMAC)
- Automation API (works with all variants)
- Non-financial undo service
- NLP command parser (critical test cases)
"""
# Mock sqlalchemy before any imports - must mock all submodules
import sys
from unittest.mock import MagicMock

# Mock all sqlalchemy modules before imports
sqlalchemy_mock = MagicMock()
sys.modules['sqlalchemy'] = sqlalchemy_mock
sys.modules['sqlalchemy.ext'] = MagicMock()
sys.modules['sqlalchemy.ext.asyncio'] = MagicMock()
sys.modules['sqlalchemy.orm'] = MagicMock()
sys.modules['sqlalchemy.dialects'] = MagicMock()
sys.modules['sqlalchemy.dialects.postgresql'] = MagicMock()

import pytest
from datetime import datetime, timezone, timedelta

# Now import our modules
from backend.api.webhooks.twilio import (
    verify_twilio_webhook,
    parse_twilio_form_data,
    generate_twiml_response,
)
from backend.api.automation import (
    AutomationType,
    AutomationStatus,
    VariantType,
    AutomationTrigger,
    AutomationSchedule,
    trigger_automation,
    schedule_automation,
    get_automation_status,
    list_automations,
    cancel_automation,
)
from backend.services.non_financial_undo import (
    NonFinancialUndoService,
    ActionType,
    UndoStatus,
)
from backend.nlp.command_parser import (
    CommandParser,
    IntentType,
)


# =============================================================================
# Twilio Webhook Tests
# =============================================================================

class TestTwilioWebhook:
    """Tests for Twilio webhook handler."""

    def test_verify_twilio_webhook_missing_signature(self):
        """CRITICAL: Test that missing signature returns False."""
        result = verify_twilio_webhook(
            request_body=b"test body",
            signature="",
            url="https://example.com/webhooks/twilio/voice"
        )
        assert result is False

    def test_verify_twilio_webhook_invalid_signature(self):
        """CRITICAL: Test that bad HMAC returns False (401 expected)."""
        result = verify_twilio_webhook(
            request_body=b"test body",
            signature="invalid_signature",
            url="https://example.com/webhooks/twilio/voice"
        )
        assert result is False

    def test_parse_twilio_form_data(self):
        """Test parsing Twilio form data."""
        body = b"CallSid=CA123&From=%2B1234567890&To=%2B0987654321"
        result = parse_twilio_form_data(body)

        assert result["CallSid"] == "CA123"
        assert result["From"] == "+1234567890"
        assert result["To"] == "+0987654321"

    def test_parse_twilio_form_data_empty(self):
        """Test parsing empty form data."""
        result = parse_twilio_form_data(b"")
        assert result == {}

    def test_generate_twiml_response(self):
        """CRITICAL: Test that recording disclosure fires in TwiML."""
        twiml = generate_twiml_response(
            message="Welcome to support",
            action="connect_agent",
            record=True
        )

        # CRITICAL: Recording disclosure must be present
        assert "recorded" in twiml.lower() or "recording" in twiml.lower()
        assert "<?xml" in twiml
        assert "<Response>" in twiml
        assert "</Response>" in twiml

    def test_generate_twiml_response_never_ivr_only(self):
        """CRITICAL: Test that response is never IVR-only."""
        twiml = generate_twiml_response(
            message="Test message",
            action="connect_agent"
        )

        assert "<Dial>" in twiml or "<Say>" in twiml
        assert twiml.strip().endswith("</Response>")

    def test_bad_hmac_returns_false(self):
        """CRITICAL: Test that bad HMAC validation returns False."""
        result = verify_twilio_webhook(
            b"test body",
            "bad_signature",
            "https://test.com/webhook"
        )
        assert result is False


# =============================================================================
# Automation API Tests
# =============================================================================

class TestAutomationAPI:
    """Tests for Automation API."""

    def test_automation_types_exist(self):
        """Test that all automation types are defined."""
        assert AutomationType.PROVISION_AGENT == "provision_agent"
        assert AutomationType.PAUSE_REFUNDS == "pause_refunds"
        assert AutomationType.ESCALATE_TICKET == "escalate_ticket"

    def test_variant_types_exist(self):
        """Test that all variant types are defined."""
        assert VariantType.MINI == "mini"
        assert VariantType.PARWA == "parwa"
        assert VariantType.PARWA_HIGH == "parwa_high"

    def test_automation_trigger_model(self):
        """Test automation trigger model."""
        trigger = AutomationTrigger(
            automation_type=AutomationType.PROVISION_AGENT,
            company_id="comp_123",
            variant=VariantType.MINI,
            parameters={"count": 2, "agent_type": "faq"},
        )
        assert trigger.automation_type == AutomationType.PROVISION_AGENT
        assert trigger.company_id == "comp_123"
        assert trigger.variant == VariantType.MINI
        assert trigger.parameters["count"] == 2

    def test_automation_schedule_model(self):
        """Test automation schedule model."""
        schedule = AutomationSchedule(
            automation_type=AutomationType.PAUSE_REFUNDS,
            company_id="comp_123",
            variant=VariantType.PARWA,
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert schedule.automation_type == AutomationType.PAUSE_REFUNDS
        assert schedule.recurring is False
        assert schedule.scheduled_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_trigger_automation_provision(self):
        """Test triggering provision automation."""
        result = await trigger_automation(
            request=AutomationTrigger(
                automation_type=AutomationType.PROVISION_AGENT,
                company_id="comp_test",
                variant=VariantType.MINI,
                parameters={"count": 3, "agent_type": "support"},
            ),
            db=MagicMock()
        )

        assert result.success is True
        assert result.status == AutomationStatus.COMPLETED
        assert result.variant == "mini"

    @pytest.mark.asyncio
    async def test_trigger_automation_pause_refunds(self):
        """Test triggering pause refunds automation."""
        result = await trigger_automation(
            request=AutomationTrigger(
                automation_type=AutomationType.PAUSE_REFUNDS,
                company_id="comp_test",
                variant=VariantType.PARWA,
            ),
            db=MagicMock()
        )

        assert result.success is True
        assert result.status == AutomationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_schedule_automation_future_time(self):
        """Test scheduling automation for future time."""
        result = await schedule_automation(
            request=AutomationSchedule(
                automation_type=AutomationType.SEND_NOTIFICATION,
                company_id="comp_test",
                variant=VariantType.MINI,
                scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2),
            ),
            db=MagicMock()
        )

        assert result.success is True
        assert result.status == AutomationStatus.PENDING


# =============================================================================
# Non-Financial Undo Service Tests
# =============================================================================

class TestNonFinancialUndoService:
    """Tests for Non-Financial Undo Service."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return NonFinancialUndoService()

    @pytest.mark.asyncio
    async def test_log_ticket_status_change(self, service):
        """Test logging a ticket status change action."""
        result = await service.log_action({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "performed_by": "user_456",
            "original_state": {"status": "open"},
            "new_state": {"status": "resolved"},
        })

        assert result["can_undo"] is True
        assert result["is_financial"] is False
        assert "action_id" in result

    @pytest.mark.asyncio
    async def test_log_financial_action_cannot_undo(self, service):
        """CRITICAL: Test that financial actions cannot be undone."""
        result = await service.log_action({
            "action_type": "refund",
            "company_id": "comp_123",
            "performed_by": "user_456",
            "original_state": {},
            "new_state": {"amount": 100.00},
            "amount": 100.00,
        })

        assert result["can_undo"] is False
        assert result["is_financial"] is True

    @pytest.mark.asyncio
    async def test_undo_non_financial_action(self, service):
        """CRITICAL: Test that non-money action can be undone."""
        log_result = await service.log_action({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "performed_by": "user_456",
            "original_state": {"status": "open", "ticket_id": "ticket_1"},
            "new_state": {"status": "resolved", "ticket_id": "ticket_1"},
        })

        undo_result = await service.undo_action(log_result["action_id"])

        assert undo_result["success"] is True
        assert undo_result["status"] == UndoStatus.COMPLETED.value
        assert undo_result["is_financial"] is False

    @pytest.mark.asyncio
    async def test_undo_financial_action_fails(self, service):
        """CRITICAL: Test that financial action cannot be undone."""
        log_result = await service.log_action({
            "action_type": "refund",
            "company_id": "comp_123",
            "performed_by": "user_456",
            "original_state": {},
            "new_state": {"amount": 50.00},
            "amount": 50.00,
        })

        undo_result = await service.undo_action(log_result["action_id"])

        assert undo_result["success"] is False
        assert undo_result["status"] == UndoStatus.NOT_UNDOABLE.value
        assert undo_result["is_financial"] is True

    @pytest.mark.asyncio
    async def test_get_undoable_actions(self, service):
        """Test getting list of undoable actions."""
        await service.log_action({
            "action_type": "tag_add",
            "company_id": "comp_get_test",
            "performed_by": "user_1",
            "original_state": {},
            "new_state": {"tag": "urgent"},
        })

        undoable = await service.get_undoable_actions("comp_get_test")

        assert len(undoable) >= 1
        for action in undoable:
            assert action["can_undo"] is True

    def test_is_action_financial(self, service):
        """Test checking if action is financial."""
        assert service.is_action_financial("refund") is True
        assert service.is_action_financial("charge") is True
        assert service.is_action_financial("payment") is True
        assert service.is_action_financial("ticket_status_change") is False
        assert service.is_action_financial("tag_add") is False


# =============================================================================
# NLP Command Parser Tests
# =============================================================================

class TestCommandParser:
    """Tests for NLP Command Parser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return CommandParser()

    def test_parse_add_2_mini(self, parser):
        """CRITICAL: Test 'Add 2 Mini' → {action: provision, count: 2, type: mini}."""
        result = parser.parse("Add 2 Mini")

        assert result.action == "provision"
        assert result.intent == IntentType.PROVISION
        assert result.entities.get("count") == 2
        assert result.entities.get("type") == "mini"
        assert result.confidence > 0.5

    def test_parse_pause_all_refunds(self, parser):
        """CRITICAL: Test 'Pause all refunds' → {action: pause_refunds, scope: all}."""
        result = parser.parse("Pause all refunds")

        assert result.action == "pause_refunds"
        assert result.intent == IntentType.PAUSE_REFUNDS
        assert result.entities.get("scope") == "all"
        assert result.confidence > 0.5

    def test_parse_escalate_ticket_123(self, parser):
        """CRITICAL: Test 'Escalate ticket 123' → {action: escalate, ticket_id: 123}."""
        result = parser.parse("Escalate ticket 123")

        assert result.action == "escalate"
        assert result.intent == IntentType.ESCALATE
        assert result.entities.get("ticket_id") == "123"
        assert result.confidence > 0.5

    def test_parse_escalate_with_hash(self, parser):
        """Test 'Escalate #456' parsing."""
        result = parser.parse("Escalate #456")

        assert result.action == "escalate"
        assert result.intent == IntentType.ESCALATE
        assert result.entities.get("ticket_id") == "456"

    def test_parse_provision_variants(self, parser):
        """Test provisioning different variants."""
        # Mini
        result = parser.parse("Add 1 Mini")
        assert result.entities.get("type") == "mini"

        # PARWA
        result = parser.parse("Add 3 PARWA")
        assert result.entities.get("type") == "parwa"

        # High
        result = parser.parse("Add 2 High")
        assert result.entities.get("type") == "parwa_high"

    def test_parse_resume_refunds(self, parser):
        """Test 'Resume all refunds' parsing."""
        result = parser.parse("Resume all refunds")

        assert result.action == "resume_refunds"
        assert result.intent == IntentType.RESUME_REFUNDS

    def test_parse_system_status(self, parser):
        """Test 'system status' parsing."""
        result = parser.parse("system status")

        assert result.action == "get_status"
        assert result.intent == IntentType.STATUS

    def test_parse_help(self, parser):
        """Test 'help' parsing."""
        result = parser.parse("help")

        assert result.action == "show_help"
        assert result.intent == IntentType.HELP

    def test_parse_unknown_returns_suggestions(self, parser):
        """Test that unknown commands return suggestions."""
        result = parser.parse("xyz abc def")

        assert result.action == "unknown"
        assert result.intent == IntentType.UNKNOWN
        assert len(result.suggestions) > 0
        assert "help" in result.suggestions

    def test_parse_empty_returns_unknown(self, parser):
        """Test that empty input returns unknown."""
        result = parser.parse("")

        assert result.action == "unknown"
        assert result.intent == IntentType.UNKNOWN

    def test_parse_case_insensitive(self, parser):
        """Test that parsing is case insensitive."""
        result1 = parser.parse("ADD 2 MINI")
        result2 = parser.parse("add 2 mini")
        result3 = parser.parse("Add 2 Mini")

        assert result1.action == result2.action == result3.action == "provision"
        assert result1.entities.get("count") == 2

    def test_parse_batch(self, parser):
        """Test batch parsing."""
        texts = [
            "Add 2 Mini",
            "Pause all refunds",
            "Escalate ticket 123",
        ]

        results = parser.parse_batch(texts)

        assert len(results) == 3
        assert results[0].action == "provision"
        assert results[1].action == "pause_refunds"
        assert results[2].action == "escalate"

    def test_to_dict(self, parser):
        """Test ParsedCommand.to_dict()."""
        result = parser.parse("Add 2 Mini")
        result_dict = result.to_dict()

        assert "action" in result_dict
        assert "intent" in result_dict
        assert "entities" in result_dict
        assert "confidence" in result_dict
        assert result_dict["action"] == "provision"


# =============================================================================
# Integration Tests
# =============================================================================

class TestWeek12Day3Integration:
    """Integration tests for Day 3 components."""

    def test_all_variant_types_supported(self):
        """Test that all variant types are supported across components."""
        variants = [VariantType.MINI, VariantType.PARWA, VariantType.PARWA_HIGH]

        for variant in variants:
            trigger = AutomationTrigger(
                automation_type=AutomationType.PROVISION_AGENT,
                company_id="test_company",
                variant=variant,
            )
            assert trigger.variant == variant

    def test_command_parser_provision_types_match_variants(self):
        """Test that parser variant types match automation variants."""
        parser = CommandParser()

        # Mini
        result = parser.parse("Add 1 Mini")
        assert result.entities.get("type") == "mini"

        # PARWA
        result = parser.parse("Add 1 PARWA")
        assert result.entities.get("type") == "parwa"

        # High (maps to parwa_high)
        result = parser.parse("Add 1 High")
        assert result.entities.get("type") == "parwa_high"

    @pytest.mark.asyncio
    async def test_financial_action_protection(self):
        """CRITICAL: Test that financial actions are protected from undo."""
        service = NonFinancialUndoService()

        # Log a refund (financial)
        log_result = await service.log_action({
            "action_type": "refund",
            "company_id": "comp_123",
            "performed_by": "user_456",
            "amount": 100.00,
        })

        # Verify it's marked as financial and not undoable
        assert log_result["is_financial"] is True
        assert log_result["can_undo"] is False

        # Verify undo fails
        undo_result = await service.undo_action(log_result["action_id"])
        assert undo_result["success"] is False
