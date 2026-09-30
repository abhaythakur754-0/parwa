# Plan: 001 — Request-Ready APIs

**Constitution:** .specify/memory/constitution.md (Articles I–III bind)

## Video lesson → PARWA mapping

Source: cododev, "Let's Handle 1 Million Requests per Second".

| Lesson from the video | PARWA application |
|---|---|
| Put Redis in front of the DB for hot reads | FR-3/FR-4 cache-aside, 10s TTL, tenant-keyed, fail-open |
| Indexes on the real query shapes | FR-5 composite indexes (tenant + time, tenant + status) |
| Don't let workers die mid-flight / recycle under load | FR-6 remove --limit-max-requests, WEB_CONCURRENCY dial |
| Load-test the happy AND the degraded path | Article III verification (3,695 req happy / 180×502 degraded) |
| One box is a ceiling, not a design flaw | Documented dials: WEB_CONCURRENCY, Render plan upgrade |
| Honest observability beats optimistic UI | Article I + FR-1/2/7/8/9 honest failure states |

## Architecture decisions

- Cache lives in the **backend** (FastAPI), not the Next.js proxy: the proxy
  stays a thin auth/forwarding shim; every backend consumer benefits.
- TTL 10s: dashboard polls tolerate 10s staleness; no invalidation protocol
  needed (ponytail rung 1: the invalidation machinery does not need to exist).
- Keys reuse existing `make_key` + `safe_get`/`safe_set` tenant validation
  (rung 2: reuse, don't rewrite) — zero new auth surface.
- Migration is idempotent because Render runs migrations on every deploy
  (re-run must not crash the service).

## Deliberately out of scope

- Horizontal clustering of the backend (single Render box is the current
  ceiling — CEO decision on plan upgrade, not a code task).
- Rate limiting changes (already shipped in ed0aef39).
- Celery queue-name audit (flagged in Task 20-e, separate spec).
