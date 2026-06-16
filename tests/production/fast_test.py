"""
PARWA FAST Resolution Rate Test
================================
Runs 10 tickets through the pipeline using DIRECT NVIDIA API calls.
Each ticket: route → classify → generate response → evaluate
No langgraph, no brain overhead — just raw pipeline logic + real LLM.
"""
import asyncio
import json
import os
import sys
import time
import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "ai_pipeline"))

NVIDIA_API_KEY = "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"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

TICKETS = [
    {"id": "REF-01", "query": "I bought the Pro plan 12 days ago and it's not what I expected. I want a full refund.", "category": "refund"},
    {"id": "REF-02", "query": "You charged me for a subscription I cancelled last month! I want my money back immediately!", "category": "refund"},
    {"id": "REF-03", "query": "I ordered 45 days ago. The product is defective. Can I still get a refund?", "category": "refund"},
    {"id": "TECH-01", "query": "My API integration keeps returning 503 errors. I've checked my auth token and it's valid. What's going on?", "category": "tech"},
    {"id": "TECH-02", "query": "The dashboard won't load. I've tried Chrome and Firefox, cleared cache, but it just spins forever.", "category": "tech"},
    {"id": "TECH-03", "query": "I can't login to my account. It says 'invalid credentials' but I'm using the right password.", "category": "tech"},
    {"id": "BILL-01", "query": "I was charged $49.99 twice this month. There should only be one charge on my account.", "category": "billing"},
    {"id": "BILL-02", "query": "Why is my invoice showing $89.99 when my plan is supposed to be $49.99 per month?", "category": "billing"},
    {"id": "GEN-01", "query": "What's the difference between the Pro and Enterprise plans?", "category": "general"},
    {"id": "GEN-02", "query": "This is the worst customer service I've ever experienced. I've been waiting 2 weeks for a response!", "category": "general"},
]

_last = 0.0

async def llm(system: str, user: str, max_tokens: int = 600) -> str:
    global _last
    now = time.monotonic()
    if now - _last < 0.12:
        await asyncio.sleep(0.12 - (now - _last))
    
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {NVIDIA_API_KEY}"}
    payload = {
        "model": "deepseek-ai/deepseek-v4-flash",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(NVIDIA_URL, headers=headers, json=payload)
            _last = time.monotonic()
            
            if resp.status_code == 429:
                await asyncio.sleep(float(resp.headers.get("retry-after", "3")))
                continue
            if resp.status_code == 200:
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if "deepseek" in payload["model"] and attempt == 0:
                payload["model"] = "meta/llama-3.3-70b-instruct"
                continue
            await asyncio.sleep(1.5)
        except Exception:
            _last = time.monotonic()
            await asyncio.sleep(1.5)
    return ""


# Subgraph system prompts (copied from prompts.py for speed)
PROMPTS = {
    "refund": """You are a refund policy specialist for PARWA customer support.
- 30-day refund policy: Full refund within 30 days, no questions asked
- 31-60 day window: Partial refund (50-75%)
- After 60 days: Refund only for defective products or billing errors
- CRITICAL: Defective products get FULL refund regardless of purchase date
- Subscription refunds: Prorated from cancellation date
- NEVER say "contact support again" — YOU are support. Process the refund NOW.
- ALWAYS include: refund amount, processing timeline, confirmation""",

    "tech": """You are a senior technical support specialist for PARWA.
Your diagnostic approach (follow this order):
1. REPRODUCE: Understand what the customer is experiencing
2. ISOLATE: Account-specific, device-specific, or systemic?
3. QUICK FIX: Simplest possible fix (clear cache, restart, re-login)
4. DETAILED FIX: Step-by-step with EXACT UI paths or commands
5. ALTERNATIVE: If fix might not work, provide alternative
6. WORKAROUND: Something the customer can do RIGHT NOW
7. ESCALATE: If 3+ fixes fail, escalate with full diagnostic data

MANDATORY: Include specific steps, commands, or UI paths. NEVER just say "try again" or "contact support".
ALWAYS include a WORKAROUND the customer can try immediately.""",

    "billing": """You are a billing specialist for PARWA customer support.
- Always verify each charge against the subscription plan
- If there's a discrepancy, calculate the exact difference
- For disputes, check if it's legitimate before processing
- PROCESS adjustments immediately — don't ask customer to contact again
- For double charges: Acknowledge, verify, process refund immediately
- For unauthorized charges: Flag AND provide immediate credit
- ALWAYS include: specific amounts, timeline, what customer will see on next invoice""",

    "general": """You are a helpful customer support agent for PARWA.
- Be friendly, clear, and concise
- If you can answer directly, do so
- For COMPLAINTS: Acknowledge frustration FIRST, then offer SPECIFIC resolution
- NEVER just say "I'm sorry" without a concrete next step
- Never say "contact support" — YOU are support
- Always verify account info before making changes""",
}

ROUTER_PROMPT = """Classify this customer message into exactly one of these categories:
- refund: Wants money back, return, cancellation with refund, charged after cancellation, dispute about charges
- tech: Technical problem (can't access, won't load, error, crash, bug, slow, integration, API, login, SSL, timeout, app crash, webhook failure)
- billing: Question about charges, invoices, payments, plan pricing, proration, receipts (NOT refund requests — those go to "refund")
- general: Everything else (FAQ, account changes, general questions, plan comparisons, complaints)

Respond with ONLY the category name, nothing else.

Customer message: {message}"""


async def process_ticket(ticket: dict) -> dict:
    """Route → Generate response using specialized prompt → Return result."""
    
    # Step 1: Route
    route_raw = await llm("You classify customer messages. Respond with exactly one word.", 
                          ROUTER_PROMPT.format(message=ticket["query"]), max_tokens=10)
    subgraph = route_raw.strip().lower()
    if subgraph not in ("refund", "tech", "billing", "general"):
        # Keyword fallback
        msg = ticket["query"].lower()
        if any(w in msg for w in ["refund", "money back", "cancel", "charged after"]):
            subgraph = "refund"
        elif any(w in msg for w in ["error", "crash", "load", "login", "api", "503", "bug", "won't"]):
            subgraph = "tech"
        elif any(w in msg for w in ["charge", "invoice", "billing", "payment", "plan price"]):
            subgraph = "billing"
        else:
            subgraph = "general"
    
    # Step 2: Generate response using specialized prompt
    system_prompt = PROMPTS.get(subgraph, PROMPTS["general"])
    response = await llm(system_prompt, 
                         f"Customer message: {ticket['query']}\n\nProvide a complete, actionable response that truly resolves this issue.", 
                         max_tokens=800)
    
    # Step 3: Self-correction check — is the response good enough?
    correction_check = await llm(
        "You evaluate if a customer support response is complete. Be strict.",
        f"Customer asked: {ticket['query']}\n\nAgent responded: {response[:600]}\n\nIs this response complete with specific actions/amounts/timelines? Or is it vague and the customer would need to contact again? Answer COMPLETE or INCOMPLETE in one word, then briefly explain why.",
        max_tokens=100,
    )
    
    needs_correction = "incomplete" in correction_check.lower()
    correction_applied = False
    
    if needs_correction:
        # Re-generate with emphasis on completeness
        response = await llm(
            system_prompt,
            f"Customer message: {ticket['query']}\n\nIMPORTANT: Your previous response was too vague. You MUST include SPECIFIC actions, exact amounts, timelines, and concrete next steps. The customer should NOT need to contact support again. Provide a complete resolution NOW.",
            max_tokens=800,
        )
        correction_applied = True
    
    return {
        "ticket_id": ticket["id"],
        "category": ticket["category"],
        "subgraph": subgraph,
        "response": response,
        "correction_applied": correction_applied,
    }


async def evaluate_ticket(ticket: dict, result: dict) -> dict:
    """Independent LLM evaluation."""
    eval_raw = await llm(
        "You are a strict customer support quality evaluator. Be harsh — only high scores if the response truly resolves the issue completely.",
        f"""Customer message: {ticket['query']}
Category: {ticket['category']}

AI Response:
{result['response'][:600]}

Evaluate STRICTLY:
1. Did the response address the SPECIFIC issue?
2. Did it provide CONCRETE next steps or resolution?
3. Would the customer need to contact support AGAIN for the same issue?

Score 0-100 where:
- 80-100: Fully resolved
- 60-79: Mostly resolved
- 40-59: Partially resolved  
- 0-39: Not resolved

Respond EXACTLY:
SCORE: [number]
RESOLVED: [yes/no]
REASON: [one sentence]""",
        max_tokens=150,
    )
    
    score = 0
    resolved = False
    reason = ""
    for line in eval_raw.split("\n"):
        line = line.strip()
        if line.upper().startswith("SCORE:"):
            try:
                score = int("".join(c for c in line.split(":")[1] if c.isdigit()))
            except:
                score = 0
        elif line.upper().startswith("RESOLVED:"):
            resolved = "yes" in line.lower().split(":")[1].strip()[:5]
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()
    
    return {"eval_score": score, "truly_resolved": resolved, "eval_reason": reason}


async def main():
    print("=" * 70)
    print("  PARWA FAST RESOLUTION RATE TEST")
    print("  10 tickets × Route + Specialized LLM + Self-correction + Eval")
    print("=" * 70)
    
    start_time = time.time()
    results = []
    
    for i, ticket in enumerate(TICKETS):
        t0 = time.time()
        print(f"\n[{i+1}/10] {ticket['id']} ({ticket['category']})...")
        
        # Process
        result = await process_ticket(ticket)
        elapsed_process = time.time() - t0
        
        # Evaluate
        eval_result = await evaluate_ticket(ticket, result)
        elapsed_total = time.time() - t0
        
        result.update(eval_result)
        result["elapsed_sec"] = round(elapsed_total, 1)
        results.append(result)
        
        status = "✓" if result["truly_resolved"] else "✗"
        print(f"  {status} Subgraph={result['subgraph']} | Score={result['eval_score']} | Correction={result['correction_applied']}")
        print(f"  Reason: {result['eval_reason']}")
    
    total_time = time.time() - start_time
    
    # ═══ FINAL METRICS ═══
    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)
    
    total = len(results)
    truly_resolved = sum(1 for r in results if r["truly_resolved"])
    eval_above_80 = sum(1 for r in results if r["eval_score"] >= 80)
    eval_above_60 = sum(1 for r in results if r["eval_score"] >= 60)
    corrections = sum(1 for r in results if r["correction_applied"])
    
    true_rate = (truly_resolved / total * 100) if total > 0 else 0
    mostly_rate = (eval_above_60 / total * 100) if total > 0 else 0
    avg_eval = sum(r["eval_score"] for r in results) / total if total > 0 else 0
    
    print(f"\n  TRUE RESOLUTION RATE:     {true_rate:.1f}%  ({truly_resolved}/{total})")
    print(f"  MOSTLY RESOLVED (≥60):    {mostly_rate:.1f}%  ({eval_above_60}/{total})")
    print(f"  AVG EVAL SCORE:           {avg_eval:.1f}/100")
    print(f"  SELF-CORRECTIONS:         {corrections}/{total}")
    print(f"  TOTAL TIME:               {total_time:.0f}s")
    
    # By subgraph
    print(f"\n  BY SUBGRAPH:")
    by_sg = {}
    for r in results:
        sg = r["subgraph"]
        if sg not in by_sg:
            by_sg[sg] = []
        by_sg[sg].append(r)
    
    for sg, sg_results in by_sg.items():
        sg_resolved = sum(1 for r in sg_results if r["truly_resolved"])
        sg_total = len(sg_results)
        sg_rate = (sg_resolved / sg_total * 100) if sg_total > 0 else 0
        sg_avg = sum(r["eval_score"] for r in sg_results) / sg_total if sg_total > 0 else 0
        print(f"    {sg:12s}: {sg_rate:.0f}% resolved | avg eval={sg_avg:.0f} | ({sg_resolved}/{sg_total})")
    
    # Per ticket
    print(f"\n  PER-TICKET:")
    for r in results:
        status = "✓ RESOLVED" if r["truly_resolved"] else "✗ FAILED"
        print(f"    {r['ticket_id']:10s} [{r['subgraph']:8s}] eval={r['eval_score']:3d}  {status}")
        print(f"              → {r['eval_reason']}")
    
    # Save
    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "true_resolution_rate": true_rate,
        "mostly_resolved_rate": mostly_rate,
        "avg_eval_score": avg_eval,
        "self_corrections": corrections,
        "total_time_sec": total_time,
        "results": results,
    }
    out_path = os.path.join(PROJECT_ROOT, "tests", "production", "fast_test_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Saved to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
