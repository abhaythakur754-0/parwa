"""Month 3 — Comprehensive Test with 30 Tickets Across All 3 Variants.

This test validates Month 3 deliverables:
1. CRM Ticket Lifecycle (auto-polling + status updates + approval queue)
2. Response Formatter V2 (context-aware, persona-based, real CRM data)
3. Metrics Dashboard (honest human effort eliminated %)
4. 50% human effort elimination target

Tickets are distributed across all 3 variants:
  - 10 Mini PARWA tickets (limited actions → recommendations)
  - 10 PARWA tickets (full execute on most actions)
  - 10 PARWA High tickets (full execute + voice + bulk)

Each variant gets a mix of:
  - Simple intents (FAQ, order status) → should auto-resolve
  - Medium intents (refund, cancellation) → execute or recommend based on variant
  - Complex intents (billing, technical) → needs reasoning
  - Action-specific (voice call, SMS) → delivery test
  - Escalation (legal threat) → should escalate

Human effort elimination calculation:
  FULLY_AUTO: intent correct + quality >= 80 + action executed + not escalated + no recommendation
  PARTIAL_AUTO: recommendation created, quality loop-back, or simulated delivery
  HUMAN_REQUIRED: escalated or quality < 60
  Target: 50% FULLY_AUTO across all 30 tickets
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")
logger = logging.getLogger("parwa.month3_test")


# ═══════════════════════════════════════════════════════════════════════════════
# 30 Test Tickets — 10 per variant, mix of intents
# ═══════════════════════════════════════════════════════════════════════════════

TICKETS: list[dict[str, Any]] = [
    # ─── MINI PARWA (10 tickets) ───────────────────────────────────────────
    {
        "ticket_id": "M3-MINI-01",
        "raw_message": "What is your return policy for electronics?",
        "customer_id": "CUST-1005",
        "channel": "email",
        "variant": "mini",
        "expected_intent": "faq_question",
        "expected_auto_resolve": True,  # FAQ = simple, all variants can share
    },
    {
        "ticket_id": "M3-MINI-02",
        "raw_message": "Where is my order? I ordered a mechanical keyboard 3 days ago.",
        "customer_id": "CUST-1005",
        "channel": "chat",
        "variant": "mini",
        "expected_intent": "order_status",
        "expected_auto_resolve": True,  # Order status = share policy, all variants can
    },
    {
        "ticket_id": "M3-MINI-03",
        "raw_message": "I was charged twice for my headphones! I want a refund now!",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "mini",
        "expected_intent": "refund_request",
        "expected_auto_resolve": False,  # Mini can only RECOMMEND refunds
    },
    {
        "ticket_id": "M3-MINI-04",
        "raw_message": "I want to cancel my laptop stand order.",
        "customer_id": "CUST-1001",
        "channel": "chat",
        "variant": "mini",
        "expected_intent": "cancellation",
        "expected_auto_resolve": False,  # Mini can only RECOMMEND cancellations
    },
    {
        "ticket_id": "M3-MINI-05",
        "raw_message": "Can you help me update my email address on my account?",
        "customer_id": "CUST-1002",
        "channel": "email",
        "variant": "mini",
        "expected_intent": "account_modification",
        "expected_auto_resolve": False,  # Mini can only RECOMMEND account mods
    },
    {
        "ticket_id": "M3-MINI-06",
        "raw_message": "How do subscriptions work? Can I upgrade my plan?",
        "customer_id": "CUST-1008",
        "channel": "chat",
        "variant": "mini",
        "expected_intent": "faq_question",
        "expected_auto_resolve": True,  # FAQ = simple
    },
    {
        "ticket_id": "M3-MINI-07",
        "raw_message": "My account is suspended and I can't access anything. Please help!",
        "customer_id": "CUST-1004",
        "channel": "chat",
        "variant": "mini",
        "expected_intent": "billing_issue",
        "expected_auto_resolve": False,  # Complex billing + account mod needed
    },
    {
        "ticket_id": "M3-MINI-08",
        "raw_message": "What does the warranty cover for my headphones?",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "mini",
        "expected_intent": "faq_question",
        "expected_auto_resolve": True,  # FAQ = simple
    },
    {
        "ticket_id": "M3-MINI-09",
        "raw_message": "I need help with my subscription renewal date.",
        "customer_id": "CUST-1003",
        "channel": "email",
        "variant": "mini",
        "expected_intent": "general_inquiry",
        "expected_auto_resolve": True,  # Simple inquiry
    },
    {
        "ticket_id": "M3-MINI-10",
        "raw_message": "Can you tell me about your shipping options?",
        "customer_id": "CUST-1002",
        "channel": "chat",
        "variant": "mini",
        "expected_intent": "faq_question",
        "expected_auto_resolve": True,  # FAQ = simple
    },

    # ─── PARWA (10 tickets) ────────────────────────────────────────────────
    {
        "ticket_id": "M3-PARWA-01",
        "raw_message": "I was charged twice for my order. Process my refund immediately!",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "refund_request",
        "expected_auto_resolve": True,  # PARWA can EXECUTE refunds
    },
    {
        "ticket_id": "M3-PARWA-02",
        "raw_message": "I want to cancel my laptop stand order, I found a cheaper one.",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "cancellation",
        "expected_auto_resolve": True,  # PARWA can EXECUTE cancellations
    },
    {
        "ticket_id": "M3-PARWA-03",
        "raw_message": "Please update my email address to marcus.johnson@newmail.com",
        "customer_id": "CUST-1002",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "account_modification",
        "expected_auto_resolve": True,  # PARWA can EXECUTE account mods
    },
    {
        "ticket_id": "M3-PARWA-04",
        "raw_message": "Where is my wireless charger? I ordered it 5 days ago.",
        "customer_id": "CUST-1001",
        "channel": "chat",
        "variant": "parwa",
        "expected_intent": "order_status",
        "expected_auto_resolve": True,  # Simple order status
    },
    {
        "ticket_id": "M3-PARWA-05",
        "raw_message": "Please send me a text message with the tracking update for my order. SMS me the details.",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "order_status",
        "expected_auto_resolve": True,  # SMS is EXECUTE on all variants
    },
    {
        "ticket_id": "M3-PARWA-06",
        "raw_message": "Your software keeps crashing every time I open it. This is the third time!",
        "customer_id": "CUST-1007",
        "channel": "chat",
        "variant": "parwa",
        "expected_intent": "technical_support",
        "expected_auto_resolve": True,  # Can send reply + create note
    },
    {
        "ticket_id": "M3-PARWA-07",
        "raw_message": "What is your cancellation policy?",
        "customer_id": "CUST-1005",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "faq_question",
        "expected_auto_resolve": True,  # FAQ = simple
    },
    {
        "ticket_id": "M3-PARWA-08",
        "raw_message": "I have nothing but problems with your service. Nothing works!",
        "customer_id": "CUST-1004",
        "channel": "chat",
        "variant": "parwa",
        "expected_intent": "complaint",
        "expected_auto_resolve": True,  # Can send reply + create note
    },
    {
        "ticket_id": "M3-PARWA-09",
        "raw_message": "How do I add more seats to my enterprise subscription?",
        "customer_id": "CUST-1006",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "account_modification",
        "expected_auto_resolve": True,  # PARWA can EXECUTE account mods
    },
    {
        "ticket_id": "M3-PARWA-10",
        "raw_message": "I'm going to contact my lawyer if you don't fix this billing error!",
        "customer_id": "CUST-1003",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "escalation",
        "expected_auto_resolve": False,  # Legal threat = always escalate
    },

    # ─── PARWA HIGH (10 tickets) ───────────────────────────────────────────
    {
        "ticket_id": "M3-HIGH-01",
        "raw_message": "I was charged twice for my headphones! Process my refund right now!",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "high",
        "expected_intent": "refund_request",
        "expected_auto_resolve": True,  # High can EXECUTE everything
    },
    {
        "ticket_id": "M3-HIGH-02",
        "raw_message": "I need to speak with someone about my order. Can you call me back please?",
        "customer_id": "CUST-1005",
        "channel": "chat",
        "variant": "high",
        "expected_intent": "order_status",
        "expected_auto_resolve": True,  # High has voice calls included
    },
    {
        "ticket_id": "M3-HIGH-03",
        "raw_message": "Cancel my laptop stand order immediately.",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "high",
        "expected_intent": "cancellation",
        "expected_auto_resolve": True,  # High can EXECUTE cancellations
    },
    {
        "ticket_id": "M3-HIGH-04",
        "raw_message": "My account is suspended and I can't access anything! This is unacceptable!",
        "customer_id": "CUST-1004",
        "channel": "chat",
        "variant": "high",
        "expected_intent": "billing_issue",
        "expected_auto_resolve": True,  # High can EXECUTE account mods to reactivate
    },
    {
        "ticket_id": "M3-HIGH-05",
        "raw_message": "I want a refund for my defective monitor AND I need you to call me to discuss replacement. Call me back!",
        "customer_id": "CUST-1008",
        "channel": "email",
        "variant": "high",
        "expected_intent": "refund_request",
        "expected_auto_resolve": True,  # High can do refund + voice call
    },
    {
        "ticket_id": "M3-HIGH-06",
        "raw_message": "I need bulk access to the analytics for my enterprise account.",
        "customer_id": "CUST-1006",
        "channel": "email",
        "variant": "high",
        "expected_intent": "general_inquiry",
        "expected_auto_resolve": True,  # High has bulk + analytics access
    },
    {
        "ticket_id": "M3-HIGH-07",
        "raw_message": "How do I set up a custom integration with your API?",
        "customer_id": "CUST-1003",
        "channel": "email",
        "variant": "high",
        "expected_intent": "general_inquiry",
        "expected_auto_resolve": True,  # High has custom integration access
    },
    {
        "ticket_id": "M3-HIGH-08",
        "raw_message": "Your plugin keeps crashing on launch. I have two open tickets about this already!",
        "customer_id": "CUST-1007",
        "channel": "chat",
        "variant": "high",
        "expected_intent": "technical_support",
        "expected_auto_resolve": True,  # Can reply + create note
    },
    {
        "ticket_id": "M3-HIGH-09",
        "raw_message": "I want to modify my enterprise account to add 50 more seats.",
        "customer_id": "CUST-1003",
        "channel": "email",
        "variant": "high",
        "expected_intent": "account_modification",
        "expected_auto_resolve": True,  # High can EXECUTE account mods
    },
    {
        "ticket_id": "M3-HIGH-10",
        "raw_message": "I'm going to sue your company for fraud! Get me a supervisor NOW!",
        "customer_id": "CUST-1004",
        "channel": "email",
        "variant": "high",
        "expected_intent": "escalation",
        "expected_auto_resolve": False,  # Legal threat = always escalate
    },
]


async def run_single_ticket(ticket: dict) -> dict[str, Any]:
    """Run a single ticket through the full PARWA pipeline with lifecycle management."""
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm
    from parwa.ticket_lifecycle import TicketLifecycleManager, TicketStatus

    # Reset CRM and graph for clean state
    reset_crm()
    reset_parwa_graph()

    ticket_id = ticket["ticket_id"]
    start_time = time.time()

    try:
        # Process through the pipeline
        result = await aprocess_ticket(
            raw_message=ticket["raw_message"],
            customer_id=ticket.get("customer_id", ""),
            channel=ticket.get("channel", "email"),
            variant=ticket.get("variant", "parwa"),
        )
        processing_time = time.time() - start_time

        # Determine lifecycle status using autonomous decision logic
        should_escalate = result.get("should_escalate", False)
        execution_results = result.get("execution_results", [])
        recommendation = result.get("recommendation")
        quality_score = result.get("quality_score", 0.0)
        variant = ticket.get("variant", "parwa")

        # Classify human effort
        from parwa.metrics_dashboard import HumanEffortCalculator
        classification = HumanEffortCalculator.classify({
            "intent_confidence": result.get("intent_confidence", 0.0),
            "quality_score": quality_score,
            "should_escalate": should_escalate,
            "escalation_reason": result.get("escalation_reason", ""),
            "recommendation": recommendation,
            "should_loop_back": result.get("should_loop_back", False),
            "execution_results": execution_results,
        })

        # Determine lifecycle status
        if should_escalate:
            lifecycle_status = "escalated"
        elif recommendation and recommendation.get("pending_approval"):
            lifecycle_status = "pending_approval"
        elif all(r.get("status") == "executed" for r in execution_results) if execution_results else False:
            lifecycle_status = "auto_resolved"
        elif any(r.get("status") == "executed" for r in execution_results):
            lifecycle_status = "auto_resolved" if quality_score >= 70 else "partial"
        else:
            lifecycle_status = "needs_review"

        # Check response quality (V2 formatter should include real data)
        final_response = result.get("final_response", "")
        has_customer_name = False
        has_specific_data = False
        try:
            from parwa.fake_crm.database import get_crm
            crm = get_crm()
            cust = crm.get_customer(ticket.get("customer_id", ""))
            if cust:
                first_name = cust.get("name", "").split()[0]
                has_customer_name = first_name.lower() in final_response.lower()
                # Check for order IDs, amounts, etc
                import re
                has_specific_data = bool(re.search(r'(ORD-|TKT-|\$[\d,.]+|PAY-|TRK-)', final_response))
        except Exception:
            pass

        return {
            "ticket_id": ticket_id,
            "variant": ticket.get("variant", "parwa"),
            "expected_intent": ticket.get("expected_intent", ""),
            "actual_intent": result.get("intent", ""),
            "expected_auto_resolve": ticket.get("expected_auto_resolve", False),
            "should_escalate": should_escalate,
            "quality_score": quality_score,
            "classification": classification.value,
            "lifecycle_status": lifecycle_status,
            "execution_results": execution_results,
            "recommendation": recommendation,
            "final_response": final_response[:500],
            "has_customer_name": has_customer_name,
            "has_specific_data": has_specific_data,
            "processing_time_seconds": round(processing_time, 2),
            "success": True,
            "error": None,
        }
    except Exception as exc:
        logger.error("Ticket %s failed: %s", ticket_id, exc, exc_info=True)
        processing_time = time.time() - start_time
        return {
            "ticket_id": ticket_id,
            "variant": ticket.get("variant", "parwa"),
            "expected_intent": ticket.get("expected_intent", ""),
            "actual_intent": "",
            "expected_auto_resolve": ticket.get("expected_auto_resolve", False),
            "should_escalate": False,
            "quality_score": 0,
            "classification": "human_required",
            "lifecycle_status": "failed",
            "execution_results": [],
            "recommendation": None,
            "final_response": "",
            "has_customer_name": False,
            "has_specific_data": False,
            "processing_time_seconds": round(processing_time, 2),
            "success": False,
            "error": str(exc),
        }


def evaluate_results(results: list[dict]) -> dict[str, Any]:
    """Evaluate all results and compute Month 3 metrics."""
    from parwa.metrics_dashboard import HumanEffortCalculator

    total = len(results)
    successful = [r for r in results if r["success"]]

    # ─── Human effort classification ────────────────────────────────────
    fully_auto = sum(1 for r in successful if r["classification"] == "fully_auto")
    partial_auto = sum(1 for r in successful if r["classification"] == "partial_auto")
    human_required = sum(1 for r in successful if r["classification"] == "human_required")

    pcts = HumanEffortCalculator.calculate_honest_percentage(
        fully_auto, partial_auto, human_required,
    )

    # ─── Per-variant breakdown ──────────────────────────────────────────
    variant_results = {}
    for variant in ["mini", "parwa", "high"]:
        variant_tickets = [r for r in successful if r["variant"] == variant]
        v_total = len(variant_tickets)
        v_fully = sum(1 for r in variant_tickets if r["classification"] == "fully_auto")
        v_partial = sum(1 for r in variant_tickets if r["classification"] == "partial_auto")
        v_human = sum(1 for r in variant_tickets if r["classification"] == "human_required")
        v_pcts = HumanEffortCalculator.calculate_honest_percentage(v_fully, v_partial, v_human)

        # Expected vs actual auto-resolve
        expected_auto = sum(1 for r in variant_tickets if r["expected_auto_resolve"])
        actual_auto = v_fully

        variant_results[variant] = {
            "total": v_total,
            "fully_auto": v_fully,
            "partial_auto": v_partial,
            "human_required": v_human,
            "human_effort_eliminated_pct": v_pcts["human_effort_eliminated_pct"],
            "expected_auto_resolve_count": expected_auto,
            "actual_auto_resolve_count": actual_auto,
            "avg_quality_score": round(
                sum(r["quality_score"] for r in variant_tickets) / max(v_total, 1), 1
            ),
        }

    # ─── Intent accuracy ────────────────────────────────────────────────
    intent_correct = sum(
        1 for r in successful
        if r["actual_intent"] == r["expected_intent"]
    )
    intent_accuracy = intent_correct / max(len(successful), 1) * 100

    # ─── Quality metrics ────────────────────────────────────────────────
    avg_quality = round(
        sum(r["quality_score"] for r in successful) / max(len(successful), 1), 1
    )

    # ─── Response quality (V2 formatter) ────────────────────────────────
    responses_with_name = sum(1 for r in successful if r.get("has_customer_name"))
    responses_with_data = sum(1 for r in successful if r.get("has_specific_data"))

    # ─── Action execution stats ─────────────────────────────────────────
    action_stats = {"executed": 0, "recommended": 0, "denied": 0, "simulated": 0, "failed": 0}
    delivery_stats = {"actually_delivered": 0, "simulated": 0, "delivery_pending": 0, "delivery_failed": 0}

    for r in successful:
        for er in r.get("execution_results", []):
            status = er.get("status", "unknown")
            if status in action_stats:
                action_stats[status] += 1

            details = er.get("details", {})
            if isinstance(details, dict):
                ds = details.get("delivery_status", "")
                if ds == "delivered":
                    delivery_stats["actually_delivered"] += 1
                elif ds == "simulated":
                    delivery_stats["simulated"] += 1
                elif ds in ("delivery_pending",):
                    delivery_stats["delivery_pending"] += 1
                elif "failed" in ds:
                    delivery_stats["delivery_failed"] += 1

    # ─── Honesty check ──────────────────────────────────────────────────
    dishonest_results = []
    for r in successful:
        for er in r.get("execution_results", []):
            status = er.get("status", "")
            details = er.get("details", {})
            if isinstance(details, dict):
                ds = details.get("delivery_status", "")
                if status == "executed" and ds == "simulated":
                    dishonest_results.append({
                        "ticket_id": r["ticket_id"],
                        "action_type": er.get("action_type"),
                        "issue": "Status says 'executed' but delivery_status is 'simulated'",
                    })

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "month": 3,
        "total_tickets": total,
        "successful_tickets": len(successful),
        "failed_tickets": total - len(successful),
        "classification": {
            "fully_auto": fully_auto,
            "partial_auto": partial_auto,
            "human_required": human_required,
        },
        "human_effort_eliminated_pct": pcts["human_effort_eliminated_pct"],
        "partial_automation_pct": pcts["partial_automation_pct"],
        "human_required_pct": pcts["human_required_pct"],
        "target_pct": 50.0,
        "target_met": pcts["human_effort_eliminated_pct"] >= 50.0,
        "intent_accuracy": round(intent_accuracy, 1),
        "avg_quality_score": avg_quality,
        "per_variant": variant_results,
        "action_stats": action_stats,
        "delivery_stats": delivery_stats,
        "response_quality": {
            "responses_with_customer_name": responses_with_name,
            "responses_with_specific_data": responses_with_data,
            "pct_with_name": round(responses_with_name / max(len(successful), 1) * 100, 1),
            "pct_with_data": round(responses_with_data / max(len(successful), 1) * 100, 1),
        },
        "honesty_check": "PASS" if not dishonest_results else f"FAIL - {len(dishonest_results)} dishonest claims",
        "dishonest_results": dishonest_results,
        "per_ticket": results,
    }


async def main():
    """Run the Month 3 comprehensive test."""
    print("=" * 80)
    print("PARWA Month 3 — Comprehensive Test (30 Tickets, 3 Variants)")
    print("=" * 80)
    print(f"  Tickets: 10 Mini PARWA + 10 PARWA + 10 PARWA High")
    print(f"  Target: 50% human effort elimination")
    print(f"  New: CRM Lifecycle + V2 Response Formatter + Metrics Dashboard")
    print("=" * 80)

    # Check Twilio availability
    import os
    twilio_available = bool(
        os.environ.get("TWILIO_ACCOUNT_SID")
        and os.environ.get("TWILIO_AUTH_TOKEN")
        and os.environ.get("TWILIO_PHONE_NUMBER")
    )
    print(f"\n  Twilio Status: {'CONFIGURED' if twilio_available else 'NOT CONFIGURED — Using honest simulation'}")

    # Initialize metrics dashboard
    from parwa.metrics_dashboard import get_metrics_collector, reset_singletons
    reset_singletons()
    metrics_collector = get_metrics_collector()

    results = []
    for i, ticket in enumerate(TICKETS):
        variant = ticket["variant"]
        ticket_id = ticket["ticket_id"]
        expected_auto = "AUTO" if ticket.get("expected_auto_resolve") else "HUMAN"
        print(f"  [{i+1}/30] {ticket_id} ({variant}) expecting={expected_auto}...")

        start = time.time()
        result = await run_single_ticket(ticket)
        elapsed = time.time() - start

        # Record in metrics dashboard
        metrics_collector.record_ticket_result(
            ticket_id=ticket_id,
            variant=variant,
            intent=result.get("actual_intent", ""),
            result_dict={
                "intent_confidence": 0.8 if result.get("actual_intent") == result.get("expected_intent") else 0.4,
                "intent_correct": result.get("actual_intent") == result.get("expected_intent"),
                "quality_score": result.get("quality_score", 0),
                "should_escalate": result.get("should_escalate", False),
                "escalation_reason": "",
                "recommendation": result.get("recommendation"),
                "should_loop_back": False,
                "execution_results": result.get("execution_results", []),
                "processing_time_seconds": elapsed,
            },
        )

        # Print summary
        status = "OK" if result["success"] else "FAIL"
        cls = result.get("classification", "?")
        quality = result.get("quality_score", 0)
        lifecycle = result.get("lifecycle_status", "?")
        name = "N" if result.get("has_customer_name") else "-"
        data = "D" if result.get("has_specific_data") else "-"
        print(f"    → {status} | Class: {cls} | Life: {lifecycle} | "
              f"Quality: {quality:.0f} | V2: {name}{data} | Time: {elapsed:.1f}s")

        # Print action details
        for er in result.get("execution_results", []):
            at = er.get("action_type", "")
            st = er.get("status", "")
            print(f"      → {at}: {st}")

        results.append(result)
        await asyncio.sleep(0.2)  # Rate limiting

    # ─── Evaluate ─────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("MONTH 3 EVALUATION RESULTS")
    print("=" * 80)

    eval_results = evaluate_results(results)

    print(f"\n  Total Tickets:              {eval_results['total_tickets']}")
    print(f"  Successful:                 {eval_results['successful_tickets']}")
    print(f"  Failed:                     {eval_results['failed_tickets']}")
    print(f"\n  ─── Human Effort Elimination ───")
    print(f"  FULLY_AUTO:                 {eval_results['classification']['fully_auto']}")
    print(f"  PARTIAL_AUTO:               {eval_results['classification']['partial_auto']}")
    print(f"  HUMAN_REQUIRED:             {eval_results['classification']['human_required']}")
    print(f"  Human Effort Eliminated:    {eval_results['human_effort_eliminated_pct']}% (TARGET: 50%)")
    print(f"  Partial Automation:         {eval_results['partial_automation_pct']}%")
    print(f"  Human Required:             {eval_results['human_required_pct']}%")

    print(f"\n  ─── Per Variant ───")
    for variant, data in eval_results["per_variant"].items():
        print(f"  {variant.upper()}:")
        print(f"    Total: {data['total']} | Fully Auto: {data['fully_auto']} | "
              f"Partial: {data['partial_auto']} | Human: {data['human_required']}")
        print(f"    Eliminated: {data['human_effort_eliminated_pct']}% | "
              f"Avg Quality: {data['avg_quality_score']}")

    print(f"\n  ─── Quality ───")
    print(f"  Intent Accuracy:            {eval_results['intent_accuracy']}%")
    print(f"  Avg Quality Score:          {eval_results['avg_quality_score']}")
    print(f"  Honesty Check:              {eval_results['honesty_check']}")

    print(f"\n  ─── Response V2 Quality ───")
    rq = eval_results["response_quality"]
    print(f"  Responses with customer name: {rq['responses_with_customer_name']}/{eval_results['successful_tickets']} ({rq['pct_with_name']}%)")
    print(f"  Responses with specific data: {rq['responses_with_specific_data']}/{eval_results['successful_tickets']} ({rq['pct_with_data']}%)")

    print(f"\n  ─── Action Stats ───")
    for action_type, count in eval_results["action_stats"].items():
        if count > 0:
            print(f"    {action_type}: {count}")

    print(f"\n  ─── Delivery Stats ───")
    for delivery_type, count in eval_results["delivery_stats"].items():
        if count > 0:
            print(f"    {delivery_type}: {count}")

    # ─── Dashboard API test ──────────────────────────────────────────────
    print(f"\n  ─── Dashboard API ───")
    from parwa.metrics_dashboard import get_dashboard_api
    dashboard = get_dashboard_api()
    summary = dashboard.get_summary()
    print(f"  Summary available: {bool(summary)}")
    print(f"  Total tracked: {summary.get('total_tickets_processed', 0)}")
    print(f"  Auto resolved: {summary.get('auto_resolved_count', 0)}")
    print(f"  Eliminated %: {summary.get('human_effort_eliminated_pct', 0)}%")
    trend = dashboard.get_trend(7)
    print(f"  Trend data: {len(trend)} days")

    # ─── Approval Queue test ─────────────────────────────────────────────
    print(f"\n  ─── Approval Queue ───")
    from parwa.ticket_lifecycle import TicketLifecycleManager
    mgr = TicketLifecycleManager()
    pending = mgr.approval_queue.get_pending()
    approval_stats = mgr.approval_queue.get_stats()
    print(f"  Pending approvals: {len(pending)}")
    print(f"  Approval stats: {approval_stats}")

    # Try auto-approve
    auto_approved = mgr.approval_queue.auto_approve_low_risk()
    print(f"  Auto-approved (low risk): {len(auto_approved)}")

    # ─── CRM Ticket Lifecycle test ───────────────────────────────────────
    print(f"\n  ─── CRM Ticket Lifecycle ───")
    open_tickets = mgr.processor.poll_crm_tickets()
    print(f"  Open tickets in CRM: {len(open_tickets)}")
    for t in open_tickets:
        print(f"    {t['ticket_id']}: {t['subject']} ({t['customer_tier']})")

    # Save results
    output_path = Path("/home/z/my-project/download/month3_comprehensive_test.json")
    output_path.write_text(json.dumps(eval_results, indent=2, default=str))
    print(f"\n  Results saved to: {output_path}")

    # Also save dashboard metrics
    dashboard_json = metrics_collector.export_json()
    dashboard_path = Path("/home/z/my-project/download/month3_dashboard_metrics.json")
    dashboard_path.write_text(dashboard_json)
    print(f"  Dashboard metrics saved to: {dashboard_path}")

    # ─── Final verdict ───────────────────────────────────────────────────
    print("\n" + "=" * 80)
    human_elim_pct = eval_results["human_effort_eliminated_pct"]
    target_met = eval_results["target_met"]
    intent_pass = eval_results["intent_accuracy"] >= 80
    quality_pass = eval_results["avg_quality_score"] >= 65
    honest_pass = "PASS" in eval_results["honesty_check"]
    v2_pass = rq["pct_with_name"] > 30 or rq["pct_with_data"] > 30  # V2 should be generating better responses

    print("  VERDICT:")
    print(f"    Human Effort >= 50%:  {'PASS' if target_met else 'FAIL'} ({human_elim_pct}%)")
    print(f"    Intent Accuracy >= 80%: {'PASS' if intent_pass else 'FAIL'} ({eval_results['intent_accuracy']}%)")
    print(f"    Avg Quality >= 65:    {'PASS' if quality_pass else 'FAIL'} ({eval_results['avg_quality_score']})")
    print(f"    Honesty Check:        {'PASS' if honest_pass else 'FAIL'}")
    print(f"    V2 Response Quality:  {'PASS' if v2_pass else 'PARTIAL'} (name: {rq['pct_with_name']}%, data: {rq['pct_with_data']}%)")

    all_pass = target_met and intent_pass and quality_pass and honest_pass
    print(f"\n  OVERALL: {'ALL TARGETS MET' if all_pass else 'SOME TARGETS NOT MET — see details above'}")
    print("=" * 80)

    return eval_results


if __name__ == "__main__":
    asyncio.run(main())
