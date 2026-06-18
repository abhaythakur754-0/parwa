"""Phase 5: Ticket 1 — Normal regression test."""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase5', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase5'

async def main():
    reset_stats()
    set_test_variant('tenant_a', 'parwa', 1999)
    state = {
        'ticket_id': 'tkt_p5_001', 'tenant_id': 'tenant_a',
        'query': 'I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?',
        'channel_type': 'chat',
        'customer_context': {'account_tier': 'parwa', 'customer_tenure_days': 180, 'recent_ticket_count': 2, 'lifetime_value': 3500},
        'metadata': {'sender': 'confused@test.io', 'timestamp': '2026-06-18T00:00:00Z'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }
    t0 = time.time()
    g = build_parwa_pipeline().compile()
    result = await g.ainvoke(state)
    elapsed = time.time() - t0
    stats = get_stats()
    q = result.get('quality_score', 'N/A')
    qd = result.get('quality_details', {})
    nodes = set(l.get('node') for l in result.get('technique_log', []))
    resp = result.get('final_response', '') or result.get('formatted_response', '') or ''
    maker_f = len(result.get('maker_flagged', []))
    maker_r = len(result.get('maker_zsv_removed', []))
    maker_s = result.get('maker_bridge_safe', True)

    out = {
        'ticket_id': 'tkt_p5_001', 'description': 'Normal: duplicate charge (regression)',
        'status': result.get('status'), 'quality_score': q, 'quality_details': qd,
        'reflexion': qd.get('reflexion', 'N/A'), 'crp': qd.get('crp', 'N/A'),
        'loops': result.get('loop_count', 0), 'reached_super_node': 8 in nodes,
        'escalated': bool(result.get('escalation_context')),
        'total_llm_calls': stats['total_calls'], 'total_tokens': stats['total_tokens'],
        'llm_errors': stats['total_errors'], 'time_s': round(elapsed, 1),
        'nodes_reached': sorted(list(nodes)), 'response_len': len(resp),
        'n1': result.get('node_1_token_usage', 0), 'n3': result.get('node_3_token_usage', 0),
        'n4': result.get('node_4_token_usage', 0), 'n5': result.get('node_5_token_usage', 0),
        'n6': result.get('node_6_token_usage', 0), 'n8': result.get('node_8_token_usage', 0),
        'maker_flagged': result.get('maker_flagged', []),
        'maker_zsv_removed': result.get('maker_zsv_removed', []),
        'maker_bridge_safe': maker_s,
        'errors': [e.get('error', str(e)) for e in result.get('errors', [])],
    }
    with open(os.path.join(RDIR, 'ticket_1.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    q_str = f'{q:.4f}' if isinstance(q, float) else str(q)
    print(f'T1 REGRESSION: quality={q_str} calls={stats["total_calls"]} time={elapsed:.1f}s loops={out["loops"]}', flush=True)
    print(f'  MAKER: flagged={maker_f} zsv_removed={maker_r} safe={maker_s}', flush=True)
    print(f'  Nodes: {sorted(list(nodes))}', flush=True)

asyncio.run(main())