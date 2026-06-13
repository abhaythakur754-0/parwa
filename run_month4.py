#!/usr/bin/env python3
"""Fast Month 4 batch runner — runs 15 tickets x 3 variants with NVIDIA primary."""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PARWA_MOCK_MODE"] = "false"

from parwa.eval.month4_tickets import MONTH4_TICKETS


def _norm_enum(val):
    """Normalize enum values like SentimentType.NEUTRAL -> neutral."""
    s = str(val).lower()
    for prefix in ("sentimenttype.", "intenttype."):
        s = s.replace(prefix, "")
    if "." in s:
        s = s.split(".")[-1]
    return s


async def run_all(variants=("mini", "parwa", "high"), delay=0.3):
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm

    all_results = {v: [] for v in variants}
    total = len(MONTH4_TICKETS) * len(variants)
    done = 0

    for variant in variants:
        print(f"\n{'='*60}")
        print(f"  VARIANT: {variant.upper()}")
        print(f"{'='*60}")

        for ticket in MONTH4_TICKETS:
            done += 1
            tid = ticket["id"]

            # Reset for clean state
            reset_parwa_graph()
            reset_crm()

            # Small delay for rate limiting (sliding window handles most of it)
            if delay > 0:
                await asyncio.sleep(delay)

            start = time.time()
            try:
                result = await aprocess_ticket(
                    raw_message=ticket["message"],
                    customer_id=ticket["customer_id"],
                    channel="email",
                    variant=variant,
                )
                elapsed = time.time() - start

                pred_intent = _norm_enum(result.get("intent", "?"))
                pred_sentiment = _norm_enum(result.get("sentiment", "?"))
                pred_escalate = bool(result.get("should_escalate", False))
                confidence = result.get("intent_confidence", 0)
                quality = result.get("quality_score", 0)
                response = str(result.get("final_response", ""))[:150]

                exp_intent = ticket["expected_intent"].lower()
                exp_sentiment = ticket["expected_sentiment"].lower()
                exp_escalate = ticket["expected_escalation"]

                intent_ok = pred_intent == exp_intent or exp_intent in pred_intent
                sent_ok = pred_sentiment == exp_sentiment
                esc_ok = pred_escalate == exp_escalate

                i_icon = "✓" if intent_ok else "✗"
                s_icon = "✓" if sent_ok else "✗"
                e_icon = "✓" if esc_ok else "✗"

                all_results[variant].append({
                    "ticket_id": tid,
                    "category": ticket["category"],
                    "difficulty": ticket["difficulty"],
                    "intent_correct": intent_ok,
                    "sentiment_correct": sent_ok,
                    "escalation_correct": esc_ok,
                    "predicted_intent": pred_intent,
                    "expected_intent": exp_intent,
                    "predicted_sentiment": pred_sentiment,
                    "expected_sentiment": exp_sentiment,
                    "predicted_escalate": pred_escalate,
                    "expected_escalate": exp_escalate,
                    "confidence": confidence,
                    "quality_score": quality,
                    "time_s": round(elapsed, 1),
                    "response_preview": response,
                    "error": None,
                })

                print(f"  [{done:2d}/{total}] {tid:7s} | I:{i_icon} S:{s_icon} E:{e_icon} | "
                      f"intent={pred_intent:20s} sent={pred_sentiment:12s} esc={str(pred_escalate):5s} | "
                      f"{elapsed:.1f}s  conf={confidence:.2f}")

            except Exception as exc:
                elapsed = time.time() - start
                all_results[variant].append({
                    "ticket_id": tid,
                    "category": ticket["category"],
                    "difficulty": ticket["difficulty"],
                    "intent_correct": False,
                    "sentiment_correct": False,
                    "escalation_correct": False,
                    "predicted_intent": "error",
                    "expected_intent": ticket["expected_intent"].lower(),
                    "predicted_sentiment": "error",
                    "expected_sentiment": ticket["expected_sentiment"].lower(),
                    "predicted_escalate": False,
                    "expected_escalate": ticket["expected_escalation"],
                    "confidence": 0,
                    "quality_score": 0,
                    "time_s": round(elapsed, 1),
                    "response_preview": "",
                    "error": str(exc),
                })
                print(f"  [{done:2d}/{total}] {tid:7s} | ERROR: {exc}")

    # ─── ANALYSIS ───
    print("\n" + "=" * 100)
    print("  MONTH 4 VARIANT COMPARISON — BUDGET REMOVED, NVIDIA PRIMARY")
    print("=" * 100)

    summary = {}
    for variant in variants:
        results = all_results[variant]
        total_t = len(results)
        if total_t == 0:
            continue

        intent_acc = sum(1 for r in results if r["intent_correct"]) / total_t * 100
        sent_acc = sum(1 for r in results if r["sentiment_correct"]) / total_t * 100
        esc_acc = sum(1 for r in results if r["escalation_correct"]) / total_t * 100
        auto_res = sum(1 for r in results if not r["predicted_escalate"] and not r["expected_escalate"]) / total_t * 100
        avg_time = sum(r["time_s"] for r in results) / total_t
        avg_conf = sum(r["confidence"] for r in results) / total_t

        got_right = [r["ticket_id"] for r in results if r["intent_correct"] and r["sentiment_correct"]]
        got_wrong = [r["ticket_id"] for r in results if not r["intent_correct"] or not r["sentiment_correct"]]
        ignored = [r["ticket_id"] for r in results if r["predicted_escalate"] and not r["expected_escalate"]]

        wrong_details = []
        for r in results:
            if not r["intent_correct"] or not r["sentiment_correct"]:
                wrong_details.append(f"    {r['ticket_id']}: intent={r['predicted_intent']} (exp:{r['expected_intent']}), "
                                     f"sent={r['predicted_sentiment']} (exp:{r['expected_sentiment']})")

        summary[variant] = {
            "intent_accuracy": round(intent_acc, 1),
            "sentiment_accuracy": round(sent_acc, 1),
            "escalation_accuracy": round(esc_acc, 1),
            "autonomous_resolution": round(auto_res, 1),
            "avg_time_s": round(avg_time, 1),
            "avg_confidence": round(avg_conf, 3),
            "got_right": got_right,
            "got_wrong": got_wrong,
            "ignored": ignored,
            "wrong_details": wrong_details,
        }

        icon = {"mini": "🟡", "parwa": "🔵", "high": "🟣"}.get(variant, "⚪")
        print(f"\n{icon} {variant.upper()} — {total_t} tickets")
        print("-" * 80)
        print(f"  Intent Accuracy:       {intent_acc:5.1f}%  (target: 90%)")
        print(f"  Sentiment Accuracy:     {sent_acc:5.1f}%  (target: 85%)")
        print(f"  Escalation Accuracy:    {esc_acc:5.1f}%  (target: 90%)")
        print(f"  Autonomous Resolution:  {auto_res:5.1f}%  (target: 75%)")
        print(f"  Avg Confidence:         {avg_conf:.3f}")
        print(f"  Avg Time:               {avg_time:.1f}s")

        if got_right:
            print(f"\n  ✓ GOT RIGHT ({len(got_right)}): {', '.join(got_right)}")
        if ignored:
            print(f"  ⚠ IGNORED/ESCALATED ({len(ignored)}): {', '.join(ignored)}")
        if got_wrong:
            print(f"  ✗ GOT WRONG ({len(got_wrong)}): {', '.join(got_wrong)}")
            for d in wrong_details:
                print(d)

    # Overall comparison table
    print("\n" + "=" * 100)
    print("  OVERALL COMPARISON TABLE")
    print("=" * 100)
    print(f"  {'Metric':<25s} {'Mini':>8s} {'PARWA':>8s} {'High':>8s} {'Target':>8s}")
    print(f"  {'─'*25} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")

    targets = [90.0, 85.0, 90.0, 75.0]
    metrics = ["intent_accuracy", "sentiment_accuracy", "escalation_accuracy", "autonomous_resolution"]
    labels = ["Intent Accuracy", "Sentiment Accuracy", "Escalation Accuracy", "Autonomous Resolution"]

    for label, metric, target in zip(labels, metrics, targets):
        vals = [summary.get(v, {}).get(metric, 0) for v in variants]
        print(f"  {label:<25s} {vals[0]:>7.1f}% {vals[1]:>7.1f}% {vals[2]:>7.1f}% {target:>7.1f}%")

    # Overall accuracy (all 3 correct)
    print(f"\n  {'─'*25} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
    for variant in variants:
        results = all_results[variant]
        total_t = len(results)
        all_correct = sum(1 for r in results if r["intent_correct"] and r["sentiment_correct"] and r["escalation_correct"])
        pct = all_correct / total_t * 100 if total_t else 0
        print(f"  {variant.upper()+' Overall':<25s} {pct:>7.1f}%")

    # Save JSON
    output_path = "/home/z/my-project/download/month4_variant_comparison.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    report = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "tickets": len(MONTH4_TICKETS),
            "variants": list(variants),
            "delay": delay,
            "llm_backend": "nvidia_primary_zai_fallback",
            "budget_removed": True,
        },
        "summary": summary,
        "per_ticket_results": {v: all_results[v] for v in variants},
    }

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nResults saved to {output_path}")
    return report


if __name__ == "__main__":
    asyncio.run(run_all())
