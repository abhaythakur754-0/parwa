# PARWA — Ops Runbook: `crm_permanent_failure_push_failed` DLQ

> **Worst-case scenario**: AI exhausted all guidance retries (`GUIDANCE_MAX_RETRIES`, default 3) **AND** PARWA could not tell the CRM to reset the ticket. The vault is in `REPROCESS_EXHAUSTED` (terminal) state. The CRM ticket is still in `pending_human` / "escalated" state and human agents have no idea AI gave up.
>
> **You (ops) MUST manually reset the CRM ticket** — until you do, the customer's request is invisible to the human support team.

---

## 1. What just happened (technical context)

When PARWA's guidance flow fails the quality check `GUIDANCE_MAX_RETRIES` times in a row, the system performs two things in sequence:

1. **Local state change** (always succeeds): vault ticket → `REPROCESS_EXHAUSTED` (terminal). `batch_guidance_tickets` will never re-queue it. See `backend/app/core/escalation_vault/guidance_ticket_flow.py` Step 9/10.
2. **CRM notification** (may fail): `CRMBridge.push_permanent_failure(provider, ticket_id, attempts, failure_context)` is called. This invokes the adapter method `push_permanent_failure_to_crm()` on Zendesk / HubSpot / Generic which:
   - **Zendesk**: `PUT /api/v2/tickets/{id}.json` with `status=open`, `tags=["ai-cannot-resolve","needs-human","parwa"]`, plus an internal note.
   - **HubSpot**: `PATCH /crm/v3/objects/tickets/{id}` with `hs_pipeline_stage=1` (New), `hs_ticket_category=PARWA_AI_CANNOT_RESOLVE`, plus a note engagement.
   - **Generic**: webhook event `parwa.cannot_resolve` with `action=reset_to_new`.

The CRM notification uses retry + exponential backoff (`CRM_PUSH_MAX_RETRIES`, `CRM_PUSH_BACKOFF_BASE_SECONDS`, `CRM_PUSH_BACKOFF_MAX_SECONDS`). If **all retries fail** (network down, CRM API 5xx, auth expired, etc.), the failure is persisted to the `graph_execution_dlq` table with `error_type=crm_permanent_failure_push_failed`.

This runbook covers that fallback path.

---

## 2. How to detect it

### 2.1 Dashboard tile (primary)

Open the PARWA dashboard → **CRM DLQ** tile on the main `/dashboard` page (BC-018). The tile shows the count of unresolved DLQ entries across the 3 BC-017 CRM error_types:

- `crm_escalation_push_failed` (Node 8 escalation push failed — recoverable)
- `crm_resume_push_failed` (guidance flow resume push failed — recoverable)
- `crm_permanent_failure_push_failed` (this runbook — MANUAL ACTION REQUIRED)

A **red count > 0** on the `Permanent Failure` sub-tile means at least one ticket is in the worst-case state. Click the tile to open `/dashboard/crm-dlq` filtered to that error_type.

### 2.2 API query (for monitoring/alerting)

```bash
# Tenant-scoped (use the user's own token)
curl -X GET 'https://parwa-backend.onrender.com/api/dlq/entries?error_type=crm_permanent_failure_push_failed&resolved=false&limit=50' \
  -H 'Authorization: Bearer <PARWA_AT>'

# Cross-tenant (platform admin only)
curl -X GET 'https://parwa-backend.onrender.com/api/dlq/entries?error_type=crm_permanent_failure_push_failed&resolved=false&company_id=__all__&limit=200' \
  -H 'Authorization: Bearer <PARWA_ADMIN_AT>'
```

### 2.3 SQL query (last resort, direct DB)

```sql
SELECT
  id,
  company_id,
  conversation_id,
  error,
  state_snapshot->>'crm_provider'      AS crm_provider,
  state_snapshot->>'crm_ticket_id'     AS crm_ticket_id,
  state_snapshot->>'escalation_id'     AS escalation_id,
  state_snapshot->>'reprocess_attempts' AS attempts,
  created_at
FROM graph_execution_dlq
WHERE error_type = 'crm_permanent_failure_push_failed'
  AND resolved_at IS NULL
ORDER BY created_at DESC;
```

### 2.4 Metrics / alerting

The Prometheus counter `parwa_crm_permanent_failure_total{provider=...}` increments on every `push_permanent_failure_to_crm()` call (whether or not the push ultimately succeeded). A separate counter `parwa_crm_push_dlq_total{provider=..., error_type="crm_permanent_failure_push_failed"}` increments only when the entry lands in the DLQ.

Recommended alert rule (Prometheus):

```yaml
- alert: ParwaCrmPermanentFailureDLQ
  expr: increase(parwa_crm_push_dlq_total{error_type="crm_permanent_failure_push_failed"}[1h]) > 0
  for: 0m
  labels:
    severity: critical
    team: parwa-ops
  annotations:
    summary: "PARWA has {{ $value }} CRM permanent-failure DLQ entries from the last hour"
    description: "AI gave up on a ticket AND we couldn't tell the CRM. Ops must manually reset the CRM ticket. See documents/ops_runbooks/crm_permanent_failure_push_failed_runbook.md"
```

---

## 3. What information you need from the DLQ entry

Each `crm_permanent_failure_push_failed` DLQ entry has a `state_snapshot` JSON column with these fields (set by `_persist_crm_permanent_failure_to_dlq()` in `guidance_ticket_flow.py`):

| Field | Purpose |
|---|---|
| `escalation_id` | Vault ticket ID — cross-reference with `/api/escalation/list` |
| `crm_provider` | One of: `zendesk`, `hubspot`, `generic` |
| `crm_ticket_id` | The external CRM ticket ID to reset |
| `reprocess_attempts` | How many guidance cycles ran (should equal `GUIDANCE_MAX_RETRIES`) |
| `failure_context` | Why AI gave up (low quality, KB miss, etc.) |
| `response_text_preview` | First 500 chars of the last AI response — for context only, do NOT send to customer |
| `company_id` | Tenant — for routing the manual fix to the right CRM account |
| `conversation_id` | PARWA conversation ID — for cross-referencing chat history |

---

## 4. Resolution procedure

### 4.1 Pre-flight (always)

1. Acknowledge the alert. Open the DLQ entry on `/dashboard/crm-dlq` to see the snapshot fields.
2. Note down `crm_provider`, `crm_ticket_id`, `escalation_id`, and `company_id` — you'll need them in steps 4.2–4.4.
3. Confirm the vault ticket is indeed in `REPROCESS_EXHAUSTED`:
   ```bash
   curl -X GET "https://parwa-backend.onrender.com/api/escalation/list?tenant_id=<company_id>&reprocess_status=exhausted&limit=100" \
     -H 'Authorization: Bearer <PARWA_AT>'
   ```
   You should see the `escalation_id` in the response. If not, the entry may already have been resolved — re-check `/api/dlq/entries/{id}`.

### 4.2 Reset the CRM ticket

Choose the section that matches `crm_provider`.

#### 4.2.1 Zendesk

The goal: set ticket status back to `open`, add the same tags + internal note that `push_permanent_failure_to_crm()` would have added.

```bash
# Get the ticket's current state first (sanity check)
curl -X GET "https://<SUBDOMAIN>.zendesk.com/api/v2/tickets/<CRM_TICKET_ID>.json" \
  -u "<EMAIL>/token:<ZENDESK_API_TOKEN>"

# Reset to open + tag + internal note
curl -X PUT "https://<SUBDOMAIN>.zendesk.com/api/v2/tickets/<CRM_TICKET_ID>.json" \
  -u "<EMAIL>/token:<ZENDESK_API_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket": {
      "status": "open",
      "tags": ["ai-cannot-resolve", "needs-human", "parwa"],
      "comment": {
        "public": false,
        "body": "PARWA AI attempted to resolve this ticket 3 times via guidance flow and could not meet the quality threshold. Last AI response preview: <RESPONSE_TEXT_PREVIEW>. Vault escalation ID: <ESCALATION_ID>. Returning to the human queue for manual handling. See documents/ops_runbooks/crm_permanent_failure_push_failed_runbook.md."
      }
    }
  }'
```

**Verify**: re-`GET` the ticket. Confirm `status=open`, tags include `ai-cannot-resolve`, and the internal note appears in the ticket's comment history.

#### 4.2.2 HubSpot

The goal: move the ticket back to pipeline stage `1` (New), set category, add a note engagement.

```bash
# Get current ticket state
curl -X GET "https://api.hubapi.com/crm/v3/objects/tickets/<CRM_TICKET_ID>" \
  -H "Authorization: Bearer <HUBSPOT_ACCESS_TOKEN>"

# Move to New (stage 1) + tag category
curl -X PATCH "https://api.hubapi.com/crm/v3/objects/tickets/<CRM_TICKET_ID>" \
  -H "Authorization: Bearer <HUBSPOT_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "properties": {
      "hs_pipeline_stage": "1",
      "hs_ticket_category": "PARWA_AI_CANNOT_RESOLVE"
    }
  }'

# Add a note engagement to the ticket
curl -X POST "https://api.hubapi.com/crm/v3/objects/notes" \
  -H "Authorization: Bearer <HUBSPOT_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "properties": {
      "hs_note_body": "PARWA AI attempted to resolve this ticket 3 times via guidance flow and could not meet the quality threshold. Returning to the human queue for manual handling. Vault escalation ID: <ESCALATION_ID>.",
      "hs_timestamp": "'$(date -u +%s%3N)'"
    }
  }'

# Then associate the note with the ticket (note ID from the previous response)
curl -X PUT "https://api.hubapi.com/crm/v3/objects/notes/<NOTE_ID>/associations/tickets/<CRM_TICKET_ID>/ticket_to_note" \
  -H "Authorization: Bearer <HUBSPOT_ACCESS_TOKEN>"
```

**Verify**: re-`GET` the ticket. Confirm `hs_pipeline_stage=1`, `hs_ticket_category=PARWA_AI_CANNOT_RESOLVE`, and the note appears in the ticket's timeline.

#### 4.2.3 Generic (webhook-based CRM)

The goal: re-fire the `parwa.cannot_resolve` webhook event to the customer's configured webhook URL.

1. Find the webhook URL from the tenant's CRM integration config (admin dashboard → Integrations → CRM).
2. Re-fire the event:

   ```bash
   curl -X POST "<WEBHOOK_URL>" \
     -H "Content-Type: application/json" \
     -H "X-Parwa-Event: parwa.cannot_resolve" \
     -H "X-Parwa-Signature: <RECOMPUTE_HMAC_WITH_INTEGRATION_SECRET>" \
     -d '{
       "event": "parwa.cannot_resolve",
       "action": "reset_to_new",
       "ticket_id": "<CRM_TICKET_ID>",
       "escalation_id": "<ESCALATION_ID>",
       "attempts": 3,
       "failure_context": "<FAILURE_CONTEXT>",
       "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
     }'
   ```

   To recompute the HMAC signature, use the integration's shared secret and the request body — see `backend/app/core/crm_bridge/crm_bridge.py::GenericCRMAdapter.push_permanent_failure_to_crm()` for the exact signature algorithm.

3. Confirm the customer's CRM acknowledged the webhook (look for a 2xx response and their own internal logs).

### 4.3 Notify the human support team

The CRM ticket is now in `open` / `new` state in the customer's support queue, but humans don't know WHY it came back. Add (or have a team lead add) a public-visible comment that includes:

- The original customer request (already in the ticket history)
- That PARWA AI attempted 3 guidance cycles and couldn't resolve
- The last AI response preview (for context, marked as "AI attempt — do not send to customer as-is")
- The escalation_id for cross-reference

### 4.4 Mark the DLQ entry as resolved

Once the CRM ticket is confirmed reset, mark the DLQ entry as resolved so it stops showing in the dashboard:

```bash
# Option A: via API (preferred — audited)
curl -X POST "https://parwa-backend.onrender.com/api/dlq/entries/<DLQ_ENTRY_ID>/resolve?retry_succeeded=false" \
  -H 'Authorization: Bearer <PARWA_AT>'
```

`retry_succeeded=false` because the underlying CRM push did NOT succeed — the entry was resolved via manual ops action, not via an automated retry.

```bash
# Option B: via the dashboard
```
On `/dashboard/crm-dlq`, click the entry's "Resolve" button. A confirmation dialog appears; select "Resolved manually (CRM push did not succeed)" and confirm.

### 4.5 Post-incident review (optional, for repeated occurrences)

If you see more than 2 `crm_permanent_failure_push_failed` entries in a 7-day window for the same tenant:

1. Check the tenant's CRM integration health: `GET /api/integrations` → look for the CRM integration's `last_error` and `consecutive_failures` fields.
2. Check whether their CRM API token has expired — most failures are auth-related.
3. Consider temporarily disabling AI guidance mode for that tenant via the admin dashboard (toggle `GUIDANCE_MAX_RETRIES=0` or disable the AI autopilot for the channel) until the CRM connectivity is restored.
4. File a post-incident note in `documents/` summarizing root cause + remediation.

---

## 5. Failure modes of the runbook itself

| Symptom | Likely cause | Fix |
|---|---|---|
| `404` on `GET /api/dlq/entries/{id}` | Entry was auto-resolved by a Celery cleanup task, or the ID is wrong | Re-list with `resolved=true` to find it; if truly gone, mark the underlying vault ticket as resolved instead via `/api/escalation/resolve` |
| `401`/`403` on Zendesk/HubSpot API | The CRM integration's stored credentials expired | Re-authenticate via the Integrations page; document the rotation in the tenant's account record |
| Zendesk `422` "Ticket cannot be open" | Ticket has a closed parent/child relationship | First reset the parent ticket, then retry; or use `status=pending` as a fallback |
| HubSpot `409` "Ticket in read-only view" | Tenant's HubSpot pipeline has custom validation rules | Move the ticket to the equivalent "new"-stage in their custom pipeline; record the stage ID in the integration's config |
| Webhook URL returns 5xx | Customer's webhook endpoint is down | Page their on-call; the PARWA-side fix is done — re-fire the webhook once they confirm recovery |

---

## 6. Related files

| File | Purpose |
|---|---|
| `backend/app/core/escalation_vault/guidance_ticket_flow.py` | Source of the DLQ entry — see `_persist_crm_permanent_failure_to_dlq()` |
| `backend/app/core/crm_bridge/crm_bridge.py` | `push_permanent_failure_to_crm()` adapters (Zendesk/HubSpot/Generic) — use this as the canonical API call reference |
| `backend/app/core/parwa_pipeline/dlq.py` | `persist_to_dlq()` + `get_dlq_entries()` + `resolve_dlq_entry()` |
| `backend/app/api/dlq.py` | HTTP API surface — `POST /api/dlq/entries/{id}/resolve` |
| `src/app/dashboard/crm-dlq/page.tsx` | Frontend dashboard page with CRM-DLQ tile + filter UI |
| `CLAUDE.md` BC-017 + BC-018 | Building codes covering the permanent-failure path and the ops dashboard tile |

---

## 7. Change log

| Date | Change | Author |
|---|---|---|
| 2026-06-25 | Initial version (BC-018) | PARWA team |
