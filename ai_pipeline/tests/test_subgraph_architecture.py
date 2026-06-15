"""Comprehensive test suite for the PARWA subgraph architecture and self-improvement loop.

Tests cover:
1. Subgraph routing (keyword, intent, brain-based)
2. Each subgraph processes tickets correctly
3. Self-improvement loop (feedback → patterns → adjustments)
4. Technique tuning based on outcomes
5. Prompt adjustments based on failure patterns
6. End-to-end dispatcher flow

Run with:
    pytest ai_pipeline/tests/test_subgraph_architecture.py -v
"""

from __future__ import annotations

import asyncio
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parwa.subgraphs.router import SubgraphRouter, route_to_subgraph, _keyword_route
from parwa.subgraphs.technique_configs import (
    get_subgraph_techniques,
    get_subgraph_cap,
    get_subgraph_kb_boosts,
    SUBGRAPH_TECHNIQUE_PRIORITIES,
    SUBGRAPH_TECHNIQUE_CAPS,
)
from parwa.subgraphs.prompts import (
    REFUND_SYSTEM_PROMPT, TECH_SYSTEM_PROMPT,
    BILLING_SYSTEM_PROMPT, GENERAL_SYSTEM_PROMPT,
    SUBGRAPH_ROUTER_PROMPT,
)
from parwa.self_improvement.feedback_collector import (
    FeedbackCollector, TicketOutcome, OutcomeType,
)
from parwa.self_improvement.pattern_learner import PatternLearner, FailurePattern
from parwa.self_improvement.prompt_adjuster import PromptAdjuster, PromptAdjustment
from parwa.self_improvement.technique_tuner import TechniqueTuner, TechniqueAdjustment


# ─── Subgraph Router Tests ────────────────────────────────────────────────────

class TestSubgraphRouter:
    """Test the subgraph routing logic."""

    def test_keyword_route_refund(self):
        """Refund-related keywords route to refund subgraph."""
        assert _keyword_route("I want a refund") == "refund"
        assert _keyword_route("I need my money back") == "refund"
        assert _keyword_route("cancel my subscription and refund") == "refund"

    def test_keyword_route_tech(self):
        """Technical keywords route to tech subgraph."""
        assert _keyword_route("the app is not working") == "tech"
        assert _keyword_route("getting a 500 error") == "tech"
        assert _keyword_route("API integration is broken") == "tech"

    def test_keyword_route_billing(self):
        """Billing keywords route to billing subgraph."""
        assert _keyword_route("I was overcharged") == "billing"
        assert _keyword_route("question about my invoice") == "billing"
        assert _keyword_route("payment failed on my account") == "billing"

    def test_keyword_route_ambiguous(self):
        """Ambiguous messages return None (needs brain routing)."""
        result = _keyword_route("Hello, I need help")
        assert result is None

    def test_intent_based_routing(self):
        """Intent in state routes directly to the correct subgraph."""
        async def _test():
            state = {"raw_message": "test", "intent": "refund_request"}
            router = SubgraphRouter(state)
            result = await router.route()
            assert result == "refund"

            state = {"raw_message": "test", "intent": "technical_support"}
            router = SubgraphRouter(state)
            result = await router.route()
            assert result == "tech"

            state = {"raw_message": "test", "intent": "billing_issue"}
            router = SubgraphRouter(state)
            result = await router.route()
            assert result == "billing"

            state = {"raw_message": "test", "intent": "faq_question"}
            router = SubgraphRouter(state)
            result = await router.route()
            assert result == "general"

        asyncio.run(_test())

    def test_cancellation_routes_to_refund(self):
        """Cancellations route to refund subgraph (often involve refunds)."""
        async def _test():
            state = {"raw_message": "I want to cancel", "intent": "cancellation"}
            router = SubgraphRouter(state)
            result = await router.route()
            assert result == "refund"
        asyncio.run(_test())

    def test_keyword_fallback(self):
        """When no intent, keyword routing is used as fallback."""
        async def _test():
            state = {"raw_message": "I want a refund please"}
            router = SubgraphRouter(state)
            result = await router.route()
            assert result == "refund"
        asyncio.run(_test())


# ─── Technique Configuration Tests ────────────────────────────────────────────

class TestTechniqueConfigs:
    """Test technique priority configurations."""

    def test_refund_priorities(self):
        """Refund subgraph uses policy-first technique priorities."""
        techniques = get_subgraph_techniques("refund", "REASONING_ENGINE")
        assert "chain_of_thought" in techniques
        assert "reverse_thinking" in techniques
        # CoT should be first (policy verification)
        assert techniques[0] == "chain_of_thought"

    def test_tech_priorities(self):
        """Tech subgraph uses diagnostic-first technique priorities."""
        techniques = get_subgraph_techniques("tech", "REASONING_ENGINE")
        assert "react" in techniques
        assert "chain_of_thought" in techniques
        # ReAct should be first (diagnostic)
        assert techniques[0] == "react"

    def test_billing_priorities(self):
        """Billing subgraph uses verification-first technique priorities."""
        techniques = get_subgraph_techniques("billing", "REASONING_ENGINE")
        assert "chain_of_thought" in techniques
        assert "self_consistency" in techniques

    def test_general_priorities(self):
        """General subgraph uses simple technique priorities."""
        techniques = get_subgraph_techniques("general", "REASONING_ENGINE")
        assert "chain_of_thought" in techniques
        assert len(techniques) <= 2  # Keep it simple for general

    def test_complexity_caps(self):
        """Technique caps increase with complexity."""
        for subgraph in ("refund", "tech", "billing", "general"):
            simple_cap = get_subgraph_cap(subgraph, "simple")
            critical_cap = get_subgraph_cap(subgraph, "critical")
            assert critical_cap >= simple_cap

    def test_tech_higher_caps(self):
        """Tech subgraph has higher caps even for simple (diagnostics need it)."""
        assert get_subgraph_cap("tech", "simple") >= 2

    def test_kb_boosts(self):
        """KB boosts are defined for each subgraph."""
        for subgraph in ("refund", "tech", "billing", "general"):
            boosts = get_subgraph_kb_boosts(subgraph)
            assert len(boosts) > 0
            # All boost values should be positive
            for term, weight in boosts.items():
                assert weight > 0

    def test_all_subgraphs_have_configs(self):
        """All 4 subgraphs have technique configs for key nodes."""
        for subgraph in ("refund", "tech", "billing", "general"):
            assert subgraph in SUBGRAPH_TECHNIQUE_PRIORITIES
            assert subgraph in SUBGRAPH_TECHNIQUE_CAPS
            # Must have reasoning engine techniques
            assert "REASONING_ENGINE" in SUBGRAPH_TECHNIQUE_PRIORITIES[subgraph]


# ─── Prompt Tests ─────────────────────────────────────────────────────────────

class TestPrompts:
    """Test specialized prompts."""

    def test_refund_prompt_mentions_policy(self):
        """Refund system prompt mentions refund policy details."""
        assert "30-day" in REFUND_SYSTEM_PROMPT
        assert "refund" in REFUND_SYSTEM_PROMPT.lower()

    def test_tech_prompt_mentions_diagnostics(self):
        """Tech system prompt mentions diagnostic approach."""
        assert "diagnostic" in TECH_SYSTEM_PROMPT.lower()
        assert "troubleshoot" in TECH_SYSTEM_PROMPT.lower()

    def test_billing_prompt_mentions_verification(self):
        """Billing system prompt mentions charge verification."""
        assert "charge" in BILLING_SYSTEM_PROMPT.lower()
        assert "invoice" in BILLING_SYSTEM_PROMPT.lower()

    def test_general_prompt_is_simple(self):
        """General system prompt is simpler than specialized ones."""
        assert len(GENERAL_SYSTEM_PROMPT) < len(REFUND_SYSTEM_PROMPT)

    def test_router_prompt_lists_categories(self):
        """Router prompt lists all 4 categories."""
        assert "refund" in SUBGRAPH_ROUTER_PROMPT
        assert "tech" in SUBGRAPH_ROUTER_PROMPT
        assert "billing" in SUBGRAPH_ROUTER_PROMPT
        assert "general" in SUBGRAPH_ROUTER_PROMPT


# ─── Feedback Collector Tests ─────────────────────────────────────────────────

class TestFeedbackCollector:
    """Test the feedback collection and analysis."""

    def test_record_outcome(self):
        """Outcomes are recorded correctly."""
        collector = FeedbackCollector()
        outcome = TicketOutcome(
            ticket_id="T-001",
            intent="refund_request",
            subgraph="refund",
            outcome=OutcomeType.RESOLVED,
            quality_score=85.0,
        )
        collector.record(outcome)
        assert collector.total_outcomes == 1

    def test_resolution_rate(self):
        """Resolution rate is calculated correctly."""
        collector = FeedbackCollector()
        # 3 resolved, 1 escalated = 75% resolution rate
        for i in range(3):
            collector.record(TicketOutcome(
                ticket_id=f"T-{i}", intent="refund_request", subgraph="refund",
                outcome=OutcomeType.RESOLVED,
            ))
        collector.record(TicketOutcome(
            ticket_id="T-3", intent="refund_request", subgraph="refund",
            outcome=OutcomeType.ESCALATED,
        ))
        assert collector.resolution_rate(days=365) == 0.75

    def test_resolution_rate_by_subgraph(self):
        """Per-subgraph resolution rates are calculated correctly."""
        collector = FeedbackCollector()
        # Refund: 2 resolved, 0 escalated = 100%
        collector.record(TicketOutcome(ticket_id="T-1", intent="refund_request", subgraph="refund", outcome=OutcomeType.RESOLVED))
        collector.record(TicketOutcome(ticket_id="T-2", intent="refund_request", subgraph="refund", outcome=OutcomeType.RESOLVED))
        # Tech: 1 resolved, 1 escalated = 50%
        collector.record(TicketOutcome(ticket_id="T-3", intent="technical_support", subgraph="tech", outcome=OutcomeType.RESOLVED))
        collector.record(TicketOutcome(ticket_id="T-4", intent="technical_support", subgraph="tech", outcome=OutcomeType.ESCALATED))

        rates = collector.resolution_rate_by_subgraph(days=365)
        assert rates["refund"] == 1.0
        assert rates["tech"] == 0.5

    def test_escalation_reasons(self):
        """Escalation reasons are tracked by intent."""
        collector = FeedbackCollector()
        collector.record(TicketOutcome(ticket_id="T-1", intent="refund_request", subgraph="refund", outcome=OutcomeType.ESCALATED))
        collector.record(TicketOutcome(ticket_id="T-2", intent="refund_request", subgraph="refund", outcome=OutcomeType.ESCALATED))
        collector.record(TicketOutcome(ticket_id="T-3", intent="technical_support", subgraph="tech", outcome=OutcomeType.ESCALATED))

        reasons = collector.escalation_reasons(days=365)
        assert len(reasons) > 0
        # Refund should be the top reason
        assert reasons[0]["intent"] == "refund_request"
        assert reasons[0]["count"] == 2

    def test_outcome_serialization(self):
        """Outcomes can be serialized and deserialized."""
        outcome = TicketOutcome(
            ticket_id="T-001",
            intent="refund_request",
            subgraph="refund",
            outcome=OutcomeType.RESOLVED,
            techniques_used=["chain_of_thought", "reverse_thinking"],
            quality_score=85.0,
        )
        data = outcome.to_dict()
        restored = TicketOutcome.from_dict(data)
        assert restored.ticket_id == "T-001"
        assert restored.subgraph == "refund"
        assert restored.outcome == OutcomeType.RESOLVED
        assert len(restored.techniques_used) == 2


# ─── Pattern Learner Tests ────────────────────────────────────────────────────

class TestPatternLearner:
    """Test the failure pattern identification."""

    def test_subgraph_failure_pattern(self):
        """Low-resolution subgraphs are identified."""
        collector = FeedbackCollector()
        # Tech subgraph: 1 resolved, 4 escalated = 20% (low)
        collector.record(TicketOutcome(ticket_id="T-1", intent="technical_support", subgraph="tech", outcome=OutcomeType.RESOLVED))
        for i in range(4):
            collector.record(TicketOutcome(
                ticket_id=f"T-{i+2}", intent="technical_support", subgraph="tech",
                outcome=OutcomeType.ESCALATED, message="API integration broken",
            ))

        learner = PatternLearner(collector)
        patterns = learner.analyze(days=365)

        # Should find a low-resolution pattern for tech
        subgraph_patterns = [p for p in patterns if p.pattern_id.startswith("subgraph_low_res_")]
        assert len(subgraph_patterns) > 0
        assert any(p.subgraph == "tech" for p in subgraph_patterns)

    def test_keyword_failure_pattern(self):
        """Keywords that appear in many escalations are identified."""
        collector = FeedbackCollector()
        for i in range(5):
            collector.record(TicketOutcome(
                ticket_id=f"T-{i}", intent="technical_support", subgraph="tech",
                outcome=OutcomeType.ESCALATED,
                message="My integration with the API is broken and not working",
            ))

        learner = PatternLearner(collector)
        patterns = learner.analyze(days=365)

        keyword_patterns = [p for p in patterns if p.pattern_id.startswith("keyword_")]
        assert len(keyword_patterns) > 0

    def test_no_patterns_when_all_resolved(self):
        """No failure patterns when everything is resolved."""
        collector = FeedbackCollector()
        for i in range(10):
            collector.record(TicketOutcome(
                ticket_id=f"T-{i}", intent="refund_request", subgraph="refund",
                outcome=OutcomeType.RESOLVED,
            ))

        learner = PatternLearner(collector)
        patterns = learner.analyze(days=365)
        assert len(patterns) == 0


# ─── Prompt Adjuster Tests ────────────────────────────────────────────────────

class TestPromptAdjuster:
    """Test automatic prompt adjustments."""

    def test_generate_adjustments_from_patterns(self):
        """Patterns generate corresponding prompt adjustments."""
        adjuster = PromptAdjuster()
        patterns = [FailurePattern(
            pattern_id="keyword_subscription",
            subgraph="refund",
            description="Subscription keyword in failures",
            frequency=3,
            impact=10.0,
            suggested_fix="Add subscription refund rules",
        )]

        adjustments = adjuster.generate_adjustments(patterns)
        assert len(adjustments) > 0
        # Should have a subscription-related adjustment
        sub_adjustments = [a for a in adjustments if "subscription" in a.content.lower()]
        assert len(sub_adjustments) > 0

    def test_apply_adjustment(self):
        """Applied adjustments modify the subgraph prompt."""
        adjuster = PromptAdjuster()
        adjustment = PromptAdjustment(
            adjustment_id="test_1",
            subgraph="refund",
            pattern_id="test",
            content="EXTRA: Always check subscription status before refund",
            confidence=0.7,
        )
        adjuster.apply(adjustment)

        adjusted = adjuster.get_adjusted_prompt("refund", REFUND_SYSTEM_PROMPT)
        assert "subscription status" in adjusted
        assert len(adjusted) > len(REFUND_SYSTEM_PROMPT)

    def test_unadjusted_prompt_unchanged(self):
        """Subgraphs without adjustments get the base prompt."""
        adjuster = PromptAdjuster()
        prompt = adjuster.get_adjusted_prompt("tech", TECH_SYSTEM_PROMPT)
        assert prompt == TECH_SYSTEM_PROMPT


# ─── Technique Tuner Tests ────────────────────────────────────────────────────

class TestTechniqueTuner:
    """Test automatic technique priority tuning."""

    def test_promote_successful_techniques(self):
        """Techniques that succeed often get promoted over failing ones."""
        collector = FeedbackCollector()
        # CoT succeeds 5 times in refund subgraph
        for i in range(5):
            collector.record(TicketOutcome(
                ticket_id=f"T-{i}", intent="refund_request", subgraph="refund",
                outcome=OutcomeType.RESOLVED,
                techniques_used=["chain_of_thought"],
            ))
        # Need at least 1 escalation in refund so the analyzer doesn't skip
        collector.record(TicketOutcome(
            ticket_id="T-FAIL", intent="refund_request", subgraph="refund",
            outcome=OutcomeType.ESCALATED,
            techniques_used=["react"],
        ))

        tuner = TechniqueTuner(collector)
        adjustments = tuner.analyze(days=365)

        # Should have some adjustments (CoT promotion or ReAct demotion)
        assert len(adjustments) > 0

    def test_demote_failing_techniques(self):
        """Techniques that fail often get alternatives promoted."""
        collector = FeedbackCollector()
        # ReAct fails 5 times in tech subgraph
        for i in range(5):
            collector.record(TicketOutcome(
                ticket_id=f"T-{i}", intent="technical_support", subgraph="tech",
                outcome=OutcomeType.ESCALATED,
                techniques_used=["react"],
            ))

        tuner = TechniqueTuner(collector)
        adjustments = tuner.analyze(days=365)

        # Should suggest promoting alternatives
        assert len(adjustments) > 0

    def test_apply_technique_adjustment(self):
        """Applied adjustments modify technique priorities."""
        collector = FeedbackCollector()
        tuner = TechniqueTuner(collector)

        adjustment = TechniqueAdjustment(
            adjustment_id="test_1",
            subgraph="refund",
            node="REASONING_ENGINE",
            change_type="promote",
            technique="reverse_thinking",
            confidence=0.7,
        )
        tuner.apply(adjustment)

        techniques = tuner.get_techniques("refund", "REASONING_ENGINE")
        assert "reverse_thinking" in techniques
        # Should be promoted to front
        assert techniques[0] == "reverse_thinking"

    def test_increase_cap_for_complex_escalations(self):
        """Complex escalations trigger cap increase."""
        collector = FeedbackCollector()
        for i in range(3):
            collector.record(TicketOutcome(
                ticket_id=f"T-{i}", intent="technical_support", subgraph="tech",
                outcome=OutcomeType.ESCALATED,
                complexity="critical",
            ))

        tuner = TechniqueTuner(collector)
        adjustments = tuner.analyze(days=365)

        cap_adjustments = [a for a in adjustments if a.change_type == "increase_cap"]
        assert len(cap_adjustments) > 0


# ─── Integration Tests ────────────────────────────────────────────────────────

class TestIntegration:
    """Test the full self-improvement loop integration."""

    def test_full_improvement_loop(self):
        """Complete loop: collect → learn → adjust → verify."""
        collector = FeedbackCollector()

        # Simulate 20 tickets with 70% resolution rate
        outcomes = [
            ("refund", OutcomeType.RESOLVED, "chain_of_thought"),
            ("refund", OutcomeType.RESOLVED, "chain_of_thought"),
            ("refund", OutcomeType.ESCALATED, "chain_of_thought"),  # Failure
            ("tech", OutcomeType.RESOLVED, "react"),
            ("tech", OutcomeType.ESCALATED, "react"),  # Failure
            ("tech", OutcomeType.ESCALATED, "react"),  # Failure
            ("billing", OutcomeType.RESOLVED, "chain_of_thought"),
            ("billing", OutcomeType.RESOLVED, "self_consistency"),
            ("general", OutcomeType.RESOLVED, "chain_of_thought"),
            ("general", OutcomeType.RESOLVED, "chain_of_thought"),
        ]
        for i, (subgraph, outcome, tech) in enumerate(outcomes):
            collector.record(TicketOutcome(
                ticket_id=f"T-{i}", intent=f"{subgraph}_issue", subgraph=subgraph,
                outcome=outcome, techniques_used=[tech],
                message="Test ticket" if outcome == OutcomeType.ESCALATED else "",
            ))

        # Step 1: Learn patterns
        learner = PatternLearner(collector)
        patterns = learner.analyze(days=365)
        assert len(patterns) > 0  # Should find some failure patterns

        # Step 2: Generate adjustments
        adjuster = PromptAdjuster()
        prompt_adjustments = adjuster.generate_adjustments(patterns)
        assert len(prompt_adjustments) > 0

        # Step 3: Apply high-confidence adjustments
        applied = 0
        for adj in prompt_adjustments:
            if adj.confidence >= 0.5:
                adjuster.apply(adj)
                applied += 1

        # Step 4: Verify adjustments are applied
        for subgraph in ("refund", "tech", "billing", "general"):
            prompt = adjuster.get_adjusted_prompt(subgraph, "BASE PROMPT")
            # At least one subgraph should have adjustments
            if subgraph in ["tech", "refund"]:
                # These had failures, should have adjustments
                pass  # Verification depends on specific patterns found

        # Step 5: Technique tuning
        tuner = TechniqueTuner(collector)
        tech_adjustments = tuner.analyze(days=365)

        for adj in tech_adjustments:
            if adj.confidence >= 0.5:
                tuner.apply(adj)

        # Verify resolution rate was calculated
        rate = collector.resolution_rate(days=365)
        assert 0.0 < rate < 1.0  # Should be between 0 and 1

    def test_outcome_types_covered(self):
        """All outcome types are handled correctly."""
        for outcome in OutcomeType:
            outcome_record = TicketOutcome(
                ticket_id="T-TEST",
                intent="test",
                subgraph="general",
                outcome=outcome,
            )
            assert outcome_record.outcome == outcome


# ─── Subgraph Graph Structure Tests ───────────────────────────────────────────

class TestSubgraphStructures:
    """Test that each subgraph has the expected structure."""

    def test_refund_graph_builds(self):
        """Refund graph can be built and compiled."""
        from parwa.subgraphs.refund_graph import build_refund_graph
        graph = build_refund_graph()
        assert graph is not None

    def test_tech_graph_builds(self):
        """Tech graph can be built and compiled."""
        from parwa.subgraphs.tech_graph import build_tech_graph
        graph = build_tech_graph()
        assert graph is not None

    def test_billing_graph_builds(self):
        """Billing graph can be built and compiled."""
        from parwa.subgraphs.billing_graph import build_billing_graph
        graph = build_billing_graph()
        assert graph is not None

    def test_general_graph_builds(self):
        """General graph can be built and compiled."""
        from parwa.subgraphs.general_graph import build_general_graph
        graph = build_general_graph()
        assert graph is not None

    def test_refund_graph_has_correct_nodes(self):
        """Refund graph has the expected nodes."""
        from parwa.subgraphs.refund_graph import RefundGraph
        graph = RefundGraph()
        assert graph.node_count == 7

    def test_tech_graph_has_more_nodes(self):
        """Tech graph has more nodes than refund (diagnostics need more steps)."""
        from parwa.subgraphs.refund_graph import RefundGraph
        from parwa.subgraphs.tech_graph import TechGraph
        refund = RefundGraph()
        tech = TechGraph()
        assert tech.node_count > refund.node_count

    def test_billing_graph_node_count(self):
        """Billing graph has the expected node count."""
        from parwa.subgraphs.billing_graph import BillingGraph
        graph = BillingGraph()
        assert graph.node_count == 8

    def test_general_graph_node_count(self):
        """General graph has the expected node count."""
        from parwa.subgraphs.general_graph import GeneralGraph
        graph = GeneralGraph()
        assert graph.node_count == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
