# Space Worker Setup — ticket lanes outside Render

## What this is (plain language)

Your Render free box can only afford **3 ticket lanes** (each lane ≈ 45MB RAM).
The space worker runs the **same ticket-solving code** on a z.ai space box,
connected to the **same database queue**. Both boxes pull from one queue, so
no ticket is ever solved twice (the database hands each ticket to exactly one
worker).

```
Tickets (database queue, status='open')
   ├── Render box:      3 lanes  (unchanged, MAX_CONCURRENT_PIPELINES=3)
   └── z.ai space box:  2 lanes  (SPACE_CONCURRENCY=2, raise anytime)
                            └── each extra lane here costs ~5MB, not Render RAM
```

**Business result:** ~45/hr → ~90–150/hr on the same $0 budget. The
theoretical ceiling stays ~400/hr (that would need every ticket done in
~1 minute AND ~40 LLM calls/minute — your dedicated LLM covers the RPM side;
ticket time is the natural brake). Raise `SPACE_CONCURRENCY` when you need
more lanes — the space box carries the weight, not Render.

## Files added

| File | What it does |
|---|---|
| `backend/run_space_worker.py` | The space-side entrypoint. Reuses Render's exact claim loop. Refuses to boot if DB grants are wrong. |
| `backend/database/sql/variant_agent_user.sql` | Creates the limited `variant_agent` DB user + heartbeat table. **You run this once.** |
| `backend/tests/test_space_worker_awareness.py` | Runnable check for the new Jarvis awareness domain (5 tests). |
| `backend/app/services/jarvis_awareness_engine.py` | **Domain 12 + Rule 13 added**: Jarvis now sees the space worker (live lanes, tickets in progress, and a warning alert if its heartbeat goes silent). |

## Setup steps (one time, ~15 minutes)

### 1. Create the limited DB user
Open the Supabase SQL editor (or psql as master), paste
`backend/database/sql/variant_agent_user.sql`, **change the password** in
line 1, and run it. Then confirm the denylist works — as `variant_agent`:

```sql
DELETE FROM tickets WHERE false;   -- must FAIL: permission denied ✅
SELECT count(*) FROM users;        -- must FAIL: permission denied ✅
```

### 2. Set the space box env vars

| Env var | Value |
|---|---|
| `DATABASE_URL` | `variant_agent` user's connection string (same host as Render's, sslmode added automatically) |
| `SPACE_CONCURRENCY` | `7` = the full 7-lane goal (each lane ~45MB **in the space**, not Render; lower it anytime) |
| `SPACE_WORKER_ID` | optional unique name, e.g. `space-1` |
| LLM keys | same as Render: `GROQ_API_KEY`, `MISTRAL_API_KEY`, `NVIDIA_API_KEY` |

Render itself changes **nothing** — no env changes, no redeploy needed.

### 3. Preflight (safety check, no workers start)

```bash
cd backend
python run_space_worker.py --preflight
```

On the real DB this proves: connected as the limited user, cannot read
`users`/`subscriptions`, cannot delete tickets, worker code imports clean.
It exits 78 (misconfiguration) if ANY grant is wrong — before touching a
single ticket.

### 4. Run it for real

```bash
cd backend
python run_space_worker.py
```

Keep it alive like any space service (process manager / restart policy).
It beats a heartbeat every 30s so Jarvis always knows it's alive.

## What Jarvis now knows (Domain 12)

Jarvis's awareness tick gains:
- `space_worker_count` / `space_worker_capacity` — how many extra lanes are live
- `space_worker_tickets_in_progress` — global in-flight tickets
- `space_worker_status` — `healthy` / `stale` / `absent`
- **Rule 13 alert**: if a space worker that WAS beating goes silent >90s,
  Jarvis raises a warning: *"Space Worker went silent — Render's own lanes
  are still solving tickets."* Never deployed = never alerts (no spam).

## Safety design (why this is safe to run)

1. **Guard on every boot** — superuser probe, `users`/`subscriptions` read
   probes, ticket-DELETE probe. Any unexpected success = loud exit.
2. **No DELETE anywhere** — the DB role cannot delete a single row.
3. **Jarvis stays separate** — the role is revoked on ALL `jarvis_*` tables.
   The ticket worker physically cannot touch Jarvis's queue.
4. **No secrets** — auth/billing/api-key tables are fully revoked. LLM keys
   live in the space box's own env vars, never read from the DB.
5. **Failover is free** — space dies? Render's 3 lanes keep solving. Queue
   is in the database; nothing is lost.

## Honest limitations

- **Chat live-push**: for chat tickets solved on the space box, the reply is
  saved to the database (customer sees it on next load/refresh) but the
  instant socket push only happens on Render. Email/SMS replies send
  normally. Non-blocking, already wrapped as "non-critical" in the code.
- **Complex integration configs** are read-only for this user
  (`rest_connectors`, `mcp_connections`): actions that only read configs
  work; if a node ever needed to MODIFY an integration config from the
  space, it would fail → ticket escalates to human, never lost.
- **`provider_configurations` is fully revoked** — LLM keys must come from
  the space box env vars (step 2). If the pipeline ever fails with a missing
  provider config, this is the first place to look.
- The Postgres-only parts (claim query, heartbeat upsert, guard probes) were
  verified by code review here; run the step-3 preflight on the real DB as
  the final live confirmation.

## Rollback

Stop the space worker process. Render keeps solving tickets with its own 3
lanes exactly as before. Optionally mark the heartbeat row stopped (the
worker does this automatically on SIGTERM). Nothing to revert in Render.
