"""
PARWA Empirical Resolution Rate - Batch Runner
Processes tickets in small batches to avoid timeouts
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

EVALUATOR_PROMPT = "Judge if this response resolves the customer problem. Be brutally honest. Respond in JSON: resolution_status (fully_resolved/partially_resolved/not_resolved), intent_match (true/false), reason (brief string). No code fences, just raw JSON."

async def route_ticket(q):
    r = await zai_chat(ROUTING_PROMPT, q)
    r = r.strip().lower()
    for v in ("refund", "tech", "billing", "general"):
        if v in r: return v
    return "general"

async def classify_intent(q):
    r = await zai_chat(INTENT_PROMPT, q)
    r = r.strip().lower()
    for v in ("refund", "billing", "technical", "complaint", "shipping", "account", "cancellation", "general", "escalation", "order_status"):
        if v in r: return v
    return "general"

async def generate_response(q, sub, emotion):
    system = SUBGRAPH_PROMPTS.get(sub, SUBGRAPH_PROMPTS["general"])
    if emotion in ("angry", "urgent"): system += " Customer is ANGRY. Show strong empathy first."
    elif emotion == "frustrated": system += " Customer is FRUSTRATED. Acknowledge frustration."
    return await zai_chat(system, q)

async def evaluate(q, resp, expected):
    r = await zai_chat(EVALUATOR_PROMPT, "Expected intent: " + expected + "\nCustomer: " + q + "\nResponse: " + resp)
    try:
        text = r.strip()
        if "```json" in text: text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text: text = text.split("```")[1].split("```")[0].strip()
        parsed = json.loads(text)
        status = parsed.get("resolution_status", "not_resolved")
        if status not in ("fully_resolved", "partially_resolved", "not_resolved"): status = "not_resolved"
        return {"resolution_status": status, "intent_match": bool(parsed.get("intent_match", False)), "reason": parsed.get("reason", "")}
    except:
        status = "not_resolved"
        if "fully_resolved" in r: status = "fully_resolved"
        elif "partially_resolved" in r: status = "partially_resolved"
        return {"resolution_status": status, "intent_match": False, "reason": "parse fallback"}

# All 20 tickets
ALL_TICKETS = [
    {"id": "R-001", "query": "I want a refund for the headphones I bought 5 days ago. The left ear stopped working.", "category": "refund", "es": "refund", "ei": "refund", "emotion": "neutral"},
    {"id": "R-002", "query": "Cancel my subscription immediately. I have been charged for 3 months and never used the service.", "category": "cancellation", "es": "refund", "ei": "cancellation", "emotion": "angry"},
    {"id": "R-003", "query": "I returned my order 2 weeks ago but still have not received my money back. Order #ORD-88234.", "category": "refund", "es": "refund", "ei": "refund", "emotion": "frustrated"},
    {"id": "R-004", "query": "This is the third time asking for a refund on the same item. Your system keeps rejecting it.", "category": "refund", "es": "refund", "ei": "refund", "emotion": "angry"},
    {"id": "R-005", "query": "I bought a laptop 45 days ago. It is defective. Can I still get a refund?", "category": "refund", "es": "refund", "ei": "refund", "emotion": "frustrated"},
    {"id": "T-001", "query": "Your app keeps crashing when I try to upload files. I am on Chrome version 125.", "category": "technical", "es": "tech", "ei": "technical", "emotion": "neutral"},
    {"id": "T-002", "query": "The API is returning 503 errors intermittently. Our production integration is affected.", "category": "technical", "es": "tech", "ei": "technical", "emotion": "urgent"},
    {"id": "T-003", "query": "I cannot log into my account. It says my credentials are invalid but I am using the right password.", "category": "technical", "es": "tech", "ei": "technical", "emotion": "frustrated"},
    {"id": "T-004", "query": "The webhook integration stopped working after your last update. Events are not being delivered.", "category": "technical", "es": "tech", "ei": "technical", "emotion": "frustrated"},
    {"id": "B-001", "query": "You charged me twice for the same order. I can see two charges of 149.99 on my card statement.", "category": "billing", "es": "billing", "ei": "billing", "emotion": "angry"},
    {"id": "B-002", "query": "My invoice shows a different amount than what I was quoted. The tax calculation seems wrong.", "category": "billing", "es": "billing", "ei": "billing", "emotion": "neutral"},
    {"id": "B-003", "query": "I upgraded from Starter to Pro last week but my invoice still shows the Starter price.", "category": "billing", "es": "billing", "ei": "billing", "emotion": "frustrated"},
    {"id": "B-004", "query": "There is an unauthorized transaction of 3450 on my account. I need this investigated immediately.", "category": "billing", "es": "billing", "ei": "billing", "emotion": "angry"},
    {"id": "G-001", "query": "What are your business hours? I need to know when I can reach a live agent.", "category": "general", "es": "general", "ei": "general", "emotion": "neutral"},
    {"id": "G-002", "query": "How do I change my email address on my account?", "category": "account", "es": "general", "ei": "account", "emotion": "neutral"},
    {"id": "G-003", "query": "I am very disappointed with the service I received. The agent was rude and unhelpful.", "category": "complaint", "es": "general", "ei": "complaint", "emotion": "angry"},
    {"id": "G-004", "query": "Do you offer an API for integrating with Salesforce?", "category": "general", "es": "general", "ei": "general", "emotion": "neutral"},
    {"id": "G-005", "query": "I am going to sue your company for selling my data without consent.", "category": "escalation", "es": "general", "ei": "escalation", "emotion": "angry"},
    {"id": "G-006", "query": "Can you tell me the status of my order #ORD-98234?", "category": "order_status", "es": "general", "ei": "order_status", "emotion": "neutral"},
    {"id": "G-007", "query": "I have been a loyal customer for 3 years and this is how you treat me? I want to speak to a manager.", "category": "escalation", "es": "general", "ei": "escalation", "emotion": "angry"},
]

# Which batch to run (set via env var BATCH)
BATCH = int(os.environ.get("BATCH", "1"))
BATCH_SIZE = 5
start_idx = (BATCH - 1) * BATCH_SIZE
end_idx = min(start_idx + BATCH_SIZE, len(ALL_TICKETS))
tickets = ALL_TICKETS[start_idx:end_idx]

async def run_batch():
    results = []
    total = len(tickets)
    print("BATCH %d: %d tickets (indices %d-%d)" % (BATCH, total, start_idx, end_idx-1))

    for i, t in enumerate(tickets):
        print("[%d/%d] %s " % (i+1, total, t["id"]), end="", flush=True)
        start = time.monotonic()

        pred_sub = await route_ticket(t["query"])
        await asyncio.sleep(1)
        pred_int = await classify_intent(t["query"])
        await asyncio.sleep(1)
        response = await generate_response(t["query"], pred_sub, t["emotion"])
        await asyncio.sleep(1)
        ev = await evaluate(t["query"], response, t["ei"])

        latency = round((time.monotonic() - start) * 1000)

        sub_ok = pred_sub == t["es"]
        int_ok = pred_int == t["ei"]
        contained = "sue" not in t["query"].lower()

        r = {
            "ticket_id": t["id"], "category": t["category"],
            "expected_subgraph": t["es"], "predicted_subgraph": pred_sub, "subgraph_correct": sub_ok,
            "expected_intent": t["ei"], "predicted_intent": pred_int, "intent_correct": int_ok,
            "resolution_status": ev["resolution_status"], "evaluator_intent_match": ev["intent_match"],
            "evaluator_reason": ev["reason"],
            "contained": contained, "response": response[:300], "latency_ms": latency,
        }
        results.append(r)

        ri = {"fully_resolved": "F", "partially_resolved": "P", "not_resolved": "N"}.get(ev["resolution_status"], "?")
        print("| Sub:%s Int:%s Res:%s | %dms | %s" % (
            "S" if sub_ok else "X", "I" if int_ok else "X", ri, latency, ev["reason"][:40]))

        await asyncio.sleep(1)

    os.makedirs("download", exist_ok=True)
    batch_file = "download/empirical_batch_%d.json" % BATCH
    with open(batch_file, "w") as f:
        json.dump({"batch": BATCH, "results": results, "timestamp": datetime.now(timezone.utc).isoformat()}, f, indent=2, default=str)
    print("\nBatch %d saved to %s" % (BATCH, batch_file))

if __name__ == "__main__":
    asyncio.run(run_batch())
