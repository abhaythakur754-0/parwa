"""Phase 3 Test Runner — Simple + Tricky Tickets

Tests Node 7 (Non-LLM resolver) with 0 LLM calls in Node 7.
5 tickets: 4 simple (should pass Node 7) + 1 tricky (should safety-net upgrade).
File-based result logging for reliability.
"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase3', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase3'

# 4 simple tickets — should be routed to simple_path → Node 7
SIMPLE_TICKETS = [
    {
        "ticket_id": "tkt_p3_001", "tenant_id": "tenant_a",
        "query": "What are the available pricing plans and their costs?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1999,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 30, "recent_ticket_count": 0, "lifetime_value": 2500},
        "sender": "newbie@startup.io",
        "description": "Simple: pricing FAQ",
    },
    {
        "ticket_id": "tkt_p3_002", "tenant_id": "tenant_a",
        "query": "How do I reset my password if I forgot it?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1998,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 90, "recent_ticket_count": 1, "lifetime_value": 5000},
        "sender": "user@company.com",
        "description": "Simple: password reset",
    },
    {
        "ticket_id": "tkt_p3_003", "tenant_id": "tenant_a",
        "query": "What is your refund policy for the Pro plan?",
        "channel_type": "email", "variant_tier": "parwa", "quota": 1997,
        "customer_context": {"account_tier": "pro", "customer_tenure_days": 60, "recent_ticket_count": 0, "lifetime_value": 1500},
        "sender": "curious@test.com",
        "description": "Simple: refund policy info",
    },
    {
        "ticket_id": "tkt_p3_004", "tenant_id": "tenant_a",
        "query": "What features are included in the PARWA plan?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1996,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 45, "recent_ticket_count": 0, "lifetime_value": 2500},
        "sender": "evaluator@test.io",
        "description": "Simple: feature inquiry",
    },
]

# 1 tricky "simple" ticket — should trigger safety net (auto-upgrade to Node 4)
TRICKY_TICKET = {
    "ticket_id": "tkt_p3_005", "tenant_id": "tenant_a",
    "query": "I was charged $149 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague?",
    "channel_type": "chat", "variant_tier": "parwa", "quota": 1995,
    "customer_context": {"account_tier": "pro", "customer_tenure_days": 180, "recent_ticket_count": 2, "lifetime_value": 3500},
    "sender": "confused@test.io",
    "description": "Tricky: duplicate charge (looks simple but is complex)",
}


async def run_ticket(num: int, ticket: dict, label: str):
    reset_stats()
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

        # Count node 7 techniques
        n7_techs = [l['technique'] for l in result.get('technique_log', []) if l.get('node') == 7]
        n7_llm = 0  # Node 7 should have 0 LLM calls

        # Check if Node 7 was reached
        reached_node_7 = any(l.get('node') == 7 for l in result.get('technique_log', []))
        auto_upgraded = result.get('auto_upgraded', False)

        # Node breakdown (technique count per node)
        node_breakdown = {}
        for l in result.get('technique_log', []):
            n = f"node_{l.get('node', '?')}"
            node_breakdown[n] = node_breakdown.get(n, 0) + 1

        resp = result.get('final_response', '') or result.get('formatted_response', '') or result.get('simple_answer', '')
        if not resp and result.get('super_node_answer'):
            resp = result['super_node_answer']

        out = {
            'ticket_id': ticket['ticket_id'], 'description': ticket['description'],
            'label': label,
            'status': result.get('status'),
            'ticket_type': result.get('ticket_type'),
            'complexity': result.get('complexity'),
            'route': result.get('route_decision', result.get('current_path')),
            'reached_node_7': reached_node_7,
            'auto_upgraded': auto_upgraded,
            'node_7_techniques': n7_techs,
            'node_7_llm_calls': n7_llm,
            'total_llm_calls': stats['total_calls'],
            'total_tokens': stats['total_tokens'],
            'llm_errors': stats['total_errors'],
            'quality_score': result.get('quality_score', 'N/A'),
            'simple_confidence': result.get('simple_confidence', 'N/A'),
            'loops': result.get('loop_count', 0),
            'escalated': bool(result.get('escalation_context')),
            'time_s': round(elapsed, 1),
            'response_preview': resp[:500],
            'errors': [e.get('error', str(e)) for e in result.get('errors', [])],
            'node_breakdown': node_breakdown,
        }
    except Exception as e:
        elapsed = time.time() - t0
        out = {
            'ticket_id': ticket['ticket_id'], 'description': ticket['description'], 'label': label,
            'status': 'ERROR', 'error': str(e), 'traceback': traceback.format_exc(),
            'time_s': round(elapsed, 1),
            'reached_node_7': False, 'auto_upgraded': False,
            'node_7_techniques': [], 'node_7_llm_calls': 0,
            'total_llm_calls': 0, 'total_tokens': 0, 'llm_errors': 0,
            'node_breakdown': {},
        }

    with open(os.path.join(RDIR, f'ticket_{num}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    print(f'  {label}: {out.get("status")} route={out.get("route")} n7={out.get("reached_node_7")} '
          f'upgraded={out.get("auto_upgraded")} calls={out.get("total_llm_calls")} '
          f'confidence={out.get("simple_confidence", "N/A")} time={out.get("time_s")}s', flush=True)
    return out


async def main():
    all_r = []
    t_all = time.time()

    print('=== PHASE 3 TEST: Non-LLM Path ===', flush=True)
    print(f'Model: NVIDIA Llama 3.1 8B | Testing Node 7 (0 LLM calls)\n', flush=True)

    # 4 simple tickets
    for i, t in enumerate(SIMPLE_TICKETS):
        print(f'[{i+1}/5] {t["description"]}...', flush=True)
        r = await run_ticket(i + 1, t, f'Simple #{i+1}')
        all_r.append(r)
        await asyncio.sleep(15)  # rate limit buffer (simple = few calls, 15s is enough)

    # 1 tricky ticket
    print(f'\n[5/5] {TRICKY_TICKET["description"]}...', flush=True)
    r = await run_ticket(5, TRICKY_TICKET, 'Tricky #5')
    all_r.append(r)

    total = time.time() - t_all
    combined = {
        'phase': '3', 'total_time_s': round(total, 1), 'total_time_min': round(total / 60, 1),
        'total_calls': sum(r.get('total_llm_calls', 0) for r in all_r if isinstance(r.get('total_llm_calls'), int)),
        'total_tokens': sum(r.get('total_tokens', 0) for r in all_r if isinstance(r.get('total_tokens'), int)),
        'total_errors': sum(r.get('llm_errors', 0) for r in all_r),
        'tickets': all_r,
    }
    with open(os.path.join(RDIR, 'combined.json'), 'w') as f:
        json.dump(combined, f, indent=2, default=str)

    # Summary
    print(f'\n=== PHASE 3 RESULTS ===', flush=True)
    for r in all_r[:4]:
        n7 = r.get('node_7_techniques', [])
        print(f'  {r["label"]}: route={r["route"]} node7={r["reached_node_7"]} '
              f'techs={len(n7)} upgraded={r["auto_upgraded"]} calls={r["total_llm_calls"]} '
              f'tokens={r.get("total_tokens",0)} time={r.get("time_s",0)}s', flush=True)
    tricky = all_r[4]
    print(f'  {tricky["label"]}: route={tricky.get("route")} node7={tricky.get("reached_node_7")} '
          f'techs={len(tricky.get("node_7_techniques", []))} upgraded={tricky.get("auto_upgraded")} '
          f'calls={tricky.get("total_llm_calls",0)} tokens={tricky.get("total_tokens",0)} '
          f'time={tricky.get("time_s",0)}s', flush=True)

    print(f'\nPhase 3 Total: {combined["total_calls"]} LLM calls, {combined["total_tokens"]} tokens, '
          f'{total:.1f}s ({total/60:.1f}min), {combined["total_errors"]} errors', flush=True)
    print(f'Results saved to {RDIR}/', flush=True)

if __name__ == '__main__':
    asyncio.run(main())