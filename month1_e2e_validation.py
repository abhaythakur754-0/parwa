"""Month 1 End-to-End Validation — Fake Tickets Across All 3 Variants.

This script runs realistic customer service tickets through the full PARWA
pipeline and measures:
1. Intent classification accuracy
2. Sentiment analysis accuracy  
3. Escalation decision accuracy
4. Action execution (variant-aware)
5. Human effort elimination percentage

Month 1 targets:
- Intent accuracy: ≥65% (was ~17%)
- Sentiment accuracy: ≥60% (was ~33%)
- Escalation accuracy: ≥70% (was ~50%)
- Human effort elimination: ≥15%
"""

import asyncio
import json
import sys
import time
from datetime import datetime

# Add project to path
sys.path.insert(0, "/home/z/my-project/parwa")

from parwa.graph import aprocess_ticket, reset_parwa_graph
from parwa.fake_crm.database import reset_crm


# ─── Test Ticket Dataset with Ground Truth ──────────────────────────────────────

TEST_TICKETS = [
    # Format: (message, customer_id, channel, variant, expected_intent, expected_sentiment, expected_escalation, description)
    
    # ── REFUND REQUESTS ──
    {
        "message": "I was charged twice for my Premium Headphones order. $189.99 on June 1st and again on June 1st. Please refund the duplicate charge.",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "refund_request",
        "expected_sentiment": ["frustrated", "neutral"],
        "expected_escalation": False,
        "description": "Duplicate charge refund (PARWA variant)",
    },
    {
        "message": "I want my money back for the Smart Watch. It's not what I expected and I want a refund immediately.",
        "customer_id": "CUST-1002",
        "channel": "chat",
        "variant": "mini",
        "expected_intent": "refund_request",
        "expected_sentiment": ["frustrated", "angry"],
        "expected_escalation": False,
        "description": "Refund demand (Mini variant — should recommend, not execute)",
    },
    {
        "message": "I need a refund for the Portable Monitor I purchased. It has dead pixels and I'm very disappointed with the quality.",
        "customer_id": "CUST-1008",
        "channel": "email",
        "variant": "high",
        "expected_intent": "refund_request",
        "expected_sentiment": ["frustrated", "angry"],
        "expected_escalation": False,
        "description": "Defective product refund (High variant — should execute)",
    },
    
    # ── ORDER STATUS ──
    {
        "message": "Where is my order? I ordered a Mechanical Keyboard and Mouse Pad on June 10th and haven't received tracking info.",
        "customer_id": "CUST-1005",
        "channel": "chat",
        "variant": "parwa",
        "expected_intent": "order_status",
        "expected_sentiment": ["neutral", "frustrated"],
        "expected_escalation": False,
        "description": "Order status inquiry",
    },
    {
        "message": "Can you check the status of my Laptop Stand order? It's been a few days.",
        "customer_id": "CUST-1001",
        "channel": "email",
        "variant": "mini",
        "expected_intent": "order_status",
        "expected_sentiment": ["neutral"],
        "expected_escalation": False,
        "description": "Simple order check (Mini variant)",
    },
    
    # ── CANCELLATION ──
    {
        "message": "Please cancel my Laptop Stand order. I changed my mind and don't want it anymore.",
        "customer_id": "CUST-1001",
        "channel": "chat",
        "variant": "parwa",
        "expected_intent": "cancellation",
        "expected_sentiment": ["neutral"],
        "expected_escalation": False,
        "description": "Order cancellation request (PARWA — should execute)",
    },
    
    # ── BILLING ISSUES ──
    {
        "message": "My card was declined and now my account is suspended. I've been a loyal customer for years and this is unacceptable. Please fix this immediately!",
        "customer_id": "CUST-1004",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "billing_issue",
        "expected_sentiment": ["frustrated", "angry"],
        "expected_escalation": False,
        "description": "Billing + account suspension (urgent)",
    },
    
    # ── TECHNICAL SUPPORT ──
    {
        "message": "The plugin pack keeps crashing every time I try to open it. I've tried reinstalling but it still doesn't work. I'm on macOS Sonoma.",
        "customer_id": "CUST-1007",
        "channel": "chat",
        "variant": "parwa",
        "expected_intent": "technical_support",
        "expected_sentiment": ["frustrated", "neutral"],
        "expected_escalation": False,
        "description": "Technical issue with software",
    },
    
    # ── FAQ QUESTIONS ──
    {
        "message": "What is your refund policy? I'm thinking about returning something.",
        "customer_id": "CUST-1002",
        "channel": "email",
        "variant": "mini",
        "expected_intent": "faq_question",
        "expected_sentiment": ["neutral"],
        "expected_escalation": False,
        "description": "FAQ question about refund policy",
    },
    
    # ── ESCALATION CASES ──
    {
        "message": "I'm going to contact my attorney about this! Your company committed fraud on my account and I will sue if this isn't resolved immediately.",
        "customer_id": "CUST-1003",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "complaint",
        "expected_sentiment": ["angry"],
        "expected_escalation": True,
        "description": "Legal threat — MUST escalate",
    },
    {
        "message": "I've emailed three times and nobody has responded. This is my fourth attempt. I demand to speak to a manager right now about my suspended account!",
        "customer_id": "CUST-1004",
        "channel": "email",
        "variant": "high",
        "expected_intent": "escalation",
        "expected_sentiment": ["angry"],
        "expected_escalation": True,
        "description": "Manager demand + repeated contact — MUST escalate",
    },
    
    # ── ACCOUNT MODIFICATION ──
    {
        "message": "I need to update my email address from the old one to aisha.patel@newcorp.co.in. Also, can we add 10 more seats to our enterprise plan?",
        "customer_id": "CUST-1003",
        "channel": "email",
        "variant": "high",
        "expected_intent": "account_modification",
        "expected_sentiment": ["neutral"],
        "expected_escalation": False,
        "description": "Account modification (High — should execute)",
    },
    
    # ── COMPLAINT ──
    {
        "message": "Your shipping is incredibly slow. I've been waiting 2 weeks for my order and the tracking hasn't updated. This is the worst service I've ever experienced.",
        "customer_id": "CUST-1005",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "complaint",
        "expected_sentiment": ["angry", "frustrated"],
        "expected_escalation": False,
        "description": "Shipping complaint (angry but not legal threat)",
    },
    
    # ── GENERAL INQUIRY ──
    {
        "message": "Hi, I was wondering what enterprise support options are available for our company? We have about 200 employees.",
        "customer_id": "CUST-1006",
        "channel": "email",
        "variant": "parwa",
        "expected_intent": "general_inquiry",
        "expected_sentiment": ["happy", "neutral"],
        "expected_escalation": False,
        "description": "General enterprise inquiry",
    },
    
    # ── COMPLEX MULTI-ISSUE ──
    {
        "message": "My account is suspended AND I was charged for a subscription I can't even use. This is ridiculous! I need my account reactivated AND a refund for the months I couldn't access.",
        "customer_id": "CUST-1004",
        "channel": "chat",
        "variant": "parwa",
        "expected_intent": "billing_issue",
        "expected_sentiment": ["angry", "frustrated"],
        "expected_escalation": False,
        "description": "Multi-issue: billing + account access",
    },
]


async def run_ticket(ticket: dict) -> dict:
    """Run a single ticket through the pipeline and evaluate results."""
    reset_parwa_graph()
    reset_crm()
    
    start = time.time()
    result = await aprocess_ticket(
        raw_message=ticket["message"],
        customer_id=ticket["customer_id"],
        channel=ticket["channel"],
        variant=ticket["variant"],
    )
    elapsed = time.time() - start
    
    # Evaluate accuracy
    actual_intent = result.get("intent", "unknown")
    actual_sentiment = result.get("sentiment", "unknown")
    actual_escalation = result.get("should_escalate", False)
    quality_score = result.get("quality_score", 0)
    final_response = result.get("final_response", "")
    
    intent_match = actual_intent == ticket["expected_intent"]
    sentiment_match = actual_sentiment in ticket["expected_sentiment"]
    escalation_match = actual_escalation == ticket["expected_escalation"]
    
    # Check variant-specific action behavior
    execution_results = result.get("execution_results", [])
    has_executed_actions = any(r.get("status") == "executed" for r in execution_results)
    has_recommended_actions = any(r.get("status") == "recommended" for r in execution_results)
    has_denied_actions = any(r.get("status") == "denied" for r in execution_results)
    
    # Determine if this ticket would need a human agent
    # A human is needed if: escalation, no meaningful response, or critical failure
    needs_human = actual_escalation or quality_score < 50 or not final_response
    
    # A human would also be needed if Mini PARWA can only recommend (not execute)
    # But that's by design — a human reviews recommendations (partial automation)
    partially_automated = has_recommended_actions and not has_executed_actions
    
    return {
        "description": ticket["description"],
        "variant": ticket["variant"],
        "intent_match": intent_match,
        "actual_intent": actual_intent,
        "expected_intent": ticket["expected_intent"],
        "sentiment_match": sentiment_match,
        "actual_sentiment": actual_sentiment,
        "expected_sentiment": ticket["expected_sentiment"],
        "escalation_match": escalation_match,
        "actual_escalation": actual_escalation,
        "expected_escalation": ticket["expected_escalation"],
        "quality_score": quality_score,
        "needs_human": needs_human,
        "partially_automated": partially_automated,
        "has_executed_actions": has_executed_actions,
        "has_recommended_actions": has_recommended_actions,
        "has_denied_actions": has_denied_actions,
        "final_response_length": len(final_response) if final_response else 0,
        "elapsed_seconds": round(elapsed, 2),
        "pipeline_errors": result.get("pipeline_errors", []),
    }


async def main():
    """Run all test tickets and generate validation report."""
    print("=" * 80)
    print("  PARWA Month 1 — End-to-End Validation with Fake Tickets")
    print("=" * 80)
    print(f"\n  Running {len(TEST_TICKETS)} test tickets across 3 variants...")
    print(f"  Started: {datetime.now().isoformat()}\n")
    
    results = []
    for i, ticket in enumerate(TEST_TICKETS):
        print(f"  [{i+1}/{len(TEST_TICKETS)}] {ticket['description'][:60]}...", end=" ", flush=True)
        result = await run_ticket(ticket)
        results.append(result)
        
        # Quick status
        intent_icon = "✓" if result["intent_match"] else "✗"
        sent_icon = "✓" if result["sentiment_match"] else "✗"
        esc_icon = "✓" if result["escalation_match"] else "✗"
        print(f"Intent:{intent_icon} Sent:{sent_icon} Esc:{esc_icon} Q:{result['quality_score']:.0f}")
    
    # ── Compute Metrics ──────────────────────────────────────────────────
    total = len(results)
    
    intent_correct = sum(1 for r in results if r["intent_match"])
    intent_accuracy = (intent_correct / total) * 100
    
    sentiment_correct = sum(1 for r in results if r["sentiment_match"])
    sentiment_accuracy = (sentiment_correct / total) * 100
    
    escalation_correct = sum(1 for r in results if r["escalation_match"])
    escalation_accuracy = (escalation_correct / total) * 100
    
    avg_quality = sum(r["quality_score"] for r in results) / total
    
    needs_human_count = sum(1 for r in results if r["needs_human"])
    partially_automated_count = sum(1 for r in results if r["partially_automated"])
    fully_automated_count = sum(1 for r in results if not r["needs_human"] and not r["partially_automated"])
    
    # Human effort elimination calculation:
    # - Fully automated = 100% of human work eliminated for that ticket
    # - Partially automated (Mini recommends) = 50% eliminated (human reviews but doesn't investigate)
    # - Needs human = 0% eliminated (though the system may have gathered useful info)
    tickets_saving_100 = fully_automated_count
    tickets_saving_50 = partially_automated_count
    tickets_saving_0 = needs_human_count
    
    human_effort_eliminated = ((tickets_saving_100 * 1.0 + tickets_saving_50 * 0.5) / total) * 100
    
    # Variant-specific results
    variant_results = {}
    for variant in ["mini", "parwa", "high"]:
        vr = [r for r in results if r["variant"] == variant]
        if vr:
            variant_results[variant] = {
                "count": len(vr),
                "intent_accuracy": (sum(1 for r in vr if r["intent_match"]) / len(vr)) * 100,
                "sentiment_accuracy": (sum(1 for r in vr if r["sentiment_match"]) / len(vr)) * 100,
                "avg_quality": sum(r["quality_score"] for r in vr) / len(vr),
                "fully_automated": sum(1 for r in vr if not r["needs_human"] and not r["partially_automated"]),
                "partially_automated": sum(1 for r in vr if r["partially_automated"]),
                "needs_human": sum(1 for r in vr if r["needs_human"]),
            }
    
    # ── Print Report ──────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  MONTH 1 VALIDATION REPORT")
    print("=" * 80)
    
    print(f"\n  {'Metric':<35} {'Result':<12} {'Target':<12} {'Status'}")
    print("  " + "-" * 75)
    
    def status(result, target):
        return "✓ PASS" if result >= target else "✗ FAIL"
    
    print(f"  {'Intent Accuracy':<35} {intent_accuracy:<12.1f} {'≥65%':<12} {status(intent_accuracy, 65)}")
    print(f"  {'Sentiment Accuracy':<35} {sentiment_accuracy:<12.1f} {'≥60%':<12} {status(sentiment_accuracy, 60)}")
    print(f"  {'Escalation Accuracy':<35} {escalation_accuracy:<12.1f} {'≥70%':<12} {status(escalation_accuracy, 70)}")
    print(f"  {'Average Quality Score':<35} {avg_quality:<12.1f} {'≥65':<12} {status(avg_quality, 65)}")
    print(f"  {'Human Effort Eliminated':<35} {human_effort_eliminated:<12.1f} {'≥15%':<12} {status(human_effort_eliminated, 15)}")
    
    print(f"\n  {'Automation Breakdown':<35}")
    print(f"  {'  Fully Automated (100% saved)':<35} {tickets_saving_100} tickets")
    print(f"  {'  Partially Automated (50% saved)':<35} {tickets_saving_50} tickets")
    print(f"  {'  Needs Human (0% saved)':<35} {tickets_saving_0} tickets")
    
    print(f"\n  {'Variant-Specific Results':<35}")
    for variant, vr in variant_results.items():
        print(f"\n  {variant.upper():<35}")
        print(f"    {'Intent Accuracy':<33} {vr['intent_accuracy']:.1f}%")
        print(f"    {'Sentiment Accuracy':<33} {vr['sentiment_accuracy']:.1f}%")
        print(f"    {'Avg Quality Score':<33} {vr['avg_quality']:.1f}")
        print(f"    {'Fully Automated':<33} {vr['fully_automated']}/{vr['count']}")
        print(f"    {'Partially Automated':<33} {vr['partially_automated']}/{vr['count']}")
        print(f"    {'Needs Human':<33} {vr['needs_human']}/{vr['count']}")
    
    print(f"\n  {'Individual Ticket Results':<35}")
    print("  " + "-" * 75)
    for i, r in enumerate(results):
        intent_mark = "✓" if r["intent_match"] else "✗"
        sent_mark = "✓" if r["sentiment_match"] else "✗"
        esc_mark = "✓" if r["escalation_match"] else "✗"
        auto_status = "FULL" if not r["needs_human"] and not r["partially_automated"] else "PARTIAL" if r["partially_automated"] else "HUMAN"
        print(f"  [{i+1:2d}] {r['description'][:50]:<50} {r['variant']:<5} I:{intent_mark} S:{sent_mark} E:{esc_mark} Q:{r['quality_score']:5.1f} {auto_status}")
        if not r["intent_match"]:
            print(f"       Intent: expected={r['expected_intent']}, got={r['actual_intent']}")
        if not r["sentiment_match"]:
            print(f"       Sentiment: expected={r['expected_sentiment']}, got={r['actual_sentiment']}")
        if not r["escalation_match"]:
            print(f"       Escalation: expected={r['expected_escalation']}, got={r['actual_escalation']}")
    
    # ── Per-Ticket Details ────────────────────────────────────────────────
    print(f"\n  {'Detailed Execution Results by Variant':<35}")
    print("  " + "-" * 75)
    for i, r in enumerate(results):
        if r["has_executed_actions"] or r["has_recommended_actions"] or r["has_denied_actions"]:
            print(f"  [{i+1:2d}] {r['description'][:60]} ({r['variant']})")
            if r["has_executed_actions"]:
                print(f"       → Actions EXECUTED (system acted autonomously)")
            if r["has_recommended_actions"]:
                print(f"       → Actions RECOMMENDED (pending human approval)")
            if r["has_denied_actions"]:
                print(f"       → Actions DENIED (variant restriction)")
    
    # ── Final Verdict ──────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    all_pass = (
        intent_accuracy >= 65 and
        sentiment_accuracy >= 60 and
        escalation_accuracy >= 70 and
        human_effort_eliminated >= 15
    )
    
    if all_pass:
        print("  ✓ MONTH 1 VALIDATION: ALL TARGETS MET")
    else:
        print("  ✗ MONTH 1 VALIDATION: SOME TARGETS NOT MET")
        if intent_accuracy < 65:
            print(f"    ✗ Intent accuracy {intent_accuracy:.1f}% < 65% target")
        if sentiment_accuracy < 60:
            print(f"    ✗ Sentiment accuracy {sentiment_accuracy:.1f}% < 60% target")
        if escalation_accuracy < 70:
            print(f"    ✗ Escalation accuracy {escalation_accuracy:.1f}% < 70% target")
        if human_effort_eliminated < 15:
            print(f"    ✗ Human effort elimination {human_effort_eliminated:.1f}% < 15% target")
    
    print("=" * 80)
    
    # Save JSON report
    report = {
        "timestamp": datetime.now().isoformat(),
        "month1_targets": {
            "intent_accuracy": {"target": 65, "actual": round(intent_accuracy, 1)},
            "sentiment_accuracy": {"target": 60, "actual": round(sentiment_accuracy, 1)},
            "escalation_accuracy": {"target": 70, "actual": round(escalation_accuracy, 1)},
            "human_effort_eliminated": {"target": 15, "actual": round(human_effort_eliminated, 1)},
            "avg_quality_score": {"target": 65, "actual": round(avg_quality, 1)},
        },
        "automation_breakdown": {
            "fully_automated": tickets_saving_100,
            "partially_automated": tickets_saving_50,
            "needs_human": tickets_saving_0,
            "total_tickets": total,
        },
        "variant_results": variant_results,
        "individual_results": results,
        "all_targets_met": all_pass,
    }
    
    with open("/home/z/my-project/download/month1_e2e_validation_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n  Report saved to: /home/z/my-project/download/month1_e2e_validation_report.json")
    
    return all_pass


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
