---
Task ID: W1
Agent: main
Task: Jarvis Wave 1 — Foundation (DB, Auth, Command Parser, Wired E2E)

Work Log:
- Created SQL schema: 13 Jarvis tables with RLS, indexes, immutable audit trigger, auto-expiry function (schemas/jarvis_wave1_schema.sql)
- Built jarvis_db.py: Dual-mode storage backend (InMemory for dev + Supabase REST via httpx for production). Zero new dependencies.
- Built command_parser.py: 2-tier intent classification — Tier 1 regex (0 tokens, 20 patterns, ~80% coverage) + Tier 2 LLM fallback (~200 tokens). 24 intent families.
- Built jarvis_auth.py: Role-based authorization (owner > supervisor > admin > team_member > viewer). Every auth decision logged to audit trail.
- Migrated notification_center.py: Same public API, now async, backed by jarvis_db. No more in-memory dicts.
- Rewrote jarvis_3_notify.py: Full command execution engine — 10 query handlers, 6 control handlers, 3 emergency handlers, 2 explain handlers. All read/write DB.
- Updated graph.py: Added run_jarvis_chat() convenience function with user_context wiring.
- Updated state.py: Added user_context, intent_result, auth_result fields to JarvisState.
- Wrote wave1_e2e_test.py: 71 tests covering parser, auth, DB, and full pipeline.
- Fixed 11 test failures iteratively (regex edge cases, LangGraph state key filtering, audit chain direction).

Stage Summary:
- 71/71 tests passing
- Full chain proven: chat → command_parser → jarvis_auth → jarvis_db → response → audit_trail
- 20 natural language commands classified correctly via regex (0 tokens)
- System flags persist in DB, can be set/revoked/queried
- Notifications persist in DB, can be created/resolved/queried
- Quality scores persist with aggregation
- Audit trail is immutable with hash chain integrity
- Role-based auth: viewer denied, admin allowed, owner can shutdown
- Zero new dependencies (uses only httpx, already installed)
- Supabase-ready: set SUPABASE_URL + SUPABASE_ANON_KEY in .env to auto-switch

Files created:
- parwa/backend/schemas/jarvis_wave1_schema.sql (13 tables, 280 lines)
- parwa/backend/app/core/jarvis_pipeline/jarvis_db.py (dual-mode backend, 500+ lines)
- parwa/backend/app/core/jarvis_pipeline/command_parser.py (2-tier parser, 370 lines)
- parwa/backend/app/core/jarvis_pipeline/jarvis_auth.py (RBAC + audit, 150 lines)
- parwa/backend/tests/wave1_e2e_test.py (71 tests, 310 lines)

Files modified:
- parwa/backend/app/core/jarvis_pipeline/notification_center.py (migrated to jarvis_db)
- parwa/backend/app/core/jarvis_pipeline/nodes/jarvis_3_notify.py (full rewrite with command execution)
- parwa/backend/app/core/jarvis_pipeline/graph.py (added run_jarvis_chat)
- parwa/backend/app/core/jarvis_pipeline/state.py (added 3 fields)