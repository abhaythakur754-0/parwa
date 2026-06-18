import sys, os, asyncio, json, time, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase7', exist_ok=True)
RDIR = '/home/z/my-project/parwa/backend/tests/results/phase7'

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats
from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store

async def run_ticket(tid, query):
    reset_stats()
    set_test_variant('tenant_a', 'parwa', 1999)
    wiki = get_wiki_store()
    pre = wiki.get_stats('tenant_a')
    state = {
        'ticket_id': tid, 'tenant_id': 'tenant_a', 'query': query,
        'channel_type': 'chat',
        'customer_context': {"account_tier": "parwa", "customer_tenure_days": 180, "recent_ticket_count": 2, "lifetime_value": 3500},
        'metadata': {'sender': 'test@test.io', 'timestamp': '2026-06-18T00:00:00Z'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }
    t0 = time.time()
    g = build_parwa_pipeline()
    c = g.compile()
    result = await c.ainvoke(state)
    elapsed = time.time() - t0
    stats = get_stats()
    post = wiki.get_stats('tenant_a')
    q = result.get('quality_score', 'N/A')
    wp = result.get('wiki_patterns', [])
    wiki_written = post['section_a_entries'] > pre['section_a_entries']
    resp = result.get('final_response', '') or result.get('formatted_response', '') or ''
    out = {
        'ticket_id': tid, 'status': result.get('status'),
        'quality': round(q, 4) if isinstance(q, float) else q,
        'quality_details': result.get('quality_details', {}),
        'calls': stats['total_calls'], 'tokens': stats['total_tokens'],
        'time_s': round(elapsed, 1), 'wiki_written': wiki_written,
        'wiki_patterns_found': len(wp), 'wiki_patterns_detail': wp[:2],
        'response_len': len(resp), 'errors': [str(e) for e in result.get('errors', [])],
    }
    print(f"  {tid}: quality={out['quality']} calls={out['calls']} tokens={out['tokens']} time={out['time_s']}s wiki_written={wiki_written} patterns={len(wp)}", flush=True)
    with open(os.path.join(RDIR, f'{tid}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    return out

async def main():
    wiki = get_wiki_store()
    wiki.clear_tenant('tenant_a')
    print("=== PHASE 7 TEST ===", flush=True)

    print("\n[T1] Complex (cold start)...", flush=True)
    r1 = await run_ticket('p7_t1',
        "I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?")

    print("\n[T2] Similar (should find T1 wiki pattern)...", flush=True)
    print("  (rate limit wait 15s...)", flush=True)
    await asyncio.sleep(15)
    r2 = await run_ticket('p7_t2',
        "My workspace was billed $2,499 twice this month and I see a different price than what my colleague sees. I did not upgrade to the High plan.")

    q1, q2 = r1.get('quality','?'), r2.get('quality','?')
    met = []
    if isinstance(q1, float) and q1 >= 0.99: met.append(f"T1={q1}>=0.99")
    elif isinstance(q1, float): met.append(f"T1={q1}<0.99")
    if isinstance(q2, float) and q2 >= 0.99: met.append(f"T2={q2}>=0.99")
    elif isinstance(q2, float): met.append(f"T2={q2}<0.99")
    if r2['wiki_patterns_found'] > 0: met.append(f"wiki_match={r2['wiki_patterns_found']}")
    else: met.append("wiki_match=0")
    if r1['calls'] <= 13: met.append(f"calls_T1={r1['calls']}")

    print(f"\n=== VERDICT: {len(met)}/5 ===", flush=True)
    for m in met: print(f"  {m}", flush=True)

    combined = {'phase':'7', 't1':r1, 't2':r2, 'targets_met':met,
                'learning_verified': r2['wiki_patterns_found']>0}
    with open(os.path.join(RDIR, 'combined.json'), 'w') as f:
        json.dump(combined, f, indent=2, default=str)

try:
    asyncio.run(main())
except Exception as e:
    print(f"FATAL: {e}", flush=True)
    traceback.print_exc()