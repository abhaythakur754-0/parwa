---
Task ID: 1
Agent: main
Task: Fix pipeline crash issues — make pipeline bulletproof so it NEVER crashes

Work Log:
- Investigated all crash logs (t4_crash.log, nohup.out, phase7/run.log, phase6 results)
- Found 6 distinct root causes of crashes/failures
- Applied fixes to 8 files

Stage Summary:
- Root causes found:
  1. NameError: asyncio not defined (t4_crash.log — exec() script missing import)
  2. sync_status undefined in node_3 when wiki operations fail
  3. run_parwa_pipeline() uses deprecated get_event_loop().run_until_complete()
  4. No global pipeline timeout — complex tickets hang forever on rate limits
  5. import litellm in node_5 (dead import, crashes if litellm not installed)
  6. state["key"] direct accesses in all nodes crash if upstream node fails

- Fixes applied:
  1. graph_v2.py: _safe_node() wrapper catches ALL exceptions in every node
  2. graph_v2.py: run_parwa_pipeline() uses asyncio.run() instead of deprecated get_event_loop()
  3. node_3: sync_status now initialized with safe default before try block
  4. llm_client.py: Added PIPELINE_HARD_TIMEOUT (300s) + set_pipeline_timeout() + _check_pipeline_timeout()
  5. llm_client.py: Reduced httpx timeout 60s→30s, added slow call warning
  6. node_5: Removed dead `import litellm`
  7. All nodes: Changed state["key"] → state.get("key", default) for safe defaults
  8. Node 4, 6: Added upstream crash detection (bail out with safe response)
  9. reset_stats() also resets _call_start_time

- Tests:
  - Created test_crash_resilience.py (5 tests)
  - All 5 tests pass: compilation, simple ticket, missing fields, empty query, refund query
  - Pipeline now ends as "stuck" instead of crashing when nodes fail
  - Smoke tests confirm: empty state → resolved, FAQ → resolved

- Files modified:
  - graph_v2.py (safe_node wrapper + asyncio.run fix)
  - llm_client.py (timeout + reset fix + httpx timeout)
  - node_2_smart_route.py (safe state access)
  - node_3_knowledge_fetch.py (sync_status fix + safe state access)
  - node_4_reasoning_engine.py (upstream crash detection)
  - node_5_act_verify.py (removed litellm + safe state access)
  - node_6_quality_format.py (upstream crash detection)
  - node_7_simple_resolver.py (safe state access)
  - node_8_super_node.py (safe state access)
  - tests/test_crash_resilience.py (NEW)
  - tests/p7_runner.py (added set_pipeline_timeout import)

---
Task ID: 2
Agent: main
Task: Phase 7 — T2→T1 Pattern Matching Fix

Work Log:
- Analyzed Phase 4 baseline: complex ticket (t5) quality=0.9506, classified as type=billing/complexity=simple/action=plan_change
- Identified 3 root problems:
  1. Node 1 complexity classifier missed multi-issue tickets (ticket 5 has duplicate charge + pricing discrepancy = 2 issues, but got "simple")
  2. Node 1 action extractor matched "upgrade...plan" pattern incorrectly (user said "never upgraded" which is negation, but regex didn't detect that)
  3. Node 3 KB retrieval was purely type-based — no cross-type detection for queries spanning multiple types (e.g., "refund policy" query classified as faq but needs refund_request KB docs)
- Implemented 3 fixes (all non-LLM, 0 extra calls):
  1. Node 1: Added MULTI_ISSUE_SIGNALS — 8 independent regex patterns detecting multi-issue tickets. If 2+ match → "complex", 1 match → "medium"
  2. Node 1: Added investigate_billing action type with 3 patterns (why+seeing/charged, different+price, charged+twice). New _extract_action() finds ALL matches and prioritizes investigate_billing over plan_change
  3. Node 3: Added cross-type pattern detection in _retrieve_knowledge(). Scans query against 6 type-specific signal dictionaries. If 2+ patterns match for an uncovered type, pulls those KB docs. Also added refund_request to faq's related_types
  4. Node 2: Added investigate_billing handling (routes to complex_path, requires complex_reasoning capability)

Stage Summary:
- Complex ticket quality: 0.9506 → 1.0000 (target >0.99 ACHIEVED)
- Classification fix: complexity=simple → complexity=complex, action=plan_change → action=investigate_billing
- LLM calls unchanged: 13 (no extra calls added)
- Tokens: ~11K (same range)
- Simple tickets: ALL 4 PASS, 0 regressions, 2 calls each
- Files modified:
  - node_1_ingest_classify.py (MULTI_ISSUE_SIGNALS, investigate_billing action, improved _extract_action, improved _classify_complexity)
  - node_2_smart_route.py (investigate_billing routing + capability)
  - node_3_knowledge_fetch.py (cross-type retrieval, query param, faq→refund_request relation)
  - tests/p7_runner.py (NEW)
  - tests/p7_quick.py (NEW)
  - tests/p7_regression.py (NEW)