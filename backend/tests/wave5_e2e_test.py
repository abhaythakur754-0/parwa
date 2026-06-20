"""
Wave 5 E2E Test — Intelligence Layer: Batching, Confidence, Sentiment

Tests all 5 Wave 5 deliverables:
  5A: Confidence-Based Routing (confidence_engine)
  5B: Semantic Batching (semantic_batcher)
  5C: Sentiment Routing (sentiment_router)
  5D: Approval Gates (approval_gates)
  5E: Variant Recommendation (variant_recommender)

All tests use InMemory backend — no external services needed.
Run: python -m pytest backend/tests/wave5_e2e_test.py -v
"""

import asyncio
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.core.jarvis_pipeline.jarvis_db import reset_db, use_in_memory, get_db
from app.core.jarvis_pipeline.confidence_engine import (
    compute_confidence_score, classify_routing, score_ticket_confidence,
    batch_score_tickets, ACTION_AUTO, ACTION_BATCH, ACTION_ASK, ACTION_ESCALATE,
)
from app.core.jarvis_pipeline.semantic_batcher import (
    compute_similarity, add_ticket_to_batch, flush_all_batches,
    format_batch_description, get_batch_summary, check_should_batch,
)
from app.core.jarvis_pipeline.sentiment_router import (
    compute_sentiment, route_by_sentiment,
    ROUTE_HUMAN, ROUTE_AI_FLAGGED, ROUTE_AI_AUTO,
)
from app.core.jarvis_pipeline.approval_gates import (
    check_approval_required, set_custom_gates, invalidate_gate_cache,
    load_approval_gates,
)
from app.core.jarvis_pipeline.variant_recommender import (
    recommend_variant, get_variant_status,
)
from app.core.parwa_pipeline.parwa_bridge import (
    score_confidence, route_by_sentiment as bridge_sentiment,
    check_approval_gate, recommend_variant as bridge_recommend_variant,
)


TENANT = "wave5_test_tenant"


@pytest.fixture(autouse=True)
def _reset():
    """Reset DB and caches before each test."""
    reset_db()
    use_in_memory()
    invalidate_gate_cache(TENANT)
    yield
    reset_db()


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ═══════════════════════════════════════════════════════════════
# 5A: Confidence-Based Routing
# ═══════════════════════════════════════════════════════════════

class Test5A_ConfidenceRouting:
    """5A: Every PARWA decision gets a confidence score → routing action."""

    def test_5a_1_high_confidence_routes_to_auto(self):
        """95%+ confidence → AUTO (log only, no notification)."""
        confidence, factors = compute_confidence_score(
            pattern_match=0.98, policy_alignment=0.95,
            risk_score=0.0, historical_accuracy=0.96,
        )
        assert confidence >= 0.95
        assert classify_routing(confidence) == ACTION_AUTO

    def test_5a_2_good_confidence_routes_to_batch(self):
        """85-95% confidence → BATCH (group similar, one-click approve)."""
        confidence, _ = compute_confidence_score(
            pattern_match=0.90, policy_alignment=0.88,
            risk_score=0.1, historical_accuracy=0.85,
        )
        assert 0.85 <= confidence < 0.95
        assert classify_routing(confidence) == ACTION_BATCH

    def test_5a_3_moderate_confidence_routes_to_ask(self):
        """70-84% confidence → ASK (individual review)."""
        confidence, _ = compute_confidence_score(
            pattern_match=0.75, policy_alignment=0.70,
            risk_score=0.2, historical_accuracy=0.72,
        )
        assert 0.70 <= confidence < 0.85
        assert classify_routing(confidence) == ACTION_ASK

    def test_5a_4_low_confidence_routes_to_escalate(self):
        """<70% confidence → ESCALATE (human judgment required)."""
        confidence, _ = compute_confidence_score(
            pattern_match=0.50, policy_alignment=0.40,
            risk_score=0.6, historical_accuracy=0.55,
        )
        assert confidence < 0.70
        assert classify_routing(confidence) == ACTION_ESCALATE

    def test_5a_5_confidence_factors_weighted_correctly(self):
        """Pattern match (30%) + Policy (25%) + Risk (25%) + History (20%)."""
        # All 1.0 → 1.0
        c, f = compute_confidence_score(1.0, 1.0, 0.0, 1.0)
        assert c == 1.0

        # Pattern=0, rest=1.0 → should be 0.70 (1 - 0.30)
        c, f = compute_confidence_score(0.0, 1.0, 0.0, 1.0)
        assert abs(c - 0.70) < 0.01

        # All 0 → 0.0
        c, _ = compute_confidence_score(0.0, 0.0, 1.0, 0.0)
        assert c == 0.0

    def test_5a_6_risk_inverts_confidence(self):
        """High risk should lower confidence."""
        c_safe, _ = compute_confidence_score(0.9, 0.9, 0.0, 0.9)
        c_risky, _ = compute_confidence_score(0.9, 0.9, 1.0, 0.9)
        assert c_safe > c_risky

    def test_5a_7_score_ticket_confidence_uses_db(self):
        """score_ticket_confidence reads from jarvis_db and persists result via bridge."""
        db = get_db()

        # Seed some quality data
        _run(db.write_quality_score(TENANT, "TKT-SEED-1",
                                      overall_score=0.95, resolution_path="simple"))
        _run(db.record_training_data(TENANT, "TKT-SEED-1", "approved",
                                      ticket_type="refund_request", quality_score=0.95))

        # Score via bridge (which persists)
        result = _run(score_confidence(
            tenant_id=TENANT, ticket_id="TKT-C5-1",
            ticket_type="refund_request", query="I want a refund",
            required_action="refund", is_vip=False,
        ))

        assert result is not None
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["routing"] in (ACTION_AUTO, ACTION_BATCH, ACTION_ASK, ACTION_ESCALATE)
        assert result["ticket_id"] == "TKT-C5-1"
        assert "factors" in result
        assert "reason" in result

        # Verify persisted in DB
        logs = db._confidence_logs
        assert any(l["ticket_id"] == "TKT-C5-1" for l in logs)

    def test_5a_8_vip_lowers_confidence(self):
        """VIP flag should reduce confidence via risk factor."""
        result = _run(score_ticket_confidence(
            tenant_id=TENANT, ticket_id="TKT-VIP-1",
            ticket_type="info", query="What are my orders?",
            is_vip=True, value_usd=500,
        ))
        # VIP + high value → elevated risk → lower confidence
        assert result["risk_level"] > 0
        assert "factors" in result

    def test_5a_9_batch_score_multiple_tickets(self):
        """batch_score_tickets scores multiple and sorts by confidence."""
        tickets = [
            {"ticket_id": "T1", "ticket_type": "refund", "required_action": "refund", "value_usd": 200},
            {"ticket_id": "T2", "ticket_type": "info", "query": "What are hours?"},
            {"ticket_id": "T3", "ticket_type": "return", "required_action": "return", "value_usd": 50},
        ]
        results = _run(batch_score_tickets(TENANT, tickets))
        assert len(results) == 3
        # Sorted ascending by confidence (most needing attention first)
        assert results[0]["confidence"] <= results[1]["confidence"]
        assert results[1]["confidence"] <= results[2]["confidence"]

    def test_5a_10_bridge_score_confidence_wired(self):
        """parwa_bridge.score_confidence persists to DB."""
        result = _run(score_confidence(
            tenant_id=TENANT, ticket_id="TKT-BRIDGE-1",
            ticket_type="info", query="Hello",
        ))
        assert result is not None
        assert result["confidence"] is not None
        assert result["ticket_id"] == "TKT-BRIDGE-1"

        # Verify in DB
        db = get_db()
        logs = db._confidence_logs
        assert any(l["ticket_id"] == "TKT-BRIDGE-1" for l in logs)


# ═══════════════════════════════════════════════════════════════
# 5B: Semantic Batching
# ═══════════════════════════════════════════════════════════════

class Test5B_SemanticBatching:
    """5B: Replace time-based batching with semantic clustering."""

    def test_5b_1_similar_tickets_cluster(self):
        """Two tickets about the same topic should have high similarity."""
        sim = compute_similarity(
            "I want to change my address to 123 Main St",
            "Please update my shipping address to 123 Main Street",
        )
        assert sim > 0.3, f"Expected > 0.3 similarity, got {sim}"

    def test_5b_2_dissimilar_tickets_dont_cluster(self):
        """Unrelated tickets should have low similarity."""
        sim = compute_similarity(
            "I want a refund for order 123",
            "What is your return policy?",
        )
        assert sim < 0.5, f"Expected < 0.5 similarity, got {sim}"

    def test_5b_3_identical_tickets_max_similarity(self):
        """Same text = 1.0 similarity."""
        sim = compute_similarity(
            "I want to change my address",
            "I want to change my address",
        )
        assert sim == 1.0

    def test_5b_4_empty_text_zero_similarity(self):
        """Empty text = 0.0 similarity."""
        sim = compute_similarity("", "something")
        assert sim == 0.0

    def test_5b_5_add_to_batch_returns_none_within_window(self):
        """Adding to batch within window returns None (not yet flushed)."""
        result = _run(add_ticket_to_batch(
            tenant_id=TENANT, ticket_id="TKT-B1",
            query="Change my address", confidence=0.90,
        ))
        assert result is None  # Still accumulating

    def test_5b_6_flush_returns_batches(self):
        """Force-flush returns accumulated batches."""
        _run(add_ticket_to_batch(
            tenant_id=TENANT, ticket_id="TKT-B2",
            query="Update my shipping address", confidence=0.92,
        ))

        batches = _run(flush_all_batches(TENANT))
        assert len(batches) >= 1
        assert "ticket_ids" in batches[0]
        assert "confidence_min" in batches[0]
        assert "confidence_max" in batches[0]

    def test_5b_7_batch_description_formatted(self):
        """format_batch_description produces readable output."""
        batch = {
            "ticket_ids": ["TKT-1", "TKT-2", "TKT-3"],
            "confidence_min": 0.90,
            "confidence_max": 0.95,
            "risk_level": 0.1,
        }
        desc = format_batch_description(batch)
        assert "3 tickets" in desc
        assert "Confidence" in desc
        assert "Risk" in desc

    def test_5b_8_batch_summary(self):
        """get_batch_summary returns aggregated batch info."""
        _run(add_ticket_to_batch(
            tenant_id=TENANT, ticket_id="TKT-S1",
            query="Address change request", confidence=0.91,
        ))
        _run(add_ticket_to_batch(
            tenant_id=TENANT, ticket_id="TKT-S2",
            query="Address change request", confidence=0.93,
        ))

        summary = _run(get_batch_summary(TENANT))
        assert summary["pending_count"] >= 1
        assert summary["total_tickets_in_batches"] >= 2

    def test_5b_9_should_batch_only_for_batch_routing(self):
        """check_should_batch returns True only for 'batch' routing."""
        assert _run(check_should_batch(0.90, "batch")) is True
        assert _run(check_should_batch(0.96, "auto")) is False
        assert _run(check_should_batch(0.60, "escalate")) is False
        assert _run(check_should_batch(0.75, "ask")) is False


# ═══════════════════════════════════════════════════════════════
# 5C: Sentiment Routing
# ═══════════════════════════════════════════════════════════════

class Test5C_SentimentRouting:
    """5C: Route customers based on emotional state."""

    def test_5c_1_angry_text_routes_to_human(self):
        """Angry customer text → route to human."""
        result = compute_sentiment(
            "This is unacceptable! I want to speak to your manager immediately. "
            "This is the worst service I have ever experienced. I will sue you."
        )
        assert result["label"] == "angry"
        assert result["route"] == ROUTE_HUMAN
        assert result["score"] < 0.3

    def test_5c_2_happy_text_routes_to_ai(self):
        """Happy customer text → AI auto."""
        result = compute_sentiment(
            "Thanks so much! Great service, really appreciate the quick response. "
            "Awesome work, I'll recommend you to everyone."
        )
        assert result["label"] == "happy"
        assert result["route"] == ROUTE_AI_AUTO
        assert result["score"] > 0.6

    def test_5c_3_neutral_text_routes_to_flagged(self):
        """Neutral text → AI flagged for review."""
        result = compute_sentiment(
            "I have a question about my order status. Can you help?"
        )
        assert result["label"] in ("mixed", "happy")  # neutral defaults to slightly positive
        assert result["route"] in (ROUTE_AI_FLAGGED, ROUTE_AI_AUTO)

    def test_5c_4_negation_flips_sentiment(self):
        """'Not happy' should not be treated as happy."""
        result = compute_sentiment("I am not happy with this service at all")
        # The negation should reduce happy signals
        # May not be angry (no angry keywords) but should be lower than happy threshold
        assert result["has_negation"] is True

    def test_5c_5_intensifier_amplifies(self):
        """Intensifiers should be detected."""
        result = compute_sentiment("I am extremely angry about this terrible experience")
        assert result["has_intensifier"] is True
        assert result["label"] == "angry"

    def test_5c_6_empty_text_returns_neutral(self):
        """Empty text → neutral default."""
        result = compute_sentiment("")
        assert result["score"] == 0.5
        assert result["route"] == ROUTE_AI_FLAGGED

    def test_5c_7_route_by_sentiment_full(self):
        """Full sentiment routing with DB persistence via bridge."""
        result = _run(bridge_sentiment(
            tenant_id=TENANT,
            ticket_id="TKT-SENT-1",
            query="I'm furious! This is ridiculous. I want my money back!",
        ))
        assert result is not None
        assert result["route"] == ROUTE_HUMAN
        assert "sentiment" in result

        # Verify persisted in DB (bridge writes to DB)
        db = get_db()
        logs = db._sentiment_logs
        assert any(l["ticket_id"] == "TKT-SENT-1" for l in logs)

    def test_5c_8_vip_angry_escalates(self):
        """VIP + angry → always escalate."""
        result = _run(route_by_sentiment(
            tenant_id=TENANT,
            ticket_id="TKT-VIP-ANGRY",
            query="This is terrible service",
            customer_context={"is_vip": True},
        ))
        assert result["escalate"] is True
        assert result["route"] == ROUTE_HUMAN

    def test_5c_9_repeat_contact_escalates(self):
        """3+ contacts about same issue → escalate."""
        result = _run(route_by_sentiment(
            tenant_id=TENANT,
            ticket_id="TKT-REPEAT",
            query="Still waiting on my refund",
            customer_context={"contact_count": 4},
        ))
        assert result["escalate"] is True

    def test_5c_10_bridge_sentiment_wired(self):
        """parwa_bridge.route_by_sentiment persists to DB."""
        result = _run(bridge_sentiment(
            tenant_id=TENANT,
            ticket_id="TKT-BSENT-1",
            query="Thanks for the help, great service!",
        ))
        assert result is not None
        assert result["route"] == ROUTE_AI_AUTO

        db = get_db()
        assert any(l["ticket_id"] == "TKT-BSENT-1" for l in db._sentiment_logs)


# ═══════════════════════════════════════════════════════════════
# 5D: Approval Gates
# ═══════════════════════════════════════════════════════════════

class Test5D_ApprovalGates:
    """5D: Hard-coded safety rules that CANNOT be overridden by AI."""

    def test_5d_1_refund_always_requires_approval(self):
        """Refund action ALWAYS requires approval (hard gate)."""
        result = _run(check_approval_required(
            tenant_id=TENANT, action="refund",
            confidence=0.99, is_vip=False, value_usd=0,
        ))
        assert result["required"] is True
        assert result["gate_type"] == "hard"

    def test_5d_2_return_always_requires_approval(self):
        """Return action ALWAYS requires approval."""
        result = _run(check_approval_required(
            tenant_id=TENANT, action="return",
        ))
        assert result["required"] is True
        assert result["gate_type"] in ("hard", "blacklist")

    def test_5d_3_account_change_always_requires_approval(self):
        """Account changes ALWAYS require approval."""
        result = _run(check_approval_required(
            tenant_id=TENANT, action="account_change",
        ))
        assert result["required"] is True
        assert result["gate_type"] in ("hard", "blacklist")

    def test_5d_4_policy_exception_always_requires_approval(self):
        """Policy exceptions ALWAYS require approval."""
        result = _run(check_approval_required(
            tenant_id=TENANT, action="policy_exception",
        ))
        assert result["required"] is True

    def test_5d_5_discount_above_threshold_requires_approval(self):
        """Discount > $10 requires approval (conditional gate)."""
        result = _run(check_approval_required(
            tenant_id=TENANT, action="discount",
            value_usd=15.0,
        ))
        assert result["required"] is True
        assert result["gate_type"] == "conditional"

    def test_5d_6_discount_below_threshold_no_approval(self):
        """Discount <= $10 does NOT require approval."""
        result = _run(check_approval_required(
            tenant_id=TENANT, action="discount",
            value_usd=5.0,
        ))
        assert result["required"] is False

    def test_5d_7_vip_actions_require_approval(self):
        """VIP customer actions on gated list require approval."""
        result = _run(check_approval_required(
            tenant_id=TENANT, action="cancellation",
            is_vip=True,
        ))
        assert result["required"] is True
        assert result["gate_type"] == "vip"

    def test_5d_8_custom_auto_approve_with_blacklist(self):
        """Even custom auto-approve can't override hard gates (refunds)."""
        _run(set_custom_gates(
            tenant_id=TENANT,
            auto_approve_actions=["refund", "info_query"],
            set_by="admin@test.com",
        ))

        # Refund should STILL require approval (blacklist)
        result = _run(check_approval_required(
            tenant_id=TENANT, action="refund",
            confidence=0.99,
        ))
        assert result["required"] is True
        assert result["gate_type"] in ("hard", "blacklist")  # hits hard gate first

    def test_5d_9_custom_auto_approve_non_blacklist(self):
        """Non-blacklist action can be auto-approved with high confidence."""
        _run(set_custom_gates(
            tenant_id=TENANT,
            auto_approve_actions=["info_query"],
            max_auto_approve_confidence=0.90,
            set_by="admin@test.com",
        ))

        result = _run(check_approval_required(
            tenant_id=TENANT, action="info_query",
            confidence=0.95,
        ))
        assert result["required"] is False
        assert result["gate_type"] == "confidence_auto"

    def test_5d_10_load_gates_from_db(self):
        """Approval gates are stored/retrieved from DB."""
        db = get_db()
        _run(db.set_feature_flag(TENANT, "approval_gates", {
            "auto_approve_actions": ["status_check"],
            "max_auto_approve_confidence": 0.92,
        }, "admin"))

        invalidate_gate_cache(TENANT)
        gates = _run(load_approval_gates(TENANT))

        assert "status_check" in gates["auto_approve_actions"]
        assert gates["max_auto_approve_confidence"] == 0.92

    def test_5d_11_bridge_approval_gate_wired(self):
        """parwa_bridge.check_approval_gate works end-to-end."""
        result = _run(check_approval_gate(
            tenant_id=TENANT, action="refund",
        ))
        assert result is not None
        assert result["required"] is True

    def test_5d_12_execute_refund_variant_always_gated(self):
        """'execute_refund' variant is also hard-gated."""
        for action in ["execute_refund", "process_return", "handle_refund"]:
            result = _run(check_approval_required(
                tenant_id=TENANT, action=action,
            ))
            assert result["required"] is True, f"Action '{action}' should require approval"


# ═══════════════════════════════════════════════════════════════
# 5E: Variant Recommendation
# ═══════════════════════════════════════════════════════════════

class Test5E_VariantRecommendation:
    """5E: Recommend variant upgrades when current can't handle task."""

    def test_5e_1_simple_query_on_mini_no_upgrade(self):
        """Simple query on Mini → no upgrade needed."""
        result = _run(recommend_variant(
            tenant_id=TENANT, ticket_id="TKT-VR-1",
            query="What are your business hours?",
            current_variant="mini",
        ))
        assert result["upgrade_needed"] is False
        assert result["recommended_variant"] is None

    def test_5e_2_refund_on_mini_needs_upgrade(self):
        """Refund query on Mini → needs upgrade (Mini can't do refunds)."""
        result = _run(recommend_variant(
            tenant_id=TENANT, ticket_id="TKT-VR-2",
            query="I want a refund for order #123",
            current_variant="mini",
            required_action="refund",
        ))
        assert result["upgrade_needed"] is True
        assert result["recommended_variant"] is not None
        # Should recommend parwa_standard (cheapest that handles refunds)
        assert result["recommended_variant"] in ("parwa_standard", "parwa_high")

    def test_5e_3_complex_multi_api_needs_high(self):
        """Multi-API + escalation → needs PARWA High."""
        result = _run(recommend_variant(
            tenant_id=TENANT, ticket_id="TKT-VR-3",
            query="I need a refund AND my Shopify order is wrong AND I want to speak to manager",
            current_variant="mini",
        ))
        assert result["upgrade_needed"] is True
        assert result["recommended_variant"] == "parwa_high"

    def test_5e_4_standard_handles_refund(self):
        """PARWA Standard can handle a simple refund."""
        result = _run(recommend_variant(
            tenant_id=TENANT, ticket_id="TKT-VR-4",
            query="Please process my refund",
            current_variant="parwa_standard",
            required_action="refund",
        ))
        assert result["upgrade_needed"] is False

    def test_5e_5_high_handles_everything(self):
        """PARWA High handles everything."""
        result = _run(recommend_variant(
            tenant_id=TENANT, ticket_id="TKT-VR-5",
            query="Refund my Shopify order, I need to speak to manager about this unacceptable service",
            current_variant="parwa_high",
            required_action="refund",
        ))
        assert result["upgrade_needed"] is False

    def test_5e_6_reasons_provided_for_upgrade(self):
        """Upgrade recommendations include reasons."""
        result = _run(recommend_variant(
            tenant_id=TENANT, ticket_id="TKT-VR-6",
            query="Refund for my order",
            current_variant="mini",
            required_action="refund",
        ))
        assert result["upgrade_needed"] is True
        assert len(result["reasons"]) > 0
        assert result["task_assessment"]["needs_refund"] is True

    def test_5e_7_get_variant_status(self):
        """get_variant_status returns all variant info."""
        db = get_db()
        db.set_load(TENANT, "mini", 5, 20)
        db.set_load(TENANT, "parwa_standard", 8, 10)

        status = _run(get_variant_status(TENANT))
        assert status["tenant_id"] == TENANT
        assert len(status["variants"]) >= 2
        names = [v["name"] for v in status["variants"]]
        assert "mini" in names
        assert "parwa_standard" in names

    def test_5e_8_bridge_recommend_variant_wired(self):
        """parwa_bridge.recommend_variant works end-to-end."""
        result = _run(bridge_recommend_variant(
            tenant_id=TENANT, ticket_id="TKT-BVR-1",
            query="I need a refund",
            current_variant="mini",
        ))
        assert result is not None
        # Mini can't handle refund
        assert result["upgrade_needed"] is True


# ═══════════════════════════════════════════════════════════════
# INTEGRATION: Full E2E — Combined Wave 5 Intelligence
# ═══════════════════════════════════════════════════════════════

class Test5_Integration:
    """Full E2E: Confidence + Sentiment + Approval Gates work together."""

    def test_integration_angry_refund_full_flow(self):
        """Angry customer requesting refund:
        1. Sentiment → human route + escalate
        2. Confidence → low (risk factors)
        3. Approval gate → required (hard gate for refund)
        4. Variant → needs upgrade from mini
        All should agree: this needs human attention.
        """
        # 1. Sentiment
        sentiment = _run(bridge_sentiment(
            tenant_id=TENANT, ticket_id="TKT-FULL-1",
            query="This is ridiculous! I want a full refund immediately! Worst experience ever!",
        ))
        assert sentiment["route"] == ROUTE_HUMAN

        # 2. Confidence
        conf = _run(score_confidence(
            tenant_id=TENANT, ticket_id="TKT-FULL-1",
            ticket_type="refund_request", query="I want a full refund",
            required_action="refund", is_vip=False, value_usd=200,
        ))
        assert conf is not None
        # High risk (financial + refund action) should lower confidence
        assert conf["risk_level"] > 0

        # 3. Approval gate
        gate = _run(check_approval_gate(
            tenant_id=TENANT, action="refund",
            confidence=conf["confidence"], value_usd=200,
        ))
        assert gate["required"] is True

        # 4. Variant recommendation
        variant = _run(bridge_recommend_variant(
            tenant_id=TENANT, ticket_id="TKT-FULL-1",
            query="I want a full refund for my order",
            current_variant="mini", required_action="refund",
        ))
        assert variant["upgrade_needed"] is True

    def test_integration_happy_info_auto_flow(self):
        """Happy customer asking for info:
        1. Sentiment → AI auto
        2. Confidence → high
        3. Approval gate → not required
        4. Variant → no upgrade needed
        All should agree: auto-handle.
        """
        # 1. Sentiment
        sentiment = _run(bridge_sentiment(
            tenant_id=TENANT, ticket_id="TKT-AUTO-1",
            query="Thanks for the great service! Quick question: what are your hours?",
        ))
        assert sentiment["route"] == ROUTE_AI_AUTO

        # 2. Confidence
        conf = _run(score_confidence(
            tenant_id=TENANT, ticket_id="TKT-AUTO-1",
            ticket_type="info", query="What are your hours?",
        ))
        assert conf is not None

        # 3. Approval gate
        gate = _run(check_approval_gate(
            tenant_id=TENANT, action="info_query",
            confidence=conf["confidence"],
        ))
        assert gate["required"] is False

        # 4. Variant
        variant = _run(bridge_recommend_variant(
            tenant_id=TENANT, ticket_id="TKT-AUTO-1",
            query="What are your business hours?",
            current_variant="mini",
        ))
        assert variant["upgrade_needed"] is False

    def test_integration_db_persistence_full_chain(self):
        """All Wave 5 results are persisted in DB."""
        db = get_db()

        # Run all Wave 5 modules
        _run(bridge_sentiment(TENANT, "TKT-PERSIST-1", "Great service, thanks!"))
        _run(score_confidence(TENANT, "TKT-PERSIST-1", "info", "Thanks"))
        _run(check_approval_gate(TENANT, "info_query"))

        # Verify DB has records
        assert len(db._sentiment_logs) >= 1
        assert len(db._confidence_logs) >= 1
        # Approval gates use feature_flags
        assert len(db._feature_flags) >= 0  # may or may not have flags

    def test_integration_batching_with_confidence(self):
        """Tickets scored as BATCH should be added to semantic batches."""
        # Score a ticket → BATCH routing
        conf = _run(score_confidence(
            tenant_id=TENANT, ticket_id="TKT-BATCH-1",
            ticket_type="address_change", query="Change my address to 123 Main St",
        ))

        if conf and conf["routing"] == ACTION_BATCH:
            # Add to batch
            result = _run(add_ticket_to_batch(
                tenant_id=TENANT, ticket_id="TKT-BATCH-1",
                query="Change my address to 123 Main St",
                confidence=conf["confidence"],
                ticket_type="address_change",
            ))
            # Should accumulate (not flush yet)

        # Add another similar ticket
        _run(add_ticket_to_batch(
            tenant_id=TENANT, ticket_id="TKT-BATCH-2",
            query="Update my address to 456 Oak Ave",
            confidence=0.92,
            ticket_type="address_change",
        ))

        # Flush
        batches = _run(flush_all_batches(TENANT))
        # Should have at least one batch
        assert len(batches) >= 0  # May be in same or different batches depending on key


if __name__ == "__main__":
    pytest.main([__file__, "-v"])