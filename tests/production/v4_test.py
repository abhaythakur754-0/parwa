"""PARWA v4 Test — 8 NEW tickets, fixed prompts, Llama model, honest evaluation"""
import httpx, time, json

KEY = "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"
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"}
MODEL = "meta/llama-3.3-70b-instruct"

# 8 BRAND NEW TICKETS — different from previous test
TICKETS = [
    {"id": "REF-10", "query": "I cancelled my subscription 2 weeks ago but I just got charged $49.99 again. This is the third time!", "cat": "refund"},
    {"id": "REF-11", "query": "The software crashes every time I open it. I bought it last week. I want all my money back.", "cat": "refund"},
    {"id": "TECH-10", "query": "Getting 401 Unauthorized on all my API calls since this morning. My token was working yesterday.", "cat": "tech"},
    {"id": "TECH-11", "query": "The mobile app keeps freezing on the login screen. I've reinstalled it twice already.", "cat": "tech"},
    {"id": "BILL-10", "query": "My invoice shows a $19.99 charge for something called 'API Add-on' but I never signed up for that.", "cat": "billing"},
    {"id": "BILL-11", "query": "I upgraded from Basic to Pro yesterday. Why am I being charged the full Pro price instead of the difference?", "cat": "billing"},
    {"id": "GEN-10", "query": "How do I export my data from your platform? I need it in CSV format.", "cat": "general"},
    {"id": "GEN-11", "query": "I've been waiting 3 days for a response to my previous ticket. This is absolutely unacceptable service!", "cat": "general"},
]

# v4 FIXED PROMPTS
PROMPTS = {
    "refund": """You are a refund specialist for PARWA. Your job is to PROCESS refunds immediately.
Rules:
- 30-day full refund, no questions asked
- Defective product = FULL refund regardless of date
- Subscription cancelled but still charged = immediate full refund of erroneous charge
- ALWAYS include: exact refund amount, processing timeline (3-5 business days), confirmation reference
- NEVER say "contact support again" — YOU are support, act NOW
- For repeated billing after cancellation: refund ALL erroneous charges + confirm cancellation is active""",

    "tech": """You are a RESOLUTION specialist, NOT a troubleshooting guide writer. RESOLVE the issue.

CRITICAL RULES:
- For 5xx errors (503, 500, etc.): This is SERVER-SIDE. Say "This is on our end." Give timeline and workaround. NEVER say "clear your cache."
- For 401/auth errors: Token likely expired or revoked. Give the EXACT fix: "Regenerate your API key at Settings > API Keys > Generate New Key. Your old key has been revoked."
- For app freezing/crashing: Identify likely cause (corrupted cache, version mismatch, account sync issue). Give ONE fix with exact steps.
- For dashboard/site not loading: Server-side issue. Acknowledge, give timeline, provide workaround (use API directly or mobile app).
- ALWAYS include: root cause identification, ONE clear fix, workaround for immediate relief, timeline/expected outcome
- NEVER list 10 steps to try. Pick the ONE most likely fix.
- NEVER say "contact support again" — YOU are the resolution""",

    "billing": """You are a billing specialist for PARWA. Resolve billing issues immediately.
Rules:
- Verify charges against the customer's plan
- For unknown charges: Investigate, explain, and process credit if incorrect
- For proration questions: Calculate exact amount with math shown
- ALWAYS include: specific dollar amounts, what appears on next invoice, timeline
- For double/erroneous charges: Immediate credit + explanation
- NEVER say "contact support again" — YOU are support""",

    "general": """You are a support agent for PARWA. RESOLVE issues, don't just acknowledge them.

For COMPLAINTS (angry customer, slow response, bad service):
- Acknowledge the SPECIFIC frustration
- Take a CONCRETE ACTION right now: escalate with ticket number, apply credit, schedule callback
- Give a SPECIFIC timeline (not "soon" — "within 4 hours")
- Confirm what the customer should expect next

For HOW-TO questions:
- Give the EXACT steps to complete the task
- Include specific URLs, menu paths, or buttons to click
- Confirm the expected result

NEVER say "contact support again" — YOU are support.
Every response must include at least ONE of: confirmation number, specific timeline, credit amount, or exact action taken.""",
}

EVAL_SYSTEM = """You are a strict, harsh customer support quality evaluator.
Only give high scores if the response TRULY RESOLVES the issue so the customer does NOT need to contact support again.
A response that just lists things to try = NOT resolved.
A response with only empathy and no concrete action = NOT resolved.
Be honest and strict."""


def llm_call(system_prompt, user_prompt, max_tokens=800):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    for attempt in range(2):
        try:
            r = httpx.post(URL, headers=HEADERS, json=payload, timeout=35.0)
            if r.status_code == 429:
                time.sleep(3)
                continue
            if r.status_code == 200:
                return r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            time.sleep(2)
        except:
            time.sleep(2)
    return ""


def parse_eval(raw):
    score, resolved, reason = 0, False, ""
    for line in raw.split("\n"):
        l = line.strip()
        if l.upper().startswith("SCORE:"):
            try:
                score = int("".join(c for c in l.split(":")[1] if c.isdigit()))
            except:
                pass
        elif l.upper().startswith("RESOLVED:"):
            rest = l.split(":", 1)[1].strip().lower() if ":" in l else ""
            resolved = rest.startswith("yes")
        elif l.upper().startswith("REASON:"):
            reason = l.split(":", 1)[1].strip()
    return score, resolved, reason


def test_ticket(t):
    print(f"\n{t['id']} ({t['cat']})...", flush=True)

    # Generate
    resp = llm_call(
        PROMPTS[t["cat"]],
        f"Customer: {t['query']}\n\nResolve this completely. Include specific actions, amounts, timelines, reference numbers."
    )
    if not resp:
        print(f"  ⚠️ Empty response!", flush=True)
        return {"id": t["id"], "cat": t["cat"], "score": 0, "resolved": False, "reason": "Empty LLM response"}

    print(f"  ({len(resp)} chars) {resp[:100]}...", flush=True)
    time.sleep(1)

    # Evaluate
    ev = llm_call(
        EVAL_SYSTEM,
        f"Customer: {t['query']}\nCategory: {t['cat']}\n\nAI Response:\n{resp}\n\nScore 0-100. Is this TRULY resolved (customer won't need to contact again for the SAME issue)?\nRespond EXACTLY:\nSCORE: [number]\nRESOLVED: [yes/no]\nREASON: [one sentence]",
        max_tokens=120,
    )

    score, resolved, reason = parse_eval(ev)
    s = "✓" if resolved else "✗"
    print(f"  {s} Score={score} | {reason}", flush=True)
    return {"id": t["id"], "cat": t["cat"], "score": score, "resolved": resolved, "reason": reason}


results = []
for t in TICKETS:
    r = test_ticket(t)
    results.append(r)
    time.sleep(1)

# Summary
total = len(results)
resolved_count = sum(1 for r in results if r["resolved"])
above_80 = sum(1 for r in results if r["score"] >= 80)
above_60 = sum(1 for r in results if r["score"] >= 60)
rate = (resolved_count / total * 100) if total else 0
avg = sum(r["score"] for r in results) / total if total else 0

print(f"\n{'='*60}")
print(f"  PARWA v4 RESULTS — 8 NEW TICKETS")
print(f"{'='*60}")
print(f"\n  TRUE RESOLUTION RATE:  {rate:.1f}% ({resolved_count}/{total})")
print(f"  SCORE >= 80:           {above_80}/{total}")
print(f"  SCORE >= 60:           {above_60}/{total}")
print(f"  AVG EVAL SCORE:        {avg:.0f}/100")

print(f"\n  BY SUBGRAPH:")
for cat in ["refund", "tech", "billing", "general"]:
    cr = [r for r in results if r["cat"] == cat]
    if cr:
        n = sum(1 for r in cr if r["resolved"])
        a = sum(r["score"] for r in cr) / len(cr)
        print(f"    {cat:12s}: {n}/{len(cr)} resolved ({n/len(cr)*100:.0f}%) | avg={a:.0f}")

print(f"\n  PER TICKET:")
for r in results:
    s = "✓ RESOLVED" if r["resolved"] else "✗ FAILED  "
    print(f"    {r['id']} [{r['cat']:7s}] score={r['score']:3d}  {s}")
    print(f"      → {r['reason']}")

with open("/home/z/my-project/tests/production/v4_new_tickets_results.json", "w") as f:
    json.dump({"true_resolution_rate": rate, "avg_eval": avg, "results": results}, f, indent=2)
print(f"\n  Saved to v4_new_tickets_results.json")
