# Spec: 001 — Request-Ready APIs (1M-Request Readiness + Honest Failure States)

**Status:** Shipped (reconstructed 2026-09-03 — original lost in sandbox reset, rebuilt from worklog)
**Source lesson:** "Let's Handle 1 Million Requests per Second" (cododev) — clustering, LB, Redis in front of PostgreSQL, indexes, load-test everything.
**Constitution:** Articles I–III bind this spec.

## Problem

Live testing on parwa.buzz (30 tickets created through the UI) exposed:

1. `/api/tickets` returned a **fake empty list (200 + `{"items":[]}`)** when the
   backend exceeded its 15s timeout — the dashboard showed "No tickets yet"
   while 31 real tickets sat in PostgreSQL.
2. The ticket-list query was the slowest hot path (15–40s for 31 rows) —
   no composite indexes; every poll hit PostgreSQL directly.
3. The backend worker self-stalled under sustained load (worker recycling
   via `--limit-max-requests 1000`).
4. The Create-Ticket modal closed even when the POST failed — the user's
   text was lost and failure looked like success.
5. Escalations page claimed "The AI is resolving all tickets automatically"
   while tickets sat in `review_needed`.

## User Stories

1. **As a dashboard user**, when the ticket service is slow or down, I see an
   honest error ("Can't reach the ticket service… your tickets are safe")
   with a Retry button — never a fake empty inbox.
2. **As a dashboard user**, when I create a ticket and the backend fails, the
   modal stays open, my text is kept, and I get a clear error toast.
3. **As a dashboard user**, my repeated list views are served fast (cache)
   instead of re-querying PostgreSQL on every poll.
4. **As an operator**, the API tier stays responsive under sustained traffic:
   indexed queries, no self-stalling workers, cache absorbing hot reads.

## Functional Requirements

- FR-1: `/api/tickets` GET: on backend timeout/unreachable → wait 1.5s, retry
  once, then return **502 `BACKEND_UNAVAILABLE`** (never a fabricated list).
- FR-2: `/api/billing/invoices` GET: same honest-502 pattern.
- FR-3: Ticket list cache-aside in backend `GET /api/v1/tickets`: Redis,
  10s TTL, key `parwa:{company_id}:cache:tickets_list:{hash-of-filters}`,
  fail-open (BC-012).
- FR-4: Escalations list cache-aside on `GET /api/escalations/list` (same
  pattern, key suffix `escalations_list`).
- FR-5: Alembic migration 039: composite indexes `tickets(company_id, created_at DESC)`
  and `tickets(company_id, status)`; idempotent (index-exists guard).
- FR-6: Dockerfile CMD: workers via `WEB_CONCURRENCY` env (default 1);
  never re-add `--limit-max-requests`.
- FR-7: Ticket store tracks `lastSyncError`; tickets page shows
  SyncErrorState (no tickets + sync failed) and a stale-data banner with
  Retry (tickets + sync failed).
- FR-8: `addTicket` returns the backend outcome; modal awaits it — closes +
  success toast only on success; keeps text + error toast on failure.
- FR-9: Escalations page copy is truthful (no automatic-resolution claims).

## Verification (Article III)

- py_compile all touched backend files: PASS
- `bunx tsc --noEmit`: 80 errors before = 80 after (0 new, all pre-existing)
- `bunx jest`: failures identical before/after (177F/557P — all pre-existing
  `fetch is not defined` in test env)
- Load test (stub backend, autocannon 30s/100conn): happy path 3,695 req,
  0 errors, 0 timeouts; backend-down path 180/180 honest 502 JSON bodies.
