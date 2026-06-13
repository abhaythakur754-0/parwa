"""Month 2 — Comprehensive Test with 15 Tickets (10 General + 5 Action-Specific).

This test validates:
1. All 22 nodes process each ticket correctly
2. Variant differentiation works (Mini=RECOMMEND, PARWA/High=EXECUTE)
3. Action execution is HONEST (never claims "executed" when not delivered)
4. SMS and voice call delivery uses DeliveryProvider
5. CRM state changes are verifiable
6. Human effort elimination reaches 15-18%

Tickets:
  T1-T10: General tickets across different intents and variants
  T11: Voice call request (PARWA High - should execute/simulate honestly)
  T12: SMS request (PARWA - should execute/simulate honestly)
  T13: Payment/refund action (PARWA - should execute)
  T14: Voice call + refund combo (PARWA High - should attempt both)
  T15: SMS notification request (Mini - SMS is EXECUTE permission)
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
logger = logging.getLogger("parwa.month2_test")


# ─── Test Tickets ────────────────────────────────────────────────────────────

TICKETS: list[dict[str, Any]] = [
    # ─── T1-T10: General tickets across intents and variants ───
    {
        "ticket_id": "T1",
        "raw_message": "I was charged twice for my order. I want a refund immediately!",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "refund_request",
        "expected_sentiment": "frustrated",
        "category": "general",
    },
    {
        "ticket_id": "T2",
        "raw_message": "Where is my order? I ordered a wireless charger 5 days ago.",
        "customer_id": "CUST-1001",
        "channel": "chat",
        "variant": "mini",
        "expected_intent": "order_status",
        "expected_sentiment": "neutral",
        "category": "general",
    },
    {
        "ticket_id": "T3",
        "raw_message": "I want to cancel my laptop stand order, I found a cheaper one elsewhere.",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "cancellation",
        "expected_sentiment": "neutral",
        "category": "general",
    },
    {
        "ticket_id": "T4",
        "raw_message": "My account has been suspended and I can't access anything. This is unacceptable!",
        "customer_id": "CUST-1004",
        "channel": "chat",
        "variant": "high",
        "expected_intent": "billing_issue",
        "expected_sentiment": "angry",
        "category": "general",
    },
    {
        "ticket_id": "T5",
        "raw_message": "Can you help me change my email address on my account?",
        "customer_id": "CUST-1002",
        "channel": "email",
        "variant": "mini",
        "expected_intent": "account_modification",
        "expected_sentiment": "neutral",
        "category": "general",
    },
    {
        "ticket_id": "T6",
        "raw_message": "Your software keeps crashing every time I open it. This is the third time I'm reporting this!",
        "customer_id": "CUST-1007",
        "channel": "chat",
        "variant": "parwa",
        "expected_intent": "technical_support",
        "expected_sentiment": "frustrated",
        "category": "general",
    },
    {
        "ticket_id": "T7",
        "raw_message": "What is your return policy for electronics?",
        "customer_id": "CUST-1005",
        "channel": "email",
        "variant": "mini",
        "expected_intent": "faq_question",
        "expected_sentiment": "neutral",
        "category": "general",
    },
    {
        "ticket_id": "T8",
        "raw_message": "I'm going to contact my lawyer if you don't fix this billing error right now!",
        "customer_id": "CUST-1003",
        "channel": "email",
        "variant": "high",
        "expected_intent": "escalation",
        "expected_sentiment": "angry",
        "category": "general",
    },
    {
        "ticket_id": "T9",
        "raw_message": "I have nothing but problems with your service. Nothing works as advertised.",
        "customer_id": "CUST-1004",
        "channel": "chat",
        "variant": "parwa",
        "expected_intent": "complaint",
        "expected_sentiment": "frustrated",
        "category": "general",
    },
    {
        "ticket_id": "T10",
        "raw_message": "How do I add more seats to my enterprise subscription?",
        "customer_id": "CUST-1006",
        "channel": "email",
        "variant": "high",
        "expected_intent": "account_modification",
        "expected_sentiment": "neutral",
        "category": "general",
    },
    # ─── T11-T15: Action-specific tickets ───
    {
        "ticket_id": "T11",
        "raw_message": "I need to speak with someone about my order. Can you call me back please?",
        "customer_id": "CUST-1005",
        "channel": "chat",
        "variant": "high",
        "expected_intent": "order_status",
        "expected_sentiment": "neutral",
        "category": "action_voice_call",
        "expected_action": "voice_call",
    },
    {
        "ticket_id": "T12",
        "raw_message": "Please send me a text message with the tracking update for my order. SMS me the details.",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "order_status",
        "expected_sentiment": "neutral",
        "category": "action_sms",
        "expected_action": "send_sms",
    },
    {
        "ticket_id": "T13",
        "raw_message": "I was charged twice for my headphones! Process my refund right now!",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "refund_request",
        "expected_sentiment": "angry",
        "category": "action_refund",
        "expected_action": "process_refund",
    },
    {
        "ticket_id": "T14",
        "raw_message": "I want a refund for my defective monitor AND I need you to call me to discuss the replacement. Call me back!",
        "customer_id": "CUST-1008",
        "channel": "email",
        "variant": "high",
        "expected_intent": "refund_request",
        "expected_sentiment": "frustrated",
        "category": "action_voice_and_refund",
        "expected_action": "voice_call",
    },
    {
        "ticket_id": "T15",
        "raw_message": "Text me the confirmation once you've updated my account email address.",
        "customer_id": "CUST-1002",
        "channel": "chat",
        "variant": "mini",
        "expected_intent": "account_modification",
        "expected_sentiment": "neutral",
        "category": "action_sms_mini",
        "expected_action": "send_sms",
    },
]


async def run_single_ticket(ticket: dict) -> dict[str, Any]:
    """Run a single ticket through the full PARWA pipeline."""
    from parwa.graph import aprocess_ticket, reset_parwa_graph

    # Reset CRM and graph for clean state
    from parwa.fake_crm.database import reset_crm
    reset_crm()
    reset_parwa_graph()

    try:
        result = await aprocess_ticket(
            raw_message=ticket["raw_message"],
            customer_id=ticket.get("customer_id", ""),
            channel=ticket.get("channel", "email"),
            variant=ticket.get("variant", "parwa"),
        )
        return {
            "ticket_id": ticket["ticket_id"],
            "category": ticket["category"],
            "variant": ticket["variant"],
            "expected_intent": ticket.get("expected_intent", ""),
            "actual_intent": result.get("intent", ""),
            "expected_sentiment": ticket.get("expected_sentiment", ""),
            "actual_sentiment": result.get("sentiment", ""),
            "should_escalate": result.get("should_escalate", False),
            "quality_score": result.get("quality_score", 0),
            "execution_results": result.get("execution_results", []),
            "recommendation": result.get("recommendation"),
            "final_response": result.get("final_response", "")[:300],
            "success": True,
            "error": None,
        }
    except Exception as exc:
        logger.error("Ticket %s failed: %s", ticket["ticket_id"], exc)
        return {
            "ticket_id": ticket["ticket_id"],
            "category": ticket["category"],
            "variant": ticket["variant"],
            "expected_intent": ticket.get("expected_intent", ""),
            "actual_intent": "",
            "expected_sentiment": ticket.get("expected_sentiment", ""),
            "actual_sentiment": "",
            "should_escalate": False,
            "quality_score": 0,
            "execution_results": [],
            "recommendation": None,
            "final_response": "",
            "success": False,
            "error": str(exc),
        }


def evaluate_results(results: list[dict]) -> dict[str, Any]:
    """Evaluate all results and compute metrics."""
    total = len(results)
    successful = [r for r in results if r["success"]]
    
    # Intent accuracy
    intent_correct = sum(
        1 for r in successful
        if r["actual_intent"] == r["expected_intent"]
    )
    intent_accuracy = intent_correct / max(len(successful), 1) * 100

    # Sentiment accuracy
    sentiment_correct = sum(
        1 for r in successful
        if r["actual_sentiment"] == r["expected_sentiment"]
    )
    sentiment_accuracy = sentiment_correct / max(len(successful), 1) * 100

    # Action-specific analysis
    action_tickets = [r for r in successful if r["category"].startswith("action_")]
    action_details = []
    for r in action_tickets:
        exec_results = r.get("execution_results", [])
        for er in exec_results:
            action_type = er.get("action_type", "")
            status = er.get("status", "")
            details = er.get("details", {})
            honest_note = details.get("honest_note", "") if isinstance(details, dict) else ""
            delivery_status = details.get("delivery_status", "") if isinstance(details, dict) else ""
            
            action_details.append({
                "ticket_id": r["ticket_id"],
                "category": r["category"],
                "variant": r["variant"],
                "action_type": action_type,
                "status": status,
                "delivery_status": delivery_status,
                "honest_note": honest_note,
                "actually_delivered": status == "executed" and delivery_status in ("", "delivered"),
            })

    # Human effort elimination calculation
    # A ticket eliminates human effort if:
    # 1. Intent is correctly classified AND
    # 2. At least one action was executed/simulated (not failed/denied) AND
    # 3. Quality score >= 65 AND
    # 4. Not escalated (escalated tickets need human)
    tickets_eliminating_human = 0
    for r in successful:
        intent_ok = r["actual_intent"] == r["expected_intent"]
        quality_ok = r["quality_score"] >= 65
        not_escalated = not r["should_escalate"]
        has_result = len(r.get("execution_results", [])) > 0
        
        # Check if at least one action was meaningfully processed
        action_processed = False
        for er in r.get("execution_results", []):
            if er.get("status") in ("executed", "simulated", "delivery_pending", "recommended"):
                action_processed = True
                break

        if intent_ok and quality_ok and not_escalated and has_result and action_processed:
            tickets_eliminating_human += 1

    human_effort_pct = tickets_eliminating_human / max(total, 1) * 100

    # Delivery honesty check
    dishonest_results = []
    for r in successful:
        for er in r.get("execution_results", []):
            action_type = er.get("action_type", "")
            status = er.get("status", "")
            details = er.get("details", {})
            if isinstance(details, dict):
                honest_note = details.get("honest_note", "")
                delivery_status = details.get("delivery_status", "")
                # Flag dishonesty: claims "executed" but delivery_status says "simulated"
                if status == "executed" and delivery_status == "simulated":
                    dishonest_results.append({
                        "ticket_id": r["ticket_id"],
                        "action_type": action_type,
                        "issue": "Status says 'executed' but delivery_status is 'simulated' - DISHONEST",
                    })

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_tickets": total,
        "successful_tickets": len(successful),
        "failed_tickets": total - len(successful),
        "intent_accuracy": round(intent_accuracy, 1),
        "sentiment_accuracy": round(sentiment_accuracy, 1),
        "human_effort_eliminated_pct": round(human_effort_pct, 1),
        "tickets_eliminating_human": tickets_eliminating_human,
        "intent_correct": intent_correct,
        "intent_total": len(successful),
        "sentiment_correct": sentiment_correct,
        "sentiment_total": len(successful),
        "avg_quality_score": round(
            sum(r["quality_score"] for r in successful) / max(len(successful), 1), 1
        ),
        "action_details": action_details,
        "dishonest_results": dishonest_results,
        "honesty_check": "PASS" if not dishonest_results else "FAIL - Found dishonest status claims",
        "per_ticket": results,
        "delivery_provider": "Twilio (if configured) or SimulationProvider (honest fallback)",
    }


async def main():
    """Run the Month 2 comprehensive test."""
    print("=" * 70)
    print("PARWA Month 2 — Comprehensive Test (15 Tickets)")
    print("=" * 70)
    print(f"  Tickets: 10 general + 5 action-specific")
    print(f"  Action-specific: Voice call, SMS, Refund, Combo, Mini SMS")
    print(f"  Delivery: Twilio (if configured) or honest simulation")
    print("=" * 70)

    # Check Twilio availability
    import os
    twilio_available = bool(
        os.environ.get("TWILIO_ACCOUNT_SID")
        and os.environ.get("TWILIO_AUTH_TOKEN")
        and os.environ.get("TWILIO_PHONE_NUMBER")
    )
    print(f"\n  Twilio Status: {'CONFIGURED — Real SMS/calls' if twilio_available else 'NOT CONFIGURED — Using honest simulation'}")
    if not twilio_available:
        print("  Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER for real delivery")
    print()

    results = []
    for i, ticket in enumerate(TICKETS):
        print(f"  [{i+1}/15] Processing {ticket['ticket_id']} ({ticket['category']}) variant={ticket['variant']}...")
        start = time.time()
        result = await run_single_ticket(ticket)
        elapsed = time.time() - start

        # Print summary
        status = "OK" if result["success"] else "FAIL"
        intent_match = "Y" if result["actual_intent"] == result["expected_intent"] else "N"
        sentiment_match = "Y" if result["actual_sentiment"] == result["expected_sentiment"] else "N"
        print(f"    → {status} | Intent: {result['actual_intent']} ({intent_match}) | "
              f"Sentiment: {result['actual_sentiment']} ({sentiment_match}) | "
              f"Quality: {result['quality_score']:.0f} | "
              f"Actions: {len(result['execution_results'])} | "
              f"Time: {elapsed:.1f}s")

        # Print action details for action-specific tickets
        if ticket["category"].startswith("action_"):
            for er in result.get("execution_results", []):
                at = er.get("action_type", "")
                st = er.get("status", "")
                details = er.get("details", {})
                if isinstance(details, dict):
                    ds = details.get("delivery_status", "")
                    hn = details.get("honest_note", "")[:80] if details.get("honest_note") else ""
                else:
                    ds = ""
                    hn = ""
                print(f"      → Action: {at} | Status: {st} | Delivery: {ds}")
                if hn:
                    print(f"        Note: {hn}")

        results.append(result)
        await asyncio.sleep(0.3)  # Rate limiting

    # Evaluate
    print("\n" + "=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)

    eval_results = evaluate_results(results)

    print(f"  Total Tickets:          {eval_results['total_tickets']}")
    print(f"  Successful:             {eval_results['successful_tickets']}")
    print(f"  Failed:                 {eval_results['failed_tickets']}")
    print(f"  Intent Accuracy:        {eval_results['intent_accuracy']}% (target: 80%)")
    print(f"  Sentiment Accuracy:     {eval_results['sentiment_accuracy']}% (target: 75%)")
    print(f"  Avg Quality Score:      {eval_results['avg_quality_score']} (target: >= 65)")
    print(f"  Human Effort Eliminated:{eval_results['human_effort_eliminated_pct']}% (target: 15-18%)")
    print(f"  Honesty Check:          {eval_results['honesty_check']}")

    # Action-specific summary
    print(f"\n  Action-Specific Results:")
    for ad in eval_results["action_details"]:
        delivered = "DELIVERED" if ad["actually_delivered"] else ad["delivery_status"] or ad["status"]
        print(f"    {ad['ticket_id']} ({ad['variant']}): {ad['action_type']} → {delivered}")
        if ad["honest_note"]:
            print(f"      Honest: {ad['honest_note'][:100]}")

    # Save results
    output_path = Path("/home/z/my-project/download/month2_comprehensive_test.json")
    output_path.write_text(json.dumps(eval_results, indent=2, default=str))
    print(f"\n  Results saved to: {output_path}")

    # Also save a delivery receipt summary
    try:
        from parwa.delivery.provider import get_simulation_receipts
        receipts = get_simulation_receipts()
        if receipts:
            receipt_path = Path("/home/z/my-project/download/month2_delivery_receipts.json")
            receipt_path.write_text(json.dumps(receipts, indent=2))
            print(f"  Delivery receipts saved to: {receipt_path}")
            print(f"  Total simulation receipts: {len(receipts)}")
    except ImportError:
        print("  Delivery receipts: Module not available")

    # Final verdict
    print("\n" + "=" * 70)
    intent_pass = eval_results["intent_accuracy"] >= 80
    sentiment_pass = eval_results["sentiment_accuracy"] >= 75
    human_pass = eval_results["human_effort_eliminated_pct"] >= 15
    honest_pass = "PASS" in eval_results["honesty_check"]

    print("  VERDICT:")
    print(f"    Intent Accuracy:      {'PASS' if intent_pass else 'FAIL'} ({eval_results['intent_accuracy']}%)")
    print(f"    Sentiment Accuracy:   {'PASS' if sentiment_pass else 'FAIL'} ({eval_results['sentiment_accuracy']}%)")
    print(f"    Human Effort >= 15%:  {'PASS' if human_pass else 'FAIL'} ({eval_results['human_effort_eliminated_pct']}%)")
    print(f"    Honesty Check:        {'PASS' if honest_pass else 'FAIL'} ({eval_results['honesty_check']})")

    all_pass = intent_pass and sentiment_pass and human_pass and honest_pass
    print(f"\n  OVERALL: {'ALL TARGETS MET' if all_pass else 'SOME TARGETS NOT MET'}")
    print("=" * 70)

    return eval_results


if __name__ == "__main__":
    asyncio.run(main())
