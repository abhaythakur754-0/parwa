"""PARWA Arena — Micro batch. 2 tickets per run to avoid timeout."""
import asyncio, json, time, httpx, sys

NVIDIA_KEY = "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"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "meta/llama-3.3-70b-instruct"

VARIANT = sys.argv[1]
T_START = int(sys.argv[2])  # 0-based start index
T_END = int(sys.argv[3])    # exclusive end index

ALL_TICKETS = [
    {"id":"TKT-01","customer_id":"CUST-1001","query":"I was charged $189.99 twice for the same order ORD-2001 on June 1st. I only ordered once! Refund the duplicate immediately.","cat":"refund","crm":"Priya Sharma (CUST-1001, premium). Order ORD-2001 $189.99 delivered. Payments: PAY-3001 $189.99 completed, PAY-3002 $189.99 completed — DUPLICATE. Card ending 4532."},
    {"id":"TKT-02","customer_id":"CUST-1003","query":"Our API integration has been intermittently failing with 503 errors for 3 days. This is blocking our entire production pipeline. Fix it NOW.","cat":"tech","crm":"Aisha Patel (CUST-1003, enterprise, 50 seats, LTV $28,750). Plan: Enterprise $2,499/mo. Previous ticket TKT-4003 API auth issues resolved."},
    {"id":"TKT-03","customer_id":"CUST-1002","query":"My subscription shows $89.99/month but I signed up for the Basic plan at $29.99. Why am I being charged 3x more?","cat":"billing","crm":"Marcus Johnson (CUST-1002, standard). No active subscription on file. Orders: ORD-2010 $129.99 delivered, ORD-2011 $299.99 cancelled+refunded. One refund already processed."},
    {"id":"TKT-04","customer_id":"CUST-1004","query":"I've been waiting 5 days for someone to fix my account access issue. Every time I call I get a different agent who knows nothing about my case. This is absolutely unacceptable.","cat":"general","crm":"Chen Wei (CUST-1004, premium). Account SUSPENDED — 3 declined card payments. Previous ticket TKT-4004 about login issues opened 5 days ago, still unresolved. No callback scheduled."},
    {"id":"TKT-05","customer_id":"CUST-1001","query":"The wireless charger from ORD-2002 arrived defective — it doesn't charge at all. I want a full refund for this broken item.","cat":"refund","crm":"Priya Sharma (CUST-1001, premium). Order ORD-2002 $49.99 shipped, Wireless Charger. Payment PAY-3003 $49.99 completed. Item defective — under 30-day window AND defective product rule applies."},
    {"id":"TKT-06","customer_id":"CUST-1005","query":"My dashboard has been stuck on 'Loading...' for 2 hours. I've tried refreshing, clearing cache, incognito — nothing works. I have a client presentation in 30 minutes!","cat":"tech","crm":"CUST-1005, standard tier. No known outages reported. Customer tried Chrome incognito already. Dashboard issues can be server-side or client-side."},
    {"id":"TKT-07","customer_id":"CUST-1003","query":"We added 15 new team members but our invoice still shows 50 seats at $2,499. It should be 65 seats. When will this be updated and what's the prorated amount?","cat":"billing","crm":"Aisha Patel (CUST-1003, enterprise). Current: 50 seats at $2,499/mo ($49.98/seat). New: 65 seats. Prorated diff: 15 x $49.98 = $749.70. Renewal: 2026-12-10."},
    {"id":"TKT-08","customer_id":"CUST-1001","query":"I've been a loyal customer for 3 years and spent over $4,500, but this is the worst support experience I've ever had. Your agent promised a callback yesterday and no one called. I want to speak to a manager.","cat":"general","crm":"Priya Sharma (CUST-1001, premium, LTV $4,520, since 2023). VIP customer. Previous ticket resolved. Notes: prefers email communication."},
]

TICKETS = ALL_TICKETS[T_START:T_END]

PROMPTS = {
    "mini": {
        "refund": "Refund specialist (Mini). 30-day full refund. Defective=full refund always. You can only RECOMMEND refunds, not process. Say 'I recommend refund of $X — team member confirms within 2 hrs.' Include amount, reason, timeline, CRM refs. NEVER say contact support.",
        "tech": "Tech RESOLUTION specialist (Mini). 1) Identify ROOT CAUSE. 2) Give ONE fix with steps. 3) If server-side: say so + timeline + workaround. 4) Workaround NOW. Format: **What's happening:** [cause] **Fix:** [ONE action] **Steps:** [how] **Workaround:** [now]. NEVER list 10 steps. NEVER say contact support.",
        "billing": "Billing specialist (Mini). Verify charges, calculate differences. You can only RECOMMEND adjustments. Say 'I recommend adjusting by $X — specialist confirms within 2 hrs.' Include amounts and math. NEVER say contact support.",
        "general": "Support agent (Mini). Complaints: 1) Acknowledge SPECIFIC frustration 2) Escalate with ticket# + schedule callback 3) Specific timeline 4) Confirm next steps. Can escalate but NOT offer credits. NEVER say contact support again.",
    },
    "parwa": {
        "refund": "Refund specialist for PARWA. 30-day full refund. Defective=full refund always. You CAN process refunds — DO IT NOW. Say 'I've processed refund of $X to original payment. 3-5 business days. Reference: [ID].' Include amount, timeline, confirmation. NEVER say contact support.",
        "tech": "Tech RESOLUTION specialist for PARWA. 1) Identify ROOT CAUSE. 2) Give ONE fix with steps. 3) If server-side: say so + timeline + workaround. 4) Workaround NOW. Format: **What's happening:** [cause] **Fix:** [ONE action] **Steps:** [how] **Workaround:** [now]. NEVER list 10 steps. NEVER say contact support.",
        "billing": "Billing specialist for PARWA. Verify charges, calculate differences. You CAN process adjustments — DO IT NOW. Say 'I've adjusted your account. Credit of $X on next invoice. Reference: [ID].' Include amounts, math. NEVER say contact support.",
        "general": "Support agent for PARWA. Complaints: 1) Acknowledge SPECIFIC frustration 2) Apply credit up to $50 + escalate with ticket# + schedule callback 3) Specific timeline 4) Confirm next steps. NEVER say contact support again.",
    },
    "high": {
        "refund": "Refund specialist for PARWA High. 30-day full refund. Defective=full refund always. Process refunds AND offer compensation — DO IT NOW. Say 'Processed refund $X, 3-5 days, Ref: [ID].' For VIP: add goodwill credit. Include amount, timeline, confirmation, extras. NEVER say contact support.",
        "tech": "Tech RESOLUTION specialist for PARWA High. 1) Identify ROOT CAUSE. 2) ONE fix + steps. 3) Server-side: file incident + page engineer + timeline + workaround. 4) Workaround NOW. 5) Enterprise: schedule senior engineer callback. Format: **What's happening:** [cause] **Fix:** [ONE action] **Steps:** [how] **Workaround:** [now] **Enterprise:** [callback]. NEVER list 10 steps. NEVER say contact support.",
        "billing": "Billing specialist for PARWA High. Verify charges, calculate differences. Process adjustments AND credits — DO IT NOW. Say 'Adjusted account. Credit $X on next invoice. Ref: [ID].' Enterprise: offer account manager callback. NEVER say contact support.",
        "general": "Support agent for PARWA High. Complaints: 1) Acknowledge SPECIFIC frustration 2) Apply credit ANY amount + escalate with ticket# + schedule voice callback from manager 3) Specific timeline 4) Confirm next steps. NEVER say contact support again.",
    },
}

async def llm(sys_prompt, user_prompt, max_tok=500):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {NVIDIA_KEY}"}
    payload = {"model": MODEL, "messages": [{"role":"system","content":sys_prompt},{"role":"user","content":user_prompt}], "temperature": 0.1, "max_tokens": max_tok}
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.post(NVIDIA_URL, headers=headers, json=payload)
            if r.status_code == 429:
                await asyncio.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 200:
                return r.json().get("choices",[{}])[0].get("message",{}).get("content","").strip()
            await asyncio.sleep(2)
        except:
            await asyncio.sleep(2)
    return ""

async def main():
    print(f"=== {VARIANT.upper()} tickets {T_START}-{T_END-1} ===", flush=True)
    prompts = PROMPTS[VARIANT]
    results = []
    for t in TICKETS:
        t0 = time.time()
        print(f"  {t['id']} ({t['cat']})...", end=" ", flush=True)
        resp = await llm(prompts[t["cat"]], f"Customer: {t['query']}\nCRM: {t['crm']}\nResolve completely with specific actions, amounts, timelines, references.")
        if not resp:
            print("EMPTY!", flush=True)
            results.append({"id":t["id"],"cat":t["cat"],"variant":VARIANT,"score":0,"resolved":False,"reason":"Empty"})
            continue
        ev = await llm("Strict evaluator. RESOLVED only if customer won't contact again. Recommending without executing = NOT resolved.",
            f"Customer: {t['query']}\nCat: {t['cat']}\nVariant: {VARIANT}\nCRM: {t['crm']}\nResponse:\n{resp}\n\nScore 0-100. Resolved?\nSCORE: [n]\nRESOLVED: [yes/no]\nREASON: [one sentence]", max_tok=80)
        score, resolved, reason = 0, False, ""
        for line in ev.split("\n"):
            l = line.strip()
            if l.upper().startswith("SCORE:"):
                try: score = int("".join(c for c in l.split(":")[1] if c.isdigit()))
                except: pass
            elif l.upper().startswith("RESOLVED:"):
                resolved = l.split(":",1)[1].strip().lower().startswith("yes") if ":" in l else False
            elif l.upper().startswith("REASON:"):
                reason = l.split(":",1)[1].strip()
        elapsed = time.time() - t0
        s = "✓" if resolved else "✗"
        print(f"{s} {score} | {reason} ({elapsed:.0f}s)", flush=True)
        results.append({"id":t["id"],"cat":t["cat"],"variant":VARIANT,"score":score,"resolved":resolved,"reason":reason})
        await asyncio.sleep(1)

    outfile = f"/home/z/my-project/tests/production/arena_{VARIANT}_{T_START}_{T_END}.json"
    with open(outfile, "w") as f:
        json.dump({"variant":VARIANT,"range":f"{T_START}-{T_END}","results":results}, f, indent=2)
    print(f"Saved {outfile}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
