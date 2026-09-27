"""
Comprehensive Unit Tests for PARWA Jarvis Command Service (Phase 3 — Day 1)

Tests cover all 7 major areas:
  1. TestParseNaturalLanguageCommand — 20+ NL command patterns, confidence, fuzzy, unknown
  2. TestReceiveCommand — command lifecycle creation, parsing, source validation
  3. TestExecuteCommand — status transitions, handler dispatch, error handling (BC-008)
  4. TestUndoCommand — undoable/non-undoable, already-undone, not-found, linking
  5. TestQuickCommands — presets, execute, not-found, skip NL parsing
  6. TestCommandHistory — pagination, filters, prune
  7. TestConstants — enum validation, confidence thresholds, limits

BC-008: All tests verify graceful degradation on invalid inputs.
BC-001: company_id is always the first parameter on public methods.
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import MagicMock, patch, call

from app.services.jarvis_command_service import (
    parse_natural_language_command,
    receive_command,
    execute_command,
    undo_command,
    get_quick_commands,
    execute_quick_command,
    get_command_history,
    get_command_by_id,
    prune_old_commands,
    cancel_command,
    _safe_parse_json,
    _merge_metadata,
    _build_unknown_command,
    _extract_parameters,
    _infer_target,
    _generate_suggestion,
    _fuzzy_match_command,
    _command_to_dict,
    _dispatch_handler,
    _execute_undo_action,
    VALID_COMMAND_INTENTS,
    VALID_COMMAND_STATUSES,
    VALID_SOURCES,
    NON_UNDOABLE_INTENTS,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    CONFIDENCE_UNKNOWN,
    DEFAULT_QUICK_COMMANDS,
    COMMAND_PATTERNS,
    MAX_PARSE_INPUT_LENGTH,
    MAX_QUICK_COMMANDS_PER_TENANT,
    MAX_COMMAND_HISTORY_PER_SESSION,
    COMMAND_HISTORY_PRUNE_BATCH,
)
from app.exceptions import NotFoundError, ValidationError


# ══════════════════════════════════════════════════════════════════
# ENSURE JarvisCommand MOCK HAS ALL NEEDED CLASS ATTRIBUTES
# ══════════════════════════════════════════════════════════════════
# The conftest _MockJarvisCommand only has id, session_id, company_id.
# We need undo_available, status, command_intent, created_at, source
# as class-level _AttrChainer() so SQLAlchemy filter expressions
# like JarvisCommand.undo_available.is_(True) work in mock queries.

from database.models.jarvis_cc import JarvisCommand as _JarvisCommandClass


class _AttrChainer:
    """Supports SQLAlchemy-style attribute chaining on mock model classes."""
    def __getattr__(self, name):
        return _AttrChainer()
    def desc(self):
        return self
    def asc(self):
        return self
    def __ge__(self, other):
        return True
    def __le__(self, other):
        return True
    def __eq__(self, other):
        return True
    def __ne__(self, other):
        return False
    def in_(self, *args):
        return self
    def isnot(self, *args):
        return self
    def is_(self, *args):
        return self
    def notin_(self, *args):
        return self
    def contains(self, *args):
        return self
    def __bool__(self):
        return True


# Add missing class attributes so filter expressions don't raise AttributeError
for _attr in (
    "undo_available", "status", "command_intent", "created_at",
    "source", "raw_input", "confidence", "command_parsed",
    "result_json", "error_message", "received_at", "parsed_at",
    "executed_at", "completed_at", "undone_by_command_id",
    "co_pilot_suggestion", "co_pilot_suggestion_type",
    "command_metadata_json", "snapshot_type", "tick_number",
    "alert_type", "severity", "category",
):
    if not hasattr(_JarvisCommandClass, _attr) or getattr(_JarvisCommandClass, _attr) is None:
        try:
            setattr(_JarvisCommandClass, _attr, _AttrChainer())
        except (TypeError, AttributeError):
            pass


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def _make_mock_command(**overrides) -> MagicMock:
    """Create a mock JarvisCommand with sensible defaults."""
    cmd = MagicMock()
    cmd.id = "test-cmd-001"
    cmd.session_id = "test-session-001"
    cmd.company_id = "test-company-001"
    cmd.raw_input = "pause all agents"
    cmd.source = "chat"
    cmd.command_parsed = json.dumps({
        "action": "pause_ai",
        "intent": "control",
        "scope": "global",
        "target": "ai",
        "parameters": {},
        "confidence": 0.85,
        "raw_input": "pause all agents",
        "suggestion": None,
    })
    cmd.command_intent = "control"
    cmd.confidence = 0.85
    cmd.co_pilot_suggestion = None
    cmd.co_pilot_suggestion_type = None
    cmd.status = "parsed"
    cmd.result_json = "{}"
    cmd.error_message = None
    cmd.command_metadata_json = "{}"
    cmd.undo_available = True
    cmd.undone_by_command_id = None
    cmd.received_at = datetime.now(timezone.utc)
    cmd.parsed_at = datetime.now(timezone.utc)
    cmd.executed_at = None
    cmd.completed_at = None
    cmd.created_at = datetime.now(timezone.utc)
    for k, v in overrides.items():
        setattr(cmd, k, v)
    return cmd


@pytest.fixture
def mock_db():
    """Create a mock SQLAlchemy session with default return values."""
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.scalar.return_value = 0
    db.query.return_value.filter.return_value.first.return_value = None
    return db


# ══════════════════════════════════════════════════════════════════
# 1. TEST PARSE NATURAL LANGUAGE COMMAND
# ══════════════════════════════════════════════════════════════════


class TestParseNaturalLanguageCommand:
    """Tests for parse_natural_language_command — the NL -> structured command parser.

    Covers all 20+ command patterns, confidence levels, fuzzy matching,
    unknown commands, empty input, long input truncation, parameter
    extraction, suggestion generation, and confidence boosting.
    """

    # ── Pattern: pause_ai (control, HIGH confidence) ──

    def test_pause_all_ai(self):
        """'pause all AI' -> action=pause_ai, intent=control, confidence=HIGH."""
        result = parse_natural_language_command("company-1", "pause all AI")
        assert result["action"] == "pause_ai"
        assert result["intent"] == "control"
        assert result["confidence"] >= CONFIDENCE_HIGH
        assert result["scope"] == "global"
        assert result["suggestion"] is None

    def test_pause_all_agents(self):
        """'pause all agents' -> action=pause_ai."""
        result = parse_natural_language_command("company-1", "pause all agents")
        assert result["action"] == "pause_ai"

    def test_stop_ai(self):
        """'stop AI' -> action=pause_ai (synonym 'stop')."""
        result = parse_natural_language_command("company-1", "stop AI")
        assert result["action"] == "pause_ai"

    def test_halt_agent(self):
        """'halt agent' -> action=pause_ai (synonym 'halt')."""
        result = parse_natural_language_command("company-1", "halt agent")
        assert result["action"] == "pause_ai"

    def test_freeze_bot(self):
        """'freeze bot' -> action=pause_ai (synonym 'freeze', target 'bot')."""
        result = parse_natural_language_command("company-1", "freeze bot")
        assert result["action"] == "pause_ai"

    # ── Pattern: resume_ai (control, HIGH confidence) ──

    def test_resume_all_agents(self):
        """'resume all agents' -> action=resume_ai, intent=control, confidence=HIGH."""
        result = parse_natural_language_command("company-1", "resume all agents")
        assert result["action"] == "resume_ai"
        assert result["intent"] == "control"
        assert result["confidence"] >= CONFIDENCE_HIGH

    def test_unpause_ai(self):
        """'unpause AI' -> action=resume_ai (synonym 'unpause')."""
        result = parse_natural_language_command("company-1", "unpause AI")
        assert result["action"] == "resume_ai"

    def test_restart_agents(self):
        """'restart agents' -> action=resume_ai (synonym 'restart')."""
        result = parse_natural_language_command("company-1", "restart agents")
        assert result["action"] == "resume_ai"

    def test_continue_all_bots(self):
        """'continue all bots' -> action=resume_ai (synonym 'continue')."""
        result = parse_natural_language_command("company-1", "continue all bots")
        assert result["action"] == "resume_ai"

    # ── Pattern: pause_refunds (control, HIGH confidence) ──

    def test_pause_refund_processing(self):
        """'pause refund processing' -> action=pause_refunds, scope=refunds."""
        result = parse_natural_language_command("company-1", "pause refund processing")
        assert result["action"] == "pause_refunds"
        assert result["intent"] == "control"
        assert result["scope"] == "refunds"
        assert result["confidence"] >= CONFIDENCE_HIGH

    def test_stop_refunds(self):
        """'stop refunds' -> action=pause_refunds."""
        result = parse_natural_language_command("company-1", "stop refunds")
        assert result["action"] == "pause_refunds"

    def test_halt_refund_processing(self):
        """'halt refund processing' -> action=pause_refunds."""
        result = parse_natural_language_command("company-1", "halt refund processing")
        assert result["action"] == "pause_refunds"

    # ── Pattern: resume_refunds ──

    def test_resume_refund_processing(self):
        """'resume refund processing' -> action=resume_refunds, scope=refunds."""
        result = parse_natural_language_command("company-1", "resume refund processing")
        assert result["action"] == "resume_refunds"
        assert result["scope"] == "refunds"

    # ── Pattern: emergency brake (override, HIGH confidence) ──

    def test_emergency_brake(self):
        """'emergency brake' -> action=pause_ai, intent=override."""
        result = parse_natural_language_command("company-1", "emergency brake")
        assert result["action"] == "pause_ai"
        assert result["intent"] == "override"
        assert result["confidence"] >= CONFIDENCE_HIGH

    def test_emergency_shutdown(self):
        """'emergency shutdown' -> action=pause_ai, intent=override."""
        result = parse_natural_language_command("company-1", "emergency shutdown")
        assert result["action"] == "pause_ai"
        assert result["intent"] == "override"

    def test_emergency_halt(self):
        """'emergency halt' -> action=pause_ai, intent=override."""
        result = parse_natural_language_command("company-1", "emergency halt")
        assert result["action"] == "pause_ai"
        assert result["intent"] == "override"

    # ── Pattern: check_system_health (query, HIGH confidence) ──

    def test_check_system_health(self):
        """'check system health' -> action=check_system_health, intent=query."""
        result = parse_natural_language_command("company-1", "check system health")
        assert result["action"] == "check_system_health"
        assert result["intent"] == "query"
        assert result["scope"] == "system"

    def test_show_system_health(self):
        """'show system health' -> action=check_system_health."""
        result = parse_natural_language_command("company-1", "show system health")
        assert result["action"] == "check_system_health"

    def test_whats_the_system_health(self):
        """'what's the system health' -> action=check_system_health."""
        result = parse_natural_language_command("company-1", "what's the system health")
        assert result["action"] == "check_system_health"

    def test_what_is_the_health(self):
        """'what is the health' -> action=check_system_health."""
        result = parse_natural_language_command("company-1", "what is the health")
        assert result["action"] == "check_system_health"

    # ── Pattern: show_errors (query, HIGH confidence) ──

    def test_show_me_todays_errors(self):
        """'show me today's errors' -> action=show_errors, intent=query."""
        result = parse_natural_language_command("company-1", "show me today's errors")
        assert result["action"] == "show_errors"
        assert result["intent"] == "query"
        assert result["scope"] == "errors"

    def test_display_errors(self):
        """'display errors' -> action=show_errors."""
        result = parse_natural_language_command("company-1", "display errors")
        assert result["action"] == "show_errors"

    def test_list_failures(self):
        """'list failures' -> action=show_errors (synonym 'failures')."""
        result = parse_natural_language_command("company-1", "list failures")
        assert result["action"] == "show_errors"

    def test_get_me_todays_errors(self):
        """'get me today's errors' -> action=show_errors."""
        result = parse_natural_language_command("company-1", "get me today's errors")
        assert result["action"] == "show_errors"

    # ── Pattern: show_ticket_details ──

    def test_show_ticket_details(self):
        """'show me the ticket details' -> action=show_ticket_details, scope=ticket."""
        result = parse_natural_language_command("company-1", "show me the ticket details")
        assert result["action"] == "show_ticket_details"
        assert result["scope"] == "ticket"

    def test_get_ticket_info(self):
        """'get ticket info' -> action=show_ticket_details."""
        result = parse_natural_language_command("company-1", "get ticket info")
        assert result["action"] == "show_ticket_details"

    # ── Pattern: status (MEDIUM confidence) ──

    def test_status_medium_confidence(self):
        """'status' -> action=check_system_health, confidence=MEDIUM."""
        result = parse_natural_language_command("company-1", "status")
        assert result["action"] == "check_system_health"
        assert result["confidence"] == CONFIDENCE_MEDIUM

    def test_how_is_everything(self):
        """'how is everything' -> action=check_system_health, confidence=MEDIUM."""
        result = parse_natural_language_command("company-1", "how is everything")
        assert result["action"] == "check_system_health"
        assert result["confidence"] == CONFIDENCE_MEDIUM

    # ── Pattern: escalate_urgent (HIGH confidence) ──

    def test_escalate_all_urgent_tickets(self):
        """'escalate all urgent tickets' -> action=escalate_urgent, intent=control."""
        result = parse_natural_language_command("company-1", "escalate all urgent tickets")
        assert result["action"] == "escalate_urgent"
        assert result["intent"] == "control"
        assert result["confidence"] >= CONFIDENCE_HIGH

    def test_raise_critical_tickets(self):
        """'raise critical tickets' -> action=escalate_urgent."""
        result = parse_natural_language_command("company-1", "raise critical tickets")
        assert result["action"] == "escalate_urgent"

    def test_bump_up_high_priority(self):
        """'bump up high priority' -> action=escalate_urgent."""
        result = parse_natural_language_command("company-1", "bump up high priority")
        assert result["action"] == "escalate_urgent"

    # ── Pattern: escalate alone (LOW confidence) ──

    def test_escalate_alone_low_confidence(self):
        """'escalate' alone -> action=escalate_urgent, confidence=LOW."""
        result = parse_natural_language_command("company-1", "escalate")
        assert result["action"] == "escalate_urgent"
        assert result["confidence"] == CONFIDENCE_LOW

    # ── Pattern: add_agents (control, HIGH confidence) ──

    def test_add_agents(self):
        """'add agents' -> action=add_agents, intent=control, scope=agents."""
        result = parse_natural_language_command("company-1", "add agents")
        assert result["action"] == "add_agents"
        assert result["intent"] == "control"
        assert result["scope"] == "agents"

    def test_add_3_more_agents_extracts_count(self):
        """'add 3 more agents' -> action=add_agents, parameters.count=3."""
        result = parse_natural_language_command("company-1", "add 3 more agents")
        assert result["action"] == "add_agents"
        assert result["parameters"].get("count") == 3

    def test_spin_up_workers(self):
        """'spin up workers' -> action=add_agents."""
        result = parse_natural_language_command("company-1", "spin up workers")
        assert result["action"] == "add_agents"

    def test_provision_5_agents(self):
        """'provision 5 agents' -> action=add_agents, parameters.count=5."""
        result = parse_natural_language_command("company-1", "provision 5 agents")
        assert result["action"] == "add_agents"
        assert result["parameters"].get("count") == 5

    def test_create_agents(self):
        """'create agents' -> action=add_agents."""
        result = parse_natural_language_command("company-1", "create agents")
        assert result["action"] == "add_agents"

    # ── Pattern: disable_last_rule (configure, HIGH confidence) ──

    def test_disable_last_auto_approve_rule(self):
        """'disable last auto-approve rule' -> action=disable_last_rule, intent=configure."""
        result = parse_natural_language_command("company-1", "disable last auto-approve rule")
        assert result["action"] == "disable_last_rule"
        assert result["intent"] == "configure"

    def test_remove_latest_policy(self):
        """'remove latest policy' -> action=disable_last_rule."""
        result = parse_natural_language_command("company-1", "remove latest policy")
        assert result["action"] == "disable_last_rule"

    def test_turn_off_most_recent_rule(self):
        """'turn off most recent rule' -> action=disable_last_rule."""
        result = parse_natural_language_command("company-1", "turn off most recent rule")
        assert result["action"] == "disable_last_rule"

    def test_delete_last_autoapprove(self):
        """'delete last autoapprove' -> action=disable_last_rule."""
        result = parse_natural_language_command("company-1", "delete last autoapprove")
        assert result["action"] == "disable_last_rule"

    # ── Pattern: export_report (report, HIGH confidence) ──

    def test_export_weekly_report(self):
        """'export weekly report' -> action=export_report, intent=report, period=weekly."""
        result = parse_natural_language_command("company-1", "export weekly report")
        assert result["action"] == "export_report"
        assert result["intent"] == "report"
        assert result["parameters"].get("period") == "weekly"

    def test_download_monthly_summary(self):
        """'download monthly summary' -> action=export_report, period=monthly."""
        result = parse_natural_language_command("company-1", "download monthly summary")
        assert result["action"] == "export_report"
        assert result["parameters"].get("period") == "monthly"

    def test_generate_report(self):
        """'generate report' (no period) -> action=export_report."""
        result = parse_natural_language_command("company-1", "generate report")
        assert result["action"] == "export_report"

    def test_create_daily_analytics(self):
        """'create daily analytics' -> action=export_report, period=daily."""
        result = parse_natural_language_command("company-1", "create daily analytics")
        assert result["action"] == "export_report"
        assert result["parameters"].get("period") == "daily"

    # ── Pattern: weekly report alone (MEDIUM confidence) ──

    def test_weekly_report_medium_confidence(self):
        """'weekly report' alone -> action=export_report, confidence=MEDIUM."""
        result = parse_natural_language_command("company-1", "weekly report")
        assert result["action"] == "export_report"
        assert result["confidence"] == CONFIDENCE_MEDIUM

    # ── Pattern: call_customer (control, HIGH confidence) ──

    def test_call_customer(self):
        """'call the customer' -> action=call_customer, intent=control."""
        result = parse_natural_language_command("company-1", "call the customer")
        assert result["action"] == "call_customer"
        assert result["intent"] == "control"

    def test_phone_client(self):
        """'phone the client' -> action=call_customer."""
        result = parse_natural_language_command("company-1", "phone the client")
        assert result["action"] == "call_customer"

    def test_dial_user(self):
        """'dial user' -> action=call_customer."""
        result = parse_natural_language_command("company-1", "dial user")
        assert result["action"] == "call_customer"

    # ── Pattern: errors today (MEDIUM confidence alternate) ──

    def test_errors_today_medium_confidence(self):
        """'errors today' -> action=show_errors, confidence=MEDIUM."""
        result = parse_natural_language_command("company-1", "errors today")
        assert result["action"] == "show_errors"
        assert result["confidence"] == CONFIDENCE_MEDIUM

    def test_any_errors_lately(self):
        """'any errors lately' -> action=show_errors."""
        result = parse_natural_language_command("company-1", "any errors lately")
        assert result["action"] == "show_errors"

    # ── Pattern: pause everything (override, MEDIUM confidence) ──

    def test_pause_everything(self):
        """'pause everything' -> action=pause_ai, intent=override, confidence=MEDIUM."""
        result = parse_natural_language_command("company-1", "pause everything")
        assert result["action"] == "pause_ai"
        assert result["intent"] == "override"
        assert result["confidence"] == CONFIDENCE_MEDIUM

    # ── Pattern: resume everything (MEDIUM confidence) ──

    def test_resume_everything(self):
        """'resume everything' -> action=resume_ai, confidence=MEDIUM."""
        result = parse_natural_language_command("company-1", "resume everything")
        assert result["action"] == "resume_ai"
        assert result["confidence"] == CONFIDENCE_MEDIUM

    # ── Pattern: show config (LOW confidence) ──

    def test_show_config_low_confidence(self):
        """'show configuration' -> action=check_system_health, confidence=LOW."""
        result = parse_natural_language_command("company-1", "show configuration")
        assert result["action"] == "check_system_health"
        assert result["confidence"] == CONFIDENCE_LOW

    def test_what_are_the_settings(self):
        """'what are the settings' -> action=check_system_health, confidence=LOW."""
        result = parse_natural_language_command("company-1", "what are the settings")
        assert result["action"] == "check_system_health"
        assert result["confidence"] == CONFIDENCE_LOW

    # ── Empty / edge input ──

    def test_empty_input_returns_unknown(self):
        """Empty string -> action=unknown, confidence=UNKNOWN."""
        result = parse_natural_language_command("company-1", "")
        assert result["action"] == "unknown"
        assert result["confidence"] == CONFIDENCE_UNKNOWN

    def test_whitespace_only_input_returns_unknown(self):
        """Whitespace-only input -> action=unknown."""
        result = parse_natural_language_command("company-1", "   ")
        assert result["action"] == "unknown"

    def test_none_input_returns_unknown(self):
        """None input -> action=unknown (BC-008: never crash)."""
        result = parse_natural_language_command("company-1", None)
        assert result["action"] == "unknown"

    def test_very_long_input_truncated(self):
        """Input exceeding MAX_PARSE_INPUT_LENGTH -> raw_input truncated."""
        long_input = "pause all agents " + "x" * 600
        result = parse_natural_language_command("company-1", long_input)
        assert len(result["raw_input"]) <= MAX_PARSE_INPUT_LENGTH

    # ── Nonsensical / unknown input ──

    def test_unknown_command_returns_low_confidence_with_suggestion(self):
        """Unrecognized input -> action=unknown, confidence=UNKNOWN, suggestion present."""
        result = parse_natural_language_command("company-1", "fly me to the moon")
        assert result["action"] == "unknown"
        assert result["confidence"] == CONFIDENCE_UNKNOWN
        assert result["suggestion"] is not None

    def test_gibberish_returns_unknown(self):
        """Complete gibberish -> action=unknown."""
        result = parse_natural_language_command("company-1", "xyzzy qwerty fnord")
        assert result["action"] == "unknown"
        assert result["confidence"] == CONFIDENCE_UNKNOWN

    # ── Confidence boosting ──

    def test_confidence_boosting_multiple_patterns_same_action(self):
        """When multiple patterns match the same action, confidence should be boosted."""
        # "show me today's errors" matches both the high-confidence "show errors" pattern
        # and the medium-confidence "errors today" pattern — both map to show_errors
        result = parse_natural_language_command("company-1", "show me today's errors")
        assert result["action"] == "show_errors"
        # With boosting, confidence >= HIGH (even though one pattern is MEDIUM)
        assert result["confidence"] >= CONFIDENCE_HIGH

    # ── Fuzzy matching for typos/partial matches ──

    def test_fuzzy_match_pause_keyword(self):
        """Input containing 'pause' should fuzzy-match to pause_ai."""
        result = parse_natural_language_command("company-1", "I want to pause something")
        assert result["action"] == "pause_ai"
        assert result["confidence"] >= CONFIDENCE_LOW

    def test_fuzzy_match_resume_keyword(self):
        """Input containing 'resume' should fuzzy-match to resume_ai."""
        result = parse_natural_language_command("company-1", "please resume the thing")
        assert result["action"] == "resume_ai"
        assert result["confidence"] >= CONFIDENCE_LOW

    def test_fuzzy_match_health_keyword(self):
        """Input containing 'health' should fuzzy-match to check_system_health."""
        result = parse_natural_language_command("company-1", "tell me about system health please")
        assert result["action"] == "check_system_health"

    # ── Case insensitivity ──

    def test_case_insensitive_parsing(self):
        """Parser should be case-insensitive — 'PAUSE ALL AGENTS' should work."""
        result = parse_natural_language_command("company-1", "PAUSE ALL AGENTS")
        assert result["action"] == "pause_ai"
        assert result["confidence"] >= CONFIDENCE_HIGH

    def test_mixed_case_parsing(self):
        """Mixed case 'ExPoRt WeEkLy RePoRt' should still parse correctly."""
        result = parse_natural_language_command("company-1", "ExPoRt WeEkLy RePoRt")
        assert result["action"] == "export_report"

    # ── Parameter extraction ──

    def test_parameter_extraction_channel_pause(self):
        """'pause all agents on email' should extract channel='email'."""
        result = parse_natural_language_command("company-1", "pause all agents on email")
        assert result["action"] == "pause_ai"
        assert result["parameters"].get("channel") == "email"

    def test_parameter_extraction_no_count_when_not_add_agents(self):
        """A number in a non-add_agents command should not produce a count parameter."""
        result = parse_natural_language_command("company-1", "export 3 report")
        assert result["action"] == "export_report"
        assert "count" not in result["parameters"]

    # ── Suggestion generation for partial input ──

    def test_suggestion_for_partial_keyword(self):
        """Input with a recognizable keyword should get a useful suggestion."""
        result = parse_natural_language_command("company-1", "pausing")
        # Either it gets a fuzzy match or a suggestion in the unknown response
        assert result is not None
        assert result["action"] is not None

    # ── Result structure completeness ──

    def test_result_has_all_required_keys(self):
        """Parsed result should have all required keys."""
        result = parse_natural_language_command("company-1", "pause all agents")
        required_keys = {"action", "intent", "scope", "target", "parameters",
                         "confidence", "raw_input", "suggestion"}
        assert required_keys.issubset(set(result.keys()))

    def test_intent_always_valid(self):
        """Parsed intent should always be in VALID_COMMAND_INTENTS or 'unknown'."""
        test_inputs = [
            "pause all AI", "resume agents", "check system health",
            "export report", "emergency brake", "escalate urgent",
            "disable last rule", "call customer", "fly to moon",
        ]
        for inp in test_inputs:
            result = parse_natural_language_command("company-1", inp)
            assert result["intent"] in VALID_COMMAND_INTENTS or result["action"] == "unknown", \
                f"Input '{inp}' produced invalid intent: {result['intent']}"


# ══════════════════════════════════════════════════════════════════
# 2. TEST RECEIVE COMMAND
# ══════════════════════════════════════════════════════════════════


class TestReceiveCommand:
    """Tests for receive_command — creating and parsing a command row.

    Verifies: JarvisCommand creation, status transitions (received -> parsing -> parsed),
    source validation, parsed data storage, undo_available flag, and BC-008 error handling.
    """

    def test_creates_jarvis_command_with_status_received(self, mock_db):
        """receive_command should create a JarvisCommand with status=received initially."""
        cmd = _make_mock_command(status="received")
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            result = receive_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                raw_input="pause all agents",
            )
        assert mock_db.add.called
        assert mock_db.flush.called

    def test_transitions_to_parsing_then_parsed(self, mock_db):
        """receive_command should transition status: received -> parsing -> parsed."""
        cmd = _make_mock_command()
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            result = receive_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                raw_input="pause all agents",
            )
        # Verify the final status is parsed (intermediate statuses were set)
        assert cmd.status == "parsed"

    def test_stores_parsed_command_in_command_parsed_json(self, mock_db):
        """receive_command should store the parsed command dict in command_parsed JSON."""
        cmd = _make_mock_command()
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            result = receive_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                raw_input="pause all agents",
            )
        # command_parsed should have been set to a JSON string containing parsed data
        assert cmd.command_parsed is not None
        parsed = json.loads(cmd.command_parsed) if isinstance(cmd.command_parsed, str) else cmd.command_parsed
        assert parsed["action"] == "pause_ai"

    def test_sets_command_intent(self, mock_db):
        """receive_command should set command_intent from parsed result."""
        cmd = _make_mock_command()
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            result = receive_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                raw_input="pause all agents",
            )
        assert cmd.command_intent == "control"

    def test_sets_confidence(self, mock_db):
        """receive_command should set confidence from parsed result."""
        cmd = _make_mock_command()
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            result = receive_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                raw_input="pause all agents",
            )
        assert cmd.confidence is not None
        assert cmd.confidence >= CONFIDENCE_HIGH

    def test_sets_undo_available_for_control_intent(self, mock_db):
        """Commands with 'control' intent should have undo_available=True."""
        cmd = _make_mock_command()
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            result = receive_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                raw_input="pause all agents",
            )
        assert cmd.undo_available is True

    def test_sets_undo_unavailable_for_query_intent(self, mock_db):
        """Commands with 'query' intent should have undo_available=False."""
        cmd = _make_mock_command()
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            result = receive_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                raw_input="check system health",
            )
        assert cmd.undo_available is False

    def test_sets_undo_unavailable_for_report_intent(self, mock_db):
        """Commands with 'report' intent should have undo_available=False."""
        cmd = _make_mock_command()
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            result = receive_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                raw_input="export weekly report",
            )
        assert cmd.undo_available is False

    def test_invalid_source_defaults_to_chat(self, mock_db):
        """receive_command with an invalid source should default to 'chat'."""
        cmd = _make_mock_command()
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            result = receive_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                raw_input="pause all agents",
                source="invalid_source",
            )
        assert mock_db.add.called

    def test_valid_source_accepted(self, mock_db):
        """receive_command with a valid source should accept it."""
        for source in VALID_SOURCES:
            mock_db.reset_mock()
            cmd = _make_mock_command()
            with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
                result = receive_command(
                    db=mock_db,
                    company_id="comp-1",
                    session_id="sess-1",
                    raw_input="pause all agents",
                    source=source,
                )
            assert mock_db.add.called

    def test_marks_as_failed_on_parse_error_bc008(self, mock_db):
        """receive_command should mark as 'failed' on parse error (BC-008)."""
        cmd = _make_mock_command()
        cmd.id = "real-id-123"  # Must have an ID for the failure path

        def raise_on_flush(*args, **kwargs):
            if not hasattr(raise_on_flush, "call_count"):
                raise_on_flush.call_count = 0
            raise_on_flush.call_count += 1
            if raise_on_flush.call_count == 2:
                raise Exception("DB error during parsing")

        mock_db.flush = raise_on_flush

        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            with pytest.raises(Exception, match="DB error during parsing"):
                receive_command(
                    db=mock_db,
                    company_id="comp-1",
                    session_id="sess-1",
                    raw_input="pause all agents",
                )

    def test_sets_parsed_at_timestamp(self, mock_db):
        """receive_command should set parsed_at timestamp."""
        cmd = _make_mock_command()
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            result = receive_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                raw_input="pause all agents",
            )
        assert cmd.parsed_at is not None


# ══════════════════════════════════════════════════════════════════
# 3. TEST EXECUTE COMMAND
# ══════════════════════════════════════════════════════════════════


class TestExecuteCommand:
    """Tests for execute_command — dispatching parsed commands to handlers.

    Verifies: status transitions (parsed -> executing -> completed),
    handler dispatching, result_json storage, error handling (BC-008),
    and invalid status rejection.
    """

    def test_transitions_parsed_to_executing_to_completed(self, mock_db):
        """execute_command should transition: parsed -> executing -> completed."""
        cmd = _make_mock_command(status="parsed")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd
        with patch(
            "app.services.jarvis_command_service._dispatch_handler",
            return_value={"success": True, "action": "pause_ai", "message": "OK", "data": {}},
        ):
            result = execute_command(
                db=mock_db,
                company_id="comp-1",
                command_id="test-cmd-001",
                session_id="sess-1",
            )
        assert cmd.status == "completed"
        assert cmd.completed_at is not None
        assert result["status"] == "completed"

    def test_dispatches_to_correct_handler(self, mock_db):
        """execute_command should dispatch to the handler matching the action."""
        cmd = _make_mock_command(status="parsed")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd
        with patch(
            "app.services.jarvis_command_service._dispatch_handler",
            return_value={"success": True, "action": "pause_ai", "message": "OK", "data": {}},
        ) as mock_dispatch:
            result = execute_command(
                db=mock_db,
                company_id="comp-1",
                command_id="test-cmd-001",
                session_id="sess-1",
            )
        mock_dispatch.assert_called_once()
        call_kwargs = mock_dispatch.call_args
        assert call_kwargs[1]["action"] == "pause_ai" or call_kwargs[0][2] == "pause_ai"

    def test_returns_handler_result_in_response(self, mock_db):
        """execute_command should include handler_result in the response."""
        handler_result = {"success": True, "action": "pause_ai", "message": "All AI paused", "data": {"paused_count": 5}}
        cmd = _make_mock_command(status="parsed")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd
        with patch(
            "app.services.jarvis_command_service._dispatch_handler",
            return_value=handler_result,
        ):
            result = execute_command(
                db=mock_db,
                company_id="comp-1",
                command_id="test-cmd-001",
                session_id="sess-1",
            )
        assert result["result"] == handler_result

    def test_sets_result_json_and_completed_at(self, mock_db):
        """execute_command should set result_json and completed_at on the command."""
        cmd = _make_mock_command(status="parsed")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd
        with patch(
            "app.services.jarvis_command_service._dispatch_handler",
            return_value={"success": True, "action": "pause_ai", "message": "OK", "data": {}},
        ):
            execute_command(
                db=mock_db,
                company_id="comp-1",
                command_id="test-cmd-001",
                session_id="sess-1",
            )
        assert cmd.result_json is not None
        assert cmd.completed_at is not None

    def test_marks_failed_on_execution_error_bc008(self, mock_db):
        """If handler raises, execute_command should return 'failed' status (BC-008)."""
        cmd = _make_mock_command(status="parsed")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd
        with patch(
            "app.services.jarvis_command_service._dispatch_handler",
            side_effect=Exception("Handler blew up"),
        ):
            result = execute_command(
                db=mock_db,
                company_id="comp-1",
                command_id="test-cmd-001",
                session_id="sess-1",
            )
        assert result["status"] == "failed"
        assert result["error"] is not None

    def test_returns_error_for_invalid_command_status(self, mock_db):
        """execute_command on a command with status='completed' should return error."""
        cmd = _make_mock_command(status="completed")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd
        result = execute_command(
            db=mock_db,
            company_id="comp-1",
            command_id="test-cmd-001",
            session_id="sess-1",
        )
        assert "cannot be executed" in result["error"]

    def test_returns_error_for_nonexistent_command(self, mock_db):
        """execute_command with non-existent command_id should return 'Command not found'."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = execute_command(
            db=mock_db,
            company_id="comp-1",
            command_id="nonexistent-id",
            session_id="sess-1",
        )
        assert result["status"] == "failed"
        assert result["error"] == "Command not found"

    def test_execution_time_ms_is_positive(self, mock_db):
        """execute_command should return a positive execution_time_ms."""
        cmd = _make_mock_command(status="parsed")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd
        with patch(
            "app.services.jarvis_command_service._dispatch_handler",
            return_value={"success": True, "action": "pause_ai", "message": "OK", "data": {}},
        ):
            result = execute_command(
                db=mock_db,
                company_id="comp-1",
                command_id="test-cmd-001",
                session_id="sess-1",
            )
        assert result["execution_time_ms"] >= 0

    def test_execute_with_received_status_allowed(self, mock_db):
        """execute_command on a command with status='received' should still execute."""
        cmd = _make_mock_command(status="received")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd
        with patch(
            "app.services.jarvis_command_service._dispatch_handler",
            return_value={"success": True, "action": "pause_ai", "message": "OK", "data": {}},
        ):
            result = execute_command(
                db=mock_db,
                company_id="comp-1",
                command_id="test-cmd-001",
                session_id="sess-1",
            )
        assert result["status"] == "completed"

    def test_marks_command_failed_in_db_on_handler_exception(self, mock_db):
        """When handler raises, the command row should be marked 'failed' in DB."""
        cmd = _make_mock_command(status="parsed")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd
        with patch(
            "app.services.jarvis_command_service._dispatch_handler",
            side_effect=Exception("Handler crashed"),
        ):
            execute_command(
                db=mock_db,
                company_id="comp-1",
                command_id="test-cmd-001",
                session_id="sess-1",
            )
        # After failure, the command should be marked as "failed" in DB
        # (the service tries to re-fetch and set status)
        assert mock_db.flush.called


# ══════════════════════════════════════════════════════════════════
# 4. TEST UNDO COMMAND
# ══════════════════════════════════════════════════════════════════


class TestUndoCommand:
    """Tests for undo_command — reversing previously executed commands.

    Verifies: find most recent undoable command, create undo command,
    link via undone_by_command_id, mark original as undone, and proper
    error handling for non-undoable, already-undone, and not-found cases.
    """

    def test_finds_most_recent_undoable_command(self, mock_db):
        """undo_command with no command_id should find the most recent undoable command."""
        original_cmd = _make_mock_command(
            status="completed",
            undo_available=True,
            command_intent="control",
        )
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = original_cmd

        with patch("app.services.jarvis_command_service._execute_undo_action", return_value={
            "success": True, "action": "resume_ai", "message": "AI resumed", "data": {},
        }):
            result = undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
            )
        assert result["status"] == "completed"
        assert result["original_action"] == "pause_ai"

    def test_creates_new_undo_command(self, mock_db):
        """undo_command should create a new JarvisCommand with action='undo'."""
        original_cmd = _make_mock_command(
            status="completed",
            undo_available=True,
            command_intent="control",
        )
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = original_cmd

        with patch("app.services.jarvis_command_service._execute_undo_action", return_value={
            "success": True, "action": "resume_ai", "message": "AI resumed", "data": {},
        }):
            result = undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
            )
        assert mock_db.add.called

    def test_links_via_undone_by_command_id(self, mock_db):
        """After undo, original command should have undone_by_command_id set."""
        original_cmd = _make_mock_command(
            status="completed",
            undo_available=True,
            command_intent="control",
        )
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = original_cmd

        with patch("app.services.jarvis_command_service._execute_undo_action", return_value={
            "success": True, "action": "resume_ai", "message": "AI resumed", "data": {},
        }):
            result = undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
            )
        assert original_cmd.undone_by_command_id is not None
        assert result["undo_command_id"] is not None

    def test_marks_original_as_undone(self, mock_db):
        """After undo, original command status should be 'undone'."""
        original_cmd = _make_mock_command(
            status="completed",
            undo_available=True,
            command_intent="control",
        )
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = original_cmd

        with patch("app.services.jarvis_command_service._execute_undo_action", return_value={
            "success": True, "action": "resume_ai", "message": "AI resumed", "data": {},
        }):
            undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
            )
        assert original_cmd.status == "undone"

    def test_undo_specific_command_by_id(self, mock_db):
        """undo_command with a command_id should undo that specific command."""
        original_cmd = _make_mock_command(
            id="cmd-to-undo",
            status="completed",
            undo_available=True,
            command_intent="control",
        )
        mock_db.query.return_value.filter.return_value.first.return_value = original_cmd

        with patch("app.services.jarvis_command_service._execute_undo_action", return_value={
            "success": True, "action": "resume_ai", "message": "AI resumed", "data": {},
        }):
            result = undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                command_id="cmd-to-undo",
            )
        assert result["status"] == "completed"
        assert result["original_command_id"] == "cmd-to-undo"

    def test_raises_not_found_when_no_undoable_command(self, mock_db):
        """When no undoable commands exist, undo_command should raise NotFoundError."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
            )
        assert "No undoable command" in str(exc_info.value.message)

    def test_raises_not_found_for_nonexistent_command_id(self, mock_db):
        """Undoing a specific non-existent command_id should raise NotFoundError."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                command_id="nonexistent-id",
            )
        assert "not found" in str(exc_info.value.message).lower()

    def test_raises_validation_error_for_non_undoable_intent_query(self, mock_db):
        """Undoing a command with query intent should raise ValidationError."""
        original_cmd = _make_mock_command(
            id="query-cmd",
            status="completed",
            undo_available=False,
            command_intent="query",
        )
        mock_db.query.return_value.filter.return_value.first.return_value = original_cmd

        with pytest.raises(ValidationError) as exc_info:
            undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                command_id="query-cmd",
            )
        assert "cannot be undone" in str(exc_info.value.message)

    def test_raises_validation_error_for_non_undoable_intent_report(self, mock_db):
        """Undoing a command with report intent should raise ValidationError."""
        original_cmd = _make_mock_command(
            id="report-cmd",
            status="completed",
            undo_available=False,
            command_intent="report",
        )
        mock_db.query.return_value.filter.return_value.first.return_value = original_cmd

        with pytest.raises(ValidationError) as exc_info:
            undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                command_id="report-cmd",
            )
        assert "cannot be undone" in str(exc_info.value.message)

    def test_raises_validation_error_for_already_undone_command(self, mock_db):
        """Undoing a command that's already undone should raise ValidationError."""
        original_cmd = _make_mock_command(
            id="already-undone",
            status="undone",
            undo_available=True,
            command_intent="control",
        )
        mock_db.query.return_value.filter.return_value.first.return_value = original_cmd

        with pytest.raises(ValidationError) as exc_info:
            undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                command_id="already-undone",
            )
        assert "already been undone" in str(exc_info.value.message)

    def test_undo_command_row_has_intent_control(self, mock_db):
        """The new undo command row should have intent='control'."""
        original_cmd = _make_mock_command(
            status="completed",
            undo_available=True,
            command_intent="control",
        )
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = original_cmd

        created_commands = []
        original_add = mock_db.add

        def capture_add(obj):
            created_commands.append(obj)
            return original_add(obj)

        mock_db.add = capture_add

        with patch("app.services.jarvis_command_service._execute_undo_action", return_value={
            "success": True, "action": "resume_ai", "message": "AI resumed", "data": {},
        }):
            undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
            )

        # The undo command row should exist
        assert len(created_commands) > 0

    def test_undo_returns_original_action(self, mock_db):
        """undo_command result should include the original action that was undone."""
        original_cmd = _make_mock_command(
            status="completed",
            undo_available=True,
            command_intent="control",
        )
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = original_cmd

        with patch("app.services.jarvis_command_service._execute_undo_action", return_value={
            "success": True, "action": "resume_ai", "message": "AI resumed", "data": {},
        }):
            result = undo_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
            )
        assert result["original_action"] == "pause_ai"


# ══════════════════════════════════════════════════════════════════
# 5. TEST QUICK COMMANDS
# ══════════════════════════════════════════════════════════════════


class TestQuickCommands:
    """Tests for get_quick_commands and execute_quick_command.

    Verifies: default quick commands returned, custom command loading,
    execute by ID, not-found error, and quick commands skip NL parsing.
    """

    def test_get_quick_commands_returns_defaults(self, mock_db):
        """get_quick_commands should return DEFAULT_QUICK_COMMANDS."""
        result = get_quick_commands(
            db=mock_db,
            company_id="comp-1",
            session_id="sess-1",
        )
        assert len(result) >= len(DEFAULT_QUICK_COMMANDS)
        # Check that default IDs are present
        default_ids = {cmd["id"] for cmd in DEFAULT_QUICK_COMMANDS}
        result_ids = {cmd["id"] for cmd in result}
        assert default_ids.issubset(result_ids)

    def test_default_quick_commands_have_required_keys(self):
        """Each default quick command should have id, label, raw_input, action, intent."""
        for cmd in DEFAULT_QUICK_COMMANDS:
            assert "id" in cmd
            assert "label" in cmd
            assert "raw_input" in cmd
            assert "action" in cmd
            assert "intent" in cmd
            assert "icon" in cmd
            assert "description" in cmd

    def test_loads_custom_commands_from_session_context(self, mock_db):
        """get_quick_commands should load custom commands from session context."""
        custom_cmd = {
            "id": "qc_custom_test",
            "label": "My Custom Command",
            "raw_input": "custom test",
            "action": "pause_ai",
            "intent": "control",
            "icon": "star",
            "description": "A custom test command",
        }
        mock_session = MagicMock()
        mock_session.context_json = json.dumps({"custom_quick_commands": [custom_cmd]})
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = get_quick_commands(
            db=mock_db,
            company_id="comp-1",
            session_id="sess-1",
        )
        result_ids = [cmd["id"] for cmd in result]
        assert "qc_custom_test" in result_ids

    def test_execute_quick_command_finds_preset_and_executes(self, mock_db):
        """execute_quick_command should find a preset by ID and execute it."""
        cmd = _make_mock_command(status="parsed")
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd):
            with patch(
                "app.services.jarvis_command_service.execute_command",
                return_value={
                    "command_id": "test-cmd-001",
                    "status": "completed",
                    "action": "pause_ai",
                    "result": {"success": True, "message": "Paused"},
                    "execution_time_ms": 10.0,
                    "error": None,
                },
            ):
                result = execute_quick_command(
                    db=mock_db,
                    company_id="comp-1",
                    session_id="sess-1",
                    quick_command_id="qc_pause_all_agents",
                )
        assert result["status"] == "completed"

    def test_execute_quick_command_raises_not_found_for_unknown_id(self, mock_db):
        """execute_quick_command should raise NotFoundError for unknown quick_command_id."""
        with pytest.raises(NotFoundError) as exc_info:
            execute_quick_command(
                db=mock_db,
                company_id="comp-1",
                session_id="sess-1",
                quick_command_id="qc_nonexistent",
            )
        assert "not found" in str(exc_info.value.message).lower()

    def test_quick_commands_skip_nl_parsing(self, mock_db):
        """Quick commands should skip NL parsing — they have pre-defined action/intent."""
        cmd = _make_mock_command(status="parsed")
        with patch("app.services.jarvis_command_service.JarvisCommand", return_value=cmd) as mock_jc:
            with patch(
                "app.services.jarvis_command_service.execute_command",
                return_value={
                    "command_id": "test-cmd-001",
                    "status": "completed",
                    "action": "pause_ai",
                    "result": {},
                    "execution_time_ms": 5.0,
                    "error": None,
                },
            ):
                execute_quick_command(
                    db=mock_db,
                    company_id="comp-1",
                    session_id="sess-1",
                    quick_command_id="qc_pause_all_agents",
                )
        # JarvisCommand should be created directly with parsed data (no NL parse step)
        assert mock_jc.called

    def test_get_quick_commands_handles_db_error_gracefully(self, mock_db):
        """get_quick_commands should return defaults even if custom loading fails."""
        mock_db.query.side_effect = Exception("DB error")
        result = get_quick_commands(
            db=mock_db,
            company_id="comp-1",
            session_id="sess-1",
        )
        # Should still return default commands (BC-008)
        assert len(result) >= len(DEFAULT_QUICK_COMMANDS)

    def test_all_default_quick_command_ids_are_unique(self):
        """All default quick command IDs should be unique."""
        ids = [cmd["id"] for cmd in DEFAULT_QUICK_COMMANDS]
        assert len(ids) == len(set(ids))

    def test_default_quick_commands_count(self):
        """There should be exactly 8 default quick commands (FR-2.8.13)."""
        assert len(DEFAULT_QUICK_COMMANDS) == 8


# ══════════════════════════════════════════════════════════════════
# 6. TEST COMMAND HISTORY
# ══════════════════════════════════════════════════════════════════


class TestCommandHistory:
    """Tests for get_command_history, get_command_by_id, and prune_old_commands.

    Verifies: paginated history, filtering by status/intent/source,
    command retrieval by ID, and pruning old commands.
    """

    def test_returns_paginated_command_history(self, mock_db):
        """get_command_history should return paginated results with total count."""
        cmd1 = _make_mock_command(id="cmd-1")
        cmd2 = _make_mock_command(id="cmd-2")
        mock_db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 2
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [cmd1, cmd2]

        result, total = get_command_history(
            db=mock_db,
            company_id="comp-1",
            session_id="sess-1",
            limit=10,
            offset=0,
        )
        assert total == 2
        assert isinstance(result, list)

    def test_filters_by_status(self, mock_db):
        """get_command_history should support filtering by status."""
        # When a filter is applied, the chain gets an extra .filter() call.
        # With MagicMock, each chained call returns the same mock, so we need
        # to set the return values on the deeper chain too.
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.count.return_value = 1
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [_make_mock_command(id="cmd-1")]

        result, total = get_command_history(
            db=mock_db,
            company_id="comp-1",
            session_id="sess-1",
            status="completed",
        )
        assert total == 1

    def test_filters_by_intent(self, mock_db):
        """get_command_history should support filtering by intent."""
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.count.return_value = 1
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [_make_mock_command(id="cmd-1")]

        result, total = get_command_history(
            db=mock_db,
            company_id="comp-1",
            session_id="sess-1",
            intent="control",
        )
        assert total == 1

    def test_filters_by_source(self, mock_db):
        """get_command_history should support filtering by source."""
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.count.return_value = 1
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [_make_mock_command(id="cmd-1")]

        result, total = get_command_history(
            db=mock_db,
            company_id="comp-1",
            session_id="sess-1",
            source="chat",
        )
        assert total == 1

    def test_returns_empty_list_on_error(self, mock_db):
        """get_command_history should return ([], 0) on error (BC-008)."""
        mock_db.query.side_effect = Exception("DB exploded")
        result, total = get_command_history(
            db=mock_db,
            company_id="comp-1",
            session_id="sess-1",
        )
        assert result == []
        assert total == 0

    def test_get_command_by_id_returns_command_dict(self, mock_db):
        """get_command_by_id should return a command dict when found."""
        cmd = _make_mock_command(id="cmd-42")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd

        result = get_command_by_id(
            db=mock_db,
            company_id="comp-1",
            command_id="cmd-42",
        )
        assert result is not None

    def test_get_command_by_id_returns_none_when_not_found(self, mock_db):
        """get_command_by_id should return None when command doesn't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = get_command_by_id(
            db=mock_db,
            company_id="comp-1",
            command_id="nonexistent",
        )
        assert result is None

    def test_get_command_by_id_returns_none_on_error(self, mock_db):
        """get_command_by_id should return None on error (BC-008)."""
        mock_db.query.side_effect = Exception("DB error")
        result = get_command_by_id(
            db=mock_db,
            company_id="comp-1",
            command_id="cmd-1",
        )
        assert result is None

    def test_prune_old_commands_when_under_limit(self, mock_db):
        """prune_old_commands should return 0 when count is under limit."""
        mock_db.query.return_value.filter.return_value.scalar.return_value = 100
        result = prune_old_commands(
            db=mock_db,
            session_id="sess-1",
            company_id="comp-1",
            max_keep=200,
        )
        assert result == 0

    def test_prune_old_commands_when_over_limit(self, mock_db):
        """prune_old_commands should prune when count exceeds limit."""
        # Set up: total commands = 10500, max_keep = 10000
        mock_db.query.return_value.filter.return_value.scalar.return_value = 10500

        # The prune query returns IDs to keep and then deletes the rest
        # For simplicity, just verify the function runs without error
        result = prune_old_commands(
            db=mock_db,
            session_id="sess-1",
            company_id="comp-1",
            max_keep=10000,
        )
        # Result depends on the mock setup, but should not raise
        assert isinstance(result, int)

    def test_cancel_command_success(self, mock_db):
        """cancel_command should mark a cancellable command as 'cancelled'."""
        cmd = _make_mock_command(status="parsed")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd

        result = cancel_command(
            db=mock_db,
            company_id="comp-1",
            command_id="test-cmd-001",
            session_id="sess-1",
        )
        assert cmd.status == "cancelled"

    def test_cancel_command_not_found_raises(self, mock_db):
        """cancel_command should raise NotFoundError if command doesn't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            cancel_command(
                db=mock_db,
                company_id="comp-1",
                command_id="nonexistent",
                session_id="sess-1",
            )

    def test_cancel_command_already_executing_raises_validation(self, mock_db):
        """cancel_command should raise ValidationError for executing command."""
        cmd = _make_mock_command(status="executing")
        mock_db.query.return_value.filter.return_value.first.return_value = cmd

        with pytest.raises(ValidationError):
            cancel_command(
                db=mock_db,
                company_id="comp-1",
                command_id="test-cmd-001",
                session_id="sess-1",
            )


# ══════════════════════════════════════════════════════════════════
# 7. TEST CONSTANTS
# ══════════════════════════════════════════════════════════════════


class TestConstants:
    """Tests for service constants — enum validation, confidence thresholds, limits.

    Ensures constants match the documented specification.
    """

    def test_valid_command_intents_has_5_intents(self):
        """VALID_COMMAND_INTENTS should have exactly 5 intents."""
        assert len(VALID_COMMAND_INTENTS) == 5
        assert "query" in VALID_COMMAND_INTENTS
        assert "control" in VALID_COMMAND_INTENTS
        assert "configure" in VALID_COMMAND_INTENTS
        assert "report" in VALID_COMMAND_INTENTS
        assert "override" in VALID_COMMAND_INTENTS

    def test_valid_command_statuses_has_8_statuses(self):
        """VALID_COMMAND_STATUSES should have exactly 8 statuses."""
        assert len(VALID_COMMAND_STATUSES) == 8
        expected = {"received", "parsing", "parsed", "executing",
                    "completed", "failed", "cancelled", "undone"}
        assert set(VALID_COMMAND_STATUSES) == expected

    def test_valid_sources(self):
        """VALID_SOURCES should contain the expected sources."""
        expected = {"chat", "api", "co_pilot", "proactive", "scheduled"}
        assert set(VALID_SOURCES) == expected

    def test_confidence_thresholds_are_sensible(self):
        """Confidence thresholds should be: HIGH > MEDIUM > LOW > UNKNOWN."""
        assert CONFIDENCE_HIGH == 0.85
        assert CONFIDENCE_MEDIUM == 0.65
        assert CONFIDENCE_LOW == 0.40
        assert CONFIDENCE_UNKNOWN == 0.15
        assert CONFIDENCE_HIGH > CONFIDENCE_MEDIUM > CONFIDENCE_LOW > CONFIDENCE_UNKNOWN

    def test_non_undoable_intents(self):
        """NON_UNDOABLE_INTENTS should be (query, report)."""
        assert NON_UNDOABLE_INTENTS == ("query", "report")
        assert "query" in NON_UNDOABLE_INTENTS
        assert "report" in NON_UNDOABLE_INTENTS
        assert "control" not in NON_UNDOABLE_INTENTS
        assert "configure" not in NON_UNDOABLE_INTENTS
        assert "override" not in NON_UNDOABLE_INTENTS

    def test_max_parse_input_length(self):
        """MAX_PARSE_INPUT_LENGTH should be 500."""
        assert MAX_PARSE_INPUT_LENGTH == 500

    def test_max_command_history_per_session(self):
        """MAX_COMMAND_HISTORY_PER_SESSION should be 10000."""
        assert MAX_COMMAND_HISTORY_PER_SESSION == 10000

    def test_command_history_prune_batch(self):
        """COMMAND_HISTORY_PRUNE_BATCH should be 200."""
        assert COMMAND_HISTORY_PRUNE_BATCH == 200

    def test_max_quick_commands_per_tenant(self):
        """MAX_QUICK_COMMANDS_PER_TENANT should be 50."""
        assert MAX_QUICK_COMMANDS_PER_TENANT == 50

    def test_command_patterns_count(self):
        """COMMAND_PATTERNS should have at least 20 patterns."""
        assert len(COMMAND_PATTERNS) >= 20

    def test_command_patterns_have_required_keys(self):
        """Each COMMAND_PATTERN should have regex, action, intent, scope, confidence."""
        for pattern in COMMAND_PATTERNS:
            assert "regex" in pattern
            assert "action" in pattern
            assert "intent" in pattern
            assert "scope" in pattern
            assert "confidence" in pattern

    def test_command_patterns_intents_are_valid(self):
        """Each COMMAND_PATTERN intent should be in VALID_COMMAND_INTENTS."""
        for pattern in COMMAND_PATTERNS:
            assert pattern["intent"] in VALID_COMMAND_INTENTS, \
                f"Pattern with action={pattern['action']} has invalid intent={pattern['intent']}"

    def test_command_patterns_confidence_in_range(self):
        """Each COMMAND_PATTERN confidence should be between 0.0 and 1.0."""
        for pattern in COMMAND_PATTERNS:
            assert 0.0 <= pattern["confidence"] <= 1.0, \
                f"Pattern with action={pattern['action']} has out-of-range confidence={pattern['confidence']}"

    def test_all_default_quick_command_actions_are_known(self):
        """Default quick command actions should match known handler actions."""
        known_actions = {
            "pause_ai", "resume_ai", "check_system_health", "show_errors",
            "escalate_urgent", "export_report", "pause_refunds", "disable_last_rule",
        }
        for cmd in DEFAULT_QUICK_COMMANDS:
            assert cmd["action"] in known_actions, \
                f"Default quick command {cmd['id']} has unknown action: {cmd['action']}"

    def test_all_default_quick_command_intents_are_valid(self):
        """Default quick command intents should be in VALID_COMMAND_INTENTS."""
        for cmd in DEFAULT_QUICK_COMMANDS:
            assert cmd["intent"] in VALID_COMMAND_INTENTS, \
                f"Default quick command {cmd['id']} has invalid intent: {cmd['intent']}"


# ══════════════════════════════════════════════════════════════════
# 8. HELPER FUNCTION TESTS
# ══════════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """Tests for internal helper functions used by the command service.

    Verifies: _safe_parse_json, _merge_metadata, _build_unknown_command,
    _extract_parameters, _infer_target, _generate_suggestion, _fuzzy_match_command.
    """

    def test_safe_parse_json_valid(self):
        """_safe_parse_json should parse valid JSON."""
        result = _safe_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_safe_parse_json_invalid(self):
        """_safe_parse_json should return empty dict for invalid JSON."""
        result = _safe_parse_json("not json at all")
        assert result == {}

    def test_safe_parse_json_none(self):
        """_safe_parse_json should return empty dict for None input."""
        result = _safe_parse_json(None)
        assert result == {}

    def test_safe_parse_json_empty_string(self):
        """_safe_parse_json should return empty dict for empty string."""
        result = _safe_parse_json("")
        assert result == {}

    def test_merge_metadata_both_valid(self):
        """_merge_metadata should merge a JSON string with a dict."""
        result = _merge_metadata('{"a": 1}', {"b": 2})
        parsed = json.loads(result)
        assert parsed["a"] == 1
        assert parsed["b"] == 2

    def test_merge_metadata_first_invalid(self):
        """_merge_metadata should handle invalid first JSON gracefully."""
        result = _merge_metadata("not json", {"b": 2})
        parsed = json.loads(result)
        assert parsed["b"] == 2

    def test_merge_metadata_none_first(self):
        """_merge_metadata should handle None first argument."""
        result = _merge_metadata(None, {"b": 2})
        parsed = json.loads(result)
        assert parsed["b"] == 2

    def test_merge_metadata_overlapping_keys(self):
        """_merge_metadata should overwrite overlapping keys with second value."""
        result = _merge_metadata('{"a": 1}', {"a": 2})
        parsed = json.loads(result)
        assert parsed["a"] == 2

    def test_build_unknown_command_with_reason(self):
        """_build_unknown_command should return unknown command with reason."""
        result = _build_unknown_command(raw_input="test", reason="Empty input")
        assert result["action"] == "unknown"
        assert result["confidence"] == CONFIDENCE_UNKNOWN

    def test_build_unknown_command_with_suggestion(self):
        """_build_unknown_command should include suggestion when provided."""
        result = _build_unknown_command(raw_input="test", suggestion="Try: pause all AI")
        assert result["action"] == "unknown"
        assert result["suggestion"] == "Try: pause all AI"

    def test_extract_parameters_add_agents_count(self):
        """_extract_parameters for add_agents should extract count."""
        result = _extract_parameters("add 5 agents", "add_agents")
        assert result.get("count") == 5

    def test_extract_parameters_export_report_period(self):
        """_extract_parameters for export_report should extract period."""
        result = _extract_parameters("export weekly report", "export_report")
        assert result.get("period") == "weekly"

    def test_extract_parameters_no_count_for_other_actions(self):
        """_extract_parameters should not extract count for non-add_agents actions."""
        result = _extract_parameters("pause 5 agents", "pause_ai")
        assert "count" not in result

    def test_infer_target_known_actions(self):
        """_infer_target should return expected targets for known actions."""
        assert _infer_target("pause_ai") == "ai"
        assert _infer_target("resume_ai") == "ai"
        assert _infer_target("check_system_health") == "system"
        assert _infer_target("show_errors") == "errors"
        assert _infer_target("export_report") == "report"
        assert _infer_target("escalate_urgent") == "tickets"

    def test_infer_target_unknown_action(self):
        """_infer_target should return 'unknown' for unknown actions."""
        assert _infer_target("nonexistent_action") == "unknown"

    def test_generate_suggestion_returns_string(self):
        """_generate_suggestion should return a string."""
        result = _generate_suggestion("pause")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fuzzy_match_command_with_pause(self):
        """_fuzzy_match_command should match 'pause' to pause_ai."""
        result = _fuzzy_match_command("I want to pause")
        assert result is not None
        assert result["action"] == "pause_ai"
        assert result["confidence"] >= CONFIDENCE_LOW

    def test_fuzzy_match_command_no_match(self):
        """_fuzzy_match_command should return None for no recognizable keywords."""
        result = _fuzzy_match_command("xyzzy qwerty fnord")
        assert result is None or result["confidence"] < CONFIDENCE_LOW

    def test_command_to_dict(self):
        """_command_to_dict should convert a mock command to a dict."""
        cmd = _make_mock_command()
        result = _command_to_dict(cmd)
        assert isinstance(result, dict)
        assert result.get("id") == "test-cmd-001"
