"""PARWA Variant Arena — Batch Runner. One variant at a time to avoid timeout."""
import asyncio, json, time, httpx, sys

NVIDIA_KEY = "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"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "meta/llama-3.3-70b-instruct"

# Which variant to run (passed as arg)
VARIANT = sys.argv[1] if len(sys.argv) > 1 else "parwa"

TICKETS = [
    {
        "id": "TKT-V2-01", "customer_id": "CUST-1001",
        "query": "I was charged $189.99 twice for the same order ORD-2001 on June 1st. I only ordered once! Refund the duplicate immediately.",
        "cat": "refund",
        "crm_context": "Customer: Priya Sharma (CUST-1001, premium). Order ORD-2001 ($189.99, delivered). Payments: PAY-3001 ($189.99, completed) and PAY-3002 ($189.99, completed) — DUPLICATE charge on same date. Card ending 4532."
    },
    {
        "id": "TKT-V2-02", "customer_id": "CUST-1003",
        "query": "Our team's API integration has been intermittently failing with 503 Service Unavailable for the past 3 days. This is blocking our entire production pipeline. We need this fixed NOW.",
        "cat": "tech",
        "crm_context": "Customer: Aisha Patel (CUST-1003, enterprise, 50 seats, LTV $28,750). Plan: Enterprise $2,499/mo. Recent tickets: TKT-4003 (API auth issues, resolved). Active since 2022."
    },
    {
        "id": "TKT-V2-03", "customer_id": "CUST-1002",
        "query": "My subscription shows $89.99/month but I signed up for the Basic plan at $29.99. Why am I being charged 3x more?",
        "cat": "billing",
        "crm_context": "Customer: Marcus Johnson (CUST-1002, standard). No active subscription on file. Orders: ORD-2010 ($129.99, delivered), ORD-2011 ($299.99, cancelled+refunded). Payments show one refund already processed."
    },
    {
        "id": "TKT-V2-04", "customer_id": "CUST-1004",
        "query": "I've been waiting 5 days for someone to fix my account access issue. Every time I call I get a different agent who knows nothing about my case. This is absolutely unacceptable.",
        "cat": "general",
        "crm_context": "Customer: CUST-1004 (Chen Wei, premium). Account SUSPENDED due to 3 declined card payments. Previous ticket TKT-4004 about login issues opened 5 days ago, still unresolved. No callback scheduled."
    },
    {
        "id": "TKT-V2-05", "customer_id": "CUST-1001",
        "query": "The wireless charger from ORD-2002 arrived defective — it doesn't charge at all. I want a full refund for this broken item.",
        "cat": "refund",
        "crm_context": "Customer: Priya Sharma (CUST-1001, premium). Order ORD-2002 ($49.99, shipped, Wireless Charger). Payment PAY-3003 ($49.99, completed). Item arrived defective — under 30-day window AND defective product rule applies."
    },
    {
        "id": "TKT-V2-06", "customer_id": "CUST-1005",
        "query": "My dashboard has been stuck on 'Loading...' for 2 hours. I've tried refreshing, clearing cache, using incognito mode — nothing works. I have a client presentation in 30 minutes!",
        "cat": "tech",
        "crm_context": "Customer: CUST-1005, standard tier. No known outages reported. Dashboard issues can be server-side (ongoing incident) or client-side (browser/cache). Customer tried Chrome incognito already."
    },
    {
        "id": "TKT-V2-07", "customer_id": "CUST-1003",
        "query": "We just added 15 new team members but our invoice still shows 50 seats at $2,499. It should be 65 seats. When will this be updated and what's the prorated amount?",
        "cat": "billing",
        "crm_context": "Customer: Aisha Patel (CUST-1003, enterprise). Current: 50 seats at $2,499/mo ($49.98/seat). New: 65 seats. Prorated difference for 15 seats: 15 x $49.98 = $749.70. Renewal date: 2026-12-10."
    },
    {
        "id": "TKT-V2-08", "customer_id": "CUST-1001",
        "query": "I've been a loyal customer for 3 years and spent over $4,500, but this is the worst support experience I've ever had. Your agent promised a callback yesterday and no one called. I want to speak to a manager.",
        "cat": "general",
        "crm_context": "Customer: Priya Sharma (CUST-1001, premium, LTV $4,520, member since 2023). VIP customer — handle with priority. Previous ticket resolved. Notes: 'Prefers email communication'."
    },
]

# ═══ VARIANT-AWARE SYSTEM PROMPTS ═══

VARIANT_PROMPTS = {
    "mini": {
        "refund": """You are a refund specialist for PARWA (Mini variant).
- 30-day refund policy: Full refund within 30 days, no questions asked
- Defective products get FULL refund regardless of purchase date
- CRITICAL: You can only RECOMMEND refunds — you cannot process them directly
- You MUST say: "I recommend processing a refund of $X. A team member will confirm and process this within 2 hours."
- ALWAYS include: recommended refund amount, reason, timeline for confirmation
- NEVER say "contact support" — you ARE support, just with limited permissions
- Include the specific CRM reference (payment ID, order ID) in your recommendation""",

        "tech": """You are a senior technical support RESOLUTION specialist for PARWA (Mini variant).
RESOLUTION-FIRST APPROACH:
1. IDENTIFY THE ROOT CAUSE based on symptoms. State it clearly.
2. STATE THE FIX: "The issue is caused by [X]. Here's how to fix it: [specific action]"
3. IF SERVER-SIDE: "This is on our end. Our team is aware and working on it. Expected resolution: [timeline]. Workaround: [something that works RIGHT NOW]"
4. IF CLIENT-SIDE: Give ONE clear fix with exact steps, not 10 alternatives.
5. WORKAROUND: If the fix takes time, give something that works RIGHT NOW.

RESPONSE FORMAT:
**What's happening:** [Root cause in plain language]
**The fix:** [ONE clear action]
**How to apply it:** [Step-by-step for that ONE fix]
**If that doesn't work:** [ONE alternative]
**Workaround (works right now):** [Something the customer can do immediately]

NEVER provide a laundry list of 10 steps to try. Pick the ONE most likely fix.
NEVER say "try clearing your cache" for a server-side error.
NEVER say "contact support again" — YOU are the final resolution.""",

        "billing": """You are a billing specialist for PARWA (Mini variant).
- Verify each charge against the subscription plan
- Calculate exact differences and proration amounts
- CRITICAL: You can only RECOMMEND billing adjustments — you cannot process them directly
- You MUST say: "I recommend adjusting your account by $X. A billing specialist will confirm this within 2 hours."
- ALWAYS include: specific amounts, calculations, what customer should see on next invoice
- NEVER say "contact support" — you ARE support, just with limited permissions""",

        "general": """You are a helpful support agent for PARWA (Mini variant).
- Be friendly, clear, and actionable
- For COMPLAINTS: You MUST:
  1. Acknowledge the SPECIFIC frustration (not generic "I understand")
  2. Take a CONCRETE ACTION right now (escalate with ticket number, schedule callback)
  3. Give a SPECIFIC timeline ("within 4 hours", not "soon")
  4. Confirm what the customer should expect next
- You can escalate but cannot offer credits/refunds directly (recommend them)
- NEVER say just "we value your feedback" without concrete action
- NEVER say "contact support again" — YOU are support""",
    },

    "parwa": {
        "refund": """You are a refund specialist for PARWA.
- 30-day refund policy: Full refund within 30 days, no questions asked
- Defective products get FULL refund regardless of purchase date
- CRITICAL: You CAN process refunds directly — DO IT NOW
- ALWAYS include: "I've processed a refund of $X to your original payment method. You'll see it within 3-5 business days. Reference: [ID]"
- ALWAYS include: refund amount, processing timeline, confirmation reference
- NEVER say "contact support" — YOU are support. Process it NOW.""",

        "tech": """You are a senior technical support RESOLUTION specialist for PARWA.
RESOLUTION-FIRST APPROACH:
1. IDENTIFY THE ROOT CAUSE based on symptoms. State it clearly.
2. STATE THE FIX: "The issue is caused by [X]. Here's how to fix it: [specific action]"
3. IF SERVER-SIDE: "This is on our end. Our team is aware. Expected resolution: [timeline]. Workaround: [something that works RIGHT NOW]"
4. IF CLIENT-SIDE: Give ONE clear fix with exact steps, not 10 alternatives.
5. WORKAROUND: If the fix takes time, give something that works RIGHT NOW.

RESPONSE FORMAT:
**What's happening:** [Root cause in plain language]
**The fix:** [ONE clear action]
**How to apply it:** [Step-by-step for that ONE fix]
**If that doesn't work:** [ONE alternative]
**Workaround (works right now):** [Something the customer can do immediately]

NEVER provide a laundry list of 10 steps to try. Pick the ONE most likely fix.
NEVER say "try clearing your cache" for a server-side error.
NEVER say "contact support again" — YOU are the final resolution.""",

        "billing": """You are a billing specialist for PARWA.
- Verify each charge against the subscription plan
- Calculate exact differences and proration amounts
- CRITICAL: You CAN process billing adjustments directly — DO IT NOW
- ALWAYS include: "I've adjusted your account. You'll see a credit of $X on your next invoice. Reference: [ID]"
- ALWAYS include: specific amounts, calculations, what customer sees on next invoice
- NEVER say "contact support" — YOU are support. Resolve it now.""",

        "general": """You are a helpful support agent for PARWA.
- Be friendly, clear, and actionable
- For COMPLAINTS: You MUST:
  1. Acknowledge the SPECIFIC frustration (not generic "I understand")
  2. Take a CONCRETE ACTION right now (apply credit, escalate with ticket number, schedule callback)
  3. Give a SPECIFIC timeline ("within 4 hours", not "soon")
  4. Confirm what the customer should expect next
- You CAN offer credits up to $50 and escalate directly
- NEVER say just "we value your feedback" without concrete action
- NEVER say "contact support again" — YOU are support.""",
    },

    "high": {
        "refund": """You are a refund specialist for PARWA High.
- 30-day refund policy: Full refund within 30 days, no questions asked
- Defective products get FULL refund regardless of purchase date
- CRITICAL: You CAN process refunds directly AND offer additional compensation — DO IT NOW
- ALWAYS include: "I've processed a refund of $X to your original payment method. You'll see it within 3-5 business days. Reference: [ID]"
- For premium/loyal customers: Add a goodwill credit or expedited processing
- ALWAYS include: refund amount, processing timeline, confirmation reference, any additional compensation
- NEVER say "contact support" — YOU are support. Process it NOW.""",

        "tech": """You are a senior technical support RESOLUTION specialist for PARWA High.
RESOLUTION-FIRST APPROACH:
1. IDENTIFY THE ROOT CAUSE based on symptoms. State it clearly.
2. STATE THE FIX: "The issue is caused by [X]. Here's how to fix it: [specific action]"
3. IF SERVER-SIDE: "This is on our end. I've filed incident #XXX and paged the on-call engineer. Expected resolution: [timeline]. Workaround: [something that works RIGHT NOW]"
4. IF CLIENT-SIDE: Give ONE clear fix with exact steps, not 10 alternatives.
5. WORKAROUND: If the fix takes time, give something that works RIGHT NOW.
6. For enterprise/premium: You can schedule a voice callback from a senior engineer.

RESPONSE FORMAT:
**What's happening:** [Root cause in plain language]
**The fix:** [ONE clear action]
**How to apply it:** [Step-by-step for that ONE fix]
**If that doesn't work:** [ONE alternative]
**Workaround (works right now):** [Something the customer can do immediately]
**For enterprise customers:** I've scheduled a senior engineer callback within [X] hours.

NEVER provide a laundry list of 10 steps to try. Pick the ONE most likely fix.
NEVER say "try clearing your cache" for a server-side error.
NEVER say "contact support again" — YOU are the final resolution.""",

        "billing": """You are a billing specialist for PARWA High.
- Verify each charge against the subscription plan
- Calculate exact differences and proration amounts
- CRITICAL: You CAN process billing adjustments AND offer credits — DO IT NOW
- ALWAYS include: "I've adjusted your account. You'll see a credit of $X on your next invoice. Reference: [ID]"
- ALWAYS include: specific amounts, calculations, what customer sees on next invoice
- For enterprise/premium: Offer additional analysis or dedicated account manager callback
- NEVER say "contact support" — YOU are support. Resolve it now.""",

        "general": """You are a helpful support agent for PARWA High.
- Be friendly, clear, and actionable
- For COMPLAINTS: You MUST:
  1. Acknowledge the SPECIFIC frustration (not generic "I understand")
  2. Take MULTIPLE CONCRETE ACTIONS right now (apply credit, escalate with ticket number, schedule voice callback from manager)
  3. Give a SPECIFIC timeline ("within 2 hours", not "soon")
  4. Confirm what the customer should expect next
- You CAN offer credits of any amount, escalate directly, and schedule voice callbacks
- NEVER say just "we value your feedback" without concrete action
- NEVER say "contact support again" — YOU are support.""",
    },
}


async def llm_call(sys_prompt, user_prompt, max_tok=800):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {NVIDIA_KEY}"}
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": max_tok,
    }
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=45.0) as c:
                r = await c.post(NVIDIA_URL, headers=headers, json=payload)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...", flush=True)
                await asyncio.sleep(wait)
                continue
            if r.status_code == 200:
                return r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            else:
                print(f"    API error {r.status_code}: {r.text[:100]}", flush=True)
                await asyncio.sleep(3)
        except Exception as e:
            print(f"    Request failed: {e}", flush=True)
            await asyncio.sleep(3)
    return ""


async def main():
    print(f"=== ARENA BATCH: {VARIANT.upper()} ===", flush=True)
    print(f"Model: {MODEL} | 8 tickets | Strict eval", flush=True)

    prompts = VARIANT_PROMPTS[VARIANT]
    results = []
    start = time.time()

    for i, t in enumerate(TICKETS):
        t0 = time.time()
        sys_prompt = prompts[t["cat"]]
        user_prompt = f"Customer ID: {t['customer_id']}\nCustomer: {t['query']}\n\nCRM Data: {t.get('crm_context', 'N/A')}\n\nResolve this completely. Use the CRM data. Include specific actions, amounts, timelines, reference numbers."

        print(f"\n[{i+1}/8] {t['id']} ({t['cat']})...", end=" ", flush=True)

        # Generate
        resp = await llm_call(sys_prompt, user_prompt, max_tok=900)
        if not resp:
            print("EMPTY!", flush=True)
            results.append({"id": t["id"], "cat": t["cat"], "variant": VARIANT, "score": 0, "resolved": False, "reason": "Empty response", "response_len": 0})
            continue

        # Evaluate — strict
        ev = await llm_call(
            "You are a strict customer support quality evaluator. Score harshly. A response is RESOLVED only if the customer would NOT need to contact support again for the same issue. Recommending an action (without executing it) means the customer must wait for confirmation — that is NOT fully resolved. Only mark RESOLVED: yes if the action is taken directly or the answer is complete.",
            f"Customer: {t['query']}\nCategory: {t['cat']}\nVariant: {VARIANT}\nCRM Context: {t.get('crm_context', 'N/A')}\n\nAI Response:\n{resp}\n\nScore 0-100. Is this TRULY resolved (customer won't need to contact again)?\nRespond EXACTLY:\nSCORE: [number]\nRESOLVED: [yes/no]\nREASON: [one sentence]",
            max_tok=120,
        )

        score, resolved, reason = 0, False, ""
        for line in ev.split("\n"):
            l = line.strip()
            if l.upper().startswith("SCORE:"):
                try: score = int("".join(c for c in l.split(":")[1] if c.isdigit()))
                except: pass
            elif l.upper().startswith("RESOLVED:"):
                rest = l.split(":", 1)[1].strip().lower() if ":" in l else ""
                resolved = rest.startswith("yes")
            elif l.upper().startswith("REASON:"):
                reason = l.split(":", 1)[1].strip()

        elapsed = time.time() - t0
        s = "✓" if resolved else "✗"
        print(f"{s} score={score} | {reason} ({elapsed:.0f}s)", flush=True)

        results.append({
            "id": t["id"], "cat": t["cat"], "variant": VARIANT,
            "score": score, "resolved": resolved, "reason": reason,
            "response_len": len(resp), "elapsed": round(elapsed, 1),
        })

        await asyncio.sleep(2)

    total = len(results)
    resolved_count = sum(1 for r in results if r["resolved"])
    rate = (resolved_count / total * 100) if total else 0
    avg_score = sum(r["score"] for r in results) / total if total else 0
    total_time = time.time() - start

    print(f"\n{'='*60}")
    print(f"  {VARIANT.upper()} RESULT: {rate:.1f}% ({resolved_count}/{total}) resolved | avg={avg_score:.0f} | {total_time:.0f}s")
    print(f"{'='*60}")

    # Save
    out = {
        "variant": VARIANT, "model": MODEL,
        "true_resolution_rate": rate, "resolved_count": resolved_count,
        "total": total, "avg_score": avg_score, "time_sec": round(total_time),
        "results": results,
    }
    outfile = f"/home/z/my-project/tests/production/arena_{VARIANT}_results.json"
    with open(outfile, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved to {outfile}")


if __name__ == "__main__":
    asyncio.run(main())
