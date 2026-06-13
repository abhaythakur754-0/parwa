#!/usr/bin/env python3
"""PARWA P1 Variant Testing Script — Honest Quality Scoring.

This script runs test tickets through all 3 PARWA variants (mini, parwa, high)
and produces an honest quality report comparing:
  - Quality scores
  - Evidence chain depth
  - Red team findings
  - Debate outcomes
  - Framework activation
  - Token usage

Usage:
    python test_variants.py [--mock] [--ticket TICKET_TEXT] [--verbose]

The --mock flag runs in mock mode (no real LLM calls) for fast iteration.
Without --mock, it uses the real LLM for honest scoring.

Test tickets cover different complexities:
  - Simple: "What is your refund policy?"
  - Medium: "I was charged twice for my subscription, please refund the duplicate charge"
  - Complex: "I want to cancel my order ORD-12345 and get a full refund. I was overcharged $149.99 and the product doesn't work. I've emailed 3 times already with no response."
  - Critical: "This is my third email about being charged $299.98 for a $49.99 plan. I want to speak to your supervisor immediately, or I will contact my attorney about filing a fraud claim."
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from typing import Any

# Add project to path
sys.path.insert(0, "/home/z/my-project/parwa")

logging.basicConfig(level=logging.WARNING)  # Quiet down except warnings
logger = logging.getLogger("parwa.test")


# ─── Test Ticket Suite ───────────────────────────────────────────────────────

TEST_TICKETS = [
    {
        "name": "Simple FAQ",
        "message": "What is your refund policy?",
        "customer_id": "CUST-001",
        "channel": "email",
        "expected_complexity": "simple",
        "expected_intent": "faq_question",
    },
    {
        "name": "Medium Refund",
        "message": "I was charged twice for my subscription, please refund the duplicate charge of $49.99",
        "customer_id": "CUST-002",
        "channel": "email",
        "expected_complexity": "medium",
        "expected_intent": "refund_request",
    },
    {
        "name": "Complex Cancel+Refund",
        "message": "I want to cancel my order ORD-12345 and get a full refund. I was overcharged $149.99 and the product doesn't work. I've emailed 3 times already with no response.",
        "customer_id": "CUST-003",
        "channel": "email",
        "expected_complexity": "complex",
        "expected_intent": "cancellation",
    },
    {
        "name": "Critical Fraud Threat",
        "message": "This is my third email about being charged $299.98 for a $49.99 plan. I want to speak to your supervisor immediately, or I will contact my attorney about filing a fraud claim.",
        "customer_id": "CUST-004",
        "channel": "email",
        "expected_complexity": "critical",
        "expected_intent": "billing_issue",
    },
    {
        "name": "Account Modification",
        "message": "I need to update my email address and add 5 more seats to my team plan. My current email is old@company.com and I want to change it to new@company.com",
        "customer_id": "CUST-005",
        "channel": "chat",
        "expected_complexity": "medium",
        "expected_intent": "account_modification",
    },
]


# ─── Quality Assessment Functions ────────────────────────────────────────────

def _assess_response_quality(ticket: dict, result: dict[str, Any]) -> dict[str, Any]:
    """Assess the quality of a variant's response for a specific ticket.

    This is an HONEST assessment — it checks if the response actually
    addresses the customer's issue, not just if it looks good.
    """
    message = ticket["message"].lower()
    expected_intent = ticket["expected_intent"]
    response = result.get("final_response", "").lower()
    quality_score = result.get("quality_score", 0.0)

    # Check 1: Intent classification accuracy
    actual_intent = result.get("intent", "unknown")
    intent_match = actual_intent == expected_intent or any(
        kw in actual_intent for kw in expected_intent.split("_")
    )

    # Check 2: Did it address the specific concern?
    concern_keywords = {
        "refund_request": ["refund", "charge", "money"],
        "billing_issue": ["charge", "billing", "amount", "plan"],
        "cancellation": ["cancel", "order"],
        "account_modification": ["update", "change", "email", "seats"],
        "faq_question": ["policy", "refund"],
    }
    expected_keywords = concern_keywords.get(expected_intent, [])
    keywords_addressed = sum(1 for kw in expected_keywords if kw in response)

    # Check 3: Specific data in response (order IDs, amounts, etc.)
    import re
    has_specific_data = bool(re.search(r'(ORD-|TKT-|\$[\d,.]+|\d{4}-\d{2}-\d{2}|order #)', response))

    # Check 4: Is the response generic/template?
    generic_phrases = [
        "thank you for reaching out",
        "we've reviewed your request",
        "a member of our team will",
        "our team will investigate",
    ]
    is_generic = any(phrase in response for phrase in generic_phrases)

    # Check 5: Was the escalation correct?
    should_escalate = result.get("should_escalate", False)
    escalation_correct = False
    if ticket["expected_complexity"] in ("critical",) and "attorney" in message:
        escalation_correct = should_escalate  # Should have escalated
    elif ticket["expected_complexity"] in ("simple", "medium"):
        escalation_correct = not should_escalate  # Should NOT have escalated

    # Check 6: Red team findings
    red_team = result.get("red_team_report", {})
    red_team_passed = red_team.get("passed", True) if isinstance(red_team, dict) else True
    red_team_severity = red_team.get("severity", "none") if isinstance(red_team, dict) else "none"

    # Check 7: Debate outcome
    debate = result.get("debate_result", {})
    debate_outcome = debate.get("outcome", "unknown") if isinstance(debate, dict) else "unknown"

    # Check 8: Evidence chain depth
    evidence_chain = result.get("evidence_chain", [])
    evidence_depth = len(evidence_chain) if isinstance(evidence_chain, list) else 0

    # Check 9: Frameworks activated
    frameworks = result.get("active_frameworks", [])
    framework_count = len(frameworks) if isinstance(frameworks, list) else 0

    # Calculate honest quality assessment
    honest_score = 0.0
    honest_issues = []

    # Intent accuracy (25 points)
    if intent_match:
        honest_score += 25
    else:
        honest_issues.append(f"intent_mismatch: expected={expected_intent}, got={actual_intent}")

    # Concern addressed (25 points)
    if keywords_addressed >= len(expected_keywords) * 0.5:
        honest_score += min(25, keywords_addressed * 8)
    else:
        honest_issues.append("concern_not_addressed")

    # Specific data (15 points)
    if has_specific_data:
        honest_score += 15
    else:
        honest_issues.append("no_specific_data")

    # Not generic (15 points)
    if not is_generic:
        honest_score += 15
    else:
        honest_score -= 5
        honest_issues.append("generic_response")

    # Escalation correct (10 points)
    if escalation_correct:
        honest_score += 10
    else:
        honest_issues.append("incorrect_escalation")

    # Red team passed (10 points)
    if red_team_passed:
        honest_score += 10
    else:
        honest_score -= 5
        honest_issues.append(f"red_team_{red_team_severity}")

    honest_score = max(0, min(100, honest_score))

    return {
        "honest_score": honest_score,
        "honest_issues": honest_issues,
        "pipeline_score": quality_score,
        "intent_match": intent_match,
        "keywords_addressed": keywords_addressed,
        "has_specific_data": has_specific_data,
        "is_generic": is_generic,
        "escalation_correct": escalation_correct,
        "red_team_passed": red_team_passed,
        "red_team_severity": red_team_severity,
        "debate_outcome": debate_outcome,
        "evidence_depth": evidence_depth,
        "framework_count": framework_count,
    }


async def _run_single_ticket(
    ticket: dict,
    variant: str,
    mock_mode: bool = False,
) -> dict[str, Any]:
    """Run a single ticket through a single variant."""
    from parwa.graph import aprocess_ticket

    start = time.monotonic()
    try:
        result = await aprocess_ticket(
            raw_message=ticket["message"],
            customer_id=ticket["customer_id"],
            channel=ticket["channel"],
            variant=variant,
        )
        elapsed = time.monotonic() - start

        # Assess quality
        assessment = _assess_response_quality(ticket, result)

        return {
            "ticket_name": ticket["name"],
            "variant": variant,
            "elapsed_seconds": round(elapsed, 2),
            "success": True,
            "final_response": result.get("final_response", "")[:200],
            "quality_score": result.get("quality_score", 0),
            "intent": result.get("intent", "unknown"),
            "complexity": result.get("complexity", "unknown"),
            "should_escalate": result.get("should_escalate", False),
            "active_frameworks": result.get("active_frameworks", []),
            "evidence_depth": assessment["evidence_depth"],
            "red_team_severity": assessment["red_team_severity"],
            "red_team_passed": assessment["red_team_passed"],
            "debate_outcome": assessment["debate_outcome"],
            "loop_count": result.get("loop_count", 0),
            "honest_score": assessment["honest_score"],
            "honest_issues": assessment["honest_issues"],
            "error": None,
        }

    except Exception as exc:
        elapsed = time.monotonic() - start
        return {
            "ticket_name": ticket["name"],
            "variant": variant,
            "elapsed_seconds": round(elapsed, 2),
            "success": False,
            "error": str(exc),
            "honest_score": 0,
            "honest_issues": [f"pipeline_error: {exc}"],
        }


async def run_all_tests(mock_mode: bool = False, verbose: bool = False) -> dict[str, Any]:
    """Run all test tickets through all variants."""
    variants = ["mini", "parwa", "high"]
    results = []

    print("\n" + "=" * 80)
    print("PARWA P1 VARIANT TESTING — Honest Quality Assessment")
    print("=" * 80)
    print(f"Mode: {'MOCK (no real LLM)' if mock_mode else 'LIVE (real LLM calls)'}")
    print(f"Tickets: {len(TEST_TICKETS)} | Variants: {len(variants)}")
    print(f"Total test cases: {len(TEST_TICKETS) * len(variants)}")
    print("=" * 80 + "\n")

    for ticket in TEST_TICKETS:
        print(f"\n--- Ticket: {ticket['name']} ---")
        print(f"    Message: {ticket['message'][:80]}...")
        print(f"    Expected: complexity={ticket['expected_complexity']}, intent={ticket['expected_intent']}")

        for variant in variants:
            print(f"\n  [{variant.upper()}] Processing...", end=" ", flush=True)
            result = await _run_single_ticket(ticket, variant, mock_mode)
            results.append(result)

            if result["success"]:
                print(f"Done in {result['elapsed_seconds']}s")
                print(f"    Pipeline Score: {result['quality_score']:.1f}/100")
                print(f"    Honest Score:   {result['honest_score']:.1f}/100")
                print(f"    Intent: {result['intent']} | Complexity: {result.get('complexity', '?')}")
                print(f"    Escalate: {result.get('should_escalate', False)} | Loops: {result.get('loop_count', 0)}")
                print(f"    Evidence Depth: {result['evidence_depth']} | Frameworks: {len(result.get('active_frameworks', []))}")
                print(f"    Red Team: {result['red_team_severity']} | Debate: {result['debate_outcome']}")
                if result["honest_issues"]:
                    print(f"    Issues: {', '.join(result['honest_issues'][:5])}")
                if verbose:
                    print(f"    Response: {result.get('final_response', 'N/A')[:150]}")
            else:
                print(f"FAILED: {result['error']}")

    # ─── Summary Report ───────────────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("SUMMARY: HONEST QUALITY SCORES BY VARIANT")
    print("=" * 80)

    variant_scores = {}
    for variant in variants:
        variant_results = [r for r in results if r["variant"] == variant]
        scores = [r["honest_score"] for r in variant_results if r["success"]]
        pipeline_scores = [r["quality_score"] for r in variant_results if r["success"]]

        avg_honest = sum(scores) / len(scores) if scores else 0
        avg_pipeline = sum(pipeline_scores) / len(pipeline_scores) if pipeline_scores else 0
        success_rate = len(scores) / len(variant_results) * 100 if variant_results else 0

        variant_scores[variant] = {
            "avg_honest_score": round(avg_honest, 1),
            "avg_pipeline_score": round(avg_pipeline, 1),
            "success_rate": round(success_rate, 1),
            "tickets_tested": len(variant_results),
            "tickets_passed": len(scores),
        }

        print(f"\n  {variant.upper()} Variant:")
        print(f"    Average Honest Score:   {avg_honest:.1f}/100")
        print(f"    Average Pipeline Score: {avg_pipeline:.1f}/100")
        print(f"    Success Rate: {success_rate:.0f}% ({len(scores)}/{len(variant_results)})")

    # ─── Per-ticket comparison ─────────────────────────────────────────
    print("\n\n" + "-" * 80)
    print("PER-TICKET COMPARISON")
    print("-" * 80)
    print(f"{'Ticket':<25} {'Mini':>8} {'PARWA':>8} {'High':>8} {'Best':>8}")
    print("-" * 80)

    for ticket in TEST_TICKETS:
        ticket_results = {v: next((r for r in results if r["ticket_name"] == ticket["name"] and r["variant"] == v), None) for v in variants}
        scores = {}
        for v, r in ticket_results.items():
            if r and r["success"]:
                scores[v] = r["honest_score"]
            else:
                scores[v] = 0.0

        best = max(scores, key=scores.get) if scores else "?"
        print(f"{ticket['name']:<25} {scores.get('mini', 0):>7.0f}  {scores.get('parwa', 0):>7.0f}  {scores.get('high', 0):>7.0f}  {best:>8}")

    # ─── Final honest assessment ──────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("HONEST SYSTEM QUALITY ASSESSMENT")
    print("=" * 80)

    # Overall system score
    all_honest_scores = [r["honest_score"] for r in results if r["success"]]
    overall_avg = sum(all_honest_scores) / len(all_honest_scores) if all_honest_scores else 0

    # Grade the system
    if overall_avg >= 85:
        grade = "A — Production ready, can handle most tickets autonomously"
    elif overall_avg >= 70:
        grade = "B — Good but needs supervision for complex/critical tickets"
    elif overall_avg >= 55:
        grade = "C — Functional but significant gaps in reasoning quality"
    elif overall_avg >= 40:
        grade = "D — Major issues, cannot replace human agents yet"
    else:
        grade = "F — System is not producing useful responses"

    print(f"\n  Overall Honest Score: {overall_avg:.1f}/100")
    print(f"  Grade: {grade}")

    # Identify strongest and weakest areas
    all_issues = []
    for r in results:
        if r["success"]:
            all_issues.extend(r.get("honest_issues", []))

    if all_issues:
        from collections import Counter
        issue_counts = Counter(all_issues)
        print(f"\n  Top Issues:")
        for issue, count in issue_counts.most_common(5):
            print(f"    - {issue}: {count} occurrences")

    # Recommendations
    print(f"\n  Key Findings:")
    mini_avg = variant_scores.get("mini", {}).get("avg_honest_score", 0)
    parwa_avg = variant_scores.get("parwa", {}).get("avg_honest_score", 0)
    high_avg = variant_scores.get("high", {}).get("avg_honest_score", 0)

    print(f"    - Mini variant:  {mini_avg:.0f}/100 (cost-optimized)")
    print(f"    - PARWA variant: {parwa_avg:.0f}/100 (balanced)")
    print(f"    - High variant:  {high_avg:.0f}/100 (quality-optimized)")

    gap = high_avg - mini_avg
    print(f"    - Quality gap (high - mini): {gap:.0f} points")

    if gap < 10:
        print(f"    → Gap is small. Consider using mini for most tickets to save costs.")
    elif gap < 25:
        print(f"    → Moderate gap. Use PARWA as default, high for complex tickets only.")
    else:
        print(f"    → Large gap. High variant significantly better — invest in quality.")

    print("\n" + "=" * 80)

    return {
        "variant_scores": variant_scores,
        "overall_score": round(overall_avg, 1),
        "grade": grade,
        "results": results,
    }


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="PARWA P1 Variant Testing")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode (no real LLM)")
    parser.add_argument("--ticket", type=str, help="Run a custom ticket text")
    parser.add_argument("--verbose", action="store_true", help="Show full responses")
    args = parser.parse_args()

    # Set mock mode if requested
    if args.mock:
        import os
        os.environ["PARWA_MOCK_MODE"] = "1"

    # Custom ticket mode
    if args.ticket:
        custom_ticket = {
            "name": "Custom",
            "message": args.ticket,
            "customer_id": "CUST-CUSTOM",
            "channel": "email",
            "expected_complexity": "medium",
            "expected_intent": "general_inquiry",
        }
        test_tickets = [custom_ticket]
    else:
        test_tickets = TEST_TICKETS

    # Override global tickets if custom
    global TEST_TICKETS
    if args.ticket:
        TEST_TICKETS = test_tickets

    result = asyncio.run(run_all_tests(mock_mode=args.mock, verbose=args.verbose))

    # Save results to file
    output_path = "/home/z/my-project/download/p1_variant_test_results.json"
    with open(output_path, "w") as f:
        # Remove non-serializable items
        clean_results = []
        for r in result["results"]:
            clean_r = {k: v for k, v in r.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
            clean_results.append(clean_r)

        json.dump({
            "variant_scores": result["variant_scores"],
            "overall_score": result["overall_score"],
            "grade": result["grade"],
            "results": clean_results,
        }, f, indent=2)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
