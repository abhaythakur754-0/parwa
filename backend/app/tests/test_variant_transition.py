"""
Tests for variant_transition.py (Week 10 Day 4 — SG-08 + SG-09)

Comprehensive unit tests for VariantTransitionHandler covering:
- Constructor and variant capabilities initialization
- register_ticket / unregister_ticket / get_ticket / get_in_flight_tickets
- initiate_upgrade: validation, transition record, in-flight tickets
- on_turn_start: first turn uses old, next turn switches
- on_turn_complete: marking turn done
- complete_transition: marking transition complete
- initiate_downgrade: validation, cache cleared, deactivation notice
- get_restricted_features: correct feature diff
- get_deactivation_notices / acknowledge_deactivation
- clear_restricted_cache
- get_effective_capabilities
- get_transition_history / get_active_transitions
- get_variant_capabilities
- get_technique_access_for_ticket / is_technique_available
- validate_transition: valid, invalid, same-variant, reverse
- rollback_transition
- Edge cases: no tickets in-flight, ticket not found, double transition
"""

import pytest
import threading
import time

from app.core.variant_transition import (
    VariantTransitionHandler,
    VariantCapabilities,
    InFlightTicket,
    TransitionRecord,
    DeactivationNotice,
    TransitionType,
    TransitionStatus,
    VARIANT_RANKING,
    _TIER_1_TECHNIQUES,
    _TIER_2_TECHNIQUES,
    _TIER_3_TECHNIQUES,
)


# ═══════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def handler():
    """Fresh VariantTransitionHandler for each test."""
    return VariantTransitionHandler()


@pytest.fixture
def handler_with_tickets(handler):
    """Handler with some in-flight tickets registered."""
    handler.register_ticket("co_1", "tkt_1", "mini_parwa")
    handler.register_ticket("co_1", "tkt_2", "parwa")
    handler.register_ticket("co_2", "tkt_3", "parwa")
    return handler


# ═══════════════════════════════════════════════════════════════════
# CONSTRUCTOR & VARIANT CAPABILITIES
# ═══════════════════════════════════════════════════════════════════


class TestConstructor:
    """Tests for VariantTransitionHandler initialization."""

    def test_initializes_all_three_variants(self, handler):
        """Should have capability definitions for all 3 variants."""
        assert "mini_parwa" in handler._capabilities
        assert "parwa" in handler._capabilities
        assert "parwa_high" in handler._capabilities

    def test_mini_parwa_tier_1(self, handler):
        """mini_parwa should have max_tier=1."""
        caps = handler._capabilities["mini_parwa"]
        assert caps.max_tier == 1
        assert caps.allowed_techniques == list(_TIER_1_TECHNIQUES)

    def test_parwa_tier_2(self, handler):
        """parwa should have max_tier=2 with tier 1 + tier 2 techniques."""
        caps = handler._capabilities["parwa"]
        assert caps.max_tier == 2
        assert len(caps.allowed_techniques) == len(_TIER_1_TECHNIQUES) + len(_TIER_2_TECHNIQUES)

    def test_parwa_high_tier_3(self, handler):
        """parwa_high should have max_tier=3 with all 14 techniques."""
        caps = handler._capabilities["parwa_high"]
        assert caps.max_tier == 3
        assert len(caps.allowed_techniques) == 14

    def test_confidence_thresholds_differ(self, handler):
        """Each variant should have a different confidence threshold."""
        mp = handler._capabilities["mini_parwa"].confidence_threshold
        pw = handler._capabilities["parwa"].confidence_threshold
        ph = handler._capabilities["parwa_high"].confidence_threshold
        assert mp > pw > ph

    def test_empty_ticket_registry(self, handler):
        """Should start with no registered tickets."""
        assert handler._ticket_registry == {}

    def test_empty_transition_history(self, handler):
        """Should start with no transition history."""
        assert handler._transition_history == {}


# ═══════════════════════════════════════════════════════════════════
# TICKET REGISTRATION
# ═══════════════════════════════════════════════════════════════════


class TestTicketRegistration:
    """Tests for ticket lifecycle management."""

    def test_register_returns_ticket(self, handler):
        """register_ticket should return an InFlightTicket."""
        ticket = handler.register_ticket("co_1", "tkt_1", "parwa")
        assert isinstance(ticket, InFlightTicket)
        assert ticket.ticket_id == "tkt_1"
        assert ticket.company_id == "co_1"

    def test_register_sets_initial_variant(self, handler):
        """Initial effective_variant should match the registered variant."""
        ticket = handler.register_ticket("co_1", "tkt_1", "parwa")
        assert ticket.effective_variant == "parwa"
        assert ticket.current_variant == "parwa"

    def test_register_turn_count_zero(self, handler):
        """Turn count should start at 0."""
        ticket = handler.register_ticket("co_1", "tkt_1", "parwa")
        assert ticket.turn_count == 0

    def test_register_no_transition_pending(self, handler):
        """New ticket should not have transition pending."""
        ticket = handler.register_ticket("co_1", "tkt_1", "parwa")
        assert ticket.transition_pending is False

    def test_get_ticket(self, handler):
        """get_ticket should return the registered ticket."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        ticket = handler.get_ticket("co_1", "tkt_1")
        assert ticket is not None
        assert ticket.ticket_id == "tkt_1"

    def test_get_ticket_wrong_company(self, handler):
        """get_ticket should return None for wrong company."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        ticket = handler.get_ticket("co_2", "tkt_1")
        assert ticket is None

    def test_get_ticket_not_found(self, handler):
        """get_ticket should return None for nonexistent ticket."""
        assert handler.get_ticket("co_1", "tkt_99") is None

    def test_unregister(self, handler):
        """unregister should return True and remove the ticket."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        assert handler.unregister_ticket("co_1", "tkt_1") is True
        assert handler.get_ticket("co_1", "tkt_1") is None

    def test_unregister_not_found(self, handler):
        """unregister should return False for nonexistent ticket."""
        assert handler.unregister_ticket("co_1", "tkt_99") is False

    def test_get_in_flight_tickets(self, handler):
        """get_in_flight_tickets should return all tickets for a company."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        handler.register_ticket("co_1", "tkt_2", "mini_parwa")
        handler.register_ticket("co_2", "tkt_3", "parwa")
        tickets = handler.get_in_flight_tickets("co_1")
        assert len(tickets) == 2

    def test_get_in_flight_tickets_empty(self, handler):
        """Should return empty list for company with no tickets."""
        assert handler.get_in_flight_tickets("co_empty") == []

    def test_new_ticket_uses_effective_variant_after_transition(self, handler):
        """New ticket registered after transition should use effective variant."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        record = handler.initiate_upgrade("co_1", "mini_parwa", "parwa", "plan upgrade")
        handler.complete_transition("co_1", record.transition_id)
        ticket = handler.register_ticket("co_1", "tkt_2", "mini_parwa")
        assert ticket.effective_variant == "parwa"


# ═══════════════════════════════════════════════════════════════════
# UPGRADE (SG-08)
# ═══════════════════════════════════════════════════════════════════


class TestInitiateUpgrade:
    """Tests for initiating a variant upgrade."""

    def test_valid_upgrade(self, handler_with_tickets):
        """Valid upgrade mini_parwa → parwa should succeed."""
        record = handler_with_tickets.initiate_upgrade(
            "co_1", "mini_parwa", "parwa", "plan upgrade",
        )
        assert record.transition_type == TransitionType.UPGRADE
        assert record.from_variant == "mini_parwa"
        assert record.to_variant == "parwa"
        assert record.status == TransitionStatus.ACTIVE

    def test_upgrade_marks_inflight_tickets(self, handler_with_tickets):
        """Upgrade should mark in-flight tickets with transition_pending."""
        handler_with_tickets.initiate_upgrade("co_1", "mini_parwa", "parwa")
        tkt1 = handler_with_tickets.get_ticket("co_1", "tkt_1")
        assert tkt1.transition_pending is True
        assert tkt1.pending_variant == "parwa"
        assert tkt1.uses_old_capabilities is True

    def test_upgrade_affected_count(self, handler_with_tickets):
        """Record should reflect number of affected in-flight tickets."""
        record = handler_with_tickets.initiate_upgrade("co_1", "mini_parwa", "parwa")
        assert record.in_flight_tickets_affected >= 1

    def test_upgrade_invalid_direction(self, handler):
        """Trying to downgrade via initiate_upgrade should return error record."""
        record = handler.initiate_upgrade("co_1", "parwa", "mini_parwa")
        assert record.status == TransitionStatus.ROLLED_BACK
        assert record.details.get("error") is True

    def test_upgrade_same_variant_fails(self, handler):
        """Upgrading to same variant should fail."""
        record = handler.initiate_upgrade("co_1", "parwa", "parwa")
        assert record.status == TransitionStatus.ROLLED_BACK

    def test_upgrade_unknown_variant(self, handler):
        """Unknown variant should fail validation."""
        record = handler.initiate_upgrade("co_1", "parwa", "unknown_variant")
        assert record.status == TransitionStatus.ROLLED_BACK

    def test_upgrade_parwa_to_parwa_high(self, handler):
        """Valid upgrade parwa → parwa_high."""
        record = handler.initiate_upgrade("co_1", "parwa", "parwa_high")
        assert record.status == TransitionStatus.ACTIVE
        assert record.transition_type == TransitionType.UPGRADE


# ═══════════════════════════════════════════════════════════════════
# ON TURN START (SG-08)
# ═══════════════════════════════════════════════════════════════════


class TestOnTurnStart:
    """Tests for turn-start variant switching logic."""

    def test_first_turn_applies_upgrade_immediately(self, handler):
        """First on_turn_start after upgrade immediately applies new variant."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        variant = handler.on_turn_start("co_1", "tkt_1")
        assert variant == "parwa"
        ticket = handler.get_ticket("co_1", "tkt_1")
        assert ticket.transition_pending is False

    def test_subsequent_turns_use_new_variant(self, handler):
        """Subsequent turns should use the new variant."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        variant1 = handler.on_turn_start("co_1", "tkt_1")  # turn 1: applies upgrade
        variant2 = handler.on_turn_start("co_1", "tkt_1")  # turn 2
        assert variant1 == "parwa"
        assert variant2 == "parwa"

    def test_turn_count_increments(self, handler):
        """on_turn_start should increment turn_count."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        handler.on_turn_start("co_1", "tkt_1")
        handler.on_turn_start("co_1", "tkt_1")
        ticket = handler.get_ticket("co_1", "tkt_1")
        assert ticket.turn_count == 2

    def test_ticket_not_found_returns_mini_parwa(self, handler):
        """Nonexistent ticket should return mini_parwa fallback."""
        assert handler.on_turn_start("co_1", "tkt_99") == "mini_parwa"

    def test_wrong_company_returns_mini_parwa(self, handler):
        """Ticket from wrong company should return mini_parwa fallback."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        assert handler.on_turn_start("co_2", "tkt_1") == "mini_parwa"

    def test_transition_pending_cleared_after_switch(self, handler):
        """After switch, transition_pending should be False."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        handler.on_turn_start("co_1", "tkt_1")  # turn 1
        handler.on_turn_start("co_1", "tkt_1")  # turn 2: switches
        ticket = handler.get_ticket("co_1", "tkt_1")
        assert ticket.transition_pending is False
        assert ticket.uses_old_capabilities is False


# ═══════════════════════════════════════════════════════════════════
# ON TURN COMPLETE
# ═══════════════════════════════════════════════════════════════════


class TestOnTurnComplete:
    """Tests for marking turns as complete."""

    def test_complete_no_error(self, handler):
        """on_turn_complete should not raise even for unknown ticket."""
        handler.on_turn_complete("co_1", "tkt_99")

    def test_complete_preserves_uses_old_capabilities(self, handler):
        """After upgrade, on_turn_complete should keep uses_old_capabilities."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        handler.on_turn_start("co_1", "tkt_1")  # turn 1: still old
        handler.on_turn_complete("co_1", "tkt_1")
        ticket = handler.get_ticket("co_1", "tkt_1")
        assert ticket.uses_old_capabilities is True


# ═══════════════════════════════════════════════════════════════════
# COMPLETE TRANSITION
# ═══════════════════════════════════════════════════════════════════


class TestCompleteTransition:
    """Tests for marking a transition as completed."""

    def test_complete_sets_status(self, handler):
        """complete_transition should set status to COMPLETED."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        record = handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        result = handler.complete_transition("co_1", record.transition_id)
        assert result.status == TransitionStatus.COMPLETED

    def test_complete_sets_effective_variant(self, handler):
        """complete_transition should set company's effective variant."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        record = handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        handler.complete_transition("co_1", record.transition_id)
        # New ticket should use parwa
        new_ticket = handler.register_ticket("co_1", "tkt_2", "mini_parwa")
        assert new_ticket.effective_variant == "parwa"

    def test_complete_not_found(self, handler):
        """Should return None for nonexistent transition."""
        assert handler.complete_transition("co_1", "tr_nonexistent") is None

    def test_complete_wrong_company(self, handler):
        """Should return None for wrong company."""
        record = handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        assert handler.complete_transition("co_2", record.transition_id) is None


# ═══════════════════════════════════════════════════════════════════
# DOWNGRADE (SG-09)
# ═══════════════════════════════════════════════════════════════════


class TestInitiateDowngrade:
    """Tests for initiating a variant downgrade."""

    def test_valid_downgrade(self, handler_with_tickets):
        """Valid downgrade parwa → mini_parwa should succeed."""
        record = handler_with_tickets.initiate_downgrade(
            "co_1", "parwa", "mini_parwa", "cancel plan",
        )
        assert record.transition_type == TransitionType.DOWNGRADE
        assert record.status == TransitionStatus.ACTIVE

    def test_downgrade_marks_tickets(self, handler_with_tickets):
        """Downgrade should mark all in-flight tickets."""
        handler_with_tickets.initiate_downgrade("co_1", "parwa", "mini_parwa")
        tkt1 = handler_with_tickets.get_ticket("co_1", "tkt_1")
        assert tkt1.transition_pending is True
        assert tkt1.pending_variant == "mini_parwa"
        assert tkt1.uses_old_capabilities is True

    def test_downgrade_sets_effective_variant(self, handler):
        """Downgrade should immediately set company effective variant."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        handler.initiate_downgrade("co_1", "parwa", "mini_parwa")
        new_ticket = handler.register_ticket("co_1", "tkt_2", "parwa")
        assert new_ticket.effective_variant == "mini_parwa"

    def test_downgrade_creates_deactivation_notice(self, handler):
        """Downgrade should generate a deactivation notice."""
        handler.register_ticket("co_1", "tkt_1", "parwa_high")
        handler.initiate_downgrade("co_1", "parwa_high", "mini_parwa")
        notices = handler.get_deactivation_notices("co_1")
        assert len(notices) == 1
        assert notices[0].variant_from == "parwa_high"
        assert notices[0].variant_to == "mini_parwa"

    def test_downgrade_invalid_direction(self, handler):
        """Trying to upgrade via initiate_downgrade should fail."""
        record = handler.initiate_downgrade("co_1", "mini_parwa", "parwa")
        assert record.status == TransitionStatus.ROLLED_BACK

    def test_downgrade_same_variant_fails(self, handler):
        """Same variant downgrade should fail."""
        record = handler.initiate_downgrade("co_1", "parwa", "parwa")
        assert record.status == TransitionStatus.ROLLED_BACK


# ═══════════════════════════════════════════════════════════════════
# RESTRICTED FEATURES
# ═══════════════════════════════════════════════════════════════════


class TestRestrictedFeatures:
    """Tests for restricted feature computation."""

    def test_parwa_to_mini_parwa_features(self, handler):
        """parwa → mini_parwa should list removed features."""
        restricted = handler.get_restricted_features("co_1", "parwa", "mini_parwa")
        assert len(restricted) > 0
        # Features like chain_of_thought_reasoning should be restricted
        assert "chain_of_thought_reasoning" in restricted
        assert "basic_classification" not in restricted  # shared feature

    def test_parwa_high_to_parwa_features(self, handler):
        """parwa_high → parwa should list tier-3 features."""
        restricted = handler.get_restricted_features("co_1", "parwa_high", "parwa")
        assert "tree_of_thoughts" in restricted
        assert "reflexion" in restricted
        assert "chain_of_thought_reasoning" not in restricted  # still in parwa

    def test_unknown_variant_returns_empty(self, handler):
        """Unknown variant should return empty list."""
        assert handler.get_restricted_features("co_1", "unknown", "parwa") == []

    def test_same_variant_returns_empty(self, handler):
        """Same variant should return empty list."""
        assert handler.get_restricted_features("co_1", "parwa", "parwa") == []


# ═══════════════════════════════════════════════════════════════════
# DEACTIVATION NOTICES
# ═══════════════════════════════════════════════════════════════════


class TestDeactivationNotices:
    """Tests for deactivation notice management."""

    def test_get_notices_empty(self, handler):
        """Should return empty list when no notices."""
        assert handler.get_deactivation_notices("co_1") == []

    def test_get_notices_after_downgrade(self, handler):
        """Should return notice after downgrade."""
        handler.register_ticket("co_1", "tkt_1", "parwa_high")
        handler.initiate_downgrade("co_1", "parwa_high", "mini_parwa")
        notices = handler.get_deactivation_notices("co_1")
        assert len(notices) == 1

    def test_acknowledge_notice(self, handler):
        """acknowledge_deactivation should mark notice as acknowledged."""
        handler.register_ticket("co_1", "tkt_1", "parwa_high")
        handler.initiate_downgrade("co_1", "parwa_high", "mini_parwa")
        notices = handler.get_deactivation_notices("co_1")
        notice_id = notices[0].notice_id
        assert handler.acknowledge_deactivation("co_1", notice_id) is True
        assert handler.get_deactivation_notices("co_1")[0].acknowledged is True

    def test_acknowledge_nonexistent(self, handler):
        """acknowledge_deactivation should return False for nonexistent notice."""
        assert handler.acknowledge_deactivation("co_1", "dn_nonexistent") is False

    def test_notice_has_message(self, handler):
        """Notice should have a human-readable message."""
        handler.register_ticket("co_1", "tkt_1", "parwa_high")
        handler.initiate_downgrade("co_1", "parwa_high", "mini_parwa")
        notice = handler.get_deactivation_notices("co_1")[0]
        assert "downgraded" in notice.message.lower()
        assert len(notice.restricted_features) > 0


# ═══════════════════════════════════════════════════════════════════
# CACHE CLEARING
# ═══════════════════════════════════════════════════════════════════


class TestClearRestrictedCache:
    """Tests for cache clearing on downgrade."""

    def test_clear_cache_returns_keys(self, handler):
        """Should return list of cleared cache keys."""
        # Simulate some cache entries
        handler._feature_cache["co_1:tree_of_thoughts"] = time.time()
        handler._feature_cache["co_1:reflexion"] = time.time()
        handler._feature_cache["co_1:basic_classification"] = time.time()

        cleared = handler.clear_restricted_cache("co_1", "parwa_high", "parwa")
        assert "co_1:tree_of_thoughts" in cleared
        assert "co_1:reflexion" in cleared
        # basic_classification is still available in parwa
        assert "co_1:basic_classification" not in cleared

    def test_clear_cache_no_entries(self, handler):
        """Should return empty list when no cache entries."""
        cleared = handler.clear_restricted_cache("co_1", "parwa_high", "parwa")
        assert cleared == []


# ═══════════════════════════════════════════════════════════════════
# EFFECTIVE CAPABILITIES
# ═══════════════════════════════════════════════════════════════════


class TestEffectiveCapabilities:
    """Tests for per-ticket effective capabilities."""

    def test_default_ticket_capabilities(self, handler):
        """Ticket without transition should have its variant's capabilities."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        caps = handler.get_effective_capabilities("co_1", "tkt_1")
        assert caps.variant_type == "parwa"
        assert caps.max_tier == 2

    def test_after_upgrade_capabilities(self, handler):
        """Ticket after upgrade and turn switch should have new capabilities."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        handler.on_turn_start("co_1", "tkt_1")  # turn 1: old
        handler.on_turn_start("co_1", "tkt_1")  # turn 2: new
        caps = handler.get_effective_capabilities("co_1", "tkt_1")
        assert caps.variant_type == "parwa"
        assert caps.max_tier == 2

    def test_nonexistent_ticket_returns_mini_parwa(self, handler):
        """Nonexistent ticket should return mini_parwa capabilities."""
        caps = handler.get_effective_capabilities("co_1", "tkt_99")
        assert caps.variant_type == "mini_parwa"

    def test_wrong_company_returns_mini_parwa(self, handler):
        """Ticket from wrong company should return mini_parwa."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        caps = handler.get_effective_capabilities("co_2", "tkt_1")
        assert caps.variant_type == "mini_parwa"


# ═══════════════════════════════════════════════════════════════════
# TRANSITION HISTORY
# ═══════════════════════════════════════════════════════════════════


class TestTransitionHistory:
    """Tests for transition history queries."""

    def test_empty_history(self, handler):
        """Should return empty list when no transitions."""
        assert handler.get_transition_history("co_1") == []

    def test_upgrade_recorded_in_history(self, handler):
        """Upgrade should be recorded in history."""
        handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        history = handler.get_transition_history("co_1")
        assert len(history) == 1
        assert history[0].transition_type == TransitionType.UPGRADE

    def test_downgrade_recorded_in_history(self, handler):
        """Downgrade should be recorded in history."""
        handler.initiate_downgrade("co_1", "parwa", "mini_parwa")
        history = handler.get_transition_history("co_1")
        assert len(history) == 1
        assert history[0].transition_type == TransitionType.DOWNGRADE

    def test_get_active_transitions(self, handler):
        """Should return only ACTIVE/PENDING transitions."""
        handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        active = handler.get_active_transitions("co_1")
        assert len(active) == 1
        assert active[0].status == TransitionStatus.ACTIVE

    def test_completed_not_in_active(self, handler):
        """Completed transitions should not appear in active list."""
        record = handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        handler.complete_transition("co_1", record.transition_id)
        active = handler.get_active_transitions("co_1")
        assert len(active) == 0


# ═══════════════════════════════════════════════════════════════════
# VARIANT CAPABILITIES QUERY
# ═══════════════════════════════════════════════════════════════════


class TestVariantCapabilities:
    """Tests for variant capability queries."""

    def test_get_known_variant(self, handler):
        """Should return capabilities for known variants."""
        caps = handler.get_variant_capabilities("parwa")
        assert isinstance(caps, VariantCapabilities)
        assert caps.variant_type == "parwa"

    def test_get_unknown_variant_fallback(self, handler):
        """Unknown variant should return mini_parwa capabilities."""
        caps = handler.get_variant_capabilities("unknown_xyz")
        assert caps.variant_type == "mini_parwa"

    def test_to_dict(self, handler):
        """to_dict should return a complete dict."""
        caps = handler.get_variant_capabilities("parwa_high")
        d = caps.to_dict()
        assert "variant_type" in d
        assert "max_tier" in d
        assert "allowed_techniques" in d
        assert "features" in d


# ═══════════════════════════════════════════════════════════════════
# TECHNIQUE ACCESS
# ═══════════════════════════════════════════════════════════════════


class TestTechniqueAccess:
    """Tests for per-ticket technique access."""

    def test_mini_parwa_techniques(self, handler):
        """mini_parwa should only have tier 1 techniques."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        techniques = handler.get_technique_access_for_ticket("co_1", "tkt_1")
        assert "clara" in techniques
        assert "crp" in techniques
        assert "chain_of_thought" not in techniques

    def test_parwa_techniques(self, handler):
        """parwa should have tier 1 + tier 2 techniques."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        techniques = handler.get_technique_access_for_ticket("co_1", "tkt_1")
        assert "clara" in techniques
        assert "chain_of_thought" in techniques
        assert "tree_of_thoughts" not in techniques

    def test_parwa_high_techniques(self, handler):
        """parwa_high should have all 14 techniques."""
        handler.register_ticket("co_1", "tkt_1", "parwa_high")
        techniques = handler.get_technique_access_for_ticket("co_1", "tkt_1")
        assert "clara" in techniques
        assert "chain_of_thought" in techniques
        assert "tree_of_thoughts" in techniques
        assert "reflexion" in techniques
        assert len(techniques) == 14

    def test_is_technique_available_true(self, handler):
        """Should return True for available technique."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        assert handler.is_technique_available("co_1", "tkt_1", "chain_of_thought") is True

    def test_is_technique_available_false(self, handler):
        """Should return False for unavailable technique."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        assert handler.is_technique_available("co_1", "tkt_1", "tree_of_thoughts") is False

    def test_is_technique_case_insensitive(self, handler):
        """Technique lookup should be case-insensitive."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        assert handler.is_technique_available("co_1", "tkt_1", "CHAIN_OF_THOUGHT") is True

    def test_technique_access_after_upgrade(self, handler):
        """After upgrade and turn switch, new techniques should be available."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        handler.on_turn_start("co_1", "tkt_1")  # turn 1: old
        handler.on_turn_start("co_1", "tkt_1")  # turn 2: new
        assert handler.is_technique_available("co_1", "tkt_1", "chain_of_thought") is True


# ═══════════════════════════════════════════════════════════════════
# VALIDATE TRANSITION
# ═══════════════════════════════════════════════════════════════════


class TestValidateTransition:
    """Tests for transition validation."""

    def test_valid_upgrade(self, handler):
        """mini_parwa → parwa should be valid upgrade."""
        is_valid, msg = handler.validate_transition("mini_parwa", "parwa")
        assert is_valid is True
        assert "upgrade" in msg

    def test_valid_downgrade(self, handler):
        """parwa → mini_parwa should be valid downgrade."""
        is_valid, msg = handler.validate_transition("parwa", "mini_parwa")
        assert is_valid is True
        assert "downgrade" in msg

    def test_same_variant_invalid(self, handler):
        """parwa → parwa should be invalid."""
        is_valid, msg = handler.validate_transition("parwa", "parwa")
        assert is_valid is False
        assert "different" in msg.lower()

    def test_unknown_variant(self, handler):
        """Unknown variant should be invalid."""
        is_valid, msg = handler.validate_transition("parwa", "nonexistent")
        assert is_valid is False
        assert "unknown" in msg.lower()

    def test_empty_variant_names(self, handler):
        """Empty variant names should be invalid."""
        is_valid, msg = handler.validate_transition("", "parwa")
        assert is_valid is False

    def test_full_upgrade_path(self, handler):
        """mini_parwa → parwa → parwa_high should both be valid."""
        v1, _ = handler.validate_transition("mini_parwa", "parwa")
        v2, _ = handler.validate_transition("parwa", "parwa_high")
        assert v1 is True
        assert v2 is True


# ═══════════════════════════════════════════════════════════════════
# ROLLBACK TRANSITION
# ═══════════════════════════════════════════════════════════════════


class TestRollbackTransition:
    """Tests for rolling back a transition."""

    def test_rollback_active_upgrade(self, handler_with_tickets):
        """Rolling back an active upgrade should revert tickets."""
        record = handler_with_tickets.initiate_upgrade("co_1", "mini_parwa", "parwa")
        result = handler_with_tickets.rollback_transition("co_1", record.transition_id)
        assert result.status == TransitionStatus.ROLLED_BACK
        # Tickets should no longer have transition pending
        tkt1 = handler_with_tickets.get_ticket("co_1", "tkt_1")
        assert tkt1.transition_pending is False
        assert tkt1.effective_variant == "mini_parwa"

    def test_rollback_completed_fails(self, handler):
        """Rolling back a completed transition should fail."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        record = handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        handler.complete_transition("co_1", record.transition_id)
        result = handler.rollback_transition("co_1", record.transition_id)
        assert result is None

    def test_rollback_not_found(self, handler):
        """Rolling back nonexistent transition should return None."""
        assert handler.rollback_transition("co_1", "tr_nonexistent") is None

    def test_rollback_wrong_company(self, handler):
        """Rolling back with wrong company should return None."""
        record = handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        assert handler.rollback_transition("co_2", record.transition_id) is None

    def test_rollback_reverts_effective_variant(self, handler):
        """Rollback should revert company effective variant."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        record = handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        handler.rollback_transition("co_1", record.transition_id)
        # New ticket should still use mini_parwa
        new_ticket = handler.register_ticket("co_1", "tkt_2", "mini_parwa")
        assert new_ticket.effective_variant == "mini_parwa"


# ═══════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for boundary conditions and edge cases."""

    def test_no_inflight_tickets_upgrade(self, handler):
        """Upgrade with no in-flight tickets should still succeed."""
        record = handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        assert record.status == TransitionStatus.ACTIVE
        assert record.in_flight_tickets_affected == 0

    def test_no_inflight_tickets_downgrade(self, handler):
        """Downgrade with no in-flight tickets should still succeed."""
        record = handler.initiate_downgrade("co_1", "parwa", "mini_parwa")
        assert record.status == TransitionStatus.ACTIVE

    def test_double_upgrade(self, handler):
        """Second upgrade should only affect tickets not already pending."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
        # tkt_1 already has transition_pending=True
        record2 = handler.initiate_upgrade("co_1", "parwa", "parwa_high")
        assert record2.in_flight_tickets_affected == 0

    def test_ticket_not_found_on_turn_start(self, handler):
        """on_turn_start for nonexistent ticket should return mini_parwa."""
        assert handler.on_turn_start("co_1", "tkt_99") == "mini_parwa"

    def test_ticket_not_found_on_turn_complete(self, handler):
        """on_turn_complete for nonexistent ticket should not raise."""
        handler.on_turn_complete("co_1", "tkt_99")

    def test_multiple_downgrades(self, handler):
        """Multiple consecutive downgrades should each work."""
        handler.register_ticket("co_1", "tkt_1", "parwa_high")
        handler.initiate_downgrade("co_1", "parwa_high", "parwa")
        # tkt_1 has pending variant=parwa, uses_old=True
        handler.on_turn_start("co_1", "tkt_1")  # turn 1: old
        handler.on_turn_start("co_1", "tkt_1")  # turn 2: switch to parwa

        # Now downgrade from parwa to mini_parwa
        handler.initiate_downgrade("co_1", "parwa", "mini_parwa")
        ticket = handler.get_ticket("co_1", "tkt_1")
        assert ticket.transition_pending is True
        assert ticket.pending_variant == "mini_parwa"


# ═══════════════════════════════════════════════════════════════════
# THREAD SAFETY
# ═══════════════════════════════════════════════════════════════════


class TestThreadSafety:
    """Basic thread safety tests."""

    def test_concurrent_register_tickets(self, handler):
        """Concurrent register_ticket calls should not crash."""
        errors = []

        def register(i):
            try:
                handler.register_ticket("co_1", f"tkt_{i}", "parwa")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=register, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_turn_start(self, handler):
        """Concurrent on_turn_start calls should not crash."""
        handler.register_ticket("co_1", "tkt_1", "mini_parwa")
        handler.initiate_upgrade("co_1", "mini_parwa", "parwa")

        errors = []
        def turn_start(i):
            try:
                handler.on_turn_start("co_1", "tkt_1")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=turn_start, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_upgrade_and_downgrade(self, handler):
        """Concurrent upgrade and downgrade should not crash."""
        handler.register_ticket("co_1", "tkt_1", "parwa")
        handler.register_ticket("co_2", "tkt_2", "parwa_high")

        errors = []
        def do_upgrade():
            try:
                handler.initiate_upgrade("co_1", "mini_parwa", "parwa")
            except Exception as e:
                errors.append(str(e))

        def do_downgrade():
            try:
                handler.initiate_downgrade("co_2", "parwa_high", "parwa")
            except Exception as e:
                errors.append(str(e))

        threads = []
        for _ in range(10):
            threads.append(threading.Thread(target=do_upgrade))
            threads.append(threading.Thread(target=do_downgrade))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
