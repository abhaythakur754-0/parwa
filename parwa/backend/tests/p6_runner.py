"""Phase 6 Test Runner — AI Wiki & Learning Loop

Tests:
  1. First complex ticket → resolves → wiki pattern written to Section A
  2. Second similar ticket → wiki Section A found → knowledge enriched → resolves
  3. Verify learning effect: wiki stats, pattern count, techniques tracked

Key metrics:
  - 0 extra LLM calls (all wiki ops are non-LLM)
  - Wiki Section A entries grow after each resolution
  - Second similar ticket sees wiki patterns in Node 3 and Node 4
  - Quality should be >= Phase 4 baseline (0.95+) on complex tickets

File-based result logging for reliability.
"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase6', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats
from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase6'

TICKETS = [
    {
        "ticket_id": "tkt_p6_001", "tenant_id": "tenant_a",
        "query": "I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1999,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 180, "recent_ticket_count": 2, "lifetime_value": 3500},
        "sender": "confused@test.io",
        "description": "Complex T1: duplicate charge + pricing discrepancy (FIRST — seeds wiki)",
        "expected_path": "complex",
    },
    {
        "ticket_id": "tkt_p6_002", "tenant_id": "tenant_a",
        "query": "My workspace was billed $2,499 twice this month and I see a different price than what my colleague sees. I did not upgrade to the High plan.",
        "channel_type": "email", "variant_tier": "parwa", "quota": 1998,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 200, "recent_ticket_count": 1, "lifetime_value": 4000},
        "sender": "billing@test.io",
        "description": "Complex T2: SIMILAR to T1 (should find wiki pattern)",
        "expected_path": "complex",
    },
    {
        "ticket_id": "tkt_p6_003", "tenant_id": "tenant_a",
        "query": "What are the available pricing plans and their costs?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1997,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 30, "recent_ticket_count": 0, "lifetime_value": 2500},
        "sender": "newbie@startup.io",
        "description": "Simple T3: pricing FAQ",
        "expected_path": "simple",
    },
    {
        "ticket_id": "tkt_p6_004", "tenant_id": "tenant_a",
        "query": "How much does the PARWA plan cost per month and what features are included?",
        "channel_type": "chat", "variant_tier": "parwa", "quota": 1996,
        "customer_context": {"account_tier": "parwa", "customer_tenure_days": 15, "recent_ticket_count": 0, "lifetime_value": 1000},
        "sender": "prospective@startup.io",
        "description": "Simple T4: SIMILAR to T3 (should find wiki pattern)",
        "expected_path": "simple",
    },
]


async def run_ticket(num: int, ticket: dict, wiki_store):
    reset_stats()
    set_test_variant(ticket['tenant_id'], ticket['variant_tier'], ticket['quota'])

    # Pre-ticket wiki stats
    pre_stats = wiki_store.get_stats(ticket['tenant_id'])

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

        # Post-ticket wiki stats
        post_stats = wiki_store.get_stats(ticket['tenant_id'])

        # Node breakdown
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

        # Phase 6 specific: wiki patterns found, wiki techniques used
        wiki_patterns = result.get('wiki_patterns', [])
        wiki_techniques_in_log = [
            l for l in result.get('technique_log', [])
            if l.get('technique') in ('AIWiki', 'WikiEnrich', 'PolicySyncCheck')
        ]
        techniques_used = result.get('techniques_used', [])

        # Check if wiki write-back happened (look for Wiki WRITE in logs or check store)
        wiki_written = post_stats['section_a_entries'] > pre_stats['section_a_entries']

        out = {
            'ticket_id': ticket['ticket_id'],
            'description': ticket['description'],
            'status': result.get('status'),
            'ticket_type': result.get('ticket_type'),
            'complexity': result.get('complexity'),
            'actual_path': actual_path,
            'expected_path': ticket.get('expected_path'),
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
            'response_preview': resp[:500],
            'errors': [e.get('error', str(e)) for e in result.get('errors', [])],
            'node_breakdown': node_bd,
            'node_1_calls': result.get('node_1_token_usage', 0),
            'node_3_calls': result.get('node_3_token_usage', 0),
            'node_4_calls': result.get('node_4_token_usage', 0),
            'node_5_calls': result.get('node_5_token_usage', 0),
            'node_6_calls': result.get('node_6_token_usage', 0),
            'node_8_calls': result.get('node_8_token_usage', 0),
            # Phase 6 specific
            'wiki_patterns_found': len(wiki_patterns),
            'wiki_techniques_in_log': wiki_techniques_in_log,
            'techniques_used': techniques_used,
            'wiki_pre_section_a': pre_stats['section_a_entries'],
            'wiki_post_section_a': post_stats['section_a_entries'],
            'wiki_written': wiki_written,
            'wiki_total_entries': post_stats['total_entries'],
        }
    except Exception as e:
        elapsed = time.time() - t0
        out = {
            'ticket_id': ticket['ticket_id'], 'description': ticket['description'],
            'status': 'ERROR', 'error': str(e), 'traceback': traceback.format_exc(),
            'time_s': round(elapsed, 1), 'total_llm_calls': 0, 'total_tokens': 0,
            'llm_errors': 1, 'quality_score': 'ERROR', 'node_breakdown': {},
            'wiki_patterns_found': 0, 'wiki_written': False,
            'wiki_pre_section_a': 0, 'wiki_post_section_a': 0,
        }

    with open(os.path.join(RDIR, f'ticket_{num}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    q = out.get('quality_score', 'N/A')
    if isinstance(q, float):
        q = f"{q:.4f}"
    path_match = "OK" if out.get('actual_path') == ticket.get('expected_path') else "MISMATCH"
    wiki_msg = f"wiki_written={out.get('wiki_written')} patterns={out.get('wiki_patterns_found')}"
    print(f'  #{num} {ticket["description"]}: path={out.get("actual_path")}({path_match}) '
          f'quality={q} calls={out.get("total_llm_calls")} tokens={out.get("total_tokens",0)} '
          f'time={out.get("time_s",0)}s | {wiki_msg}', flush=True)
    return out


async def main():
    all_r = []
    t_all = time.time()

    # Clear wiki for clean test
    wiki_store = get_wiki_store()
    wiki_store.clear_tenant('tenant_a')

    print('=== PHASE 6 TEST: AI Wiki & Learning Loop ===', flush=True)
    print('Model: NVIDIA Llama 3.1 8B', flush=True)
    print('Phase 6: Wiki Section A read/write, pattern enrichment, 0 extra LLM calls')
    print('Learning test: T1 seeds wiki → T2 should find T1\'s pattern\n', flush=True)

    # Ticket 1: Complex (seeds wiki)
    print('--- Ticket 1: Complex (FIRST — seeds wiki) ---', flush=True)
    print(f'[1/4] {TICKETS[0]["description"]}...', flush=True)
    r = await run_ticket(1, TICKETS[0], wiki_store)
    all_r.append(r)
    await asyncio.sleep(15)

    # Ticket 2: Complex SIMILAR (should find wiki pattern from T1)
    print(f'\n--- Ticket 2: Complex SIMILAR (should find wiki pattern) ---', flush=True)
    print(f'[2/4] {TICKETS[1]["description"]}...', flush=True)
    r = await run_ticket(2, TICKETS[1], wiki_store)
    all_r.append(r)
    await asyncio.sleep(15)

    # Ticket 3: Simple (seeds wiki for simple path)
    print(f'\n--- Ticket 3: Simple (seeds wiki) ---', flush=True)
    print(f'[3/4] {TICKETS[2]["description"]}...', flush=True)
    r = await run_ticket(3, TICKETS[2], wiki_store)
    all_r.append(r)
    await asyncio.sleep(15)

    # Ticket 4: Simple SIMILAR (should find wiki pattern from T3)
    print(f'\n--- Ticket 4: Simple SIMILAR (should find wiki pattern) ---', flush=True)
    print(f'[4/4] {TICKETS[3]["description"]}...', flush=True)
    r = await run_ticket(4, TICKETS[3], wiki_store)
    all_r.append(r)

    total = time.time() - t_all

    # Final wiki stats
    final_stats = wiki_store.get_stats('tenant_a')

    # Summary
    print(f'\n=== PHASE 6 RESULTS ===', flush=True)

    print(f'\n--- Wiki Learning Loop ---', flush=True)
    print(f'  Wiki Section A entries: {final_stats["section_a_entries"]}', flush=True)
    print(f'  Wiki total entries:     {final_stats["total_entries"]}', flush=True)

    # Check learning: T2 should have found patterns from T1
    t1_written = all_r[0].get('wiki_written', False)
    t2_patterns = all_r[1].get('wiki_patterns_found', 0)
    t3_written = all_r[2].get('wiki_written', False)
    t4_patterns = all_r[3].get('wiki_patterns_found', 0)

    print(f'\n--- Learning Verification ---', flush=True)
    print(f'  T1 wiki written (seed):    {"YES" if t1_written else "NO"} {"✅" if t1_written else "❌"}', flush=True)
    print(f'  T2 found wiki patterns:     {t2_patterns} {"✅" if t2_patterns > 0 else "⚠️ (may need keyword overlap)"}', flush=True)
    print(f'  T3 wiki written (seed):    {"YES" if t3_written else "NO"} {"✅" if t3_written else "❌"}', flush=True)
    print(f'  T4 found wiki patterns:     {t4_patterns} {"✅" if t4_patterns > 0 else "⚠️ (may need keyword overlap)"}', flush=True)

    # Quality comparison
    print(f'\n--- Quality Scores ---', flush=True)
    for r in all_r:
        q = r.get('quality_score', 'N/A')
        if isinstance(q, float):
            q_str = f"{q:.4f}"
        else:
            q_str = str(q)
        wiki_enrich = any(l.get('technique') == 'WikiEnrich' for l in r.get('wiki_techniques_in_log', []))
        wiki_tag = " [WIKI-ENRICHED]" if wiki_enrich else ""
        print(f'  {r["description"]}: quality={q_str} calls={r.get("total_llm_calls")}{wiki_tag}', flush=True)

    total_calls = sum(r.get('total_llm_calls', 0) for r in all_r if isinstance(r.get('total_llm_calls'), int))
    total_tokens = sum(r.get('total_tokens', 0) for r in all_r if isinstance(r.get('total_tokens'), int))
    total_errors = sum(r.get('llm_errors', 0) for r in all_r)
    print(f'\nPhase 6 Total: {total_calls} LLM calls, {total_tokens} tokens, '
          f'{total:.1f}s ({total/60:.1f}min), {total_errors} errors', flush=True)
    print(f'Results saved to {RDIR}/', flush=True)

    # Save combined
    combined = {
        'phase': '6',
        'focus': 'AI Wiki 3-section integration, learning loop',
        'total_time_s': round(total, 1), 'total_time_min': round(total / 60, 1),
        'total_calls': total_calls, 'total_tokens': total_tokens, 'total_errors': total_errors,
        'wiki_final_stats': final_stats,
        'learning_verification': {
            't1_wiki_written': t1_written,
            't2_found_patterns': t2_patterns,
            't3_wiki_written': t3_written,
            't4_found_patterns': t4_patterns,
        },
        'tickets': all_r,
    }
    with open(os.path.join(RDIR, 'combined.json'), 'w') as f:
        json.dump(combined, f, indent=2, default=str)

    with open(os.path.join(RDIR, 'status.txt'), 'w') as f:
        f.write(f"DONE\nwiki_entries={final_stats['section_a_entries']}\n"
                f"calls={total_calls}\ntime={total:.1f}s\nerrors={total_errors}\n")


if __name__ == '__main__':
    asyncio.run(main())