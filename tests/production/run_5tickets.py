"""PARWA Empirical - 5 tickets at a time, 10s delays between calls"""
import httpx, json, os, time
from datetime import datetime, timezone

KEY = "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"
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DELAY = 3  # seconds between API calls

def chat(sys, user, max_tokens=300, temp=0.1):
    """Synchronous chat with NVIDIA API."""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"}
    models = ["deepseek-ai/deepseek-v4-flash", "meta/llama-3.3-70b-instruct"]
    for model in models:
        for attempt in range(3):
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "system", "content": sys}, {"role": "user", "content": user}],
                    "max_tokens": max_tokens, "temperature": temp,
                }
                r = httpx.post(URL, headers=headers, json=payload, timeout=45)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
                elif r.status_code == 429:
                    print(f"(429) ", end="", flush=True)
                    time.sleep(15)
                else:
                    print(f"({r.status_code}) ", end="", flush=True)
                    time.sleep(3)
            except Exception as e:
                print(f"(err) ", end="", flush=True)
                time.sleep(5)
    return ""

def parse_eval(text):
    try:
        t = text.strip()
        if "```json" in t: t = t.split("```json")[1].split("```")[0].strip()
        elif "```" in t: t = t.split("```")[1].split("```")[0].strip()
        d = json.loads(t)
        status = d.get("resolution_status", "not_resolved")
        if status not in ("fully_resolved", "partially_resolved", "not_resolved"): status = "not_resolved"
        return {"status": status, "intent_match": bool(d.get("intent_match", False)), "actionable": bool(d.get("actionable", False)), "reason": d.get("reason", "")}
    except:
        status = "not_resolved"
        if "fully_resolved" in text: status = "fully_resolved"
        elif "partially_resolved" in text: status = "partially_resolved"
        return {"status": status, "intent_match": False, "actionable": False, "reason": "parse fallback"}

# ALL 30 TICKETS
ALL = [
    ("R-001","I want a refund for the headphones I bought 5 days ago. The left ear stopped working.","refund","refund","neutral"),
    ("R-002","Cancel my subscription immediately. I have been charged for 3 months and never used the service.","refund","cancellation","angry"),
    ("R-003","I returned my order 2 weeks ago but still have not received my money back. Order #ORD-88234.","refund","refund","frustrated"),
    ("R-004","This is the third time asking for a refund on the same item. Your system keeps rejecting it.","refund","refund","angry"),
    ("R-005","I bought a laptop 45 days ago. It is defective. Can I still get a refund?","refund","refund","frustrated"),
    ("R-006","My subscription renewed yesterday but I cancelled last week. I need the renewal charge reversed.","refund","refund","frustrated"),
    ("R-007","I accidentally purchased the Pro plan instead of Starter. Can you refund the difference?","refund","refund","neutral"),
    ("R-008","You people stole my money! I never signed up for this and you have been charging me for 6 months!","refund","refund","angry"),
    ("T-001","Your app keeps crashing when I try to upload files. Chrome version 125.","tech","technical","neutral"),
    ("T-002","The API is returning 503 errors intermittently. Our production integration is affected.","tech","technical","urgent"),
    ("T-003","I cannot log into my account. It says credentials invalid but I am using the right password.","tech","technical","frustrated"),
    ("T-004","The webhook integration stopped working after your last update. Events not being delivered.","tech","technical","frustrated"),
    ("T-005","My dashboard is loading extremely slow. 30 seconds for any page to load.","tech","technical","frustrated"),
    ("B-001","You charged me twice for the same order! Two charges of $149.99 on my card statement.","billing","billing","angry"),
    ("B-002","My invoice shows a different amount than what I was quoted. The tax calculation seems wrong.","billing","billing","neutral"),
    ("B-003","I upgraded from Starter to Pro last week but my invoice still shows the Starter price.","billing","billing","frustrated"),
    ("B-004","There is an unauthorized transaction of $3,450 on my account. Investigate immediately.","billing","billing","angry"),
    ("B-005","Can you explain the proration on my latest invoice? I do not understand the mid-cycle upgrade charge.","billing","billing","neutral"),
    ("G-001","What are your business hours? I need to know when I can reach a live agent.","general","general","neutral"),
    ("G-002","How do I change my email address on my account?","general","account","neutral"),
    ("G-003","I am very disappointed with the service. The agent was rude and unhelpful.","general","complaint","angry"),
    ("G-004","Do you offer an API for integrating with Salesforce?","general","general","neutral"),
    ("G-005","I am going to sue your company for selling my data without consent.","general","escalation","angry"),
    ("G-006","Can you tell me the status of my order #ORD-98234?","general","order_status","neutral"),
    ("G-007","I have been a loyal customer for 3 years and this is how you treat me? I want to speak to a manager.","general","escalation","angry"),
    ("G-008","What is the difference between your Starter and Pro plans?","general","general","neutral"),
    ("T-006","Getting SSL certificate errors when connecting to your API endpoint from our EU servers.","tech","technical","neutral"),
    ("T-007","Your mobile app will not open on my iPhone 15. Crashes immediately on launch.","tech","technical","frustrated"),
    ("B-006","My payment failed but my card is working fine everywhere else. What is wrong with your system?","billing","billing","frustrated"),
    ("B-007","I need a receipt for my annual subscription payment for tax purposes.","billing","billing","neutral"),
]

ROUTE_P = "Classify the customer message into one category: refund, tech, billing, general. Respond with ONLY the category name. One word."
INTENT_P = "Classify the customer intent into one: refund, cancellation, billing, technical, complaint, shipping, account, general, escalation, order_status. Respond with ONLY the intent name. One word."
RESP = {
    "refund": "You are a refund policy specialist for PARWA. 30-day full refund, 31-60 day partial (50-75%), 60+ defects only. Subscription refunds prorated. Be empathetic. 2-3 sentences with specific details.",
    "tech": "You are a technical support specialist for PARWA. Start with simplest fix. Give specific steps. If 3+ fixes fail, escalate. 2-3 sentences.",
    "billing": "You are a billing specialist for PARWA. Verify charges against plan. Show exact amounts. 2-3 sentences with numbers.",
    "general": "You are a helpful customer support agent for PARWA. Be friendly, clear, concise. For complaints, acknowledge frustration first. For legal threats, route to specialist. 2-3 sentences.",
}
EVAL_P = 'Judge if this support response actually resolves the customer problem. Be brutally honest. JSON only: {"resolution_status": "fully_resolved"/"partially_resolved"/"not_resolved", "intent_match": true/false, "actionable": true/false, "reason": "brief"}'

# BATCH CONTROL - process 5 tickets at a time
BATCH_NUM = int(os.environ.get("BATCH", "1"))
BATCH_SIZE = 5
start_idx = (BATCH_NUM - 1) * BATCH_SIZE
end_idx = min(start_idx + BATCH_SIZE, len(ALL))
tickets = ALL[start_idx:end_idx]

# Load existing results if any
results_file = "download/empirical_progress.json"
existing = []
if os.path.exists(results_file):
    with open(results_file) as f:
        existing = json.load(f)
    print(f"Loaded {len(existing)} existing results")

print(f"Batch {BATCH_NUM}: {len(tickets)} tickets (indices {start_idx}-{end_idx-1})")
print(f"Using {DELAY}s delay between API calls")
print("=" * 60)

for i, (tid, q, es, ei, em) in enumerate(tickets):
    # Skip if already done
    if any(r["id"] == tid for r in existing):
        print(f"  {tid} already done, skipping")
        continue
    print(f"[{len(existing)+1}/{len(ALL)}] {tid} ", end="", flush=True)
    s = time.monotonic()

    # Route
    time.sleep(DELAY)
    r_sub = chat(ROUTE_P, q, 20, 0.1)
    pred_sub = "general"
    for v in ("refund", "tech", "billing", "general"):
        if v in r_sub.lower():
            pred_sub = v
            break

    # Intent
    time.sleep(DELAY)
    r_int = chat(INTENT_P, q, 20, 0.1)
    pred_int = "general"
    for v in ("refund", "billing", "technical", "complaint", "shipping", "account", "cancellation", "general", "escalation", "order_status"):
        if v in r_int.lower():
            pred_int = v
            break

    # Response
    sys_p = RESP.get(pred_sub, RESP["general"])
    if em in ("angry", "urgent"):
        sys_p += " IMPORTANT: Customer is ANGRY. Show strong empathy first."
    elif em == "frustrated":
        sys_p += " Customer is FRUSTRATED. Acknowledge their frustration."
    time.sleep(DELAY)
    response = chat(sys_p, q, 400, 0.3)

    # Evaluate
    time.sleep(DELAY)
    ev_text = chat(EVAL_P, f"Expected intent: {ei}\nCustomer: {q}\nResponse: {response}", 200, 0.1)
    ev = parse_eval(ev_text)

    lat = round((time.monotonic() - s) * 1000)
    sub_ok = pred_sub == es
    int_ok = pred_int == ei
    contained = "sue" not in q.lower() and ev["status"] != "not_resolved"

    result = {
        "id": tid, "expected_sub": es, "pred_sub": pred_sub, "sub_ok": sub_ok,
        "expected_intent": ei, "pred_int": pred_int, "int_ok": int_ok,
        "resolution": ev["status"], "intent_match": ev["intent_match"],
        "actionable": ev["actionable"], "reason": ev["reason"],
        "contained": contained, "response": response[:200], "lat_ms": lat,
    }
    existing.append(result)

    ri = {"fully_resolved": "F", "partially_resolved": "P", "not_resolved": "N"}.get(ev["status"], "?")
    print(f"| Sub:{'S' if sub_ok else 'X'} Int:{'I' if int_ok else 'X'} Res:{ri} | {lat}ms | {ev['reason'][:35]}")

    # Save progress after each ticket
    os.makedirs("download", exist_ok=True)
    with open(results_file, "w") as f:
        json.dump(existing, f, indent=2, default=str)

# Final metrics
n = len(existing)
if n > 0:
    contained_n = len([r for r in existing if r["contained"]])
    sub_ok_n = len([r for r in existing if r["sub_ok"]])
    int_ok_n = len([r for r in existing if r["int_ok"]])
    fully_n = len([r for r in existing if r["resolution"] == "fully_resolved"])
    partial_n = len([r for r in existing if r["resolution"] == "partially_resolved"])
    not_res_n = len([r for r in existing if r["resolution"] == "not_resolved"])
    true_res_n = len([r for r in existing if r["int_ok"] and r["resolution"] == "fully_resolved"])
    ind_res_n = len([r for r in existing if r["contained"] and r["resolution"] in ("fully_resolved", "partially_resolved")])
    int_cont_n = len([r for r in existing if r["int_ok"] and r["contained"]])

    print()
    print("=" * 60)
    print(f"EMPIRICAL RESULTS ({n} tickets processed)")
    print("=" * 60)
    print(f"Containment Rate:             {contained_n/n*100:.1f}%")
    print(f"Subgraph Routing Accuracy:    {sub_ok_n/n*100:.1f}%")
    print(f"Intent Accuracy:              {int_ok_n/n*100:.1f}%")
    print(f"Intent-Correct Containment:   {int_cont_n/n*100:.1f}%")
    print(f"Fully Resolved:               {fully_n/n*100:.1f}%")
    print(f"Partially Resolved:           {partial_n/n*100:.1f}%")
    print(f"Not Resolved:                 {not_res_n/n*100:.1f}%")
    print(f"True Resolution Rate:         {true_res_n/n*100:.1f}%")
    print(f"Industry-Comparable Rate:     {ind_res_n/n*100:.1f}%")

    # Save final results
    final = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": "empirical_nvidia_deepseek",
        "total_tickets": n,
        "metrics": {
            "containment_rate": round(contained_n/n*100, 2),
            "subgraph_routing_accuracy": round(sub_ok_n/n*100, 2),
            "intent_accuracy": round(int_ok_n/n*100, 2),
            "intent_correct_containment_rate": round(int_cont_n/n*100, 2),
            "fully_resolved_rate": round(fully_n/n*100, 2),
            "partially_resolved_rate": round(partial_n/n*100, 2),
            "not_resolved_rate": round(not_res_n/n*100, 2),
            "true_resolution_rate": round(true_res_n/n*100, 2),
            "industry_comparable_rate": round(ind_res_n/n*100, 2),
        },
        "per_ticket_results": existing,
    }
    with open("download/empirical_resolution_rate_results.json", "w") as f:
        json.dump(final, f, indent=2, default=str)
    print("Saved to download/empirical_resolution_rate_results.json")
