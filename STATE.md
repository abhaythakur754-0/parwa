# PARWA — Current State

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
