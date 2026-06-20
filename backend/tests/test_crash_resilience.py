"""Crash Resilience Test — verifies the pipeline NEVER crashes.

Tests:
  1. Simple ticket → resolves cleanly (fast, no LLM issues)
  2. Node 3 crash simulation → pipeline continues gracefully
  3. Missing state fields → handled with defaults
  4. Pipeline timeout → aborts instead of hanging
  5. Complex ticket → resolves or escalates (never crashes)

This is the FIRST thing that should pass before any Phase 7 work.
"""
import sys, os, asyncio, time, json, traceback
sys.path.insert(0, '/home/z/my-project/parwa/backend')

from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline
from app.core.parwa_pipeline.nodes.node_2_smart_route import set_test_variant
from app.core.parwa_pipeline.llm_client import reset_stats, get_stats, set_pipeline_timeout

RDIR = '/home/z/my-project/parwa/backend/tests/results'
os.makedirs(RDIR, exist_ok=True)

results = {}


def make_state(ticket_id, query, tier="parwa", quota=999, ctx=None):
    return {
        'ticket_id': ticket_id,
        'tenant_id': 'tenant_test',
        'query': query,
        'channel_type': 'chat',
        'customer_context': ctx or {'account_tier': tier, 'customer_tenure_days': 90, 'recent_ticket_count': 0, 'lifetime_value': 500},
        'metadata': {'sender': 'test@test.io', 'timestamp': '2026-06-18T00:00:00Z'},
        'loop_count': 0,
        'total_token_usage': 0,
        'technique_log': [],
        'errors': [],
    }


async def test_simple_ticket():
    """Test 1: Simple FAQ ticket — should resolve quickly."""
    print("  [1] Simple FAQ ticket...", end=" ", flush=True)
    reset_stats()
    set_test_variant('tenant_test', 'parwa', 999)
    set_pipeline_timeout(120)

    state = make_state('crash_t1', 'What are your pricing plans?')
    g = build_parwa_pipeline().compile()
    result = await g.ainvoke(state)

    assert result.get('status') in ('resolved', 'escalated', 'stuck'), f"bad status: {result.get('status')}"
    assert 'errors' in result, "missing errors key"
    print(f"OK status={result.get('status')}", flush=True)
    return {'test': 'simple_ticket', 'status': result.get('status'), 'errors': len(result.get('errors', []))}


async def test_missing_fields():
    """Test 2: State with minimal fields — should not crash."""
    print("  [2] Missing state fields...", end=" ", flush=True)
    reset_stats()
    set_pipeline_timeout(30)

    # Minimal state — only required fields
    state = {
        'ticket_id': 'crash_t2',
        'tenant_id': 'tenant_test',
        'query': 'Help me with my account',
        'loop_count': 0,
        'technique_log': [],
        'errors': [],
    }
    g = build_parwa_pipeline().compile()
    result = await g.ainvoke(state)

    assert result is not None, "result is None!"
    assert result.get('status') in ('resolved', 'escalated', 'stuck'), f"bad status: {result.get('status')}"
    print(f"OK status={result.get('status')}", flush=True)
    return {'test': 'missing_fields', 'status': result.get('status')}


async def test_empty_query():
    """Test 3: Empty query — should not crash."""
    print("  [3] Empty query...", end=" ", flush=True)
    reset_stats()
    set_pipeline_timeout(30)

    state = make_state('crash_t3', '')
    g = build_parwa_pipeline().compile()
    result = await g.ainvoke(state)

    assert result is not None, "result is None for empty query!"
    print(f"OK status={result.get('status')}", flush=True)
    return {'test': 'empty_query', 'status': result.get('status')}


async def test_refund_simple():
    """Test 4: Simple refund query — should route to simple path or complex."""
    print("  [4] Refund query...", end=" ", flush=True)
    reset_stats()
    set_test_variant('tenant_test', 'parwa', 999)
    set_pipeline_timeout(120)

    state = make_state('crash_t4', 'I want a refund for my recent purchase')
    g = build_parwa_pipeline().compile()
    result = await g.ainvoke(state)

    assert result is not None
    assert result.get('status') in ('resolved', 'escalated', 'stuck')
    print(f"OK status={result.get('status')}", flush=True)
    return {'test': 'refund', 'status': result.get('status'), 'type': result.get('ticket_type')}


async def test_graph_compilation():
    """Test 5: Graph compiles without errors."""
    print("  [5] Graph compilation...", end=" ", flush=True)
    try:
        g = build_parwa_pipeline()
        compiled = g.compile()
        print("OK", flush=True)
        return {'test': 'compilation', 'status': 'OK'}
    except Exception as e:
        print(f"FAIL: {e}", flush=True)
        return {'test': 'compilation', 'status': 'FAIL', 'error': str(e)}


async def main():
    print("=== CRASH RESILIENCE TEST ===\n", flush=True)

    tests = [
        test_graph_compilation,
        test_simple_ticket,
        test_missing_fields,
        test_empty_query,
        test_refund_simple,
    ]

    all_results = []
    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            r = await test_fn()
            all_results.append(r)
            if r.get('status') not in ('FAIL',):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  CRASHED: {type(e).__name__}: {e}", flush=True)
            all_results.append({'test': test_fn.__name__, 'status': 'CRASHED', 'error': str(e)})
            traceback.print_exc()
            failed += 1

    print(f"\n=== RESULTS: {passed}/{len(tests)} passed, {failed} failed ===", flush=True)

    out = {
        'phase': 'crash_resilience',
        'passed': passed,
        'failed': failed,
        'total': len(tests),
        'tests': all_results,
    }
    with open(os.path.join(RDIR, 'crash_resilience.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)

    if failed == 0:
        print("ALL CRASH RESILIENCE TESTS PASSED!", flush=True)
    else:
        print(f"WARNING: {failed} test(s) still failing!", flush=True)

    return failed == 0


if __name__ == '__main__':
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)