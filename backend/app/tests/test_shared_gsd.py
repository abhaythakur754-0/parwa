"""Tests for Shared GSD Manager (shared_gsd.py)

Covers:
- Valid transition lookup (parwa, mini_parwa, high_parwa variants)
- Transition reason explanation
- Transition recording
- Transition history retrieval
- State duration calculation
- Analytics (state distribution, bottlenecks)
- Recovery suggestions
- Transition heatmap
- Event emission (listeners)
- Edge cases (unknown states, empty history)
- Lifecycle management (clear data)

Target: 55+ tests
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from app.core.shared_gsd import (
    SharedGSDManager,
    TransitionLogEntry,
)

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def manager() -> SharedGSDManager:
    return SharedGSDManager()


COMPANY_ID = "co_test_123"
TICKET_ID = "tkt_001"
ANOTHER_TICKET = "tkt_002"
ANOTHER_COMPANY = "co_test_456"


# ═══════════════════════════════════════════════════════════════════
# 1. Valid Transition Lookup
# ═══════════════════════════════════════════════════════════════════


class TestValidTransitions:

    def test_new_to_greeting_parwa(self, manager):
        targets = manager.get_valid_transitions("new")
        assert "greeting" in targets

    def test_greeting_to_diagnosis_parwa(self, manager):
        targets = manager.get_valid_transitions("greeting")
        assert "diagnosis" in targets

    def test_diagnosis_has_resolution_and_escalate(self, manager):
        targets = manager.get_valid_transitions("diagnosis")
        assert "resolution" in targets
        assert "escalate" in targets

    def test_resolution_to_follow_up_and_closed(self, manager):
        targets = manager.get_valid_transitions("resolution")
        assert "follow_up" in targets
        assert "closed" in targets

    def test_follow_up_to_closed_and_diagnosis(self, manager):
        targets = manager.get_valid_transitions("follow_up")
        assert "closed" in targets
        assert "diagnosis" in targets

    def test_escalate_to_human_handoff(self, manager):
        targets = manager.get_valid_transitions("escalate")
        assert "human_handoff" in targets

    def test_human_handoff_to_diagnosis(self, manager):
        targets = manager.get_valid_transitions("human_handoff")
        assert "diagnosis" in targets

    def test_closed_to_new(self, manager):
        targets = manager.get_valid_transitions("closed")
        assert "new" in targets

    def test_mini_parwa_no_escalate(self, manager):
        targets = manager.get_valid_transitions("diagnosis", variant="mini_parwa")
        assert "escalate" not in targets
        assert "resolution" in targets

    def test_mini_parwa_no_human_handoff(self, manager):
        targets = manager.get_valid_transitions("escalate", variant="mini_parwa")
        assert "human_handoff" not in targets

    def test_high_parwa_has_escalate(self, manager):
        targets = manager.get_valid_transitions("diagnosis", variant="high_parwa")
        assert "escalate" in targets

    def test_unknown_state_returns_empty(self, manager):
        targets = manager.get_valid_transitions("unknown_state")
        assert targets == []

    def test_greeting_has_escalate_in_parwa(self, manager):
        targets = manager.get_valid_transitions("greeting")
        assert "escalate" in targets

    def test_closed_no_escalate(self, manager):
        targets = manager.get_valid_transitions("closed")
        assert "escalate" not in targets


# ═══════════════════════════════════════════════════════════════════
# 2. Transition Reason
# ═══════════════════════════════════════════════════════════════════


class TestTransitionReason:

    def test_valid_transition_reason(self, manager):
        result = manager.get_transition_reason("new", "greeting")
        assert result["valid"] is True
        assert "permitted" in result["reason"].lower()

    def test_invalid_transition_reason(self, manager):
        result = manager.get_transition_reason("new", "closed")
        assert result["valid"] is False
        assert "not permitted" in result["reason"].lower()

    def test_invalid_shows_valid_targets(self, manager):
        result = manager.get_transition_reason("diagnosis", "new")
        assert result["valid"] is False
        assert "resolution" in result["reason"]

    def test_reason_has_suggestion_for_valid_states(self, manager):
        result = manager.get_transition_reason("greeting", "new")
        assert result["valid"] is False
        assert "Valid targets" in result["reason"]


# ═══════════════════════════════════════════════════════════════════
# 3. Transition Recording
# ═══════════════════════════════════════════════════════════════════


class TestTransitionRecording:

    def test_record_single_transition(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        history = manager.get_transition_history(COMPANY_ID, TICKET_ID)
        assert len(history) == 1
        assert history[0]["from_state"] == "new"
        assert history[0]["to_state"] == "greeting"

    def test_record_multiple_transitions(self, manager):
        transitions = [
            ("new", "greeting"),
            ("greeting", "diagnosis"),
            ("diagnosis", "resolution"),
        ]
        for from_s, to_s in transitions:
            manager.record_transition(COMPANY_ID, TICKET_ID, from_s, to_s)
        history = manager.get_transition_history(COMPANY_ID, TICKET_ID)
        assert len(history) == 3

    def test_record_with_metadata(self, manager):
        meta = {"confidence": 0.95, "intent": "billing"}
        manager.record_transition(
            COMPANY_ID,
            TICKET_ID,
            "diagnosis",
            "resolution",
            metadata=meta,
        )
        history = manager.get_transition_history(COMPANY_ID, TICKET_ID)
        assert history[0]["metadata"]["confidence"] == 0.95
        assert history[0]["metadata"]["intent"] == "billing"

    def test_record_updates_current_state(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        assert manager.get_current_state(COMPANY_ID, TICKET_ID) == "greeting"

    def test_record_isolation_by_ticket(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        manager.record_transition(COMPANY_ID, ANOTHER_TICKET, "new", "greeting")
        h1 = manager.get_transition_history(COMPANY_ID, TICKET_ID)
        h2 = manager.get_transition_history(COMPANY_ID, ANOTHER_TICKET)
        assert len(h1) == 1
        assert len(h2) == 1

    def test_record_isolation_by_company(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        manager.record_transition(ANOTHER_COMPANY, TICKET_ID, "new", "greeting")
        h1 = manager.get_transition_history(COMPANY_ID, TICKET_ID)
        h2 = manager.get_transition_history(ANOTHER_COMPANY, TICKET_ID)
        assert len(h1) == 1
        assert len(h2) == 1

    def test_record_timestamp_is_recent(self, manager):
        before = time.time()
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        after = time.time()
        history = manager.get_transition_history(COMPANY_ID, TICKET_ID)
        assert before <= history[0]["timestamp"] <= after


# ═══════════════════════════════════════════════════════════════════
# 4. Transition History Retrieval
# ═══════════════════════════════════════════════════════════════════


class TestTransitionHistory:

    def test_empty_history_for_unknown_ticket(self, manager):
        history = manager.get_transition_history(COMPANY_ID, "unknown_ticket")
        assert history == []

    def test_empty_history_for_unknown_company(self, manager):
        history = manager.get_transition_history("unknown_company", TICKET_ID)
        assert history == []

    def test_history_ordered_by_timestamp(self, manager):
        for i in range(5):
            manager.record_transition(
                COMPANY_ID,
                TICKET_ID,
                f"state_{i}",
                f"state_{i + 1}",
            )
        history = manager.get_transition_history(COMPANY_ID, TICKET_ID)
        timestamps = [h["timestamp"] for h in history]
        assert timestamps == sorted(timestamps)

    def test_history_preserves_order(self, manager):
        transitions = [
            ("new", "greeting"),
            ("greeting", "diagnosis"),
            ("diagnosis", "resolution"),
        ]
        for from_s, to_s in transitions:
            manager.record_transition(COMPANY_ID, TICKET_ID, from_s, to_s)
        history = manager.get_transition_history(COMPANY_ID, TICKET_ID)
        assert history[0]["from_state"] == "new"
        assert history[1]["from_state"] == "greeting"
        assert history[2]["from_state"] == "diagnosis"


# ═══════════════════════════════════════════════════════════════════
# 5. State Duration Calculation
# ═══════════════════════════════════════════════════════════════════


class TestStateDuration:

    def test_duration_for_never_entered_state(self, manager):
        dur = manager.get_state_duration(COMPANY_ID, TICKET_ID, "diagnosis")
        assert dur == 0.0

    def test_duration_for_current_state(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "diagnosis")
        time.sleep(0.05)
        dur = manager.get_state_duration(COMPANY_ID, TICKET_ID, "diagnosis")
        assert dur >= 0.05

    def test_duration_for_exited_state(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "diagnosis")
        time.sleep(0.05)
        manager.record_transition(COMPANY_ID, TICKET_ID, "diagnosis", "resolution")
        dur = manager.get_state_duration(COMPANY_ID, TICKET_ID, "diagnosis")
        assert dur >= 0.05

    def test_duration_for_empty_ticket(self, manager):
        dur = manager.get_state_duration(COMPANY_ID, "no_such_ticket", "diagnosis")
        assert dur == 0.0


# ═══════════════════════════════════════════════════════════════════
# 6. Analytics
# ═══════════════════════════════════════════════════════════════════


class TestAnalytics:

    def test_analytics_empty_company(self, manager):
        analytics = manager.get_analytics("no_such_company")
        assert analytics["total_tickets"] == 0
        assert analytics["total_transitions"] == 0
        assert analytics["state_distribution"] == {}

    def test_analytics_state_distribution(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        manager.record_transition(COMPANY_ID, TICKET_ID, "greeting", "diagnosis")
        analytics = manager.get_analytics(COMPANY_ID)
        dist = analytics["state_distribution"]
        assert dist.get("greeting", 0) == 1
        assert dist.get("diagnosis", 0) == 1

    def test_analytics_total_tickets(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        manager.record_transition(COMPANY_ID, ANOTHER_TICKET, "new", "greeting")
        analytics = manager.get_analytics(COMPANY_ID)
        assert analytics["total_tickets"] == 2

    def test_analytics_total_transitions(self, manager):
        for i in range(4):
            manager.record_transition(
                COMPANY_ID,
                TICKET_ID,
                f"s{i}",
                f"s{i + 1}",
            )
        analytics = manager.get_analytics(COMPANY_ID)
        assert analytics["total_transitions"] == 4

    def test_analytics_has_average_durations(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "diagnosis")
        manager.record_transition(COMPANY_ID, TICKET_ID, "diagnosis", "resolution")
        analytics = manager.get_analytics(COMPANY_ID)
        assert "average_duration_seconds" in analytics

    def test_analytics_bottleneck_detection(self, manager):
        # Simulate stuck in diagnosis
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "diagnosis")
        # Lower threshold for testing
        original = manager.STUCK_THRESHOLD_SECONDS
        manager.STUCK_THRESHOLD_SECONDS = 0.01
        time.sleep(0.02)
        manager.record_transition(COMPANY_ID, TICKET_ID, "diagnosis", "resolution")
        analytics = manager.get_analytics(COMPANY_ID)
        bottlenecks = analytics["bottleneck_states"]
        assert len(bottlenecks) > 0
        manager.STUCK_THRESHOLD_SECONDS = original

    def test_analytics_transition_frequency(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        analytics = manager.get_analytics(COMPANY_ID)
        freq = analytics["transition_frequency"]
        assert ("new", "greeting") in freq
        assert freq[("new", "greeting")] == 1

    def test_analytics_company_isolation(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        analytics = manager.get_analytics(ANOTHER_COMPANY)
        assert analytics["total_tickets"] == 0


# ═══════════════════════════════════════════════════════════════════
# 7. Recovery Suggestions
# ═══════════════════════════════════════════════════════════════════


class TestRecoverySuggestions:

    def test_no_suggestion_for_progressing_ticket(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        suggestions = manager.suggest_recovery(COMPANY_ID, TICKET_ID)
        assert len(suggestions) >= 1
        assert any(s["action"] == "no_action_needed" for s in suggestions)

    def test_suggestion_for_stuck_ticket(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "diagnosis")
        # Override threshold for testing
        original_stuck = manager.STUCK_THRESHOLD_SECONDS
        original_critical = manager.CRITICAL_STUCK_THRESHOLD_SECONDS
        manager.STUCK_THRESHOLD_SECONDS = 0.01
        manager.CRITICAL_STUCK_THRESHOLD_SECONDS = 0.02
        time.sleep(0.03)
        suggestions = manager.suggest_recovery(COMPANY_ID, TICKET_ID)
        actions = [s["action"] for s in suggestions]
        assert "escalate_to_human" in actions
        manager.STUCK_THRESHOLD_SECONDS = original_stuck
        manager.CRITICAL_STUCK_THRESHOLD_SECONDS = original_critical

    def test_suggestion_for_unknown_ticket(self, manager):
        suggestions = manager.suggest_recovery(COMPANY_ID, "no_such_ticket")
        assert suggestions == []

    def test_diagnosis_loop_suggestion(self, manager):
        # Simulate entering diagnosis many times
        pairs = [
            ("new", "diagnosis"),
            ("diagnosis", "resolution"),
            ("resolution", "diagnosis"),
            ("diagnosis", "resolution"),
            ("resolution", "diagnosis"),
            ("diagnosis", "resolution"),
            ("resolution", "diagnosis"),
        ]
        for from_s, to_s in pairs:
            manager.record_transition(COMPANY_ID, TICKET_ID, from_s, to_s)
        suggestions = manager.suggest_recovery(COMPANY_ID, TICKET_ID)
        actions = [s["action"] for s in suggestions]
        assert "escalate_diagnosis_loop" in actions

    def test_suggestion_has_priority(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        suggestions = manager.suggest_recovery(COMPANY_ID, TICKET_ID)
        for s in suggestions:
            assert "priority" in s
            assert s["priority"] in ("high", "medium", "low")


# ═══════════════════════════════════════════════════════════════════
# 8. Transition Heatmap
# ═══════════════════════════════════════════════════════════════════


class TestTransitionHeatmap:

    def test_empty_heatmap(self, manager):
        heatmap = manager.get_transition_heatmap("no_company")
        assert heatmap == {}

    def test_heatmap_single_transition(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        heatmap = manager.get_transition_heatmap(COMPANY_ID)
        assert heatmap["new"]["greeting"] == 1

    def test_heatmap_counts_transitions(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        manager.record_transition(COMPANY_ID, ANOTHER_TICKET, "new", "greeting")
        heatmap = manager.get_transition_heatmap(COMPANY_ID)
        assert heatmap["new"]["greeting"] == 2

    def test_heatmap_multiple_paths(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "diagnosis", "resolution")
        manager.record_transition(COMPANY_ID, ANOTHER_TICKET, "diagnosis", "escalate")
        heatmap = manager.get_transition_heatmap(COMPANY_ID)
        assert heatmap["diagnosis"]["resolution"] == 1
        assert heatmap["diagnosis"]["escalate"] == 1

    def test_heatmap_company_isolation(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        heatmap = manager.get_transition_heatmap(ANOTHER_COMPANY)
        assert heatmap == {}


# ═══════════════════════════════════════════════════════════════════
# 9. Event Emission
# ═══════════════════════════════════════════════════════════════════


class TestEventEmission:

    def test_listener_called_on_transition(self, manager):
        listener = MagicMock()
        manager.add_event_listener(listener)
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        listener.assert_called_once()
        call_arg = listener.call_args[0][0]
        assert isinstance(call_arg, TransitionLogEntry)
        assert call_arg.from_state == "new"
        assert call_arg.to_state == "greeting"

    def test_listener_error_does_not_crash(self, manager):
        bad_listener = MagicMock(side_effect=RuntimeError("listener error"))
        manager.add_event_listener(bad_listener)
        # Should not raise
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        bad_listener.assert_called_once()

    def test_remove_listener(self, manager):
        listener = MagicMock()
        manager.add_event_listener(listener)
        manager.remove_event_listener(listener)
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        listener.assert_not_called()

    def test_multiple_listeners(self, manager):
        l1 = MagicMock()
        l2 = MagicMock()
        manager.add_event_listener(l1)
        manager.add_event_listener(l2)
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        l1.assert_called_once()
        l2.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 10. Lifecycle Management
# ═══════════════════════════════════════════════════════════════════


class TestLifecycleManagement:

    def test_clear_ticket_data(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        manager.clear_ticket_data(COMPANY_ID, TICKET_ID)
        history = manager.get_transition_history(COMPANY_ID, TICKET_ID)
        assert history == []
        assert manager.get_current_state(COMPANY_ID, TICKET_ID) is None

    def test_clear_ticket_preserves_other_tickets(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        manager.record_transition(COMPANY_ID, ANOTHER_TICKET, "new", "greeting")
        manager.clear_ticket_data(COMPANY_ID, TICKET_ID)
        h1 = manager.get_transition_history(COMPANY_ID, TICKET_ID)
        h2 = manager.get_transition_history(COMPANY_ID, ANOTHER_TICKET)
        assert h1 == []
        assert len(h2) == 1

    def test_clear_company_data(self, manager):
        manager.record_transition(COMPANY_ID, TICKET_ID, "new", "greeting")
        manager.clear_company_data(COMPANY_ID)
        assert manager.get_transition_history(COMPANY_ID, TICKET_ID) == []
        assert manager.get_transition_heatmap(COMPANY_ID) == {}

    def test_clear_nonexistent_ticket_no_error(self, manager):
        manager.clear_ticket_data(COMPANY_ID, "no_such_ticket")

    def test_clear_nonexistent_company_no_error(self, manager):
        manager.clear_company_data("no_such_company")

    def test_get_current_state_none_for_unknown(self, manager):
        assert manager.get_current_state(COMPANY_ID, "no_ticket") is None
