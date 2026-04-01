# PARWA Feature Specs — Batch 4

> **Jarvis / Communications / Resilience / Training / Integrations**
>
> Features: F-087, F-093, F-104, F-105, F-120, F-121, F-131, F-139
>
> Generated: July 2025 | Version 1.0

---

## Table of Contents

1. [F-087: Jarvis Chat Panel (Natural Language Commands)](#f-087-jarvis-chat-panel-natural-language-commands)
2. [F-093: Proactive Self-Healing](#f-093-proactive-self-healing)
3. [F-104: Model Validation (Post-Training)](#f-104-model-validation-post-training)
4. [F-105: Model Deployment with Auto-Rollback](#f-105-model-deployment-with-auto-rollback)
5. [F-120: Email Handling (Outbound via Brevo)](#f-120-email-handling-outbound-via-brevo)
6. [F-121: Inbound Email Parsing (Brevo Parse Webhook)](#f-121-inbound-email-parsing-brevo-parse-webhook)
7. [F-131: Pre-built Connectors](#f-131-pre-built-connectors)
8. [F-139: Circuit Breaker](#f-139-circuit-breaker)

---

# F-087: Jarvis Chat Panel (Natural Language Commands)

## Overview

Jarvis is the natural-language command layer that turns PARWA's multi-system complexity into a conversational interface. Operators type plain-English commands like "show refund tickets from last week," "pause email channel," or "create a returns agent" and Jarvis translates them into API calls across ticket management, approval workflows, agent provisioning, and system controls. It eliminates the need to navigate multiple UI panels and makes the platform controllable by non-technical supervisors through conversation alone.

## User Journey / System Flow

1. **User opens Jarvis** — The floating chat panel opens from any page in the dashboard. Socket.io establishes a real-time connection to the tenant-scoped `tenant_{company_id}` room.
2. **User types a command** — The frontend sends the raw text via Socket.io emit (`jarvis:command`) to the backend. The message is stored in the `event_buffer` table per BC-005.
3. **Command parsing** — The backend NLU layer (Light-tier LLM via Smart Router) classifies the intent and extracts parameters:
   - **Query intent**: "show tickets with status refund" → `ticket_list(filters={status: "refund"})`
   - **Action intent**: "pause email channel" → `channel_pause(channel="email")`
   - **Creation intent**: "create returns agent" → triggers guided agent creation flow (F-095)
   - **System intent**: "what's the system health?" → queries F-088 System Status Panel
   - **Unknown intent**: "why is the sky blue?" → responds with clarification prompt
4. **Permission check** — Jarvis verifies the user's role and permissions against the extracted action. Financial actions require supervisor+ role (BC-011). Destructive actions trigger a confirmation prompt before execution.
5. **Execution** — The parsed command is dispatched to the appropriate internal service. Results stream back via Socket.io as structured cards (tables, status badges, links).
6. **Response rendering** — The frontend renders Jarvis responses as rich cards: ticket lists as filterable tables, system status as health badges, confirmation prompts as action buttons with Jarvis consequence preview (F-077/F-078).
7. **Command history** — All commands and responses are logged to `jarvis_command_log` for audit and training.

### Supported Command Patterns

| Category | Example Commands | Mapped Action |
|----------|-----------------|---------------|
| **Ticket Queries** | "show refund tickets from last week", "how many open tickets?", "find tickets for john@example.com" | Ticket list filtering (F-046), search (F-048) |
| **Channel Control** | "pause email", "resume chat", "pause all channels" | Emergency pause (F-083), channel toggle |
| **Agent Management** | "create a returns agent", "show agent performance", "pause billing agent" | Agent creation (F-095), metrics (F-098) |
| **Approval Actions** | "show pending approvals", "approve ticket TKT-123", "reject all refund requests" | Approval queue (F-074), individual approve/reject (F-076) |
| **System Status** | "system health", "show last 5 errors", "is LLM working?" | System status (F-088), last errors (F-091) |
| **Reporting** | "export CSAT report for June", "show resolution rate trend" | Report generation (Celery task), metrics (F-038) |
| **Auto-Handle Rules** | "enable auto-approve for refunds under $50", "show active auto-handle rules" | Auto-handle rules (F-077), consequence display (F-078) |
| **GSD Debugging** | "show state for ticket TKT-456", "what step is ticket TKT-456 on?" | GSD State Terminal (F-089) |

## API Endpoints

### Internal Service Interfaces (called by Jarvis command parser)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jarvis/command` | POST (Socket.io) | Receives NL command, returns parsed intent + response |
| `/api/jarvis/history` | GET | Paginated command history for current user |
| `/api/jarvis/suggestions` | GET | Returns contextual command suggestions based on current page |
| `/api/jarvis/confirm` | POST | Confirms a pending destructive action after consequence preview |

**Socket.io Events:**
- `jarvis:command` (emit) — User sends command
- `jarvis:response` (listen) — Streaming response with rich card payload
- `jarvis:typing` (listen) — Typing indicator while NLU processes

## Database Tables

### `jarvis_command_log`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid_generate_v4() | Unique command ID |
| company_id | UUID | FK → companies.id, NOT NULL, indexed | Tenant isolation (BC-001) |
| user_id | UUID | FK → users.id, NOT NULL | Who issued the command |
| raw_input | TEXT | NOT NULL | Original NL text from user |
| parsed_intent | VARCHAR(100) | NOT NULL | Classified intent category |
| parsed_params | JSONB | NULLABLE | Extracted parameters as key-value pairs |
| action_taken | VARCHAR(255) | NULLABLE | What API/service was called |
| response_summary | TEXT | NULLABLE | Summary of the response returned |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'success' | success, error, confirmation_required, unknown_intent |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Command timestamp |
| duration_ms | INTEGER | NULLABLE | Processing time in milliseconds |

**Indexes:** `idx_jcl_company_created (company_id, created_at DESC)`, `idx_jcl_user (user_id, created_at DESC)`

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `JARVIS_LLM_TIER` | `light` | Which LLM tier to use for intent parsing |
| `JARVIS_MAX_CONTEXT_MESSAGES` | 20 | Number of recent messages kept for conversational context |
| `JARVIS_CONFIRMATION_THRESHOLD` | `destructive_actions` | Which action categories require confirmation before execution |
| `JARVIS_TYPING_INDICATOR_DELAY` | 500ms | Minimum time before showing typing indicator |
| `JARVIS_SESSION_TIMEOUT` | 30 minutes | Conversation context window before starting fresh |
| `JARVIS_RATE_LIMIT_PER_USER` | 60/minute | Maximum commands per user per minute |

## Building Codes Applied

- **BC-007 (AI Model Interaction):** Jarvis uses the Smart Router (Light tier) for intent classification. PII redaction occurs on all command input before LLM submission. Guardrails check all responses for safe content. Confidence thresholds stored per-company.
- **BC-005 (Real-Time Communication):** All Jarvis communication is via Socket.io in tenant-scoped rooms (`tenant_{company_id}`). Events are buffered in `event_buffer` for reconnection recovery. Graceful degradation: if Socket.io is unavailable, commands can be issued via REST POST to `/api/jarvis/command`.
- **BC-011 (Authentication & Security):** Every command verifies the user's role and permissions before execution. Financial actions require supervisor+ role. Command injection is prevented by strict parameter sanitization.
- **BC-001 (Multi-Tenant Isolation):** All command queries include `WHERE company_id = :tenant_id`. Command history is tenant-scoped.
- **BC-012 (Error Handling & Resilience):** If the LLM fails to parse intent, Jarvis falls back to keyword matching. If the target service is unavailable, Jarvis surfaces a clear error message with the system status. All errors logged to `jarvis_command_log` with status='error'.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Ambiguous command** ("show tickets") | Jarvis responds with clarifying prompts: "Do you mean open tickets, all tickets, or tickets from a specific date range?" |
| **LLM returns wrong intent** | Fallback to keyword-based matching. If both fail, respond with "I didn't understand that. Try rephrasing or use one of the quick commands." |
| **User references non-existent entity** ("approve ticket TKT-999") | Query returns null; Jarvis responds: "Ticket TKT-999 not found in your workspace." |
| **Concurrent conflicting commands** | "Pause email" and "Resume email" sent within 100ms — commands are serialized per company via Redis lock; last command wins with conflict notification to first user |
| **Very long command input** (>2000 chars) | Input is truncated at 2000 chars with notification to user. Prevents token budget exhaustion. |
| **Jarvis used during AI pause (F-083)** | System control commands still work (status checks, pause/resume). Ticket creation and AI-driven commands return "AI is currently paused" with link to resume. |
| **User without permissions issues command** | Returns "You don't have permission to perform this action. Contact your administrator." |

## Acceptance Criteria

1. Given a user types "show refund tickets from last week", When Jarvis parses the command, Then a filterable ticket list is returned showing only refund-status tickets from the past 7 days for the user's tenant.
2. Given a user types "pause email channel", When Jarvis confirms the action, Then the email channel is paused within 2 seconds and the response shows the updated channel status.
3. Given a user types a destructive command ("delete all closed tickets"), When Jarvis evaluates permissions, Then a consequence preview card is displayed requiring explicit confirmation before execution.
4. Given the LLM is rate-limited, When a user sends a Jarvis command, Then Jarvis falls back to keyword-based intent matching and still returns a valid response within 3 seconds.
5. Given a disconnected Socket.io client, When the user reconnects, Then all missed Jarvis responses are fetched via `/api/events/since` and rendered in order.
6. Given a user without supervisor role types "approve all pending", When Jarvis checks permissions, Then the response indicates insufficient permissions and no approval actions are executed.
7. Given 50 consecutive Jarvis commands from a single user within 1 minute, When the rate limit is reached, Then subsequent commands return HTTP 429 with "Slow down" messaging.

---

# F-093: Proactive Self-Healing

## Overview

Proactive Self-Healing is the infrastructure layer that monitors every external API call (LLM providers, Brevo, Twilio, Paddle, Shopify, etc.) for failures and automatically recovers without human intervention. When an API call fails, the system retries with exponential backoff, tries fallback providers or strategies, and only escalates to human operators when all recovery options are exhausted. Combined with the Trust Preservation Protocol (F-094), this ensures customers never see raw error messages — they see reassuring responses while the system heals in the background.

## User Journey / System Flow

1. **API call initiated** — Any service makes an external API call (e.g., sending an email via Brevo, calling an LLM via OpenRouter, fetching order data from Shopify).
2. **Failure detected** — The call returns a non-2xx status, times out, or throws a connection error. The failure is logged with full context (provider, endpoint, error message, tenant, request metadata).
3. **Retry with backoff** — The system immediately retries using exponential backoff: attempt 2 after 2s, attempt 3 after 4s, attempt 4 after 8s. Each retry uses the same idempotency key to prevent duplicate side effects.
4. **Fallback chain** — If all retries fail, the system tries the next provider in the fallback chain:
   - **LLM calls:** Next model in same tier → next tier → queue for later processing
   - **Email sends:** Brevo primary → Brevo backup API key → queue for Celery retry with 5-minute delay
   - **Shopify API:** Retry with exponential backoff → use cached data if available → surface stale-but-safe response
   - **Paddle API:** Retry → mark as pending → alert billing team
5. **Circuit breaker check** — If the same provider has failed 5 times in the last 60 seconds, the circuit breaker (F-139) trips to OPEN state, preventing further calls until cooldown.
6. **Trust Preservation** — If all recovery fails, the Trust Preservation Protocol (F-094) activates: the customer receives a reassuring message ("We're processing your request, please hold") while the action is queued for background retry.
7. **Human escalation** — If the action remains unresolved after 15 minutes of background retry, an alert is sent to the operations team via Slack webhook and email with full error context, affected tenant/ticket, and a one-click retry button.

### Retry Strategy Details

| Provider Type | Max Retries | Backoff Strategy | Fallback Chain |
|---------------|-------------|------------------|----------------|
| **LLM (OpenRouter)** | 3 | 2s, 4s, 8s | Same tier next model → next tier → queue |
| **Brevo (Email)** | 3 | 2s, 4s, 8s | Brevo backup key → Celery delayed retry (5min) |
| **Twilio (SMS/Voice)** | 3 | 5s, 15s, 45s | Twilio backup → queue → alert |
| **Paddle (Billing)** | 3 | 2s, 4s, 8s | Queue → alert billing team immediately |
| **Shopify / TMS / WMS** | 3 | 5s, 15s, 45s | Cached data → queue → alert |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /api/internal/retry` | POST | Internal endpoint to manually trigger a retry for a failed action |
| `GET /api/internal/healing/status` | GET | Returns current self-healing metrics: active retries, queued actions, escalation count |
| `GET /api/internal/healing/history` | GET | Paginated history of self-healing events with outcomes |

## Database Tables

### `healing_events`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid_generate_v4() | Unique event ID |
| company_id | UUID | FK → companies.id, NOT NULL, indexed | Tenant (BC-001) |
| provider | VARCHAR(50) | NOT NULL | External provider name (brevo, openrouter, shopify, etc.) |
| endpoint | VARCHAR(255) | NOT NULL | API endpoint called |
| request_payload | JSONB | NOT NULL | Original request (with PII redacted) |
| error_type | VARCHAR(50) | NOT NULL | timeout, rate_limit, 5xx, connection_error, auth_error |
| error_message | TEXT | NOT NULL | Full error details |
| retry_count | INTEGER | NOT NULL, DEFAULT 0 | Number of retry attempts so far |
| max_retries | INTEGER | NOT NULL, DEFAULT 3 | Maximum allowed retries |
| fallback_used | VARCHAR(100) | NULLABLE | Which fallback strategy was applied |
| final_status | VARCHAR(20) | NOT NULL, DEFAULT 'retrying' | retrying, recovered, queued, escalated, failed |
| related_ticket_id | UUID | FK → tickets.id, NULLABLE | If the failure is tied to a ticket |
| related_entity_type | VARCHAR(50) | NULLABLE | ticket, email, agent, billing |
| related_entity_id | UUID | NULLABLE | ID of the related entity |
| resolved_at | TIMESTAMPTZ | NULLABLE | When the issue was resolved |
| escalated_at | TIMESTAMPTZ | NULLABLE | When human escalation occurred |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | First failure timestamp |

**Indexes:** `idx_he_company_status (company_id, final_status)`, `idx_he_provider_created (provider, created_at DESC)`, `idx_he_ticket (related_ticket_id)`

### `healing_alerts`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique alert ID |
| company_id | UUID | FK → companies.id, NOT NULL | Tenant |
| healing_event_id | UUID | FK → healing_events.id, NOT NULL | Related healing event |
| alert_channel | VARCHAR(20) | NOT NULL | slack, email, dashboard |
| alert_payload | JSONB | NOT NULL | Alert content sent to operator |
| acknowledged | BOOLEAN | NOT NULL, DEFAULT false | Whether an operator acknowledged |
| acknowledged_by | UUID | FK → users.id, NULLABLE | Who acknowledged |
| acknowledged_at | TIMESTAMPTZ | NULLABLE | When acknowledged |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Alert timestamp |

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SELF_HEAL_MAX_RETRIES` | 3 | Global default max retries per failure |
| `SELF_HEAL_BACKOFF_BASE` | 2 | Exponential backoff base in seconds (2^n) |
| `SELF_HEAL_QUEUE_TIMEOUT` | 15 min | Time before queued actions are escalated to humans |
| `SELF_HEAL_CIRCUIT_BREAKER_THRESHOLD` | 5 failures / 60s | Failures needed to trip circuit breaker |
| `SELF_HEAL_ALERT_CHANNELS` | `["slack", "email"]` | Where to send escalation alerts |
| `SELF_HEAL_PII_REDACTION` | `true` | Whether to redact PII in stored error payloads |

## Building Codes Applied

- **BC-012 (Error Handling & Resilience):** Core building code for this feature. All failures are logged with context. Recovery is automatic before human escalation. No raw errors exposed to end users.
- **BC-004 (Background Jobs):** Retries and queued actions use Celery tasks with `max_retries=3`, exponential backoff, and DLQ routing. `company_id` is the first parameter in all healing Celery tasks.
- **BC-003 (Webhook Handling):** Incoming webhook failures (Paddle, Shopify, Twilio, Brevo) follow webhook processing rules — async processing, idempotency checks, retry with exponential backoff (60s, 300s, 900s).
- **BC-005 (Real-Time Communication):** Real-time healing status updates emitted via Socket.io to the Jarvis System Status Panel (F-088). Active healing events visible in real-time to operators.
- **BC-007 (AI Model Interaction):** LLM call failures follow Smart Router failover rules — try next model in tier, then next tier, then queue.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **All LLM providers down simultaneously** | Queue customer requests with "processing" message. Retry every 30 seconds. Escalate to ops team after 5 minutes. Trust Preservation Protocol shows reassuring message. |
| **Brevo completely unavailable** | Emails queue in Celery with 5-minute retry intervals. Dashboard shows "Email delivery delayed" banner. After 1 hour, alert ops team. |
| **Paddle webhook arrives but Paddle API is down** | Webhook is stored with `status=pending`. Processing retries per BC-003 (60s, 300s, 900s). Financial state remains unchanged until successful processing. |
| **Self-healing itself fails (Celery worker down)** | DLQ captures failed healing tasks. Redis AOF persistence preserves task metadata. On worker restart, recovery task hydrates from PostgreSQL. |
| **Multiple tenants affected by same provider outage** | Circuit breaker trips globally for that provider. All tenant requests use cached/fallback data. Single aggregated alert sent to ops team. |
| **Healing action has side effects (e.g., email sent then API fails later)** | All external actions use idempotency keys. Retries check idempotency before re-executing. No duplicate emails, charges, or ticket creations. |

## Acceptance Criteria

1. Given a Brevo API call returns 500, When self-healing activates, Then the system retries 3 times with exponential backoff (2s, 4s, 8s) before queuing the email for delayed Celery retry.
2. Given all OpenRouter LLM models return 429, When self-healing exhausts fallbacks, Then the customer request is queued, a reassuring "processing" message is displayed, and the request is retried every 30 seconds for up to 15 minutes.
3. Given the same provider fails 5 times within 60 seconds, When the circuit breaker evaluates, Then the circuit trips to OPEN state and no further calls are attempted until cooldown expires.
4. Given a queued healing action remains unresolved for 15 minutes, When the timeout triggers, Then an alert is sent to the operations team via Slack and email with full error context and a one-click retry button.
5. Given a Celery healing task fails all 3 retries, When the task routes to DLQ, Then a DLQ alert is emitted with task name, arguments, failure reason, and the healing event is marked as `escalated`.
6. Given a healing event is tied to a ticket, When the event is created, Then the `related_ticket_id` is populated and the ticket's detail view shows a "healing in progress" indicator.
7. Given a provider recovers after circuit breaker trip, When the cooldown period (60s) expires, Then the circuit transitions to HALF-OPEN, allows one probe request, and if successful, transitions back to CLOSED.

---

# F-104: Model Validation (Post-Training)

## Overview

Model Validation is the quality gate between model training and production deployment. After a model completes training (F-102), this feature runs a comprehensive evaluation suite against holdout datasets, edge-case scenarios, and regression tests. The validation produces a scorecard that must meet minimum thresholds before the model is approved for deployment. This prevents degraded models from reaching production and protects customer experience.

## User Journey / System Flow

1. **Training completes** — F-102 (Training Run Execution) signals that a new model checkpoint is ready for validation.
2. **Holdout dataset preparation** — The system selects a holdout dataset that was NOT used during training (20% of available ticket data). The dataset is stratified by intent category to ensure balanced representation.
3. **Run validation suite** — A Celery task executes the following test batteries in sequence:
   - **Accuracy test:** Compare model predictions against labeled ground truth across all intent categories
   - **Confidence calibration test:** Verify predicted confidence scores match actual accuracy (no over/under-confidence)
   - **Regression test:** Run the model against a fixed set of 200 "golden" test cases that the previous model handled correctly. Flag any regressions.
   - **Edge-case test:** Run 100 adversarial/edge-case inputs (multi-language, typos, long inputs, ambiguous queries, PII-containing inputs)
   - **Latency test:** Measure P95 and P99 response times across 1000 synthetic requests
   - **Safety test:** Run 50 inputs designed to trigger guardrails (harmful content, off-topic, hallucination attempts)
4. **Scorecard generation** — All results are aggregated into a validation scorecard with per-metric scores and an overall PASS/FAIL determination.
5. **Threshold comparison** — Each metric is compared against configurable pass/fail thresholds. If any critical metric fails, the overall result is FAIL.
6. **Notification** — Results are emitted via Socket.io to the Jarvis panel and stored in the `model_validations` table. A PASS triggers F-105 (deployment). A FAIL surfaces detailed failure reasons and recommendations.
7. **Manual review option** — Operators can override a FAIL with supervisor+ approval, documenting the reason for the override.

### Validation Metrics & Thresholds

| Metric | Weight | Pass Threshold | Critical? |
|--------|--------|---------------|-----------|
| **Overall Accuracy** | 30% | ≥ 85% | Yes |
| **Intent-level F1 (macro avg)** | 20% | ≥ 80% | Yes |
| **Confidence Calibration (ECE)** | 10% | ≤ 0.15 | No |
| **Regression Rate** | 15% | ≤ 5% (max 10/200 regressions) | Yes |
| **Edge-Case Pass Rate** | 10% | ≥ 75% | No |
| **P95 Latency** | 10% | ≤ 2000ms | No |
| **Safety Compliance** | 5% | 100% (0 safety failures) | Yes |
| **Overall Score** | 100% | ≥ 80% weighted | Yes |

### Test Dataset Requirements

| Dataset | Size | Source | Purpose |
|---------|------|--------|---------|
| **Holdout set** | 20% of labeled tickets | Random stratified split | General accuracy evaluation |
| **Golden regression set** | 200 fixed cases | Curated from production success cases | Prevent regressions |
| **Edge-case set** | 100 fixed cases | Curated adversarial inputs | Robustness testing |
| **Safety test set** | 50 fixed cases | Curated harmful/off-topic inputs | Guardrails compliance |
| **Latency benchmark set** | 1000 synthetic cases | Generated from ticket patterns | Performance benchmarking |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /api/models/validate` | POST | Trigger validation for a specific model checkpoint |
| `GET /api/models/{checkpoint_id}/validation` | GET | Get validation scorecard for a checkpoint |
| `GET /api/models/validation/history` | GET | Paginated list of all validation runs |
| `POST /api/models/{checkpoint_id}/validation/override` | POST | Override a FAIL result (supervisor+ only) |

## Database Tables

### `model_validations`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid_generate_v4() | Unique validation ID |
| company_id | UUID | FK → companies.id, NOT NULL, indexed | Tenant (BC-001) |
| model_checkpoint_id | UUID | FK → model_checkpoints.id, NOT NULL | Which model was validated |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'running' | running, passed, failed, overridden |
| overall_score | DECIMAL(5,2) | NULLABLE | Weighted overall score (0-100) |
| accuracy_score | DECIMAL(5,2) | NULLABLE | Intent classification accuracy |
| f1_macro_score | DECIMAL(5,2) | NULLABLE | Macro-averaged F1 score |
| calibration_error | DECIMAL(5,2) | NULLABLE | Expected Calibration Error |
| regression_count | INTEGER | NULLABLE | Number of golden case regressions |
| regression_rate | DECIMAL(5,2) | NULLABLE | Percentage of regressions |
| edge_case_pass_rate | DECIMAL(5,2) | NULLABLE | Edge-case handling accuracy |
| p95_latency_ms | INTEGER | NULLABLE | 95th percentile response time |
| safety_pass | BOOLEAN | NULLABLE | Whether all safety tests passed |
| detailed_results | JSONB | NULLABLE | Full per-category breakdown |
| failure_reasons | TEXT[] | NULLABLE | Array of failure reason descriptions |
| override_reason | TEXT | NULLABLE | Reason for manual override |
| overridden_by | UUID | FK → users.id, NULLABLE | Who overrode the result |
| started_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | When validation started |
| completed_at | TIMESTAMPTZ | NULLABLE | When validation completed |
| duration_seconds | INTEGER | NULLABLE | Total validation time |

**Indexes:** `idx_mv_company_checkpoint (company_id, model_checkpoint_id)`, `idx_mv_status (status)`

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `VALIDATION_HOLDOUT_RATIO` | 0.20 | Fraction of data held out for validation |
| `VALIDATION_ACCURACY_THRESHOLD` | 85% | Minimum accuracy to pass |
| `VALIDATION_REGRESSION_THRESHOLD` | 5% | Maximum allowed regression rate |
| `VALIDATION_SAFETY_REQUIRED` | true | Whether 100% safety compliance is required |
| `VALIDATION_TIMEOUT` | 1800s (30 min) | Maximum time for a validation run |
| `VALIDATION_MIN_DATASET_SIZE` | 100 | Minimum labeled samples required to validate |

## Building Codes Applied

- **BC-007 (AI Model Interaction):** Validation runs models through the Smart Router with PII redaction. Guardrails safety tests verify content safety compliance. Confidence calibration checks align with per-company confidence threshold storage (BC-007 Rule 9).
- **BC-004 (Background Jobs):** Validation runs as a Celery task with `max_retries=1` (validation is deterministic but may time out). `company_id` is the first parameter. Task logged in `task_logs` with start/end/duration.
- **BC-012 (Error Handling & Resilience):** If validation times out, it's marked as `failed` with reason. No partial results are used for deployment decisions.
- **BC-001 (Multi-Tenant Isolation):** Validation datasets are tenant-scoped. A model trained for Company A is never validated against Company B's data.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Insufficient training data (< 100 labeled samples)** | Validation returns `failed` with reason "Insufficient data for reliable validation." Model is NOT deployed. |
| **Validation timeout (exceeds 30 min)** | Celery soft_time_limit kills the task. Validation marked as `failed` with reason "Validation timed out." No deployment. |
| **All metrics pass but regression rate is 6%** | FAIL due to regression threshold (5%). Detailed results show which golden cases regressed for targeted retraining. |
| **Operator overrides a FAIL** | Requires supervisor+ role. Override reason is mandatory and audit-logged. The model proceeds to F-105 with an "override" flag. |
| **Model was trained on all available data (no holdout)** | Validation uses the golden regression set (200 cases) and edge-case set (100 cases) only. Accuracy score is marked as "unavailable" with reduced weight. |
| **New intent category added since last training** | Validation flags the new category as "untested" if insufficient examples exist. Does not block deployment but warns operator. |

## Acceptance Criteria

1. Given a newly trained model checkpoint, When validation is triggered, Then the system runs accuracy, regression, edge-case, latency, and safety tests against the holdout dataset and produces a scorecard within 30 minutes.
2. Given all metrics meet or exceed thresholds, When the scorecard is finalized, Then the validation status is set to `passed` and F-105 (deployment) is automatically triggered.
3. Given the regression test finds 12 out of 200 golden cases regressed (6% rate), When the scorecard is generated, Then validation status is `failed` with failure reasons listing the 12 regressed cases.
4. Given the safety test finds 2 blocked responses that should have been blocked (pass) but 1 harmful response that was NOT blocked, When safety compliance is evaluated, Then `safety_pass` is `false` and the overall validation fails.
5. Given a validation run times out after 30 minutes, When the Celery task is killed, Then the validation status is `failed` with reason "Validation timed out" and no deployment is triggered.
6. Given a validation fails but the supervisor determines the failure is acceptable, When the override endpoint is called with a documented reason, Then the validation status changes to `overridden` and deployment proceeds with the override flag.
7. Given a model is trained for Company A with 500 labeled samples, When validation runs, Then the holdout set is exactly 100 samples (20%) and all validation results are scoped to Company A's data only.

---

# F-105: Model Deployment with Auto-Rollback

## Overview

Model Deployment with Auto-Rollback implements zero-downtime canary deployments for retrained AI models. A new model that passes validation (F-104) is gradually rolled out to a small percentage of traffic, monitored for quality degradation, and either promoted to full deployment or automatically rolled back if metrics deteriorate. This ensures that model improvements reach production safely without risking customer experience.

## User Journey / System Flow

1. **Validation passed** — F-104 confirms the new model meets all quality thresholds. The deployment pipeline is triggered.
2. **Pre-deployment snapshot** — The current production model's configuration and metrics are snapshot stored in `model_deployments` for rollback reference.
3. **Canary deployment (5%)** — The new model is deployed to 5% of incoming requests. Traffic routing is handled at the Smart Router level via a weighted random selection.
4. **Canary monitoring (15 minutes)** — During the canary window, the system continuously monitors:
   - **Error rate**: % of responses resulting in guardrails blocks or failures (threshold: > 10%)
   - **Avg confidence score**: Mean confidence of canary responses (threshold: < 70%)
   - **Escalation rate**: % of canary tickets escalated to humans (threshold: > 2x baseline)
   - **Customer feedback**: CSAT scores on canary-handled tickets (threshold: < 3.0/5.0)
   - **Latency**: P95 response time (threshold: > 3000ms)
5. **Gradual promotion** — If canary metrics are healthy, traffic is increased: 5% → 25% → 50% → 100%. Each stage is monitored for 5 minutes.
6. **Full deployment** — At 100%, the model becomes the new production default. The old model is archived.
7. **Auto-rollback trigger** — If ANY monitored metric exceeds its threshold during ANY stage, the system automatically rolls back:
   - Canary traffic instantly redirected back to the previous model
   - Alert sent to operations team with metric details
   - Deployment marked as `rolled_back` with rollback reason
   - Model version returned to the previous stable checkpoint

### Deployment Stages

| Stage | Traffic % | Duration | Rollback Triggers |
|-------|-----------|----------|-------------------|
| Canary | 5% | 15 minutes | Error rate > 10%, Confidence < 70%, Escalation > 2x, CSAT < 3.0, P95 > 3000ms |
| Ramp 1 | 25% | 5 minutes | Same as canary + comparison to previous model's metrics at same traffic level |
| Ramp 2 | 50% | 5 minutes | Same as Ramp 1 |
| Full | 100% | Permanent | Continuous monitoring for 24 hours post-deployment |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /api/models/deploy` | POST | Start canary deployment for a validated checkpoint |
| `GET /api/models/deployments/{deployment_id}` | GET | Get deployment status and metrics |
| `POST /api/models/deployments/{deployment_id}/rollback` | POST | Manual rollback to previous model |
| `POST /api/models/deployments/{deployment_id}/promote` | POST | Skip canary, force promote to 100% (supervisor+ only) |
| `GET /api/models/deployments/history` | GET | Paginated deployment history |

## Database Tables

### `model_deployments`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid_generate_v4() | Unique deployment ID |
| company_id | UUID | FK → companies.id, NOT NULL, indexed | Tenant (BC-001) |
| model_checkpoint_id | UUID | FK → model_checkpoints.id, NOT NULL | New model being deployed |
| previous_checkpoint_id | UUID | FK → model_checkpoints.id, NOT NULL | Previous production model (for rollback) |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'canary' | canary, ramp_1, ramp_2, full, rolled_back, failed |
| canary_percentage | INTEGER | NOT NULL, DEFAULT 5 | Current traffic percentage |
| validation_id | UUID | FK → model_validations.id, NOT NULL | Link to validation result |
| canary_error_rate | DECIMAL(5,2) | NULLABLE | Error rate during canary |
| canary_avg_confidence | DECIMAL(5,2) | NULLABLE | Average confidence during canary |
| canary_escalation_rate | DECIMAL(5,2) | NULLABLE | Escalation rate during canary |
| canary_csat_score | DECIMAL(3,1) | NULLABLE | CSAT during canary |
| canary_p95_latency_ms | INTEGER | NULLABLE | P95 latency during canary |
| baseline_error_rate | DECIMAL(5,2) | NULLABLE | Previous model's error rate for comparison |
| baseline_escalation_rate | DECIMAL(5,2) | NULLABLE | Previous model's escalation rate |
| rollback_reason | TEXT | NULLABLE | Why the deployment was rolled back |
| rollback_triggered_by | VARCHAR(20) | NULLABLE | auto or manual |
| rolled_back_at | TIMESTAMPTZ | NULLABLE | When rollback occurred |
| promoted_at | TIMESTAMPTZ | NULLABLE | When promoted to full |
| started_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Deployment start time |
| completed_at | TIMESTAMPTZ | NULLABLE | Deployment completion time |

**Indexes:** `idx_md_company_status (company_id, status)`, `idx_md_checkpoint (model_checkpoint_id)`

### `model_deployment_metrics`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique metric snapshot ID |
| deployment_id | UUID | FK → model_deployments.id, NOT NULL | Parent deployment |
| stage | VARCHAR(20) | NOT NULL | canary, ramp_1, ramp_2, full |
| traffic_percentage | INTEGER | NOT NULL | Traffic percentage at this snapshot |
| error_rate | DECIMAL(5,2) | NOT NULL | Current error rate |
| avg_confidence | DECIMAL(5,2) | NOT NULL | Current average confidence |
| escalation_rate | DECIMAL(5,2) | NOT NULL | Current escalation rate |
| csat_score | DECIMAL(3,1) | NULLABLE | Current CSAT |
| p95_latency_ms | INTEGER | NOT NULL | Current P95 latency |
| request_count | INTEGER | NOT NULL | Number of requests in this snapshot window |
| recorded_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Snapshot timestamp |

**Indexes:** `idx_dmm_deployment_stage (deployment_id, stage)`, `idx_dmm_recorded (recorded_at DESC)`

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DEPLOY_CANARY_PERCENTAGE` | 5 | Initial canary traffic percentage |
| `DEPLOY_CANARY_DURATION` | 900s (15 min) | How long to monitor at canary level |
| `DEPLOY_RAMP_STAGES` | [25, 50, 100] | Traffic percentages for ramp stages |
| `DEPLOY_RAMP_DURATION` | 300s (5 min) | Duration per ramp stage |
| `DEPLOY_ROLLBACK_ERROR_RATE` | 10% | Error rate threshold triggering rollback |
| `DEPLOY_ROLLBACK_CONFIDENCE` | 70 | Minimum average confidence score |
| `DEPLOY_ROLLBACK_ESCALATION_MULTIPLIER` | 2.0x | Escalation rate vs baseline threshold |
| `DEPLOY_ROLLBACK_CSAT` | 3.0 | Minimum CSAT score during deployment |
| `DEPLOY_ROLLBACK_P95_LATENCY` | 3000ms | Maximum P95 latency |
| `DEPLOY_POST_MONITOR_DURATION` | 24 hours | Continuous monitoring after full deployment |

## Building Codes Applied

- **BC-007 (AI Model Interaction):** Deployment operates through the Smart Router. The new model is added to the model rotation with a weight parameter controlling traffic percentage. PII redaction and Guardrails apply to all canary traffic.
- **BC-004 (Background Jobs):** Deployment monitoring runs as a Celery beat task every 60 seconds during active deployments. Metric collection and evaluation are background tasks. `company_id` passed as first parameter.
- **BC-012 (Error Handling & Resilience):** Auto-rollback is the primary error recovery mechanism. If the deployment process itself fails (e.g., database error updating model config), the system defaults to the previous model — zero customer impact.
- **BC-001 (Multi-Tenant Isolation):** Deployments are per-tenant. A canary deployment for Company A does not affect Company B's traffic routing. Each tenant maintains independent model versions.
- **BC-009 (Approval Workflow):** Force-promotion (skipping canary) requires supervisor+ approval with documented reason.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Canary shows 11% error rate at 5% traffic** | Auto-rollback triggered immediately. Error rate metric is checked every 60 seconds. Previous model restored. Alert sent. |
| **Deployment during AI pause (F-083)** | Deployment proceeds but monitoring is paused. When AI resumes, canary monitoring begins from that point. |
| **Database failure during traffic switch** | Smart Router falls back to previous model (stored in Redis cache). Deployment marked as `failed`. Manual intervention required. |
| **Operator force-promotes a model** | Requires supervisor+ role. Canary stages skipped. Model promoted to 100%. Continuous monitoring for 24 hours — if metrics degrade, auto-rollback still triggers. |
| **Multiple deployments queued for same tenant** | Only one active deployment per tenant. New deployment request fails with "deployment already in progress." |
| **Rollback itself fails** | Critical alert sent to ops team. Redis-cached previous model config used as emergency fallback. Manual intervention required. |

## Acceptance Criteria

1. Given a model passes validation, When deployment is triggered, Then the model receives 5% of traffic for 15 minutes while metrics are continuously collected.
2. Given canary metrics show error rate of 12% (above 10% threshold), When the next metric check runs (within 60 seconds), Then auto-rollback is triggered and 100% of traffic returns to the previous model.
3. Given canary metrics are healthy at 5% for 15 minutes, When the canary window expires, Then traffic increases to 25% for 5 minutes, then 50% for 5 minutes, then 100%.
4. Given a deployment is in `canary` stage, When the operator calls the rollback endpoint, Then traffic immediately returns to the previous model and the deployment is marked `rolled_back` with reason "manual."
5. Given a deployment reaches `full` status, When 24 hours of post-deployment monitoring completes without metric violations, Then the deployment is marked as the permanent production model and the old model is archived.
6. Given Company A deploys a new model, When Company B makes API calls, Then Company B's traffic continues using Company B's current model — no cross-tenant interference.
7. Given the previous model's baseline escalation rate is 1%, When the canary escalation rate reaches 2.5% (> 2x baseline), Then auto-rollback is triggered.

---

# F-120: Email Handling (Outbound via Brevo)

## Overview

Email Handling manages all outbound email delivery through the Brevo (formerly Sendinblue) API. This includes transactional emails (ticket responses, password resets, welcome emails), notification emails (approval reminders, system alerts), and batch sends (reports, newsletters). Every outbound email uses a Brevo template, is rate-limited to prevent spam flags, tracked for delivery/bounce/complaint status, and logged for audit compliance. This is the outbound counterpart to F-121 (Inbound Email Parsing).

## User Journey / System Flow

1. **Email request initiated** — A PARWA service (ticket response, approval reminder, password reset, etc.) creates an email send request with: template ID, recipient address, template parameters, and related entity (ticket_id, user_id, etc.).
2. **Template validation** — The system verifies the requested template ID exists in the tenant's allowed template list and is one of the 10 defined Brevo templates.
3. **Rate limit check** — Before sending, the system checks:
   - **Per-thread limit:** Max 5 emails per thread per 24 hours (BC-006 Rule 2)
   - **Per-recipient limit:** Max 5 emails per customer per hour (BC-006 Rule 3)
   - **OOO check:** If this is a reply to an inbound email, verify the inbound didn't have OOO headers (BC-006 Rule 1)
4. **Recipient validation** — Check the recipient's email status. If `email_status = 'invalid'` (from a previous bounce/complaint), block sending and log.
5. **Send via Brevo API** — Call Brevo's `/smtp/email` endpoint with the template ID and parameters. Brevo handles actual delivery, DKIM signing, and SPF compliance.
6. **Log the send** — Create an `email_logs` record with template_used, recipient, status='sent', related_entity, and timestamp.
7. **Delivery tracking** — Brevo webhooks (delivered, bounced, complained, opened, clicked) update the `email_logs` status. Bounces and complaints trigger recipient email invalidation and account manager notification.
8. **Failure retry** — If the Brevo API call fails, retry up to 3 times with exponential backoff (BC-006 Rule 9). After 3 failures, log and alert ops team.

### Brevo Template Format

PARWA defines exactly 10 Brevo templates. Each template has:

| Template ID | Name | Purpose | Unsubscribe Required? |
|-------------|------|---------|----------------------|
| `tpl_parwa_ticket_response` | Ticket Response | AI/agent response to customer inquiry | No (transactional) |
| `tpl_parwa_password_reset` | Password Reset | Password reset link email | No (transactional) |
| `tpl_parwa_email_verification` | Email Verification | Account verification link | No (transactional) |
| `tpl_parwa_welcome` | Welcome Email | Post-onboarding welcome | No (transactional) |
| `tpl_parwa_approval_reminder` | Approval Reminder | Pending approval notification | No (internal) |
| `tpl_parwa_overage_notice` | Overage Notice | Daily overage charge notification | No (billing) |
| `tpl_parwa_first_victory` | First Victory | First AI resolution celebration | No (transactional) |
| `tpl_parwa_cancellation_confirm` | Cancellation Confirmation | Subscription cancellation receipt | No (transactional) |
| `tpl_parwa_newsletter` | Newsletter | Marketing/product updates | Yes |
| `tpl_parwa_system_alert` | System Alert | Ops team alerts and reports | No (internal) |

### Rate Limits & Throttling

| Limit Type | Threshold | Scope | Action on Exceed |
|------------|-----------|-------|-----------------|
| Per-thread per 24h | 5 emails | thread_id (ticket conversation) | Block with `rate_limited` status |
| Per-recipient per hour | 5 emails | recipient email address | Queue for next hour window |
| Brevo API rate limit | 2000/second | Account-level | Automatic retry after Brevo-specified cooldown |
| Daily send cap | 50,000 emails | Per tenant | Alert ops team, queue overflow for next day |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /api/email/send` | POST | Send a single email using a Brevo template |
| `POST /api/email/send-batch` | POST | Send batch emails (up to 100 recipients) |
| `GET /api/email/logs` | GET | Paginated email log for current tenant |
| `GET /api/email/logs/{email_log_id}` | GET | Get detailed email log with delivery status |
| `POST /api/email/recall` | POST | Recall a recently sent email via Brevo (within recall window) |
| `GET /api/email/templates` | GET | List available Brevo templates for current tenant |

**Celery Tasks:**
- `send_email_task(company_id, template_id, recipient, params, related_entity)` — Async email send
- `send_batch_email_task(company_id, template_id, recipients, params)` — Async batch send

## Database Tables

### `email_logs`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid_generate_v4() | Unique log ID |
| company_id | UUID | FK → companies.id, NOT NULL, indexed | Tenant (BC-001) |
| template_used | VARCHAR(100) | NOT NULL | Brevo template identifier |
| recipient_email | VARCHAR(255) | NOT NULL | Recipient email address |
| recipient_name | VARCHAR(255) | NULLABLE | Recipient display name |
| params | JSONB | NOT NULL | Template parameters used |
| brevo_message_id | VARCHAR(255) | NULLABLE | Brevo's message ID for tracking |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'queued' | queued, sent, delivered, bounced, failed, recalled, rate_limited |
| related_entity_type | VARCHAR(50) | NULLABLE | ticket, user, agent, billing |
| related_entity_id | UUID | NULLABLE | ID of the related entity |
| thread_id | UUID | FK → tickets.id, NULLABLE | For per-thread rate limiting |
| retry_count | INTEGER | NOT NULL, DEFAULT 0 | Number of send retries |
| error_message | TEXT | NULLABLE | Failure reason if status is failed/bounced |
| bounced_at | TIMESTAMPTZ | NULLABLE | When bounce was detected |
| complained_at | TIMESTAMPTZ | NULLABLE | When spam complaint was detected |
| recalled_at | TIMESTAMPTZ | NULLABLE | When email was recalled |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Email creation timestamp |
| sent_at | TIMESTAMPTZ | NULLABLE | When email was sent to Brevo |
| delivered_at | TIMESTAMPTZ | NULLABLE | When delivery was confirmed |

**Indexes:** `idx_el_company_status (company_id, status)`, `idx_el_recipient (recipient_email)`, `idx_el_related (related_entity_type, related_entity_id)`, `idx_el_thread_created (thread_id, created_at)`

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BREVO_API_KEY` | (from env) | Primary Brevo API key |
| `BREVO_API_KEY_BACKUP` | (from env) | Backup Brevo API key for failover |
| `BREVO_MAX_RETRIES` | 3 | Max send retries per email |
| `BREVO_RETRY_BACKOFF` | 2s, 4s, 8s | Exponential backoff for retries |
| `EMAIL_THREAD_LIMIT_24H` | 5 | Max emails per thread per 24 hours |
| `EMAIL_RECIPIENT_LIMIT_1H` | 5 | Max emails per recipient per hour |
| `EMAIL_DAILY_CAP` | 50000 | Max emails per tenant per day |
| `EMAIL_RECALL_WINDOW` | 300s (5 min) | Maximum time after send to recall an email |

## Building Codes Applied

- **BC-006 (Email Communication):** This is the primary feature implementing BC-006. All 9 mandatory rules apply: OOO detection (Rule 1), per-thread limit (Rule 2), per-recipient rate limit (Rule 3), Brevo template requirement (Rule 4), email logging (Rule 5), email loop prevention (Rule 6), unsubscribe links for marketing (Rule 7), bounce/complaint handling (Rule 8), retry logic (Rule 9).
- **BC-003 (Webhook Handling):** Brevo delivery/bounce/complaint webhooks are received via `/webhooks/brevo/events`, verified by IP allowlist, deduplicated by event ID, and processed asynchronously via Celery.
- **BC-004 (Background Jobs):** Email sending is handled by Celery tasks with `max_retries=3`, exponential backoff, and DLQ routing. `company_id` is first parameter. All tasks logged in `task_logs`.
- **BC-001 (Multi-Tenant Isolation):** Email logs are tenant-scoped. Rate limits are per-tenant. Templates are tenant-aware.
- **BC-012 (Error Handling & Resilience):** Failed sends are retried with backoff. Brevo API key failover to backup key. If all fails, email is queued and ops team alerted.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Brevo API key expires or is revoked** | System fails over to backup API key. If both keys fail, emails queue in Celery and ops team is alerted immediately. |
| **Recipient email previously bounced** | Email blocked with status `bounced_recipient`. No send attempt made. Dashboard shows invalid email indicator on customer profile. |
| **Rate limit exceeded mid-batch send** | Batch is split: emails within limit are sent immediately, remainder is queued for next rate limit window. Partial batch results reported. |
| **Email sent but Brevo API timeout before confirmation** | Treated as potential failure. Retry with same idempotency key. Brevo's own idempotency prevents duplicate delivery. |
| **Template parameters missing required fields** | Celery task fails with validation error. Logged as `failed` with reason "Missing template parameters: {field_names}". No email sent. |
| **Email recall requested after 5-minute window** | Recall request rejected with "Recall window expired." Email has already left Brevo's servers. |

## Acceptance Criteria

1. Given a ticket response is generated, When the email send task executes, Then the email is sent using `tpl_parwa_ticket_response` template with correct parameters and logged in `email_logs` with status='sent'.
2. Given 5 emails have been sent to the same thread within 24 hours, When a 6th email is attempted, Then the send is blocked with status='rate_limited' and no Brevo API call is made.
3. Given 5 emails have been sent to customer@example.com within 1 hour, When a 6th email is attempted, Then the email is queued for the next hour window and processed after the rate limit resets.
4. Given a Brevo bounce webhook is received for customer@example.com, When the webhook is processed, Then the customer's email_status is updated to 'invalid' and the account manager receives a notification.
5. Given the primary Brevo API key returns 401, When the send task retries, Then the backup Brevo API key is used. If both fail, the email is queued and the ops team receives an alert.
6. Given a marketing email is sent, When the Brevo template is rendered, Then the email includes a valid unsubscribe link per BC-006 Rule 7.
7. Given an operator clicks "Recall" on an email sent 2 minutes ago, When the recall API is called, Then Brevo is instructed to recall the email and the `email_logs` status is updated to 'recalled'.

---

# F-121: Inbound Email Parsing (Brevo Parse Webhook)

## Overview

Inbound Email Parsing receives customer emails via Brevo's Parse Webhook, extracts the content (body, headers, attachments), and routes them into the PARWA ticket system. This is how customer replies to support emails, new support inquiries via email, and forwarded emails become actionable tickets. The parser handles thread detection (matching replies to existing tickets), attachment extraction, HTML/text body parsing, and email loop prevention.

## User Journey / System Flow

1. **Email received by Brevo** — Customer sends an email to the tenant's dedicated support address (e.g., support@company.parwa.ai). Brevo receives it and parses the raw email.
2. **Brevo Parse Webhook fires** — Brevo POSTs the parsed email payload to PARWA's `/webhooks/brevo/inbound` endpoint. The payload includes: sender, recipients, subject, text body, HTML body, headers, attachments, and raw email ID.
3. **IP allowlist verification** — The endpoint verifies the request originates from a Brevo IP address (BC-003 Rule 5). Non-allowlisted requests are rejected with 403.
4. **Idempotency check** — The Brevo `message_id` header is checked against the `webhook_events` table. If already processed, return 200 with `already_processed` (BC-003 Rule 6).
5. **OOO / Auto-reply detection** — Check for `X-Auto-Response-Suppress`, `Auto-Submitted`, `X-NRL`, and `Precedence: bulk` headers. If present, return `auto_reply_ignored` and do NOT create a ticket (BC-006 Rule 1).
6. **Recipient validation** — Verify the email is addressed to a known tenant support address. Extract `company_id` from the recipient address mapping.
7. **Thread detection** — Analyze the email headers for `In-Reply-To` and `References` headers to match the email to an existing ticket thread. If matched, append the message to the existing ticket.
8. **New ticket creation** — If no thread match is found, create a new ticket with the email content. The ticket is classified by intent (F-062) and routed by the Smart Router (F-054).
9. **Attachment processing** — Extract attachments from the email payload. Files are uploaded to the tenant's storage (S3-compatible). Attachment references are linked to the ticket message.
10. **Rate limit check** — Verify the sender hasn't exceeded the 5-emails-per-thread-per-24h limit (BC-006 Rule 2).
11. **Response** — Return 200 OK within 3 seconds. Actual processing is deferred to a Celery task.

### Brevo Parse Webhook Payload Format

```json
{
  "message_id": "<abc123@company.parwa.ai>",
  "from": {"name": "John Doe", "email": "john@example.com"},
  "to": [{"name": "Support", "email": "support@company.parwa.ai"}],
  "subject": "Re: Order #12345 - Missing Item",
  "text": "Plain text body of the email...",
  "html": "<html><body>HTML body of the email...</body></html>",
  "headers": {
    "In-Reply-To": "<msg-456@company.parwa.ai>",
    "References": "<msg-123@company.parwa.ai> <msg-456@company.parwa.ai>",
    "X-Auto-Response-Suppress": null,
    "Auto-Submitted": null
  },
  "attachments": [
    {
      "name": "receipt.pdf",
      "content_type": "application/pdf",
      "content": "base64-encoded-content..."
    }
  ],
  "raw": "Full raw email source..."
}
```

### Thread Detection Logic

1. Extract `In-Reply-To` header → query `ticket_messages` for a message with matching `email_message_id`
2. If no `In-Reply-To`, check `References` header → parse space-separated message IDs, query each
3. If no header match, check subject line for "Re:" prefix → fuzzy match against recent ticket subjects (last 7 days)
4. If still no match, create a new ticket

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /webhooks/brevo/inbound` | POST | Brevo Parse webhook receiver |
| `GET /api/email/inbound/logs` | GET | Paginated inbound email processing log |
| `GET /api/email/inbound/parse-status/{message_id}` | GET | Check processing status of a specific inbound email |

## Database Tables

### `ticket_messages` (extended for inbound email)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique message ID |
| company_id | UUID | FK → companies.id, NOT NULL, indexed | Tenant |
| ticket_id | UUID | FK → tickets.id, NOT NULL, indexed | Parent ticket |
| sender_type | VARCHAR(20) | NOT NULL | customer, agent, ai, system |
| sender_email | VARCHAR(255) | NULLABLE | Sender's email address |
| sender_name | VARCHAR(255) | NULLABLE | Sender's display name |
| channel | VARCHAR(20) | NOT NULL, DEFAULT 'email' | email, chat, sms, voice |
| body_text | TEXT | NULLABLE | Plain text body |
| body_html | TEXT | NULLABLE | HTML body |
| email_message_id | VARCHAR(255) | NULLABLE, UNIQUE | For thread matching |
| email_in_reply_to | VARCHAR(255) | NULLABLE | In-Reply-To header value |
| email_references | TEXT | NULLABLE | References header value |
| is_auto_reply | BOOLEAN | NOT NULL, DEFAULT false | Whether this was detected as auto-reply |
| is_internal | BOOLEAN | NOT NULL, DEFAULT false | Internal note vs customer-visible |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Message timestamp |

**Indexes:** `idx_tm_ticket_created (ticket_id, created_at)`, `idx_tm_email_msg_id (email_message_id)`, `idx_tm_company (company_id)`

### `ticket_attachments`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique attachment ID |
| company_id | UUID | FK → companies.id, NOT NULL, indexed | Tenant |
| ticket_message_id | UUID | FK → ticket_messages.id, NOT NULL | Parent message |
| ticket_id | UUID | FK → tickets.id, NOT NULL, indexed | Parent ticket (denormalized for queries) |
| filename | VARCHAR(255) | NOT NULL | Original filename |
| content_type | VARCHAR(100) | NOT NULL | MIME type |
| file_size_bytes | INTEGER | NOT NULL | File size |
| storage_path | VARCHAR(500) | NOT NULL | S3 storage path |
| uploaded_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Upload timestamp |

**Indexes:** `idx_ta_message (ticket_message_id)`, `idx_ta_ticket (ticket_id)`

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BREVO_PARSE_ENDPOINT` | `/webhooks/brevo/inbound` | Webhook URL registered with Brevo |
| `BREVO_IP_ALLOWLIST` | (Brevo documented IPs) | IP addresses allowed for webhook calls |
| `INBOUND_MAX_ATTACHMENT_SIZE` | 25 MB | Maximum attachment size per file |
| `INBOUND_MAX_ATTACHMENTS_PER_EMAIL` | 10 | Maximum attachments per inbound email |
| `INBOUND_THREAD_SUBJECT_FUZZY_DAYS` | 7 | Days to look back for subject-based thread matching |
| `INBOUND_RATE_LIMIT_THREAD_24H` | 5 | Max inbound emails per thread per 24h |
| `INBOUND_SUPPORTED_ATTACHMENT_TYPES` | pdf,doc,docx,xls,xlsx,png,jpg,jpeg,gif,csv,txt | Allowed file types |
| `INBOUND_STORAGE_BACKEND` | `s3` | Storage backend for attachments |

## Building Codes Applied

- **BC-006 (Email Communication):** Core building code. OOO/auto-reply detection (Rule 1). Per-thread rate limiting (Rule 2). Email loop prevention (Rule 6). All rules enforced before ticket creation.
- **BC-003 (Webhook Handling):** Brevo Parse webhook verification via IP allowlist (Rule 5). Idempotency via `message_id` unique constraint (Rule 6). Async processing via Celery (Rule 7). 3-second response SLA (Rule 10).
- **BC-004 (Background Jobs):** Email processing is a Celery task with `max_retries=3`, exponential backoff, and DLQ routing. `company_id` is first parameter.
- **BC-001 (Multi-Tenant Isolation):** Recipient address maps to `company_id`. All ticket/message creation is tenant-scoped. Attachments stored in tenant-isolated S3 paths.
- **BC-010 (Data Lifecycle & Compliance):** PII in email bodies is flagged for the PII Redaction Engine (F-056). Email content retained per tenant's data retention policy.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Email with no body (empty text and HTML)** | Ticket/message created with body_text = "[No content]" and a note flagging the empty content for agent review. |
| **Very large email (> 25MB total including attachments)** | Email is rejected with HTTP 200 (to prevent Brevo retry) and logged as `rejected_too_large`. Ops team notified. |
| **Malformed HTML body** | HTML parser attempts to extract text. If parsing fails, falls back to text body. If both fail, creates ticket with "[Content could not be parsed]" message. |
| **Email from a previously complained address** | Checked against `email_status = 'invalid'`. Email is rejected and logged. No ticket created. |
| **Duplicate In-Reply-To matching multiple tickets** | Uses the most recent ticket match. Logs a warning for investigation. |
| **Attachment with unsupported file type (e.g., .exe)** | Attachment is rejected but email body is still processed. Message includes note "Attachment {filename} was blocked (unsupported file type)." |
| **Brevo sends the same webhook twice** | Idempotency check on `message_id` returns `already_processed` on second delivery. No duplicate ticket or message created. |

## Acceptance Criteria

1. Given a customer sends an email to support@company.parwa.ai, When the Brevo Parse webhook fires, Then a new ticket is created with the email body, sender info, and subject within 10 seconds.
2. Given a customer replies to an existing ticket email (with In-Reply-To header), When the webhook fires, Then the reply is appended to the existing ticket thread as a new message — no new ticket is created.
3. Given an inbound email has X-Auto-Response-Suppress header, When the webhook processes it, Then no ticket is created and the response is `auto_reply_ignored`.
4. Given an inbound email has 3 attachments (PDF, PNG, CSV), When processed, Then all attachments are uploaded to S3, linked to the ticket message, and viewable in the ticket detail modal.
5. Given Brevo sends the same webhook payload twice (same message_id), When the second delivery is processed, Then the idempotency check returns `already_processed` and no duplicate ticket/message is created.
6. Given an inbound email from an address with `email_status = 'invalid'`, When the webhook processes it, Then the email is rejected and logged — no ticket is created.
7. Given 6 emails from the same sender to the same thread within 24 hours, When the 6th email arrives, Then it is blocked by the per-thread rate limit and logged as `rate_limited`.

---

# F-131: Pre-built Connectors

## Overview

Pre-built Connectors provide ready-to-use integrations with popular third-party platforms: Shopify (e-commerce), GitHub (development), TMS/WMS (logistics), Zendesk/Intercom (support migration), and Stripe (payments). Each connector includes guided OAuth authorization, automatic data synchronization, webhook event handling, and a unified health monitoring interface. Connectors enable PARWA's AI to access real-time external data (order status, shipment tracking, issue details) for accurate customer support responses.

## User Journey / System Flow

### Shopify Connector

1. **OAuth initiation** — Operator clicks "Connect Shopify" in the integration setup (F-030). PARWA redirects to Shopify's OAuth authorize URL with the app's `client_id` and `scopes` (read_orders, read_products, read_customers).
2. **OAuth callback** — Shopify redirects back with an authorization code. PARWA exchanges it for an access token via Shopify's `/admin/oauth/access_token` endpoint.
3. **Webhook registration** — PARWA registers webhooks for: `orders/create`, `orders/updated`, `products/update`, `customers/create`. All webhooks verified via HMAC-SHA256 (BC-003 Rule 3).
4. **Data sync** — Initial sync fetches recent orders, products, and customers via Shopify's REST API. Subsequent updates come via webhooks.
5. **Health monitoring** — Integration Health Monitor (F-137) tracks last sync time, error rate, and API latency.

### GitHub Connector

1. **OAuth initiation** — Operator clicks "Connect GitHub". PARWA redirects to GitHub's OAuth authorize URL with scopes: `read:issues`, `read:pull_requests`, `repo`.
2. **OAuth callback** — GitHub redirects back with code. PARWA exchanges for access token.
3. **Webhook registration** — Register for: `issues`, `issue_comment`, `pull_request` events on selected repositories.
4. **Data sync** — Fetch open issues and recent PRs. Subsequent updates via webhooks.

### TMS/WMS Connector

1. **API key configuration** — Operator enters TMS/WMS API endpoint and API key (no OAuth — these systems typically use API keys).
2. **Connection test** — PARWA makes a test API call to verify connectivity and credentials.
3. **Data mapping** — Operator maps TMS/WMS fields (order_id, tracking_number, shipment_status) to PARWA fields via a mapping configuration UI.
4. **Sync scheduling** — Configure polling interval (default: every 5 minutes) for shipment status updates.

### Connector Types Summary

| Connector | Auth Method | Webhook Events | Data Synced | Primary Use Case |
|-----------|-------------|----------------|-------------|-----------------|
| **Shopify** | OAuth 2.0 | orders/create, orders/updated, products/update, customers/create | Orders, products, customers | E-commerce support |
| **GitHub** | OAuth 2.0 | issues, issue_comment, pull_request | Issues, PRs, repo metadata | Technical/Dev support |
| **TMS/WMS** | API Key | Polling-based (no webhooks) | Shipments, tracking, inventory | Logistics support |
| **Zendesk** | OAuth 2.0 | ticket.created, ticket.updated | Tickets, users, comments | Support migration |
| **Intercom** | OAuth 2.0 | conversation.created, conversation.updated | Conversations, contacts | Support migration |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/connectors/available` | GET | List available pre-built connectors |
| `POST /api/connectors/shopify/auth` | POST | Initiate Shopify OAuth flow |
| `GET /api/connectors/shopify/callback` | GET | Shopify OAuth callback |
| `POST /api/connectors/github/auth` | POST | Initiate GitHub OAuth flow |
| `GET /api/connectors/github/callback` | GET | GitHub OAuth callback |
| `POST /api/connectors/tms-wms/configure` | POST | Configure TMS/WMS with API key and mapping |
| `POST /api/connectors/tms-wms/test` | POST | Test TMS/WMS connectivity |
| `POST /api/connectors/{connector_id}/disconnect` | POST | Disconnect a connector and revoke tokens |
| `POST /api/connectors/{connector_id}/resync` | POST | Trigger manual data resync |
| `GET /api/connectors/{connector_id}/status` | GET | Get connector sync status and health |
| `POST /webhooks/shopify` | POST | Shopify webhook receiver |
| `POST /webhooks/github` | POST | GitHub webhook receiver |

## Database Tables

### `integrations`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid_generate_v4() | Unique integration ID |
| company_id | UUID | FK → companies.id, NOT NULL, indexed | Tenant (BC-001) |
| connector_type | VARCHAR(50) | NOT NULL | shopify, github, tms_wms, zendesk, intercom |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'configuring' | configuring, active, disconnected, error |
| auth_method | VARCHAR(20) | NOT NULL | oauth, api_key |
| access_token | TEXT | NULLABLE | Encrypted OAuth access token |
| refresh_token | TEXT | NULLABLE | Encrypted OAuth refresh token |
| api_key | TEXT | NULLABLE | Encrypted API key (for TMS/WMS) |
| api_endpoint | VARCHAR(500) | NULLABLE | Base URL for API calls |
| external_account_id | VARCHAR(255) | NULLABLE | External system account/shop identifier |
| external_account_name | VARCHAR(255) | NULLABLE | Display name for external account |
| webhook_secret | TEXT | NULLABLE | HMAC secret for webhook verification |
| field_mapping | JSONB | NULLABLE | Custom field mapping configuration |
| last_sync_at | TIMESTAMPTZ | NULLABLE | Last successful data sync |
| sync_frequency_seconds | INTEGER | NULLABLE | Polling interval (NULL = webhook-based) |
| error_count_24h | INTEGER | NOT NULL, DEFAULT 0 | Errors in last 24 hours |
| last_error_message | TEXT | NULLABLE | Most recent error |
| connected_at | TIMESTAMPTZ | NULLABLE | When connector was activated |
| disconnected_at | TIMESTAMPTZ | NULLABLE | When connector was disconnected |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Integration creation time |

**Indexes:** `idx_int_company_type (company_id, connector_type)`, `idx_int_status (status)`

### `connector_sync_log`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique log ID |
| company_id | UUID | FK → companies.id, NOT NULL, indexed | Tenant |
| integration_id | UUID | FK → integrations.id, NOT NULL, indexed | Parent integration |
| sync_type | VARCHAR(20) | NOT NULL | full, incremental, webhook, manual |
| records_synced | INTEGER | NOT NULL, DEFAULT 0 | Number of records synced |
| records_failed | INTEGER | NOT NULL, DEFAULT 0 | Number of records that failed |
| error_message | TEXT | NULLABLE | Sync error details |
| duration_ms | INTEGER | NULLABLE | Sync duration |
| started_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Sync start time |
| completed_at | TIMESTAMPTZ | NULLABLE | Sync completion time |

**Indexes:** `idx_csl_integration (integration_id, started_at DESC)`

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SHOPIFY_CLIENT_ID` | (from env) | Shopify app client ID |
| `SHOPIFY_CLIENT_SECRET` | (from env) | Shopify app client secret |
| `SHOPIFY_SCOPES` | `read_orders,read_products,read_customers` | OAuth permission scopes |
| `GITHUB_CLIENT_ID` | (from env) | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | (from env) | GitHub OAuth app client secret |
| `TMS_WMS_DEFAULT_POLL_INTERVAL` | 300s (5 min) | Default polling frequency for TMS/WMS |
| `CONNECTOR_TOKEN_ENCRYPTION_KEY` | (from env) | Encryption key for stored access tokens |
| `CONNECTOR_MAX_SYNC_RETRIES` | 3 | Max retries per sync operation |
| `CONNECTOR_SYNC_TIMEOUT` | 600s (10 min) | Maximum sync duration |

## Building Codes Applied

- **BC-003 (Webhook Handling):** All incoming webhooks (Shopify HMAC-SHA256, GitHub HMAC-SHA256) are verified before processing (Rules 2, 3). Idempotency via `webhook_events` table (Rule 6). Async processing via Celery (Rule 7). 3-second response SLA (Rule 10).
- **BC-004 (Background Jobs):** Data sync operations are Celery tasks with `max_retries=3`, exponential backoff. `company_id` is first parameter. All tasks logged in `task_logs`.
- **BC-001 (Multi-Tenant Isolation):** Each connector is tenant-scoped. Data synced from Shopify is stored with the tenant's `company_id`. No cross-tenant data sharing between connectors.
- **BC-011 (Authentication & Security):** OAuth tokens and API keys are encrypted at rest using AES-256. Tokens stored in `integrations` table with encryption. Token refresh handled automatically for expiring tokens.
- **BC-012 (Error Handling & Resilience):** Connector failures trigger the circuit breaker (F-139). Sync failures are retried with backoff. Connector health is monitored by F-137 and surfaced in Jarvis System Status Panel (F-088).
- **BC-005 (Real-Time Communication):** Connector status updates emitted via Socket.io to tenant-scoped rooms. Real-time sync progress visible in dashboard.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Shopify OAuth token expires** | PARWA uses the refresh token to obtain a new access token. If refresh fails, connector status changes to `error` and operator is notified to re-authenticate. |
| **GitHub webhook signature mismatch** | Webhook rejected with 403. Logged as potential security event. No data processed. |
| **TMS/WMS API endpoint unreachable** | Circuit breaker (F-139) trips after 5 consecutive failures. Connector status shows `error`. Polling retries after cooldown. Cached data used in the interim. |
| **Shopify rate limit (402) during sync** | Sync pauses for Shopify-specified cooldown. Resumes automatically. Partial sync progress is maintained. |
| **Operator disconnects an active connector** | Access token is revoked via provider's API. Webhook registrations are removed. Synced data is retained but no longer updated. |
| **Data sync returns duplicate records** | Upsert logic based on external system's unique ID. No duplicate records created. Existing records updated with latest data. |

## Acceptance Criteria

1. Given an operator clicks "Connect Shopify" and completes the OAuth flow, When the callback is processed, Then the Shopify integration is stored with status='active', webhooks are registered, and an initial data sync begins.
2. Given a Shopify `orders/updated` webhook fires, When the webhook is received and verified, Then the corresponding order data is updated in PARWA and any related tickets are notified via Socket.io.
3. Given a TMS/WMS connector is configured with API key and endpoint, When the connection test runs, Then a test API call is made and the result (success/failure) is displayed within 5 seconds.
4. Given Shopify returns a 402 rate limit during sync, When the sync task encounters the rate limit, Then the sync pauses for the specified cooldown and resumes without data loss.
5. Given an operator clicks "Disconnect" on an active Shopify connector, When the disconnection completes, Then the access token is revoked, webhooks are unregistered, and the integration status changes to 'disconnected'.
6. Given a connector has 5 consecutive sync failures, When the circuit breaker evaluates, Then the connector's circuit trips to OPEN and no further API calls are attempted until cooldown.
7. Given Shopify sends a webhook with an invalid HMAC signature, When the webhook is received, Then the request is rejected with 403, logged as a security event, and no data is processed.

---

# F-139: Circuit Breaker

## Overview

The Circuit Breaker prevents cascading failures from external integration outages by temporarily stopping calls to unhealthy services. When an external API (LLM provider, Brevo, Twilio, Shopify, TMS/WMS) fails repeatedly, the circuit breaker "trips" and redirects all traffic to fallback strategies or cached data. After a cooldown period, the breaker allows a small number of probe requests to test recovery. This protects PARWA from being overwhelmed by failing external services and ensures graceful degradation.

## User Journey / System Flow

1. **Normal operation (CLOSED state)** — All external API calls pass through the circuit breaker. Each call result is tracked in a sliding window.
2. **Failure tracking** — The circuit breaker maintains a sliding window of recent calls (default: 60 seconds). Each failed call increments the failure counter. Each successful call decrements it.
3. **Threshold evaluation** — If the failure count exceeds the threshold (default: 5 failures in 60 seconds), the circuit trips to OPEN state.
4. **OPEN state** — All new calls to the failing service are immediately rejected with a `CircuitOpenError`. No actual API calls are made. The calling service falls back to its fallback strategy (queue, cached data, or safe default response).
5. **Cooldown timer** — A cooldown timer starts when the circuit opens (default: 60 seconds). During cooldown, the circuit remains OPEN.
6. **HALF-OPEN state** — After cooldown expires, the circuit transitions to HALF-OPEN. In this state, the breaker allows exactly **1 probe request** through to test if the service has recovered.
7. **Recovery or re-trip** — If the probe request succeeds, the circuit transitions back to CLOSED (normal operation). If the probe fails, the circuit re-opens (back to OPEN) and the cooldown timer restarts.
8. **Notification** — State transitions (CLOSED → OPEN, OPEN → HALF-OPEN, HALF-OPEN → CLOSED/OPEN) are emitted via Socket.io and logged for monitoring.

### State Machine Diagram

```
         Failure threshold exceeded
    CLOSED ──────────────────────> OPEN
      ^                               │
      │                               │ Cooldown expires
      │                               v
      └──────────────────────── HALF-OPEN
                    Probe succeeds │        │ Probe fails
                              CLOSED        OPEN
```

### Per-Service Configuration

| Service | Failure Threshold | Cooldown | Half-Open Probes | Fallback Strategy |
|---------|-------------------|----------|------------------|-------------------|
| **OpenRouter (LLM)** | 5 / 60s | 60s | 1 | Queue request, try next provider |
| **Brevo (Email)** | 5 / 60s | 120s | 1 | Queue emails for delayed send |
| **Twilio (SMS/Voice)** | 3 / 60s | 120s | 1 | Queue messages, show "sending delayed" |
| **Paddle (Billing)** | 3 / 60s | 300s | 1 | Queue billing actions, alert immediately |
| **Shopify** | 5 / 60s | 300s | 1 | Use cached order data |
| **TMS/WMS** | 5 / 60s | 300s | 1 | Use cached shipment data |
| **GitHub** | 5 / 120s | 600s | 1 | Use cached issue data |
| **Custom Integrations** | 5 / 60s | 120s | 1 | Configurable per connector |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/internal/circuit-breaker/status` | GET | Get all circuit breaker states |
| `GET /api/internal/circuit-breaker/{service_name}` | GET | Get specific service circuit state |
| `POST /api/internal/circuit-breaker/{service_name}/reset` | POST | Manually reset circuit to CLOSED (ops only) |
| `POST /api/internal/circuit-breaker/{service_name}/trip` | POST | Manually trip circuit to OPEN (ops only) |
| `GET /api/internal/circuit-breaker/history` | GET | Paginated circuit state transition history |

## Database Tables

### `circuit_breaker_states`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid_generate_v4() | Unique state record |
| service_name | VARCHAR(100) | NOT NULL, UNIQUE | External service identifier |
| state | VARCHAR(20) | NOT NULL, DEFAULT 'closed' | closed, open, half_open |
| failure_count | INTEGER | NOT NULL, DEFAULT 0 | Current failure count in sliding window |
| success_count | INTEGER | NOT NULL, DEFAULT 0 | Current success count in sliding window |
| last_failure_at | TIMESTAMPTZ | NULLABLE | Timestamp of most recent failure |
| last_success_at | TIMESTAMPTZ | NULLABLE | Timestamp of most recent success |
| opened_at | TIMESTAMPTZ | NULLABLE | When circuit last opened |
| half_opened_at | TIMESTAMPTZ | NULLABLE | When circuit last entered half-open |
| closed_at | TIMESTAMPTZ | NULLABLE | When circuit last closed (recovered) |
| failure_threshold | INTEGER | NOT NULL, DEFAULT 5 | Failures needed to trip |
| cooldown_seconds | INTEGER | NOT NULL, DEFAULT 60 | Cooldown duration in OPEN state |
| window_seconds | INTEGER | NOT NULL, DEFAULT 60 | Sliding window duration |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last state update |

**Indexes:** `idx_cbs_service (service_name)` — UNIQUE index ensures one record per service

### `circuit_breaker_history`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique history record |
| service_name | VARCHAR(100) | NOT NULL, indexed | Service identifier |
| from_state | VARCHAR(20) | NOT NULL | Previous state |
| to_state | VARCHAR(20) | NOT NULL | New state |
| reason | VARCHAR(255) | NULLABLE | Why the transition occurred |
| failure_count_at_transition | INTEGER | NOT NULL | Failure count when transition happened |
| probe_result | VARCHAR(20) | NULLABLE | For HALF-OPEN transitions: success or failure |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Transition timestamp |

**Indexes:** `idx_cbh_service_created (service_name, created_at DESC)`

**Redis Keys (primary state store for performance):**

| Key Pattern | Type | TTL | Description |
|-------------|------|-----|-------------|
| `parwa:cb:{service_name}:state` | STRING | None | Current state: closed, open, half_open |
| `parwa:cb:{service_name}:failures` | SORTED SET | Window seconds | Timestamp-scored failure records |
| `parwa:cb:{service_name}:successes` | SORTED SET | Window seconds | Timestamp-scored success records |
| `parwa:cb:{service_name}:opened_at` | STRING | None | When the circuit was last opened |

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CB_DEFAULT_FAILURE_THRESHOLD` | 5 | Default failures to trip circuit |
| `CB_DEFAULT_COOLDOWN` | 60s | Default cooldown in OPEN state |
| `CB_DEFAULT_WINDOW` | 60s | Default sliding window duration |
| `CB_DEFAULT_HALF_OPEN_PROBES` | 1 | Probes allowed in HALF-OPEN state |
| `CB_STATE_SYNC_INTERVAL` | 10s | Interval to sync Redis → PostgreSQL |
| `CB_HEALTH_CHECK_INTERVAL` | 30s | Interval for proactive health checks in OPEN state |
| `CB_ALERT_ON_TRIP` | true | Whether to alert ops team on circuit trip |
| `CB_AUTO_RESET_AFTER` | 3600s (1 hour) | Auto-reset circuit if manually reset not done within 1 hour |

## Building Codes Applied

- **BC-012 (Error Handling & Resilience):** This is a core resilience feature. Prevents cascading failures from external services. All state transitions are logged. Fallback strategies ensure graceful degradation. The circuit breaker is the last line of defense before human escalation.
- **BC-003 (Webhook Handling):** If a webhook processing circuit trips (e.g., Shopify webhooks failing), incoming webhooks are still accepted (200 OK) but queued for later processing per BC-003 Rule 7.
- **BC-004 (Background Jobs):** Circuit breaker state sync from Redis to PostgreSQL runs as a Celery beat task every 10 seconds. Health check probes in HALF-OPEN state run as Celery tasks with `company_id` parameter.
- **BC-005 (Real-Time Communication):** Circuit state transitions are emitted via Socket.io to tenant-scoped rooms. Real-time circuit status visible in Jarvis System Status Panel (F-088) and Integration Health Monitor (F-137).
- **BC-001 (Multi-Tenant Isolation):** Circuit breakers are service-level (not tenant-level) since external services like OpenRouter and Brevo are shared. However, tenant-specific connectors (Shopify, TMS/WMS) have per-tenant circuit instances keyed by `parwa:cb:{company_id}:{connector_id}:state`.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Redis fails while circuit is OPEN** | Circuit state recovered from PostgreSQL fallback on Redis restart. Recovery task runs on Celery worker startup (BC-004 Rule 9). During Redis downtime, circuits default to CLOSED (fail-open) to avoid unnecessary blocking. |
| **All circuits trip simultaneously (multi-provider outage)** | Trust Preservation Protocol (F-094) activates globally. All customer interactions show reassuring "processing" messages. Critical alert sent to ops team with all tripped circuits listed. |
| **Circuit stuck in OPEN for extended period** | Auto-reset after 1 hour if no manual intervention. Health check probes continue every 30 seconds. Ops team receives escalating alerts at 5min, 15min, 1 hour. |
| **HALF-OPEN probe succeeds but next request fails** | Circuit stays CLOSED after successful probe. If the next request fails, the failure counter increments normally. Circuit will re-trip if threshold is reached again. |
| **Manual reset while service is still down** | Circuit resets to CLOSED. First request fails, failure counter increments. If threshold is reached quickly, circuit re-opens. An alert warns ops team that the manual reset may have been premature. |
| **Circuit breaker called from within a Celery task** | Circuit state is checked via Redis (primary) or PostgreSQL (fallback). No HTTP overhead. `CircuitOpenError` is caught and the task falls back to its retry/dead-letter logic. |
| **Tenant-specific connector trips for one tenant but not another** | Per-tenant circuits are independent. Company A's Shopify circuit tripping does not affect Company B's Shopify connection. |

## Acceptance Criteria

1. Given a service (e.g., Brevo) returns 5 consecutive failures within 60 seconds, When the circuit breaker evaluates, Then the circuit state transitions from CLOSED to OPEN and a Socket.io event is emitted to all connected clients.
2. Given the circuit is in OPEN state, When a new API call to the same service is attempted, Then the call is immediately rejected with `CircuitOpenError` and no actual API call is made.
3. Given the circuit has been OPEN for 60 seconds (cooldown), When the cooldown expires, Then the circuit transitions to HALF-OPEN and exactly 1 probe request is allowed through.
4. Given the probe request in HALF-OPEN state succeeds, When the result is evaluated, Then the circuit transitions to CLOSED and normal traffic resumes.
5. Given the probe request in HALF-OPEN state fails, When the result is evaluated, Then the circuit transitions back to OPEN and the cooldown timer restarts from 0.
6. Given the circuit state is stored in Redis, When Redis restarts, Then the circuit state is recovered from PostgreSQL and the correct state is restored within 10 seconds.
7. Given an operator calls the manual reset endpoint while the circuit is OPEN, When the reset is processed, Then the circuit transitions to CLOSED immediately and the transition is logged in `circuit_breaker_history` with reason "manual_reset."

---

## Summary

| Feature | Category | Building Codes | Priority | Dependencies |
|---------|----------|---------------|----------|-------------|
| F-087: Jarvis Chat Panel | Jarvis / AI | BC-007, BC-005, BC-011, BC-001, BC-012 | Critical | F-054, F-053, F-088 |
| F-093: Proactive Self-Healing | Resilience / Infra | BC-012, BC-004, BC-003, BC-005, BC-007 | Critical | F-055, F-137, F-139 |
| F-104: Model Validation | AI / Training | BC-007, BC-004, BC-012, BC-001 | Critical | F-102, F-105, F-116 |
| F-105: Model Deployment | AI / Infra | BC-007, BC-004, BC-012, BC-001, BC-009 | Critical | F-104, F-055, F-098 |
| F-120: Email Handling (Outbound) | Communications | BC-006, BC-003, BC-004, BC-001, BC-012 | Critical | F-065, F-121, F-084 |
| F-121: Inbound Email Parsing | Communications | BC-006, BC-003, BC-004, BC-001, BC-010 | Critical | F-120, F-062, F-070 |
| F-131: Pre-built Connectors | Integrations | BC-003, BC-004, BC-001, BC-011, BC-012, BC-005 | Critical | F-137, F-070 |
| F-139: Circuit Breaker | Resilience / Infra | BC-012, BC-003, BC-004, BC-005, BC-001 | Critical | F-137, F-138, F-093, F-094 |

---

> **Document version:** 1.0 | **Last updated:** July 2025 | **Status:** Ready for implementation planning
