"""Phase 7 Quick Test — Complex ticket only (saves ~60s on simple tickets)"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase7', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase7'

TICKET = {
    "ticket_id": "tkt_p7_005", "tenant_id": "tenant_a",
    "query": "I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?",
    "channel_type": "chat", "variant_tier": "parwa", "quota": 1995,
    "customer_context": {"account_tier": "parwa", "customer_tenure_days": 180, "recent_ticket_count": 2, "lifetime_value": 3500},
    "sender": "confused@test.io",
    "description": "Complex: duplicate charge + pricing discrepancy",
}

async def main():
    reset_stats()
    set_test_variant(TICKET['tenant_id'], TICKET['variant_tier'], TICKET['quota'])
    state = {
        'ticket_id': TICKET['ticket_id'], 'tenant_id': TICKET['tenant_id'],
        'query': TICKET['query'], 'channel_type': TICKET['channel_type'],
        'customer_context': TICKET['customer_context'],
        'metadata': {'sender': TICKET['sender'], 'timestamp': '2026-06-18T00:00:00Z'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }
    t0 = time.time()
    try:
        graph = build_parwa_pipeline()
        compiled = graph.compile()
        result = await compiled.ainvoke(state)
        elapsed = time.time() - t0
        stats = get_stats()

        node_bd = {}
        for l in result.get('technique_log', []):
            n = f"node_{l.get('node', '?')}"
            node_bd[n] = node_bd.get(n, 0) + 1

        reached_node_4 = any(l.get('node') == 4 for l in result.get('technique_log', []))
        reached_node_7 = any(l.get('node') == 7 for l in result.get('technique_log', []))
        actual_path = "simple" if (reached_node_7 and not reached_node_4) else "complex"

        resp = result.get('final_response', '') or result.get('formatted_response', '') or result.get('simple_answer', '')
        if not resp and result.get('super_node_answer'):
            resp = result['super_node_answer']

        quality = result.get('quality_score', 'N/A')
        qd = result.get('quality_details', {})

        out = {
            'ticket_id': TICKET['ticket_id'],
            'description': TICKET['description'],
            'status': result.get('status'),
            'ticket_type': result.get('ticket_type'),
            'complexity': result.get('complexity'),
            'action': result.get('required_action'),
            'actual_path': actual_path,
            'total_llm_calls': stats['total_calls'],
            'total_tokens': stats['total_tokens'],
            'llm_errors': stats['total_errors'],
            'quality_score': quality,
            'quality_details': qd,
            'reflexion': qd.get('reflexion', 'N/A'),
            'crp': qd.get('crp', 'N/A'),
            'loops': result.get('loop_count', 0),
            'escalated': bool(result.get('escalation_context')),
            'time_s': round(elapsed, 1),
            'response_len': len(resp),
            'response_preview': resp[:800],
            'errors': [e.get('error', str(e)) for e in result.get('errors', [])],
            'node_breakdown': node_bd,
            'node_1_calls': result.get('node_1_token_usage', 0),
            'node_3_calls': result.get('node_3_token_usage', 0),
            'node_4_calls': result.get('node_4_token_usage', 0),
            'node_5_calls': result.get('node_5_token_usage', 0),
            'node_6_calls': result.get('node_6_token_usage', 0),
            'node_8_calls': result.get('node_8_token_usage', 0),
        }
    except Exception as e:
        elapsed = time.time() - t0
        import traceback as tb
        out = {
            'ticket_id': TICKET['ticket_id'], 'description': TICKET['description'],
            'status': 'ERROR', 'error': str(e), 'traceback': tb.format_exc(),
            'time_s': round(elapsed, 1), 'quality_score': 'ERROR',
        }

    with open(os.path.join(RDIR, 'ticket_5_quick.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    # Print results
    q = out.get('quality_score', 'N/A')
    q_str = f"{q:.4f}" if isinstance(q, float) else str(q)
    print(f'\n=== PHASE 7 QUICK TEST: Complex Ticket Only ===', flush=True)
    print(f'  ticket_type:   {out.get("ticket_type", "?")}  (Phase 4 was: billing)', flush=True)
    print(f'  complexity:    {out.get("complexity", "?")}  (Phase 4 was: simple -> NOW FIXED)', flush=True)
    print(f'  action:        {out.get("action", "?")}  (Phase 4 was: plan_change -> NOW investigate_billing)', flush=True)
    print(f'  path:          {out.get("actual_path", "?")}', flush=True)
    print(f'  quality:       {q_str}', flush=True)
    if isinstance(q, float):
        print(f'  Phase 4 delta: {"+" if q - 0.9506 >= 0 else ""}{q - 0.9506:.4f}', flush=True)
        print(f'  Target >0.99: {"ACHIEVED!" if q >= 0.99 else "NOT YET" if q >= 0.95 else "NEEDS MORE WORK"}', flush=True)
    print(f'  calls:         {out.get("total_llm_calls", "?")}', flush=True)
    print(f'  tokens:        {out.get("total_tokens", "?")}', flush=True)
    print(f'  time:          {out.get("time_s", "?")}s', flush=True)
    print(f'  loops:         {out.get("loops", 0)}', flush=True)
    print(f'  errors:        {out.get("errors", [])}', flush=True)
    print(f'\n  Quality details: {json.dumps(out.get("quality_details", {}), indent=4, default=str)}', flush=True)
    print(f'\n  Node calls: N1={out.get("node_1_calls",0)} N3={out.get("node_3_calls",0)} '
          f'N4={out.get("node_4_calls",0)} N5={out.get("node_5_calls",0)} '
          f'N6={out.get("node_6_calls",0)} N8={out.get("node_8_calls",0)}', flush=True)
    print(f'\n  Response preview ({out.get("response_len",0)} chars):', flush=True)
    print(f'  {out.get("response_preview", "")[:600]}', flush=True)

if __name__ == '__main__':
    asyncio.run(main())