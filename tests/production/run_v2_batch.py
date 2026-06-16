"""Quick batch runner for v2 empirical test — processes 3 tickets at a time."""
import httpx, json, time, os, sys
from datetime import datetime, timezone

KEY = os.environ.get("NVIDIA_API_KEY", "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")
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DELAY = 3

def chat(sys_p, user_p, max_tokens=400, temp=0.2):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"}
    models = ["z-ai/glm-5.1", "deepseek-ai/deepseek-v4-flash", "meta/llama-3.3-70b-instruct"]
    for model in models:
        for attempt in range(2):
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": user_p}],
                    "max_tokens": max_tokens, "temperature": temp,
                }
                r = httpx.post(URL, headers=headers, json=payload, timeout=45)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
                elif r.status_code == 429:
                    print(f"(429-{model.split('/')[-1]}) ", end="", flush=True)
                    time.sleep(10 + attempt * 5)
                else:
                    time.sleep(3)
            except Exception as e:
                print(f"(err) ", end="", flush=True)
                time.sleep(5)
    return ""


def parse_eval(text):
    try:
        t = text.strip()
        if "```json" in t:
            t = t.split("```json")[1].split("```")[0].strip()
        elif "```" in t:
            t = t.split("```")[1].split("```")[0].strip()
        d = json.loads(t)
        status = d.get("resolution_status", "not_resolved")
        if status not in ("fully_resolved", "partially_resolved", "not_resolved"):
            status = "not_resolved"
        return {
            "status": status,
            "intent_match": bool(d.get("intent_match", False)),
            "actionable": bool(d.get("actionable", False)),
            "quality_score": min(100, max(0, int(d.get("quality_score", 50)))),
            "reason": d.get("reason", ""),
        }
    except Exception:
        status = "not_resolved"
        if "fully_resolved" in text:
            status = "fully_resolved"
        elif "partially_resolved" in text:
            status = "partially_resolved"
        return {"status": status, "intent_match": False, "actionable": False, "quality_score": 40, "reason": "parse fallback"}


# ─── Prompts ──────────────────────────────────────────────────────────────────
ROUTE_P = """Classify the customer message into one category: refund, tech, billing, general.

RULES:
- Cancel subscription + charges = refund
- Charged after cancellation = refund
- API returning errors / app crashing = tech
- Do you have an API? = general (question, not tech problem)
- Charged twice / wrong amount = billing (unless explicitly asking for money back)
- Complaints about service quality = general
- Legal threats = general

Respond with ONLY the category name."""

INTENT_P = """Classify the customer intent into one: refund, cancellation, billing, technical, complaint, shipping, account, general, escalation, order_status.

Respond with ONLY the intent name."""

RESP = {
    "refund": """You are a refund policy specialist for PARWA. Rules:
- 30-day full refund, no questions asked
- 31-60 day partial (50-75%) BUT defective products get FULL refund regardless of date
- After 60 days: full refund for defective products, partial for billing errors only
- Subscription refunds: prorated from cancellation date
- Accidental plan purchase: refund difference immediately
- Charged after cancellation: immediate full refund + confirm cancellation

CRITICAL: Process the refund NOW with EXACT amount and timeline. Do NOT say "contact support".
State the exact refund amount and when it will arrive. Be empathetic for angry customers.
3-4 sentences with specific amounts and dates.""",

    "tech": """You are a senior technical support specialist for PARWA. Rules:
- Start with simplest fix (clear cache, restart, re-login)
- Give SPECIFIC steps with exact UI paths or commands
- Provide a WORKAROUND the customer can use immediately
- If fix might not work, provide alternative approach
- For API issues: check auth, rate limits, payload, endpoint URL
- For login issues: check account status, then cache, then password reset
- For performance: check network, browser, server status
- For SSL/cert: check system time, cert chain, proxy/firewall

MANDATORY: Include at least 3 specific steps AND a workaround.
NEVER say "contact support" without providing complete resolution first.
4-5 sentences with specific actionable steps.""",

    "billing": """You are a billing specialist for PARWA. Rules:
- Verify charges against subscription plan
- Show exact amounts with line items
- Charged twice: Immediately acknowledge, verify, process duplicate refund
- Unauthorized charges: Flag for investigation AND provide immediate credit
- Proration: Explain with exact numbers
- Failed payments: Check card status, offer retry options

CRITICAL: Show exact dollar amounts. Process adjustments immediately.
Do NOT say "contact support". Resolve it now. 3-4 sentences with specific amounts.""",

    "general": """You are a helpful customer support agent for PARWA. Rules:
- For complaints: Acknowledge frustration FIRST, then offer SPECIFIC resolution action
- For legal threats: Do NOT give legal advice. Route to compliance team.
- For account changes: Give exact steps or process directly
- For plan comparisons: Give specific feature and price differences
- NEVER say just "I'm sorry you're frustrated" without concrete next step
- NEVER say "contact support". YOU are support. 3-4 sentences.""",
}

EVAL_P = """Judge if this support response actually resolves the customer problem. Be brutally honest.

Evaluation criteria:
- fully_resolved: Customer can take action immediately AND response addresses their core problem. Must provide actual resolution or actionable steps, not just "we're looking into it".
- partially_resolved: Response provides useful info or partial steps, but customer still needs to do something or wait. "We've initiated a refund arriving in 3-5 days" = partially (customer waits).
- not_resolved: Empathetic but doesn't address the problem, or tells customer to contact support again.

Special rules:
- Tech responses must include specific steps + workaround to be fully_resolved
- Refund responses must state exact amount + timeline to be fully_resolved
- Billing responses must show exact amounts to be fully_resolved
- Complaints must offer concrete resolution (not just empathy) to be at least partially_resolved
- "Please contact support again" = not_resolved

JSON only:
{"resolution_status": "fully_resolved"/"partially_resolved"/"not_resolved", "intent_match": true/false, "actionable": true/false, "quality_score": 0-100, "reason": "brief"}"""


# ─── ALL 30 TICKETS ───────────────────────────────────────────────────────────
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
    ("T-006","Getting SSL certificate errors when connecting to your API endpoint from our EU servers.","tech","technical","neutral"),
    ("T-007","Your mobile app will not open on my iPhone 15. Crashes immediately on launch.","tech","technical","frustrated"),
    ("B-001","You charged me twice for the same order! Two charges of $149.99 on my card statement.","billing","billing","angry"),
    ("B-002","My invoice shows a different amount than what I was quoted. The tax calculation seems wrong.","billing","billing","neutral"),
    ("B-003","I upgraded from Starter to Pro last week but my invoice still shows the Starter price.","billing","billing","frustrated"),
    ("B-004","There is an unauthorized transaction of $3,450 on my account. Investigate immediately.","billing","billing","angry"),
    ("B-005","Can you explain the proration on my latest invoice? I do not understand the mid-cycle upgrade charge.","billing","billing","neutral"),
    ("B-006","My payment failed but my card is working fine everywhere else. What is wrong with your system?","billing","billing","frustrated"),
    ("B-007","I need a receipt for my annual subscription payment for tax purposes.","billing","billing","neutral"),
    ("G-001","What are your business hours? I need to know when I can reach a live agent.","general","general","neutral"),
    ("G-002","How do I change my email address on my account?","general","account","neutral"),
    ("G-003","I am very disappointed with the service. The agent was rude and unhelpful.","general","complaint","angry"),
    ("G-004","Do you offer an API for integrating with Salesforce?","general","general","neutral"),
    ("G-005","I am going to sue your company for selling my data without consent.","general","escalation","angry"),
    ("G-006","Can you tell me the status of my order #ORD-98234?","general","order_status","neutral"),
    ("G-007","I have been a loyal customer for 3 years and this is how you treat me? I want to speak to a manager.","general","escalation","angry"),
    ("G-008","What is the difference between your Starter and Pro plans?","general","general","neutral"),
]

# ─── Process tickets ──────────────────────────────────────────────────────────
# START and END from command line args: python run_v2_batch.py START END
start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
end_idx = int(sys.argv[2]) if len(sys.argv) > 2 else len(ALL)
tickets = ALL[start_idx:end_idx]

results_file = "/home/z/my-project/download/v2_empirical_progress.json"
existing = []
if os.path.exists(results_file):
    with open(results_file) as f:
        existing = json.load(f)
    print(f"Loaded {len(existing)} existing results")

print(f"PARWA v2 Batch: tickets {start_idx}-{end_idx-1} ({len(tickets)} tickets)")
print("=" * 60)

for i, (tid, q, es, ei, em) in enumerate(tickets):
    if any(r["id"] == tid for r in existing):
        print(f"  {tid} already done, skip")
        continue

    print(f"[{len(existing)+1}/30] {tid} ", end="", flush=True)
    t0 = time.monotonic()

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
        sys_p += " IMPORTANT: Customer is ANGRY/URGENT. Show strong empathy first, then resolve."
    elif em == "frustrated":
        sys_p += " Customer is FRUSTRATED. Acknowledge frustration, then provide complete resolution."
    time.sleep(DELAY)
    response = chat(sys_p, q, 500, 0.3)

    # Evaluate
    time.sleep(DELAY)
    ev_text = chat(EVAL_P, f"Expected intent: {ei}\nCustomer: {q}\nResponse: {response}", 200, 0.1)
    ev = parse_eval(ev_text)

    lat = round((time.monotonic() - t0) * 1000)
    sub_ok = pred_sub == es
    int_ok = pred_int == ei
    contained = "sue" not in q.lower() and ev["status"] != "not_resolved"

    result = {
        "id": tid, "expected_sub": es, "pred_sub": pred_sub, "sub_ok": sub_ok,
        "expected_intent": ei, "pred_int": pred_int, "int_ok": int_ok,
        "resolution": ev["status"], "intent_match": ev["intent_match"],
        "actionable": ev["actionable"], "quality_score": ev["quality_score"],
        "reason": ev["reason"], "contained": contained,
        "response": response[:300], "lat_ms": lat,
    }
    existing.append(result)

    ri = {"fully_resolved": "FULL", "partially_resolved": "PART", "not_resolved": "NOT"}.get(ev["status"], "?")
    print(f"-> Sub:{'OK' if sub_ok else 'XX'} Int:{'OK' if int_ok else 'XX'} Res:{ri} Q:{ev['quality_score']} | {ev['reason'][:50]}")

    # Save after each ticket
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    with open(results_file, "w") as f:
        json.dump(existing, f, indent=2, default=str)

print(f"\nDone. {len(existing)} total results saved.")
