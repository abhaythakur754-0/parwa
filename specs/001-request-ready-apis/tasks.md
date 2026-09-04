# Tasks: 001 — Request-Ready APIs

**Status: all 15 shipped** (reconstructed from worklog Task 23/24; checklist
kept as the record of what "done" means for this spec).

## Backend

- [x] 1. `safe_set(key, value, ttl_seconds)` in app/core/redis.py — tenant-validated, fail-open, mirrors safe_get
- [x] 2. Cache-aside on GET /api/v1/tickets (10s TTL, filter-hash key)
- [x] 3. Cache-aside on GET /api/escalations/list
- [x] 4. Migration 039: tickets(company_id, created_at DESC) + (company_id, status), idempotent guard
- [x] 5. Dockerfile: --workers ${WEB_CONCURRENCY:-1}; document never re-adding --limit-max-requests

## Next.js proxy layer

- [x] 6. /api/tickets: 1.5s wait → single retry → honest 502 BACKEND_UNAVAILABLE
- [x] 7. /api/billing/invoices: honest 502 (fake empty list removed)

## Frontend

- [x] 8. ticket-store: lastSyncError flag; set on 5xx/network error, cleared on success
- [x] 9. ticket-store: addTicket async → Promise<Ticket | null>
- [x] 10. tickets page: SyncErrorState with Retry (empty + sync failed)
- [x] 11. tickets page: stale-data banner with Retry (data + sync failed)
- [x] 12. CreateTicketModal: await outcome; close+toast on success; keep text+error toast on failure
- [x] 13. escalations page: truthful copy (no false "AI is resolving everything")

## Process

- [x] 14. spec-kit initialized (.specify/ + constitution)
- [x] 15. Verification per Article III (py_compile, tsc delta 0, jest delta 0, load tests)
