"""
Tests for Cross-Variant Interaction Module — Situation Gaps.

Covers three core capabilities of ``CrossVariantInteractionService``:

1. Confidence-Based Escalation — low confidence scores auto-escalate
   to a higher-tier variant.
2. Same-Ticket Handoff — full context transfer when tickets move
   between variants.
3. Multi-Variant Conflict Resolution — detecting and resolving
   conflicting responses across variants/channels.

Plus edge cases for BC-008 (never crash) and thread-safety.
"""

import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# Module-level stubs — populated by the autouse fixture below.
# These satisfy pyflakes F821 checks; the real imports happen
# inside the fixture after the logger is mocked.
CrossVariantInteractionService = None  # type: ignore[assignment,misc]
ConfidenceEscalationResult = None  # type: ignore[assignment,misc]
HandoffContext = None  # type: ignore[assignment,misc]
HandoffResult = None  # type: ignore[assignment,misc]
RegisteredResponse = None  # type: ignore[assignment,misc]
ConflictCheckResult = None  # type: ignore[assignment,misc]
ConflictResult = None  # type: ignore[assignment,misc]
ResolutionResult = None  # type: ignore[assignment,misc]
CustomerInteractionSummary = None  # type: ignore[assignment,misc]
ConfidenceHistoryEntry = None  # type: ignore[assignment,misc]
EscalationReason = None  # type: ignore[assignment,misc]
ConflictSeverity = None  # type: ignore[assignment,misc]
ResolutionStrategy = None  # type: ignore[assignment,misc]
HandoffStatus = None  # type: ignore[assignment,misc]
CrossVariantInteractionError = None  # type: ignore[assignment,misc]
CONFIDENCE_THRESHOLDS = None  # type: ignore[assignment,misc]
CONFLICT_TIME_WINDOW_SECONDS = None  # type: ignore[assignment,misc]
ESCALATION_CHAIN = None  # type: ignore[assignment,misc]
VALID_VARIANTS = None  # type: ignore[assignment,misc]


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.cross_variant_interaction import (
            CrossVariantInteractionService,
            ConfidenceEscalationResult,
            HandoffContext,
            HandoffResult,
            RegisteredResponse,
            ConflictCheckResult,
            ConflictResult,
            ResolutionResult,
            CustomerInteractionSummary,
            ConfidenceHistoryEntry,
            EscalationReason,
            ConflictSeverity,
            ResolutionStrategy,
            HandoffStatus,
            CrossVariantInteractionError,
            CONFIDENCE_THRESHOLDS,
            CONFLICT_TIME_WINDOW_SECONDS,
            ESCALATION_CHAIN,
            VALID_VARIANTS,
        )
        globals().update({
            "CrossVariantInteractionService": CrossVariantInteractionService,
            "ConfidenceEscalationResult": ConfidenceEscalationResult,
            "HandoffContext": HandoffContext,
            "HandoffResult": HandoffResult,
            "RegisteredResponse": RegisteredResponse,
            "ConflictCheckResult": ConflictCheckResult,
            "ConflictResult": ConflictResult,
            "ResolutionResult": ResolutionResult,
            "CustomerInteractionSummary": CustomerInteractionSummary,
            "ConfidenceHistoryEntry": ConfidenceHistoryEntry,
            "EscalationReason": EscalationReason,
            "ConflictSeverity": ConflictSeverity,
            "ResolutionStrategy": ResolutionStrategy,
            "HandoffStatus": HandoffStatus,
            "CrossVariantInteractionError": CrossVariantInteractionError,
            "CONFIDENCE_THRESHOLDS": CONFIDENCE_THRESHOLDS,
            "CONFLICT_TIME_WINDOW_SECONDS": CONFLICT_TIME_WINDOW_SECONDS,
            "ESCALATION_CHAIN": ESCALATION_CHAIN,
            "VALID_VARIANTS": VALID_VARIANTS,
        })


# ═══════════════════════════════════════════════════════════════════
# 1. Confidence-Based Escalation
# ═══════════════════════════════════════════════════════════════════


class TestConfidenceBasedEscalation:
    """Escalation triggered when variant confidence falls below
    its tier-specific threshold.

    Thresholds:
        mini_parwa  → 0.65
        parwa       → 0.45
        parwa_high  → 0.30
    """

    def setup_method(self):
        self.svc = CrossVariantInteractionService()

    def test_mini_parwa_low_confidence_escalates_to_parwa(self):
        """mini_parwa with confidence 0.50 (< 0.65) should escalate
        to parwa."""
        result = self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-001",
            variant_type="mini_parwa",
            confidence_score=0.50,
            original_query="How do I reset my password?",
            generated_response="I think you go to settings...",
        )
        assert result.should_escalate is True
        assert result.target_variant == "parwa"
        assert result.original_variant == "mini_parwa"
        assert result.requires_human_review is False
        assert result.confidence_score == 0.50
        assert "original_query" in result.escalation_context
        assert result.escalation_context["original_query"] == "How do I reset my password?"

    def test_parwa_low_confidence_escalates_to_parwa_high(self):
        """parwa with confidence 0.30 (< 0.45) should escalate
        to parwa_high."""
        result = self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-002",
            variant_type="parwa",
            confidence_score=0.30,
            original_query="Refund my order",
            generated_response="Let me look into that...",
        )
        assert result.should_escalate is True
        assert result.target_variant == "parwa_high"
        assert result.original_variant == "parwa"
        assert result.requires_human_review is False

    def test_parwa_high_low_confidence_flags_human_review(self):
        """parwa_high with confidence 0.20 (< 0.30) should flag for
        human review because there is no higher tier."""
        result = self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-003",
            variant_type="parwa_high",
            confidence_score=0.20,
            original_query="Complex legal question",
            generated_response="I am not sure about this...",
        )
        assert result.should_escalate is True
        assert result.target_variant == ""
        assert result.requires_human_review is True
        assert "human review" in result.reason.lower()

    def test_sufficient_confidence_no_escalation(self):
        """Any variant with confidence above its threshold should
        NOT escalate."""
        # mini_parwa at 0.70 (>= 0.65) — no escalation
        r1 = self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-004",
            variant_type="mini_parwa",
            confidence_score=0.70,
            original_query="Hello",
            generated_response="Hi there!",
        )
        assert r1.should_escalate is False
        assert r1.target_variant == ""

        # parwa at 0.80 (>= 0.45) — no escalation
        r2 = self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-005",
            variant_type="parwa",
            confidence_score=0.80,
            original_query="Status of order #123?",
            generated_response="Your order is shipped.",
        )
        assert r2.should_escalate is False

        # parwa_high at 0.95 (>= 0.30) — no escalation
        r3 = self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-006",
            variant_type="parwa_high",
            confidence_score=0.95,
            original_query="Legal question",
            generated_response="Here is the answer...",
        )
        assert r3.should_escalate is False

    def test_confidence_history_tracking(self):
        """get_confidence_history should return entries after
        evaluations."""
        self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-HIST",
            variant_type="mini_parwa",
            confidence_score=0.40,
            original_query="Q1",
            generated_response="A1",
        )
        self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-HIST",
            variant_type="mini_parwa",
            confidence_score=0.80,
            original_query="Q2",
            generated_response="A2",
        )
        history = self.svc.get_confidence_history("co1", "TKT-HIST")
        assert len(history) == 2
        assert history[0].ticket_id == "TKT-HIST"
        assert history[0].variant_type == "mini_parwa"
        assert history[0].confidence_score == 0.40
        assert history[0].escalated is True
        assert history[1].confidence_score == 0.80
        assert history[1].escalated is False

    def test_unknown_variant_no_escalation(self):
        """Unknown variant type should return safe no-escalation
        result (BC-008)."""
        result = self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-UNK",
            variant_type="unknown_variant",
            confidence_score=0.10,
            original_query="test",
            generated_response="test",
        )
        assert result.should_escalate is False
        assert result.target_variant == ""
        assert result.requires_human_review is False
        assert "unknown" in result.reason.lower()

    def test_exact_threshold_value_no_escalation(self):
        """Confidence exactly at the threshold should NOT escalate."""
        result = self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-EXACT",
            variant_type="mini_parwa",
            confidence_score=0.65,
            original_query="Q",
            generated_response="A",
        )
        assert result.should_escalate is False

    def test_confidence_clamped_to_valid_range(self):
        """Confidence scores outside 0.0–1.0 are clamped."""
        # Negative confidence clamped to 0.0
        r1 = self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-CLAMP1",
            variant_type="mini_parwa",
            confidence_score=-0.5,
            original_query="Q",
            generated_response="A",
        )
        assert r1.confidence_score == 0.0
        assert r1.should_escalate is True  # 0.0 < 0.65

        # Confidence > 1.0 clamped to 1.0
        r2 = self.svc.evaluate_confidence_escalation(
            company_id="co1",
            ticket_id="TKT-CLAMP2",
            variant_type="mini_parwa",
            confidence_score=1.5,
            original_query="Q",
            generated_response="A",
        )
        assert r2.confidence_score == 1.0
        assert r2.should_escalate is False  # 1.0 >= 0.65


# ═══════════════════════════════════════════════════════════════════
# 2. Same-Ticket Handoff
# ═══════════════════════════════════════════════════════════════════


class TestSameTicketHandoff:
    """Handoff lifecycle: initiate → retrieve context → acknowledge.

    Validates that full context (conversation history, classification,
    sentiment, customer data) is bundled and preserved through the
    handoff.
    """

    def setup_method(self):
        self.svc = CrossVariantInteractionService()
        self.sample_history = [
            {"role": "user", "content": "Hello", "timestamp": "2025-01-01T00:00:00Z"},
            {"role": "agent", "content": "Hi there!", "variant": "mini_parwa",
             "timestamp": "2025-01-01T00:00:05Z"},
            {"role": "user", "content": "I need help with billing",
             "timestamp": "2025-01-01T00:00:10Z"},
        ]

    def test_initiate_handoff_success(self):
        """Creating a handoff from mini_parwa to parwa should
        succeed with success=True."""
        result = self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-HO1",
            from_variant="mini_parwa",
            to_variant="parwa",
            conversation_history=self.sample_history,
        )
        assert result.success is True
        assert result.duplicate_prevented is False
        assert result.handoff_context is not None
        assert result.handoff_context.ticket_id == "TKT-HO1"
        assert result.handoff_context.from_variant == "mini_parwa"
        assert result.handoff_context.to_variant == "parwa"
        assert result.handoff_context.acknowledged is False
        assert len(result.handoff_context.conversation_history) == 3

    def test_duplicate_handoff_prevented(self):
        """Creating the same handoff twice should return
        duplicate_prevented=True on the second attempt."""
        self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-DUP",
            from_variant="mini_parwa",
            to_variant="parwa",
            conversation_history=self.sample_history,
        )
        result2 = self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-DUP",
            from_variant="mini_parwa",
            to_variant="parwa",
            conversation_history=self.sample_history,
        )
        assert result2.success is True
        assert result2.duplicate_prevented is True
        assert result2.handoff_context is not None

    def test_get_handoff_context_returns_context(self):
        """get_handoff_context should return the stored context
        after a handoff is created."""
        self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-GH",
            from_variant="parwa",
            to_variant="parwa_high",
            conversation_history=self.sample_history,
        )
        ctx = self.svc.get_handoff_context("co1", "TKT-GH", "parwa_high")
        assert ctx is not None
        assert ctx.ticket_id == "TKT-GH"
        assert ctx.from_variant == "parwa"
        assert ctx.to_variant == "parwa_high"
        assert ctx.conversation_history == self.sample_history

    def test_acknowledge_handoff_success(self):
        """Acknowledging a handoff should return True and update
        the acknowledged_at timestamp."""
        self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-ACK",
            from_variant="mini_parwa",
            to_variant="parwa",
            conversation_history=self.sample_history,
        )
        before = datetime.now(timezone.utc)
        ok = self.svc.acknowledge_handoff("co1", "TKT-ACK", "parwa")
        after = datetime.now(timezone.utc)
        assert ok is True
        # Verify the context was updated
        ctx = self.svc.get_handoff_context("co1", "TKT-ACK", "parwa")
        assert ctx is not None
        assert ctx.acknowledged is True
        assert ctx.acknowledged_at is not None
        assert before <= ctx.acknowledged_at <= after

    def test_acknowledge_nonexistent_handoff(self):
        """Acknowledging a handoff that doesn't exist should
        return False."""
        ok = self.svc.acknowledge_handoff("co1", "TKT-NOPE", "parwa")
        assert ok is False

    def test_get_active_handoffs_filters_acknowledged(self):
        """Active handoffs should exclude acknowledged ones."""
        # Create two handoffs
        self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-ACT1",
            from_variant="mini_parwa",
            to_variant="parwa",
            conversation_history=self.sample_history,
        )
        self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-ACT2",
            from_variant="mini_parwa",
            to_variant="parwa",
            conversation_history=self.sample_history,
        )
        # Both should be active
        active = self.svc.get_active_handoffs("co1")
        assert len(active) == 2

        # Acknowledge one
        self.svc.acknowledge_handoff("co1", "TKT-ACT1", "parwa")

        # Only one should remain active
        active = self.svc.get_active_handoffs("co1")
        assert len(active) == 1
        assert active[0].handoff_context.ticket_id == "TKT-ACT2"

    def test_handoff_bundles_full_context(self):
        """Verify conversation_history, classification_data,
        sentiment_data, customer_context are all preserved."""
        classification = {"category": "billing", "priority": "high"}
        sentiment = {"score": -0.5, "label": "frustrated"}
        customer_ctx = {"plan": "enterprise", "region": "US"}

        result = self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-FULL",
            from_variant="mini_parwa",
            to_variant="parwa",
            conversation_history=self.sample_history,
            classification_data=classification,
            sentiment_data=sentiment,
            customer_context=customer_ctx,
        )
        assert result.success is True
        ctx = result.handoff_context
        assert ctx.conversation_history == self.sample_history
        assert ctx.classification_data == classification
        assert ctx.sentiment_data == sentiment
        assert ctx.customer_context == customer_ctx

    def test_recreate_handoff_after_acknowledge(self):
        """After a handoff is acknowledged, a new handoff for the
        same ticket+variant should succeed (not be blocked as
        duplicate)."""
        self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-RENEW",
            from_variant="mini_parwa",
            to_variant="parwa",
            conversation_history=self.sample_history,
        )
        self.svc.acknowledge_handoff("co1", "TKT-RENEW", "parwa")
        result2 = self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-RENEW",
            from_variant="mini_parwa",
            to_variant="parwa",
            conversation_history=self.sample_history,
        )
        assert result2.success is True
        assert result2.duplicate_prevented is False


# ═══════════════════════════════════════════════════════════════════
# 3. Multi-Variant Conflict Resolution
# ═══════════════════════════════════════════════════════════════════


class TestMultiVariantConflictResolution:
    """Detecting and resolving conflicts when different variants
    respond to the same customer on different channels within
    the time window.

    Severity heuristic:
        - Identical content → LOW
        - conf_delta > 0.40 AND tier_delta >= 2 → HIGH
        - conf_delta > 0.20 OR tier_delta >= 1 → MEDIUM
        - else → LOW
    """

    def setup_method(self):
        self.svc = CrossVariantInteractionService()

    def test_register_single_response_no_conflict(self):
        """A single response registration should not trigger a
        conflict."""
        result = self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-R1",
            customer_id="CUST-001",
            variant_type="mini_parwa",
            channel="chat",
            response_content="Your order is on its way.",
            confidence_score=0.90,
        )
        assert result.has_conflict is False
        assert result.conflict_id == ""

    def test_conflicting_responses_detected(self):
        """Responses from different variants on different channels
        for the same customer within the time window should
        trigger a conflict."""
        # First response: mini_parwa on chat
        r1 = self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-C1",
            customer_id="CUST-002",
            variant_type="mini_parwa",
            channel="chat",
            response_content="We will refund your order.",
            confidence_score=0.70,
        )
        assert r1.has_conflict is False

        # Second response: parwa on email — different variant +
        # different channel → conflict
        r2 = self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-C2",
            customer_id="CUST-002",
            variant_type="parwa",
            channel="email",
            response_content="Your refund has been processed.",
            confidence_score=0.60,
        )
        assert r2.has_conflict is True
        assert r2.conflict_id != ""
        assert len(r2.conflicting_responses) == 2
        assert r2.customer_id == "CUST-002"

    def test_same_variant_same_channel_no_conflict(self):
        """Responses from the same variant or on the same channel
        should NOT trigger a conflict."""
        # Same variant, different channel → no conflict
        # (same variant is filtered out)
        self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-SV1",
            customer_id="CUST-003",
            variant_type="parwa",
            channel="chat",
            response_content="Hello!",
            confidence_score=0.90,
        )
        r2 = self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-SV2",
            customer_id="CUST-003",
            variant_type="parwa",
            channel="email",
            response_content="How can I help?",
            confidence_score=0.85,
        )
        assert r2.has_conflict is False

    def test_conflict_severity_levels(self):
        """Test all three severity levels: LOW, MEDIUM, HIGH."""
        # LOW severity: identical content
        self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-SEV1",
            customer_id="CUST-SEV",
            variant_type="mini_parwa",
            channel="chat",
            response_content="Your order has been shipped.",
            confidence_score=0.90,
        )
        r_low = self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-SEV2",
            customer_id="CUST-SEV",
            variant_type="parwa",
            channel="email",
            response_content="Your order has been shipped.",
            confidence_score=0.85,
        )
        assert r_low.has_conflict is True
        assert r_low.severity == ConflictSeverity.LOW

    def test_conflict_severity_high(self):
        """HIGH severity: large confidence delta + tier delta >= 2."""
        self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-HIGH1",
            customer_id="CUST-HIGH",
            variant_type="mini_parwa",
            channel="chat",
            response_content="Yes, the feature is available.",
            confidence_score=0.95,
        )
        r_high = self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-HIGH2",
            customer_id="CUST-HIGH",
            variant_type="parwa_high",
            channel="email",
            response_content="No, that feature is not available.",
            confidence_score=0.30,
        )
        assert r_high.has_conflict is True
        # conf_delta = 0.95 - 0.30 = 0.65 > 0.40
        # tier_delta = 2 (mini_parwa=0, parwa_high=2) >= 2
        assert r_high.severity == ConflictSeverity.HIGH

    def test_conflict_severity_medium(self):
        """MEDIUM severity: moderate confidence delta or tier
        delta >= 1."""
        self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-MED1",
            customer_id="CUST-MED",
            variant_type="mini_parwa",
            channel="chat",
            response_content="Delivery takes 2-3 days.",
            confidence_score=0.80,
        )
        r_med = self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-MED2",
            customer_id="CUST-MED",
            variant_type="parwa",
            channel="email",
            response_content="Delivery takes 3-5 business days.",
            confidence_score=0.50,
        )
        assert r_med.has_conflict is True
        # conf_delta = 0.30, tier_delta = 1
        # Not identical content, conf_delta <= 0.40 but tier_delta >= 1
        assert r_med.severity == ConflictSeverity.MEDIUM

    def test_resolve_conflict_prefer_high_confidence(self):
        """Resolving a MEDIUM conflict with MERGE_PREFER_HIGH_CONFIDENCE
        should pick the highest-confidence response."""
        self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-RES1",
            customer_id="CUST-RES",
            variant_type="mini_parwa",
            channel="chat",
            response_content="We will ship soon.",
            confidence_score=0.60,
        )
        r = self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-RES2",
            customer_id="CUST-RES",
            variant_type="parwa",
            channel="email",
            response_content="Shipped yesterday.",
            confidence_score=0.90,
        )
        assert r.has_conflict is True

        resolution = self.svc.resolve_conflict(
            company_id="co1",
            conflict_id=r.conflict_id,
            strategy=ResolutionStrategy.MERGE_PREFER_HIGH_CONFIDENCE,
        )
        assert resolution.resolved is True
        assert resolution.final_response == "Shipped yesterday."
        assert resolution.strategy_used == ResolutionStrategy.MERGE_PREFER_HIGH_CONFIDENCE
        assert resolution.conflicts_merged == 2

    def test_resolve_conflict_human_review(self):
        """Resolving a HIGH conflict with HUMAN_REVIEW should use
        the highest-tier variant's response."""
        self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-HR1",
            customer_id="CUST-HR",
            variant_type="mini_parwa",
            channel="chat",
            response_content="Feature is available.",
            confidence_score=0.95,
        )
        r = self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-HR2",
            customer_id="CUST-HR",
            variant_type="parwa_high",
            channel="email",
            response_content="Feature not available.",
            confidence_score=0.30,
        )
        assert r.has_conflict is True

        resolution = self.svc.resolve_conflict(
            company_id="co1",
            conflict_id=r.conflict_id,
            strategy=ResolutionStrategy.HUMAN_REVIEW,
        )
        assert resolution.resolved is True
        # parwa_high has higher tier rank than mini_parwa
        assert resolution.final_response == "Feature not available."
        assert resolution.strategy_used == ResolutionStrategy.HUMAN_REVIEW

    def test_resolve_conflict_not_found(self):
        """Resolving a non-existent conflict_id should return
        resolved=False."""
        resolution = self.svc.resolve_conflict(
            company_id="co1",
            conflict_id="nonexistent-conflict-id",
            strategy=ResolutionStrategy.NO_ACTION,
        )
        assert resolution.resolved is False
        assert "not found" in resolution.message.lower()

    def test_customer_interaction_summary(self):
        """Verify summary shows all variants, channels,
        interaction counts, and active conflicts."""
        self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-SUM1",
            customer_id="CUST-SUM",
            variant_type="mini_parwa",
            channel="chat",
            response_content="Hello!",
            confidence_score=0.90,
        )
        self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-SUM2",
            customer_id="CUST-SUM",
            variant_type="parwa",
            channel="email",
            response_content="Welcome!",
            confidence_score=0.85,
        )
        self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-SUM3",
            customer_id="CUST-SUM",
            variant_type="mini_parwa",
            channel="chat",
            response_content="How can I help?",
            confidence_score=0.88,
        )

        summary = self.svc.get_customer_interaction_summary("co1", "CUST-SUM")
        assert summary.customer_id == "CUST-SUM"
        assert summary.total_interactions == 3
        assert "mini_parwa" in summary.variants_used
        assert "parwa" in summary.variants_used
        assert "chat" in summary.channels_used
        assert "email" in summary.channels_used
        assert summary.interactions_by_variant["mini_parwa"] == 2
        assert summary.interactions_by_variant["parwa"] == 1
        assert summary.last_interaction_at is not None

    def test_no_conflict_outside_time_window(self):
        """Responses outside the 300s window should not conflict."""
        now = datetime.now(timezone.utc)
        past_time = now - timedelta(seconds=400)

        # Register first response with a past timestamp
        old_response = RegisteredResponse(
            ticket_id="TKT-TW1",
            customer_id="CUST-TW",
            variant_type="mini_parwa",
            channel="chat",
            response_content="Old response.",
            confidence_score=0.90,
            timestamp=past_time,
        )
        with self.svc._lock:
            if "co1" not in self.svc._customer_interactions:
                self.svc._customer_interactions["co1"] = {}
            if "CUST-TW" not in self.svc._customer_interactions["co1"]:
                self.svc._customer_interactions["co1"]["CUST-TW"] = []
            self.svc._customer_interactions["co1"]["CUST-TW"].append(
                old_response,
            )

        # Register a new response — should NOT conflict with old one
        r = self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-TW2",
            customer_id="CUST-TW",
            variant_type="parwa",
            channel="email",
            response_content="New response.",
            confidence_score=0.85,
        )
        assert r.has_conflict is False

    def test_check_conflicts_returns_active(self):
        """check_conflicts should return all unresolved conflicts
        for a customer."""
        r = self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-CC1",
            customer_id="CUST-CC",
            variant_type="mini_parwa",
            channel="chat",
            response_content="A",
            confidence_score=0.80,
        )
        self.svc.register_response(
            company_id="co1",
            ticket_id="TKT-CC2",
            customer_id="CUST-CC",
            variant_type="parwa",
            channel="email",
            response_content="B",
            confidence_score=0.50,
        )
        conflicts = self.svc.check_conflicts("co1", "CUST-CC")
        assert len(conflicts) >= 1
        # All should be unresolved
        for c in conflicts:
            assert c.resolved is False


# ═══════════════════════════════════════════════════════════════════
# 4. Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """BC-008 compliance, invalid inputs, empty data, and
    thread-safety.
    """

    def setup_method(self):
        self.svc = CrossVariantInteractionService()

    def test_empty_conversation_history_handoff(self):
        """Handoff with empty history should still succeed."""
        result = self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-EMPTY",
            from_variant="mini_parwa",
            to_variant="parwa",
            conversation_history=[],
        )
        assert result.success is True
        assert result.handoff_context is not None
        assert result.handoff_context.conversation_history == []

    def test_invalid_variant_handoff_fails(self):
        """Handoff with invalid variant name should return
        success=False."""
        # Invalid from_variant
        r1 = self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-INV1",
            from_variant="invalid_variant",
            to_variant="parwa",
            conversation_history=[{"role": "user", "content": "hi"}],
        )
        assert r1.success is False
        assert "invalid from_variant" in r1.message.lower()

        # Invalid to_variant
        r2 = self.svc.initiate_handoff(
            company_id="co1",
            ticket_id="TKT-INV2",
            from_variant="mini_parwa",
            to_variant="nonexistent",
            conversation_history=[{"role": "user", "content": "hi"}],
        )
        assert r2.success is False
        assert "invalid to_variant" in r2.message.lower()

    def test_bc008_never_crashes(self):
        """Passing None/bad inputs to all public methods should
        never raise exceptions (BC-008 compliance)."""

        # evaluate_confidence_escalation with None values
        r1 = self.svc.evaluate_confidence_escalation(
            company_id=None,  # type: ignore[arg-type]
            ticket_id=None,  # type: ignore[arg-type]
            variant_type=None,  # type: ignore[arg-type]
            confidence_score="not_a_number",  # type: ignore[arg-type]
            original_query=None,  # type: ignore[arg-type]
            generated_response=None,  # type: ignore[arg-type]
        )
        assert isinstance(r1, ConfidenceEscalationResult)

        # get_confidence_history with None
        r2 = self.svc.get_confidence_history(
            None, None)  # type: ignore[arg-type]
        assert isinstance(r2, list)

        # initiate_handoff with bad input
        r3 = self.svc.initiate_handoff(
            company_id=None,  # type: ignore[arg-type]
            ticket_id=None,  # type: ignore[arg-type]
            from_variant=None,  # type: ignore[arg-type]
            to_variant=None,  # type: ignore[arg-type]
            conversation_history=None,  # type: ignore[arg-type]
        )
        assert isinstance(r3, HandoffResult)

        # get_handoff_context with None
        r4 = self.svc.get_handoff_context(
            None, None, None)  # type: ignore[arg-type]
        # Should return None or HandoffContext, not crash
        assert r4 is None or isinstance(r4, HandoffContext)

        # acknowledge_handoff with None
        r5 = self.svc.acknowledge_handoff(
            None, None, None)  # type: ignore[arg-type]
        assert isinstance(r5, bool)

        # get_active_handoffs with None
        r6 = self.svc.get_active_handoffs(None)  # type: ignore[arg-type]
        assert isinstance(r6, list)

        # register_response with bad inputs
        r7 = self.svc.register_response(
            company_id=None,  # type: ignore[arg-type]
            ticket_id=None,  # type: ignore[arg-type]
            customer_id=None,  # type: ignore[arg-type]
            variant_type=None,  # type: ignore[arg-type]
            channel=None,  # type: ignore[arg-type]
            response_content=None,  # type: ignore[arg-type]
            confidence_score="bad",  # type: ignore[arg-type]
        )
        assert isinstance(r7, ConflictCheckResult)

        # check_conflicts with None
        r8 = self.svc.check_conflicts(None, None)  # type: ignore[arg-type]
        assert isinstance(r8, list)

        # resolve_conflict with None
        r9 = self.svc.resolve_conflict(
            None,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
        )
        assert isinstance(r9, ResolutionResult)

        # get_customer_interaction_summary with None
        r10 = self.svc.get_customer_interaction_summary(
            None,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
        )
        assert isinstance(r10, CustomerInteractionSummary)

    def test_concurrent_access_thread_safety(self):
        """Rapid concurrent calls to multiple methods should not
        crash (thread-safety via internal lock)."""
        svc = CrossVariantInteractionService()
        errors: list = []
        num_threads = 20

        def worker(tid: int):
            """Each thread runs a mix of operations."""
            try:
                # Confidence evaluation
                svc.evaluate_confidence_escalation(
                    company_id="co-conc",
                    ticket_id=f"TKT-{tid}",
                    variant_type="mini_parwa",
                    confidence_score=0.3 + (tid % 50) / 100.0,
                    original_query=f"query-{tid}",
                    generated_response=f"response-{tid}",
                )
                # Handoff
                svc.initiate_handoff(
                    company_id="co-conc",
                    ticket_id=f"TKT-{tid}",
                    from_variant="mini_parwa",
                    to_variant="parwa",
                    conversation_history=[
                        {"role": "user", "content": f"msg-{tid}"}
                    ],
                )
                # Register response
                svc.register_response(
                    company_id="co-conc",
                    ticket_id=f"TKT-{tid}",
                    customer_id=f"CUST-{tid % 5}",
                    variant_type="mini_parwa" if tid % 2 == 0 else "parwa",
                    channel="chat" if tid % 2 == 0 else "email",
                    response_content=f"response-{tid}",
                    confidence_score=0.5 + (tid % 30) / 100.0,
                )
                # Get summary
                svc.get_customer_interaction_summary(
                    "co-conc",
                    f"CUST-{tid % 5}",
                )
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, (
            f"Concurrent access produced {len(errors)} errors: {errors}"
        )


# ═══════════════════════════════════════════════════════════════════
# 5. Constants & Enum Verification
# ═══════════════════════════════════════════════════════════════════


class TestConstantsAndEnums:
    """Verify module-level constants and enum values are correct."""

    def test_confidence_thresholds(self):
        assert CONFIDENCE_THRESHOLDS == {
            "mini_parwa": 0.65,
            "parwa": 0.45,
            "parwa_high": 0.30,
        }

    def test_escalation_chain(self):
        assert ESCALATION_CHAIN == ["mini_parwa", "parwa", "parwa_high"]

    def test_valid_variants(self):
        assert VALID_VARIANTS == {"mini_parwa", "parwa", "parwa_high"}

    def test_conflict_time_window(self):
        assert CONFLICT_TIME_WINDOW_SECONDS == 300.0

    def test_escalation_reason_values(self):
        assert EscalationReason.LOW_CONFIDENCE.value == "low_confidence"
        assert EscalationReason.CONTEXT_TRANSFER.value == "context_transfer"
        assert EscalationReason.CONFLICT_DETECTED.value == "conflict_detected"
        assert EscalationReason.TECHNIQUE_UNAVAILABLE.value == "technique_unavailable"
        assert EscalationReason.MANUAL_REQUEST.value == "manual_request"

    def test_conflict_severity_values(self):
        assert ConflictSeverity.LOW.value == "LOW"
        assert ConflictSeverity.MEDIUM.value == "MEDIUM"
        assert ConflictSeverity.HIGH.value == "HIGH"

    def test_resolution_strategy_values(self):
        assert ResolutionStrategy.NO_ACTION.value == "no_action"
        assert ResolutionStrategy.MERGE_PREFER_HIGH_CONFIDENCE.value == "merge_prefer_high_confidence"
        assert ResolutionStrategy.HUMAN_REVIEW.value == "human_review"

    def test_handoff_status_values(self):
        assert HandoffStatus.PENDING.value == "pending"
        assert HandoffStatus.ACKNOWLEDGED.value == "acknowledged"


# ═══════════════════════════════════════════════════════════════════
# 6. Service Initialization
# ═══════════════════════════════════════════════════════════════════


class TestServiceInitialization:
    """Verify clean initial state after construction."""

    def test_service_creates_instance(self):
        svc = CrossVariantInteractionService()
        assert svc is not None

    def test_empty_confidence_history(self):
        svc = CrossVariantInteractionService()
        assert svc.get_confidence_history("co1", "TKT-NEW") == []

    def test_empty_active_handoffs(self):
        svc = CrossVariantInteractionService()
        assert svc.get_active_handoffs("co1") == []

    def test_empty_conflicts(self):
        svc = CrossVariantInteractionService()
        assert svc.check_conflicts("co1", "CUST-NEW") == []

    def test_empty_interaction_summary(self):
        svc = CrossVariantInteractionService()
        summary = svc.get_customer_interaction_summary("co1", "CUST-NEW")
        assert summary.total_interactions == 0
        assert summary.variants_used == []
        assert summary.channels_used == []

    def test_custom_error_is_properly_constructed(self):
        err = CrossVariantInteractionError(
            message="test error",
            details={"key": "value"},
        )
        assert err.message == "test error"
        assert err.details == {"key": "value"}
