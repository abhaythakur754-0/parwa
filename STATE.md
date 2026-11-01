# PARWA — Current State

**Last verified:** 2026-10-29 (Tool Factory + Self-Extension task 36)

## Superglue tool layer (NEW — task 36, live-verified)
- GENERIC tool factory: `scripts/tool_factory.py` (any spec → any tenant)
- Payments preset (8 Razorpay tools, creds-as-inputs) deployed for
  `acme-payments-demo`; credential-free matrix 9/9 PASS
- SELF-EXTENSION proven: `gadgethub-demo` got `warranty-status-check`
  designed by Mistral (Superglue LLM lane) + created + verified with real data
- One-command proof: `python3 scripts/production_e2e_test.py` → ALL PASS
- ONLY remaining gap: real Razorpay keys (creds are tool INPUTS — no redeploy)
- Key Superglue behavior: failed steps are invisible to transforms/outputTransform;
  failure diagnostics live in run response `stepResults[]` only


**Last verified:** 2026-09-03 16:00 UTC

## Git
- Branch: `production-readiness-fixes`
- Latest commit: `276b030c` — fix: migrate to Supabase PostgreSQL, remove hardcoded credentials, production-ready render.yaml
- Working tree (uncommitted): reliability + security fixes from tasks 20-a…20-d
  (JWT revocation fail-closed, Celery queue starvation, overage retry, alembic
  autogenerate coverage, MCP Dockerfile/BACKEND_URL, escalation + pipeline +
  technique hardening, socket client auth). Nothing committed yet.

## Database (Supabase — source of truth)
- PostgreSQL via Supabase; 156 tables (matches 38 model modules under
  `backend/database/models/`, all now imported by `alembic/env.py`)
- RLS enabled on all 156 public tables (verified 2026-06-24)
- **BLOCKER for deploy: Supabase credentials expired** (see repo worklog).
  Rotate SUPABASE_URL / service keys before any deployment.

## Billing
- **Paddle FULLY removed** — 0 active Paddle imports/SDK usage in the codebase.
  Razorpay is the ONLY billing provider.
  - Legacy `paddle_*` DB columns/tables are kept for compat and now store Razorpay IDs
  - `PaddleOperationError` survives only as a never-raised compat shim
  - Overage charges are DB-managed: recorded → next Razorpay invoice cycle;
    retry path is DB-only (no provider auto-charge), retries exhausted → "dead" + error log

## Redis + Celery (in use)
- Broker/backend on Redis; 33 task modules; beat schedule active
- 8 queues: `parwa_default, ai_heavy, ai_light, email, webhook, analytics, training, parwa_dlq`
  (x-dead-letter-exchange → `parwa_dlq`, acks_late + reject_on_worker_lost)
- Worker entry (`backend/worker/main.py`) and `backend/Dockerfile.celery` now consume
  ALL 8 queues (was `default,dead_letter` → silent starvation)
- Residual risk: ~51 task decorators in `app/tasks/` still declare `queue="default"`
  (and a few `queue="billing"`) — names not in `QUEUE_NAMES`; needs an audit

## Auth / Security
- `is_token_revoked()` (jwt_auth.py) now fails CLOSED in production on Redis
  errors, softened by a 60s in-process last-known-good jti cache; dev/test
  still fails open. Deny path = same 401 flow as blacklist hit.

## Rust parwa_core
- Source exists (`backend/parwa_core/`, maturin/pyo3) but NOT compiled —
  no .so in repo. Pure-Python fallbacks in `parwa_core_bridge.py` are active
  (functional but slower). `backend/Dockerfile.celery` builds it for the
  worker image; backend image skips by default (`SKIP_RUST_BUILD=true`).
  Run `maturin develop --release` before performance-sensitive deploys.

## Infra
- `infra/docker/mcp.Dockerfile` fixed: builds from repo root against
  `backend/requirements.txt`, python 3.12 (matches backend), copies
  `mcp_server/` + `backend/` (MCP delegates to backend modules)
- MCP `BACKEND_URL` default corrected to `http://localhost:8000`
  (matches .env.example) across all 15 mcp_server files
- AI Wiki is DB-backed (`ai_wiki_entries` model; in-memory fallback remains)

## Known Limitations
- Supabase creds expired (BLOCKER above)
- Top-level `tests/` suites (192 unit + 12 integration + infra/production/e2e)
  are NOT wired into `.github/workflows/ci.yml` — only backend tests run in CI
- Rust parwa_core uncompiled (fallbacks active)
- Task-decorator queue names audit pending (see Redis + Celery above)

## Deployment status (2026-10-29)
- Security hardening (RLS + view security_invoker) ships as migration 042 and
  self-applies on every deploy via lifespan `alembic upgrade head`.
- Commit identity fixed for Vercel deployment (was sandbox placeholder).
- Remaining owner action: Supabase project active + DATABASE_URL set on the
  hosting platform (Render/Vercel) for the backend to boot and self-heal.

## Ticket-driven lifecycle (proven live, task 40)
- New ticket → missing capability → self-extension builds tool → DB stores
  tool inventory + agent ownership + origin ticket → later tickets reuse
  from DB. Demo: scripts/ticket_to_tool_demo.py → ALL PASS on live Superglue.
- Gotchas: sqlite URL must be absolute (4 slashes) or best-effort registry
  silently skips; Superglue list endpoint 404s → use tool_exists(id).

## Novel-capability hardening (task 41)
- Production-ready proven on 4 NEVER-seen capabilities: 4/4 tools live,
  verified, registered; write→approval gate; reuse path OK.
- New: universal fallback template (any capability), risk param on
  extend_toolset, repair shape guard. Unknown capability no longer
  dead-ends or borrows wrong-domain templates.

## Daily Learning Loop (task 45, 2026-10-30)
- Memory: db/learning.db (committed) + scripts/learning_loop.py (stdlib,
  zero deps). Commands: briefing / add-lesson / add-gap / decide /
  log-day / start-done-drop-gap / export / selfcheck.
- Ritual: ONE long session daily — briefing -> build -> write-back
  (log-day never skipped) -> commit. Receipts make "improve day by day"
  provable, not a slogan.
- Seeded with real history: 7 rules, 8 open gaps (P1 = Supabase creds
  rotation), 3 decisions.
- Selfcheck 17/17 PASS; edge battery PASS.

## HumanReplacement loop (task 46, 2026-11-01) — CLOSED END-TO-END
- The ticket flow is now: AI gives up → mistake noted in AI wiki
  (unsolved, with the escalation ask) → request pushed to the tenant's
  CRM → CRM human solves it there → resolution webhook applies via
  CRMResolutionService → wiki note upgraded (solved_after_failure) →
  next identical ticket solved by AI from memory.
- Notifications follow "one escalation, one ring": tenant CRM connected
  → CRM tells its humans (PARWA agent email skipped). No CRM → PARWA
  email+in-app stays (only channel). awaiting_client nudges go through
  the CRM thread; email only as fallback.
- Self-check: backend/tests/test_humanreplacement_loop.py (stdlib
  assert, runs anywhere) — 5/5 PASS.
- Gap #10 closed; lesson #9 (snapshot before upsert); day #4 logged.
- NEXT: live test with a real CRM sandbox ticket (webhook → wiki upgrade
  → AI resolves the repeat from memory).
