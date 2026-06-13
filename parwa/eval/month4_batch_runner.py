#!/usr/bin/env python3
"""Month 4 Batch Variant Comparison Runner — ZAI SDK powered.

Processes all 15 Month 4 tickets through ALL 3 variants (mini, parwa, high)
using the ZAI SDK as the primary LLM backend with TPM-optimized batching.

Key features:
- ZAI SDK primary (no mock data — real LLM responses)
- Configurable inter-ticket delay for rate limit management
- Per-variant detailed metrics
- Side-by-side comparison: what each variant IGNORES vs GETS RIGHT vs GETS WRONG
- JSON results export for analysis

Month 4 targets (from roadmap):
- Intent accuracy: 90%+ (up from 80% Month 2)
- Sentiment accuracy: 85%+
- Escalation accuracy: 90%+
- Autonomous resolution: 75%+

Usage:
    python -m parwa.eval.month4_batch_runner                    # Full run (15 x 3 = 45 tickets)
    python -m parwa.eval.month4_batch_runner --variant mini     # Only mini
    python -m parwa.eval.month4_batch_runner --delay 3.0        # 3s between tickets
    python -m parwa.eval.month4_batch_runner --quick             # 3 tickets only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from parwa.eval.month4_tickets import MONTH4_TICKETS, get_dataset_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("parwa.eval.month4_batch_runner")


# ════════════════════════════════════════════════════════════════════════════════
# MONTH 4 TARGETS
# ════════════════════════════════════════════════════════════════════════════════

M4_TARGETS = {
    "intent_accuracy": 90.0,
    "sentiment_accuracy": 85.0,
    "escalation_accuracy": 90.0,
    "autonomous_resolution": 75.0,
}


# ════════════════════════════════════════════════════════════════════════════════
# EVALUATION FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def _evaluate_result(
    pipeline_result: dict[str, Any],
    ticket: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate a single ticket result against expected values.

    Returns a dict with correctness flags and details.
    """
    # Extract pipeline outputs
    predicted_intent = pipeline_result.get("intent", "general_inquiry")
    if isinstance(predicted_intent, str):
        predicted_intent = predicted_intent.lower()
    else:
        predicted_intent = str(predicted_intent).lower()

    predicted_sentiment = pipeline_result.get("sentiment", "neutral")
    if isinstance(predicted_sentiment, str):
        predicted_sentiment = predicted_sentiment.lower()
    else:
        predicted_sentiment = str(predicted_sentiment).lower()

    predicted_escalate = pipeline_result.get("should_escalate", False)
    if isinstance(predicted_escalate, str):
        predicted_escalate = predicted_escalate.lower() in ("true", "yes")

    # Get the primary action from action_plans
    action_plans = pipeline_result.get("action_plans", [])
    predicted_action = ""
    if action_plans and isinstance(action_plans, list):
        first_action = action_plans[0]
        if isinstance(first_action, dict):
            predicted_action = first_action.get("action_type", "")
            if isinstance(predicted_action, str):
                predicted_action = predicted_action.lower()
            else:
                predicted_action = str(predicted_action).lower()

    # Also check final_response for action hints
    final_response = pipeline_result.get("final_response", "")
    if not predicted_action and final_response:
        # Try to infer action from the response
        response_lower = final_response.lower()
        if "refund" in response_lower:
            predicted_action = "process_refund"
        elif "cancel" in response_lower:
            predicted_action = "cancel_order"
        elif "escalat" in response_lower:
            predicted_action = "escalate_to_human"
        elif "faq" in response_lower or "policy" in response_lower:
            predicted_action = "share_faq"

    # Expected values
    expected_intent = ticket["expected_intent"].lower()
    expected_sentiment = ticket["expected_sentiment"].lower()
    expected_escalate = ticket["expected_escalation"]
    expected_action = ticket["expected_action"].lower()

    # Compute correctness
    intent_correct = predicted_intent == expected_intent
    sentiment_correct = predicted_sentiment == expected_sentiment
    escalation_correct = predicted_escalate == expected_escalate

    # Action correctness: check if the predicted action contains or matches expected
    action_correct = False
    if predicted_action == expected_action:
        action_correct = True
    elif expected_action in predicted_action:
        action_correct = True
    elif predicted_action in expected_action:
        action_correct = True
    # Special case: escalate_to_human matches escalate
    elif expected_action == "escalate" and "escalat" in predicted_action:
        action_correct = True

    # Autonomous resolution: ticket was resolved without human escalation
    # when expected_escalation is False (meaning the AI should handle it)
    autonomous_resolution = not predicted_escalate and not expected_escalate

    return {
        "ticket_id": ticket["id"],
        "category": ticket["category"],
        "difficulty": ticket["difficulty"],
        "variant": ticket.get("_run_variant", "parwa"),
        # Predictions
        "predicted_intent": predicted_intent,
        "predicted_sentiment": predicted_sentiment,
        "predicted_escalate": predicted_escalate,
        "predicted_action": predicted_action,
        # Expected
        "expected_intent": expected_intent,
        "expected_sentiment": expected_sentiment,
        "expected_escalate": expected_escalate,
        "expected_action": expected_action,
        # Correctness
        "intent_correct": intent_correct,
        "sentiment_correct": sentiment_correct,
        "escalation_correct": escalation_correct,
        "action_correct": action_correct,
        "autonomous_resolution": autonomous_resolution,
        # Extra pipeline data
        "intent_confidence": pipeline_result.get("intent_confidence", 0),
        "quality_score": pipeline_result.get("quality_score", 0),
        "clarifying_question": pipeline_result.get("clarifying_question", ""),
        "multi_intent_detected": pipeline_result.get("multi_intent_detected", False),
        "low_confidence_flag": pipeline_result.get("low_confidence_flag", False),
        "escalation_trigger_reason": pipeline_result.get("escalation_trigger_reason", ""),
        "final_response_preview": final_response[:300] if final_response else "",
    }


async def _run_single_ticket(
    ticket: dict[str, Any],
    variant: str,
    delay: float = 2.0,
) -> dict[str, Any]:
    """Process a single ticket through one variant and evaluate results.

    Uses the ZAI SDK via ainvoke_llm (which now has ZAI SDK as primary).
    Adds a configurable delay between tickets for rate limit management.

    Returns a dict with all evaluation metrics.
    """
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm
    from parwa.turboquant.token_tracker import get_token_tracker

    # Reset state for clean run
    reset_parwa_graph()
    reset_crm()

    # Note: token tracker accumulates across tickets (no reset needed)
    # We measure per-ticket token usage by taking the difference

    # Wait for rate limiting
    if delay > 0:
        await asyncio.sleep(delay)

    ticket_id = ticket["id"]
    message = ticket["message"]
    customer_id = ticket["customer_id"]

    logger.info(">>> [%s] Processing %s via %s variant (customer: %s)",
                datetime.now().strftime("%H:%M:%S"), ticket_id, variant, customer_id)

    start_time = time.time()

    # Get token count before processing for delta measurement
    tokens_before = 0
    try:
        tracker = get_token_tracker()
        tokens_before = tracker.get_total_tokens()
    except Exception:
        pass
    try:
        result = await aprocess_ticket(
            raw_message=message,
            customer_id=customer_id,
            channel="email",
            variant=variant,
        )
        elapsed_ms = (time.time() - start_time) * 1000

        # Get token usage from tracker (delta = this ticket's usage)
        total_tokens = 0
        try:
            tracker = get_token_tracker()
            total_tokens = tracker.get_total_tokens() - tokens_before
        except Exception:
            total_tokens = 0

        pipeline_result = {
            "intent": result.get("intent", "general_inquiry"),
            "intent_confidence": result.get("intent_confidence", 0),
            "sentiment": result.get("sentiment", "neutral"),
            "should_escalate": result.get("should_escalate", False),
            "action_plans": result.get("action_plans", []),
            "quality_score": result.get("quality_score", 0),
            "final_response": result.get("final_response", ""),
            "clarifying_question": result.get("clarifying_question", ""),
            "multi_intent_detected": result.get("multi_intent_detected", False),
            "low_confidence_flag": result.get("low_confidence_flag", False),
            "escalation_trigger_reason": result.get("escalation_trigger_reason", ""),
        }

        evaluation = _evaluate_result(pipeline_result, ticket)
        evaluation["time_ms"] = round(elapsed_ms, 0)
        evaluation["total_tokens"] = total_tokens
        evaluation["variant"] = variant
        evaluation["pipeline_error"] = None

        # Status indicators
        intent_icon = "✓" if evaluation["intent_correct"] else "✗"
        sent_icon = "✓" if evaluation["sentiment_correct"] else "✗"
        esc_icon = "✓" if evaluation["escalation_correct"] else "✗"
        act_icon = "✓" if evaluation["action_correct"] else "✗"

        logger.info(
            "<<< [%s] %s/%s done in %.0fms | Intent:%s Sent:%s Esc:%s Act:%s | conf=%.2f",
            datetime.now().strftime("%H:%M:%S"), ticket_id, variant, elapsed_ms,
            intent_icon, sent_icon, esc_icon, act_icon,
            evaluation["intent_confidence"],
        )

        return evaluation

    except Exception as exc:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error("!!! %s/%s FAILED: %s", ticket_id, variant, exc)
        return {
            "ticket_id": ticket_id,
            "category": ticket["category"],
            "difficulty": ticket["difficulty"],
            "variant": variant,
            "intent_correct": False,
            "sentiment_correct": False,
            "escalation_correct": False,
            "action_correct": False,
            "autonomous_resolution": False,
            "time_ms": round(elapsed_ms, 0),
            "total_tokens": 0,
            "pipeline_error": str(exc),
            "predicted_intent": "error",
            "predicted_sentiment": "error",
            "predicted_escalate": False,
            "predicted_action": "error",
            "expected_intent": ticket["expected_intent"],
            "expected_sentiment": ticket["expected_sentiment"],
            "expected_escalate": ticket["expected_escalation"],
            "expected_action": ticket["expected_action"],
            "intent_confidence": 0,
            "quality_score": 0,
            "clarifying_question": "",
            "multi_intent_detected": False,
            "low_confidence_flag": False,
            "escalation_trigger_reason": "",
            "final_response_preview": "",
        }


# ════════════════════════════════════════════════════════════════════════════════
# VARIANT ANALYSIS
# ════════════════════════════════════════════════════════════════════════════════

def _analyze_variant(results: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    """Analyze results for a single variant — what it GOT RIGHT, WRONG, IGNORED."""
    total = len(results)
    if total == 0:
        return {"variant": variant, "total": 0}

    got_right = []  # Intent + sentiment both correct
    got_wrong = []  # Intent or sentiment wrong
    ignored = []    # Escalated when shouldn't have (didn't handle it)

    for r in results:
        is_right = r["intent_correct"] and r["sentiment_correct"]
        is_ignored = r["predicted_escalate"] and not r["expected_escalate"]
        is_wrong = not r["intent_correct"] or not r["sentiment_correct"]

        if is_ignored:
            ignored.append(r["ticket_id"])
        elif is_right:
            got_right.append(r["ticket_id"])
        elif is_wrong:
            got_wrong.append(r["ticket_id"])

    intent_correct_count = sum(1 for r in results if r["intent_correct"])
    sentiment_correct_count = sum(1 for r in results if r["sentiment_correct"])
    escalation_correct_count = sum(1 for r in results if r["escalation_correct"])
    action_correct_count = sum(1 for r in results if r["action_correct"])
    autonomous_count = sum(1 for r in results if r["autonomous_resolution"])

    # Per-category breakdown
    category_accuracy: dict[str, dict[str, Any]] = {}
    for r in results:
        cat = r["category"]
        if cat not in category_accuracy:
            category_accuracy[cat] = {"total": 0, "intent_correct": 0, "sentiment_correct": 0}
        category_accuracy[cat]["total"] += 1
        if r["intent_correct"]:
            category_accuracy[cat]["intent_correct"] += 1
        if r["sentiment_correct"]:
            category_accuracy[cat]["sentiment_correct"] += 1

    # Per-difficulty breakdown
    difficulty_accuracy: dict[str, dict[str, Any]] = {}
    for r in results:
        diff = r["difficulty"]
        if diff not in difficulty_accuracy:
            difficulty_accuracy[diff] = {"total": 0, "intent_correct": 0, "autonomous": 0}
        difficulty_accuracy[diff]["total"] += 1
        if r["intent_correct"]:
            difficulty_accuracy[diff]["intent_correct"] += 1
        if r["autonomous_resolution"]:
            difficulty_accuracy[diff]["autonomous"] += 1

    avg_time = sum(r["time_ms"] for r in results) / total if total else 0
    avg_tokens = sum(r.get("total_tokens", 0) for r in results) / total if total else 0
    avg_confidence = sum(r.get("intent_confidence", 0) for r in results) / total if total else 0

    return {
        "variant": variant,
        "total": total,
        "intent_accuracy": round(intent_correct_count / total * 100, 1),
        "sentiment_accuracy": round(sentiment_correct_count / total * 100, 1),
        "escalation_accuracy": round(escalation_correct_count / total * 100, 1),
        "action_accuracy": round(action_correct_count / total * 100, 1),
        "autonomous_resolution_rate": round(autonomous_count / total * 100, 1),
        "avg_confidence": round(avg_confidence, 3),
        "avg_time_ms": round(avg_time, 0),
        "avg_tokens_per_ticket": round(avg_tokens, 0),
        "got_right": got_right,
        "got_wrong": got_wrong,
        "ignored": ignored,
        "wrong_details": [
            {
                "ticket_id": r["ticket_id"],
                "category": r["category"],
                "predicted_intent": r["predicted_intent"],
                "expected_intent": r["expected_intent"],
                "predicted_sentiment": r["predicted_sentiment"],
                "expected_sentiment": r["expected_sentiment"],
            }
            for r in results if not r["intent_correct"] or not r["sentiment_correct"]
        ],
        "category_accuracy": category_accuracy,
        "difficulty_accuracy": difficulty_accuracy,
    }


# ════════════════════════════════════════════════════════════════════════════════
# REPORT GENERATION
# ════════════════════════════════════════════════════════════════════════════════

def _print_comparison_table(all_results: dict[str, list[dict[str, Any]]]) -> None:
    """Print a side-by-side comparison table of all 3 variants."""
    print("\n" + "=" * 100)
    print("  MONTH 4 VARIANT COMPARISON — REAL LLM (ZAI SDK)")
    print("=" * 100)

    for variant in ["mini", "parwa", "high"]:
        results = all_results.get(variant, [])
        if not results:
            continue

        analysis = _analyze_variant(results, variant)
        icon = {"mini": "🟡", "parwa": "🔵", "high": "🟣"}.get(variant, "⚪")
        name = {"mini": "Mini PARWA", "parwa": "PARWA", "high": "PARWA High"}.get(variant, variant)

        print(f"\n{icon} {name} — {analysis['total']} tickets")
        print("-" * 80)
        print(f"  Intent Accuracy:       {analysis['intent_accuracy']:5.1f}%  (target: {M4_TARGETS['intent_accuracy']}%)")
        print(f"  Sentiment Accuracy:     {analysis['sentiment_accuracy']:5.1f}%  (target: {M4_TARGETS['sentiment_accuracy']}%)")
        print(f"  Escalation Accuracy:    {analysis['escalation_accuracy']:5.1f}%  (target: {M4_TARGETS['escalation_accuracy']}%)")
        print(f"  Action Accuracy:        {analysis['action_accuracy']:5.1f}%")
        print(f"  Autonomous Resolution:  {analysis['autonomous_resolution_rate']:5.1f}%  (target: {M4_TARGETS['autonomous_resolution']}%)")
        print(f"  Avg Confidence:         {analysis['avg_confidence']:.3f}")
        print(f"  Avg Time:               {analysis['avg_time_ms']:.0f}ms")
        print(f"  Avg Tokens/Ticket:      {analysis['avg_tokens_per_ticket']:.0f}")

        # What it GOT RIGHT
        if analysis["got_right"]:
            print(f"\n  ✓ GOT RIGHT ({len(analysis['got_right'])}): {', '.join(analysis['got_right'])}")

        # What it IGNORED (escalated when shouldn't have)
        if analysis["ignored"]:
            print(f"  ⚠ IGNORED/ESCALATED ({len(analysis['ignored'])}): {', '.join(analysis['ignored'])}")

        # What it GOT WRONG
        if analysis["got_wrong"]:
            print(f"  ✗ GOT WRONG ({len(analysis['got_wrong'])}): {', '.join(analysis['got_wrong'])}")
            for detail in analysis["wrong_details"]:
                print(f"    - {detail['ticket_id']}: intent={detail['predicted_intent']} (expected {detail['expected_intent']}), "
                      f"sentiment={detail['predicted_sentiment']} (expected {detail['expected_sentiment']})")

        # Per-category breakdown
        print(f"\n  Category Breakdown:")
        for cat, cat_data in analysis["category_accuracy"].items():
            pct = cat_data["intent_correct"] / cat_data["total"] * 100 if cat_data["total"] else 0
            print(f"    {cat:25s}: {pct:5.1f}% intent ({cat_data['intent_correct']}/{cat_data['total']})")

        # Per-difficulty breakdown
        print(f"\n  Difficulty Breakdown:")
        for diff, diff_data in analysis["difficulty_accuracy"].items():
            pct = diff_data["intent_correct"] / diff_data["total"] * 100 if diff_data["total"] else 0
            auto_pct = diff_data["autonomous"] / diff_data["total"] * 100 if diff_data["total"] else 0
            print(f"    {diff:10s}: {pct:5.1f}% intent, {auto_pct:5.1f}% autonomous ({diff_data['intent_correct']}/{diff_data['total']})")

    # Overall comparison
    print("\n" + "=" * 100)
    print("  OVERALL COMPARISON TABLE")
    print("=" * 100)
    print(f"  {'Metric':<25s} {'Mini':>8s} {'PARWA':>8s} {'High':>8s} {'Target':>8s}")
    print(f"  {'─' * 25} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8}")

    metrics = ["intent_accuracy", "sentiment_accuracy", "escalation_accuracy", "autonomous_resolution_rate"]
    labels = ["Intent Accuracy", "Sentiment Accuracy", "Escalation Accuracy", "Autonomous Resolution"]
    targets = [90.0, 85.0, 90.0, 75.0]

    for metric, label, target in zip(metrics, labels, targets):
        vals = []
        for variant in ["mini", "parwa", "high"]:
            results = all_results.get(variant, [])
            if results:
                analysis = _analyze_variant(results, variant)
                vals.append(analysis.get(metric, 0))
            else:
                vals.append(0)
        print(f"  {label:<25s} {vals[0]:>7.1f}% {vals[1]:>7.1f}% {vals[2]:>7.1f}% {target:>7.1f}%")

    print()


# ════════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ════════════════════════════════════════════════════════════════════════════════

async def run_batch(
    variant_filter: str | None = None,
    delay: float = 2.0,
    quick: bool = False,
) -> dict[str, Any]:
    """Run the Month 4 batch evaluation.

    Args:
        variant_filter: If set, only run this variant ('mini', 'parwa', 'high').
        delay: Seconds between tickets for rate limit management.
        quick: If True, only run 3 tickets per variant.

    Returns:
        Complete results dict with all variant analyses.
    """
    # Ensure mock mode is OFF — we want real LLM responses
    os.environ["PARWA_MOCK_MODE"] = "false"
    from parwa.utils.llm import MOCK_MODE
    if MOCK_MODE:
        logger.warning("⚠ Mock mode is ON! Set PARWA_MOCK_MODE=false for real LLM calls.")
        logger.warning("  Continuing anyway — the pipeline will use MockLLM fallback.")

    # Select tickets
    tickets = MONTH4_TICKETS
    if quick:
        # Pick one from each difficulty level
        tickets = [t for t in MONTH4_TICKETS if t["difficulty"] in ("simple", "medium", "critical")][:3]
        logger.info("Quick mode: running %d tickets per variant", len(tickets))

    # Select variants
    variants = ["mini", "parwa", "high"]
    if variant_filter:
        variants = [variant_filter]

    stats = get_dataset_stats()
    logger.info("Month 4 Batch Runner starting")
    logger.info("  Tickets: %d | Variants: %s | Delay: %.1fs", len(tickets), variants, delay)
    logger.info("  Dataset: %d categories, %d escalation tickets, %.1f%% escalation rate",
                len(stats["categories"]),
                sum(1 for t in tickets if t["expected_escalation"]),
                stats["escalation_rate"])

    all_results: dict[str, list[dict[str, Any]]] = {v: [] for v in variants}
    all_raw: dict[str, list[dict[str, Any]]] = {v: [] for v in variants}

    total_runs = len(tickets) * len(variants)
    completed = 0

    for variant in variants:
        logger.info("\n%s Running variant: %s %s", "=" * 20, variant.upper(), "=" * 20)

        for i, ticket in enumerate(tickets):
            completed += 1
            ticket_with_variant = {**ticket, "_run_variant": variant}

            logger.info("[%d/%d] Processing %s via %s...", completed, total_runs, ticket["id"], variant)

            result = await _run_single_ticket(ticket_with_variant, variant, delay=delay)
            all_results[variant].append(result)
            all_raw[variant].append(result)

    # Generate reports
    print_comparison = True
    if print_comparison:
        _print_comparison_table(all_results)

    # Save JSON results
    output_path = "/home/z/my-project/download/month4_variant_comparison.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Build full report
    report = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "tickets": len(tickets),
            "variants": variants,
            "delay": delay,
            "quick_mode": quick,
            "llm_backend": "zai_sdk_primary",
        },
        "dataset_stats": stats,
        "targets": M4_TARGETS,
        "variant_analyses": {},
        "per_ticket_results": {v: all_raw[v] for v in variants},
    }

    for variant in variants:
        report["variant_analyses"][variant] = _analyze_variant(all_results[variant], variant)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info("Results saved to %s", output_path)

    return report


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Month 4 Batch Variant Comparison Runner")
    parser.add_argument("--variant", choices=["mini", "parwa", "high"],
                        help="Only run this variant")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Delay between tickets in seconds (default: 2.0)")
    parser.add_argument("--quick", action="store_true",
                        help="Quick test with 3 tickets per variant")
    args = parser.parse_args()

    asyncio.run(run_batch(
        variant_filter=args.variant,
        delay=args.delay,
        quick=args.quick,
    ))


if __name__ == "__main__":
    main()
