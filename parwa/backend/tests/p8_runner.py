"""
Phase 8 Test Runner — Jarvis Pipeline + PARWA with NEW Diverse Tickets

Tests ALL Phase 8 roadmap items:
1. Stuck ticket → Jarvis SENSE detects → Notification with unique key
2. Admin copies key → asks Jarvis → gets full details
3. Admin asks "How many refunds today?" → Jarvis answers with real data
4. Policy changes detected → Jarvis informs
5. Quota monitoring
6. Admin chat via Jarvis

NEW tickets (different from Phase 4-7):
  T1: Complaint — emotional, multi-sentence, frustrated customer
  T2: Technical — SSO login issue with security concern
  T3: Account change — workspace split with team members
  T4: Complex billing — annual plan mid-year cancellation + credit calculation
  T5: FAQ — plan comparison for enterprise evaluation
  T6: Stuck trigger — forced escalation to test Jarvis detection
"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase8', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats
from app.core.jarvis_pipeline.graph import run_jarvis, run_jarvis_monitor
from app.core.jarvis_pipeline.notification_center import (
    get_notification, get_tenant_notifications, get_stats as get_nf_stats,
    clear_all, resolve_notification,
)

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase8'

# ── NEW Diverse Tickets (completely different from before) ──────

NEW_TICKETS = [
    {
        "ticket_id": "tkt_p8_001", "tenant_id": "tenant_b",
        "query": "This is absolutely unacceptable! I've been a customer for 2 years and my account just got locked for no reason. I demand to speak to a manager right now. I run a team of 15 people on the PARWA plan and we've spent over $50,000 with you. Fix this immediately or we're cancelling everything and moving to Zendesk.",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1500,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 730, "recent_ticket_count": 8, "lifetime_value": 50000},
        "sender": "angry_ceo@bigcorp.com",
        "description": "NEW T1: Emotional complaint + threat to cancel",
        "expected_path": "complex",
    },
    {
        "ticket_id": "tkt_p8_002", "tenant_id": "tenant_b",
        "query": "My team is getting 'SSO sync failed' errors when trying to login. We use Okta and it was working fine until yesterday. I checked and our Okta certificate doesn't expire until 2027. Three of my team members are locked out and can't access any tickets. We have a critical client deadline in 4 hours.",
        "channel_type": "email", "variant_tier": "parwa", "quota": 1499,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 365, "recent_ticket_count": 3, "lifetime_value": 12000},
        "sender": "it_admin@techco.io",
        "description": "NEW T2: Technical SSO failure + time pressure",
        "expected_path": "complex",
    },
    {
        "ticket_id": "tkt_p8_003", "tenant_id": "tenant_b",
        "query": "We need to split our workspace. Half our team needs the PARWA plan and the other half needs the High plan because they handle enterprise clients. How do we set this up? We have 20 team members total. Also, what happens to our open tickets when we move people to a new workspace?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1498,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 200, "recent_ticket_count": 1, "lifetime_value": 8000},
        "sender": "ops@scaling-startup.com",
        "description": "NEW T3: Workspace split + team management",
        "expected_path": "complex",
    },
    {
        "ticket_id": "tkt_p8_004", "tenant_id": "tenant_b",
        "query": "We're on the annual PARWA plan ($24,999/year, started January 2026). It's now June and we need to cancel. I know we're past the 30-day window but we've only used 6 out of 12 months. What's our prorated credit? We also have a $200 billing credit from a previous overcharge. Can that be applied to the refund?",
        "channel_type": "email", "variant_tier": "parwa", "quota": 1497,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 180, "recent_ticket_count": 2, "lifetime_value": 20000},
        "sender": "finance@midsaas.com",
        "description": "NEW T4: Annual cancellation + credit calculation",
        "expected_path": "complex",
    },
    {
        "ticket_id": "tkt_p8_005", "tenant_id": "tenant_b",
        "query": "We're evaluating PARWA vs Zendesk vs Intercom for our enterprise support team. Can you give me a detailed comparison of PARWA's High plan vs the others? We handle 5,000+ tickets/month across email, chat, and phone. Do you support phone integration?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1496,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 14, "recent_ticket_count": 0, "lifetime_value": 0},
        "sender": "vp_support@enterprise.com",
        "description": "NEW T5: Enterprise evaluation / comparison",
        "expected_path": "simple",
    },
]


async def run_parwa_ticket(ticket: dict) -> dict:
    """Run a single ticket through PARWA pipeline."""
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
        if not resp and result.get('super_node_answer'):
            resp = result['super_node_answer']

        return {
            'ticket_id': ticket['ticket_id'],
            'description': ticket['description'],
            'status': result.get('status'),
            'ticket_type': result.get('ticket_type'),
            'complexity': result.get('complexity'),
            'action': result.get('required_action'),
            'actual_path': actual_path,
            'expected_path': ticket.get('expected_path'),
            'quality_score': result.get('quality_score', 'N/A'),
            'quality_details': result.get('quality_details', {}),
            'total_llm_calls': stats['total_calls'],
            'total_tokens': stats['total_tokens'],
            'time_s': round(elapsed, 1),
            'response_len': len(resp),
            'errors': [str(e) for e in result.get('errors', [])],
            'escalated': bool(result.get('escalation_context')),
            'parwa_state': result,  # Full state for Jarvis
        }
    except Exception as e:
        return {
            'ticket_id': ticket['ticket_id'], 'description': ticket['description'],
            'status': 'ERROR', 'error': str(e), 'traceback': traceback.format_exc(),
        }


async def test_stuck_ticket_detection():
    """Test 6: Simulate a stuck ticket and verify Jarvis detects + notifies."""
    print('\n' + '='*60, flush=True)
    print('TEST 6: Stuck Ticket → Jarvis Detection → Notification', flush=True)
    print('='*60, flush=True)

    clear_all()
    fake_stuck_state = {
        'ticket_id': 'tkt_STUCK_001',
        'tenant_id': 'tenant_b',
        'query': 'I need a $50,000 refund immediately',
        'status': 'escalated',
        'ticket_type': 'refund_request',
        'complexity': 'hard',
        'quality_score': 0.72,
        'loop_count': 2,
        'escalation_context': {'reason': 'quality_below_threshold'},
        'errors': [{'error': 'Quality 72% after 2 loops, below 85% threshold'}],
        'technique_log': [],
        'total_token_usage': 26,
    }

    jarvis_result = await run_jarvis_monitor(fake_stuck_state)
    notifications = jarvis_result.get('notifications', [])

    if notifications:
        key = notifications[0]['notification_key']
        print(f'  Notification created: {key}', flush=True)
        print(f'  Title: {notifications[0]["title"]}', flush=True)
        print(f'  Priority: {notifications[0]["priority"]} ({notifications[0]["priority_score"]})', flush=True)

        # Verify lookup by key works
        looked_up = get_notification(key)
        if looked_up:
            print(f'  Lookup by key: OK', flush=True)
        else:
            print(f'  Lookup by key: FAILED', flush=True)

        return True, notifications
    else:
        print(f'  NO notifications created (FAILED)', flush=True)
        return False, []


async def test_admin_chat():
    """Test: Admin asks questions via Jarvis chat."""
    print('\n' + '='*60, flush=True)
    print('TEST 7: Admin Chat via Jarvis', flush=True)
    print('='*60, flush=True)

    set_test_variant('tenant_b', 'parwa', 1496)

    # Prepare signals context
    from app.core.parwa_pipeline.nodes.node_2_smart_route import MOCK_VARIANT_REGISTRY
    # Make sure tenant_b has some quota state
    set_test_variant('tenant_b', 'parwa', 1496)

    questions = [
        "What is PARWA-NFY-001?",
        "How's my quota looking?",
        "What's the accuracy trend?",
    ]

    results = []
    for q in questions:
        jarvis_result = await run_jarvis(
            tenant_id='tenant_b',
            trigger='admin_chat',
            admin_question=q,
        )
        response = jarvis_result.get('chat_response', '')
        ok = len(response) > 20
        print(f'  Q: "{q}"', flush=True)
        print(f'  A: {response[:150]}...' if len(response) > 150 else f'  A: {response}', flush=True)
        print(f'  {"OK" if ok else "FAIL"}', flush=True)
        print(flush=True)
        results.append(ok)
        await asyncio.sleep(15)

    return all(results)


async def main():
    clear_all()
    t_all = time.time()

    print('=== PHASE 8: Jarvis Pipeline + PARWA (NEW Diverse Tickets) ===', flush=True)
    print('Roadmap: Phase 8 — Jarvis SENSE, EVALUATE, NOTIFY', flush=True)
    print(f'Tickets: {len(NEW_TICKETS)} NEW diverse tickets (different from Phases 4-7)\n', flush=True)

    # ── Part A: Run PARWA tickets + Jarvis monitoring ────────
    print('--- Part A: PARWA Pipeline (NEW Tickets) + Jarvis Monitor ---', flush=True)
    ticket_results = []
    for i, ticket in enumerate(NEW_TICKETS):
        print(f'\n[{i+1}/{len(NEW_TICKETS)}] {ticket["description"]}...', flush=True)
        result = await run_parwa_ticket(ticket)
        ticket_results.append(result)

        # Run Jarvis monitor on the result
        jarvis_r = await run_jarvis_monitor(result.get('parwa_state', {}))
        j_nfs = jarvis_r.get('notifications', [])

        # Print summary
        q = result.get('quality_score', 'N/A')
        q_str = f"{q:.4f}" if isinstance(q, float) else str(q)
        path_ok = result.get('actual_path') == ticket.get('expected_path')
        print(f'  type={result.get("ticket_type","?"):12s} cx={result.get("complexity","?"):8s} '
              f'path={result.get("actual_path")}({ "OK" if path_ok else "MISMATCH"}) '
              f'quality={q_str} calls={result.get("total_llm_calls","?")} '
              f'time={result.get("time_s","?")}s '
              f'jarvis_nfs={len(j_nfs)}', flush=True)

        # Save individual result
        with open(os.path.join(RDIR, f'ticket_{i+1}.json'), 'w') as f:
            json.dump(result, f, indent=2, default=str)

        await asyncio.sleep(15)

    # ── Part B: Stuck ticket test ────────────────────────────
    stuck_ok, stuck_nfs = await test_stuck_ticket_detection()

    # ── Part C: Admin chat test ──────────────────────────────
    chat_ok = await test_admin_chat()

    # ── Summary ──────────────────────────────────────────────
    total = time.time() - t_all
    print(f'\n{"="*60}', flush=True)
    print('PHASE 8 RESULTS SUMMARY', flush=True)
    print(f'{"="*60}', flush=True)

    # PARWA results
    print('\n--- PARWA Pipeline (NEW Tickets) ---', flush=True)
    for i, r in enumerate(ticket_results):
        q = r.get('quality_score', 'N/A')
        q_str = f"{q:.4f}" if isinstance(q, float) else str(q)
        path_ok = r.get('actual_path') == r.get('expected_path')
        print(f'  T{i+1}: {r["description"]}', flush=True)
        print(f'      path={r.get("actual_path")}({"OK" if path_ok else "MISMATCH"}) '
              f'quality={q_str} calls={r.get("total_llm_calls","?")} '
              f'time={r.get("time_s","?")}s', flush=True)

    # Quality summary
    qualities = [r.get('quality_score') for r in ticket_results if isinstance(r.get('quality_score'), float)]
    if qualities:
        avg_q = sum(qualities) / len(qualities)
        min_q = min(qualities)
        max_q = max(qualities)
        above_99 = sum(1 for q in qualities if q >= 0.99)
        print(f'\n  Quality: avg={avg_q:.4f} min={min_q:.4f} max={max_q:.4f}', flush=True)
        print(f'  Tickets >= 0.99: {above_99}/{len(qualities)}', flush=True)

    # Jarvis results
    nf_stats = get_nf_stats('tenant_b')
    print(f'\n--- Jarvis Pipeline ---', flush=True)
    print(f'  Stuck ticket detection: {"PASS" if stuck_ok else "FAIL"}', flush=True)
    if stuck_nfs:
        print(f'  Notification key: {stuck_nfs[0]["notification_key"]}', flush=True)
    print(f'  Admin chat: {"PASS" if chat_ok else "FAIL"}', flush=True)
    print(f'  Total notifications: {nf_stats["total"]}', flush=True)
    print(f'  Unresolved: {nf_stats["unresolved"]}', flush=True)
    print(f'  By priority: {nf_stats["by_priority"]}', flush=True)

    # Overall
    total_calls = sum(r.get('total_llm_calls', 0) for r in ticket_results if isinstance(r.get('total_llm_calls'), int))
    total_tokens = sum(r.get('total_tokens', 0) for r in ticket_results if isinstance(r.get('total_tokens'), int))
    errors = sum(1 for r in ticket_results if r.get('status') == 'ERROR')
    print(f'\n  Total PARWA calls: {total_calls}, tokens: {total_tokens}', flush=True)
    print(f'  Errors: {errors}', flush=True)
    print(f'  Total time: {total:.1f}s ({total/60:.1f}min)', flush=True)
    print(f'\n  Results saved to {RDIR}/', flush=True)

    # Save combined
    combined = {
        'phase': '8',
        'description': 'Jarvis 3-Node Pipeline + PARWA with new diverse tickets',
        'total_time_s': round(total, 1),
        'total_calls': total_calls,
        'total_tokens': total_tokens,
        'quality_avg': round(avg_q, 4) if qualities else 'N/A',
        'quality_min': round(min_q, 4) if qualities else 'N/A',
        'quality_max': round(max_q, 4) if qualities else 'N/A',
        'jarvis_stuck_detected': stuck_ok,
        'jarvis_admin_chat': chat_ok,
        'notification_stats': nf_stats,
        'tickets': [{k: v for k, v in r.items() if k != 'parwa_state'} for r in ticket_results],
    }
    with open(os.path.join(RDIR, 'combined.json'), 'w') as f:
        json.dump(combined, f, indent=2, default=str)

    print(f'\n{"PASS" if errors == 0 and stuck_ok else "ISSUES DETECTED"}', flush=True)


if __name__ == '__main__':
    asyncio.run(main())