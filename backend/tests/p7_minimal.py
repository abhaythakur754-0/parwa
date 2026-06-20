import sys, os, asyncio, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')

try:
    from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
    from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
    from app.core.parwa_pipeline.llm_client import reset_stats
    from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store

    wiki = get_wiki_store()
    wiki.clear_tenant('tenant_a')
    reset_stats()
    set_test_variant('tenant_a', 'parwa', 1999)

    state = {
        'ticket_id': 'p7_t1', 'tenant_id': 'tenant_a',
        'query': "I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?",
        'channel_type': 'chat',
        'customer_context': {"account_tier": "parwa", "customer_tenure_days": 180},
        'metadata': {'sender': 'test@test.io'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }

    async def run():
        g = build_parwa_pipeline()
        c = g.compile()
        print("invoking...", flush=True)
        result = await c.ainvoke(state)
        print(f"done: q={result.get('quality_score')} status={result.get('status')}", flush=True)
        return result

    result = asyncio.run(run())
    print(f"FINAL: {result.get('quality_score')}", flush=True)

except Exception as e:
    print(f"FATAL: {e}", flush=True)
    traceback.print_exc()
    with open('/tmp/p7_err.txt', 'w') as f:
        f.write(traceback.format_exc())