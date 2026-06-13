#!/usr/bin/env python3
"""Month 4 Variant Comparison Runner — PARWA Real Evaluation Framework.

Processes all 15 Month 4 tickets through ALL 3 variants (mini, parwa, high)
and generates a detailed comparison report showing what each variant handles,
misses, and gets wrong.

Month 4 targets (from roadmap):
- Intent accuracy: 90%+ (up from 80% Month 2)
- Sentiment accuracy: 85%+ (up from 75% Month 2)
- Escalation accuracy: 90%+ (up from 80% Month 2)
- Autonomous resolution: 75%+ (up from 55% Month 2)

Usage:
    python -m parwa.eval.month4_runner                           # Full run (15 tickets x 3 variants = 45 calls)
    python -m parwa.eval.month4_runner --quick                   # Quick test (3 tickets x 3 variants = 9 calls)
    python -m parwa.eval.month4_runner --ticket M4-005           # Single ticket through all variants
    python -m parwa.eval.month4_runner --variant mini            # All tickets through one variant only
    python -m parwa.eval.month4_runner --delay 2.0               # Custom delay between API calls
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
logger = logging.getLogger("parwa.eval.month4_runner")


# ════════════════════════════════════════════════════════════════════════════════
# MONTH 4 TARGETS
# ════════════════════════════════════════════════════════════════════════════════

MONTH4_TARGETS = {
    "intent_accuracy": 90,
    "sentiment_accuracy": 85,
    "escalation_accuracy": 90,
    "autonomous_resolution": 75,
}

ALL_VARIANTS = ["mini", "parwa", "high"]

# Output path for results
RESULTS_PATH = "/home/z/my-project/download/month4_variant_test_results.json"


# ════════════════════════════════════════════════════════════════════════════════
# SENTIMENT MATCHING — allow close alternatives
# ════════════════════════════════════════════════════════════════════════════════

# Some sentiment confusion is expected; these are considered "close enough"
SENTIMENT_ALT_MAP: dict[str, list[str]] = {
    "angry": ["frustrated"],
    "frustrated": ["angry"],
    "neutral": [],
    "happy": [],
}


def _sentiment_match(actual: str, expected: str, strict: bool = False) -> bool:
    """Check if actual sentiment matches expected, with optional fuzzy matching.

    In strict mode, exact match only.
    In fuzzy mode (default), angry<->frustrated are considered equivalent.
    """
    if actual == expected:
        return True
    if not strict:
        alts = SENTIMENT_ALT_MAP.get(expected, [])
        if actual in alts:
            return True
    return False


# ════════════════════════════════════════════════════════════════════════════════
# TICKET PROCESSING
# ════════════════════════════════════════════════════════════════════════════════

async def process_ticket_through_variant(
    ticket: dict[str, Any],
    variant: str,
    delay: float = 1.0,
) -> dict[str, Any]:
    """Process a single ticket through one variant and record all results.

    Args:
        ticket: The ticket dict from MONTH4_TICKETS
        variant: One of 'mini', 'parwa', 'high'
        delay: Seconds to wait before processing (for rate limiting)

    Returns:
        Dict with all recorded metrics
    """
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm

    # Reset state for clean run
    reset_parwa_graph()
    reset_crm()

    # Wait for rate limiting
    if delay > 0:
        await asyncio.sleep(delay)

    ticket_id = ticket["id"]
    message = ticket["message"]
    customer_id = ticket["customer_id"]

    logger.info("Processing %s via %s variant (customer: %s)", ticket_id, variant, customer_id)

    start_time = time.time()
    try:
        result = await aprocess_ticket(
            raw_message=message,
            customer_id=customer_id,
            channel="email",
            variant=variant,
        )
        elapsed = time.time() - start_time
        error = None
    except Exception as exc:
        elapsed = time.time() - start_time
        result = {}
        error = str(exc)
        logger.error("Error processing %s via %s: %s", ticket_id, variant, exc)

    # Extract results
    actual_intent = result.get("intent", "unknown")
    actual_sentiment = result.get("sentiment", "unknown")
    actual_escalation = result.get("should_escalate", False)
    quality_score = result.get("quality_score", 0)
    final_response = result.get("final_response", "")
    actions_taken = result.get("actions", [])
    nodes_traversed = result.get("nodes_traversed", [])
    complexity = result.get("complexity", "unknown")

    # If actions_taken are dicts, extract action types
    if actions_taken and isinstance(actions_taken[0], dict):
        action_types = [a.get("action_type", str(a)) for a in actions_taken]
    else:
        action_types = [str(a) for a in actions_taken]

    # Compare against expected
    expected_intent = ticket["expected_intent"]
    expected_sentiment = ticket["expected_sentiment"]
    expected_escalation = ticket["expected_escalation"]
    expected_action = ticket["expected_action"]

    intent_match = actual_intent == expected_intent
    sentiment_match = _sentiment_match(actual_sentiment, expected_sentiment)
    escalation_match = actual_escalation == expected_escalation

    # Action match — check if expected action appears in the actions taken
    action_match = expected_action in action_types if action_types else False
    # Also check partial matches (e.g., "process_refund" might appear as "recommend:process_refund")
    if not action_match and action_types:
        action_match = any(expected_action in str(a) for a in action_types)

    return {
        "ticket_id": ticket_id,
        "variant": variant,
        "customer_id": customer_id,
        "category": ticket["category"],
        "difficulty": ticket["difficulty"],
        # Expected values
        "expected_intent": expected_intent,
        "expected_sentiment": expected_sentiment,
        "expected_escalation": expected_escalation,
        "expected_action": expected_action,
        # Actual values
        "actual_intent": actual_intent,
        "actual_sentiment": actual_sentiment,
        "actual_escalation": actual_escalation,
        "actual_actions": action_types,
        "quality_score": quality_score,
        "complexity": complexity,
        "final_response_length": len(final_response),
        "final_response_preview": final_response[:300] if final_response else "",
        "nodes_traversed": nodes_traversed if isinstance(nodes_traversed, list) else list(nodes_traversed) if nodes_traversed else [],
        # Match results
        "intent_match": intent_match,
        "sentiment_match": sentiment_match,
        "escalation_match": escalation_match,
        "action_match": action_match,
        # Timing
        "elapsed_seconds": round(elapsed, 2),
        # Errors
        "error": error,
    }


async def run_all_tickets(
    tickets: list[dict[str, Any]],
    variants: list[str] | None = None,
    delay: float = 1.0,
) -> list[dict[str, Any]]:
    """Process all tickets through all specified variants.

    Processes sequentially (not in parallel) to respect rate limits.
    Adds increasing delay between calls to avoid rate limiting.

    Args:
        tickets: List of ticket dicts from MONTH4_TICKETS
        variants: List of variants to test (default: all 3)
        delay: Base delay between API calls in seconds

    Returns:
        List of result dicts, one per ticket-variant combination
    """
    if variants is None:
        variants = ALL_VARIANTS

    all_results: list[dict[str, Any]] = []
    total_calls = len(tickets) * len(variants)
    call_count = 0

    logger.info("Starting Month 4 evaluation: %d tickets x %d variants = %d calls",
                len(tickets), len(variants), total_calls)

    for ticket in tickets:
        for variant in variants:
            call_count += 1
            # Progressive delay: longer waits as we go to avoid rate limits
            progressive_delay = delay + (0.1 * (call_count // 10))

            result = await process_ticket_through_variant(
                ticket=ticket,
                variant=variant,
                delay=progressive_delay,
            )
            all_results.append(result)

            # Log progress
            intent_ok = "OK" if result["intent_match"] else "MISS"
            sent_ok = "OK" if result["sentiment_match"] else "MISS"
            esc_ok = "OK" if result["escalation_match"] else "MISS"
            logger.info(
                "  [%d/%d] %s/%s: intent=%s sent=%s esc=%s q=%.0f (%.1fs)",
                call_count, total_calls,
                result["ticket_id"], variant,
                intent_ok, sent_ok, esc_ok,
                result["quality_score"],
                result["elapsed_seconds"],
            )

    return all_results


# ════════════════════════════════════════════════════════════════════════════════
# ANALYSIS & REPORTING
# ════════════════════════════════════════════════════════════════════════════════

def compute_variant_metrics(results: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    """Compute all metrics for a single variant from results."""
    variant_results = [r for r in results if r["variant"] == variant]
    if not variant_results:
        return {"variant": variant, "total": 0}

    total = len(variant_results)
    intent_correct = sum(1 for r in variant_results if r["intent_match"])
    sentiment_correct = sum(1 for r in variant_results if r["sentiment_match"])
    escalation_correct = sum(1 for r in variant_results if r["escalation_match"])
    action_correct = sum(1 for r in variant_results if r["action_match"])
    errors = sum(1 for r in variant_results if r.get("error"))

    # Quality scores
    quality_scores = [r["quality_score"] for r in variant_results if r["quality_score"] is not None]
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

    # Timing
    elapsed_times = [r["elapsed_seconds"] for r in variant_results]
    avg_elapsed = sum(elapsed_times) / len(elapsed_times) if elapsed_times else 0

    # Per-category accuracy
    categories: dict[str, dict] = {}
    for r in variant_results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "intent_correct": 0, "sentiment_correct": 0,
                               "escalation_correct": 0, "action_correct": 0}
        categories[cat]["total"] += 1
        if r["intent_match"]:
            categories[cat]["intent_correct"] += 1
        if r["sentiment_match"]:
            categories[cat]["sentiment_correct"] += 1
        if r["escalation_match"]:
            categories[cat]["escalation_correct"] += 1
        if r["action_match"]:
            categories[cat]["action_correct"] += 1

    # Per-difficulty accuracy
    difficulties: dict[str, dict] = {}
    for r in variant_results:
        diff = r["difficulty"]
        if diff not in difficulties:
            difficulties[diff] = {"total": 0, "intent_correct": 0, "sentiment_correct": 0,
                                  "escalation_correct": 0}
        difficulties[diff]["total"] += 1
        if r["intent_match"]:
            difficulties[diff]["intent_correct"] += 1
        if r["sentiment_match"]:
            difficulties[diff]["sentiment_correct"] += 1
        if r["escalation_match"]:
            difficulties[diff]["escalation_correct"] += 1

    return {
        "variant": variant,
        "total_tickets": total,
        "intent_accuracy": round(intent_correct / total * 100, 1) if total else 0,
        "sentiment_accuracy": round(sentiment_correct / total * 100, 1) if total else 0,
        "escalation_accuracy": round(escalation_correct / total * 100, 1) if total else 0,
        "action_accuracy": round(action_correct / total * 100, 1) if total else 0,
        "avg_quality_score": round(avg_quality, 1),
        "avg_elapsed_seconds": round(avg_elapsed, 2),
        "errors": errors,
        "categories": categories,
        "difficulties": difficulties,
    }


def compute_variant_comparison(all_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare what each variant handles vs misses."""
    comparison: dict[str, Any] = {
        "mini_misses_parwa_gets": [],   # Tickets Mini gets wrong but Parwa gets right
        "parwa_misses_high_gets": [],   # Tickets Parwa gets wrong but High gets right
        "all_variants_wrong": [],       # Tickets ALL variants get wrong
        "all_variants_right": [],       # Tickets ALL variants get right
        "mini_only_misses": [],         # Things only Mini misses
    }

    # Group results by ticket
    ticket_results: dict[str, dict[str, dict]] = {}
    for r in all_results:
        tid = r["ticket_id"]
        variant = r["variant"]
        if tid not in ticket_results:
            ticket_results[tid] = {}
        ticket_results[tid][variant] = r

    for tid, vresults in ticket_results.items():
        mini_r = vresults.get("mini")
        parwa_r = vresults.get("parwa")
        high_r = vresults.get("high")

        # Check intent accuracy across variants
        mini_intent = mini_r["intent_match"] if mini_r else None
        parwa_intent = parwa_r["intent_match"] if parwa_r else None
        high_intent = high_r["intent_match"] if high_r else None

        mini_esc = mini_r["escalation_match"] if mini_r else None
        parwa_esc = parwa_r["escalation_match"] if parwa_r else None
        high_esc = high_r["escalation_match"] if high_r else None

        # Overall: intent AND sentiment AND escalation all match
        mini_ok = all([
            mini_r["intent_match"], mini_r["sentiment_match"], mini_r["escalation_match"]
        ]) if mini_r else False
        parwa_ok = all([
            parwa_r["intent_match"], parwa_r["sentiment_match"], parwa_r["escalation_match"]
        ]) if parwa_r else False
        high_ok = all([
            high_r["intent_match"], high_r["sentiment_match"], high_r["escalation_match"]
        ]) if high_r else False

        entry = {
            "ticket_id": tid,
            "category": vresults.get("parwa", vresults.get("mini", vresults.get("high", {}))).get("category", ""),
            "mini_intent_ok": mini_intent,
            "parwa_intent_ok": parwa_intent,
            "high_intent_ok": high_intent,
            "mini_escalation_ok": mini_esc,
            "parwa_escalation_ok": parwa_esc,
            "high_escalation_ok": high_esc,
            "mini_fully_ok": mini_ok,
            "parwa_fully_ok": parwa_ok,
            "high_fully_ok": high_ok,
        }

        if mini_ok and parwa_ok and high_ok:
            comparison["all_variants_right"].append(entry)
        elif not mini_ok and not parwa_ok and not high_ok:
            comparison["all_variants_wrong"].append(entry)
        elif not mini_ok and parwa_ok:
            comparison["mini_misses_parwa_gets"].append(entry)
        elif not parwa_ok and high_ok:
            comparison["parwa_misses_high_gets"].append(entry)

        # Mini-specific misses
        if mini_r and not mini_ok:
            mini_misses = []
            if not mini_r["intent_match"]:
                mini_misses.append(f"intent: got '{mini_r['actual_intent']}' expected '{mini_r['expected_intent']}'")
            if not mini_r["sentiment_match"]:
                mini_misses.append(f"sentiment: got '{mini_r['actual_sentiment']}' expected '{mini_r['expected_sentiment']}'")
            if not mini_r["escalation_match"]:
                mini_misses.append(f"escalation: got {mini_r['actual_escalation']} expected {mini_r['expected_escalation']}")
            comparison["mini_only_misses"].append({
                "ticket_id": tid,
                "category": mini_r["category"],
                "misses": mini_misses,
            })

    return comparison


def generate_report(
    all_results: list[dict[str, Any]],
    variant_metrics: dict[str, dict],
    comparison: dict[str, Any],
) -> str:
    """Generate a detailed text report for stdout."""

    lines: list[str] = []

    lines.append("")
    lines.append("=" * 90)
    lines.append("  PARWA Month 4 — Variant Comparison Report")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Tickets: {len(MONTH4_TICKETS)} | Variants: {', '.join(ALL_VARIANTS)}")
    lines.append(f"  Total evaluations: {len(all_results)}")
    lines.append("=" * 90)

    # ─── Per-Variant Accuracy Summary ────────────────────────────────────────
    lines.append("")
    lines.append("  PER-VARIANT ACCURACY SUMMARY")
    lines.append("  " + "-" * 86)
    lines.append(f"  {'Metric':<25} {'Mini':>10} {'Parwa':>10} {'High':>10} {'Target':>10} {'Status':>10}")
    lines.append("  " + "-" * 86)

    metrics_to_show = [
        ("Intent Accuracy", "intent_accuracy", MONTH4_TARGETS["intent_accuracy"]),
        ("Sentiment Accuracy", "sentiment_accuracy", MONTH4_TARGETS["sentiment_accuracy"]),
        ("Escalation Accuracy", "escalation_accuracy", MONTH4_TARGETS["escalation_accuracy"]),
        ("Action Accuracy", "action_accuracy", None),
        ("Avg Quality Score", "avg_quality_score", None),
        ("Avg Elapsed (s)", "avg_elapsed_seconds", None),
        ("Errors", "errors", None),
    ]

    for name, key, target in metrics_to_show:
        mini_val = variant_metrics.get("mini", {}).get(key, "N/A")
        parwa_val = variant_metrics.get("parwa", {}).get(key, "N/A")
        high_val = variant_metrics.get("high", {}).get(key, "N/A")

        if isinstance(mini_val, float):
            mini_str = f"{mini_val:.1f}"
            parwa_str = f"{parwa_val:.1f}"
            high_str = f"{high_val:.1f}"
        else:
            mini_str = str(mini_val)
            parwa_str = str(parwa_val)
            high_str = str(high_val)

        if target is not None:
            # Use the best variant (parwa or high) as the primary check
            best_val = max(
                variant_metrics.get("parwa", {}).get(key, 0),
                variant_metrics.get("high", {}).get(key, 0),
            )
            status = "PASS" if best_val >= target else "FAIL"
            target_str = f"{target}%"
        else:
            status = "-"
            target_str = "-"

        lines.append(f"  {name:<25} {mini_str:>10} {parwa_str:>10} {high_str:>10} {target_str:>10} {status:>10}")

    lines.append("  " + "-" * 86)

    # ─── Per-Ticket Comparison Table ─────────────────────────────────────────
    lines.append("")
    lines.append("  PER-TICKET COMPARISON TABLE")
    lines.append("  " + "-" * 86)
    lines.append(f"  {'Ticket':<8} {'Category':<22} {'Mini':^20} {'Parwa':^20} {'High':^20}")
    lines.append(f"  {'':8} {'':22} {'I  S  E  A':^20} {'I  S  E  A':^20} {'I  S  E  A':^20}")
    lines.append("  " + "-" * 86)

    # Group by ticket
    ticket_results: dict[str, dict[str, dict]] = {}
    for r in all_results:
        tid = r["ticket_id"]
        variant = r["variant"]
        if tid not in ticket_results:
            ticket_results[tid] = {}
        ticket_results[tid][variant] = r

    for ticket in MONTH4_TICKETS:
        tid = ticket["id"]
        cat = ticket["category"]
        vresults = ticket_results.get(tid, {})

        def _variant_str(vname: str) -> str:
            r = vresults.get(vname)
            if not r:
                return "    -    "
            if r.get("error"):
                return "  ERROR  "
            i = "+" if r["intent_match"] else "-"
            s = "+" if r["sentiment_match"] else "-"
            e = "+" if r["escalation_match"] else "-"
            a = "+" if r["action_match"] else "-"
            return f"{i}  {s}  {e}  {a}"

        mini_str = _variant_str("mini")
        parwa_str = _variant_str("parwa")
        high_str = _variant_str("high")

        lines.append(f"  {tid:<8} {cat:<22} {mini_str:^20} {parwa_str:^20} {high_str:^20}")

    lines.append("  " + "-" * 86)
    lines.append("  Legend: I=Intent  S=Sentiment  E=Escalation  A=Action  (+)=correct  (-)=incorrect")

    # ─── Variant Capability Analysis ─────────────────────────────────────────
    lines.append("")
    lines.append("  VARIANT CAPABILITY ANALYSIS")
    lines.append("  " + "-" * 86)

    # What Mini misses
    mini_misses = comparison.get("mini_misses_parwa_gets", [])
    lines.append(f"")
    lines.append(f"  Tickets Mini misses but Parwa gets right: {len(mini_misses)}")
    for entry in mini_misses:
        lines.append(f"    - {entry['ticket_id']} ({entry['category']})")

    # What Parwa misses but High gets
    parwa_misses = comparison.get("parwa_misses_high_gets", [])
    lines.append(f"")
    lines.append(f"  Tickets Parwa misses but High gets right: {len(parwa_misses)}")
    for entry in parwa_misses:
        lines.append(f"    - {entry['ticket_id']} ({entry['category']})")

    # All variants right
    all_right = comparison.get("all_variants_right", [])
    lines.append(f"")
    lines.append(f"  Tickets ALL variants get right: {len(all_right)}/{len(MONTH4_TICKETS)}")
    for entry in all_right:
        lines.append(f"    - {entry['ticket_id']} ({entry['category']})")

    # All variants wrong
    all_wrong = comparison.get("all_variants_wrong", [])
    lines.append(f"")
    lines.append(f"  Tickets ALL variants get wrong: {len(all_wrong)}/{len(MONTH4_TICKETS)}")
    for entry in all_wrong:
        lines.append(f"    - {entry['ticket_id']} ({entry['category']})")

    # Mini-specific detail
    mini_only = comparison.get("mini_only_misses", [])
    if mini_only:
        lines.append(f"")
        lines.append(f"  Mini PARWA — Specific Misses (detailed):")
        for entry in mini_only:
            lines.append(f"    {entry['ticket_id']} ({entry['category']}):")
            for miss in entry["misses"]:
                lines.append(f"      - {miss}")

    # ─── Per-Category Breakdown ──────────────────────────────────────────────
    lines.append("")
    lines.append("  PER-CATEGORY ACCURACY (Intent / Sentiment / Escalation)")
    lines.append("  " + "-" * 86)

    all_categories = sorted(set(t["category"] for t in MONTH4_TICKETS))
    lines.append(f"  {'Category':<25} {'Mini I/S/E':>15} {'Parwa I/S/E':>15} {'High I/S/E':>15}")
    lines.append("  " + "-" * 86)

    for cat in all_categories:
        row_parts = []
        for variant in ALL_VARIANTS:
            cat_data = variant_metrics.get(variant, {}).get("categories", {}).get(cat)
            if cat_data and cat_data["total"] > 0:
                i_pct = round(cat_data["intent_correct"] / cat_data["total"] * 100)
                s_pct = round(cat_data["sentiment_correct"] / cat_data["total"] * 100)
                e_pct = round(cat_data["escalation_correct"] / cat_data["total"] * 100)
                row_parts.append(f"{i_pct}/{s_pct}/{e_pct}")
            else:
                row_parts.append("-/-/-")

        lines.append(f"  {cat:<25} {row_parts[0]:>15} {row_parts[1]:>15} {row_parts[2]:>15}")

    lines.append("  " + "-" * 86)

    # ─── Per-Difficulty Breakdown ────────────────────────────────────────────
    lines.append("")
    lines.append("  PER-DIFFICULTY ACCURACY (Intent / Sentiment / Escalation)")
    lines.append("  " + "-" * 86)

    all_diffs = ["simple", "medium", "complex", "critical"]
    lines.append(f"  {'Difficulty':<25} {'Mini I/S/E':>15} {'Parwa I/S/E':>15} {'High I/S/E':>15}")
    lines.append("  " + "-" * 86)

    for diff in all_diffs:
        row_parts = []
        for variant in ALL_VARIANTS:
            diff_data = variant_metrics.get(variant, {}).get("difficulties", {}).get(diff)
            if diff_data and diff_data["total"] > 0:
                i_pct = round(diff_data["intent_correct"] / diff_data["total"] * 100)
                s_pct = round(diff_data["sentiment_correct"] / diff_data["total"] * 100)
                e_pct = round(diff_data["escalation_correct"] / diff_data["total"] * 100)
                row_parts.append(f"{i_pct}/{s_pct}/{e_pct}")
            else:
                row_parts.append("-/-/-")

        lines.append(f"  {diff:<25} {row_parts[0]:>15} {row_parts[1]:>15} {row_parts[2]:>15}")

    lines.append("  " + "-" * 86)

    # ─── Overall Quality Score ───────────────────────────────────────────────
    lines.append("")
    lines.append("  OVERALL QUALITY SCORE PER VARIANT")
    lines.append("  " + "-" * 86)

    for variant in ALL_VARIANTS:
        vm = variant_metrics.get(variant, {})
        if not vm or vm.get("total_tickets", 0) == 0:
            lines.append(f"  {variant.upper():<15} — No results")
            continue

        # Composite score: weighted average of accuracies
        intent_w = 0.35
        sentiment_w = 0.20
        escalation_w = 0.25
        action_w = 0.20

        composite = (
            vm["intent_accuracy"] * intent_w +
            vm["sentiment_accuracy"] * sentiment_w +
            vm["escalation_accuracy"] * escalation_w +
            vm["action_accuracy"] * action_w
        )

        grade = "A" if composite >= 90 else "B" if composite >= 80 else "C" if composite >= 70 else "D" if composite >= 60 else "F"

        lines.append(f"  {variant.upper():<15} Composite: {composite:.1f}/100  (Grade: {grade})")
        lines.append(f"  {'':15} Intent: {vm['intent_accuracy']:.1f}%  Sentiment: {vm['sentiment_accuracy']:.1f}%  "
                     f"Escalation: {vm['escalation_accuracy']:.1f}%  Action: {vm['action_accuracy']:.1f}%")
        lines.append(f"  {'':15} Avg Quality: {vm['avg_quality_score']:.1f}  Avg Time: {vm['avg_elapsed_seconds']:.1f}s  "
                     f"Errors: {vm.get('errors', 0)}")

    lines.append("  " + "-" * 86)

    # ─── Month 4 Target Summary ─────────────────────────────────────────────
    lines.append("")
    lines.append("=" * 90)
    lines.append("  MONTH 4 TARGETS vs ACTUALS (using PARWA variant as primary)")
    lines.append("=" * 90)

    parwa_m = variant_metrics.get("parwa", {})
    checks = [
        ("Intent Accuracy", parwa_m.get("intent_accuracy", 0), MONTH4_TARGETS["intent_accuracy"]),
        ("Sentiment Accuracy", parwa_m.get("sentiment_accuracy", 0), MONTH4_TARGETS["sentiment_accuracy"]),
        ("Escalation Accuracy", parwa_m.get("escalation_accuracy", 0), MONTH4_TARGETS["escalation_accuracy"]),
    ]

    # Autonomous resolution = tickets where intent + sentiment + escalation all match AND quality >= 70
    parwa_results = [r for r in all_results if r["variant"] == "parwa"]
    auto_resolved = sum(
        1 for r in parwa_results
        if r["intent_match"] and r["sentiment_match"] and r["escalation_match"]
        and (r["quality_score"] or 0) >= 70
    )
    auto_rate = round(auto_resolved / len(parwa_results) * 100, 1) if parwa_results else 0
    checks.append(("Autonomous Resolution", auto_rate, MONTH4_TARGETS["autonomous_resolution"]))

    all_pass = True
    for name, actual, target in checks:
        passed = actual >= target
        if not passed:
            all_pass = False
        icon = "PASS" if passed else "FAIL"
        lines.append(f"  [{icon}] {name:<30} {actual:>6.1f}% / {target}% target")

    lines.append(f"")
    lines.append(f"  Overall: {'ALL TARGETS MET' if all_pass else 'SOME TARGETS NOT MET'}")
    lines.append("=" * 90)

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

async def run_month4_evaluation(
    quick: bool = False,
    ticket_id: str | None = None,
    variant: str | None = None,
    delay: float = 1.0,
) -> bool:
    """Run the Month 4 variant comparison evaluation.

    Args:
        quick: If True, run only 3 representative tickets
        ticket_id: If set, run only this specific ticket through all variants
        variant: If set, run all tickets through only this variant
        delay: Base delay between API calls (seconds)

    Returns:
        True if all Month 4 targets are met
    """
    stats = get_dataset_stats()
    logger.info("Month 4 ticket dataset: %d tickets, %d categories, %d unique customers",
                stats["total_tickets"], len(stats["categories"]), stats["unique_customers"])

    # Select tickets
    if ticket_id:
        tickets = [t for t in MONTH4_TICKETS if t["id"] == ticket_id]
        if not tickets:
            logger.error("Ticket %s not found", ticket_id)
            return False
    elif quick:
        # Quick mode: 3 representative tickets (simple, medium, complex)
        tickets = [
            next(t for t in MONTH4_TICKETS if t["id"] == "M4-001"),   # Simple FAQ
            next(t for t in MONTH4_TICKETS if t["id"] == "M4-005"),   # Medium refund
            next(t for t in MONTH4_TICKETS if t["id"] == "M4-013"),   # Critical escalation
        ]
    else:
        tickets = MONTH4_TICKETS

    # Select variants
    variants = [variant] if variant else ALL_VARIANTS

    # Run all tickets through all variants
    all_results = await run_all_tickets(tickets, variants, delay=delay)

    # Compute metrics
    variant_metrics: dict[str, dict] = {}
    for v in variants:
        variant_metrics[v] = compute_variant_metrics(all_results, v)

    # Compute comparison
    comparison = compute_variant_comparison(all_results)

    # Generate report
    report_text = generate_report(all_results, variant_metrics, comparison)
    print(report_text)

    # Save results JSON
    output = {
        "timestamp": datetime.now().isoformat(),
        "month": 4,
        "targets": MONTH4_TARGETS,
        "dataset_stats": stats,
        "variant_metrics": variant_metrics,
        "comparison": {
            "mini_misses_parwa_gets": comparison["mini_misses_parwa_gets"],
            "parwa_misses_high_gets": comparison["parwa_misses_high_gets"],
            "all_variants_right": comparison["all_variants_right"],
            "all_variants_wrong": comparison["all_variants_wrong"],
            "mini_only_misses": comparison["mini_only_misses"],
        },
        "per_ticket_results": all_results,
        "report_text": report_text,
    }

    # Ensure output directory exists
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2, default=str)
    logger.info("Results saved to: %s", RESULTS_PATH)

    # Check targets
    parwa_m = variant_metrics.get("parwa", {})
    if parwa_m:
        all_pass = (
            parwa_m.get("intent_accuracy", 0) >= MONTH4_TARGETS["intent_accuracy"]
            and parwa_m.get("sentiment_accuracy", 0) >= MONTH4_TARGETS["sentiment_accuracy"]
            and parwa_m.get("escalation_accuracy", 0) >= MONTH4_TARGETS["escalation_accuracy"]
        )
    else:
        all_pass = False

    return all_pass


def main():
    parser = argparse.ArgumentParser(
        description="PARWA Month 4 Variant Comparison Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m parwa.eval.month4_runner                    # Full run (45 calls)
  python -m parwa.eval.month4_runner --quick             # Quick test (9 calls)
  python -m parwa.eval.month4_runner --ticket M4-005     # Single ticket
  python -m parwa.eval.month4_runner --variant mini      # Mini only
  python -m parwa.eval.month4_runner --delay 2.0         # Slower rate limiting
        """,
    )
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: only 3 representative tickets")
    parser.add_argument("--ticket", type=str, default=None,
                        help="Run a specific ticket ID (e.g., M4-005)")
    parser.add_argument("--variant", type=str, default=None,
                        choices=["mini", "parwa", "high"],
                        help="Run only through one variant")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Base delay between API calls in seconds (default: 1.0)")
    args = parser.parse_args()

    success = asyncio.run(run_month4_evaluation(
        quick=args.quick,
        ticket_id=args.ticket,
        variant=args.variant,
        delay=args.delay,
    ))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
