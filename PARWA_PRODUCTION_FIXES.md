# Parwa Production Fix Kit — 2026-09-27

Ready-to-apply fixes for the Parwa backend repo. Written because the sandbox clone of
`/home/z/parwa` was recycled before edits could be pushed. Each fix below includes the
exact change, the file it targets, and a verification step.

Work through it top-to-bottom. Steps 1–2 are P0 (security), 3–5 are P1, 6–8 are P2/P3.

---

## 0. ROTATE CREDENTIALS (do this before touching code)

Two live Superglue tokens sat hardcoded in `backend/app/core/superglue_client.py` and are
in git history permanently (they also leaked into sandbox probe scripts and patch files,
now purged/redacted):

- `sg_…`   → `SUPERGLUE_AUTH_TOKEN` (full tool-run / tool-delete / job-enqueue access)
- `sgai_…` → `SUPERGLUE_LLM_API_KEY` (LLM API access)

The stack is Bearer-token-only (no session id), so **the token is the only thing standing
between the public internet and tool execution.**

1. Revoke/reissue both tokens on the Superglue side.
2. Set new values ONLY as env vars (Render dashboard): `SUPERGLUE_AUTH_TOKEN`,
   `SUPERGLUE_LLM_API_KEY`.
3. Never paste the new values into any file, chat, or patch.

Verification: old token returns 401 from `/sgapi/v1/tools`; new token works from env only.

---

## 1. superglue_client.py — secrets out of source (P0)

Current pattern (line numbers approximate):

```python
DEFAULT_SUPERGLUE_URL = "https://preview-chat-….space-z.ai/sgapi"
DEFAULT_SUPERGLUE_TOKEN = "sg_…"              # ← DELETE
DEFAULT_SUPERGLUE_CORE_URL = "https://…/sgapi/v1/tools"
DEFAULT_SUPERGLUE_LLM_KEY = "sgai_…"          # ← DELETE
```

Replace with env-only resolution and fail loudly when unconfigured:

```python
def _superglue_token() -> str:
    """Bearer token. REQUIRED — no default, fail closed."""
    token = os.environ.get("SUPERGLUE_AUTH_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "SUPERGLUE_AUTH_TOKEN is not set. Superglue calls are disabled. "
            "Set it in the environment (never in code)."
        )
    return token


def _llm_key() -> str:
    key = os.environ.get("SUPERGLUE_LLM_API_KEY", "").strip()
    if not key:
        raise RuntimeError("SUPERGLUE_LLM_API_KEY is not set (required by the LLM lane).")
    return key
```

Callers that previously did `os.environ.get("SUPERGLUE_AUTH_TOKEN", DEFAULT_SUPERGLUE_TOKEN)`
switch to `os.environ.get("SUPERGLUE_AUTH_TOKEN") or _superglue_token()` — i.e. env only.
Also drop the two older tokens from comments/docstrings; they are dead but still leak
context into history.

Verification: `grep -rn "sg_\|sgai_" backend/` returns zero hits; the service still boots
and a tool call with env set succeeds.

---

## 2. superglue_actions.py — restore auth (P0)

`Depends(lambda: None)` on 2 endpoints = unauthenticated route. Find them:

```bash
grep -n "Depends(lambda: None)" backend/app/api/superglue_actions.py
```

Fix: replace with the same dependency the other protected routers use (the project's
verify-token / tenant-resolution dependency, e.g. `Depends(get_current_tenant)` — match
whichever `backend/app/core/security` or deps helper the rest of the API uses):

```python
# before
@router.post("/run")
async def run_action(..., _auth: None = Depends(lambda: None)):

# after
@router.post("/run")
async def run_action(..., tenant = Depends(get_current_tenant)):
```

Then confirm exposure from OUTSIDE the network (do this first — it tells you if the bug
was live):

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://parwa-backend.onrender.com/<the-2-paths>
# 401/403 = gateway is saving you (still fix the dep)
# 200/422/500 = it was exploitable; fix + write down what happened
```

Add a CI test asserting every route in `app/api/` returns 401 without credentials
(loop over `app.routes`, skip explicit `allow_anonymous=True` markers).

---

## 3. Worker queue-name mismatch (P1, one line)

`backend/worker/main.py` listens on the wrong queues, so the Celery worker consumes
nothing and the in-process/DB-queue fallbacks carry all production load:

```bash
grep -n '"default' backend/worker/main.py backend/app/core/celery_app.py
```

```python
# before
worker.start(queues=["default", "dead_letter"])
# after (must match celery_app task_queues / task_default_queue)
worker.start(queues=["parwa_default", "parwa_dlq"])
```

Also add dispatch idempotency while you're in there: every pipeline dispatch carries a
`run_id` (or hash of tenant+subject+created-hour); the consumer skips if that `run_id` was
already started. This kills the re-dispatch → duplicate pipelines → OOM failure mode
recorded in the worklog.

Verification: `/health` celery check flips from degraded to healthy; enqueue one job and
watch it get consumed by the worker (not the inline fallback).

---

## 4. Embedding dimension mismatch (P1)

Runtime has TWO embedders (Google text-embedding-004 = 768-dim, NVIDIA = 1024-dim) but
migration `033_pgvector` created `vector(768)`. Any NVIDIA insert = guaranteed 500 on the
live RAG path (N3 hybrid retrieval).

Diagnose first:

```sql
SELECT vector_dims(embedding), count(*) FROM document_chunks GROUP BY 1;
```

- If the table is empty or 768-only and the product standardizes on NVIDIA: new migration
  `039_embedding_dim_1024` with
  `ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1024);`
  (empty table = instant; non-empty = truncate + re-embed, vector(768)→vector(1024) casts fail).
- If you must keep both providers: store `embedding_model` + `embedding_dim` per chunk,
  filter to one model per query before cosine, and use an untyped `vector` column.
  Mixed-dim rows in one cosine pass crash regardless of storage.

Also delete/ignore the second embedder path whichever way you choose — one embedder,
one dimension, enforced by a check constraint:

```sql
ALTER TABLE document_chunks
  ADD CONSTRAINT embedding_dim_ok CHECK (vector_dims(embedding) = 1024);
```

Verification: embed + store one chunk with the production embedder; run a hybrid query;
no dimension errors.

---

## 5. Duplicate-ticket 500 (P1)

Reproduced live (Task 14): identical subject+message → HTTP 500. In the ticket-creation
service, catch the unique/integrity error (or pre-check within a short tenant-scoped
window) and return the existing ticket with 200 instead of crashing:

```python
existing = await tickets.find_first(
    tenant_id=tenant.id, subject=subject, created_at >= now - timedelta(minutes=5)
)
if existing:
    return existing  # idempotent create
```

Verification: POST the same ticket twice → second call returns the first ticket's id, 200.

---

## 6. Sentry DSN (P2, 30 min)

`SENTRY_DSN` is not set in production — every 500 and 403 wart above is invisible. Set
`SENTRY_DSN` on Render + initialize the SDK in the FastAPI factory. Re-run the duplicate
ticket curl to confirm the event lands in Sentry.

---

## 7. 403 tenant wart + KB retrieval hit-rate (P2)

- Intermittent `403 "Tenant identification required"` right after re-login (self-heals on
  next login). Pull Render logs around a repro, check whether the JWT sub/tenant claim is
  missing vs. the middleware running before the tenant cache warms.
- Ticket #6 escalated although the KB held the answer: replay it, dump the N3 retrieval
  scores, tune the RRF/top-k/threshold until the KB chunk wins.

---

## 8. Dead code (P3, one PR)

- `backend/main.py` legacy monolith: confirm `Dockerfile` / `render.yaml` entrypoints
  don't reference it, then delete.
- `sse.py` router: unregistered — delete or register.
- Paddle remnants: delete.
- Frontend: `next-auth`, `@tanstack/react-query` (and react-table if unused) are
  installed but never imported — remove (already done in the sandbox package.json as the
  reference diff).

---

## Priority recap

| # | Fix | Effort | Priority |
|---|-----|--------|----------|
| 0 | Rotate both Superglue tokens | 10 min | **P0 — irreversible risk until done** |
| 1 | Keys out of `superglue_client.py` | 30 min | P0 |
| 2 | Restore auth on 2 endpoints + CI 401 test | 30–60 min | P0 |
| 3 | Celery queue names + dispatch dedup | 1 hr | P1 |
| 4 | Embedder pin + pgvector dim migration | half day | P1 |
| 5 | Duplicate-ticket 500 fix | 2 hr | P1 |
| 6 | Sentry | 30 min | P2 |
| 7 | 403 wart + KB hit-rate | open | P2 |
| 8 | Dead-code cleanup | 1 PR | P3 |
