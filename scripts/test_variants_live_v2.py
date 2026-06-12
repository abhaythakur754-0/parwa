#!/usr/bin/env python3
"""PARWA Live Variant Test — Run all variants against real-world tickets.

This script:
1. Starts the ZAI LLM Bridge
2. Resets the Fake CRM for each test
3. Runs each ticket through each variant (mini, parwa, high)
4. Captures results: response quality, action accuracy, CRM state changes
5. Produces an honest report

Usage:
    PARWA_MOCK_MODE=false python scripts/test_variants_live_v2.py
"""

import asyncio
import json
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure we're using real LLM
os.environ["PARWA_MOCK_MODE"] = "false"


async def run_single_ticket(ticket: dict, variant: str) -> dict[str, Any]:
    """Run a single ticket through the PARWA pipeline with a specific variant."""
    from parwa.graph import aprocess_ticket
    from parwa.fake_crm.database import reset_crm, get_crm

    # Reset CRM for clean state
    reset_crm()

    ticket_id = ticket["id"]
    name = ticket["name"]
    customer_id = ticket["customer_id"]
    channel = ticket["channel"]
    message = ticket["message"]

    print(f"\n{'='*70}")
    print(f"  Ticket {ticket_id}: {name}")
    print(f"  Variant: {variant.upper()} | Channel: {channel}")
    print(f"  Customer: {customer_id}")
    print(f"  Message: {message[:100]}...")
    print(f"{'='*70}")

    start = time.time()
    try:
        result = await aprocess_ticket(
            raw_message=message,
            customer_id=customer_id,
            channel=channel,
            variant=variant,
        )
        elapsed = time.time() - start

        # Check CRM state after execution
        crm = get_crm()
        crm_actions = crm.get_action_log()
        customer_after = crm.get_customer(customer_id)

        # Extract key results
        final_response = result.get("final_response", "")
        quality_score = result.get("quality_score", 0)
        intent = result.get("intent", "unknown")
        sentiment = result.get("sentiment", "unknown")
        complexity = result.get("complexity", "unknown")
        execution_results = result.get("execution_results", [])
        recommendation = result.get("recommendation")
        active_frameworks = result.get("active_frameworks", [])
        should_escalate = result.get("should_escalate", False)
        verification_passed = result.get("verification_passed", False)

        # Evaluate accuracy
        expected_intent = ticket.get("expected_intent", "")
        expected_complexity = ticket.get("expected_complexity", "")
        expected_actions = ticket.get("expected_actions", [])
        expected_outcome = ticket.get("expected_outcome", "")

        intent_match = intent == expected_intent
        complexity_match = complexity == expected_complexity

        # Check if expected actions were taken
        actions_taken = [r.get("action_type") for r in execution_results]
        action_match = any(
            expected in actions_taken
            for expected in expected_actions
        ) if expected_actions else True

        # Check variant-specific expectations
        variant_expectation = ticket.get("variant_expectations", {}).get(variant, "")
        variant_met = _check_variant_expectation(
            variant, execution_results, recommendation, variant_expectation
        )

        result_summary = {
            "ticket_id": ticket_id,
            "ticket_name": name,
            "variant": variant,
            "elapsed_seconds": round(elapsed, 2),
            "success": True,
            "intent": intent,
            "intent_match": intent_match,
            "sentiment": sentiment,
            "complexity": complexity,
            "complexity_match": complexity_match,
            "quality_score": quality_score,
            "final_response": final_response[:500],
            "execution_results": execution_results,
            "recommendation": recommendation,
            "active_frameworks": active_frameworks,
            "should_escalate": should_escalate,
            "verification_passed": verification_passed,
            "crm_actions": crm_actions,
            "action_match": action_match,
            "variant_expectation": variant_expectation,
            "variant_met": variant_met,
            "expected_intent": expected_intent,
            "expected_complexity": expected_complexity,
            "expected_actions": expected_actions,
            "expected_outcome": expected_outcome,
        }

        # Print summary
        status_icon = "✅" if quality_score >= 70 else "⚠️" if quality_score >= 50 else "❌"
        print(f"\n  {status_icon} Result: intent={intent} (expected={expected_intent}, match={intent_match})")
        print(f"  Sentiment: {sentiment} | Complexity: {complexity} (match={complexity_match})")
        print(f"  Quality Score: {quality_score:.1f} | Escalated: {should_escalate}")
        print(f"  Actions taken: {actions_taken}")
        print(f"  Action match: {action_match} | Variant met: {variant_met}")
        print(f"  Frameworks: {active_frameworks}")
        print(f"  CRM actions: {len(crm_actions)} | Elapsed: {elapsed:.2f}s")
        if recommendation:
            print(f"  Recommendation: {recommendation.get('action_type')} (pending approval)")
        print(f"  Response: {final_response[:200]}...")

        return result_summary

    except Exception as exc:
        elapsed = time.time() - start
        print(f"\n  ❌ ERROR: {exc}")
        traceback.print_exc()
        return {
            "ticket_id": ticket_id,
            "ticket_name": name,
            "variant": variant,
            "elapsed_seconds": round(elapsed, 2),
            "success": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def _check_variant_expectation(
    variant: str,
    execution_results: list[dict],
    recommendation: dict | None,
    expectation: str,
) -> bool:
    """Check if the variant-specific expectation was met."""
    if not expectation:
        return True

    expectation_lower = expectation.lower()

    if variant == "mini":
        # Mini should RECOMMEND, not EXECUTE for restricted actions
        if "recommend" in expectation_lower:
            return recommendation is not None and recommendation.get("pending_approval", False)
        if "deny" in expectation_lower:
            return any(r.get("status") == "denied" for r in execution_results)
    elif variant in ("parwa", "high"):
        # PARWA/High should EXECUTE
        if "execute" in expectation_lower:
            return any(r.get("status") == "executed" for r in execution_results)
        if "escalate" in expectation_lower.lower():
            return any(r.get("action_type") == "escalate_to_human" for r in execution_results)
        if "deny" in expectation_lower:
            return any(r.get("status") == "denied" for r in execution_results)

    # Default: if there are execution results with "executed" status, consider it met
    return any(r.get("status") == "executed" for r in execution_results)


async def run_all_tests() -> dict[str, Any]:
    """Run all test tickets through all variants."""
    from parwa.tests.real_world_tickets_v2 import get_tickets

    tickets = get_tickets()
    variants = ["mini", "parwa", "high"]

    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║          PARWA LIVE VARIANT TEST — Real LLM + Real CRM         ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Tickets: {len(tickets):3d}  |  Variants: {len(variants)}  |  Total runs: {len(tickets)*len(variants):3d}        ║")
    print(f"║  Mode: REAL LLM (ZAI SDK)  |  CRM: Fake CRM with rich data    ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    all_results = []
    summary_by_variant = {v: {"total": 0, "success": 0, "quality_scores": [], "intent_matches": 0, "action_matches": 0, "variant_mets": 0, "errors": 0} for v in variants}

    for ticket in tickets:
        for variant in variants:
            result = await run_single_ticket(ticket, variant)
            all_results.append(result)

            v = variant
            summary_by_variant[v]["total"] += 1
            if result.get("success"):
                summary_by_variant[v]["success"] += 1
                summary_by_variant[v]["quality_scores"].append(result.get("quality_score", 0))
                if result.get("intent_match"):
                    summary_by_variant[v]["intent_matches"] += 1
                if result.get("action_match"):
                    summary_by_variant[v]["action_matches"] += 1
                if result.get("variant_met"):
                    summary_by_variant[v]["variant_mets"] += 1
            else:
                summary_by_variant[v]["errors"] += 1

    # Compute averages
    for v in variants:
        scores = summary_by_variant[v]["quality_scores"]
        summary_by_variant[v]["avg_quality"] = sum(scores) / len(scores) if scores else 0
        total = summary_by_variant[v]["total"]
        summary_by_variant[v]["intent_accuracy"] = summary_by_variant[v]["intent_matches"] / total if total else 0
        summary_by_variant[v]["action_accuracy"] = summary_by_variant[v]["action_matches"] / total if total else 0
        summary_by_variant[v]["variant_compliance"] = summary_by_variant[v]["variant_mets"] / total if total else 0

    # Print final summary
    print("\n\n")
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║                    FINAL RESULTS SUMMARY                        ║")
    print("╠══════════════════════════════════════════════════════════════════╣")

    for v in variants:
        s = summary_by_variant[v]
        print(f"║  {v.upper():8s} | Success: {s['success']}/{s['total']} | Avg Quality: {s['avg_quality']:.1f}")
        print(f"║           | Intent Acc: {s['intent_accuracy']:.1%} | Action Acc: {s['action_accuracy']:.1%}")
        print(f"║           | Variant Compliance: {s['variant_compliance']:.1%} | Errors: {s['errors']}")
        print("║──────────────────────────────────────────────────────────────────║")

    # Can PARWA replace humans?
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  CAN PARWA REPLACE HUMANS?                                      ║")
    print("╠══════════════════════════════════════════════════════════════════╣")

    best_variant = max(summary_by_variant.values(), key=lambda x: x["avg_quality"])
    best_name = [v for v, s in summary_by_variant.items() if s is best_variant][0]

    if best_variant["avg_quality"] >= 80 and best_variant["action_accuracy"] >= 0.8:
        print("║  ✅ YES — Best variant (HIGH) can handle most tickets           ║")
        print(f"║     Quality: {best_variant['avg_quality']:.1f} | Action accuracy: {best_variant['action_accuracy']:.1%}")
    elif best_variant["avg_quality"] >= 60:
        print("║  ⚠️  PARTIALLY — Handles routine tickets, needs human backup    ║")
        print(f"║     Quality: {best_variant['avg_quality']:.1f} | Action accuracy: {best_variant['action_accuracy']:.1%}")
    else:
        print("║  ❌ NOT YET — Too many failures, needs more work                ║")
        print(f"║     Quality: {best_variant['avg_quality']:.1f} | Action accuracy: {best_variant['action_accuracy']:.1%}")

    print("╚══════════════════════════════════════════════════════════════════╝")

    # Save results
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_tickets": len(tickets),
        "variants_tested": variants,
        "all_results": all_results,
        "summary_by_variant": summary_by_variant,
    }

    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "test_results_live_v2.json"
    )
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n📄 Full report saved to: {report_path}")

    return report


async def run_quick_test():
    """Quick test — just 3 tickets, 1 variant, to verify the pipeline works."""
    from parwa.graph import aprocess_ticket
    from parwa.fake_crm.database import reset_crm, get_crm

    # Reset CRM
    reset_crm()

    print("⚡ Quick test — 1 ticket, PARWA variant")
    print("-" * 50)

    message = (
        "Hi, I was charged $189.99 twice for order ORD-2001 on June 1st. "
        "I only ordered once. Please refund the duplicate charge."
    )

    start = time.time()
    result = await aprocess_ticket(
        raw_message=message,
        customer_id="CUST-1001",
        channel="email",
        variant="parwa",
    )
    elapsed = time.time() - start

    print(f"\n✅ Pipeline completed in {elapsed:.2f}s")
    print(f"Intent: {result.get('intent')}")
    print(f"Sentiment: {result.get('sentiment')}")
    print(f"Complexity: {result.get('complexity')}")
    print(f"Quality Score: {result.get('quality_score')}")
    print(f"Final Response: {result.get('final_response', '')[:300]}...")
    print(f"Frameworks: {result.get('active_frameworks')}")
    print(f"Execution Results: {result.get('execution_results')}")

    # Check CRM state
    crm = get_crm()
    actions = crm.get_action_log()
    customer = crm.get_customer("CUST-1001")
    print(f"\nCRM Actions: {len(actions)}")
    for a in actions:
        print(f"  - {a['action']}: {a['details']}")

    if customer:
        payments = customer.get("payments", [])
        refunded = [p for p in payments if p.get("status") == "refunded"]
        print(f"Payments: {len(payments)} total, {len(refunded)} refunded")
        for p in refunded:
            print(f"  - {p['payment_id']}: ${p.get('refunded_amount', 0)} refunded")

    return result


if __name__ == "__main__":
    if "--quick" in sys.argv:
        asyncio.run(run_quick_test())
    else:
        asyncio.run(run_all_tests())
