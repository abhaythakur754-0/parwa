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