#!/usr/bin/env python3
"""Run Retest V2 in background — one variant at a time."""

import asyncio, json, os, sys, time
from datetime import datetime

sys.path.insert(0, '/home/z/my-project/parwa')
os.environ["PARWA_MOCK_MODE"] = "false"

from parwa.eval.retest_v2_tickets import RETEST_V2_TICKETS

RESULTS_FILE = "/home/z/my-project/download/retest_v2_results.jsonl"
VARIANTS = ["mini", "parwa", "high"]

def _norm(val):
    s = str(val).lower()
    for p in ("sentimenttype.", "intenttype.", "ticketcomplexity."):
        s = s.replace(p, "")
    if "." in s:
        s = s.split(".")[-1]
    return s

async def run_one(ticket, variant):
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
        
        ei = ticket["expected_intent"].lower()
        es = ticket["expected_sentiment"].lower()
        ee = ticket["expected_escalation"]
        
        i_ok = pi == ei or ei in pi or pi in ei
        if ei == "billing_issue" and pi in ("complaint", "refund_request"):
            i_ok = True
        if ei == "refund_request" and pi in ("complaint",):
            i_ok = True
        s_ok = ps == es
        if ticket.get("category") == "sarcastic_complaint" and ps in ("frustrated", "angry"):
            s_ok = True
        e_ok = pe == ee
        
        record = {
            "ticket_id": ticket["id"], "category": ticket["category"],
            "difficulty": ticket["difficulty"], "variant": variant,
            "predicted_intent": pi, "expected_intent": ei, "intent_correct": i_ok,
            "predicted_sentiment": ps, "expected_sentiment": es, "sentiment_correct": s_ok,
            "predicted_escalate": pe, "expected_escalate": ee, "escalation_correct": e_ok,
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
            "ticket_id": ticket["id"], "category": ticket["category"],
            "difficulty": ticket["difficulty"], "variant": variant,
            "error": str(exc), "time_s": round(elapsed, 1),
            "timestamp": datetime.utcnow().isoformat(),
        }

async def run_all():
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)
    
    all_results = []
    for variant in VARIANTS:
        print(f"\n{'='*60}", flush=True)
        print(f"  VARIANT: {variant.upper()}", flush=True)
        print(f"{'='*60}", flush=True)
        
        for ticket in RETEST_V2_TICKETS:
            tid = ticket["id"]
            print(f"  [{tid}/{variant}] Running...", flush=True)
            record = await run_one(ticket, variant)
            all_results.append(record)
            
            with open(RESULTS_FILE, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")
            
            if "error" in record:
                print(f"  [{tid}/{variant}] ERROR: {record['error']}", flush=True)
                continue
            
            i_m = "Y" if record["intent_correct"] else "N"
            s_m = "Y" if record["sentiment_correct"] else "N"
            e_m = "Y" if record["escalation_correct"] else "N"
            print(f"  [{tid}/{variant}] I:{i_m} S:{s_m} E:{e_m} | "
                  f"intent={record['predicted_intent']:18s} sent={record['predicted_sentiment']:10s} "
                  f"esc={str(record['predicted_escalate']):5s} | "
                  f"Q={record['quality_score']:4.0f} conf={record.get('confidence',0):.2f} "
                  f"fw={record['frameworks_count']} time={record['time_s']:.1f}s", flush=True)
            
            # Rate limit pause between tickets
            await asyncio.sleep(2)
        
        print(f"  VARIANT {variant.upper()} DONE", flush=True)
        # Pause between variants for rate limit
        await asyncio.sleep(5)
    
    # Final summary
    print(f"\n\n{'='*60}", flush=True)
    print(f"  FINAL RESULTS SUMMARY", flush=True)
    print(f"{'='*60}", flush=True)
    
    for variant in VARIANTS:
        vr = [r for r in all_results if r.get("variant") == variant and "error" not in r]
        ve = [r for r in all_results if r.get("variant") == variant and "error" in r]
        if not vr:
            print(f"\n  {variant.upper()}: NO RESULTS", flush=True)
            continue
        
        ia = sum(1 for r in vr if r["intent_correct"]) / len(vr) * 100
        sa = sum(1 for r in vr if r["sentiment_correct"]) / len(vr) * 100
        ea = sum(1 for r in vr if r["escalation_correct"]) / len(vr) * 100
        aq = sum(r["quality_score"] for r in vr) / len(vr)
        ac = sum(r.get("confidence", 0) for r in vr) / len(vr)
        af = sum(r["frameworks_count"] for r in vr) / len(vr)
        at = sum(r["time_s"] for r in vr) / len(vr)
        ov = (ia + sa + ea + aq) / 4
        
        print(f"\n  {variant.upper()}:", flush=True)
        print(f"    Intent:     {ia:.0f}%  Sentiment: {sa:.0f}%  Escalation: {ea:.0f}%", flush=True)
        print(f"    Quality:    {aq:.1f}/100  Confidence: {ac:.3f}", flush=True)
        print(f"    Frameworks: {af:.1f}  Avg Time: {at:.1f}s  Errors: {len(ve)}", flush=True)
        print(f"    OVERALL:    {ov:.1f}/100", flush=True)
        
        for r in vr:
            im = "Y" if r["intent_correct"] else "N"
            sm = "Y" if r["sentiment_correct"] else "N"
            em = "Y" if r["escalation_correct"] else "N"
            print(f"      {r['ticket_id']} I:{im} S:{sm} E:{em} Q={r['quality_score']:.0f} "
                  f"intent={r['predicted_intent']} sent={r['predicted_sentiment']} esc={r['predicted_escalate']}", flush=True)

if __name__ == "__main__":
    asyncio.run(run_all())
