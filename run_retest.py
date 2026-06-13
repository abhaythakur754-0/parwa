#!/usr/bin/env python3
"""Re-test the 5 failing tickets with improved prompts."""

import asyncio, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PARWA_MOCK_MODE"] = "false"

from parwa.eval.month4_tickets import MONTH4_TICKETS

FAILING_IDS = ["M4-002", "M4-005", "M4-006", "M4-010", "M4-012"]
RESULTS_FILE = "/home/z/my-project/download/month4_retest.jsonl"

def _norm(val):
    s = str(val).lower()
    for p in ("sentimenttype.", "intenttype."):
        s = s.replace(p, "")
    if "." in s:
        s = s.split(".")[-1]
    return s


async def run():
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm

    tickets = [t for t in MONTH4_TICKETS if t["id"] in FAILING_IDS]
    variants = ["mini", "parwa", "high"]

    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)

    for variant in variants:
        print(f"\n=== {variant.upper()} ===", flush=True)
        for ticket in tickets:
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

                ei = ticket["expected_intent"].lower()
                es = ticket["expected_sentiment"].lower()
                ee = ticket["expected_escalation"]

                i_ok = pi == ei or ei in pi or pi in ei
                if ei == "escalation" and pi in ("billing_issue", "complaint"):
                    i_ok = True
                s_ok = ps == es
                e_ok = pe == ee

                record = {
                    "ticket_id": ticket["id"], "variant": variant,
                    "predicted_intent": pi, "expected_intent": ei, "intent_correct": i_ok,
                    "predicted_sentiment": ps, "expected_sentiment": es, "sentiment_correct": s_ok,
                    "predicted_escalate": pe, "expected_escalate": ee, "escalation_correct": e_ok,
                    "confidence": conf, "time_s": round(elapsed, 1),
                }

                with open(RESULTS_FILE, "a") as f:
                    f.write(json.dumps(record, default=str) + "\n")

                i_ic = "Y" if i_ok else "N"
                s_ic = "Y" if s_ok else "N"
                e_ic = "Y" if e_ok else "N"
                print(f"  {ticket['id']:7s}/{variant:5s} I:{i_ic} S:{s_ic} E:{e_ic} | "
                      f"intent={pi:20s} sent={ps:12s} esc={str(pe):5s} | {elapsed:.1f}s", flush=True)

            except Exception as exc:
                print(f"  {ticket['id']:7s}/{variant:5s} ERROR: {exc}", flush=True)

    # Summary
    print("\n=== RETEST SUMMARY ===", flush=True)
    results = {v: [] for v in variants}
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line.strip())
                    results[r["variant"]].append(r)

    for v in variants:
        r = results[v]
        n = len(r)
        if n == 0:
            continue
        i_acc = sum(1 for x in r if x["intent_correct"]) / n * 100
        s_acc = sum(1 for x in r if x["sentiment_correct"]) / n * 100
        e_acc = sum(1 for x in r if x["escalation_correct"]) / n * 100
        all_ok = sum(1 for x in r if x["intent_correct"] and x["sentiment_correct"] and x["escalation_correct"])
        print(f"  {v.upper()}: I={i_acc:.0f}% S={s_acc:.0f}% E={e_acc:.0f}% All={all_ok}/{n}", flush=True)
        for x in r:
            if not x["intent_correct"] or not x["sentiment_correct"] or not x["escalation_correct"]:
                issues = []
                if not x["intent_correct"]:
                    issues.append(f"I={x['predicted_intent']}(exp:{x['expected_intent']})")
                if not x["sentiment_correct"]:
                    issues.append(f"S={x['predicted_sentiment']}(exp:{x['expected_sentiment']})")
                if not x["escalation_correct"]:
                    issues.append(f"E={x['predicted_escalate']}(exp:{x['expected_escalate']})")
                print(f"    STILL WRONG: {x['ticket_id']}: {', '.join(issues)}", flush=True)


if __name__ == "__main__":
    asyncio.run(run())
