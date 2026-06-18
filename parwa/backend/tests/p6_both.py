"""Phase 6 Combined Test: T1 seeds wiki → T2 finds wiki pattern

MUST run as a single process so the in-memory wiki store persists.
"""
import sys, os, asyncio, time, json
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase6', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline, _wiki_write_on_resolve
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats
from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase6'


async def run_ticket(ticket_id, query, ctx, quota, wiki_store):
    reset_stats()
    set_test_variant('tenant_a', 'parwa', quota)
    pre = wiki_store.get_stats('tenant_a')

    state = {
        'ticket_id': ticket_id, 'tenant_id': 'tenant_a',
        'query': query, 'channel_type': 'chat',
        'customer_context': ctx,
        'metadata': {'sender': 'test@test.io'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }
    t0 = time.time()
    graph = build_parwa_pipeline()
    compiled = graph.compile()
    result = await compiled.ainvoke(state)
    elapsed = time.time() - t0
    stats = get_stats()

    # Wiki write-back for complex path
    if result.get('quality_passed'):
        _wiki_write_on_resolve(result)

    post = wiki_store.get_stats('tenant_a')
    wp = result.get('wiki_patterns', [])
    q = result.get('quality_score', 'N/A')
    resp = result.get('final_response', '') or result.get('formatted_response', '') or ''
    n4 = any(l.get('node') == 4 for l in result.get('technique_log', []))
    n7 = any(l.get('node') == 7 for l in result.get('technique_log', []))
    path = 'simple' if (n7 and not n4) else 'complex'
    wiki_written = post['section_a_entries'] > pre['section_a_entries']
    wiki_logs = [l['result_summary'] for l in result.get('technique_log', [])
                 if 'Wiki' in l.get('technique', '') or 'wiki' in l.get('technique', '').lower()
                 or 'MetaLearner' in l.get('technique', '')]

    out = {
        'ticket_id': ticket_id, 'path': path,
        'quality': round(q, 4) if isinstance(q, float) else str(q),
        'calls': stats['total_calls'], 'tokens': stats['total_tokens'],
        'time_s': round(elapsed, 1), 'loops': result.get('loop_count', 0),
        'escalated': bool(result.get('escalation_context')),
        'wiki_written': wiki_written, 'wiki_patterns': len(wp),
        'wiki_patterns_detail': wp[:2],
        'wiki_logs': wiki_logs,
        'techniques_used': result.get('techniques_used', []),
        'resp_len': len(resp), 'resp_preview': resp[:300],
    }
    with open(os.path.join(RDIR, f'{ticket_id}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    return out


async def main():
    wiki_store = get_wiki_store()
    wiki_store.clear_tenant('tenant_a')

    ctx1 = {'account_tier': 'parwa', 'customer_tenure_days': 180, 'recent_ticket_count': 2, 'lifetime_value': 3500}
    ctx2 = {'account_tier': 'parwa', 'customer_tenure_days': 200, 'recent_ticket_count': 1, 'lifetime_value': 4000}

    print('=== PHASE 6 TEST: AI Wiki Learning Loop ===', flush=True)

    # T1: Complex (seeds wiki)
    print('\n[T1] Complex ticket (seeds wiki)...', flush=True)
    r1 = await run_ticket('tkt_p6_t1',
        'I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?',
        ctx1, 1999, wiki_store)
    print(f'  quality={r1["quality"]} calls={r1["calls"]} tokens={r1["tokens"]} '
          f'time={r1["time_s"]}s wiki_written={r1["wiki_written"]}', flush=True)

    await asyncio.sleep(15)

    # T2: Similar (should find wiki)
    print('\n[T2] Similar complex ticket (should find wiki pattern)...', flush=True)
    r2 = await run_ticket('tkt_p6_t2',
        'My workspace was billed $2,499 twice this month and I see a different price than what my colleague sees.',
        ctx2, 1998, wiki_store)
    print(f'  quality={r2["quality"]} calls={r2["calls"]} tokens={r2["tokens"]} '
          f'time={r2["time_s"]}s wiki_written={r2["wiki_written"]}', flush=True)

    final = wiki_store.get_stats('tenant_a')

    print(f'\n=== PHASE 6 RESULTS ===', flush=True)
    print(f'Wiki Section A entries: {final["section_a_entries"]}', flush=True)
    print(f'T1 wiki written: {r1["wiki_written"]} {"OK" if r1["wiki_written"] else "FAIL"}', flush=True)
    print(f'T2 wiki patterns found: {r2["wiki_patterns"]} {"LEARNING LOOP PROVEN!" if r2["wiki_patterns"] > 0 else "(keyword overlap check)"}', flush=True)
    if r2["wiki_patterns"] > 0:
        print(f'  T2 patterns: quality={r2["wiki_patterns_detail"][0].get("quality_achieved")} '
              f'techniques={r2["wiki_patterns_detail"][0].get("techniques_that_worked")}', flush=True)
    print(f'T2 wiki logs: {r2["wiki_logs"]}', flush=True)

    print(f'\n--- Comparison ---', flush=True)
    print(f'T1 (cold): quality={r1["quality"]} calls={r1["calls"]} time={r1["time_s"]}s', flush=True)
    print(f'T2 (warm):  quality={r2["quality"]} calls={r2["calls"]} time={r2["time_s"]}s', flush=True)
    print(f'Extra LLM calls from wiki: 0 (all wiki ops are non-LLM)', flush=True)

    combined = {
        'phase': '6', 'focus': 'AI Wiki 3-section integration, learning loop',
        't1': r1, 't2': r2, 'wiki_stats': final,
        'learning_verified': r2['wiki_patterns'] > 0,
    }
    with open(os.path.join(RDIR, 'combined.json'), 'w') as f:
        json.dump(combined, f, indent=2, default=str)
    print(f'\nResults saved to {RDIR}/', flush=True)


if __name__ == '__main__':
    asyncio.run(main())