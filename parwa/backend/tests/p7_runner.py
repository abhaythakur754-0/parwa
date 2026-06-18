"""Phase 7 Test — T2→T1 Wiki Pattern Matching + 0.99 Quality Target

Tests:
  1. T1 Complex ticket → resolves → wiki pattern written (cold start)
  2. T2 Similar complex ticket → wiki pattern FOUND + enriched → quality 0.99+

Key verifications:
  - Wiki search normalization fixes T2→T1 matching
  - Quality formula recalibration hits 0.99+
  - Same 13 LLM calls, same ~11K tokens (no regression)
"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase7', exist_ok=True)

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats
from app.core.parwa_pipeline.ai_wiki_store import get_wiki_store

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase7'

async def run_ticket(ticket_id, tenant_id, query, variant_tier, quota, customer_context, wiki_store):
    reset_stats()
    set_test_variant(tenant_id, variant_tier, quota)

    pre_stats = wiki_store.get_stats(tenant_id)

    state = {
        'ticket_id': ticket_id, 'tenant_id': tenant_id,
        'query': query, 'channel_type': 'chat',
        'customer_context': customer_context,
        'metadata': {'sender': 'test@test.io', 'timestamp': '2026-06-18T00:00:00Z'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }
    t0 = time.time()
    try:
        graph = build_parwa_pipeline()
        compiled = graph.compile()
        result = await compiled.ainvoke(state)
        elapsed = time.time() - t0
        stats = get_stats()
        post_stats = wiki_store.get_stats(tenant_id)

        # Extract Phase 7 specific data
        wiki_patterns = result.get('wiki_patterns', [])
        wiki_log_entries = [
            l for l in result.get('technique_log', [])
            if l.get('technique') in ('AIWiki', 'WikiEnrich', 'PolicySyncCheck', 'MetaLearner',
                                       'StructureCheck', 'AnswerAdequacy', 'KBGrounding',
                                       'FederatedReasoning')
        ]

        quality = result.get('quality_score', result.get('simple_confidence', 'N/A'))
        quality_details = result.get('quality_details', {})
        resp = (result.get('final_response', '') or result.get('formatted_response', '') 
                or result.get('simple_answer', ''))
        
        reached_node_4 = any(l.get('node') == 4 for l in result.get('technique_log', []))
        reached_node_7 = any(l.get('node') == 7 for l in result.get('technique_log', []))
        actual_path = "simple" if (reached_node_7 and not reached_node_4) else "complex"

        wiki_written = post_stats['section_a_entries'] > pre_stats['section_a_entries']

        out = {
            'ticket_id': ticket_id,
            'status': result.get('status'),
            'ticket_type': result.get('ticket_type'),
            'actual_path': actual_path,
            'total_llm_calls': stats['total_calls'],
            'total_tokens': stats['total_tokens'],
            'quality_score': round(quality, 4) if isinstance(quality, float) else quality,
            'quality_details': quality_details,
            'time_s': round(elapsed, 1),
            'loops': result.get('loop_count', 0),
            'escalated': bool(result.get('escalation_context')),
            'response_len': len(resp),
            'response_preview': resp[:400],
            'errors': [e.get('error', str(e)) for e in result.get('errors', [])],
            # Phase 7: Wiki pattern matching verification
            'wiki_patterns_found': len(wiki_patterns),
            'wiki_patterns_detail': wiki_patterns[:2],
            'wiki_techniques_in_log': [l['result_summary'] for l in wiki_log_entries],
            'techniques_used': result.get('techniques_used', []),
            'wiki_pre_section_a': pre_stats['section_a_entries'],
            'wiki_post_section_a': post_stats['section_a_entries'],
            'wiki_written': wiki_written,
            'wiki_total_entries': post_stats['total_entries'],
            # Phase 7: Quality details
            'non_llm_95': quality_details.get('all_non_llm_95', False),
            'non_llm_90': quality_details.get('all_non_llm_90', False),
        }
    except Exception as e:
        elapsed = time.time() - t0
        out = {
            'ticket_id': ticket_id, 'status': 'ERROR',
            'error': str(e), 'traceback': traceback.format_exc(),
            'time_s': round(elapsed, 1), 'quality_score': 'ERROR',
            'total_llm_calls': 0, 'wiki_written': False,
            'wiki_patterns_found': 0,
        }

    with open(os.path.join(RDIR, f'{ticket_id}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    return out


async def main():
    wiki_store = get_wiki_store()
    wiki_store.clear_tenant('tenant_a')

    print('=== PHASE 7 TEST: Wiki Pattern Matching + 0.99 Quality ===', flush=True)
    print('Target: quality >= 0.99, T2 wiki patterns found > 0', flush=True)

    # Ticket 1: Complex (seeds wiki)
    print('\n[T1] Complex ticket (seeds wiki, cold start)...', flush=True)
    r1 = await run_ticket(
        'tkt_p7_t1', 'tenant_a',
        "I was charged $2,499 twice this month and I never upgraded to the High plan. Why am I seeing different prices than my colleague on the same workspace?",
        'parwa', 1999,
        {"account_tier": "parwa", "customer_tenure_days": 180, "recent_ticket_count": 2, "lifetime_value": 3500},
        wiki_store,
    )
    q1 = r1.get('quality_score', 'ERR')
    print(f'  T1: quality={q1} calls={r1["total_llm_calls"]} tokens={r1["total_tokens"]} '
          f'time={r1["time_s"]}s wiki_written={r1["wiki_written"]} '
          f'patterns_found={r1["wiki_patterns_found"]}', flush=True)
    if isinstance(q1, float):
        status1 = "PASS" if q1 >= 0.99 else "NEEDS_WORK"
    else:
        status1 = "ERROR"
    print(f'  T1 quality target (0.99): {status1}', flush=True)

    await asyncio.sleep(15)  # rate limit

    # Ticket 2: Similar complex (should find wiki pattern from T1)
    print('\n[T2] Similar complex ticket (should find T1 wiki pattern)...', flush=True)
    r2 = await run_ticket(
        'tkt_p7_t2', 'tenant_a',
        "My workspace was billed $2,499 twice this month and I see a different price than what my colleague sees. I did not upgrade to the High plan.",
        'parwa', 1998,
        {"account_tier": "parwa", "customer_tenure_days": 200, "recent_ticket_count": 1, "lifetime_value": 4000},
        wiki_store,
    )
    q2 = r2.get('quality_score', 'ERR')
    print(f'  T2: quality={q2} calls={r2["total_llm_calls"]} tokens={r2["total_tokens"]} '
          f'time={r2["time_s"]}s wiki_written={r2["wiki_written"]} '
          f'patterns_found={r2["wiki_patterns_found"]}', flush=True)
    if isinstance(q2, float):
        status2 = "PASS" if q2 >= 0.99 else "NEEDS_WORK"
    else:
        status2 = "ERROR"
    print(f'  T2 quality target (0.99): {status2}', flush=True)

    # Wiki pattern matching verification
    print(f'\n=== WIKI PATTERN MATCHING ===', flush=True)
    final_stats = wiki_store.get_stats('tenant_a')
    print(f'Wiki Section A entries: {final_stats["section_a_entries"]}', flush=True)
    print(f'T1 wiki written: {"YES" if r1["wiki_written"] else "NO"}', flush=True)
    print(f'T2 found wiki patterns: {r2["wiki_patterns_found"]}', flush=True)
    if r2["wiki_patterns_found"] > 0:
        print(f'T2 wiki enrichment: ACTIVE (T2→T1 pattern matching WORKS!)', flush=True)
        print(f'T2 wiki pattern detail: {json.dumps(r2["wiki_patterns_detail"][0] if r2["wiki_patterns_detail"] else {}, indent=2)}', flush=True)
    else:
        print(f'WARNING: T2→T1 pattern matching still failing!', flush=True)

    # Quality details
    print(f'\n=== QUALITY DETAILS ===', flush=True)
    print(f'T1 quality: {q1}', flush=True)
    print(f'T2 quality: {q2}', flush=True)
    if isinstance(q1, (int, float)):
        print(f'T1 quality_details: {json.dumps(r1.get("quality_details", {}), indent=2)}', flush=True)
    if isinstance(q2, (int, float)):
        print(f'T2 quality_details: {json.dumps(r2.get("quality_details", {}), indent=2)}', flush=True)

    # LLM calls
    print(f'\n=== LLM CALLS (should be 13 each) ===', flush=True)
    print(f'T1: {r1["total_llm_calls"]} calls', flush=True)
    print(f'T2: {r2["total_llm_calls"]} calls', flush=True)

    # Final verdict
    print(f'\n=== PHASE 7 VERDICT ===', flush=True)
    targets_met = []
    if isinstance(q1, float) and q1 >= 0.99:
        targets_met.append("T1 quality >= 0.99")
    if isinstance(q2, float) and q2 >= 0.99:
        targets_met.append("T2 quality >= 0.99")
    if r2["wiki_patterns_found"] > 0:
        targets_met.append("T2→T1 wiki pattern matching")
    if r1["total_llm_calls"] <= 13:
        targets_met.append("T1 LLM calls <= 13")
    if r2["total_llm_calls"] <= 13:
        targets_met.append("T2 LLM calls <= 13")

    if len(targets_met) == 5:
        print(f'ALL TARGETS MET: {", ".join(targets_met)}', flush=True)
    else:
        print(f'Targets met: {len(targets_met)}/5', flush=True)
        for t in targets_met:
            print(f'  OK: {t}', flush=True)
        if not (isinstance(q1, float) and q1 >= 0.99):
            print(f'  MISS: T1 quality (got {q1})', flush=True)
        if not (isinstance(q2, float) and q2 >= 0.99):
            print(f'  MISS: T2 quality (got {q2})', flush=True)
        if r2["wiki_patterns_found"] == 0:
            print(f'  MISS: T2 wiki patterns (got 0)', flush=True)

    combined = {
        'phase': '7',
        'focus': 'T2→T1 wiki pattern matching fix + 0.99 quality calibration',
        't1': r1, 't2': r2,
        'targets_met': targets_met,
        'total_targets': 5,
        'wiki_final_stats': final_stats,
        'learning_verified': r2['wiki_patterns_found'] > 0,
    }
    with open(os.path.join(RDIR, 'combined.json'), 'w') as f:
        json.dump(combined, f, indent=2, default=str)

    with open(os.path.join(RDIR, 'status.txt'), 'w') as f:
        f.write(f"DONE\nt1_quality={q1}\nt2_quality={q2}\n"
                f"t1_wiki_written={r1['wiki_written']}\n"
                f"t2_patterns_found={r2['wiki_patterns_found']}\n"
                f"wiki_entries={final_stats['section_a_entries']}\n"
                f"targets_met={len(targets_met)}/5\n")

    print(f'\nResults saved to {RDIR}/', flush=True)


if __name__ == '__main__':
    asyncio.run(main())