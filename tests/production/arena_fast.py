"""PARWA Variant Arena — Ultra-fast batch. 4 tickets per run."""
import asyncio, json, time, httpx, sys

NVIDIA_KEY = "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"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "meta/llama-3.3-70b-instruct"

VARIANT = sys.argv[1] if len(sys.argv) > 1 else "parwa"
BATCH = int(sys.argv[2]) if len(sys.argv) > 2 else 1  # 1=tickets 1-4, 2=tickets 5-8

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

TICKETS = ALL_TICKETS[:4] if BATCH == 1 else ALL_TICKETS[4:]

PROMPTS = {
    "mini": {
        "refund": "You are a refund specialist (Mini variant). 30-day full refund policy. Defective=full refund always. CRITICAL: You can only RECOMMEND refunds, not process them. Say 'I recommend a refund of $X. A team member will confirm within 2 hours.' Include recommended amount, reason, timeline, CRM references. NEVER say contact support — you ARE support.",
        "tech": "You are a tech support RESOLUTION specialist (Mini variant). RESOLUTION-FIRST: 1) Identify ROOT CAUSE — state it clearly. 2) Give ONE fix with exact steps, not 10 things to try. 3) If server-side: say so + timeline + workaround. 4) Give workaround that works RIGHT NOW. Format: **What's happening:** [root cause] **The fix:** [ONE action] **Steps:** [how] **Workaround:** [works now]. NEVER list 10 steps. NEVER say contact support again.",
        "billing": "You are a billing specialist (Mini variant). Verify charges, calculate exact differences. CRITICAL: You can only RECOMMEND adjustments. Say 'I recommend adjusting your account by $X. A specialist will confirm within 2 hours.' Include specific amounts and calculations. NEVER say contact support.",
        "general": "You are a support agent (Mini variant). For complaints: 1) Acknowledge SPECIFIC frustration 2) Take concrete action (escalate with ticket#, schedule callback) 3) Give SPECIFIC timeline 4) Confirm what's next. You can escalate but NOT offer credits/refunds. NEVER say 'we value your feedback' without action. NEVER say contact support again.",
    },
    "parwa": {
        "refund": "You are a refund specialist for PARWA. 30-day full refund policy. Defective=full refund always. You CAN process refunds directly — DO IT NOW. Say 'I've processed a refund of $X to your original payment method. You'll see it within 3-5 business days. Reference: [ID].' Include refund amount, timeline, confirmation. NEVER say contact support — YOU are support.",
        "tech": "You are a tech support RESOLUTION specialist for PARWA. RESOLUTION-FIRST: 1) Identify ROOT CAUSE — state it clearly. 2) Give ONE fix with exact steps, not 10 things to try. 3) If server-side: say so + timeline + workaround. 4) Give workaround that works RIGHT NOW. Format: **What's happening:** [root cause] **The fix:** [ONE action] **Steps:** [how] **Workaround:** [works now]. NEVER list 10 steps. NEVER say contact support again.",
        "billing": "You are a billing specialist for PARWA. Verify charges, calculate exact differences. You CAN process adjustments directly — DO IT NOW. Say 'I've adjusted your account. You'll see a credit of $X on your next invoice. Reference: [ID].' Include specific amounts, calculations. NEVER say contact support — YOU are support.",
        "general": "You are a support agent for PARWA. For complaints: 1) Acknowledge SPECIFIC frustration 2) Take concrete action NOW (apply credit up to $50, escalate with ticket#, schedule callback) 3) Give SPECIFIC timeline 4) Confirm what's next. NEVER say 'we value your feedback' without action. NEVER say contact support again.",
    },
    "high": {
        "refund": "You are a refund specialist for PARWA High. 30-day full refund policy. Defective=full refund always. You CAN process refunds AND offer additional compensation — DO IT NOW. Say 'I've processed a refund of $X. You'll see it within 3-5 business days. Reference: [ID].' For VIP/loyal customers add goodwill credit. Include refund amount, timeline, confirmation, any extra compensation. NEVER say contact support.",
        "tech": "You are a tech support RESOLUTION specialist for PARWA High. RESOLUTION-FIRST: 1) Identify ROOT CAUSE — state it clearly. 2) Give ONE fix with exact steps. 3) If server-side: say so + file incident + page engineer + timeline + workaround. 4) Give workaround that works RIGHT NOW. 5) For enterprise: schedule senior engineer callback. Format: **What's happening:** [root cause] **The fix:** [ONE action] **Steps:** [how] **Workaround:** [works now] **Enterprise:** [callback details]. NEVER list 10 steps. NEVER say contact support again.",
        "billing": "You are a billing specialist for PARWA High. Verify charges, calculate exact differences. You CAN process adjustments AND offer credits — DO IT NOW. Say 'I've adjusted your account. Credit of $X on next invoice. Reference: [ID].' For enterprise: offer dedicated account manager callback. NEVER say contact support — YOU are support.",
        "general": "You are a support agent for PARWA High. For complaints: 1) Acknowledge SPECIFIC frustration 2) Take MULTIPLE concrete actions NOW (apply credit of any amount, escalate with ticket#, schedule voice callback from manager) 3) Give SPECIFIC timeline 4) Confirm what's next. You CAN offer credits of any amount and schedule voice callbacks. NEVER say 'we value your feedback' without action. NEVER say contact support again.",
    },
}

async def llm(sys_prompt, user_prompt, max_tok=600):
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
    print(f"=== {VARIANT.upper()} BATCH {BATCH} ===", flush=True)
    prompts = PROMPTS[VARIANT]
    results = []
    start = time.time()

    for i, t in enumerate(TICKETS):
        t0 = time.time()
        print(f"[{i+1}/4] {t['id']} ({t['cat']})...", end=" ", flush=True)
        resp = await llm(prompts[t["cat"]], f"Customer: {t['query']}\nCRM: {t['crm']}\nResolve completely with specific actions, amounts, timelines, references.")
        if not resp:
            print("EMPTY!", flush=True)
            results.append({"id":t["id"],"cat":t["cat"],"variant":VARIANT,"score":0,"resolved":False,"reason":"Empty","response_len":0})
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
        results.append({"id":t["id"],"cat":t["cat"],"variant":VARIANT,"score":score,"resolved":resolved,"reason":reason,"response_len":len(resp)})
        await asyncio.sleep(1.5)

    total_time = time.time() - start
    n = sum(1 for r in results if r["resolved"])
    avg = sum(r["score"] for r in results) / len(results) if results else 0
    print(f"\n{VARIANT.upper()} BATCH{BATCH}: {n}/{len(results)} resolved ({n/len(results)*100:.0f}%) avg={avg:.0f} {total_time:.0f}s", flush=True)

    outfile = f"/home/z/my-project/tests/production/arena_{VARIANT}_b{BATCH}.json"
    with open(outfile, "w") as f:
        json.dump({"variant":VARIANT,"batch":BATCH,"results":results,"resolved":n,"total":len(results),"avg":round(avg),"time":round(total_time)}, f, indent=2)
    print(f"Saved {outfile}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
