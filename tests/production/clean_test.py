"""
PARWA Clean Resolution Rate Test
=================================
Runs 10 tickets through the ACTUAL SubgraphDispatcher pipeline.
Uses NVIDIA API directly. No complexity. Just results.
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

# 10 tickets covering all 4 subgraphs
TICKETS = [
    {"id": "REF-01", "query": "I bought the Pro plan 12 days ago and it's not what I expected. I want a full refund.", "category": "refund"},
    {"id": "REF-02", "query": "You charged me for a subscription I cancelled last month! I want my money back immediately!", "category": "refund"},
    {"id": "REF-03", "query": "I ordered 45 days ago. Can I still get a partial refund? The product is defective.", "category": "refund"},
    {"id": "TECH-01", "query": "My API integration keeps returning 503 errors. I've checked my auth token and it's valid. What's going on?", "category": "tech"},
    {"id": "TECH-02", "query": "The dashboard won't load. I've tried Chrome and Firefox, cleared cache, but it just spins forever.", "category": "tech"},
    {"id": "TECH-03", "query": "I can't login to my account. It says 'invalid credentials' but I'm using the right password. I've reset it twice.", "category": "tech"},
    {"id": "BILL-01", "query": "I was charged $49.99 twice this month. There should only be one charge on my account.", "category": "billing"},
    {"id": "BILL-02", "query": "Why is my invoice showing $89.99 when my plan is supposed to be $49.99 per month?", "category": "billing"},
    {"id": "GEN-01", "query": "What's the difference between the Pro and Enterprise plans?", "category": "general"},
    {"id": "GEN-02", "query": "This is the worst customer service I've ever experienced. I've been waiting 2 weeks for a response!", "category": "general"},
]

_last_call = 0.0

async def nvidia_call(system_prompt: str, user_prompt: str, model: str = "deepseek-ai/deepseek-v4-flash", max_tokens: int = 800) -> str:
    """Single NVIDIA API call."""
    global _last_call
    now = time.monotonic()
    gap = now - _last_call
    if gap < 0.15:
        await asyncio.sleep(0.15 - gap)

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {NVIDIA_API_KEY}"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(NVIDIA_URL, headers=headers, json=payload)
            _last_call = time.monotonic()

            if resp.status_code == 429:
                await asyncio.sleep(float(resp.headers.get("retry-after", "3")))
                continue
            if resp.status_code == 200:
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            # Fallback model
            if "deepseek" in model and attempt == 0:
                payload["model"] = "meta/llama-3.3-70b-instruct"
                continue
            if attempt < 2:
                await asyncio.sleep(2)
                continue
            return ""
        except Exception:
            _last_call = time.monotonic()
            if attempt < 2:
                await asyncio.sleep(2)
                continue
            return ""
    return ""


async def run_pipeline(ticket: dict) -> dict:
    """Run a ticket through the ACTUAL PARWA SubgraphDispatcher pipeline."""
    from parwa.subgraphs.dispatcher import SubgraphDispatcher
    
    dispatcher = SubgraphDispatcher()
    state = {
        "raw_message": ticket["query"],
        "ticket_id": ticket["id"],
        "variant": "parwa",
    }
    
    start = time.time()
    try:
        result = await dispatcher.process(state)
        elapsed = time.time() - start
        return {
            "ticket_id": ticket["id"],
            "category": ticket["category"],
            "subgraph": result.get("_subgraph", "unknown"),
            "response": result.get("final_response", "")[:500],
            "quality_score": result.get("quality_score", 0.0),
            "techniques": result.get("active_frameworks", []),
            "elapsed_sec": round(elapsed, 1),
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "ticket_id": ticket["id"],
            "category": ticket["category"],
            "subgraph": "error",
            "response": str(e)[:300],
            "quality_score": 0.0,
            "techniques": [],
            "elapsed_sec": round(elapsed, 1),
            "error": str(e),
        }


async def evaluate_ticket(ticket: dict, pipeline_result: dict) -> dict:
    """Independent LLM evaluation of whether the response truly resolves the ticket."""
    eval_prompt = f"""You are evaluating whether an AI customer support response truly resolves a customer's issue.

Customer message: {ticket['query']}
Category: {ticket['category']}

AI Response:
{pipeline_result['response']}

Evaluate STRICTLY:
1. Did the response address the SPECIFIC issue? (not just generic advice)
2. Did it provide CONCRETE next steps or resolution? (not just "we'll look into it")
3. Would the customer need to contact support AGAIN for the same issue?

Score 0-100:
- 80-100: Fully resolved (customer doesn't need to contact again)
- 60-79: Mostly resolved (minor follow-up might be needed)
- 40-59: Partially resolved (customer likely needs to contact again)
- 0-39: Not resolved (customer definitely needs to contact again)

Also answer: Would this customer need to contact support again for the SAME issue? (yes/no)

Respond in EXACTLY this format:
SCORE: [number]
RESOLVED: [yes/no]
REASON: [one sentence]"""

    eval_system = "You are a strict, objective customer support quality evaluator. Be harsh — only give high scores if the response truly resolves the issue completely."
    
    raw = await nvidia_call(eval_system, eval_prompt, max_tokens=200)
    
    # Parse
    score = 0
    resolved = False
    reason = ""
    for line in raw.split("\n"):
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
    
    return {
        "eval_score": score,
        "truly_resolved": resolved,
        "eval_reason": reason,
    }


async def main():
    print("=" * 70)
    print("  PARWA CLEAN RESOLUTION RATE TEST")
    print("  10 tickets × ACTUAL pipeline × NVIDIA evaluation")
    print("=" * 70)
    print()
    
    results = []
    
    for i, ticket in enumerate(TICKETS):
        print(f"[{i+1}/10] Processing {ticket['id']} ({ticket['category']})...")
        
        # Step 1: Run through the actual pipeline
        pipeline_result = await run_pipeline(ticket)
        print(f"  → Subgraph: {pipeline_result['subgraph']}")
        print(f"  → Quality: {pipeline_result['quality_score']:.0f}/100")
        print(f"  → Techniques: {len(pipeline_result['techniques'])} ({', '.join(pipeline_result['techniques'][:5])})")
        print(f"  → Time: {pipeline_result['elapsed_sec']}s")
        if pipeline_result['error']:
            print(f"  → ERROR: {pipeline_result['error'][:100]}")
        
        # Step 2: Independent evaluation
        eval_result = await evaluate_ticket(ticket, pipeline_result)
        print(f"  → Eval Score: {eval_result['eval_score']}/100")
        print(f"  → Truly Resolved: {eval_result['truly_resolved']}")
        print(f"  → Reason: {eval_result['eval_reason']}")
        print()
        
        results.append({**pipeline_result, **eval_result})
        
        # Brief pause between tickets
        await asyncio.sleep(0.5)
    
    # ═══ CALCULATE FINAL METRICS ═══
    print()
    print("=" * 70)
    print("  FINAL RESULTS")
    print("=" * 70)
    
    total = len(results)
    truly_resolved = sum(1 for r in results if r["truly_resolved"])
    quality_above_80 = sum(1 for r in results if r["quality_score"] >= 80)
    eval_above_80 = sum(1 for r in results if r["eval_score"] >= 80)
    eval_above_60 = sum(1 for r in results if r["eval_score"] >= 60)
    
    true_resolution_rate = (truly_resolved / total * 100) if total > 0 else 0
    quality_pass_rate = (quality_above_80 / total * 100) if total > 0 else 0
    eval_pass_rate = (eval_above_80 / total * 100) if total > 0 else 0
    mostly_resolved_rate = (eval_above_60 / total * 100) if total > 0 else 0
    
    avg_quality = sum(r["quality_score"] for r in results) / total if total > 0 else 0
    avg_eval = sum(r["eval_score"] for r in results) / total if total > 0 else 0
    
    # By subgraph
    by_subgraph = {}
    for r in results:
        sg = r["subgraph"]
        if sg not in by_subgraph:
            by_subgraph[sg] = {"total": 0, "resolved": 0, "quality_scores": [], "eval_scores": []}
        by_subgraph[sg]["total"] += 1
        if r["truly_resolved"]:
            by_subgraph[sg]["resolved"] += 1
        by_subgraph[sg]["quality_scores"].append(r["quality_score"])
        by_subgraph[sg]["eval_scores"].append(r["eval_score"])
    
    print(f"\n  TRUE RESOLUTION RATE:   {true_resolution_rate:.1f}%  ({truly_resolved}/{total} truly resolved)")
    print(f"  QUALITY PASS RATE:      {quality_pass_rate:.1f}%  (internal quality >= 80)")
    print(f"  EVAL PASS RATE:         {eval_pass_rate:.1f}%  (LLM eval >= 80)")
    print(f"  MOSTLY RESOLVED RATE:   {mostly_resolved_rate:.1f}%  (LLM eval >= 60)")
    print(f"\n  AVG INTERNAL QUALITY:   {avg_quality:.1f}/100")
    print(f"  AVG LLM EVAL SCORE:     {avg_eval:.1f}/100")
    
    print(f"\n  BY SUBGRAPH:")
    for sg, data in by_subgraph.items():
        sg_rate = (data["resolved"] / data["total"] * 100) if data["total"] > 0 else 0
        sg_avg_q = sum(data["quality_scores"]) / len(data["quality_scores"]) if data["quality_scores"] else 0
        sg_avg_e = sum(data["eval_scores"]) / len(data["eval_scores"]) if data["eval_scores"] else 0
        print(f"    {sg:12s}: {sg_rate:.0f}% resolved | avg quality={sg_avg_q:.0f} | avg eval={sg_avg_e:.0f} | ({data['resolved']}/{data['total']})")
    
    print(f"\n  PER-TICKET DETAIL:")
    for r in results:
        status = "✓ RESOLVED" if r["truly_resolved"] else "✗ NOT RESOLVED"
        print(f"    {r['ticket_id']:10s} [{r['subgraph']:8s}] Q={r['quality_score']:5.0f} E={r['eval_score']:3d} {status}")
        print(f"              → {r['eval_reason']}")
    
    # Save results
    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "true_resolution_rate": true_resolution_rate,
        "quality_pass_rate": quality_pass_rate,
        "eval_pass_rate": eval_pass_rate,
        "mostly_resolved_rate": mostly_resolved_rate,
        "avg_internal_quality": avg_quality,
        "avg_llm_eval": avg_eval,
        "by_subgraph": {sg: {
            "resolution_rate": (d["resolved"]/d["total"]*100) if d["total"] > 0 else 0,
            "avg_quality": sum(d["quality_scores"])/len(d["quality_scores"]) if d["quality_scores"] else 0,
            "avg_eval": sum(d["eval_scores"])/len(d["eval_scores"]) if d["eval_scores"] else 0,
            "total": d["total"],
            "resolved": d["resolved"],
        } for sg, d in by_subgraph.items()},
        "tickets": results,
    }
    
    output_path = os.path.join(PROJECT_ROOT, "tests", "production", "clean_test_results.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n  Results saved to: {output_path}")
    print()
    
    # DIAGNOSIS
    print("=" * 70)
    print("  DIAGNOSIS: Why isn't it higher?")
    print("=" * 70)
    
    not_resolved = [r for r in results if not r["truly_resolved"]]
    if not_resolved:
        print(f"\n  {len(not_resolved)} tickets NOT truly resolved:")
        for r in not_resolved:
            print(f"    {r['ticket_id']} [{r['subgraph']}]: {r['eval_reason']}")
    
    # Check quality gap: internal vs external evaluation
    quality_eval_gap = avg_quality - avg_eval
    if quality_eval_gap > 15:
        print(f"\n  ⚠️  INTERNAL vs EXTERNAL GAP: {quality_eval_gap:.0f} points")
        print(f"     Internal quality scorer rates responses at {avg_quality:.0f}/100")
        print(f"     Independent LLM evaluation rates them at {avg_eval:.0f}/100")
        print(f"     → Your quality scorer is TOO GENEROUS — it's passing responses that don't truly resolve")


if __name__ == "__main__":
    asyncio.run(main())
