"""Phase 6 T2: Similar complex ticket (should find wiki pattern from T1)"""
import sys, os, asyncio, time, json
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase6', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats
from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase6'

async def main():
    wiki_store = get_wiki_store()
    reset_stats()
    set_test_variant('tenant_a', 'parwa', 1998)

    pre = wiki_store.get_stats('tenant_a')
    print(f'T2 pre-wiki: Section A = {pre["section_a_entries"]} entries', flush=True)

    state = {
        'ticket_id': 'tkt_p6_t2', 'tenant_id': 'tenant_a',
        'query': 'My workspace was billed $2,499 twice this month and I see a different price than what my colleague sees. I did not upgrade to the High plan.',
        'channel_type': 'chat',
        'customer_context': {'account_tier': 'parwa', 'customer_tenure_days': 200, 'recent_ticket_count': 1, 'lifetime_value': 4000},
        'metadata': {'sender': 'test@test.io'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }
    t0 = time.time()
    graph = build_parwa_pipeline()
    compiled = graph.compile()
    result = await compiled.ainvoke(state)
    elapsed = time.time() - t0
    stats = get_stats()
    # Phase 6: Wiki write-back for complex path
    from app.core.parwa_pipeline.graph_v2 import _wiki_write_on_resolve
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
    techs = result.get('techniques_used', [])

    print(f'T2: path={path} quality={round(q, 4) if isinstance(q, float) else q} '
          f'calls={stats["total_calls"]} tokens={stats["total_tokens"]} time={round(elapsed, 1)}s', flush=True)
    print(f'T2: wiki_written={wiki_written} patterns_found={len(wp)} wiki_logs={wiki_logs}', flush=True)
    print(f'T2: techniques={techs}', flush=True)
    print(f'T2: loops={result.get("loop_count", 0)} escalated={bool(result.get("escalation_context"))}', flush=True)

    if len(wp) > 0:
        print(f'\n*** LEARNING LOOP PROVEN! T2 found {len(wp)} wiki patterns from T1 ***', flush=True)
        for p in wp:
            print(f'  - quality={p.get("quality_achieved")} techniques={p.get("techniques_that_worked")}', flush=True)
    else:
        print(f'\nNote: T2 did not find wiki patterns (keyword overlap may be low — wiki search uses 4+ char terms)', flush=True)

    out = {
        'ticket_id': 'tkt_p6_t2', 'status': result.get('status'), 'path': path,
        'quality': round(q, 4) if isinstance(q, float) else str(q),
        'calls': stats['total_calls'], 'tokens': stats['total_tokens'], 'time_s': round(elapsed, 1),
        'wiki_written': wiki_written, 'wiki_patterns': len(wp),
        'wiki_patterns_detail': wp[:2],
        'wiki_logs': wiki_logs, 'techniques_used': techs,
        'resp_len': len(resp), 'resp_preview': resp[:300],
    }
    with open(os.path.join(RDIR, 'tkt_p6_t2.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    # Load T1 result for comparison
    t1_path = os.path.join(RDIR, 'tkt_p6_t1.json')
    t1 = {}
    if os.path.exists(t1_path):
        with open(t1_path) as f:
            t1 = json.load(f)

    print(f'\n=== PHASE 6 COMPARISON ===', flush=True)
    print(f'T1 (no wiki):  quality={t1.get("quality")} calls={t1.get("calls")} time={t1.get("time_s")}s wiki_written={t1.get("wiki_written")}', flush=True)
    print(f'T2 (wiki):     quality={out["quality"]} calls={out["calls"]} time={out["time_s"]}s patterns_found={out["wiki_patterns"]}', flush=True)
    print(f'Wiki total entries: {post["total_entries"]}', flush=True)

    combined = {
        'phase': '6', 'focus': 'AI Wiki learning loop',
        't1': t1, 't2': out,
        'wiki_stats': post,
        'learning_verified': out['wiki_patterns'] > 0,
    }
    with open(os.path.join(RDIR, 'combined.json'), 'w') as f:
        json.dump(combined, f, indent=2, default=str)

    print(f'\nResults saved to {RDIR}/', flush=True)

asyncio.run(main())