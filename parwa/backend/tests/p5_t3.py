"""Phase 5: Ticket 3 — Impossible ticket (API/GraphQL/webhook — not in KB)."""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase5', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase5'

async def main():
    reset_stats()
    set_test_variant('tenant_a', 'parwa', 1997)
    state = {
        'ticket_id': 'tkt_p5_003', 'tenant_id': 'tenant_a',
        'query': 'I need the exact API rate limit for your Slack integration when using the real-time event streaming feature with WebSocket connections, and I want to know why my custom OAuth2 flow is returning a 403 error when trying to connect to your GraphQL endpoint for bulk ticket import. Also what is the maximum payload size for the webhook callback?',
        'channel_type': 'chat',
        'customer_context': {'account_tier': 'parwa', 'customer_tenure_days': 30, 'recent_ticket_count': 0, 'lifetime_value': 2500},
        'metadata': {'sender': 'developer@techcorp.io', 'timestamp': '2026-06-18T00:00:00Z'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }
    t0 = time.time()
    try:
        g = build_parwa_pipeline().compile()
        result = await g.ainvoke(state)
        elapsed = time.time() - t0
        stats = get_stats()
        q = result.get('quality_score', 'N/A')
        qd = result.get('quality_details', {})
        nodes = set(l.get('node') for l in result.get('technique_log', []))
        resp = result.get('final_response', '') or result.get('formatted_response', '') or result.get('simple_answer', '')
        if not resp and result.get('super_node_answer'):
            resp = result['super_node_answer']

        out = {
            'ticket_id': 'tkt_p5_003', 'description': 'Impossible: API/GraphQL/webhook (not in KB)',
            'status': result.get('status'), 'quality_score': q, 'quality_details': qd,
            'reflexion': qd.get('reflexion', 'N/A'), 'crp': qd.get('crp', 'N/A'),
            'loops': result.get('loop_count', 0), 'reached_super_node': 8 in nodes,
            'escalated': bool(result.get('escalation_context')),
            'escalation_key': result.get('escalation_context', {}).get('notification_key', None),
            'escalation_context_keys': list(result.get('escalation_context', {}).keys()) if result.get('escalation_context') else [],
            'total_llm_calls': stats['total_calls'], 'total_tokens': stats['total_tokens'],
            'llm_errors': stats['total_errors'], 'time_s': round(elapsed, 1),
            'nodes_reached': sorted(list(nodes)), 'response_len': len(resp),
            'response_preview': resp[:500],
            'n1': result.get('node_1_token_usage', 0), 'n3': result.get('node_3_token_usage', 0),
            'n4': result.get('node_4_token_usage', 0), 'n5': result.get('node_5_token_usage', 0),
            'n6': result.get('node_6_token_usage', 0), 'n8': result.get('node_8_token_usage', 0),
            'maker_flagged': result.get('maker_flagged', []),
            'maker_zsv_removed': result.get('maker_zsv_removed', []),
            'maker_bridge_safe': result.get('maker_bridge_safe', True),
            'errors': [e.get('error', str(e)) for e in result.get('errors', [])],
        }
    except Exception as e:
        elapsed = time.time() - t0
        out = {'status': 'ERROR', 'error': str(e), 'traceback': traceback.format_exc(), 'time_s': round(elapsed, 1)}

    with open(os.path.join(RDIR, 'ticket_3.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    q = out.get('quality_score', 'N/A')
    q_str = f'{q:.4f}' if isinstance(q, float) else str(q)
    loops = out.get('loops', 0)
    super_n = out.get('reached_super_node', False)
    esc = out.get('escalated', False)
    esc_key = out.get('escalation_key')
    maker_f = len(out.get('maker_flagged', []))
    maker_r = len(out.get('maker_zsv_removed', []))

    status_parts = [f'quality={q_str}', f'calls={out.get("total_llm_calls", "N/A")}', f'time={out.get("time_s", 0)}s']
    if loops > 0: status_parts.append(f'loops={loops}')
    if super_n: status_parts.append('SUPER_NODE')
    if esc: status_parts.append(f'ESCALATED({esc_key})')

    print(f'T3 IMPOSSIBLE: {" | ".join(status_parts)}', flush=True)
    print(f'  MAKER: flagged={maker_f} zsv_removed={maker_r} safe={out.get("maker_bridge_safe", True)}', flush=True)
    print(f'  Nodes: {out.get("nodes_reached", [])}', flush=True)
    print(f'  Reflexion: {out.get("reflexion", "N/A")} CRP: {out.get("crp", "N/A")}', flush=True)
    if esc:
        print(f'  ESCALATION KEY: {esc_key}', flush=True)
        esc_ctx = out.get('escalation_context', {})
        if 'all_solutions' in esc_ctx:
            print(f'  Super Node solutions count: {len(esc_ctx["all_solutions"])}', flush=True)
        if 'super_node_quality' in esc_ctx:
            print(f'  Super Node quality: {esc_ctx["super_node_quality"]}', flush=True)

    with open(os.path.join(RDIR, 't3_status.txt'), 'w') as f:
        f.write(f'DONE\nquality={q}\ncalls={out.get("total_llm_calls", "N/A")}\nloops={loops}\nsuper_node={super_n}\nescalated={esc}\nkey={esc_key}\n')

asyncio.run(main())