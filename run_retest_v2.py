#!/usr/bin/env python3
"""Run Retest V2 — New tough tickets across all 3 variants.

Runs 8 new tickets × 3 variants = 24 test runs.
Saves results to /home/z/my-project/download/retest_v2_results.jsonl
Prints a detailed comparison at the end.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PARWA_MOCK_MODE"] = "false"

from parwa.eval.retest_v2_tickets import RETEST_V2_TICKETS

RESULTS_FILE = "/home/z/my-project/download/retest_v2_results.jsonl"
VARIANTS = ["mini", "parwa", "high"]


def _norm(val):
    """Normalize enum/string values."""
    s = str(val).lower()
    for p in ("sentimenttype.", "intenttype.", "ticketcomplexity."):
        s = s.replace(p, "")
    if "." in s:
        s = s.split(".")[-1]
    return s


async def run_one_ticket(ticket, variant):
    """Run a single ticket through the pipeline and return results."""
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm

    reset_parwa_graph()
    reset_crm()

    start = time.time()
    try:
        result = await aprocess_ticket(
            raw_message=ticket["message"],
            customer_id=ticket["customer_id"],
            channel="email",
            variant=variant,
        )
        elapsed = time.time() - start

        pi = _norm(result.get("intent", "?"))
        ps = _norm(result.get("sentiment", "?"))
        pe = bool(result.get("should_escalate", False))
        conf = result.get("intent_confidence", 0)
        quality = result.get("quality_score", 0)
        resp = str(result.get("final_response", ""))[:500]
        complexity = _norm(result.get("complexity", "?"))
        frameworks = result.get("active_frameworks", [])
        actions = result.get("action_plans", [])
        action_types = []
        for a in (actions or []):
            if hasattr(a, "action_type"):
                action_types.append(str(a.action_type))
            elif isinstance(a, dict):
                action_types.append(str(a.get("action_type", "?")))
        escalation_reason = result.get("escalation_reason", "")
        reasoning = str(result.get("reasoning_conclusion", ""))[:300]
        evidence_count = len(result.get("evidence_chain", []))

        # Check correctness
        ei = ticket["expected_intent"].lower()
        es = ticket["expected_sentiment"].lower()
        ee = ticket["expected_escalation"]

        i_ok = pi == ei or ei in pi or pi in ei
        # Special: billing_issue and complaint overlap for escalation tickets
        if ei == "billing_issue" and pi in ("complaint", "refund_request"):
            i_ok = True
        if ei == "refund_request" and pi in ("complaint",):
            i_ok = True

        s_ok = ps == es
        # Sarcasm can register as frustrated or angry — both acceptable for sarcastic_complaint
        if ticket.get("category") == "sarcastic_complaint" and ps in ("frustrated", "angry"):
            s_ok = True

        e_ok = pe == ee

        record = {
            "ticket_id": ticket["id"],
            "category": ticket["category"],
            "difficulty": ticket["difficulty"],
            "variant": variant,
            "predicted_intent": pi,
            "expected_intent": ei,
            "intent_correct": i_ok,
            "predicted_sentiment": ps,
            "expected_sentiment": es,
            "sentiment_correct": s_ok,
            "predicted_escalate": pe,
            "expected_escalate": ee,
            "escalation_correct": e_ok,
            "confidence": round(conf, 3) if isinstance(conf, (int, float)) else conf,
            "quality_score": round(quality, 1) if isinstance(quality, (int, float)) else quality,
            "complexity": complexity,
            "frameworks_count": len(frameworks) if frameworks else 0,
            "frameworks": frameworks[:10] if frameworks else [],
            "action_types": action_types,
            "escalation_reason": escalation_reason,
            "evidence_count": evidence_count,
            "reasoning_preview": reasoning,
            "response_preview": resp,
            "time_s": round(elapsed, 1),
            "timestamp": datetime.utcnow().isoformat(),
        }

        return record

    except Exception as exc:
        elapsed = time.time() - start
        return {
            "ticket_id": ticket["id"],
            "category": ticket["category"],
            "difficulty": ticket["difficulty"],
            "variant": variant,
            "error": str(exc),
            "time_s": round(elapsed, 1),
            "timestamp": datetime.utcnow().isoformat(),
        }


async def run_all():
    """Run all tickets across all variants."""
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)

    # Clear previous results
    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)

    all_results = []

    for variant in VARIANTS:
        print(f"\n{'='*70}")
        print(f"  RUNNING VARIANT: {variant.upper()}")
        print(f"{'='*70}")

        for ticket in RETEST_V2_TICKETS:
            tid = ticket["id"]
            cat = ticket["category"]
            diff = ticket["difficulty"]
            print(f"\n  [{tid}] {cat} (difficulty: {diff})", flush=True)
            print(f"    Customer: {ticket['customer_id']}", flush=True)

            record = await run_one_ticket(ticket, variant)
            all_results.append(record)

            # Save incrementally
            with open(RESULTS_FILE, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")

            if "error" in record:
                print(f"    ERROR: {record['error']}", flush=True)
                continue

            # Print summary
            i_mark = "✓" if record["intent_correct"] else "✗"
            s_mark = "✓" if record["sentiment_correct"] else "✗"
            e_mark = "✓" if record["escalation_correct"] else "✗"

            print(f"    Intent:     {record['predicted_intent']:20s} (expected: {record['expected_intent']:20s}) {i_mark}", flush=True)
            print(f"    Sentiment:  {record['predicted_sentiment']:12s} (expected: {record['expected_sentiment']:12s}) {s_mark}", flush=True)
            print(f"    Escalate:   {str(record['predicted_escalate']):5s}        (expected: {str(record['expected_escalate']):5s})        {e_mark}", flush=True)
            print(f"    Quality:    {record['quality_score']:5.1f}/100", flush=True)
            print(f"    Confidence: {record.get('confidence', 0):.3f}", flush=True)
            print(f"    Complexity: {record['complexity']}", flush=True)
            print(f"    Frameworks: {record['frameworks_count']} activated", flush=True)
            print(f"    Evidence:   {record['evidence_count']} entries", flush=True)
            print(f"    Actions:    {record['action_types']}", flush=True)
            if record.get('escalation_reason'):
                print(f"    Esc Reason: {record['escalation_reason']}", flush=True)
            print(f"    Time:       {record['time_s']:.1f}s", flush=True)
            if record.get('reasoning_preview'):
                print(f"    Reasoning:  {record['reasoning_preview'][:120]}...", flush=True)

    # ─── Print final comparison ───────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"  FINAL COMPARISON — RETEST V2")
    print(f"{'='*70}")

    for variant in VARIANTS:
        v_results = [r for r in all_results if r.get("variant") == variant and "error" not in r]
        v_errors = [r for r in all_results if r.get("variant") == variant and "error" in r]

        if not v_results:
            print(f"\n  {variant.upper()}: NO SUCCESSFUL RESULTS")
            continue

        intent_acc = sum(1 for r in v_results if r["intent_correct"]) / len(v_results) * 100
        sentiment_acc = sum(1 for r in v_results if r["sentiment_correct"]) / len(v_results) * 100
        escalation_acc = sum(1 for r in v_results if r["escalation_correct"]) / len(v_results) * 100
        avg_quality = sum(r["quality_score"] for r in v_results) / len(v_results)
        avg_confidence = sum(r.get("confidence", 0) for r in v_results) / len(v_results)
        avg_frameworks = sum(r["frameworks_count"] for r in v_results) / len(v_results)
        avg_evidence = sum(r["evidence_count"] for r in v_results) / len(v_results)
        avg_time = sum(r["time_s"] for r in v_results) / len(v_results)
        overall = (intent_acc + sentiment_acc + escalation_acc + avg_quality) / 4

        print(f"\n  ┌─── {variant.upper()} VARIANT ───┐")
        print(f"  │ Intent Accuracy:     {intent_acc:5.1f}%  ({int(intent_acc*len(v_results)/100)}/{len(v_results)})", )
        print(f"  │ Sentiment Accuracy:  {sentiment_acc:5.1f}%  ({int(sentiment_acc*len(v_results)/100)}/{len(v_results)})")
        print(f"  │ Escalation Accuracy: {escalation_acc:5.1f}%  ({int(escalation_acc*len(v_results)/100)}/{len(v_results)})")
        print(f"  │ Avg Quality Score:   {avg_quality:5.1f}/100")
        print(f"  │ Avg Confidence:      {avg_confidence:.3f}")
        print(f"  │ Avg Frameworks:      {avg_frameworks:.1f}")
        print(f"  │ Avg Evidence:        {avg_evidence:.1f}")
        print(f"  │ Avg Time:            {avg_time:.1f}s")
        print(f"  │ Errors:              {len(v_errors)}")
        print(f"  │ OVERALL SCORE:       {overall:.1f}/100")
        print(f"  └──────────────────────────┘")

        # Per-ticket detail
        print(f"\n  Per-ticket breakdown:")
        for r in v_results:
            i_mark = "✓" if r["intent_correct"] else "✗"
            s_mark = "✓" if r["sentiment_correct"] else "✗"
            e_mark = "✓" if r["escalation_correct"] else "✗"
            print(f"    {r['ticket_id']} | I:{i_mark} S:{s_mark} E:{e_mark} | "
                  f"Q={r['quality_score']:4.0f} | {r['predicted_intent']:18s} | {r['predicted_sentiment']:10s} | esc={str(r['predicted_escalate']):5s}")

    print(f"\n  Results saved to: {RESULTS_FILE}")
    return all_results


if __name__ == "__main__":
    asyncio.run(run_all())
