# PARWA Feature Specs — Batch 6

> **Dashboard / Tickets / AI Core**
>
> Features: F-036, F-037, F-038, F-048, F-049, F-050, F-052, F-058, F-061, F-062, F-065, F-066, F-068, F-069, F-070
>
> Generated: July 2025 | Version 1.0

---

## Table of Contents

1. [F-036: Dashboard Home Overview](#f-036-dashboard-home-overview)
2. [F-037: Activity Feed (Real-time)](#f-037-activity-feed-real-time)
3. [F-038: Key Metrics Overview](#f-038-key-metrics-overview)
4. [F-048: Ticket Search](#f-048-ticket-search)
5. [F-049: Ticket Intent Classification](#f-049-ticket-intent-classification)
6. [F-050: Ticket Assignment](#f-050-ticket-assignment)
7. [F-052: Omnichannel Sessions](#f-052-omnichannel-sessions)
8. [F-058: Blocked Response Manager & Review Queue](#f-058-blocked-response-manager--review-queue)
9. [F-061: DSPy Prompt Optimization](#f-061-dspy-prompt-optimization)
10. [F-062: Sentiment Analysis (Empathy Engine)](#f-062-sentiment-analysis-empathy-engine)
11. [F-065: Auto-Response Generation](#f-065-auto-response-generation)
12. [F-066: AI Draft Composer (Co-Pilot Mode)](#f-066-ai-draft-composer-co-pilot-mode)
13. [F-068: Context Health Meter](#f-068-context-health-meter)
14. [F-069: 90% Capacity Popup](#f-069-90-capacity-popup)
15. [F-070: Customer Identity Resolution](#f-070-customer-identity-resolution)

---

# F-036: Dashboard Home Overview

## Overview

The Dashboard Home is the primary landing page after login, presenting a unified card-based layout of all key widgets — activity feed, metrics summary, adaptation tracker, savings counter, and contextual alerts. It personalizes the widget arrangement and data visibility based on the authenticated user's role (agent, supervisor, admin) and the tenant's plan tier, ensuring every user sees the most actionable information first.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `GET /api/dashboard/layout` | GET | `?role={agent\|supervisor\|admin}` | Returns widget config: which cards are visible, their order, and sizes for the user's role |
| `GET /api/dashboard/summary` | GET | `?range={24h\|7d\|30d}` | Aggregated counts: open tickets, AI-resolved count, avg response time, unresolved escalations |
| `GET /api/dashboard/alerts` | GET | — | Active contextual alerts: plan limits approaching, integration failures, AI paused status |

## DB Tables

- **`dashboard_widgets`** — `id, company_id, widget_type, position_x, position_y, width, height, is_visible, role_filter, config_json`
- **`dashboard_alerts`** — `id, company_id, alert_type, severity, message, dismissible, dismissed_by, dismissed_at, created_at`
- Leverages: `tickets`, `integrations`, `audit_trail` for aggregate queries (all with `company_id` scoping per BC-001)

## BC Rules

- **BC-001** (Multi-Tenant Isolation): All dashboard queries filtered by `company_id`. Widget configs are per-tenant. One tenant never sees another's metrics.
- **BC-011** (Authentication & Security): Widget visibility filtered by user role. Admin widgets (billing, agent provisioning) hidden from agents.
- **BC-012** (Error Handling & Resilience): If any widget's data source fails, the card renders a "Data temporarily unavailable" placeholder with retry. The dashboard never blocks on a single widget failure.

## Edge Cases

1. **New tenant with zero tickets** — All metric cards display "No data yet" with encouraging onboarding messaging and a link to F-028 (Onboarding Wizard).
2. **Agent viewing during AI pause** — Alert banner displayed prominently. Metrics still show historical data. Activity feed shows pause event per BC-005 Rule 8.
3. **Tenant on Starter plan missing Growth-tier widgets** — Widget config excludes plan-gated cards. A "Upgrade to unlock" teaser shown for hidden widgets (F-042 Growth Nudge).
4. **Concurrent admin layout changes** — Layout writes use optimistic locking with `updated_at` version check. Last-write-wins with merge conflict notification.

## Acceptance

1. Given an admin user logs in, When the dashboard loads, Then all admin-visible widgets render within 2 seconds and each card displays data scoped to the admin's tenant only.
2. Given an agent user logs in, When the dashboard loads, Then agent-specific widgets (my tickets, my metrics) are shown and admin-only widgets (billing, agent management) are hidden.
3. Given a widget's data source returns an error, When the dashboard renders, Then that card shows a "Data temporarily unavailable" message while all other widgets render normally.
4. Given a tenant on the Starter plan, When the dashboard loads, Then Growth/High-tier exclusive widgets are hidden with an upgrade teaser card visible.

---

# F-037: Activity Feed (Real-time)

## Overview

The Activity Feed is a live-updating event stream showing recent platform events — new tickets, AI resolutions, escalations, agent assignments, integration syncs, and team actions — delivered via Socket.io with infinite-scroll pagination and filtering by event type. Each event links through to its relevant detail view, giving operators a real-time operational pulse without refreshing the page.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `GET /api/events/feed` | GET | `?type={ticket\|ai\|escalation\|integration\|team}&before={cursor}&limit=25` | Paginated list of feed events with actor, action, target, timestamp, and deep-link |
| `GET /api/events/since` | GET | `?last_seen={timestamp}` | Events missed during Socket.io disconnection (BC-005 rehydration) |
| `Socket.io: event:new` | Emit | `tenant_{company_id}` room | Real-time push of each new activity event as it occurs |

## DB Tables

- **`event_buffer`** — `id, company_id, event_type, payload (JSONB), created_at` (24h retention, cleaned by Celery beat per BC-005 Rule 4)
- **`activity_events`** — `id, company_id, actor_id, actor_type (ai\|human\|system), action, target_type, target_id, metadata (JSONB), created_at`
  - Indexes: `idx_ae_company_created (company_id, created_at DESC)`, `idx_ae_type (company_id, event_type, created_at DESC)`

## BC Rules

- **BC-005** (Real-Time Communication): Socket.io rooms scoped as `tenant_{company_id}`. Every emit also stored in `event_buffer`. Client reconnection fetches missed events via `/api/events/since`. Graceful degradation: feed works on REST-only page refresh.
- **BC-001** (Multi-Tenant Isolation): All activity events filtered by `company_id`. No cross-tenant event leakage.
- **BC-012** (Error Handling & Resilience): If Socket.io is down, feed still loads via REST pagination. Events are never lost — always persisted to DB first.

## Edge Cases

1. **Client disconnects for 30 minutes** — On reconnect, `/api/events/since` returns up to 500 missed events (capped to prevent overload). Older events available via REST pagination.
2. **High-velocity tenant (100+ events/minute)** — Server-side throttling: events batched into 1-second chunks before Socket.io emit. Pagination returns 25 events per page regardless of velocity.
3. **AI pause event during active feed** — Pause event emitted with `paused: true` flag. Feed UI renders a persistent "AI Paused" banner. All subsequent AI events tagged with pause context.
4. **Filter returns zero results** — Empty state shows "No events matching this filter" with a "Clear filters" button and suggestion to broaden the time range.

## Acceptance

1. Given a new ticket is created by the system, When the event is emitted, Then all connected clients in the same tenant's Socket.io room receive the event within 500ms and the feed auto-scrolls to show it.
2. Given a client disconnects for 5 minutes and 30 events occur, When the client reconnects, Then all 30 missed events are fetched via `/api/events/since` and appended to the feed in chronological order.
3. Given a user filters the feed by "AI resolutions" event type, When the filter is applied, Then only AI resolution events are displayed and the filter is reflected in the URL query params for shareability.
4. Given Socket.io is completely unavailable, When the user refreshes the page, Then the activity feed loads and displays all recent events via the REST API endpoint with no data loss.

---

# F-038: Key Metrics Overview

## Overview

The Key Metrics Overview is a widget grid displaying the tenant's most important KPIs — total tickets, AI resolution rate, average response time, customer satisfaction (CSAT) score, and active integration health — each with configurable time range selectors (24h, 7d, 30d) and inline trend sparklines. These metrics serve as the primary data source for other dashboard widgets (F-040 Savings, F-041 Workforce Allocation) and are computed from pre-aggregated materialized views for sub-second rendering.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `GET /api/metrics/summary` | GET | `?range={24h\|7d\|30d}` | All KPI cards: `{total_tickets, ai_resolved, ai_resolution_rate, avg_response_time_ms, csat_score, integration_health, sparkline_data}` |
| `GET /api/metrics/{metric}` | GET | `?range={24h\|7d\|30d}&granularity={hour\|day}` | Individual metric with trend data points for sparkline rendering |

## DB Tables

- **`metric_aggregates`** (materialized view, refreshed every 5 min by Celery beat) — `company_id, metric_name, period_type, period_start, value_primary, value_secondary, computed_at`
- **`tickets`** — Source for ticket count, resolution status, response time calculations
- **`ticket_feedback`** — Source for CSAT scores
- **`integrations`** — Source for health status (last_sync_at, status)

## BC Rules

- **BC-001** (Multi-Tenant Isolation): All metric queries filtered by `company_id`. Materialized view includes `company_id` partitioning.
- **BC-007** (AI Model Interaction): AI resolution rate metric uses confidence-score-weighted counts. Resolution quality metrics feed back into per-company confidence threshold configuration (BC-007 Rule 9).
- **BC-012** (Error Handling & Resilience): If materialized view refresh fails, stale data (up to 15 minutes old) is served with a "Last updated: X min ago" indicator. No 500 errors for metrics.

## Edge Cases

1. **New tenant with <1 hour of data** — 24h range returns available data with a "Partial data" badge. 7d and 30d ranges show "Insufficient data — collecting" message.
2. **Materialized view refresh fails** — Last-known-good data served. "Data may be stale" warning shown on each card. Celery DLQ alert triggers ops team investigation.
3. **Metric spike anomaly (10x normal volume)** — Sparkline renders normally but a "Anomaly detected" badge is shown. Optional link to F-044 (Seasonal Spike Forecast) for investigation.
4. **Time range switch during active WebSocket connection** — New metric data pushed via Socket.io `metrics:updated` event. No page reload required.

## Acceptance

1. Given the user selects the "7d" time range, When the metrics load, Then all KPI cards display values computed from the last 7 days of data with a sparkline showing daily trend points.
2. Given the materialized view is 8 minutes stale, When metrics are displayed, Then a "Last updated: 8 min ago" indicator is shown on each card and the data is the last known-good values.
3. Given a tenant has both AI-resolved and human-handled tickets, When the AI Resolution Rate metric is computed, Then the rate is `ai_resolved_count / total_resolved_count * 100` rounded to 1 decimal place.
4. Given a user hovers over a sparkline data point, When the tooltip renders, Then it shows the exact metric value and the timestamp for that data point.

---

# F-048: Ticket Search

## Overview

Ticket Search provides full-text search across tickets by customer name/email, ticket ID, or message content with fuzzy matching and relevance ranking. It uses PostgreSQL's `tsvector` for content search combined with trigram similarity for typo tolerance, and returns faceted filter counts (by status, channel, assignee) alongside results for rapid narrowing across large ticket volumes.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `GET /api/tickets/search` | GET | `?q={query}&page={1}&limit={25}&sort={relevance\|date}&status={open\|closed}&channel={email\|chat}` | `{results: [{ticket_id, subject, preview, relevance_score, status, channel, customer_name, updated_at}], total, facets: {status: {}, channel: {}}}` |
| `GET /api/tickets/search/suggestions` | GET | `?q={partial}&limit={5}` | Top 5 autocomplete suggestions with type-ahead for ticket IDs and customer names |

## DB Tables

- **`tickets`** — `id, company_id, subject, status, channel, customer_id, assignee_id, created_at, updated_at`
- **`ticket_messages`** — `id, company_id, ticket_id, sender_type, content_text, created_at`
  - `content_text` column: full-text search index via `tsvector('english', content_text)` with GIN index
  - Trigram index: `gin (content_text gin_trgm_ops)` for fuzzy matching
  - Composite index: `idx_tm_ticket_created (ticket_id, created_at)`
- **`customers`** — `id, company_id, full_name, email, phone` (searched by name/email with trigram)

## BC Rules

- **BC-001** (Multi-Tenant Isolation): All search queries include `WHERE company_id = :tenant_id`. No cross-tenant ticket leakage via search. A search for a term that exists in another tenant's tickets returns zero results.
- **BC-011** (Authentication & Security): Search results respect role-based visibility. Agents only see tickets assigned to them or their team unless they have "view all" permission.
- **BC-012** (Error Handling & Resilience): Empty query returns no results (not a 400). Very long queries (>500 chars) truncated with notification. Timeout on complex queries at 5 seconds, returning partial results.

## Edge Cases

1. **Typo in search query ("refunnd" instead of "refund")** — Trigram similarity matching catches the typo and returns refund-related tickets with a reduced relevance score, ordered after exact matches.
2. **Search returns 10,000+ results** — Pagination enforced (25 per page). Facet counts reflect total matches. Performance maintained via partitioned GIN index on `company_id`.
3. **Special characters in query (SQL injection attempt)** — Parameterized queries prevent injection. Literal special characters are escaped. No raw SQL interpolation.
4. **Search by ticket ID fragment ("TKT-45")** — Ticket ID lookup prioritized over full-text search. Partial ID match returns exact ticket with high relevance score.

## Acceptance

1. Given a user searches for "refund status" with a 7-day scope, When results load, Then tickets containing both "refund" and "status" in subject or message content are returned, ranked by relevance score.
2. Given a user types "TKT-123" in the search box, When the autocomplete triggers, Then the exact ticket (if it belongs to the user's tenant) appears as the top suggestion.
3. Given a user searches with a typo "shiping", When fuzzy matching activates, Then tickets containing "shipping" are returned with a "Did you mean: shipping?" suggestion.
4. Given a search returns results across multiple statuses, When facet counts are displayed, Then the count for each status (open, closed, pending) accurately reflects the total matches per status for the current tenant.

---

# F-049: Ticket Intent Classification

## Overview

Ticket Intent Classification is the AI engine that automatically categorizes every incoming ticket by primary intent (refund, technical support, billing inquiry, feature request, complaint, general inquiry) and urgency level (urgent, routine, informational) using the Smart Router's Light-tier LLM. Classification drives downstream routing (F-050), response strategy selection, and escalation policies, and is logged as structured metadata on each ticket for analytics and training feedback loops.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `POST /api/internal/classify` | POST | `{ticket_id, message_content, channel}` | `{intent, urgency, confidence, model_used, latency_ms}` — internal service, not user-facing |
| `POST /api/tickets/{id}/classify/correct` | POST | `{correct_intent, correct_urgency}` | Records correction as training feedback. Returns `{feedback_id, updated_model_mistake_count}` |
| `GET /api/classifications/stats` | GET | `?range={7d\|30d}` | Classification accuracy stats: `{total_classified, corrections, accuracy_rate, per_intent_breakdown}` |

## DB Tables

- **`ticket_intents`** — `id, ticket_id (FK), company_id, intent (VARCHAR 50), urgency (VARCHAR 20), confidence (DECIMAL 5,2), model_id (FK → api_providers), corrected_intent (VARCHAR 50), corrected_at, created_at`
  - Indexes: `idx_ti_ticket (ticket_id UNIQUE)`, `idx_ti_company_intent (company_id, intent)`
- **`classification_corrections`** — `id, company_id, ticket_id, original_intent, corrected_intent, original_urgency, corrected_urgency, corrected_by (FK → users.id), created_at`
- **`model_mistakes`** — `id, company_id, model_id, mistake_count, last_mistake_at` — tracks mistakes per BC-007 Rule 10 (threshold: 50)

## BC Rules

- **BC-007** (AI Model Interaction): Uses Smart Router Light tier for classification. PII redacted before LLM call (BC-007 Rule 5). Confidence thresholds stored per-company (BC-007 Rule 9). If confidence below threshold, ticket flagged for human review. Mistake count tracked — model removed from rotation at 50 mistakes (BC-007 Rule 10).
- **BC-004** (Background Jobs): Classification runs as a Celery task triggered by ticket creation. `company_id` is first parameter. `max_retries=3`, exponential backoff.
- **BC-001** (Multi-Tenant Isolation): Classification models and thresholds are per-tenant. Company A's classifier never processes Company B's tickets.

## Edge Cases

1. **Multi-intent message ("I want a refund AND my account is locked")** — Classifies as the dominant intent (highest confidence). Secondary intent stored in `metadata` JSONB field for potential multi-label routing.
2. **Classification confidence below threshold (e.g., 45%)** — Ticket flagged as `classification_review_needed`. Routed to default queue instead of intent-specific queue. Human agent prompted to verify classification.
3. **LLM returns 429 (rate limited) during classification** — Smart Router tries next model in Light tier (BC-007 Rule 3). If all Light models rate-limited, falls back to Medium tier. Classification still completes within 5 seconds.
4. **Model accumulates 50 mistake reports** — Automatically flagged for retraining and removed from active rotation (BC-007 Rule 10). New classification requests routed to next available model. Alert sent to ops team.

## Acceptance

1. Given a new ticket is created with message "I need to cancel my subscription and get a refund", When the classification task runs, Then the ticket is classified with intent=`refund` and urgency=`routine` with confidence ≥ 70% within 3 seconds.
2. Given a classification returns confidence < 55%, When the ticket is routed, Then the ticket status includes `classification_review_needed` flag and it appears in the supervisor review queue.
3. Given an agent corrects a misclassification from "billing" to "technical", When the correction is submitted, Then the correction is logged in `classification_corrections`, the model's mistake count increments, and the ticket's intent is updated.
4. Given a model accumulates 50 mistake reports for a tenant, When the threshold is reached, Then the model is automatically removed from the tenant's active rotation and an alert is sent to the operations team.

---

# F-050: Ticket Assignment

## Overview

Ticket Assignment combines AI-powered automatic routing (based on classification from F-049, agent workload, and skill matching) with full manual override capability for supervisors. Auto-routing scores each agent on classification match, current open ticket count, and historical resolution speed, then assigns the ticket to the best-fit agent. Supervisors can reassign at any time, configure round-robin rules for specific intents, and set escalation paths that trigger when no qualified agent is available.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `POST /api/internal/assign` | POST | `{ticket_id, strategy: auto\|round_robin\|manual}` | `{assigned_agent_id, assignment_reason, score_breakdown}` — internal routing service |
| `POST /api/tickets/{id}/reassign` | POST | `{target_agent_id, reason}` | `{success, previous_agent_id, reassigned_by}` — manual override endpoint |
| `GET /api/agents/workload` | GET | `?skill={refund\|technical}` | `{agents: [{id, name, open_count, max_capacity, skills, avg_resolution_time}]}` |
| `PUT /api/assignment-rules` | PUT | `{intent, strategy, agent_pool, escalation_timeout}` | Updated assignment rules config |

## DB Tables

- **`ticket_assignments`** — `id, ticket_id (FK), company_id, agent_id (FK → users.id), assignment_type (auto\|manual\|round_robin), score_breakdown (JSONB), reassigned_from_id, reassigned_by, created_at`
  - Indexes: `idx_ta_ticket (ticket_id)`, `idx_ta_agent (agent_id, created_at DESC)`
- **`assignment_rules`** — `id, company_id, intent, strategy, agent_pool_ids (UUID[]), escalation_timeout_min, max_capacity_per_agent, is_active`
- **`agent_workload_cache`** — `agent_id, company_id, open_ticket_count, last_updated` (Redis-backed, refreshed every 30s)

## BC Rules

- **BC-008** (State Management): Ticket assignment is a GSD state transition (`unassigned` → `assigned`). State persisted to both Redis and PostgreSQL. Assignment history maintained for audit.
- **BC-005** (Real-Time Communication): Assignment changes emitted via Socket.io to both the assigned agent and the tenant room. Agent's ticket list updates in real-time without refresh.
- **BC-001** (Multi-Tenant Isolation): Agent pools and assignment rules are per-tenant. Agents from one tenant are never considered for another tenant's tickets.
- **BC-012** (Error Handling & Resilience): If auto-assignment fails (no agents available), ticket enters `unassigned` queue with escalation timer. No ticket is silently dropped.

## Edge Cases

1. **No agent available with matching skill** — Ticket enters the unassigned escalation queue. Escalation timer starts per `assignment_rules.escalation_timeout_min`. After timeout, alerts supervisor via Socket.io and email.
2. **Agent at max capacity (e.g., 15/15 open tickets)** — Agent excluded from auto-assignment scoring. Ticket routed to next-best agent. If all agents at capacity, enters unassigned queue.
3. **Supervisor reassigns ticket while AI is processing** — Manual override takes precedence. AI assignment task checks current state before writing. If ticket already reassigned, AI task aborts silently.
4. **Agent goes offline mid-assignment** — Agent's availability flag set to `false` via Socket.io disconnect. Open tickets remain assigned but agent excluded from future auto-assignments. No reassignment of existing tickets unless triggered by supervisor.

## Acceptance

1. Given a ticket classified as "refund" intent, When auto-assignment runs, Then the ticket is assigned to the agent with the highest score combining refund skill match, lowest open count, and fastest avg resolution time.
2. Given a supervisor reassigns ticket TKT-100 from Agent A to Agent B with reason "specialist needed", When the reassignment completes, Then the ticket's assignee is Agent B, the reassignment is logged with reason and actor, and both agents receive real-time Socket.io notifications.
3. Given all agents for "technical" intent are at max capacity, When a new technical ticket arrives, Then the ticket enters the unassigned queue and a supervisor alert is emitted within the configured escalation timeout.
4. Given an assignment rule specifies round-robin for "billing" intent with agents [A, B, C], When 6 billing tickets arrive, Then tickets are distributed A→B→C→A→B→C in order.

---

# F-052: Omnichannel Sessions

## Overview

Omnichannel Sessions consolidate all customer interactions across channels (email, live chat, SMS, voice calls, social media) into a single unified ticket thread. Each channel's messages are ingested via channel-specific webhooks (Brevo for email, Twilio for SMS/voice, custom for chat/social), stitched into a chronological timeline while preserving channel context metadata, and surfaced in a single conversation view. This enables agents to see the full customer journey without switching between tools.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `GET /api/tickets/{id}/messages` | GET | `?channel=all\|email\|chat\|sms\|voice\|social&before={cursor}&limit=50` | Chronological messages with `{id, channel, sender_type, content, attachments, channel_metadata, created_at}` |
| `GET /api/tickets/{id}/channels` | GET | — | Summary of all channels involved: `{channels: [{type, message_count, first_message_at, last_message_at, external_id}]}` |
| `POST /api/tickets/{id}/messages` | POST | `{channel, content, attachments}` | Adds agent message to the thread. Dispatches to channel-specific sender (Brevo/Twilio/chat). |

**Channel Webhook Endpoints (inbound):**

| Endpoint | Method | Provider | Key Data |
|----------|--------|----------|----------|
| `POST /webhooks/brevo/inbound` | POST | Brevo | Inbound email parsed to ticket message (BC-003, BC-006) |
| `POST /webhooks/twilio/sms` | POST | Twilio | Incoming SMS mapped to ticket via phone number (BC-003) |
| `POST /webhooks/twilio/voice` | POST | Twilio | Call started/ended events logged. Transcription stored if available. |
| `POST /webhooks/chat/message` | POST | Internal | Live chat messages from embedded widget |
| `POST /webhooks/social/{platform}` | POST | Social | DMs and mentions from social channels (Twitter/IG/FB) |

## DB Tables

- **`ticket_messages`** — `id, company_id, ticket_id, channel (VARCHAR 20), sender_type (customer\|agent\|ai\|system), content_text, content_html, attachments (JSONB), channel_metadata (JSONB — email headers, SMS number, call duration, social post URL), external_message_id, created_at`
  - Indexes: `idx_tm_ticket_created (ticket_id, created_at)`, `idx_tm_channel (company_id, channel, created_at DESC)`
- **`customer_channels`** — `id, company_id, customer_id, channel_type, external_id (email address/phone/social handle), is_verified, last_used_at`
  - Unique constraint: `(company_id, channel_type, external_id)`
- **`channel_configs`** — `id, company_id, channel_type, webhook_secret, is_active, config_json` (per BC-003 webhook verification)

## BC Rules

- **BC-003** (Webhook Handling): All channel webhooks verify HMAC/signature before processing (Paddle, Twilio, Brevo patterns). Idempotency via `external_message_id`. Async processing via Celery. Response within 3 seconds.
- **BC-005** (Real-Time Communication): New messages from any channel emitted via Socket.io to the tenant room and the assigned agent. Real-time typing indicators for live chat channel.
- **BC-006** (Email Communication): Inbound email processing checks for OOO headers and 5-per-24h rate limit. Outbound email responses use Brevo templates. Email loop detection active.
- **BC-001** (Multi-Tenant Isolation): All channel data scoped by `company_id`. Customer channel mappings are tenant-isolated. Cross-tenant channel linking prevented.

## Edge Cases

1. **Customer switches from email to chat mid-conversation** — Both messages stitched into same ticket thread. Channel transition tagged with a system message: "Customer continued via live chat." Channel context preserved in `channel_metadata`.
2. **Duplicate webhook delivery (Twilio retries)** — Idempotency check on `external_message_id` prevents duplicate message creation. Second delivery returns 200 with `already_processed`.
3. **Voice call with no transcription** — Call logged as a message with channel=voice, content="Voice call (duration: 4m 32s)", and `channel_metadata` containing call SID and recording URL. Agent can manually add notes.
4. **Social media DM from unregistered customer** — System creates a new customer record, links the social channel, and creates a new ticket. Identity resolution (F-070) attempts to match to existing customer by profile signals.

## Acceptance

1. Given a customer sends an email, then later sends an SMS about the same issue, When both are ingested, Then both messages appear in the same ticket thread in chronological order with correct channel labels.
2. Given an agent is viewing a ticket, When a new customer message arrives from any channel, Then the message appears in the conversation view in real-time via Socket.io without page refresh.
3. Given a Twilio SMS webhook is delivered twice with the same MessageSID, When the second delivery arrives, Then the system returns `already_processed` and no duplicate message is created.
4. Given an agent replies to a ticket that originated from email, When the reply is sent, Then it dispatches via Brevo using the correct Brevo template and logs the email in `email_logs`.

---

# F-058: Blocked Response Manager & Review Queue

## Overview

The Blocked Response Manager captures all AI responses that were blocked by the Guardrails AI (F-057) before they reached customers, and presents them in a dedicated admin review queue. Admins can inspect the original prompt, the blocked response, and the specific guardrail violation reason, then choose to edit and approve the response, permanently ban the blocking pattern, or dismiss it. Approved responses undergo a second Guardrails check before delivery per BC-007 Rule 7.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `GET /api/guardrails/queue` | GET | `?status={pending\|approved\|dismissed\|banned}&reason={hallucination\|off_topic\|pii_leak\|policy_violation}&page={1}` | Paginated blocked responses with `{id, ticket_id, original_prompt, blocked_response, block_reason, model_used, created_at}` |
| `POST /api/guardrails/queue/{id}/approve` | POST | `{edited_response?}` | Runs second Guardrails check. If passed, delivers to customer. Returns `{delivered: true, new_guardrails_result}` |
| `POST /api/guardrails/queue/{id}/dismiss` | POST | `{dismissal_reason}` | Marks as dismissed. Safe fallback template was already sent to customer. Returns `{status: dismissed}` |
| `POST /api/guardrails/ban-pattern` | POST | `{pattern_type, pattern_value, reason}` | Adds pattern to permanent ban list. Future responses matching this pattern are auto-blocked. |

## DB Tables

- **`guardrails_blocked_queue`** — `id, company_id, ticket_id, message_id, original_prompt (TEXT), blocked_response (TEXT), block_reason (VARCHAR 50), block_details (JSONB — specific rule violations), model_id, reviewed_by (FK → users.id), review_action (approved\|dismissed\|banned), edited_response (TEXT), reviewed_at, created_at`
  - Indexes: `idx_gbq_company_status (company_id, review_action, created_at DESC)`, `idx_gbq_reason (company_id, block_reason)`
- **`guardrails_banned_patterns`** — `id, company_id, pattern_type (regex\|keyword\|topic), pattern_value, added_by (FK → users.id), reason, is_active, created_at`
- **`guardrails_audit_log`** — `id, company_id, blocked_queue_id, action, performed_by, result, created_at`

## BC Rules

- **BC-007** (AI Model Interaction): Released responses MUST pass a second Guardrails check before delivery (BC-007 Rule 7). If the second check also blocks, the response cannot be approved — admin is informed the edit is still unsafe. Guardrails evaluation uses the Smart Router with PII redaction.
- **BC-009** (Approval Workflow): Approving a previously blocked response is an approval action. It requires admin role. Every approve/dismiss action is logged in `guardrails_audit_log` with actor, timestamp, and reason.
- **BC-001** (Multi-Tenant Isolation): Blocked response queue is per-tenant. Admin from Company A cannot see or approve Company B's blocked responses.
- **BC-010** (Data Lifecycle): Blocked responses containing PII are redacted before display in the review queue. Original PII never stored in `blocked_response` column (PII redacted before DB store per BC-007 Rule 5).

## Edge Cases

1. **Admin edits a blocked response but second Guardrails check still blocks it** — Edit is rejected. Admin sees the specific rule that still triggers. Must edit further or dismiss. Response is never delivered.
2. **Queue backlog of 500+ blocked responses** — Pagination enforced (25 per page). Filters available by block reason, date range, and model. Batch dismiss available for "off_topic" category only (not PII or hallucination).
3. **Blocked response is for a ticket that was already resolved** — Queue item marked as `stale`. Admin can still review but cannot deliver (ticket closed). Stale items archived after 30 days per BC-010.
4. **Customer sends a follow-up while blocked response is in queue** — Safe fallback template was already sent. The follow-up triggers a new AI response cycle. The original blocked item remains in queue for review (training value).

## Acceptance

1. Given the Guardrails AI blocks a response for hallucination, When the blocked response is captured, Then it appears in the admin review queue within 1 second with the full original prompt, blocked response, and hallucination reason.
2. Given an admin edits a blocked response and clicks "Approve", When the second Guardrails check runs, Then if passed, the response is delivered to the customer via the original channel and the queue item is marked as `approved`.
3. Given an admin approves a response that fails the second Guardrails check, When the check returns blocked, Then the approval is rejected with a message explaining which guardrail rule still triggers and the response is NOT delivered.
4. Given an admin adds a pattern to the banned patterns list, When a future AI response matches the pattern, Then it is automatically blocked without requiring a full Guardrails evaluation, and it enters the queue with reason `banned_pattern`.

---

# F-061: DSPy Prompt Optimization

## Overview

DSPy Prompt Optimization is an automated prompt engineering pipeline that iteratively optimizes prompt templates against historical resolution quality metrics. Using DSPy's compiler, the system takes a defined prompt signature (input/output specification), runs it against a dataset of past tickets with known outcomes, applies optimization strategies (e.g., few-shot selection, instruction refinement), and produces an improved prompt that is A/B tested against the current production prompt before promotion.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `POST /api/ai/optimize/start` | POST | `{prompt_id, dataset_range, optimization_strategy, max_iterations}` | `{optimization_run_id, status: running, estimated_duration_min}` |
| `GET /api/ai/optimize/{run_id}` | GET | — | `{status, current_iteration, max_iterations, best_score, current_prompt, baseline_score}` |
| `POST /api/ai/optimize/{run_id}/promote` | POST | `{confirm: true}` | Promotes the best prompt to production. Returns `{production_prompt_id, previous_prompt_id}` |
| `GET /api/ai/optimize/history` | GET | `?prompt_id={id}` | History of optimization runs with scores and outcomes |

## DB Tables

- **`prompt_templates`** — `id, company_id, prompt_name, intent_type, prompt_text, version, is_production, created_at`
  - Unique: `(company_id, prompt_name, version)`
- **`optimization_runs`** — `id, company_id, prompt_template_id, strategy (few_shot\|instruction_refine\|cot_chain), status (running\|completed\|failed\|promoted), baseline_score, best_score, best_prompt_text, iterations_completed, max_iterations, dataset_size, started_at, completed_at`
- **`optimization_iterations`** — `id, optimization_run_id, iteration_number, prompt_text, score, metrics (JSONB — accuracy, latency, token_usage), created_at`
- **`prompt_ab_tests`** — `id, company_id, prompt_a_id, prompt_b_id, traffic_split, metric_a, metric_b, winner, started_at, ended_at`

## BC Rules

- **BC-007** (AI Model Interaction): Optimization runs use the Smart Router for LLM calls during evaluation. PII redacted from all evaluation data. Model selection for optimization respects tier configuration.
- **BC-004** (Background Jobs): Optimization runs as a Celery task with `max_retries=3`, exponential backoff, `soft_time_limit=1800` (30 min). `company_id` is first parameter. Task logged in `task_logs`.
- **BC-001** (Multi-Tenant Isolation): Prompts, optimization runs, and A/B tests are per-tenant. One tenant's optimized prompt never affects another tenant.
- **BC-012** (Error Handling & Resilience): If optimization run times out or fails, it is marked as `failed` with error details. The current production prompt remains unchanged. No partial promotion.

## Edge Cases

1. **Insufficient training data (<100 resolved tickets)** — Optimization cannot start. Returns error "Minimum 100 resolved tickets required for optimization." Admin directed to collect more data.
2. **Optimized prompt scores worse than baseline** — Run completes but best_score < baseline_score. Promotion is blocked. Admin sees comparison but cannot promote a worse prompt. System recommends trying a different strategy.
3. **Optimization run during active A/B test for same prompt** — New run is queued. Cannot run two optimizations for the same prompt simultaneously. Returns "Optimization already in progress."
4. **Promoted prompt causes guardrails block rate increase** — A/B test monitors guardrails block rate. If block rate increases > 5% vs baseline, auto-rollback to previous prompt triggered within 1 hour.

## Acceptance

1. Given a prompt template with 500 historical resolved tickets, When an optimization run starts with strategy=few_shot and max_iterations=10, Then the system completes 10 iterations within 30 minutes and returns the best-scoring prompt variant.
2. Given an optimization run completes with best_score (87%) > baseline_score (78%), When the admin promotes the prompt, Then the new prompt becomes `is_production=true` and the previous prompt is archived with `is_production=false`.
3. Given an optimization run fails at iteration 3 due to LLM timeout, When the failure occurs, Then the run is marked as `failed` with the error details, the current production prompt remains unchanged, and a Celery retry is attempted.
4. Given a promoted prompt is A/B tested against the previous version, When the guardrails block rate increases by 6% for the new prompt, Then auto-rollback is triggered and the previous prompt is restored as production.

---

# F-062: Sentiment Analysis (Empathy Engine)

## Overview

The Empathy Engine performs real-time sentiment detection on every customer message, scoring frustration levels on a 0-100 scale (0=calm, 100=extremely frustrated) and categorizing tone (angry, sad, anxious, neutral, positive). These scores drive dynamic AI tone adjustment (more empathetic language for frustrated customers), trigger escalation to human agents when frustration exceeds a threshold, and power customer satisfaction analytics. The engine uses the Smart Router's Light tier for low-latency scoring on every message.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `POST /api/internal/sentiment` | POST | `{message_text, ticket_id, customer_id}` | `{sentiment_score (0-100), tone, frustration_level (low\|medium\|high\|critical), confidence, model_used}` |
| `GET /api/tickets/{id}/sentiment-timeline` | GET | — | `{messages: [{message_id, sentiment_score, tone, created_at}], trend: increasing\|stable\|decreasing}` |
| `GET /api/sentiment/summary` | GET | `?range={7d\|30d}` | `{avg_sentiment, frustrated_tickets_count, escalation_rate_by_sentiment, top_frustration_topics}` |

## DB Tables

- **`message_sentiments`** — `id, company_id, message_id (FK → ticket_messages.id), ticket_id, customer_id, sentiment_score (INTEGER 0-100), tone (VARCHAR 20), frustration_level (VARCHAR 10), confidence (DECIMAL 5,2), model_id, created_at`
  - Indexes: `idx_ms_ticket (ticket_id)`, `idx_ms_score (company_id, sentiment_score)`, `idx_ms_customer (customer_id, created_at DESC)`
- **`sentiment_thresholds`** — `id, company_id, escalation_threshold (INTEGER, default 80), tone_adjust_threshold (INTEGER, default 50), alert_threshold (INTEGER, default 90)` — per-company config (BC-007 Rule 9)
- **`sentiment_escalations`** — `id, company_id, ticket_id, message_id, sentiment_score, escalation_action, created_at`

## BC Rules

- **BC-007** (AI Model Interaction): Uses Smart Router Light tier. PII redacted before LLM call. Sentiment thresholds stored per-company in database (not hardcoded) per BC-007 Rule 9. If model fails, default to neutral sentiment.
- **BC-005** (Real-Time Communication): Critical sentiment spikes (score ≥ escalation threshold) emitted via Socket.io to supervisors in real-time. Urgent Attention Panel (F-080) updated immediately.
- **BC-004** (Background Jobs): Sentiment scoring for high-volume messages queued via Celery. `company_id` first parameter. Non-blocking to message ingestion pipeline.
- **BC-001** (Multi-Tenant Isolation): Sentiment data, thresholds, and escalation rules are per-tenant.

## Edge Cases

1. **Customer frustration rapidly increases across 3 messages (30→60→95)** — Each message scored independently. Trend detected by `sentiment-timeline` endpoint. At score 95, immediate escalation emitted via Socket.io. Ticket flagged in F-080 Urgent Attention Panel.
2. **Sentiment model returns timeout** — Default to `sentiment_score=50, tone=neutral, confidence=0`. Message processing continues. No ticket blocked due to sentiment failure. Logged for model health monitoring.
3. **Sarcastic message ("Oh great, another error")** — Sentiment model trained to detect sarcasm as negative. If confidence low, frustration_level set to `medium` as conservative default. Misclassifications correctable via training feedback.
4. **Customer uses all-caps but is not actually angry ("THANK YOU SO MUCH")** — Positive words override capitalization signal. Score remains low. Model uses semantic analysis, not heuristic rules like caps-lock detection alone.

## Acceptance

1. Given a customer message "This is the third time I've been charged incorrectly!", When sentiment is scored, Then `sentiment_score ≥ 70`, `tone=angry`, and `frustration_level=high` with confidence ≥ 60%.
2. Given a company's escalation threshold is 80 and a customer message scores 85, When the sentiment is processed, Then a real-time escalation alert is emitted via Socket.io to all supervisors and the ticket is flagged for priority review.
3. Given the LLM model for sentiment analysis times out, When the fallback activates, Then the message is assigned `sentiment_score=50, tone=neutral` and the ticket processing continues without delay.
4. Given 5 messages in a ticket with scores [20, 30, 45, 65, 80], When the sentiment timeline is requested, Then the trend is reported as `increasing` and the escalation threshold alert history is visible.

---

# F-065: Auto-Response Generation

## Overview

Auto-Response Generation is the end-to-end pipeline that produces brand-aligned customer responses automatically by combining intent classification (F-049), RAG retrieval from the knowledge base (F-064), sentiment-aware tone adjustment (F-062), and template generation through the Smart Router's Medium tier. When confidence is high and guardrails pass, the response is delivered directly to the customer; when confidence is below threshold, the response is routed to the AI Draft Composer (F-066) for human review before sending.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `POST /api/internal/auto-respond` | POST | `{ticket_id, message_id}` | Internal pipeline trigger. Returns `{response_text, confidence, guardrails_passed, delivery_method (auto\|draft), model_used, rag_sources}` |
| `POST /api/tickets/{id}/auto-response/regenerate` | POST | `{reason: different_tone\|more_detail\|simpler}` | Regenerates response with adjusted parameters. Returns new draft. |

## DB Tables

- **`auto_responses`** — `id, company_id, ticket_id, message_id, response_text, intent_used, sentiment_score, confidence (DECIMAL 5,2), rag_sources (JSONB — [{chunk_id, relevance_score, content_preview}]), guardrails_result (JSONB), delivery_method (auto\|draft), model_id, delivered_at, created_at`
  - Indexes: `idx_ar_ticket (ticket_id)`, `idx_ar_company_confidence (company_id, confidence)`
- **`auto_response_audit`** — `id, company_id, auto_response_id, action (generated\|delivered\|blocked\|edited\|dismissed), actor_type (ai\|human), details (JSONB), created_at`

## BC Rules

- **BC-007** (AI Model Interaction): Full Smart Router pipeline: PII redaction → RAG retrieval → Medium-tier LLM generation → Guardrails check → PII redaction of output. If Guardrails blocks, safe fallback template sent and blocked response queued per F-058. Invalid JSON retry with simplified prompt (BC-007 Rule 8).
- **BC-006** (Email Communication): Auto-delivered responses sent via Brevo templates. Email loop detection (OOO headers, 5-per-24h limit) checked before sending. Rate limiting enforced (5 emails/customer/hour).
- **BC-009** (Approval Workflow): Responses below confidence threshold routed as drafts to F-066 (human review) instead of auto-delivered. This is the human-in-the-loop gate.
- **BC-005** (Real-Time Communication): Auto-response delivery emitted via Socket.io. Draft creation notified to assigned agent. Customer typing indicator suppressed while response generates.

## Edge Cases

1. **RAG retrieval returns zero relevant results** — Response generated without KB context but flagged with `rag_sources=[]` and lower confidence. If confidence drops below threshold, routed as draft. Response explicitly states general information only.
2. **Guardrails blocks auto-response** — Safe fallback template sent to customer immediately. Blocked response logged in F-057/F-058 queue for admin review. Customer never sees the blocked content.
3. **Customer sends 3 messages in rapid succession** — Pipeline processes messages sequentially per ticket. First message gets full auto-response. Second and third are debounced — if context is similar, a single consolidated response is generated.
4. **Auto-response for voice channel** — Response text is converted to speech via TTS before delivery. Text is logged in `ticket_messages` with `channel=voice`. Guardrails check applies to text before TTS conversion.

## Acceptance

1. Given a ticket with high-confidence intent classification (≥ 85%) and relevant RAG results, When auto-response generation runs, Then a brand-aligned response is delivered to the customer within 5 seconds via the original channel.
2. Given a ticket with medium confidence classification (55-84%), When auto-response is generated, Then the response is NOT auto-delivered but instead saved as a draft in the AI Draft Composer (F-066) for the assigned agent to review and send.
3. Given RAG retrieval finds 3 relevant knowledge base chunks, When the response is generated, Then the `rag_sources` array contains all 3 sources with their relevance scores and the response references the information accurately.
4. Given a Guardrails check blocks the generated response, When the block occurs, Then a safe fallback template is immediately sent to the customer and the blocked response is queued in F-058 for admin review.

---

# F-066: AI Draft Composer (Co-Pilot Mode)

## Overview

The AI Draft Composer provides human agents with AI-generated response drafts in real-time that they can accept as-is, edit before sending, or regenerate with different parameters (tone, detail level, language). It activates when auto-response confidence is below the auto-delivery threshold (routing from F-065) or when agents manually request a draft. The composer surface is embedded inline in the ticket detail view (F-047) and uses streaming via Socket.io to show the draft being generated character-by-character for immediate agent productivity.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `POST /api/tickets/{id}/draft/generate` | POST | `{tone: empathetic\|professional\|casual, detail: brief\|detailed, language: auto\|en\|es}` | `{draft_id, response_text, confidence, rag_sources, generation_time_ms}` |
| `POST /api/tickets/{id}/draft/{draft_id}/accept` | POST | `{edited_text?}` | Sends the draft (original or edited) to customer. Returns `{sent: true, channel, delivery_id}` |
| `POST /api/tickets/{id}/draft/{draft_id}/regenerate` | POST | `{adjustment_reason}` | Generates alternative draft. Returns new `{draft_id, response_text}`. |
| `Socket.io: draft:stream` | Listen | `tenant_{company_id}` | Streams draft tokens as they are generated (real-time typing effect) |

## DB Tables

- **`response_drafts`** — `id, company_id, ticket_id, message_id, draft_text, tone_used, detail_level, language, confidence, rag_sources (JSONB), model_id, status (pending\|accepted\|dismissed\|expired), edited_text, accepted_by (FK → users.id), sent_at, created_at, expires_at`
  - Indexes: `idx_rd_ticket (ticket_id, created_at DESC)`, `idx_rd_status (company_id, status)`
- **`draft_feedback`** — `id, company_id, draft_id, was_edited (BOOLEAN), edit_distance (INTEGER), time_to_accept_sec, agent_id, created_at` — tracks draft quality for prompt optimization (F-061)

## BC Rules

- **BC-007** (AI Model Interaction): Draft generation uses Smart Router Medium tier. PII redacted before LLM call and before DB store. Guardrails check on generated draft. If Guardrails blocks, agent sees "Draft blocked by safety filter" with reason — no draft sent.
- **BC-006** (Email Communication): When agent accepts/sends a draft, it follows outbound email rules: Brevo template, rate limiting (5/customer/hour), loop detection.
- **BC-005** (Real-Time Communication): Draft generation streamed via Socket.io `draft:stream` event for real-time typing effect. Agent sees the draft appear incrementally without waiting for full generation.
- **BC-001** (Multi-Tenant Isolation): Drafts scoped by `company_id`. An agent cannot see drafts from another tenant's tickets.

## Edge Cases

1. **Agent requests draft while another draft is still generating** — Cancel previous draft generation, start new one. Previous draft marked as `expired`. Agent notified of regeneration.
2. **Agent edits 80% of the draft before sending** — Full edit tracked. `draft_feedback.was_edited=true`, `edit_distance` calculated. High edit distance on a specific intent triggers prompt optimization review (F-061).
3. **Draft expires (not accepted within 30 minutes)** — Draft status set to `expired`. Agent can regenerate. Expired drafts retained for 7 days for analytics, then deleted per BC-010.
4. **No RAG sources available for draft generation** — Draft generated without KB context. Draft prefixed with system note: "Note: No knowledge base articles matched. Verify accuracy before sending." Confidence score reduced.

## Acceptance

1. Given an agent clicks "Generate Draft" on a ticket, When the draft generates, Then the agent sees the draft text appearing in real-time via Socket.io streaming within 3 seconds and the draft is labeled with its confidence score and RAG sources.
2. Given an agent edits a draft and clicks "Send", When the send action executes, Then the edited text is delivered to the customer via the original channel and the original draft and edited version are both stored for audit.
3. Given a draft is generated but the Guardrails check blocks it, When the agent views the draft area, Then they see "Draft blocked by safety filter" with the specific blocking reason and the option to regenerate.
4. Given a draft is not accepted within 30 minutes, When the expiry triggers, Then the draft status changes to `expired` and the agent is prompted to regenerate if they still need a response.

---

# F-068: Context Health Meter

## Overview

The Context Health Meter is a real-time visual indicator embedded in the ticket detail view (F-047) that shows the quality and completeness of the conversation context available to the AI. It computes a composite health score (0-100) based on retrieval relevance (RAG match quality), context freshness (time since last significant update), context completeness (missing customer/order info), and token utilization (how close to the context window limit). When health degrades, the meter turns yellow/red and suggests specific remediation actions.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `GET /api/tickets/{id}/context-health` | GET | — | `{health_score (0-100), status (healthy\|degraded\|critical), components: {relevance, freshness, completeness, token_utilization}, recommendations: [{action, reason}], context_window_used_pct}` |
| `Socket.io: context:health:update` | Listen | `tenant_{company_id}` | Real-time health score updates as conversation progresses |

## DB Tables

- **`context_health_snapshots`** — `id, company_id, ticket_id, health_score, relevance_score, freshness_score, completeness_score, token_utilization_pct, context_window_tokens, max_context_tokens, status (healthy\|degraded\|critical), recommendations (JSONB), created_at`
  - Index: `idx_chs_ticket_created (ticket_id, created_at DESC)`
- **`context_warnings`** — `id, company_id, ticket_id, warning_type (stale_context\|low_relevance\|high_token_usage\|missing_info), severity, dismissed, dismissed_by, created_at`

## BC Rules

- **BC-008** (State Management): Context health is part of the GSD state for each ticket. Updated on every message in the conversation. State persisted to both Redis (primary) and PostgreSQL (fallback) per BC-008.
- **BC-005** (Real-Time Communication): Health score updates emitted via Socket.io to the ticket detail view. Agent sees the meter change in real-time as new messages are added. Changes trigger visual transitions (green→yellow→red).
- **BC-007** (AI Model Interaction): Token utilization calculated from the Smart Router's context window tracking. RAG relevance scores come from the vector search (F-064) cosine similarity.
- **BC-001** (Multi-Tenant Isolation): Context health data scoped by `company_id`. Token limits and context windows are per-tenant configuration.

## Edge Cases

1. **Token utilization reaches 85%** — Health score drops below 50 (critical). Context Compression Trigger (F-067) activated automatically. Agent sees "Context nearly full — compression recommended" warning.
2. **RAG returns low relevance results (all < 0.3 cosine similarity)** — Relevance component scores low. Health meter shows yellow. Recommendation: "No relevant knowledge base articles found. Consider providing manual context."
3. **Customer info missing (no email, no order ID in context)** — Completeness component scores low. Recommendation: "Customer identity partially resolved. Link customer account for better responses." Links to F-070.
4. **Rapid conversation (20 messages in 5 minutes)** — Freshness stays high but token utilization climbs fast. Health meter transitions from green to yellow to red. 90% Capacity Popup (F-069) triggered.

## Acceptance

1. Given a ticket with 5 messages and recent RAG results with relevance > 0.8, When context health is calculated, Then the health score is ≥ 75 (healthy) and the meter displays green.
2. Given a ticket where all RAG results have relevance < 0.3, When context health is updated, Then the health score drops below 50 (degraded), the meter shows yellow, and a recommendation to provide manual context is displayed.
3. Given token utilization reaches 88% of the context window, When the health score is computed, Then the status is `critical`, the meter shows red, and the Context Compression Trigger (F-067) is recommended.
4. Given an agent dismisses a context health warning, When the dismissal is recorded, Then the warning is marked as `dismissed` for that agent but reappears if health further degrades.

---

# F-069: 90% Capacity Popup (New Chat Trigger)

## Overview

The 90% Capacity Popup is a proactive UI notification that appears when a conversation's AI context utilization reaches 90% of the model's context window, prompting the agent to start a fresh thread for new topics to maintain AI response quality. The popup explains why context is limited, offers a one-click "Start New Thread" action that preserves customer identity and links the new thread to the parent ticket, and can be snoozed for 5 minutes if the agent needs to finish the current exchange.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `POST /api/tickets/{id}/split-thread` | POST | `{reason: context_capacity, link_to_parent: true}` | Creates new ticket linked to parent. Returns `{new_ticket_id, parent_ticket_id}` |
| `POST /api/tickets/{id}/capacity-popup/snooze` | POST | `{snooze_minutes: 5}` | Suppresses popup for specified duration. Returns `{snoozed_until}` |
| `GET /api/tickets/{id}/context-usage` | GET | — | `{tokens_used, tokens_max, usage_pct, estimated_remaining_turns}` |

## DB Tables

- **`ticket_threads`** — `id, company_id, parent_ticket_id (FK → tickets.id, nullable), customer_id, channel, status, context_tokens_at_close, created_at`
  - Index: `idx_tt_parent (parent_ticket_id)`, `idx_tt_customer (customer_id, created_at DESC)`
- **`capacity_popup_dismissals`** — `id, company_id, ticket_id, user_id, action (started_new\|snoozed\|dismissed), snoozed_until, created_at`

## BC Rules

- **BC-008** (State Management): Context capacity is tracked as part of the GSD state. The 90% threshold triggers a state transition that emits the popup event. Thread splitting preserves state continuity via parent-child relationship.
- **BC-005** (Real-Time Communication): Popup triggered via Socket.io event `ticket:capacity_warning`. The event carries the exact token count and estimated remaining turns. No polling required.
- **BC-001** (Multi-Tenant Isolation): Context limits and capacity thresholds are per-tenant. Thread splitting creates child tickets within the same tenant.

## Edge Cases

1. **Popup dismissed 3 times in a row** — After 3 dismissals, popup becomes persistent (cannot be snoozed). System note added to ticket: "Context capacity critically high. Please start a new thread."
2. **Agent starts new thread but customer continues on old thread** — Incoming message on old thread triggers a system note: "This thread has reached context capacity. Response quality may be degraded." Links to the new thread.
3. **Split thread immediately receives a related message** — Customer identity preserved in new thread (F-070). New thread's context starts fresh with customer profile and link to parent thread summary.
4. **Context usage jumps from 70% to 95% in one message** — Popup appears immediately at 95% (not waiting for exactly 90%). System auto-compresses context (F-067) and triggers popup simultaneously.

## Acceptance

1. Given a ticket's context utilization reaches 90%, When the threshold is crossed, Then the 90% Capacity Popup appears in the agent's UI within 2 seconds showing the current token usage and a "Start New Thread" button.
2. Given the agent clicks "Start New Thread", When the thread split completes, Then a new ticket is created with the same customer and channel, linked to the parent ticket, and the agent is navigated to the new ticket's detail view.
3. Given the agent clicks "Snooze for 5 minutes", When the snooze is active, Then the popup is hidden for 5 minutes. If context usage exceeds 95% during snooze, the popup reappears regardless of snooze.
4. Given a new thread is created from a split, When the customer sends a new message, Then the message is routed to the new thread (not the old one) based on the customer identity linkage.

---

# F-070: Customer Identity Resolution

## Overview

Customer Identity Resolution unifies customer identities across email, chat, phone, and social channels by matching on email address, phone number, account ID, and behavioral signals (device fingerprint, session cookies). When a new interaction arrives from any channel, the resolution engine searches for existing customer records using a multi-signal matching algorithm with configurable confidence thresholds, and either links the interaction to an existing customer profile or creates a new one. This ensures the omnichannel experience (F-052) and provides a complete customer history regardless of entry channel.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `POST /api/internal/identity/resolve` | POST | `{signals: {email, phone, account_id, device_fingerprint, social_handle, session_cookie}}` | `{customer_id, match_type (exact\|probable\|new), confidence, matched_signals: [], existing_channels: []}` |
| `POST /api/customers/{id}/merge` | POST | `{source_customer_id, merge_strategy: keep_latest\|keep_all}` | Merges two customer records. Returns `{merged_customer_id, merged_channel_count}` |
| `GET /api/customers/{id}/identity-graph` | GET | — | `{customer: {}, channels: [], linked_tickets: [], unresolved_matches: [], confidence_scores: {}}` |

## DB Tables

- **`customers`** — `id, company_id, full_name, email, phone, account_id, device_fingerprint_hash, is_merged, merged_into_id (FK → customers.id), created_at, updated_at`
  - Indexes: `idx_c_company_email (company_id, email)`, `idx_c_company_phone (company_id, phone)`, `idx_c_company_account (company_id, account_id)`
- **`customer_channels`** — `id, company_id, customer_id, channel_type, external_id, is_verified, verification_method, first_seen_at, last_seen_at`
  - Unique: `(company_id, channel_type, external_id)`
- **`identity_match_log`** — `id, company_id, input_signals (JSONB), matched_customer_id (nullable), match_type (exact\|probable\|none), confidence, signals_matched (TEXT[]), created_at`
- **`customer_merge_audit`** — `id, company_id, source_customer_id, target_customer_id, merged_by, merge_strategy, field_mappings (JSONB), created_at`

## BC Rules

- **BC-007** (AI Model Interaction): Probabilistic matching uses Light-tier LLM to evaluate ambiguous matches (e.g., same name + similar email domain but different address). Confidence thresholds stored per-company (BC-007 Rule 9).
- **BC-010** (Data Lifecycle & Compliance): Customer PII (email, phone, name) encrypted at rest. Device fingerprints hashed (never stored in plaintext). Customer records subject to GDPR right-to-erasure requests — merge history preserved but PII purged.
- **BC-001** (Multi-Tenant Isolation): Customer records are per-tenant. Identity resolution never matches customers across tenants. Each tenant's customer graph is fully isolated.
- **BC-011** (Authentication & Security): Customer merge operation requires supervisor+ role. Merge is audit-logged with before/after state. Merge can be reversed within 24 hours.

## Edge Cases

1. **Two customers share the same email (e.g., shared family email)** — System creates separate customer records with a `probable` match flagged. Supervisor reviews and confirms they are separate individuals or merges.
2. **Customer uses different emails across channels (gmail for chat, work email for support)** — Probabilistic matching correlates via phone number or device fingerprint. If confidence ≥ 80%, auto-linked. Otherwise flagged for review.
3. **Merge operation reversibility** — Within 24 hours of merge, supervisor can reverse. Original records restored from merge audit log. After 24 hours, merge is permanent but PII still erasable per GDPR.
4. **Bulk identity resolution on data import** — Large customer lists imported during onboarding (F-030) processed via Celery batch. Each record resolved independently. `company_id` first parameter. Batch results logged with match/creation counts.

## Acceptance

1. Given a new SMS arrives from phone number +15551234567 and an existing customer has the same phone number, When identity resolution runs, Then the SMS is linked to the existing customer with `match_type=exact` and `confidence=1.0`.
2. Given a chat message from "john.d@gmail.com" and an existing customer has "john.doe@gmail.com" with the same device fingerprint, When probabilistic matching evaluates, Then the match is `probable` with confidence ≥ 70% and the interaction is auto-linked.
3. Given a supervisor merges two customer records, When the merge completes, Then all channels, tickets, and interaction history from both records are consolidated under the target customer and the merge is audit-logged with full field mappings.
4. Given a GDPR erasure request for a customer, When the erasure executes, Then all PII fields (email, phone, name) are purged, the customer record is anonymized, but the merge audit log retains the record IDs (without PII) for data integrity.
