"""PARWA Resolution Rate Test - Single file, no imports from project"""
import asyncio, json, time, httpx

NVIDIA_KEY = "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"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

TICKETS = [
    {"id": "REF-01", "query": "I bought the Pro plan 12 days ago and it's not what I expected. I want a full refund.", "cat": "refund"},
    {"id": "TECH-01", "query": "My API integration keeps returning 503 errors. Auth token is valid. What's going on?", "cat": "tech"},
    {"id": "BILL-01", "query": "I was charged $49.99 twice this month. There should only be one charge.", "cat": "billing"},
    {"id": "GEN-01", "query": "What's the difference between the Pro and Enterprise plans?", "cat": "general"},
    {"id": "REF-02", "query": "You charged me after I cancelled my subscription! Refund immediately!", "cat": "refund"},
    {"id": "TECH-02", "query": "The dashboard won't load. I've tried Chrome and Firefox, cleared cache, but it just spins.", "cat": "tech"},
    {"id": "BILL-02", "query": "Why is my invoice $89.99 when my plan is $49.99/month?", "cat": "billing"},
    {"id": "GEN-02", "query": "This is the worst customer service ever. I've been waiting 2 weeks for a response!", "cat": "general"},
]

PROMPTS = {
    "refund": "You are a refund policy specialist for PARWA customer support.\n- 30-day refund policy: Full refund within 30 days, no questions asked\n- 31-60 day window: Partial refund (50-75%)\n- After 60 days: Refund only for defective products or billing errors\n- CRITICAL: Defective products get FULL refund regardless of purchase date\n- Subscription refunds: Prorated from cancellation date\n- NEVER say contact support again. YOU are support. Process the refund NOW.\n- ALWAYS include: refund amount, processing timeline, confirmation",
    "tech": "You are a senior technical support specialist for PARWA.\nDiagnostic approach:\n1. REPRODUCE: What is the customer experiencing\n2. ISOLATE: Account, device, or systemic?\n3. QUICK FIX: Simplest fix (clear cache, restart, re-login)\n4. DETAILED FIX: Step-by-step with exact commands or UI paths\n5. ALTERNATIVE: If fix might not work\n6. WORKAROUND: Something customer can do RIGHT NOW\n7. ESCALATE: If 3+ fixes fail\n\nInclude specific steps and commands. ALWAYS include a workaround. NEVER say contact support.",
    "billing": "You are a billing specialist for PARWA customer support.\n- Verify each charge against the subscription plan\n- If discrepancy, calculate exact difference\n- PROCESS adjustments immediately\n- For double charges: Acknowledge, verify, process refund immediately\n- ALWAYS include: specific amounts, timeline, what customer sees on next invoice\n- NEVER say contact support again. YOU are support.",
    "general": "You are a helpful customer support agent for PARWA.\n- Be friendly, clear, concise\n- For COMPLAINTS: Acknowledge frustration FIRST, then offer SPECIFIC resolution\n- NEVER just say sorry without concrete next step\n- Never say contact support. YOU are support.",
}

async def llm_call(sys_prompt, user_prompt, max_tok=700):
    """Single LLM call with GLM-5.1, fallback to Llama."""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {NVIDIA_KEY}"}
    
    for model in ["z-ai/glm-5.1", "meta/llama-3.3-70b-instruct"]:
        payload = {
            "model": model,
            "messages": [{"role":"system","content":sys_prompt},{"role":"user","content":user_prompt}],
            "temperature": 0.1,
            "max_tokens": max_tok,
        }
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30.0) as c:
                    r = await c.post(NVIDIA_URL, headers=headers, json=payload)
                if r.status_code == 429:
                    await asyncio.sleep(3)
                    continue
                if r.status_code == 200:
                    return r.json().get("choices",[{}])[0].get("message",{}).get("content","").strip()
            except:
                await asyncio.sleep(1)
    return ""

async def main():
    print("=" * 70)
    print("  PARWA RESOLUTION RATE TEST — 8 Tickets, Real LLM")
    print("=" * 70)
    
    results = []
    start = time.time()
    
    for i, t in enumerate(TICKETS):
        t0 = time.time()
        print(f"\n[{i+1}/8] {t['id']} ({t['cat']})...", flush=True)
        
        # Route (keyword-based, matches our SubgraphRouter)
        msg = t["query"].lower()
        if any(w in msg for w in ["refund", "money back", "cancel", "charged after"]):
            subgraph = "refund"
        elif any(w in msg for w in ["error", "crash", "load", "login", "api", "503", "bug", "won't", "spins"]):
            subgraph = "tech"
        elif any(w in msg for w in ["charge", "invoice", "billing", "payment", "$"]):
            subgraph = "billing"
        else:
            subgraph = "general"
        
        # Generate
        resp = await llm_call(PROMPTS[subgraph], 
            f"Customer: {t['query']}\n\nResolve this completely. Include specific actions, amounts, timelines.")
        
        if not resp:
            print(f"  ⚠️ Empty response", flush=True)
            results.append({"id":t["id"],"cat":t["cat"],"subgraph":subgraph,"score":0,"resolved":False,"reason":"Empty response","response":""})
            continue
        
        # Evaluate — pass FULL response, no truncation
        ev = await llm_call(
            "You are a strict customer support quality evaluator. Be harsh. Only high scores if truly resolved.",
            f"Customer: {t['query']}\nCategory: {t['cat']}\n\nAI Response:\n{resp}\n\nScore 0-100. Is this TRULY resolved (customer won't need to contact again)?\nRespond EXACTLY:\nSCORE: [number]\nRESOLVED: [yes/no]\nREASON: [one sentence]",
            max_tok=120
        )
        
        score, resolved, reason = 0, False, ""
        for line in ev.split("\n"):
            l = line.strip()
            if l.upper().startswith("SCORE:"):
                try: score = int("".join(c for c in l.split(":")[1] if c.isdigit()))
                except: pass
            elif l.upper().startswith("RESOLVED:"):
                rest = l.split(":",1)[1].strip().lower() if ":" in l else ""
                resolved = rest.startswith("yes")
            elif l.upper().startswith("REASON:"):
                reason = l.split(":",1)[1].strip()
        
        elapsed = time.time() - t0
        s = "✓" if resolved else "✗"
        print(f"  {s} Score={score} | {reason}", flush=True)
        print(f"  Response ({len(resp)} chars, {elapsed:.0f}s)", flush=True)
        results.append({"id":t["id"],"cat":t["cat"],"subgraph":subgraph,"score":score,"resolved":resolved,"reason":reason,"response_len":len(resp),"elapsed":round(elapsed,1)})
        await asyncio.sleep(0.5)
    
    total_time = time.time() - start
    
    # ═══ FINAL ═══
    total = len(results)
    resolved_count = sum(1 for r in results if r["resolved"])
    above_80 = sum(1 for r in results if r["score"] >= 80)
    above_60 = sum(1 for r in results if r["score"] >= 60)
    rate = (resolved_count/total*100) if total else 0
    avg = sum(r["score"] for r in results)/total if total else 0
    
    print(f"\n{'='*70}")
    print(f"  ═══ FINAL RESULTS ═══")
    print(f"{'='*70}")
    print(f"\n  TRUE RESOLUTION RATE:  {rate:.1f}% ({resolved_count}/{total})")
    print(f"  SCORE >= 80:           {above_80}/{total} ({above_80/total*100:.0f}%)")
    print(f"  SCORE >= 60:           {above_60}/{total} ({above_60/total*100:.0f}%)")
    print(f"  AVG EVAL SCORE:        {avg:.0f}/100")
    print(f"  TOTAL TIME:            {total_time:.0f}s")
    
    print(f"\n  BY SUBGRAPH:")
    for cat in ["refund","tech","billing","general"]:
        cr = [r for r in results if r["cat"]==cat]
        if cr:
            n = sum(1 for r in cr if r["resolved"])
            a = sum(r["score"] for r in cr)/len(cr)
            print(f"    {cat:12s}: {n}/{len(cr)} resolved ({n/len(cr)*100:.0f}%) | avg score={a:.0f}")
    
    print(f"\n  PER TICKET:")
    for r in results:
        s = "✓ RESOLVED" if r["resolved"] else "✗ FAILED  "
        print(f"    {r['id']} [{r['cat']:7s}] score={r['score']:3d}  {s}")
        print(f"      → {r['reason']}")
    
    # Save
    out = {"true_resolution_rate": rate, "avg_eval": avg, "time_sec": round(total_time), "results": results}
    with open("/home/z/my-project/tests/production/quick_test_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Saved to quick_test_results.json")

if __name__ == "__main__":
    asyncio.run(main())
