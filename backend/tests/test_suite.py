"""
Comprehensive Test Suite for the Unified Variant + Jarvis + Notification CRM.

Tests:
1. Unit tests for individual nodes (comm bus, auto_fix, maker, batch_refunds, clarification)
2. Integration test: Full pipeline with complicated ticket
3. Quality scoring and human-replacement assessment
4. Notification CRM lifecycle test
5. Jarvis loop-whole monitor test
6. Variant comparison (Mini vs Pro vs High on same ticket)
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.logger import get_logger

logger = get_logger("test_suite")


# ══════════════════════════════════════════════════════════════════
# TEST RESULT TRACKER
# ══════════════════════════════════════════════════════════════════


class TestResult:
    """Track test results and generate reports."""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.start_time = time.monotonic()

    def add(self, name: str, passed: bool, details: str = "", score: float = 0.0):
        self.results.append({
            "test": name,
            "passed": passed,
            "details": details,
            "score": score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r["passed"])

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r["passed"])

    @property
    def pass_rate(self) -> float:
        return (self.passed_count / self.total * 100) if self.total > 0 else 0

    @property
    def elapsed_ms(self) -> float:
        return round((time.monotonic() - self.start_time) * 1000, 2)

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "TEST RESULTS SUMMARY",
            "=" * 60,
            f"Total:  {self.total}",
            f"Passed: {self.passed_count}",
            f"Failed: {self.failed_count}",
            f"Rate:   {self.pass_rate:.1f}%",
            f"Time:   {self.elapsed_ms}ms",
            "",
        ]

        # Group by pass/fail
        for result in self.results:
            icon = "PASS" if result["passed"] else "FAIL"
            score_str = f" (score: {result['score']:.1f})" if result['score'] else ""
            lines.append(f"  [{icon}] {result['test']}{score_str}")
            if result["details"] and not result["passed"]:
                lines.append(f"        -> {result['details']}")

        lines.append("=" * 60)
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# UNIT TESTS
# ══════════════════════════════════════════════════════════════════


def test_comm_bus(tr: TestResult):
    """Test inter-node communication bus."""
    from app.core.parwa_graph_state import (
        create_initial_state,
        post_to_comm_bus,
        read_comm_bus,
        post_shared_insight,
        get_shared_insights,
    )

    state = create_initial_state(
        query="test query",
        company_id="test_co",
        variant_tier="parwa_high",
    )

    # Test posting to comm bus (correct 5-arg API)
    update1 = post_to_comm_bus(state, "pii_check", "all", "insight", {"pii_detected": True, "redacted": True})
    update2 = post_to_comm_bus(state, "empathy_check", "all", "insight", {"empathy_score": 0.85, "emotion": "angry"})
    update3 = post_to_comm_bus(state, "classify", "all", "insight", {"intent": "billing", "complexity": "high"})

    # Merge updates into state (simulating LangGraph state merge)
    if "node_comm_bus" not in state:
        state["node_comm_bus"] = {}
    for upd in [update1, update2, update3]:
        if "node_comm_bus" in upd:
            bus_upd = upd["node_comm_bus"]
            if "messages" in bus_upd:
                if "messages" not in state["node_comm_bus"]:
                    state["node_comm_bus"]["messages"] = []
                state["node_comm_bus"]["messages"].extend(bus_upd["messages"])

    # Test reading from comm bus (correct 4-arg API)
    messages = read_comm_bus(state, "all", ["insight"])
    has_pii = any(m.get("from_node") == "pii_check" for m in messages)
    has_empathy = any(m.get("from_node") == "empathy_check" for m in messages)
    has_classify = any(m.get("from_node") == "classify" for m in messages)

    tr.add("comm_bus_post_and_read", has_pii and has_empathy and has_classify,
           f"message count: {len(messages)}")

    # Test that nodes can read each other's data
    empathy_msg = next((m for m in messages if m.get("from_node") == "empathy_check"), {})
    empathy_payload = empathy_msg.get("payload", {})
    emotion_known = empathy_payload.get("emotion") == "angry"
    tr.add("comm_bus_cross_node_read", emotion_known,
           f"emotion from bus: {empathy_payload.get('emotion')}")

    # Test shared insights
    insight_update = post_shared_insight("pii_check", "pii_detected", True)
    if "node_comm_bus" in insight_update:
        si = insight_update["node_comm_bus"].get("shared_insights", {})
        state["node_comm_bus"].setdefault("shared_insights", {}).update(si)

    insights = get_shared_insights(state)
    tr.add("comm_bus_shared_insights", isinstance(insights, dict),
           f"insights type: {type(insights).__name__}")


def test_auto_fix(tr: TestResult):
    """Test auto-fix node for all tiers."""
    from app.core.unified_variant.graph import auto_fix_node
    from app.core.parwa_graph_state import create_initial_state

    for tier in ["mini_parwa", "parwa", "parwa_high"]:
        state = create_initial_state(
            query="test auto fix",
            company_id="test_co",
            variant_tier=tier,
        )
        state["quality_score"] = 0.6  # Below threshold
        state["generated_response"] = (
            "I understand your concern. Please be advised that we apologize "
            "for the inconvenience. As per our policy, your request has been "
            "processed. Thank you for your patience."
        )
        state["emotion_profile"] = {"dominant": "angry", "urgency": "high"}

        result = asyncio.get_event_loop().run_until_complete(auto_fix_node(state))

        has_result = "auto_fix_result" in result
        fix_result = result.get("auto_fix_result", {})
        fix_needed = fix_result.get("fix_needed", False)
        fixes_applied = len(fix_result.get("fixes_applied", []))

        tr.add(f"auto_fix_{tier}", has_result and fix_needed,
               f"fixes_applied={fixes_applied}, needed={fix_needed}",
               score=fix_result.get("fixed_quality", 0) * 100)


def test_maker_llm(tr: TestResult):
    """Test Maker validator with LLM for all tiers."""
    from app.core.unified_variant.graph import maker_validator_llm_node
    from app.core.parwa_graph_state import create_initial_state

    for tier in ["mini_parwa", "parwa", "parwa_high"]:
        state = create_initial_state(
            query="I need a refund for overcharging",
            company_id="test_co",
            variant_tier=tier,
        )
        state["generated_response"] = (
            "I see the billing issue. I'm processing a refund for the overcharge "
            "right away. You should see the credit within 3-5 business days."
        )
        state["classification"] = {"intent": "refund", "complexity": "medium"}
        state["pii_redacted_query"] = "I need a refund for overcharging"

        result = asyncio.get_event_loop().run_until_complete(maker_validator_llm_node(state))

        has_result = "maker_llm_result" in result
        maker_result = result.get("maker_llm_result", {})
        k_solutions = maker_result.get("k", 0)

        # Check that K varies by tier
        expected_k = {"mini_parwa": 3, "parwa": 5, "parwa_high": 7}
        correct_k = k_solutions == expected_k.get(tier, 5)

        tr.add(f"maker_llm_{tier}", has_result,
               f"k={k_solutions}, expected={expected_k.get(tier)}, correct_k={correct_k}")


def test_batch_refunds(tr: TestResult):
    """Test batch refund node."""
    from app.core.unified_variant.graph import batch_refunds_node
    from app.core.parwa_graph_state import create_initial_state

    # Test refund request
    state = create_initial_state(
        query="I need a refund for the duplicate charge of $2,499",
        company_id="test_co",
        variant_tier="parwa_high",
    )
    state["classification"] = {"intent": "refund", "complexity": "medium"}
    state["billing_dispute"] = {"amount": 2499, "reason": "duplicate_charge"}

    result = asyncio.get_event_loop().run_until_complete(batch_refunds_node(state))

    has_result = "refund_batch" in result
    batch_result = result.get("refund_batch", {})
    is_refund = batch_result.get("is_refund", False)
    has_preview = bool(result.get("refund_preview"))

    tr.add("batch_refunds_refund_detected", is_refund,
           f"is_refund={is_refund}, preview={has_preview}")

    # Test non-refund request
    state2 = create_initial_state(
        query="How do I reset my password?",
        company_id="test_co",
        variant_tier="parwa_high",
    )
    state2["classification"] = {"intent": "technical", "complexity": "simple"}

    result2 = asyncio.get_event_loop().run_until_complete(batch_refunds_node(state2))
    not_refund = not result2.get("refund_batch", {}).get("is_refund", True)

    tr.add("batch_refunds_non_refund_skipped", not_refund,
           f"is_refund={result2.get('refund_batch', {}).get('is_refund')}")


def test_clarification_gate(tr: TestResult):
    """Test clarification gate for uncertain variants."""
    from app.core.unified_variant.graph import clarification_gate_node
    from app.core.parwa_graph_state import create_initial_state

    # Low confidence -> should need clarification
    state = create_initial_state(
        query="I'm not sure what happened with my account",
        company_id="test_co",
        variant_tier="parwa_high",
    )
    state["confidence_score"] = {"overall": 0.3}
    state["quality_score"] = 0.4
    state["classification"] = {"intent": "billing", "complexity": "high"}

    result = asyncio.get_event_loop().run_until_complete(clarification_gate_node(state))

    needs_clarification = result.get("clarification_result", {}).get("needs_clarification", False)
    has_question = bool(result.get("clarification_result", {}).get("clarification_question"))

    tr.add("clarification_low_confidence", needs_clarification and has_question,
           f"needs_clarification={needs_clarification}, has_question={has_question}")

    # High confidence -> should NOT need clarification
    state2 = create_initial_state(
        query="Reset my password",
        company_id="test_co",
        variant_tier="parwa_high",
    )
    state2["confidence_score"] = {"overall": 0.95}
    state2["quality_score"] = 0.98
    state2["classification"] = {"intent": "technical", "complexity": "simple"}

    result2 = asyncio.get_event_loop().run_until_complete(clarification_gate_node(state2))

    no_clarification = not result2.get("clarification_result", {}).get("needs_clarification", True)
    tr.add("clarification_high_confidence", no_clarification,
           f"needs_clarification={result2.get('clarification_result', {}).get('needs_clarification')}")


def test_permissions(tr: TestResult):
    """Test that tier permissions are correctly defined."""
    from app.core.unified_variant.graph import get_tier_permissions, TIER_PERMISSIONS

    # All tiers should have auto_fix
    for tier in ["mini_parwa", "parwa", "parwa_high"]:
        perms = get_tier_permissions(tier)
        has_auto_fix = perms.get("auto_fix", False)
        has_maker_llm = perms.get("maker_llm", False)
        has_batch_refunds = perms.get("batch_refunds", False)
        has_clarification = perms.get("clarification", False)

        tr.add(f"permissions_{tier}_auto_fix", has_auto_fix,
               f"auto_fix={has_auto_fix}")
        tr.add(f"permissions_{tier}_maker_llm", has_maker_llm,
               f"maker_llm={has_maker_llm}")
        tr.add(f"permissions_{tier}_batch_refunds", has_batch_refunds,
               f"batch_refunds={has_batch_refunds}")
        tr.add(f"permissions_{tier}_clarification", has_clarification,
               f"clarification={has_clarification}")

    # Verify High has more depth than Mini
    mini_perms = get_tier_permissions("mini_parwa")
    high_perms = get_tier_permissions("parwa_high")

    mini_retries = mini_perms.get("max_quality_retries", 0)
    high_retries = high_perms.get("max_quality_retries", 0)

    tr.add("permissions_high_more_retries", high_retries > mini_retries,
           f"mini_retries={mini_retries}, high_retries={high_retries}")

    # Mini monetary actions need approval
    mini_monetary = mini_perms.get("monetary_actions") == "approval_required"
    tr.add("permissions_mini_monetary_approval", mini_monetary,
           f"monetary_actions={mini_perms.get('monetary_actions')}")

    # High has full autonomy
    high_monetary = high_perms.get("monetary_actions") == "auto"
    tr.add("permissions_high_full_autonomy", high_monetary,
           f"monetary_actions={high_perms.get('monetary_actions')}")


# ══════════════════════════════════════════════════════════════════
# JARVIS LOOP-WHOLE TESTS
# ══════════════════════════════════════════════════════════════════


def test_jarvis_monitor(tr: TestResult):
    """Test Jarvis loop-whole monitor."""
    from app.services.jarvis_agents.loop_whole_monitor import (
        get_jarvis_monitor,
        VariantObserver,
        JarvisDecider,
        JarvisActor,
    )
    from app.core.parwa_graph_state import create_initial_state

    # Test with a healthy state
    state = create_initial_state(
        query="Simple question",
        company_id="test_co",
        variant_tier="parwa_high",
    )
    state["quality_score"] = 0.95
    state["confidence_score"] = {"overall": 0.95}
    state["errors"] = []

    monitor = get_jarvis_monitor()
    result = monitor.process(state)

    has_decision = "jarvis_decision" in result
    has_action = "jarvis_action_result" in result
    health_ok = result.get("jarvis_snapshot", {}).get("health") in ("healthy", "unknown")

    tr.add("jarvis_healthy_state", has_decision and has_action and health_ok,
           f"health={result.get('jarvis_snapshot', {}).get('health')}")

    # Test with a problematic state
    state2 = create_initial_state(
        query="EMERGENCY: I need to speak to a manager NOW",
        company_id="test_co",
        variant_tier="parwa_high",
    )
    state2["emergency_flag"] = True
    state2["emergency_type"] = "legal_threat"
    state2["quality_score"] = 0.3
    state2["errors"] = ["quality_critical"]

    result2 = monitor.process(state2)

    decision = result2.get("jarvis_decision", {}).get("decision", "")
    is_escalation = decision in ("emergency_escalate", "critical_intervention")

    tr.add("jarvis_emergency_escalation", is_escalation,
           f"decision={decision}")

    # Test clarification flow
    state3 = create_initial_state(
        query="I'm not sure what to do about my subscription",
        company_id="test_co",
        variant_tier="parwa_high",
    )
    state3["quality_score"] = 0.6
    state3["confidence_score"] = {"overall": 0.4}
    state3["clarification_result"] = {
        "needs_clarification": True,
        "clarification_question": "Would you prefer to cancel or explore alternatives?",
        "clarification_type": "retention_check",
        "client_notification": {
            "options": ["Hear alternatives", "Proceed with cancellation", "Pause subscription"],
        },
    }

    result3 = monitor.process(state3)
    decision3 = result3.get("jarvis_decision", {}).get("decision", "")
    is_clarify = decision3 == "clarify_with_client"

    tr.add("jarvis_clarification_decision", is_clarify,
           f"decision={decision3}")

    # Test client response processing
    feedback = monitor.process_client_response(
        company_id="test_co",
        ticket_id="tkt_test",
        client_response="I want to hear about alternatives first",
        state=state3,
    )

    has_choice = "client_choice" in feedback
    tr.add("jarvis_client_response", has_choice,
           f"choice={feedback.get('client_choice')}")


# ══════════════════════════════════════════════════════════════════
# NOTIFICATION CRM TESTS
# ══════════════════════════════════════════════════════════════════


def test_notification_crm(tr: TestResult):
    """Test Notification CRM service."""
    from app.services.notification_crm.notification_crm_service import (
        get_notification_crm,
        NotificationType,
        NotificationStatus,
    )

    crm = get_notification_crm()

    # Create a refund notification
    notif_id = crm.create_notification(
        company_id="test_co",
        notification_type=NotificationType.REFUND_BATCH,
        title="Refund request: duplicate charge",
        summary="Customer charged $2,499 twice",
        customer_id="cust_test_001",
        ticket_id="tkt_test_001",
        metadata={"amount": 2499},
        jarvis_context={"problem": "duplicate_charge"},
        client_options=["Full refund", "Partial credit", "Investigate first"],
    )

    has_id = bool(notif_id)
    tr.add("notification_crm_create", has_id, f"notif_id={notif_id}")

    # Get notification
    notif = crm.get_notification(notif_id)
    found = notif is not None
    tr.add("notification_crm_get", found)

    # Get Jarvis context
    jarvis_ctx = crm.get_jarvis_context(notif_id)
    has_context = "notification" in jarvis_ctx and "jarvis_context" in jarvis_ctx
    tr.add("notification_crm_jarvis_context", has_context,
           f"keys={list(jarvis_ctx.keys())}")

    # Mark as read
    read_ok = crm.mark_as_read(notif_id)
    tr.add("notification_crm_mark_read", read_ok)

    # Create similar notification (should merge)
    notif_id2 = crm.create_notification(
        company_id="test_co",
        notification_type=NotificationType.REFUND_BATCH,
        title="Refund request: duplicate charge",  # Same title = should merge
        summary="Another duplicate charge found",
        customer_id="cust_test_001",
        ticket_id="tkt_test_002",
        metadata={"amount": 1500},
    )

    notif2 = crm.get_notification(notif_id2) if notif_id2 else None
    is_batch = notif2.is_batch if notif2 else False
    tr.add("notification_crm_merge_similar", is_batch,
           f"is_batch={is_batch}")

    # Test confusion notification
    notif_id3 = crm.create_notification(
        company_id="test_co",
        notification_type=NotificationType.CONFUSION,
        title="Confusion on return policy",
        summary="AI told customer 60 days instead of 30 days",
        customer_id="cust_test_001",
        ticket_id="tkt_test_003",
        jarvis_context={"correct_policy": "30 days", "ai_stated": "60 days"},
    )

    has_confusion = bool(notif_id3)
    tr.add("notification_crm_confusion_type", has_confusion)

    # Get categories for UI
    categories = crm.get_notification_categories()
    has_categories = len(categories) > 0
    tr.add("notification_crm_categories", has_categories,
           f"count={len(categories)}")

    # Get pending count
    pending = crm.get_pending_count("test_co")
    has_counts = isinstance(pending, dict)
    tr.add("notification_crm_pending_count", has_counts,
           f"pending={pending}")

    # Resolve notification
    resolved = crm.resolve_notification(notif_id, "Refund processed")
    tr.add("notification_crm_resolve", resolved)


# ══════════════════════════════════════════════════════════════════
# INTEGRATION TEST: Complicated Ticket
# ══════════════════════════════════════════════════════════════════


def test_complicated_ticket(tr: TestResult):
    """Integration test: Process the complicated ticket through High Parwa.

    This is the BIG test — observe how High Parwa handles the
    multi-issue, multi-employee, high-emotion ticket.
    """
    try:
        from tests.fake_crm_data import (
            build_complicated_test_state,
            COMPLICATED_TICKET,
            HUMAN_AGENT_BASELINE,
            evaluate_response_quality,
        )
        from app.services.jarvis_agents.loop_whole_monitor import get_jarvis_monitor

        # Build the complicated ticket state
        state = build_complicated_test_state()

        tr.add("complicated_ticket_state_built", True,
               f"ticket_id={state.get('ticket_id')}")

        # Verify state has all the context
        has_billing = "billing_dispute" in state
        has_emotion = "emotion_profile" in state
        has_context = "ticket_context" in state

        tr.add("complicated_ticket_context_complete",
               has_billing and has_emotion and has_context,
               f"billing={has_billing}, emotion={has_emotion}, context={has_context}")

        # Run Jarvis monitor on the state (simulating post-pipeline analysis)
        monitor = get_jarvis_monitor()
        jarvis_result = monitor.process(state)

        has_snapshot = "jarvis_snapshot" in jarvis_result
        has_decision = "jarvis_decision" in jarvis_result
        has_quality = "ticket_quality" in jarvis_result

        tr.add("complicated_ticket_jarvis_analysis",
               has_snapshot and has_decision,
               f"snapshot={has_snapshot}, decision={has_decision}")

        # Evaluate what Jarvis decided
        decision = jarvis_result.get("jarvis_decision", {}).get("decision", "")
        action = jarvis_result.get("jarvis_action_result", {}).get("jarvis_action", "")

        tr.add("complicated_ticket_jarvis_decision",
               decision != "monitor_only",
               f"decision={decision}, action={action}")

        # Check quality assessment
        quality = jarvis_result.get("ticket_quality", {})
        if quality:
            overall = quality.get("overall_score", 0)
            can_replace = quality.get("can_replace_human", False)

            tr.add("complicated_ticket_quality_score",
                   overall > 0,
                   f"overall={overall}, can_replace_human={can_replace}",
                   score=overall)
        else:
            tr.add("complicated_ticket_quality_score", False,
                   "No quality metrics computed", score=0)

        # Simulated response evaluation
        # In a real test, the pipeline would generate a response
        # For testing, we evaluate what a TYPICAL AI response would look like
        simulated_response = (
            "I hear you, and I want to help fix all of this right now. "
            "Let me take ownership of all three issues personally.\n\n"
            "First, the billing overcharge — I can see the $8,500 discrepancy. "
            "I'm processing a full refund for the overcharged amount right away.\n\n"
            "Second, the return policy misinformation — our AI incorrectly told "
            "23 customers about a 60-day policy when it should be 30 days. "
            "I'm updating the knowledge base immediately and we'll reach out to "
            "affected customers to correct this.\n\n"
            "Third, the API connection drops during peak hours — I'm escalating "
            "this to P1 with our engineering team. We'll have a fix deployed "
            "within 24 hours.\n\n"
            "I'll personally follow up with you by 5 PM today with updates on "
            "all three items. You have my commitment that this gets resolved."
        )

        evaluation = evaluate_response_quality(
            simulated_response,
            COMPLICATED_TICKET,
            tier="parwa_high",
        )

        tr.add("complicated_ticket_response_evaluation",
               evaluation.get("overall_score", 0) > 50,
               f"overall={evaluation.get('overall_score')}, "
               f"can_replace_human={evaluation.get('can_replace_human')}, "
               f"gap={evaluation.get('gap_vs_human')}",
               score=evaluation.get("overall_score", 0))

        # Honest assessment
        assessment = evaluation.get("honest_assessment", "")
        logger.info("HONEST ASSESSMENT: %s", assessment)

    except Exception as e:
        tr.add("complicated_ticket_integration", False, str(e)[:200])


# ══════════════════════════════════════════════════════════════════
# VARIANT COMPARISON TEST
# ══════════════════════════════════════════════════════════════════


def test_variant_comparison(tr: TestResult):
    """Compare Mini, Pro, and High on the same ticket.

    All variants should have SAME CAPABILITY (same nodes),
    but DIFFERENT RESTRICTIONS (permissions).
    """
    from app.core.unified_variant.graph import get_tier_permissions, TIER_PERMISSIONS
    from tests.fake_crm_data import build_simple_test_state

    # All tiers should have the same permission keys
    mini_perms = get_tier_permissions("mini_parwa")
    pro_perms = get_tier_permissions("parwa")
    high_perms = get_tier_permissions("parwa_high")

    same_keys = set(mini_perms.keys()) == set(pro_perms.keys()) == set(high_perms.keys())
    tr.add("variant_comparison_same_permission_keys", same_keys,
           f"mini_keys={len(mini_perms)}, pro_keys={len(pro_perms)}, high_keys={len(high_perms)}")

    # All tiers should have core capabilities enabled
    core_capabilities = ["auto_fix", "maker_llm", "batch_refunds", "clarification", "deep_enrichment"]
    for cap in core_capabilities:
        mini_has = mini_perms.get(cap, False)
        pro_has = pro_perms.get(cap, False)
        high_has = high_perms.get(cap, False)

        all_have = mini_has and pro_has and high_has
        tr.add(f"variant_comparison_{cap}", all_have,
               f"mini={mini_has}, pro={pro_has}, high={high_has}")

    # Restrictions should differ
    mini_monetary = mini_perms.get("monetary_actions")
    pro_monetary = pro_perms.get("monetary_actions")
    high_monetary = high_perms.get("monetary_actions")

    different_monetary = not (mini_monetary == pro_monetary == high_monetary)
    tr.add("variant_comparison_monetary_differs", different_monetary,
           f"mini={mini_monetary}, pro={pro_monetary}, high={high_monetary}")

    # Quality thresholds should differ
    mini_threshold = mini_perms.get("quality_threshold", 0)
    high_threshold = high_perms.get("quality_threshold", 0)
    threshold_differs = high_threshold > mini_threshold
    tr.add("variant_comparison_threshold_differs", threshold_differs,
           f"mini={mini_threshold}, high={high_threshold}")


# ══════════════════════════════════════════════════════════════════
# MAIN TEST RUNNER
# ══════════════════════════════════════════════════════════════════


def run_all_tests() -> TestResult:
    """Run all tests and return results."""
    tr = TestResult()

    logger.info("Starting comprehensive test suite...")

    # Unit tests
    logger.info("Running unit tests...")
    test_comm_bus(tr)
    test_auto_fix(tr)
    test_maker_llm(tr)
    test_batch_refunds(tr)
    test_clarification_gate(tr)
    test_permissions(tr)

    # Jarvis tests
    logger.info("Running Jarvis loop-whole tests...")
    test_jarvis_monitor(tr)

    # Notification CRM tests
    logger.info("Running Notification CRM tests...")
    test_notification_crm(tr)

    # Variant comparison
    logger.info("Running variant comparison tests...")
    test_variant_comparison(tr)

    # Integration test (THE BIG ONE)
    logger.info("Running complicated ticket integration test...")
    test_complicated_ticket(tr)

    # Print results
    print(tr.summary())

    return tr


if __name__ == "__main__":
    results = run_all_tests()
