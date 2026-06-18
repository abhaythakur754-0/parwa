"""Run tricky ticket 5 for Phase 3 — file-based result logging"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase3'

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

async def main():
    reset_stats()
    ticket = {
        'ticket_id': 'tkt_p3_005', 'tenant_id': 'tenant_a',
        'query': 'I was charged $149 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague?',
        'channel_type': 'chat', 'variant_tier': 'parwa', 'quota': 1995,
        'customer_context': {'account_tier': 'pro', 'customer_tenure_days': 180, 'recent_ticket_count': 2, 'lifetime_value': 3500},
        'sender': 'confused@test.io',
        'description': 'Tricky: duplicate charge (looks simple but is complex)',
    }
    set_test_variant(ticket['tenant_id'], ticket['variant_tier'], ticket['quota'])
    state = {
        'ticket_id': ticket['ticket_id'], 'tenant_id': ticket['tenant_id'],
        'query': ticket['query'], 'channel_type': ticket['channel_type'],
        'customer_context': ticket['customer_context'],
        'metadata': {'sender': ticket['sender'], 'timestamp': '2026-06-18T00:00:00Z'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }
    t0 = time.time()
    try:
        graph = build_parwa_pipeline()
        compiled = graph.compile()
        result = await compiled.ainvoke(state)
        elapsed = time.time() - t0
        stats = get_stats()

        n7_techs = [l['technique'] for l in result.get('technique_log', []) if l.get('node') == 7]
        n7_reached = any(l.get('node') == 7 for l in result.get('technique_log', []))
        auto_up = result.get('auto_upgraded', False)
        node_bd = {}
        for l in result.get('technique_log', []):
            n = f"node_{l.get('node', '?')}"
            node_bd[n] = node_bd.get(n, 0) + 1

        resp = result.get('final_response', '') or result.get('formatted_response', '') or result.get('simple_answer', '')
        if not resp and result.get('super_node_answer'):
            resp = result['super_node_answer']

        out = {
            'ticket_id': ticket['ticket_id'], 'description': ticket['description'], 'label': 'Tricky#5',
            'status': result.get('status'), 'ticket_type': result.get('ticket_type'),
            'complexity': result.get('complexity'),
            'route': result.get('route_decision', result.get('current_path')),
            'reached_node_7': n7_reached, 'auto_upgraded': auto_up,
            'node_7_techniques': n7_techs, 'node_7_llm_calls': 0,
            'total_llm_calls': stats['total_calls'], 'total_tokens': stats['total_tokens'],
            'llm_errors': stats['total_errors'],
            'quality_score': result.get('quality_score', 'N/A'),
            'simple_confidence': result.get('simple_confidence', 'N/A'),
            'loops': result.get('loop_count', 0),
            'escalated': bool(result.get('escalation_context')),
            'time_s': round(elapsed, 1), 'response_preview': resp[:500],
            'errors': [], 'node_breakdown': node_bd,
        }
    except Exception as e:
        elapsed = time.time() - t0
        out = {
            'ticket_id': ticket['ticket_id'], 'description': ticket['description'], 'label': 'Tricky#5',
            'status': 'ERROR', 'error': str(e), 'traceback': traceback.format_exc(),
            'time_s': round(elapsed, 1), 'reached_node_7': False, 'auto_upgraded': False,
            'node_7_techniques': [], 'node_7_llm_calls': 0,
            'total_llm_calls': 0, 'total_tokens': 0, 'llm_errors': 0, 'node_breakdown': {},
        }

    with open(os.path.join(RDIR, 'ticket_5.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    # Write status file for easy polling
    with open(os.path.join(RDIR, 't5_status.txt'), 'w') as f:
        f.write(f"DONE status={out.get('status')} route={out.get('route')} n7={out.get('reached_node_7')} "
                f"upgraded={out.get('auto_upgraded')} calls={out.get('total_llm_calls')} "
                f"tokens={out.get('total_tokens', 0)} conf={out.get('simple_confidence', 'N/A')} "
                f"quality={out.get('quality_score', 'N/A')} time={out.get('time_s')}s\n")

asyncio.run(main())