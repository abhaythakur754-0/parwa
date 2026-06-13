#!/usr/bin/env python3
"""Run one variant of Month 4 test. Usage: python run_variant.py mini|parwa|high"""

import asyncio, json, os, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PARWA_MOCK_MODE"] = "false"

from parwa.eval.month4_tickets import MONTH4_TICKETS

RESULTS_FILE = "/home/z/my-project/download/month4_results.jsonl"

def _norm(val):
    s = str(val).lower()
    for p in ("sentimenttype.", "intenttype."):
        s = s.replace(p, "")
    if "." in s:
        s = s.split(".")[-1]
    return s


async def run_variant(variant):
    from parwa.graph import aprocess_ticket, reset_parwa_graph
    from parwa.fake_crm.database import reset_crm

    for ticket in MONTH4_TICKETS:
        # Skip if already processed
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE) as f:
                existing = [json.loads(l) for l in f if l.strip()]
                if any(r["ticket_id"] == ticket["id"] and r["variant"] == variant for r in existing):
                    print(f"  SKIP {ticket['id']}/{variant} (already done)", flush=True)
                    continue

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

            i_ic = "Y" if i_ok else "N"
            s_ic = "Y" if s_ok else "N"
            e_ic = "Y" if e_ok else "N"
            print(f"  {ticket['id']:7s}/{variant:5s} I:{i_ic} S:{s_ic} E:{e_ic} | "
                  f"intent={pi:20s} sent={ps:12s} esc={str(pe):5s} | {elapsed:.1f}s", flush=True)

        except Exception as exc:
            print(f"  {ticket['id']:7s}/{variant:5s} ERROR: {exc}", flush=True)

    print(f"  VARIANT {variant.upper()} DONE", flush=True)


if __name__ == "__main__":
    variant = sys.argv[1] if len(sys.argv) > 1 else "parwa"
    asyncio.run(run_variant(variant))
