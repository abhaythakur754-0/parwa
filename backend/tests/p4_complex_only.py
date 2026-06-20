"""Phase 4: Complex ticket test only (nohup-safe)."""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase4', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase4'
STATUS_FILE = os.path.join(RDIR, 't5_status.txt')

TICKET = {
    'ticket_id': 'tkt_p4_005',
    'tenant_id': 'tenant_a',
    'query': 'I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?',
    'channel_type': 'chat',
    'variant_tier': 'parwa',
    'quota': 1995,
    'customer_context': {
        'account_tier': 'parwa',
        'customer_tenure_days': 180,
        'recent_ticket_count': 2,
        'lifetime_value': 3500,
    },
    'sender': 'confused@test.io',
}


async def main():
    # Write running status
    with open(STATUS_FILE, 'w') as f:
        f.write('RUNNING\n')

    reset_stats()
    set_test_variant(TICKET['tenant_id'], TICKET['variant_tier'], TICKET['quota'])
    state = {
        'ticket_id': TICKET['ticket_id'],
        'tenant_id': TICKET['tenant_id'],
        'query': TICKET['query'],
        'channel_type': TICKET['channel_type'],
        'customer_context': TICKET['customer_context'],
        'metadata': {'sender': TICKET['sender'], 'timestamp': '2026-06-18T00:00:00Z'},
        'loop_count': 0,
        'total_token_usage': 0,
        'technique_log': [],
        'errors': [],
    }

    t0 = time.time()
    try:
        g = build_parwa_pipeline().compile()
        result = await g.ainvoke(state)
        elapsed = time.time() - t0
        stats = get_stats()

        node_bd = {}
        for l in result.get('technique_log', []):
            n = f"node_{l.get('node', '?')}"
            node_bd[n] = node_bd.get(n, 0) + 1

        reached_7 = any(l.get('node') == 7 for l in result.get('technique_log', []))
        reached_4 = any(l.get('node') == 4 for l in result.get('technique_log', []))
        reached_8 = any(l.get('node') == 8 for l in result.get('technique_log', []))
        actual_path = 'simple' if (reached_7 and not reached_4) else 'complex'

        resp = result.get('final_response', '') or result.get('formatted_response', '') or result.get('simple_answer', '')
        if not resp and result.get('super_node_answer'):
            resp = result['super_node_answer']

        q = result.get('quality_score', 'N/A')
        qd = result.get('quality_details', {})

        out = {
            'ticket_id': TICKET['ticket_id'],
            'description': 'Complex: duplicate charge + pricing discrepancy',
            'status': result.get('status'),
            'ticket_type': result.get('ticket_type'),
            'complexity': result.get('complexity'),
            'actual_path': actual_path,
            'reached_node_4': reached_4,
            'reached_node_8': reached_8,
            'total_llm_calls': stats['total_calls'],
            'total_tokens': stats['total_tokens'],
            'llm_errors': stats['total_errors'],
            'quality_score': q,
            'quality_details': qd,
            'reflexion': qd.get('reflexion', 'N/A'),
            'crp': qd.get('crp', 'N/A'),
            'loops': result.get('loop_count', 0),
            'escalated': bool(result.get('escalation_context')),
            'time_s': round(elapsed, 1),
            'response_preview': resp[:800],
            'response_len': len(resp),
            'errors': [e.get('error', str(e)) for e in result.get('errors', [])],
            'node_breakdown': node_bd,
            'n1_calls': result.get('node_1_token_usage', 0),
            'n3_calls': result.get('node_3_token_usage', 0),
            'n4_calls': result.get('node_4_token_usage', 0),
            'n5_calls': result.get('node_5_token_usage', 0),
            'n6_calls': result.get('node_6_token_usage', 0),
            'n8_calls': result.get('node_8_token_usage', 0),
        }
    except Exception as e:
        elapsed = time.time() - t0
        out = {
            'status': 'ERROR',
            'error': str(e),
            'traceback': traceback.format_exc(),
            'time_s': round(elapsed, 1),
        }

    # Save result
    with open(os.path.join(RDIR, 'ticket_5.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    # Write status
    q = out.get('quality_score', 'N/A')
    calls = out.get('total_llm_calls', 'N/A')
    errs = out.get('llm_errors', 0)
    elapsed = out.get('time_s', 'N/A')
    with open(STATUS_FILE, 'w') as f:
        f.write(f"DONE\nquality={q}\ncalls={calls}\ntime={elapsed}s\nerrors={errs}\n")

    print(f"COMPLEX TICKET DONE: quality={q} calls={calls} time={elapsed}s", flush=True)


if __name__ == '__main__':
    asyncio.run(main())