"""Phase 6 T1: Complex ticket (seeds wiki)"""
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
    wiki_store.clear_tenant('tenant_a')
    reset_stats()
    set_test_variant('tenant_a', 'parwa', 1999)

    pre = wiki_store.get_stats('tenant_a')
    state = {
        'ticket_id': 'tkt_p6_t1', 'tenant_id': 'tenant_a',
        'query': 'I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?',
        'channel_type': 'chat',
        'customer_context': {'account_tier': 'parwa', 'customer_tenure_days': 180, 'recent_ticket_count': 2, 'lifetime_value': 3500},
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
    qp = result.get('quality_passed')
    if qp:
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

    print(f'T1: path={path} quality={round(q, 4) if isinstance(q, float) else q} '
          f'calls={stats["total_calls"]} tokens={stats["total_tokens"]} time={round(elapsed, 1)}s', flush=True)
    print(f'T1: wiki_written={wiki_written} patterns_found={len(wp)} wiki_logs={wiki_logs}', flush=True)
    print(f'T1: techniques={techs}', flush=True)
    print(f'T1: loops={result.get("loop_count", 0)} escalated={bool(result.get("escalation_context"))}', flush=True)

    out = {
        'ticket_id': 'tkt_p6_t1', 'status': result.get('status'), 'path': path,
        'quality': round(q, 4) if isinstance(q, float) else str(q),
        'calls': stats['total_calls'], 'tokens': stats['total_tokens'], 'time_s': round(elapsed, 1),
        'wiki_written': wiki_written, 'wiki_patterns': len(wp), 'wiki_logs': wiki_logs,
        'techniques_used': techs, 'resp_len': len(resp), 'resp_preview': resp[:300],
    }
    with open(os.path.join(RDIR, 'tkt_p6_t1.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print('T1 saved', flush=True)

asyncio.run(main())