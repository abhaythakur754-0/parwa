"""Minimal Phase 7 T1 debug"""
import sys, os, asyncio, time, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')

print("1. Imports starting...", flush=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats
from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store

print("2. Imports done", flush=True)

async def main():
    wiki_store = get_wiki_store()
    wiki_store.clear_tenant('tenant_a')
    reset_stats()
    set_test_variant('tenant_a', 'parwa', 1999)

    state = {
        'ticket_id': 'debug_t1', 'tenant_id': 'tenant_a',
        'query': "I was charged $2,499 twice this month and I never upgraded to the High plan.",
        'channel_type': 'chat',
        'customer_context': {"account_tier": "parwa", "customer_tenure_days": 180},
        'metadata': {'sender': 'test@test.io', 'timestamp': '2026-06-18T00:00:00Z'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }

    print("3. Building graph...", flush=True)
    graph = build_parwa_pipeline()
    compiled = graph.compile()

    print("4. Invoking pipeline...", flush=True)
    t0 = time.time()
    try:
        result = await compiled.ainvoke(state)
        elapsed = time.time() - t0
        print(f"5. Pipeline done in {elapsed:.1f}s", flush=True)
        print(f"   status={result.get('status')}", flush=True)
        print(f"   quality={result.get('quality_score')}", flush=True)
        print(f"   errors={result.get('errors', [])}", flush=True)
        
        # Check wiki
        stats = wiki_store.get_stats('tenant_a')
        print(f"   wiki_entries={stats['section_a_entries']}", flush=True)
        
        # Check technique log
        for l in result.get('technique_log', []):
            print(f"   [{l.get('node')}] {l.get('technique')}: {l.get('result_summary', '')[:80]}", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        traceback.print_exc()

asyncio.run(main())