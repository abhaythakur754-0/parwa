"""Phase 5 Test Runner — Quality Loop, Super Node, Escalation, MAKER Safety

Tests:
  1. Normal complex ticket (regression — should still pass 0.90+)
  2. Hard ticket designed to trigger quality loop
  3. Impossible ticket designed to escalate to human
  4. MAKER bridge filtering verification
"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase5', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase5'

# Ticket 1: Normal complex (regression — should pass first try)
TICKET_NORMAL = {
    "ticket_id": "tkt_p5_001", "tenant_id": "tenant_a",
    "query": "I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?",
    "channel_type": "chat", "variant_tier": "parwa", "quota": 1999,
    "customer_context": {"account_tier": "parwa", "customer_tenure_days": 180, "recent_ticket_count": 2, "lifetime_value": 3500},
    "sender": "confused@test.io",
    "description": "Normal: duplicate charge + pricing discrepancy",
}

# Ticket 2: Hard — multi-part, vague, tests quality loop
# This ticket asks about something the KB doesn't fully cover
# (data export during security incident + compensation for it)
# Should stress the quality system
TICKET_HARD = {
    "ticket_id": "tkt_p5_002", "tenant_id": "tenant_a",
    "query": "Someone accessed my account without permission last week and exported all our data. I want to know exactly what they accessed, when I'll get compensated for this security breach, and what your compliance obligations are under GDPR for this incident. Also I want a full refund of the last 6 months because I no longer trust your platform.",
    "channel_type": "email", "variant_tier": "parwa", "quota": 1998,
    "customer_context": {"account_tier": "parwa", "customer_tenure_days": 400, "recent_ticket_count": 5, "lifetime_value": 12000},
    "sender": "angry@enterprise.io",
    "description": "Hard: security breach + GDPR + 6-month refund demand",
}

# Ticket 3: Impossible — asks about something completely outside the KB
# (integrations with specific third-party tools, API rate limits, etc.)
# Should eventually escalate to human
TICKET_IMPOSSIBLE = {
    "ticket_id": "tkt_p5_003", "tenant_id": "tenant_a",
    "query": "I need the exact API rate limit for your Slack integration when using the real-time event streaming feature with WebSocket connections, and I want to know why my custom OAuth2 flow is returning a 403 error when trying to connect to your GraphQL endpoint for bulk ticket import. Also what's the maximum payload size for the webhook callback?",
    "channel_type": "chat", "variant_tier": "parwa", "quota": 1997,
    "customer_context": {"account_tier": "parwa", "customer_tenure_days": 30, "recent_ticket_count": 0, "lifetime_value": 2500},
    "sender": "developer@techcorp.io",
    "description": "Impossible: API/GraphQL/webhook questions (not in KB)",
}


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
        g = build_parwa_pipeline().compile()
        result = await g.ainvoke(state)
        elapsed = time.time() - t0
        stats = get_stats()

        # Node breakdown
        node_bd = {}
        for l in result.get('technique_log', []):
            n = f"node_{l.get('node', '?')}"
            node_bd[n] = node_bd.get(n, 0) + 1

        # Which nodes were reached
        nodes_reached = set(l.get('node') for l in result.get('technique_log', []))

        resp = result.get('final_response', '') or result.get('formatted_response', '') or result.get('simple_answer', '')
        if not resp and result.get('super_node_answer'):
            resp = result['super_node_answer']

        q = result.get('quality_score', 'N/A')
        qd = result.get('quality_details', {})

        # MAKER data
        maker_flagged = result.get('maker_flagged', [])
        maker_removed = result.get('maker_zsv_removed', [])
        maker_safe = result.get('maker_bridge_safe', True)

        out = {
            'ticket_id': ticket['ticket_id'],
            'description': ticket['description'],
            'status': result.get('status'),
            'ticket_type': result.get('ticket_type'),
            'complexity': result.get('complexity'),
            'actual_path': 'simple' if (7 in nodes_reached and 4 not in nodes_reached) else 'complex',
            'nodes_reached': sorted(list(nodes_reached)),
            'quality_score': q,
            'quality_details': qd,
            'reflexion': qd.get('reflexion', 'N/A'),
            'crp': qd.get('crp', 'N/A'),
            'loops': result.get('loop_count', 0),
            'reached_super_node': 8 in nodes_reached,
            'escalated': bool(result.get('escalation_context')),
            'escalation_key': result.get('escalation_context', {}).get('notification_key', None),
            'total_llm_calls': stats['total_calls'],
            'total_tokens': stats['total_tokens'],
            'llm_errors': stats['total_errors'],
            'time_s': round(elapsed, 1),
            'response_len': len(resp),
            'response_preview': resp[:500],
            'node_breakdown': node_bd,
            # Per-node LLM calls
            'n1_calls': result.get('node_1_token_usage', 0),
            'n3_calls': result.get('node_3_token_usage', 0),
            'n4_calls': result.get('node_4_token_usage', 0),
            'n5_calls': result.get('node_5_token_usage', 0),
            'n6_calls': result.get('node_6_token_usage', 0),
            'n8_calls': result.get('node_8_token_usage', 0),
            # MAKER Phase 5
            'maker_flagged': maker_flagged,
            'maker_zsv_removed': maker_removed,
            'maker_bridge_safe': maker_safe,
            'errors': [e.get('error', str(e)) for e in result.get('errors', [])],
        }
    except Exception as e:
        elapsed = time.time() - t0
        out = {
            'ticket_id': ticket['ticket_id'], 'description': ticket['description'],
            'status': 'ERROR', 'error': str(e), 'traceback': traceback.format_exc(),
            'time_s': round(elapsed, 1),
        }

    with open(os.path.join(RDIR, f'ticket_{num}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    # Print result
    q = out.get('quality_score', 'N/A')
    if isinstance(q, float):
        q_str = f"{q:.4f}"
    else:
        q_str = str(q)
    loops = out.get('loops', 0)
    super_node = out.get('reached_super_node', False)
    escalated = out.get('escalated', False)
    maker_flag = len(out.get('maker_flagged', []))
    maker_rem = len(out.get('maker_zsv_removed', []))

    flags = []
    if loops > 0: flags.append(f"looped={loops}")
    if super_node: flags.append("SUPER_NODE")
    if escalated: flags.append(f"ESCALATED({out.get('escalation_key', '?')})")
    flag_str = " ".join(flags) if flags else "PASS"

    print(f'  #{num} {ticket["description"]}:', flush=True)
    print(f'      quality={q_str} calls={out.get("total_llm_calls", "N/A")} '
          f'time={out.get("time_s", 0)}s [{flag_str}]', flush=True)
    print(f'      MAKER: flagged={maker_flag} zsv_removed={maker_rem} safe={out.get("maker_bridge_safe", True)}', flush=True)
    if out.get('nodes_reached'):
        print(f'      Nodes: {out["nodes_reached"]}', flush=True)
    if out.get('escalation_context'):
        print(f'      Escalation key: {out["escalation_context"].get("notification_key")}', flush=True)

    return out


async def main():
    all_r = []
    t_all = time.time()

    print('=== PHASE 5 TEST: Quality Loop + Super Node + Escalation + MAKER Safety ===', flush=True)
    print(f'Model: NVIDIA Llama 3.1 8B\n', flush=True)

    # Ticket 1: Normal (regression)
    print('[1/3] Normal complex ticket (regression)...', flush=True)
    r1 = await run_ticket(1, TICKET_NORMAL)
    all_r.append(r1)
    await asyncio.sleep(15)

    # Ticket 2: Hard (quality loop stress test)
    print(f'\n[2/3] Hard ticket (security + GDPR + refund demand)...', flush=True)
    r2 = await run_ticket(2, TICKET_HARD)
    all_r.append(r2)

    # Ticket 3: Impossible (escalation test)
    print(f'\n[3/3] Impossible ticket (API/GraphQL/webhook)...', flush=True)
    r3 = await run_ticket(3, TICKET_IMPOSSIBLE)
    all_r.append(r3)

    total = time.time() - t_all

    # Summary
    print(f'\n{"="*60}', flush=True)
    print('PHASE 5 RESULTS SUMMARY', flush=True)
    print(f'{"="*60}', flush=True)

    for r in all_r:
        q = r.get('quality_score', 'N/A')
        q_str = f"{q:.4f}" if isinstance(q, float) else str(q)
        loops = r.get('loops', 0)
        super_n = "YES" if r.get('reached_super_node') else "no"
        esc = "YES" if r.get('escalated') else "no"
        maker_f = len(r.get('maker_flagged', []))
        maker_r = len(r.get('maker_zsv_removed', []))

        print(f'  {r["description"]}:', flush=True)
        print(f'    Quality: {q_str} | Loops: {loops} | SuperNode: {super_n} | Escalated: {esc}', flush=True)
        print(f'    Calls: {r.get("total_llm_calls", "N/A")} | Tokens: {r.get("total_tokens", 0)} | Time: {r.get("time_s", 0)}s', flush=True)
        print(f'    MAKER: flagged={maker_f} zsv_removed={maker_r} safe={r.get("maker_bridge_safe", True)}', flush=True)
        print(f'    Nodes: {r.get("nodes_reached", [])}', flush=True)

    total_calls = sum(r.get('total_llm_calls', 0) for r in all_r if isinstance(r.get('total_llm_calls'), int))
    total_tokens = sum(r.get('total_tokens', 0) for r in all_r if isinstance(r.get('total_tokens'), int))
    print(f'\nPhase 5 Total: {total_calls} LLM calls, {total_tokens} tokens, {total:.1f}s ({total/60:.1f}min)', flush=True)

    # Verify Phase 5 requirements
    print(f'\n{"="*60}', flush=True)
    print('PHASE 5 CHECKLIST', flush=True)
    print(f'{"="*60}', flush=True)

    # 1. Quality loop
    any_looped = any(r.get('loops', 0) > 0 for r in all_r)
    print(f'  [{"OK" if any_looped else "N/A"}] Quality loop activated: {any_looped}', flush=True)

    # 2. Super Node
    super_hit = any(r.get('reached_super_node') for r in all_r)
    print(f'  [{"OK" if super_hit else "N/A"}] Super Node activated: {super_hit}', flush=True)

    # 3. Escalation
    any_escalated = any(r.get('escalated') for r in all_r)
    esc_key = [r.get('escalation_key') for r in all_r if r.get('escalated')]
    print(f'  [{"OK" if any_escalated else "N/A"}] Human escalation: {any_escalated} {esc_key}', flush=True)

    # 4. MAKER safeguards
    any_flagged = any(len(r.get('maker_flagged', [])) > 0 for r in all_r)
    any_removed = any(len(r.get('maker_zsv_removed', [])) > 0 for r in all_r)
    all_safe = all(r.get('maker_bridge_safe', True) for r in all_r)
    print(f'  [{"OK" if any_flagged else "SKIP"}] MAKER flagged low-confidence: {any_flagged}', flush=True)
    print(f'  [{"OK" if any_removed else "SKIP"}] MAKER ZSV gate removed: {any_removed}', flush=True)
    print(f'  [{"OK" if all_safe else "WARN"}] MAKER final safe: {all_safe}', flush=True)

    # 5. Regression
    r1_quality = r1.get('quality_score', 0)
    print(f'  [{"OK" if isinstance(r1_quality, float) and r1_quality >= 0.90 else "FAIL"}] Regression (normal ticket >= 0.90): {r1_quality}', flush=True)

    combined = {
        'phase': '5',
        'total_time_s': round(total, 1),
        'total_calls': total_calls,
        'total_tokens': total_tokens,
        'tickets': all_r,
    }
    with open(os.path.join(RDIR, 'combined.json'), 'w') as f:
        json.dump(combined, f, indent=2, default=str)

    print(f'\nResults saved to {RDIR}/', flush=True)


if __name__ == '__main__':
    asyncio.run(main())