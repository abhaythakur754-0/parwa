"""
PARWA MINIMAL Test — 5 tickets, 2 LLM calls each (response + eval)
"""
import asyncio, json, os, sys, time, httpx

NVIDIA_KEY = "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"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

TICKETS = [
    {"id": "REF-01", "query": "I bought the Pro plan 12 days ago and it's not what I expected. I want a full refund.", "cat": "refund"},
    {"id": "TECH-01", "query": "My API integration keeps returning 503 errors. Auth token is valid. What's going on?", "cat": "tech"},
    {"id": "BILL-01", "query": "I was charged $49.99 twice this month. There should only be one charge.", "cat": "billing"},
    {"id": "GEN-01", "query": "What's the difference between the Pro and Enterprise plans?", "cat": "general"},
    {"id": "REF-02", "query": "You charged me after I cancelled my subscription! Refund immediately!", "cat": "refund"},
]

PROMPTS = {
    "refund": "You are a refund specialist. 30-day full refund policy. Defective = full refund regardless of date. ALWAYS include refund amount, timeline, confirmation. NEVER say contact support again.",
    "tech": "You are a senior tech support specialist. ALWAYS provide: 1) Specific diagnostic steps 2) Quick fix 3) Workaround 4) When to escalate. NEVER say 'contact support'. Include exact commands/paths.",
    "billing": "You are a billing specialist. ALWAYS verify charges. Include specific amounts, timeline, what customer sees on next invoice. NEVER say contact support again.",
    "general": "You are a helpful support agent. Be concise and specific. For complaints, offer concrete resolution. NEVER say contact support.",
}

_last = 0.0

async def llm(sys_prompt, user_prompt, max_tok=600):
    global _last
    now = time.monotonic()
    if now - _last < 0.1:
        await asyncio.sleep(0.1 - (now - _last))
    
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {NVIDIA_KEY}"}
    payload = {"model": "deepseek-ai/deepseek-v4-flash", "messages": [{"role":"system","content":sys_prompt},{"role":"user","content":user_prompt}], "temperature":0.1, "max_tokens":max_tok}
    
    for att in range(2):
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.post(NVIDIA_URL, headers=headers, json=payload)
            _last = time.monotonic()
            if r.status_code == 429:
                await asyncio.sleep(2); continue
            if r.status_code == 200:
                return r.json().get("choices",[{}])[0].get("message",{}).get("content","").strip()
            if att == 0:
                payload["model"] = "meta/llama-3.3-70b-instruct"
        except:
            _last = time.monotonic()
            await asyncio.sleep(1)
    return ""

async def main():
    print("PARWA RESOLUTION RATE TEST — 5 tickets")
    print("="*60)
    results = []
    
    for i, t in enumerate(TICKETS):
        print(f"\n[{i+1}/5] {t['id']} ({t['cat']})...", flush=True)
        
        # Generate response
        resp = await llm(PROMPTS[t["cat"]], f"Customer: {t['query']}\n\nResolve this completely. Include specific actions, amounts, timelines.")
        print(f"  Response: {resp[:120]}...", flush=True)
        
        # Evaluate
        ev = await llm(
            "Strict evaluator. Only high scores if truly resolved.",
            f"Customer asked: {t['query']}\nAgent responded: {resp[:500]}\n\nScore 0-100. Is this TRULY resolved (customer won't need to contact again)?\nRespond: SCORE: [number]\\nRESOLVED: [yes/no]\\nREASON: [one sentence]",
            max_tok=100
        )
        
        score, resolved, reason = 0, False, ""
        for line in ev.split("\n"):
            l = line.strip()
            if l.upper().startswith("SCORE:"):
                try: score = int("".join(c for c in l.split(":")[1] if c.isdigit()))
                except: pass
            elif l.upper().startswith("RESOLVED:"):
                resolved = "yes" in l.lower().split(":")[1].strip()[:5]
            elif l.upper().startswith("REASON:"):
                reason = l.split(":",1)[1].strip()
        
        s = "✓" if resolved else "✗"
        print(f"  {s} Score={score} Resolved={resolved} | {reason}", flush=True)
        results.append({"id": t["id"], "cat": t["cat"], "score": score, "resolved": resolved, "reason": reason, "response": resp[:300]})
    
    # Final
    total = len(results)
    resolved_count = sum(1 for r in results if r["resolved"])
    rate = (resolved_count/total*100) if total else 0
    avg = sum(r["score"] for r in results)/total if total else 0
    
    print(f"\n{'='*60}")
    print(f"TRUE RESOLUTION RATE: {rate:.1f}% ({resolved_count}/{total})")
    print(f"AVG EVAL SCORE: {avg:.0f}/100")
    
    # By category
    for cat in ["refund","tech","billing","general"]:
        cat_r = [r for r in results if r["cat"]==cat]
        if cat_r:
            cr = sum(1 for r in cat_r if r["resolved"])
            print(f"  {cat}: {cr}/{len(cat_r)} resolved")
    
    print(f"\nPER TICKET:")
    for r in results:
        s = "✓ RESOLVED" if r["resolved"] else "✗ FAILED"
        print(f"  {r['id']} [{r['cat']:7s}] score={r['score']:3d} {s}")
        print(f"    → {r['reason']}")
    
    # Save
    out = {"true_resolution_rate": rate, "avg_eval": avg, "results": results}
    path = "/home/z/my-project/tests/production/minimal_test_results.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved: {path}")

if __name__ == "__main__":
    asyncio.run(main())
