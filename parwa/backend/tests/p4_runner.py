"""Phase 4 Test Runner — Quality + Token Optimization

Tests the FULL optimized pipeline:
  - Node 3: 1 LLM call (was 5) — removed HyDE, MultiQuery, StepBack
  - Node 4: 7 LLM calls (was 9) — removed LeastToMost, UoT
  - Node 6: 2 LLM calls (was 3) — merged CRP revision + scoring
  - Node 5: 0 LLM calls (provide_info only)
  - Node 1: 1 LLM call (unchanged)

Complex path expected: 1+1+7+0+2 = 11 LLM calls (was ~18)
Simple path expected: 1+1+0 = 2 LLM calls (Node 7 = 0 LLM, Node 3 = 1)

File-based result logging for reliability.
"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase4', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase4'

TICKETS = [
    {
        "ticket_id": "tkt_p4_001", "tenant_id": "tenant_a",
        "query": "What are the available pricing plans and their costs?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1999,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 30, "recent_ticket_count": 0, "lifetime_value": 2500},
        "sender": "newbie@startup.io",
        "description": "Simple: pricing FAQ",
        "expected_path": "simple",
        "expected_calls_range": (2, 4),  # Node 1 (1) + Node 3 (1)
    },
    {
        "ticket_id": "tkt_p4_002", "tenant_id": "tenant_a",
        "query": "How do I reset my password if I forgot it?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1998,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 90, "recent_ticket_count": 1, "lifetime_value": 5000},
        "sender": "user@company.com",
        "description": "Simple: password reset",
        "expected_path": "simple",
        "expected_calls_range": (2, 4),
    },
    {
        "ticket_id": "tkt_p4_003", "tenant_id": "tenant_a",
        "query": "What is your refund policy for the Pro plan?",
        "channel_type": "email", "variant_tier": "parwa", "quota": 1997,
        "customer_context": {"account_tier": "pro", "customer_tenure_days": 60, "recent_ticket_count": 0, "lifetime_value": 1500},
        "sender": "curious@test.com",
        "description": "Simple: refund policy info",
        "expected_path": "simple",
        "expected_calls_range": (2, 4),
    },
    {
        "ticket_id": "tkt_p4_004", "tenant_id": "tenant_a",
        "query": "What features are included in the PARWA plan?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1996,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 45, "recent_ticket_count": 0, "lifetime_value": 2500},
        "sender": "evaluator@test.io",
        "description": "Simple: feature inquiry",
        "expected_path": "simple",
        "expected_calls_range": (2, 4),
    },
    {
        "ticket_id": "tkt_p4_005", "tenant_id": "tenant_a",
        "query": "I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1995,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 180, "recent_ticket_count": 2, "lifetime_value": 3500},
        "sender": "confused@test.io",
        "description": "Complex: duplicate charge + pricing discrepancy",
        "expected_path": "complex",
        "expected_calls_range": (10, 25),  # without loop: ~11, with 1 loop: ~20
    },
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

        # Node breakdown (technique count per node)
        node_bd = {}
        for l in result.get('technique_log', []):
            n = f"node_{l.get('node', '?')}"
            node_bd[n] = node_bd.get(n, 0) + 1

        # Which path?
        reached_node_7 = any(l.get('node') == 7 for l in result.get('technique_log', []))
        reached_node_4 = any(l.get('node') == 4 for l in result.get('technique_log', []))
        reached_node_8 = any(l.get('node') == 8 for l in result.get('technique_log', []))
        actual_path = "simple" if (reached_node_7 and not reached_node_4) else "complex"

        resp = result.get('final_response', '') or result.get('formatted_response', '') or result.get('simple_answer', '')
        if not resp and result.get('super_node_answer'):
            resp = result['super_node_answer']

        quality = result.get('quality_score', 'N/A')
        qd = result.get('quality_details', {})

        out = {
            'ticket_id': ticket['ticket_id'],
            'description': ticket['description'],
            'status': result.get('status'),
            'ticket_type': result.get('ticket_type'),
            'complexity': result.get('complexity'),
            'actual_path': actual_path,
            'expected_path': ticket.get('expected_path'),
            'reached_node_7': reached_node_7,
            'reached_node_4': reached_node_4,
            'reached_node_8': reached_node_8,
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
            'response_preview': resp[:500],
            'response_len': len(resp),
            'errors': [e.get('error', str(e)) for e in result.get('errors', [])],
            'node_breakdown': node_bd,
            # Per-node LLM call counts
            'node_1_calls': result.get('node_1_token_usage', 0),
            'node_3_calls': result.get('node_3_token_usage', 0),
            'node_4_calls': result.get('node_4_token_usage', 0),
            'node_5_calls': result.get('node_5_token_usage', 0),
            'node_6_calls': result.get('node_6_token_usage', 0),
            'node_8_calls': result.get('node_8_token_usage', 0),
        }
    except Exception as e:
        elapsed = time.time() - t0
        out = {
            'ticket_id': ticket['ticket_id'], 'description': ticket['description'],
            'status': 'ERROR', 'error': str(e), 'traceback': traceback.format_exc(),
            'time_s': round(elapsed, 1), 'total_llm_calls': 0, 'total_tokens': 0,
            'llm_errors': 1, 'quality_score': 'ERROR', 'node_breakdown': {},
        }

    with open(os.path.join(RDIR, f'ticket_{num}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    # Print compact status
    q = out.get('quality_score', 'N/A')
    if isinstance(q, float):
        q = f"{q:.4f}"
    path_match = "OK" if out.get('actual_path') == ticket.get('expected_path') else "MISMATCH"
    print(f'  #{num} {ticket["description"]}: path={out.get("actual_path")}({path_match}) '
          f'quality={q} calls={out.get("total_llm_calls")} tokens={out.get("total_tokens",0)} '
          f'time={out.get("time_s",0)}s', flush=True)
    return out


async def main():
    all_r = []
    t_all = time.time()

    print('=== PHASE 4 TEST: Quality + Token Optimization ===', flush=True)
    print('Model: NVIDIA Llama 3.1 8B', flush=True)
    print('Optimizations: N3(-4calls), N4(-2calls), N6(-1call) = -7 calls/ticket', flush=True)
    print(f'Target: 0.95+ quality on complex tickets\n', flush=True)

    # Run simple tickets first (fast, ~2 calls each)
    print('--- Simple Tickets (Node 7 path) ---', flush=True)
    for i, t in enumerate(TICKETS[:4]):
        print(f'[{i+1}/5] {t["description"]}...', flush=True)
        r = await run_ticket(i + 1, t)
        all_r.append(r)
        await asyncio.sleep(15)  # rate limit buffer

    # Complex ticket (slow, ~11-20 calls)
    print(f'\n--- Complex Ticket (Node 4→5→6 path) ---', flush=True)
    print(f'[5/5] {TICKETS[4]["description"]}...', flush=True)
    r = await run_ticket(5, TICKETS[4])
    all_r.append(r)

    total = time.time() - t_all

    # Summary
    simple_results = all_r[:4]
    complex_result = all_r[4]

    # Per-node call breakdown for complex ticket
    print(f'\n=== PHASE 4 RESULTS ===', flush=True)
    print(f'\n--- Per-Node LLM Calls (Complex Ticket) ---', flush=True)
    print(f'  Node 1 (Ingest+Classify): {complex_result.get("node_1_calls", "N/A")}', flush=True)
    print(f'  Node 3 (Knowledge):       {complex_result.get("node_3_calls", "N/A")}  [was 5 in Phase 2]', flush=True)
    print(f'  Node 4 (Reasoning):       {complex_result.get("node_4_calls", "N/A")}  [was 9 in Phase 2]', flush=True)
    print(f'  Node 5 (Act+Verify):      {complex_result.get("node_5_calls", "N/A")}', flush=True)
    print(f'  Node 6 (Quality):         {complex_result.get("node_6_calls", "N/A")}  [was 2 in Phase 2, was 3 in P4 draft]', flush=True)
    print(f'  Node 8 (Super):           {complex_result.get("node_8_calls", "N/A")}', flush=True)
    print(f'  TOTAL:                    {complex_result.get("total_llm_calls", "N/A")}  [was ~18 in Phase 2]', flush=True)

    print(f'\n--- Quality Scores ---', flush=True)
    q = complex_result.get('quality_score', 'N/A')
    if isinstance(q, float):
        status = "PASS >= 0.95!" if q >= 0.95 else "PASS >= 0.90" if q >= 0.90 else "BELOW TARGET"
        print(f'  Complex ticket quality: {q:.4f} [{status}]', flush=True)
        print(f'  Reflexion: {complex_result.get("reflexion", "N/A")}', flush=True)
        print(f'  CRP:       {complex_result.get("crp", "N/A")}', flush=True)
        print(f'  Loops:     {complex_result.get("loops", 0)}', flush=True)
        print(f'  Escalated: {complex_result.get("escalated", False)}', flush=True)

    # Simple tickets summary
    print(f'\n--- Simple Tickets (Node 7) ---', flush=True)
    for r in simple_results:
        q_s = r.get('quality_score', 'simple')
        print(f'  {r["description"]}: path={r.get("actual_path")} calls={r.get("total_llm_calls")} '
              f'time={r.get("time_s",0)}s', flush=True)

    total_calls = sum(r.get('total_llm_calls', 0) for r in all_r if isinstance(r.get('total_llm_calls'), int))
    total_tokens = sum(r.get('total_tokens', 0) for r in all_r if isinstance(r.get('total_tokens'), int))
    total_errors = sum(r.get('llm_errors', 0) for r in all_r)
    print(f'\nPhase 4 Total: {total_calls} LLM calls, {total_tokens} tokens, '
          f'{total:.1f}s ({total/60:.1f}min), {total_errors} errors', flush=True)
    print(f'Results saved to {RDIR}/', flush=True)

    # Save combined
    combined = {
        'phase': '4',
        'optimizations': 'N3(-4calls), N4(-2calls), N6(-1call), N8(-1call)',
        'total_time_s': round(total, 1), 'total_time_min': round(total / 60, 1),
        'total_calls': total_calls, 'total_tokens': total_tokens, 'total_errors': total_errors,
        'complex_quality': complex_result.get('quality_score', 'N/A'),
        'complex_calls': complex_result.get('total_llm_calls', 'N/A'),
        'tickets': all_r,
    }
    with open(os.path.join(RDIR, 'combined.json'), 'w') as f:
        json.dump(combined, f, indent=2, default=str)

    # Write status file for polling
    with open('/home/z/my-project/parwa/backend/tests/results/phase4/status.txt', 'w') as f:
        q = complex_result.get('quality_score', 'N/A')
        f.write(f"DONE\nquality={q}\ncalls={total_calls}\ntime={total:.1f}s\nerrors={total_errors}\n")


if __name__ == '__main__':
    asyncio.run(main())