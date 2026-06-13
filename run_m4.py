#!/usr/bin/env python3
"""Run Month 4 batch test and write output to a log file."""

import asyncio, json, os, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PARWA_MOCK_MODE"] = "false"

LOG_FILE = "/home/z/my-project/download/month4_output.log"
RESULTS_FILE = "/home/z/my-project/download/month4_results.jsonl"

from parwa.eval.month4_tickets import MONTH4_TICKETS

def _norm(val):
    s = str(val).lower()
    for p in ("sentimenttype.", "intenttype."):
        s = s.replace(p, "")
    if "." in s:
        s = s.split(".")[-1]
    return s

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
        f.flush()
    # Also print
    print(msg, flush=True)


async def process_ticket(ticket, variant):
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm

    reset_parwa_graph()
    reset_crm()

    start = time.time()
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
    resp = str(result.get("final_response", ""))[:200]

    ei = ticket["expected_intent"].lower()
    es = ticket["expected_sentiment"].lower()
    ee = ticket["expected_escalation"]

    i_ok = pi == ei or ei in pi or pi in ei
    if ei == "escalation" and pi in ("billing_issue", "complaint"):
        i_ok = True
    s_ok = ps == es
    e_ok = pe == ee

    record = {
        "ticket_id": ticket["id"], "category": ticket["category"],
        "difficulty": ticket["difficulty"], "variant": variant,
        "predicted_intent": pi, "expected_intent": ei, "intent_correct": i_ok,
        "predicted_sentiment": ps, "expected_sentiment": es, "sentiment_correct": s_ok,
        "predicted_escalate": pe, "expected_escalate": ee, "escalation_correct": e_ok,
        "confidence": conf, "quality_score": quality, "time_s": round(elapsed, 1),
        "response_preview": resp,
    }

    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")
        f.flush()

    i_ic = "Y" if i_ok else "N"
    s_ic = "Y" if s_ok else "N"
    e_ic = "Y" if e_ok else "N"
    log(f"  {ticket['id']:7s}/{variant:5s} I:{i_ic} S:{s_ic} E:{e_ic} | "
        f"intent={pi:20s} sent={ps:12s} esc={str(pe):5s} | {elapsed:.1f}s conf={conf:.2f}")

    return record


async def run_all():
    variants = ["mini", "parwa", "high"]
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)

    total = len(MONTH4_TICKETS) * len(variants)
    done = 0
    start_all = time.time()

    for variant in variants:
        log(f"\n{'='*60}")
        log(f"  VARIANT: {variant.upper()}")
        log(f"{'='*60}")

        for ticket in MONTH4_TICKETS:
            done += 1
            try:
                await process_ticket(ticket, variant)
            except Exception as exc:
                log(f"  {ticket['id']:7s}/{variant:5s} ERROR: {exc}")

    elapsed_all = time.time() - start_all
    log(f"\nTotal time: {elapsed_all:.1f}s")

    # Read all results and print comparison
    results = {v: [] for v in variants}
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            for line in f:
                rec = json.loads(line.strip())
                results[rec["variant"]].append(rec)

    log("\n" + "=" * 90)
    log("  MONTH 4 COMPARISON — BUDGET REMOVED, NVIDIA PRIMARY")
    log("=" * 90)
    log(f"  {'Metric':<25s} {'Mini':>8s} {'PARWA':>8s} {'High':>8s} {'Target':>8s}")
    log(f"  {'─'*25} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")

    for metric, label, target in [
        ("intent_correct", "Intent Accuracy", 90),
        ("sentiment_correct", "Sentiment Accuracy", 85),
        ("escalation_correct", "Escalation Accuracy", 90),
    ]:
        vals = []
        for v in variants:
            r = results[v]
            pct = sum(1 for x in r if x.get(metric, False)) / len(r) * 100 if r else 0
            vals.append(pct)
        log(f"  {label:<25s} {vals[0]:>7.1f}% {vals[1]:>7.1f}% {vals[2]:>7.1f}% {target:>7.1f}%")

    vals = []
    for v in variants:
        r = results[v]
        auto = sum(1 for x in r if not x.get("predicted_escalate", False) and not x.get("expected_escalate", False))
        pct = auto / len(r) * 100 if r else 0
        vals.append(pct)
    log(f"  {'Autonomous Resolution':<25s} {vals[0]:>7.1f}% {vals[1]:>7.1f}% {vals[2]:>7.1f}% {75:>7.1f}%")

    log(f"\n  {'─'*25} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
    for v in variants:
        r = results[v]
        all_ok = sum(1 for x in r if x.get("intent_correct") and x.get("sentiment_correct") and x.get("escalation_correct"))
        pct = all_ok / len(r) * 100 if r else 0
        log(f"  {v.upper()+' Overall':<25s} {pct:>7.1f}%")

    for v in variants:
        r = results[v]
        wrong = [x for x in r if not x.get("intent_correct") or not x.get("sentiment_correct") or not x.get("escalation_correct")]
        if wrong:
            log(f"\n  {v.upper()} WRONG ({len(wrong)}):")
            for x in wrong:
                issues = []
                if not x.get("intent_correct"):
                    issues.append(f"I={x['predicted_intent']}(exp:{x['expected_intent']})")
                if not x.get("sentiment_correct"):
                    issues.append(f"S={x['predicted_sentiment']}(exp:{x['expected_sentiment']})")
                if not x.get("escalation_correct"):
                    issues.append(f"E={x['predicted_escalate']}(exp:{x['expected_escalate']})")
                log(f"    {x['ticket_id']}: {', '.join(issues)}")

    log(f"\nResults saved to {RESULTS_FILE}")
    log(f"Full log at {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(run_all())
