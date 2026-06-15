#!/usr/bin/env python3
"""PARWA Variant Arena — Run tickets across all 3 variants and compare.

Runs 3 test tickets across mini, parwa, and high variants:
  1. SIMPLE ticket: Basic refund request
  2. COMPLEX ticket: Multi-issue billing escalation
  3. COMPLICATED/CRITICAL ticket: Token-heavy, edge-case nightmare

Reports per-variant:
  - Techniques activated per node (are they all firing now?)
  - Quality score
  - Confidence level
  - Active frameworks list
  - Pipeline errors
  - Token estimates
"""

import asyncio
import json
import sys
import os
import time

# Ensure parwa is importable
sys.path.insert(0, "/home/z/my-project")

# Force MOCK_MODE so we don't need real LLM keys
os.environ["PARWA_MOCK_MODE"] = "1"

from parwa.graph import process_ticket


# ─── Test Tickets ──────────────────────────────────────────────────────────

TICKETS = {
    "T1_SIMPLE_REFUND": {
        "raw_message": "Hi, I was charged twice for my order. Can I get a refund for the duplicate charge?",
        "customer_id": "cust_001",
        "channel": "email",
        "description": "Simple refund request — should only activate CoT",
    },

    "T2_COMPLEX_BILLING": {
        "raw_message": (
            "I've been trying to resolve a billing issue for 3 weeks now. "
            "I was charged $49.99 on March 1st, then again $49.99 on March 3rd for the same order. "
            "I called your support line twice and was told both times it would be resolved within 48 hours. "
            "It's now March 21st and I still haven't received my refund. "
            "I also noticed a $12.99 charge for a subscription I never signed up for. "
            "I want ALL charges reversed immediately or I'm contacting my attorney. "
            "This is completely unacceptable and I'm extremely frustrated with the lack of response."
        ),
        "customer_id": "cust_002",
        "channel": "email",
        "description": "Complex billing escalation — should activate CoT + ReAct + ToT + Reverse + GST",
    },

    "T3_CRITICAL_NIGHTMARE": {
        "raw_message": (
            "URGENT: I am writing to formally escalate a series of critical issues that have remained "
            "unresolved despite multiple contacts over the past 45 days. Here is the complete timeline:\n\n"
            "1. On January 15th, I placed Order #ORD-78234 for $249.99 (premium widget package). "
            "The order was confirmed but never shipped.\n\n"
            "2. On January 22nd, I noticed a second charge of $249.99 on my credit card for the same order. "
            "I contacted support via chat (Ticket #TKT-4456) and was told it was a 'system glitch' that "
            "would be resolved in 3-5 business days.\n\n"
            "3. On February 1st, I received an email saying my order was CANCELLED, but neither charge "
            "was refunded. I called the support hotline and spoke with 'Sarah' who said she would escalate "
            "to billing. She gave me a reference number REF-88234.\n\n"
            "4. On February 10th, I noticed ANOTHER charge of $12.99/month for a 'Premium Support Plan' "
            "that I never signed up for. This has been charged for 3 months (December, January, February) "
            "totaling $38.97 in unauthorized charges.\n\n"
            "5. On February 15th, I received a collections notice for $249.99 claiming I have an unpaid "
            "balance. This is for the order that was CANCELLED. How can I owe money for a cancelled order "
            "that was never fulfilled AND was charged twice to my card?\n\n"
            "6. I contacted support again on February 28th (Ticket #TKT-5501) and the agent told me the "
            "previous tickets were 'closed as resolved' even though nothing was resolved.\n\n"
            "7. On March 1st, I attempted to speak with a supervisor and was told none were available. "
            "I was promised a callback within 24 hours. No one called.\n\n"
            "Total financial impact:\n"
            "  - Double charge: $249.99 (should be refunded)\n"
            "  - Cancelled order charge: $249.99 (should be refunded)\n"
            "  - Unauthorized subscription: $38.97 (3 months × $12.99)\n"
            "  - Collections damage: CREDIT SCORE IMPACT\n"
            "  - Total monetary: $538.95\n\n"
            "I am giving you 48 hours to resolve this completely before I:\n"
            "  1. File a complaint with the Better Business Bureau\n"
            "  2. File a chargeback with my credit card company for all unauthorized charges\n"
            "  3. Contact a consumer rights attorney about the collections damage\n"
            "  4. Post about this experience on all social media platforms\n\n"
            "This is my FINAL attempt at resolution through normal channels. I expect:\n"
            "  - Full refund of $538.95\n"
            "  - Removal of the collections notice\n"
            "  - Written confirmation that my account is clear\n"
            "  - An explanation of why my previous 4 contacts were ignored\n"
        ),
        "customer_id": "cust_003",
        "channel": "email",
        "description": "Critical nightmare — should activate ALL techniques including UoT (the emergency brake)",
    },
}

VARIANTS = ["mini", "parwa", "high"]


async def run_ticket(ticket_key: str, ticket_data: dict, variant: str) -> dict:
    """Run a single ticket through the pipeline and collect results."""
    start = time.time()
    try:
        result = await process_ticket(
            raw_message=ticket_data["raw_message"],
            customer_id=ticket_data.get("customer_id", ""),
            channel=ticket_data.get("channel", "email"),
            variant=variant,
        ) or {}
    except Exception as e:
        result = {"error": str(e), "error_type": type(e).__name__}

    elapsed = time.time() - start

    return {
        "ticket": ticket_key,
        "variant": variant,
        "elapsed_seconds": round(elapsed, 2),
        "quality_score": result.get("quality_score", 0),
        "confidence": result.get("confidence", 0),
        "intent": result.get("intent", "unknown"),
        "complexity": result.get("complexity", "unknown"),
        "sentiment": result.get("sentiment", "unknown"),
        "should_escalate": result.get("should_escalate", False),
        "active_frameworks": result.get("active_frameworks", []),
        "reasoning_conclusion": (result.get("reasoning_conclusion") or "")[:120],
        "final_response": (result.get("final_response") or "")[:200],
        "pipeline_errors": result.get("pipeline_errors", []),
        "has_error": bool(result.get("error")),
        "error": result.get("error"),
        "reasoning_chain_length": len(result.get("reasoning_chain", [])),
        "reasoning_paths_count": len(result.get("reasoning_paths", [])),
        "action_plans_count": len(result.get("action_plans", [])),
        "strategy_plan_steps": len(result.get("strategy_plan", [])),
        "kb_results_count": len(result.get("kb_results", [])),
    }


async def main():
    print("=" * 80)
    print("PARWA VARIANT ARENA — Testing All 3 Tickets × 3 Variants")
    print("=" * 80)
    print(f"Running {len(TICKETS)} tickets × {len(VARIANTS)} variants = {len(TICKETS) * len(VARIANTS)} runs")
    print()

    all_results = []

    for ticket_key, ticket_data in TICKETS.items():
        print(f"\n{'─' * 70}")
        print(f"TICKET: {ticket_key}")
        print(f"  Description: {ticket_data['description']}")
        print(f"  Message length: {len(ticket_data['raw_message'])} chars")
        print(f"{'─' * 70}")

        for variant in VARIANTS:
            print(f"\n  ▸ Running {ticket_key} on variant='{variant}'...")
            result = await run_ticket(ticket_key, ticket_data, variant)
            all_results.append(result)

            # Print summary
            status = "OK" if not result["has_error"] else f"ERROR: {result.get('error', 'unknown')[:80]}"
            print(f"    Status: {status}")
            print(f"    Time: {result['elapsed_seconds']}s")
            print(f"    Intent: {result['intent']} | Complexity: {result['complexity']} | Sentiment: {result['sentiment']}")
            print(f"    Quality Score: {result['quality_score']}")
            print(f"    Escalated: {result['should_escalate']}")
            print(f"    Active Frameworks: {result['active_frameworks']}")
            print(f"    Reasoning paths: {result['reasoning_paths_count']} | Strategy steps: {result['strategy_plan_steps']}")
            print(f"    KB results: {result['kb_results_count']} | Action plans: {result['action_plans_count']}")
            print(f"    Pipeline errors: {len(result['pipeline_errors'])}")

    # ─── Comparison Table ──────────────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("COMPARISON TABLE")
    print("=" * 80)

    for ticket_key in TICKETS:
        print(f"\n  {ticket_key}:")
        print(f"    {'Variant':<10} {'Quality':<10} {'Complexity':<12} {'Escalated':<12} {'Frameworks':<45} {'Errors':<8}")
        print(f"    {'─'*10} {'─'*10} {'─'*12} {'─'*12} {'─'*45} {'─'*8}")

        for r in all_results:
            if r["ticket"] == ticket_key:
                fws = ", ".join(r["active_frameworks"]) if r["active_frameworks"] else "NONE"
                if len(fws) > 43:
                    fws = fws[:40] + "..."
                err_count = len(r["pipeline_errors"]) + (1 if r["has_error"] else 0)
                print(f"    {r['variant']:<10} {r['quality_score']:<10} {r['complexity']:<12} {str(r['should_escalate']):<12} {fws:<45} {err_count:<8}")

    # ─── Technique Activation Check ────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("TECHNIQUE ACTIVATION CHECK (are they all firing?)")
    print("=" * 80)

    for ticket_key in TICKETS:
        print(f"\n  {ticket_key}:")
        for variant in VARIANTS:
            r = [x for x in all_results if x["ticket"] == ticket_key and x["variant"] == variant][0]
            fws = set(r["active_frameworks"])

            checks = {
                "chain_of_thought": fws,
                "react": fws,
                "tree_of_thoughts": fws,
                "reverse_thinking": fws,
                "graph_of_strategic_thought": fws,
                "uncertainty_of_thought": fws,
                "hyde": fws,
                "multi_query": fws,
                "step_back": fws,
                "clara": fws,
            }

            activated = [name for name, s in checks.items() if name in s]
            missing = [name for name, s in checks.items() if name not in s]

            print(f"    {variant}: ACTIVATED({len(activated)}) = {activated}")
            if missing:
                print(f"           NOT activated: {missing}")

    # ─── Save raw results ──────────────────────────────────────────────────
    output_path = "/home/z/my-project/download/variant_arena_results.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n\nRaw results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
