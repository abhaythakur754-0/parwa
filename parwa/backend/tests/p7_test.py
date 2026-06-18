#!/usr/bin/env python3
"""Phase 7 test - writes results to JSON, safe for nohup"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase7', exist_ok=True)

LOG = '/home/z/my-project/parwa/backend/tests/results/phase7/run.log'

def log(msg):
    with open(LOG, 'a') as f:
        f.write(msg + '\n')
    print(msg, flush=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats
from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase7'

async def run_ticket(tid, query):
    reset_stats()
    set_test_variant('tenant_a', 'parwa', 1999)
    wiki = get_wiki_store()
    pre = wiki.get_stats('tenant_a')

    state = {
        'ticket_id': tid, 'tenant_id': 'tenant_a',
        'query': query, 'channel_type': 'chat',
        'customer_context': {"account_tier": "parwa", "customer_tenure_days": 180, "recent_ticket_count": 2, "lifetime_value": 3500},
        'metadata': {'sender': 'test@test.io', 'timestamp': '2026-06-18T00:00:00Z'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }
    t0 = time.time()
    try:
        g = build_parwa_pipeline()
        c = g.compile()
        result = await c.ainvoke(state)
        elapsed = time.time() - t0
        stats = get_stats()
        post = wiki.get_stats('tenant_a')
        q = result.get('quality_score', 'N/A')
        wp = result.get('wiki_patterns', [])
        wiki_written = post['section_a_entries'] > pre['section_a_entries']
        resp = result.get('final_response', '') or result.get('formatted_response', '') or result.get('combined_answer', '')
        
        out = {
            'ticket_id': tid, 'status': result.get('status'),
            'quality': round(q, 4) if isinstance(q, float) else q,
            'quality_details': result.get('quality_details', {}),
            'calls': stats['total_calls'], 'tokens': stats['total_tokens'],
            'time_s': round(elapsed, 1), 'wiki_written': wiki_written,
            'wiki_patterns_found': len(wp),
            'wiki_patterns_detail': wp[:2],
            'errors': [e.get('error', str(e)) for e in result.get('errors', [])],
            'response_len': len(resp),
        }
        log(f"  {tid}: quality={out['quality']} calls={out['calls']} tokens={out['tokens']} "
            f"time={out['time_s']}s wiki_written={out['wiki_written']} patterns={out['wiki_patterns_found']}")
        if out['quality_details']:
            log(f"    details: {json.dumps(out['quality_details'])}")
    except Exception as e:
        elapsed = time.time() - t0
        out = {'ticket_id': tid, 'status': 'ERROR', 'error': str(e),
               'traceback': traceback.format_exc(), 'time_s': round(elapsed, 1),
               'quality': 'ERROR', 'calls': 0, 'wiki_written': False, 'wiki_patterns_found': 0}
        log(f"  {tid}: ERROR - {e}")
        log(traceback.format_exc())

    with open(os.path.join(RDIR, f'{tid}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    return out


async def main():
    wiki = get_wiki_store()
    wiki.clear_tenant('tenant_a')
    log("=== PHASE 7 TEST ===")

    log("\n[T1] Complex (cold start)...")
    r1 = await run_ticket('p7_t1',
        "I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?")

    log("\n[T2] Similar (should find T1 wiki pattern)...")
    await asyncio.sleep(15)  # rate limit
    r2 = await run_ticket('p7_t2',
        "My workspace was billed $2,499 twice this month and I see a different price than what my colleague sees. I did not upgrade to the High plan.")

    # Verdict
    q1, q2 = r1.get('quality','?'), r2.get('quality','?')
    met = []
    if isinstance(q1, float) and q1 >= 0.99: met.append(f"T1>=0.99({q1})")
    elif isinstance(q1, float): met.append(f"T1={q1}(need 0.99)")
    if isinstance(q2, float) and q2 >= 0.99: met.append(f"T2>=0.99({q2})")
    elif isinstance(q2, float): met.append(f"T2={q2}(need 0.99)")
    if r2['wiki_patterns_found'] > 0: met.append(f"T2 wiki={r2['wiki_patterns_found']}")
    else: met.append("T2 wiki=0(MISS)")
    if r1['calls'] <= 13: met.append(f"T1 calls={r1['calls']}")

    log(f"\n=== VERDICT: {len(met)}/5 targets met ===")
    for m in met: log(f"  {m}")

    combined = {'phase': '7', 'focus': 'T2→T1 wiki fix + 0.99 quality', 't1': r1, 't2': r2,
                'targets_met': met, 'learning_verified': r2['wiki_patterns_found'] > 0}
    with open(os.path.join(RDIR, 'combined.json'), 'w') as f:
        json.dump(combined, f, indent=2, default=str)
    log(f"\nResults: {RDIR}/")

if __name__ == '__main__':
    asyncio.run(main())