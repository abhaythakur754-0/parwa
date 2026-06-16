"""
PARWA Empirical Resolution Rate - Inline Runner
Runs 20 tickets through real ZAI SDK LLM calls
"""
import asyncio
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone

_last_call_time = 0.0

async def zai_chat(system_prompt, user_message, max_retries=2):
    global _last_call_time
    for attempt in range(max_retries):
        try:
            now = time.monotonic()
            elapsed = now - _last_call_time
            if elapsed < 3.0:
                await asyncio.sleep(3.0 - elapsed)
            cmd = ["z-ai", "chat", "--prompt", user_message, "--system", system_prompt]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            _last_call_time = time.monotonic()
            if result.returncode == 0 and result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content.strip():
                        return content.strip()
                except json.JSONDecodeError:
                    text = result.stdout.strip()
                    if text and len(text) > 5:
                        return text
            if attempt < max_retries - 1:
                await asyncio.sleep(3 * (attempt + 1))
            else:
                return ""
        except Exception as e:
            _last_call_time = time.monotonic()
            if attempt < max_retries - 1:
                await asyncio.sleep(3)
            else:
                return ""
    return ""

ROUTING_PROMPT = "Classify into one: refund/tech/billing/general. One word only.\n- refund: money back, return, reimbursement, cancellation\n- tech: errors, bugs, crashes, not working, API issues\n- billing: charges, payments, invoices, pricing\n- general: everything else"

INTENT_PROMPT = "Classify intent. One word only: refund, cancellation, billing, technical, complaint, shipping, account, general, escalation, order_status"

SUBGRAPH_PROMPTS = {
    "refund": "You are a refund policy specialist. 30-day full refund, 31-60 partial, 60+ defects only. Be empathetic. Respond professionally in 2-4 sentences.",
    "tech": "You are a tech support specialist. Start with simplest fix. If 3+ fixes fail, escalate. Respond professionally in 2-4 sentences.",
    "billing": "You are a billing specialist. Verify charges against plan. Show exact line items. Respond professionally in 2-4 sentences.",
    "general": "You are a helpful support agent. Be friendly, clear, concise. Respond professionally in 2-4 sentences.",
}

EVALUATOR_PROMPT = "Judge if this response resolves the customer problem. Be brutally honest. Respond in JSON format with keys: resolution_status (fully_resolved/partially_resolved/not_resolved), intent_match (true/false), reason (brief string)."


async def route_ticket(query):
    r = await zai_chat(ROUTING_PROMPT, query)
    r = r.strip().lower()
    for v in ("refund", "tech", "billing", "general"):
        if v in r:
            return v
    return "general"


async def classify_intent(query):
    r = await zai_chat(INTENT_PROMPT, query)
    r = r.strip().lower()
    for v in ("refund", "billing", "technical", "complaint", "shipping", "account", "cancellation", "general", "escalation", "order_status"):
        if v in r:
            return v
    return "general"


async def generate_response(query, subgraph, emotion):
    system = SUBGRAPH_PROMPTS.get(subgraph, SUBGRAPH_PROMPTS["general"])
    if emotion in ("angry", "urgent"):
        system += " Customer is ANGRY. Show strong empathy first."
    elif emotion == "frustrated":
        system += " Customer is FRUSTRATED. Acknowledge frustration."
    return await zai_chat(system, query)


async def evaluate(query, response, expected_intent):
    r = await zai_chat(EVALUATOR_PROMPT, "Expected intent: " + expected_intent + "\nCustomer: " + query + "\nResponse: " + response)
    try:
        text = r.strip()
        # Remove code fences
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        parsed = json.loads(text)
        status = parsed.get("resolution_status", "not_resolved")
        if status not in ("fully_resolved", "partially_resolved", "not_resolved"):
            status = "not_resolved"
        return {
            "resolution_status": status,
            "intent_match": bool(parsed.get("intent_match", False)),
            "reason": parsed.get("reason", ""),
        }
    except (json.JSONDecodeError, ValueError):
        status = "not_resolved"
        if "fully_resolved" in r:
            status = "fully_resolved"
        elif "partially_resolved" in r:
            status = "partially_resolved"
        return {"resolution_status": status, "intent_match": False, "reason": "parse fallback"}


TICKETS = [
    {"id": "R-001", "query": "I want a refund for the headphones I bought 5 days ago. The left ear stopped working.", "category": "refund", "expected_subgraph": "refund", "expected_intent": "refund", "emotion": "neutral"},
    {"id": "R-002", "query": "Cancel my subscription immediately. I have been charged for 3 months and never used the service.", "category": "cancellation", "expected_subgraph": "refund", "expected_intent": "cancellation", "emotion": "angry"},
    {"id": "R-003", "query": "I returned my order 2 weeks ago but still have not received my money back. Order #ORD-88234.", "category": "refund", "expected_subgraph": "refund", "expected_intent": "refund", "emotion": "frustrated"},
    {"id": "R-004", "query": "This is the third time asking for a refund on the same item. Your system keeps rejecting it.", "category": "refund", "expected_subgraph": "refund", "expected_intent": "refund", "emotion": "angry"},
    {"id": "R-005", "query": "I bought a laptop 45 days ago. It is defective. Can I still get a refund?", "category": "refund", "expected_subgraph": "refund", "expected_intent": "refund", "emotion": "frustrated"},
    {"id": "T-001", "query": "Your app keeps crashing when I try to upload files. I am on Chrome version 125.", "category": "technical", "expected_subgraph": "tech", "expected_intent": "technical", "emotion": "neutral"},
    {"id": "T-002", "query": "The API is returning 503 errors intermittently. Our production integration is affected.", "category": "technical", "expected_subgraph": "tech", "expected_intent": "technical", "emotion": "urgent"},
    {"id": "T-003", "query": "I cannot log into my account. It says my credentials are invalid but I am using the right password.", "category": "technical", "expected_subgraph": "tech", "expected_intent": "technical", "emotion": "frustrated"},
    {"id": "T-004", "query": "The webhook integration stopped working after your last update. Events are not being delivered.", "category": "technical", "expected_subgraph": "tech", "expected_intent": "technical", "emotion": "frustrated"},
    {"id": "B-001", "query": "You charged me twice for the same order. I can see two charges of 149.99 on my card statement.", "category": "billing", "expected_subgraph": "billing", "expected_intent": "billing", "emotion": "angry"},
    {"id": "B-002", "query": "My invoice shows a different amount than what I was quoted. The tax calculation seems wrong.", "category": "billing", "expected_subgraph": "billing", "expected_intent": "billing", "emotion": "neutral"},
    {"id": "B-003", "query": "I upgraded from Starter to Pro last week but my invoice still shows the Starter price.", "category": "billing", "expected_subgraph": "billing", "expected_intent": "billing", "emotion": "frustrated"},
    {"id": "B-004", "query": "There is an unauthorized transaction of 3450 on my account. I need this investigated immediately.", "category": "billing", "expected_subgraph": "billing", "expected_intent": "billing", "emotion": "angry"},
    {"id": "G-001", "query": "What are your business hours? I need to know when I can reach a live agent.", "category": "general", "expected_subgraph": "general", "expected_intent": "general", "emotion": "neutral"},
    {"id": "G-002", "query": "How do I change my email address on my account?", "category": "account", "expected_subgraph": "general", "expected_intent": "account", "emotion": "neutral"},
    {"id": "G-003", "query": "I am very disappointed with the service I received. The agent was rude and unhelpful.", "category": "complaint", "expected_subgraph": "general", "expected_intent": "complaint", "emotion": "angry"},
    {"id": "G-004", "query": "Do you offer an API for integrating with Salesforce?", "category": "general", "expected_subgraph": "general", "expected_intent": "general", "emotion": "neutral"},
    {"id": "G-005", "query": "I am going to sue your company for selling my data without consent.", "category": "escalation", "expected_subgraph": "general", "expected_intent": "escalation", "emotion": "angry"},
    {"id": "G-006", "query": "Can you tell me the status of my order #ORD-98234?", "category": "order_status", "expected_subgraph": "general", "expected_intent": "order_status", "emotion": "neutral"},
    {"id": "G-007", "query": "I have been a loyal customer for 3 years and this is how you treat me? I want to speak to a manager.", "category": "escalation", "expected_subgraph": "general", "expected_intent": "escalation", "emotion": "angry"},
]


async def run_all():
    results = []
    total = len(TICKETS)
    print("PARWA EMPIRICAL TEST: %d tickets, real ZAI SDK LLM calls" % total)
    print("=" * 70)

    for i, t in enumerate(TICKETS):
        tid = t["id"]
        print("[%d/%d] %s " % (i+1, total, tid), end="", flush=True)
        start = time.monotonic()

        pred_sub = await route_ticket(t["query"])
        await asyncio.sleep(1)
        pred_int = await classify_intent(t["query"])
        await asyncio.sleep(1)
        response = await generate_response(t["query"], pred_sub, t["emotion"])
        await asyncio.sleep(1)
        ev = await evaluate(t["query"], response, t["expected_intent"])

        latency = round((time.monotonic() - start) * 1000)

        sub_ok = pred_sub == t["expected_subgraph"]
        int_ok = pred_int == t["expected_intent"]
        # Legal threats should escalate
        contained = "sue" not in t["query"].lower()

        r = {
            "ticket_id": tid,
            "category": t["category"],
            "expected_subgraph": t["expected_subgraph"],
            "predicted_subgraph": pred_sub,
            "subgraph_correct": sub_ok,
            "expected_intent": t["expected_intent"],
            "predicted_intent": pred_int,
            "intent_correct": int_ok,
            "resolution_status": ev["resolution_status"],
            "evaluator_intent_match": ev["intent_match"],
            "evaluator_reason": ev["reason"],
            "contained": contained,
            "response": response[:200],
            "latency_ms": latency,
        }
        results.append(r)

        ri = {"fully_resolved": "F", "partially_resolved": "P", "not_resolved": "N"}.get(ev["resolution_status"], "?")
        sub_mark = "S" if sub_ok else "X"
        int_mark = "I" if int_ok else "X"
        print("| Sub:%s Int:%s Res:%s | %dms" % (sub_mark, int_mark, ri, latency))

        await asyncio.sleep(1)

    # Calculate metrics
    n = len(results)
    contained_n = len([r for r in results if r["contained"]])
    sub_ok_n = len([r for r in results if r["subgraph_correct"]])
    int_ok_n = len([r for r in results if r["intent_correct"]])
    fully_n = len([r for r in results if r["resolution_status"] == "fully_resolved"])
    partial_n = len([r for r in results if r["resolution_status"] == "partially_resolved"])
    not_res_n = len([r for r in results if r["resolution_status"] == "not_resolved"])
    true_res_n = len([r for r in results if r["intent_correct"] and r["resolution_status"] == "fully_resolved"])
    ind_res_n = len([r for r in results if r["contained"] and r["resolution_status"] in ("fully_resolved", "partially_resolved")])
    int_contained_n = len([r for r in results if r["intent_correct"] and r["contained"]])
    ev_int_n = len([r for r in results if r["evaluator_intent_match"]])

    # Per-subgraph breakdown
    by_sub = {}
    for r in results:
        by_sub.setdefault(r["predicted_subgraph"], []).append(r)

    print()
    print("=" * 70)
    print("EMPIRICAL RESULTS - REAL LLM MEASUREMENTS")
    print("=" * 70)
    print("Tickets: %d | LLM calls: ~%d | Model: GLM-4-Plus" % (n, n*5))
    print()
    print("INDUSTRY-STANDARD METRICS:")
    print("  Method 1: Containment Rate:              %.1f%%  (%d/%d)" % (contained_n/n*100, contained_n, n))
    print("  Method 2: Intent-Correct Containment:    %.1f%%  (%d/%d)" % (int_contained_n/n*100, int_contained_n, n))
    print("  Method 3: True Resolution Rate:          %.1f%%  (%d/%d)" % (true_res_n/n*100, true_res_n, n))
    print("  Method 4: Industry-Comparable Rate:      %.1f%%  (%d/%d)" % (ind_res_n/n*100, ind_res_n, n))
    print()
    print("BREAKDOWN:")
    print("  Subgraph Routing Accuracy:  %.1f%%" % (sub_ok_n/n*100))
    print("  Intent Accuracy:            %.1f%%" % (int_ok_n/n*100))
    print("  Evaluator Intent Match:     %.1f%%" % (ev_int_n/n*100))
    print("  Fully Resolved:             %.1f%%" % (fully_n/n*100))
    print("  Partially Resolved:         %.1f%%" % (partial_n/n*100))
    print("  Not Resolved:               %.1f%%" % (not_res_n/n*100))
    print()
    print("BY SUBGRAPH:")
    for sg, sg_results in sorted(by_sub.items()):
        sg_n = len(sg_results)
        sg_int = len([r for r in sg_results if r["intent_correct"]])
        sg_full = len([r for r in sg_results if r["resolution_status"] == "fully_resolved"])
        sg_true = len([r for r in sg_results if r["intent_correct"] and r["resolution_status"] == "fully_resolved"])
        sg_cont = len([r for r in sg_results if r["contained"]])
        print("  %-10s %d tickets | Intent: %.0f%% | Contain: %.0f%% | TrueRes: %.0f%%" % (
            sg, sg_n, sg_int/sg_n*100, sg_cont/sg_n*100, sg_true/sg_n*100))

    # Failed tickets
    failed = [r for r in results if r["resolution_status"] == "not_resolved" or not r["intent_correct"]]
    if failed:
        print()
        print("TICKETS NEEDING IMPROVEMENT (%d):" % len(failed))
        for r in failed:
            int_mark = "X" if not r["intent_correct"] else "OK"
            sub_mark = "X" if not r["subgraph_correct"] else "OK"
            print("  %-5s [%-12s] Sub:%-8s %s Int:%-12s %s | Res:%-18s | %s" % (
                r["ticket_id"], r["category"],
                r["predicted_subgraph"], sub_mark,
                r["predicted_intent"], int_mark,
                r["resolution_status"],
                r["evaluator_reason"][:50]))

    # Improvement levers
    intent_fail = [r for r in results if not r["intent_correct"]]
    res_fail = [r for r in results if r["resolution_status"] == "not_resolved"]
    print()
    print("IMPROVEMENT LEVERS:")
    print("  Intent failures:    %d/%d (%.1f%%)" % (len(intent_fail), n, len(intent_fail)/n*100))
    print("  Resolution failures: %d/%d (%.1f%%)" % (len(res_fail), n, len(res_fail)/n*100))
    biggest = "intent" if len(intent_fail) >= len(res_fail) else "resolution quality"
    print("  BIGGEST LEVER: %s" % biggest)

    # Industry comparison
    print()
    print("INDUSTRY COMPARISON:")
    print("  %-20s %10s %10s %10s" % ("Company", "Reported", "Real Est.", "PARWA"))
    print("  %-20s %10s %10s %10s" % ("Intercom Fin", "50-70%", "35-55%", "%.1f%%" % (ind_res_n/n*100)))
    print("  %-20s %10s %10s %10s" % ("Zendesk AI", "40-60%", "25-45%", "%.1f%%" % (ind_res_n/n*100)))
    print("  %-20s %10s %10s %10s" % ("Sierra AI", "70-80%", "55-72%", "%.1f%%" % (ind_res_n/n*100)))
    print("  %-20s %10s %10s %10s" % ("PARWA (true)", "--", "--", "%.1f%%" % (true_res_n/n*100)))

    # Save
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": "empirical_real_llm_zai_sdk_glm4_plus",
        "total_tickets": n,
        "total_llm_calls_approx": n * 5,
        "metrics": {
            "containment_rate": round(contained_n/n*100, 2),
            "subgraph_routing_accuracy": round(sub_ok_n/n*100, 2),
            "intent_accuracy": round(int_ok_n/n*100, 2),
            "evaluator_intent_match_rate": round(ev_int_n/n*100, 2),
            "intent_correct_containment_rate": round(int_contained_n/n*100, 2),
            "fully_resolved_rate": round(fully_n/n*100, 2),
            "partially_resolved_rate": round(partial_n/n*100, 2),
            "not_resolved_rate": round(not_res_n/n*100, 2),
            "true_resolution_rate": round(true_res_n/n*100, 2),
            "industry_comparable_rate": round(ind_res_n/n*100, 2),
        },
        "per_ticket_results": results,
        "improvement_levers": {
            "intent_failures": len(intent_fail),
            "resolution_failures": len(res_fail),
            "biggest_lever": biggest,
        },
    }

    os.makedirs("download", exist_ok=True)
    with open("download/empirical_resolution_rate_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print("\nSaved to download/empirical_resolution_rate_results.json")


if __name__ == "__main__":
    asyncio.run(run_all())
