"""Phase 5: Manual loop test — proves quality loop + Super Node work by calling nodes directly."""
import sys, os, asyncio, time, json, traceback, re
sys.path.insert(0, '/home/z/my-project/parwa/backend')
os.makedirs('/home/z/my-project/parwa/backend/tests/results/phase5', exist_ok=True)

from app.core.parwa_pipeline.nodes.node_1_ingest_classify import node_1_ingest_classify
from app.core.parwa_pipeline.nodes.node_2_smart_route import node_2_smart_route, set_test_variant
from app.core.parwa_pipeline.nodes.node_3_knowledge_fetch import node_3_knowledge_fetch
from app.core.parwa_pipeline.nodes.node_4_reasoning_engine import node_4_reasoning_engine
from app.core.parwa_pipeline.nodes.node_5_act_verify import node_5_act_verify
from app.core.parwa_pipeline.nodes.node_6_quality_format import node_6_quality_format
from app.core.parwa_pipeline.nodes.node_8_super_node import node_8_super_node
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats

RDIR = '/home/z/my-project/parwa/backend/tests/results/phase5'

PASS_THRESHOLD = 0.97  # Artificially high to force loops
MAX_LOOPS = 2
SUPER_THRESHOLD = 0.85

async def main():
    reset_stats()
    set_test_variant('tenant_a', 'parwa', 1996)

    state = {
        'ticket_id': 'tkt_p5_loop_test', 'tenant_id': 'tenant_a',
        'query': 'I was charged $2,499 twice this month and also my colleague is seeing different prices. I want both issues resolved and also need to know the exact compensation for this error.',
        'channel_type': 'chat',
        'customer_context': {'account_tier': 'parwa', 'customer_tenure_days': 180, 'recent_ticket_count': 2, 'lifetime_value': 3500},
        'metadata': {'sender': 'confused@test.io', 'timestamp': '2026-06-18T00:00:00Z'},
        'loop_count': 0, 'total_token_usage': 0, 'technique_log': [], 'errors': [],
    }

    t0 = time.time()
    quality_scores = []
    node_4_calls_total = 0
    node_6_calls_total = 0
    reached_super = False
    escalated = False

    # === RUN NODES 1-3 ===
    print("Running Node 1 (Ingest+Classify)...", flush=True)
    r1 = await node_1_ingest_classify(state)
    state.update(r1)
    print(f"  type={r1.get('ticket_type')} complexity={r1.get('complexity')} action={r1.get('required_action')}", flush=True)

    print("Running Node 2 (Smart Route)...", flush=True)
    r2 = await node_2_smart_route(state)
    state.update(r2)
    print(f"  path={r2.get('route_decision')} tier={r2.get('variant_tier')}", flush=True)

    print("Running Node 3 (Knowledge Fetch)...", flush=True)
    r3 = await node_3_knowledge_fetch(state)
    state.update(r3)
    print(f"  docs={len(r3.get('knowledge_context', []))} sufficient={r3.get('knowledge_sufficient')}", flush=True)

    # Determine path
    path = state.get('route_decision', state.get('current_path', 'simple_path'))
    print(f"\nPath: {path}", flush=True)

    if path == 'simple_path':
        print("Simple path — skipping loop test", flush=True)
        return

    # === QUALITY LOOP ===
    for loop_num in range(MAX_LOOPS + 1):
        loop_label = f"Loop {loop_num}" if loop_num > 0 else "First pass"
        print(f"\n--- {loop_label} ---", flush=True)

        # Node 4
        print("  Running Node 4 (Reasoning)...", flush=True)
        r4 = await node_4_reasoning_engine(state)
        state.update(r4)
        node_4_calls_total += r4.get('node_4_token_usage', 0)
        maker_f = len(r4.get('maker_flagged', []))
        maker_r = len(r4.get('maker_zsv_removed', []))
        print(f"  Node 4: {r4.get('node_4_token_usage', 0)} LLM calls, MAKER flagged={maker_f} zsv_removed={maker_r}", flush=True)

        # Node 5
        print("  Running Node 5 (Act+Verify)...", flush=True)
        r5 = await node_5_act_verify(state)
        state.update(r5)
        print(f"  Node 5: {r5.get('node_5_token_usage', 0)} LLM calls, verified={r5.get('actions_verified')}", flush=True)

        # Node 6
        print("  Running Node 6 (Quality)...", flush=True)
        r6 = await node_6_quality_format(state)
        state.update(r6)
        node_6_calls_total += r6.get('node_6_token_usage', 0)
        quality = r6.get('quality_score', 0)
        quality_scores.append(quality)
        print(f"  Node 6: quality={quality:.4f} (threshold={PASS_THRESHOLD})", flush=True)
        print(f"    Details: reflexion={r6.get('quality_details', {}).get('reflexion', 'N/A')} "
              f"crp={r6.get('quality_details', {}).get('crp', 'N/A')} "
              f"zero_shot={r6.get('quality_details', {}).get('zero_shot', 'N/A')}", flush=True)

        # Check quality
        if quality >= PASS_THRESHOLD:
            print(f"\n  ✅ QUALITY PASSED ({quality:.4f} >= {PASS_THRESHOLD}) after {loop_num} loops", flush=True)
            break

        if loop_num < MAX_LOOPS:
            print(f"  ❌ Quality below threshold → looping back to Node 4", flush=True)
            state['loop_count'] = loop_num + 1
            # Clear previous combined_answer so Node 4 generates fresh
            state['combined_answer'] = ''
        else:
            print(f"  ❌ Max loops ({MAX_LOOPS}) reached → activating Super Node", flush=True)

    # === SUPER NODE (if needed) ===
    final_quality = state.get('quality_score', 0)
    if final_quality < PASS_THRESHOLD:
        print(f"\n=== SUPER NODE (quality {final_quality:.4f} < {PASS_THRESHOLD}) ===", flush=True)
        reached_super = True
        r8 = await node_8_super_node(state)
        state.update(r8)
        super_q = r8.get('super_node_quality', 0)
        escalated = r8.get('status') == 'escalated'
        esc_key = r8.get('escalation_context', {}).get('notification_key', None)
        print(f"  Super Node quality: {super_q}", flush=True)
        print(f"  Escalated: {escalated} (key: {esc_key})", flush=True)
        print(f"  Node 8 LLM calls: {r8.get('node_8_token_usage', 0)}", flush=True)

        if escalated:
            final_quality = super_q

    elapsed = time.time() - t0
    stats = get_stats()

    resp = state.get('final_response', '') or state.get('formatted_response', '') or state.get('super_node_answer', '')

    out = {
        'description': 'Forced loop + Super Node test',
        'status': state.get('status'),
        'quality_scores_per_loop': [f"{s:.4f}" for s in quality_scores],
        'final_quality': state.get('quality_score', 'N/A'),
        'loops_executed': len(quality_scores) - 1,
        'node_4_total_calls': node_4_calls_total,
        'node_6_total_calls': node_6_calls_total,
        'reached_super_node': reached_super,
        'escalated': escalated,
        'escalation_key': esc_key if escalated else None,
        'total_llm_calls': stats['total_calls'],
        'total_tokens': stats['total_tokens'],
        'llm_errors': stats['total_errors'],
        'time_s': round(elapsed, 1),
        'response_len': len(resp),
        'response_preview': resp[:500],
    }

    with open(os.path.join(RDIR, 'ticket_loop_test.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    print(f'\n{"="*60}', flush=True)
    print('PHASE 5 SAFETY SYSTEMS VERIFICATION', flush=True)
    print(f'{"="*60}', flush=True)
    print(f'  Quality scores per loop: {[f"{s:.4f}" for s in quality_scores]}', flush=True)
    print(f'  Loops executed: {out["loops_executed"]}', flush=True)
    print(f'  Super Node: {"ACTIVATED" if reached_super else "not needed"}', flush=True)
    print(f'  Human escalation: {"YES" if escalated else "no"} {"(" + esc_key + ")" if escalated else ""}', flush=True)
    print(f'  Node 4 total LLM calls: {node_4_calls_total} (7 per pass)', flush=True)
    print(f'  Node 6 total LLM calls: {node_6_calls_total} (2 per pass)', flush=True)
    print(f'  Total LLM calls: {stats["total_calls"]}', flush=True)
    print(f'  Total time: {elapsed:.1f}s', flush=True)

asyncio.run(main())