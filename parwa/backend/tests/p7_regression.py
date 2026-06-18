"""Phase 7 Regression Test — Simple tickets only (fast, ~8 calls each)"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

TICKETS = [
    {"ticket_id": "tkt_p7_001", "tenant_id": "tenant_a",
     "query": "What are the available pricing plans and their costs?",
     "channel_type": "chat", "variant_tier": "parwa", "quota": 1999,
     "customer_context": {"account_tier": "parwa", "customer_tenure_days": 30, "recent_ticket_count": 0, "lifetime_value": 2500},
     "sender": "newbie@startup.io", "description": "Simple: pricing FAQ", "expected_path": "simple"},
    {"ticket_id": "tkt_p7_002", "tenant_id": "tenant_a",
     "query": "How do I reset my password if I forgot it?",
     "channel_type": "chat", "variant_tier": "parwa", "quota": 1998,
     "customer_context": {"account_tier": "parwa", "customer_tenure_days": 90, "recent_ticket_count": 1, "lifetime_value": 5000},
     "sender": "user@company.com", "description": "Simple: password reset", "expected_path": "simple"},
    {"ticket_id": "tkt_p7_003", "tenant_id": "tenant_a",
     "query": "What is your refund policy for the Pro plan?",
     "channel_type": "email", "variant_tier": "parwa", "quota": 1997,
     "customer_context": {"account_tier": "pro", "customer_tenure_days": 60, "recent_ticket_count": 0, "lifetime_value": 1500},
     "sender": "curious@test.com", "description": "Simple: refund policy", "expected_path": "simple"},
    {"ticket_id": "tkt_p7_004", "tenant_id": "tenant_a",
     "query": "What features are included in the PARWA plan?",
     "channel_type": "chat", "variant_tier": "parwa", "quota": 1996,
     "customer_context": {"account_tier": "parwa", "customer_tenure_days": 45, "recent_ticket_count": 0, "lifetime_value": 2500},
     "sender": "evaluator@test.io", "description": "Simple: feature inquiry", "expected_path": "simple"},
]


async def run_ticket(num: int, ticket: dict):
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
        reached_node_7 = any(l.get('node') == 7 for l in result.get('technique_log', []))
        reached_node_4 = any(l.get('node') == 4 for l in result.get('technique_log', []))
        actual_path = "simple" if (reached_node_7 and not reached_node_4) else "complex"
        resp = result.get('final_response', '') or result.get('formatted_response', '') or result.get('simple_answer', '')
        quality = result.get('quality_score', 'N/A')
        out = {
            'ticket_id': ticket['ticket_id'], 'description': ticket['description'],
            'status': result.get('status'), 'ticket_type': result.get('ticket_type'),
            'complexity': result.get('complexity'), 'action': result.get('required_action'),
            'actual_path': actual_path, 'expected_path': ticket.get('expected_path'),
            'total_llm_calls': stats['total_calls'], 'total_tokens': stats['total_tokens'],
            'quality_score': quality, 'time_s': round(elapsed, 1),
            'response_len': len(resp), 'errors': result.get('errors', []),
            'response_preview': resp[:300],
        }
    except Exception as e:
        elapsed = time.time() - t0
        out = {'ticket_id': ticket['ticket_id'], 'description': ticket['description'],
               'status': 'ERROR', 'error': str(e), 'time_s': round(elapsed, 1)}

    path_ok = out.get('actual_path') == ticket.get('expected_path')
    status_icon = "OK" if path_ok else "FAIL"
    q = out.get('quality_score', 'N/A')
    q_str = f"{q:.4f}" if isinstance(q, float) else str(q)
    print(f'  #{num} [{status_icon}] {ticket["description"]}: path={out.get("actual_path")} '
          f'type={out.get("ticket_type","?")} q={q_str} '
          f'calls={out.get("total_llm_calls","?")} time={out.get("time_s",0)}s', flush=True)
    if out.get('status') == 'ERROR':
        print(f'       ERROR: {out.get("error", "?")}', flush=True)
    return out


async def main():
    print('=== PHASE 7 REGRESSION: Simple Tickets ===\n', flush=True)
    results = []
    for i, t in enumerate(TICKETS):
        print(f'[{i+1}/4] {t["description"]}...', flush=True)
        r = await run_ticket(i + 1, t)
        results.append(r)
        await asyncio.sleep(10)

    # Summary
    all_ok = all(r.get('actual_path') == r.get('expected_path') for r in results if r.get('status') != 'ERROR')
    errors = sum(1 for r in results if r.get('status') == 'ERROR')
    print(f'\n{"ALL PASS" if all_ok and errors == 0 else "REGRESSION DETECTED"} — {errors} errors', flush=True)


if __name__ == '__main__':
    asyncio.run(main())