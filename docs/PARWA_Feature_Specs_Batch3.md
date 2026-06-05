# PARWA Feature Specs — Batch 3: AI Core Engine

> **AI-Powered Customer Support Platform**
>
> This document contains detailed feature specifications for 8 critical AI Core features. These features form the intelligence backbone of PARWA — the state engine, model routing, safety, scoring, workflow orchestration, and knowledge retrieval systems that power every AI interaction on the platform.
>
> **Tech Stack:** FastAPI (backend), PostgreSQL + pgvector (database), Redis (cache + state), OpenRouter (LLM provider), LiteLLM (model abstraction), LangGraph (workflow), DSPy (prompt optimization), Celery (background jobs)
>
> **Building Codes Reference:** BC-007 (AI Model Interaction), BC-008 (State Management), BC-001 (Multi-Tenant Isolation), BC-004 (Background Jobs), BC-010 (Data Lifecycle), BC-011 (Authentication & Security), BC-012 (Error Handling & Resilience), BC-009 (Approval Workflow), BC-013 (Technique Router)

---

# F-053: GSD State Engine

## Overview

The GSD (Guided Support Dialogue) State Engine replaces raw chat history with a structured JSON state object that tracks every dimension of a support conversation — intent, collected information, pending actions, resolution progress, and handoff status. Rather than re-reading entire conversation histories on each LLM call (expensive and error-prone), the engine maintains a compact, validated state machine that persists across Redis (hot) and PostgreSQL (cold), surviving restarts and enabling lightning-fast context reconstruction.

## Architecture

**Dual-Storage State Architecture:**
1. **Redis (Primary):** Stores the active GSD state as a JSON string at key `parwa:{company_id}:gsd:{session_id}` with a 2-hour TTL. Sub-millisecond reads for every LLM call.
2. **PostgreSQL (Fallback):** The `sessions` table stores the same state JSON in a `state` JSONB column. Every Redis write triggers an asynchronous PostgreSQL write via Celery. On Redis failure or restart, state is recovered from Postgres.
3. **State Recovery Task:** On Celery worker startup, a recovery task hydrates Redis from PostgreSQL for all sessions with `updated_at` within the last 2 hours and `status != 'closed'`.
4. **Schema Validator:** Every state mutation passes through a Pydantic model that enforces required fields and data types. Invalid mutations are rejected and logged.

**State Update Flow:**
```
User Message → FastAPI endpoint → GSDStateEngine.update_state(session_id, delta)
    → Load from Redis (fallback: Postgres)
    → Merge delta with current state
    → Validate against GSDStateSchema (Pydantic)
    → Calculate token usage via tiktoken
    → Check context health thresholds (70%/90%/95%)
    → If 90%+: trigger Dynamic Context Compression
    → Dual write: Redis SETEX + Postgres UPDATE
    → Return validated state to caller (LangGraph workflow)
```

## JSON State Structure

```json
{
  "session_id": "uuid-v4",
  "company_id": "uuid-v4",
  "ticket_id": "uuid-v4 | null",
  "customer_id": "uuid-v4 | null",
  "agent_id": "uuid-v4 | null",

  "conversation": {
    "history": [
      {"role": "user", "content": "I need a refund for order #12345", "timestamp": "2026-03-15T10:00:00Z", "token_count": 12},
      {"role": "assistant", "content": "I'd be happy to help with your refund. Can you confirm the order amount?", "timestamp": "2026-03-15T10:00:05Z", "token_count": 18}
    ],
    "summary": null,
    "compression_count": 0,
    "total_tokens": 30,
    "max_tokens": 4096
  },

  "intent": {
    "primary": "refund",
    "secondary": ["billing", "order_inquiry"],
    "confidence": 0.92,
    "classified_at": "2026-03-15T10:00:01Z",
    "model_used": "meta-llama/llama-3-8b-instruct:free"
  },

  "collected_info": {
    "order_id": "12345",
    "order_amount": null,
    "reason": "product_defective",
    "customer_satisfaction": null,
    "missing_fields": ["order_amount"]
  },

  "resolution": {
    "status": "in_progress",
    "steps_completed": ["identify_intent", "collect_order_id", "collect_reason"],
    "steps_pending": ["verify_order", "calculate_refund", "execute_refund"],
    "current_step": "verify_order",
    "requires_approval": true,
    "approval_type": "refund",
    "estimated_refund_amount": null
  },

  "handoff": {
    "status": "ai_handling",
    "previous_handler": null,
    "handoff_reason": null,
    "handoff_timestamp": null
  },

  "metadata": {
    "channel": "chat",
    "language": "en",
    "customer_tier": "standard",
    "is_vip": false,
    "created_at": "2026-03-15T10:00:00Z",
    "updated_at": "2026-03-15T10:00:05Z",
    "last_activity_at": "2026-03-15T10:00:05Z",
    "context_health": "healthy",
    "suggest_new_chat": false,
    "version": 3
  }
}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/sessions/{session_id}/state` | Retrieve current GSD state (from Redis, fallback Postgres) |
| `PATCH` | `/api/sessions/{session_id}/state` | Apply a partial state delta (merged + validated) |
| `POST` | `/api/sessions/{session_id}/state/reset` | Reset conversation history, preserve metadata |
| `GET` | `/api/sessions/{session_id}/state/health` | Get context health metrics (token usage, thresholds) |
| `POST` | `/api/sessions/{session_id}/state/compress` | Manually trigger context compression |
| `POST` | `/api/sessions/bulk/health` | Get health metrics for all active sessions (admin) |

**Internal Service Interface (Python):**
```python
class GSDStateEngine:
    async def load_state(session_id: str) -> GSDState
    async def update_state(session_id: str, delta: dict) -> GSDState
    async def reset_conversation(session_id: str) -> GSDState
    async def compress_context(session_id: str, keep_last: int = 20) -> GSDState
    async def get_context_health(session_id: str) -> ContextHealth
    async def recover_from_postgres() -> int  # Returns count of recovered sessions
```

## Database Tables

### `sessions`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT uuid_generate_v4() | Session identifier |
| `company_id` | UUID | NOT NULL, FK → companies.id | Tenant isolation |
| `ticket_id` | UUID | FK → tickets.id, NULLABLE | Associated ticket |
| `customer_id` | UUID | FK → contacts.id, NULLABLE | Customer identifier |
| `state` | JSONB | NOT NULL | Full GSD state JSON |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'active' | active / idle / closed / compression_pending |
| `context_tokens` | INTEGER | NOT NULL, DEFAULT 0 | Current token count |
| `max_tokens` | INTEGER | NOT NULL, DEFAULT 4096 | Model context window size |
| `context_health` | VARCHAR(20) | NOT NULL, DEFAULT 'healthy' | healthy / warning / compressing / critical |
| `channel` | VARCHAR(20) | NOT NULL, DEFAULT 'chat' | chat / email / sms / voice / social |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Session creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last state update |

**Indexes:**
- `idx_sessions_company_id` ON `sessions(company_id)`
- `idx_sessions_ticket_id` ON `sessions(ticket_id)` WHERE `ticket_id IS NOT NULL`
- `idx_sessions_status_updated` ON `sessions(status, updated_at)` — for recovery queries
- `idx_sessions_company_active` ON `sessions(company_id, status)` WHERE `status != 'closed'`

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `GSD_REDIS_TTL` | 7200 | Redis key TTL in seconds (2 hours) |
| `GSD_IDLE_TIMEOUT` | 7200 | Session idle timeout before marking as idle |
| `GSD_MAX_TOKENS` | 4096 | Default context window size |
| `GSD_COMPRESSION_THRESHOLD` | 0.90 | Token usage % that triggers compression |
| `GSD_CRITICAL_THRESHOLD` | 0.95 | Token usage % that triggers new chat suggestion |
| `GSD_WARNING_THRESHOLD` | 0.70 | Token usage % that triggers warning log |
| `GSD_COMPRESSION_KEEP_LAST` | 20 | Number of recent messages to keep during compression |
| `GSD_RECOVERY_WINDOW_HOURS` | 2 | How far back to look for sessions to recover on restart |
| `GSD_STATE_VERSION` | 1 | Schema version for migration compatibility |

## Building Codes Applied

- **BC-008 (State Management — GSD Engine):** This feature IS the implementation of BC-008.
  - Rule 1: Dual storage (Redis + Postgres) on every state update — **FULLY IMPLEMENTED**
  - Rule 2: Recovery task on startup hydrates Redis from Postgres — **FULLY IMPLEMENTED**
  - Rule 3: Three context health thresholds (70%/90%/95%) — **FULLY IMPLEMENTED**
  - Rule 4: Dynamic context compression preserving key facts — **FULLY IMPLEMENTED**
  - Rule 5: Pydantic schema validation on every update — **FULLY IMPLEMENTED**
  - Rule 6: 2-hour idle timeout with summary on return — **FULLY IMPLEMENTED**
  - Rule 7: context_tokens updated on every interaction — **FULLY IMPLEMENTED**
  - Rule 8: Conversation history as role-content array — **FULLY IMPLEMENTED**
- **BC-001 (Multi-Tenant Isolation):**
  - Rule 1: All queries scoped by `company_id` — state reads/writes always filtered
  - Rule 7: Redis keys namespaced with `parwa:{company_id}:gsd:{session_id}`
  - Rule 8: Index on `company_id` on sessions table
- **BC-004 (Background Jobs):**
  - Rule 1: `company_id` as first parameter in recovery Celery task
  - Rule 2: Recovery task has `max_retries=3` with exponential backoff
  - Rule 8: Redis primary, Postgres fallback — dual write on every update
- **BC-012 (Error Handling & Resilience):**
  - Redis failure gracefully falls back to Postgres reads
  - Invalid state mutations return 422 with specific validation errors

## Edge Cases

1. **Redis crash during active session:** System falls back to Postgres for reads. State continues to be written to Postgres. When Redis recovers, the startup recovery task rehydrates all active sessions.
2. **Simultaneous updates to same session:** Uses optimistic locking with the `version` field in state. If version mismatch detected, the update is rejected with HTTP 409 Conflict, and the caller must reload and retry.
3. **Corrupted state JSON in Redis:** If `json.loads()` fails, the Redis key is deleted and state is recovered from Postgres. An error is logged and the incident is recorded in `task_logs`.
4. **Context compression loses critical data:** The compression prompt explicitly preserves fields listed in `resolution.steps_completed`, all `collected_info` keys with non-null values, and the `intent` block. A post-compression validation checks that these fields exist.
5. **Session recovery picks up stale data:** The recovery window is limited to 2 hours. Sessions idle for longer are marked as `idle` and require user confirmation before resuming.
6. **Token count exceeds max after a single large message:** If a single user message exceeds 30% of max_tokens, it is truncated with a `[message truncated: {length} characters]` marker and the full message is stored in `sessions.raw_message_log` for reference.

## Acceptance Criteria

1. **Dual-write verification:** Create a session, send 5 messages, kill Redis, send 1 more message. Verify all 6 messages are present when state is loaded from Postgres. Restart Redis and verify recovery task hydrates all active sessions.
2. **Context compression trigger:** Send 200 messages in a session to exceed 90% token threshold. Verify automatic compression fires, `compression_count` increments, and key facts (intent, collected_info, resolution.steps_completed) are preserved.
3. **Schema validation enforcement:** Attempt to PATCH state with `{"intent": {"primary": 123}}` (wrong type). Verify the update is rejected with 422 and the error message specifies the invalid field.
4. **Idle timeout behavior:** Create a session, wait 2h 5m, send a new message. Verify the session shows a conversation summary and offers to continue or start fresh.
5. **Optimistic locking:** Two concurrent PATCH requests to the same session. Verify one succeeds (200) and one fails (409) with a version mismatch message.
6. **Context health endpoint:** GET `/api/sessions/{id}/state/health` returns accurate token count, percentage, health status, and whether compression is recommended.
7. **Tenant isolation:** Create sessions for Tenant A and Tenant B. Attempt to GET Tenant B's session state using Tenant A's credentials. Verify 404 response.

---

# F-054: Smart Router (3-Tier LLM)

## Overview

The Smart Router classifies incoming request complexity and routes each request to the optimal LLM tier — Light for FAQ/classification/tagging, Medium for standard customer responses and summarization, and Heavy for complex reasoning, multi-step resolution, and knowledge synthesis. Using OpenRouter's free tier, the router maintains priority-ordered model lists per tier and transparently falls through to backup models when primary models hit rate limits or return errors. This ensures cost optimization (simple queries use cheap models) while maintaining quality (complex queries get powerful models).

## Architecture

**Three-Tier Routing Architecture:**

```
Incoming Request → Complexity Classifier (Light model)
    ├── Score ≤ 0.3 → LIGHT tier (fast, cheap)
    ├── Score 0.3–0.7 → MEDIUM tier (balanced)
    └── Score > 0.7 → HEAVY tier (powerful, expensive)

Each Tier:
    Model 1 (priority 1) ──→ try
    Model 2 (priority 2) ──→ fallback on 429/timeout/error
    Model 3 (priority 3) ──→ fallback
    ... (all models in tier exhausted) ──→ escalate to next tier

All Tiers Exhausted → Queue request + return "processing" to user
```

**LiteLLM Integration:** All model calls go through LiteLLM's unified interface, which normalizes request/response formats across providers. LiteLLM handles token counting, retry logic, and response parsing.

**Routing Decision Flow:**
1. Request arrives at `SmartRouter.route(company_id, messages, task_type, context)`
2. If `task_type` is explicitly specified (e.g., `"classify"`, `"generate_response"`), use the corresponding tier directly
3. If `task_type` is `"auto"`, run complexity classifier (Light tier) to score the request
4. Select tier based on score
5. Iterate through models in priority order for that tier
6. On each model: PII redact → LLM call → validate JSON → guardrails check → PII redact output → return
7. On failure (429, timeout, invalid JSON): try next model in same tier
8. On tier exhaustion: try next tier up
9. On all tiers exhausted: queue for retry

## Model Priority Lists

### Light Tier (Classification, Tagging, Sentiment)
| Priority | Model ID (OpenRouter) | Provider | Context Window | Use Case |
|----------|----------------------|----------|----------------|----------|
| 1 | `meta-llama/llama-3-8b-instruct:free` | Meta | 8K | Primary: intent classification, sentiment analysis |
| 2 | `mistralai/mistral-7b-instruct:free` | Mistral | 8K | Backup: classification, entity extraction |
| 3 | `google/gemma-2-9b-it:free` | Google | 8K | Fallback: tagging, language detection |

### Medium Tier (Standard Responses, Summarization)
| Priority | Model ID (OpenRouter) | Provider | Context Window | Use Case |
|----------|----------------------|----------|----------------|----------|
| 1 | `mistralai/mistral-7b-instruct:free` | Mistral | 8K | Primary: customer responses, summarization |
| 2 | `meta-llama/llama-3-8b-instruct:free` | Meta | 8K | Backup: email drafting, FAQ answers |
| 3 | `google/gemma-2-9b-it:free` | Google | 8K | Fallback: template filling, short responses |

### Heavy Tier (Complex Reasoning, Knowledge Synthesis)
| Priority | Model ID (OpenRouter) | Provider | Context Window | Use Case |
|----------|----------------------|----------|----------------|----------|
| 1 | `meta-llama/llama-3-8b-instruct:free` | Meta | 8K | Primary: multi-step reasoning with RAG context |
| 2 | `mistralai/mistral-7b-instruct:free` | Mistral | 8K | Backup: complex resolution paths |
| 3 | `google/gemma-2-9b-it:free` | Google | 8K | Fallback: edge case handling |

> **Note:** The Heavy tier on the free tier shares models with Light/Medium but uses larger context windows and more detailed system prompts. As the company scales, paid models (e.g., `anthropic/claude-3.5-sonnet`, `openai/gpt-4o`) will be added with higher priority.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/ai/route` | Route a request through the Smart Router |
| `GET` | `/api/ai/models` | List all configured models with status and tier |
| `PUT` | `/api/ai/models/{model_id}/priority` | Update model priority within tier |
| `POST` | `/api/ai/models/{model_id}/disable` | Temporarily disable a model |
| `GET` | `/api/ai/models/health` | Real-time health dashboard of all models |
| `POST` | `/api/ai/classify-complexity` | Manually classify request complexity |

**POST `/api/ai/route` Request Body:**
```json
{
  "company_id": "uuid",
  "session_id": "uuid",
  "messages": [
    {"role": "system", "content": "You are a helpful customer support agent..."},
    {"role": "user", "content": "I need a refund for my order #12345"}
  ],
  "task_type": "auto",
  "context": {
    "ticket_id": "uuid",
    "customer_tier": "vip",
    "knowledge_context": "..."
  },
  "response_format": {"type": "json_object"},
  "max_tokens": 500
}
```

## Database Tables

### `api_providers`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT uuid_generate_v4() | Provider record ID |
| `company_id` | UUID | NULLABLE, FK → companies.id | NULL = global, UUID = tenant-specific override |
| `model_id` | VARCHAR(100) | NOT NULL, UNIQUE | OpenRouter model identifier |
| `provider` | VARCHAR(50) | NOT NULL | meta / mistral / google / anthropic / openai |
| `tier` | VARCHAR(10) | NOT NULL | light / medium / heavy |
| `priority` | INTEGER | NOT NULL, DEFAULT 10 | Lower = higher priority |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true | Can be disabled without deletion |
| `context_window` | INTEGER | NOT NULL | Max token context window |
| `max_output_tokens` | INTEGER | NOT NULL | Max output tokens |
| `cost_per_1k_input` | DECIMAL(8,4) | DEFAULT 0.0000 | Cost tracking (0 for free tier) |
| `cost_per_1k_output` | DECIMAL(8,4) | DEFAULT 0.0000 | Cost tracking |
| `rate_limit_rpm` | INTEGER | DEFAULT 20 | Requests per minute limit |
| `rate_limit_tpm` | INTEGER | DEFAULT 40000 | Tokens per minute limit |
| `config` | JSONB | DEFAULT '{}' | Additional model-specific config |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Record creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update |

**Indexes:**
- `idx_api_providers_tier_priority` ON `api_providers(tier, priority)` WHERE `is_active = true`
- `idx_api_providers_company` ON `api_providers(company_id)` WHERE `company_id IS NOT NULL`

### `model_usage_logs`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Log entry ID |
| `company_id` | UUID | NOT NULL, FK → companies.id | Tenant |
| `session_id` | UUID | NULLABLE | Session (if applicable) |
| `model_id` | VARCHAR(100) | NOT NULL | Model used |
| `tier` | VARCHAR(10) | NOT NULL | Tier used |
| `task_type` | VARCHAR(50) | NOT NULL | classify / respond / summarize / reason |
| `input_tokens` | INTEGER | NOT NULL | Tokens sent |
| `output_tokens` | INTEGER | NOT NULL | Tokens received |
| `latency_ms` | INTEGER | NOT NULL | Response time |
| `status` | VARCHAR(20) | NOT NULL | success / rate_limited / error / fallback |
| `error_message` | TEXT | NULLABLE | Error details if failed |
| `fallback_model` | VARCHAR(100) | NULLABLE | Model fell back to (if applicable) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Timestamp |

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SMART_ROUTER_DEFAULT_TIER` | `medium` | Default tier when task_type is ambiguous |
| `SMART_ROUTER_TIMEOUT_MS` | 30000 | Per-model call timeout in milliseconds |
| `SMART_ROUTER_MAX_RETRIES` | 2 | Retries per model before falling to next |
| `SMART_ROUTER_COMPLEXITY_THRESHOLD_LOW` | 0.3 | Below this → Light tier |
| `SMART_ROUTER_COMPLEXITY_THRESHOLD_HIGH` | 0.7 | Above this → Heavy tier |
| `SMART_ROUTER_QUEUE_EXPIRY` | 300 | Queued request expiry in seconds |
| `OPENROUTER_API_KEY` | env var | OpenRouter API key |
| `LITELLM_DROP_PARAMS` | `true` | Drop unsupported params for model compatibility |

## Technique Integration (BC-013)

The Smart Router and Technique Router (BC-013) are **separate, complementary systems** that both execute for every query. Understanding their distinct responsibilities is critical:

- **Smart Router (F-054)** selects which **MODEL** to use — Light, Medium, or Heavy tier — based on request complexity classification.
- **Technique Router (BC-013)** selects which **TECHNIQUE** to apply — such as Chain-of-Thought (F-140), ReAct (F-141), Reverse Thinking (F-141), etc. — based on query signals, intent, confidence, and sentiment.

**Execution Flow:**
```
Incoming Request
    │
    ├──► Smart Router (F-054) ──► SELECTS MODEL (Light/Medium/Heavy)
    │
    └──► Technique Router (BC-013) ──► SELECTS TECHNIQUE(s) (CoT, ReAct, UoT, etc.)

Both decisions are made in parallel and combined for the final LLM call:
  Selected Model + Selected Technique(s) → Enhanced LLM Prompt → Response
```

The Smart Router passes the following **query signals** to the Technique Router for technique selection:
- Complexity score (0.0–1.0) from the complexity classifier
- Selected tier (light/medium/heavy)
- Task type (classify/respond/summarize/reason)
- Context metadata (intent, sentiment, customer tier)

These signals inform the Technique Router's decision about which reasoning techniques to activate for the current query.

## Building Codes Applied

- **BC-007 (AI Model Interaction — Smart Router):** This feature IS the implementation of BC-007.
  - Rule 1: Priority-ordered model lists per tier — **FULLY IMPLEMENTED** (see Model Priority Lists)
  - Rule 2: Model config in `api_providers` table, admin-managed — **FULLY IMPLEMENTED**
  - Rule 3: 429 triggers next model in tier, then next tier — **FULLY IMPLEMENTED**
  - Rule 4: All models rate-limited → queue + immediate "processing" response — **FULLY IMPLEMENTED**
  - Rule 5: PII redaction before LLM call (delegated to F-056) — **INTEGRATION POINT**
  - Rule 6: Guardrails check before delivery (delegated to F-057) — **INTEGRATION POINT**
  - Rule 7: Manager review queue for blocked responses — **INTEGRATION POINT** (F-058)
  - Rule 8: Invalid JSON retry with simplified prompt — **FULLY IMPLEMENTED**
  - Rule 9: Confidence thresholds per company — **INTEGRATION POINT** (F-059)
  - Rule 10: Training feedback threshold LOCKED at 50 — **INTEGRATION POINT** (F-100)
- **BC-013 (Technique Router Integration):** Smart Router passes complexity score, selected tier, task type, and context metadata to the Technique Router for technique selection — **INTEGRATION POINT**
- **BC-001 (Multi-Tenant Isolation):** All queries scoped by `company_id`; tenant-specific model overrides supported
- **BC-004 (Background Jobs):** Queued requests processed via Celery with retry logic
- **BC-012 (Error Handling & Resilience):** Graceful degradation through tier fallback chain

## Edge Cases

1. **All free-tier models rate-limited simultaneously:** Request is queued in Redis with key `parwa:{company_id}:queue:{request_id}` with a 5-minute TTL. User receives: "Your request is being processed. We'll respond shortly." A Celery beat task processes the queue every 30 seconds.
2. **Model returns content in wrong language:** Post-processing step checks if response language matches `session.metadata.language`. If mismatch, request is retried with an explicit language instruction appended to the system prompt.
3. **OpenRouter API key rotation:** The system maintains up to 3 API keys in rotation. If key 1 fails auth, key 2 is tried immediately. Failed keys are flagged and retried after 5 minutes.
4. **LiteLLM version compatibility issue:** If LiteLLM raises an unexpected error for a model, the model is temporarily disabled for 10 minutes and the incident is logged to `model_usage_logs` with status `error`.
5. **Request exceeds model context window:** If `input_tokens > model.context_window - 200`, the request is automatically escalated to a model with a larger context window. If none available, context compression is triggered before retrying.
6. **Tenant-specific model override conflicts:** If a tenant has a custom model config for a tier, it completely replaces the global list for that tenant. Admins are warned if the custom list has fewer than 2 models.

## Acceptance Criteria

1. **Tier routing accuracy:** Submit 10 FAQ queries — verify ≥ 8 route to Light tier. Submit 10 complex multi-step queries — verify ≥ 8 route to Heavy tier.
2. **Rate limit failover:** Configure 3 models in Light tier. Simulate 429 on model 1. Verify model 2 is tried immediately. Simulate 429 on model 2. Verify model 3 is used. Simulate 429 on model 3. Verify escalation to Medium tier.
3. **Model disable/enable:** Disable model 1 via API. Route a Light-tier request. Verify model 2 is used. Re-enable model 1. Verify model 1 is used again.
4. **Admin model management:** Add a new model, set priority, assign to tier via API. Verify it appears in the routing pool. Remove it. Verify it is no longer used.
5. **Usage logging:** Process 50 requests across all tiers. Verify `model_usage_logs` has 50 entries with accurate token counts, latency, and status.
6. **Queue behavior:** Simulate all models rate-limited. Verify user receives "processing" message. Verify queued request is processed within 30 seconds when a model becomes available.
7. **Invalid JSON handling:** Configure a model to return malformed JSON. Verify the retry-with-simplified-prompt fires. If still invalid, verify fallback template is returned.

---

# F-055: Model Failover & Rate Limit Handling

## Overview

Model Failover & Rate Limit Handling provides the resilience layer that ensures PARWA never drops a conversation due to model unavailability. It monitors every LLM call for rate limits (429), timeouts, authentication errors, and degraded responses, then transparently switches to backup models or providers without any user-visible interruption. The system also implements circuit breaker patterns to avoid hammering already-overloaded models, and maintains a real-time health dashboard that tracks per-model success rates, latency percentiles, and error rates.

## Architecture

**Circuit Breaker Pattern:**
```
For each model, maintain a CircuitBreaker state:
  CLOSED (healthy) → normal operation
    └── 5 consecutive failures → OPEN (tripped)
  OPEN (tripped) → reject all requests immediately, use fallback
    └── after 60s cooldown → HALF_OPEN (probing)
  HALF_OPEN (probing) → allow 1 test request
    └── success → CLOSED
    └── failure → OPEN (reset cooldown timer)
```

**Failover Decision Tree:**
```
Model Call:
  ├── 200 OK → Validate response → Return
  ├── 429 Rate Limited → Log + CircuitBreaker.record_failure()
  │   ├── Next model in same tier available → try next
  │   ├── Same tier exhausted → escalate to next tier
  │   └── All tiers exhausted → queue request
  ├── 401/403 Auth Error → Disable model permanently, alert ops
  ├── 500/502/503 Server Error → CircuitBreaker.record_failure()
  │   └── Same cascade as 429
  ├── Timeout (>30s) → CircuitBreaker.record_failure()
  │   └── Same cascade as 429
  └── Unexpected Error → Log full traceback, CircuitBreaker.record_failure()
      └── Same cascade as 429
```

**Health Monitoring:**
- Per-model metrics tracked in Redis with 1-minute rolling windows:
  - `parwa:health:{model_id}:success_count`
  - `parwa:health:{model_id}:error_count`
  - `parwa:health:{model_id}:total_latency_ms`
  - `parwa:health:{model_id}:rate_limit_count`
- Aggregated every minute by a Celery beat task and stored in `model_health_snapshots`
- System Status Panel (F-088) consumes these snapshots for real-time display

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/ai/health` | Overall system health summary |
| `GET` | `/api/ai/health/models` | Per-model health with circuit breaker states |
| `GET` | `/api/ai/health/models/{model_id}` | Detailed health for specific model |
| `POST` | `/api/ai/health/models/{model_id}/reset-circuit` | Manually reset circuit breaker |
| `GET` | `/api/ai/failover-log` | Recent failover events (paginated) |
| `POST` | `/api/ai/test-model/{model_id}` | Send a test prompt to verify model is responsive |

### `GET /api/ai/health/models` Response:
```json
{
  "models": [
    {
      "model_id": "meta-llama/llama-3-8b-instruct:free",
      "tier": "light",
      "circuit_state": "closed",
      "success_rate_1m": 0.98,
      "success_rate_5m": 0.95,
      "avg_latency_ms": 1200,
      "p95_latency_ms": 2800,
      "errors_last_minute": 2,
      "rate_limits_last_minute": 0,
      "consecutive_failures": 0,
      "last_failure_at": null,
      "cooldown_ends_at": null,
      "is_healthy": true
    }
  ],
  "system_healthy": true,
  "active_models": 6,
  "degraded_models": 1,
  "offline_models": 0,
  "checked_at": "2026-03-15T10:00:00Z"
}
```

## Database Tables

### `model_health_snapshots`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Snapshot ID |
| `model_id` | VARCHAR(100) | NOT NULL | Model identifier |
| `circuit_state` | VARCHAR(20) | NOT NULL | closed / open / half_open |
| `success_count` | INTEGER | NOT NULL, DEFAULT 0 | Successful calls in window |
| `error_count` | INTEGER | NOT NULL, DEFAULT 0 | Failed calls in window |
| `rate_limit_count` | INTEGER | NOT NULL, DEFAULT 0 | 429 responses in window |
| `total_latency_ms` | BIGINT | NOT NULL, DEFAULT 0 | Cumulative latency in window |
| `call_count` | INTEGER | NOT NULL, DEFAULT 0 | Total calls in window |
| `consecutive_failures` | INTEGER | NOT NULL, DEFAULT 0 | Current consecutive failure streak |
| `window_start` | TIMESTAMPTZ | NOT NULL | Start of aggregation window |
| `window_end` | TIMESTAMPTZ | NOT NULL | End of aggregation window |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Snapshot timestamp |

**Indexes:**
- `idx_model_health_model_time` ON `model_health_snapshots(model_id, created_at DESC)`
- Retention: 30 days via Celery beat cleanup task

### `failover_events`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Event ID |
| `company_id` | UUID | NOT NULL | Tenant |
| `session_id` | UUID | NULLABLE | Session |
| `from_model` | VARCHAR(100) | NOT NULL | Model that failed |
| `to_model` | VARCHAR(100) | NOT NULL | Model fell back to |
| `reason` | VARCHAR(50) | NOT NULL | rate_limit / timeout / auth_error / server_error / invalid_response |
| `error_detail` | TEXT | NULLABLE | Error message or stack trace |
| `latency_ms` | INTEGER | NULLABLE | Time spent on failed call |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Event timestamp |

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | 5 | Consecutive failures to trip circuit |
| `CIRCUIT_BREAKER_COOLDOWN_SECS` | 60 | Seconds before trying HALF_OPEN |
| `CIRCUIT_BREAKER_HALF_OPEN_MAX_TESTS` | 1 | Test requests allowed in HALF_OPEN |
| `MODEL_CALL_TIMEOUT_MS` | 30000 | Per-model call timeout |
| `RATE_LIMIT_BACKOFF_BASE_MS` | 1000 | Base backoff after rate limit |
| `HEALTH_SNAPSHOT_INTERVAL_SECS` | 60 | How often to aggregate health metrics |
| `HEALTH_RETENTION_DAYS` | 30 | Days to keep health snapshots |
| `MODEL_DISABLE_ALERT_THRESHOLD` | 10 | Failures in 5 min to trigger ops alert |

## Building Codes Applied

- **BC-007 (AI Model Interaction):** Rules 3-4 (429 handling, queue fallback) — **FULLY IMPLEMENTED**
- **BC-004 (Background Jobs):** Health snapshot aggregation via Celery beat; circuit breaker state cleanup via scheduled task
- **BC-012 (Error Handling & Resilience):** Circuit breaker prevents cascading failures; auth errors trigger permanent model disable with ops alert
- **BC-001 (Multi-Tenant Isolation):** Failover events and health snapshots are tenant-scoped where applicable

## Edge Cases

1. **Cascading rate limits across all providers:** Circuit breakers trip on all models within seconds. All requests are queued. The queue processor holds requests for up to 5 minutes, then returns a graceful degradation message: "Our AI assistant is experiencing high demand. A human agent will be notified."
2. **Model returns 200 but with degraded quality:** Response validation checks for empty responses, responses under 10 tokens, and responses containing error phrases (e.g., "I'm sorry, I can't", "As an AI language model"). Degraded responses are treated as failures for circuit breaker purposes but are still delivered to the user with a confidence penalty.
3. **Half-open state test request fails:** Circuit immediately returns to OPEN state. Cooldown timer resets to full 60 seconds. The test failure is logged to `failover_events`.
4. **Model auth error during active conversation:** Model is permanently disabled (not circuit-breaker cooldown). Ops team is alerted via email. All active requests using that model are immediately rerouted to next available model.
5. **Multiple tenants competing for same free-tier rate limits:** Rate limits are tracked globally (not per-tenant) since OpenRouter free tier shares limits. The system uses a global token bucket algorithm to fairly distribute capacity across tenants when limits are approaching.

## Acceptance Criteria

1. **Circuit breaker tripping:** Simulate 5 consecutive failures on a model. Verify circuit opens (state = "open"). Verify no requests are sent to that model. Verify cooldown timer starts.
2. **Circuit breaker recovery:** After cooldown, verify circuit enters HALF_OPEN. Send 1 test request that succeeds. Verify circuit closes and model returns to normal rotation.
3. **Cross-tier escalation:** Trip circuits on all Light-tier models. Submit a Light-tier request. Verify it is automatically escalated to Medium tier. Verify the escalation is logged in `failover_events`.
4. **Health dashboard accuracy:** Process 100 requests (90 success, 5 rate limits, 5 timeouts) for a model. Verify health endpoint shows correct success rate (~90%), error counts, and latency stats.
5. **Manual circuit reset:** Trip a circuit breaker. Call `POST /api/ai/health/models/{id}/reset-circuit`. Verify circuit immediately closes without waiting for cooldown.
6. **Queue processing under duress:** Trip all circuits. Queue 20 requests. Restore one model. Verify queue is processed in FIFO order within 60 seconds.
7. **Auth error permanent disable:** Simulate 401 on a model. Verify model is permanently disabled and ops alert is sent. Verify it does not recover via circuit breaker.

---

# F-056: PII Redaction Engine

## Overview

The PII Redaction Engine scans all text entering and leaving the PARWA system for personally identifiable information — email addresses, phone numbers, credit card numbers, Social Security numbers, IP addresses, and other sensitive patterns. Before any text is sent to an LLM or stored in the database, PII is replaced with deterministic placeholders (e.g., `[EMAIL_1]`, `[PHONE_2]`). The original values are stored in a secure, encrypted vault keyed by session ID, enabling restoration when displaying text back to authorized agents. This prevents PII leakage to LLM providers, ensures GDPR compliance, and protects customer data at rest.

## Architecture

**Dual-Direction Redaction Pipeline:**
```
INGRESS (User → System):
  Raw text → regex scan → identify PII entities → replace with placeholders
    → store mapping in vault → return redacted text

EGRESS (System → User):
  Redacted text → look up placeholders in vault → restore original values
    → return clean text to user

STORAGE (System → Database):
  Redacted text → store as-is (no PII in DB)

LLM CALL (System → Model):
  Redacted text → send to model → receive response (may contain placeholder references)
    → no restoration needed (model sees placeholders)
```

**Redaction Flow:**
```
Input: "My email is john@example.com and my card is 4111-1111-1111-1111. Call me at (555) 123-4567."

Step 1 - Scan: Apply all regex patterns in priority order
Step 2 - Map:  {EMAIL_1: "john@example.com", CREDIT_CARD_1: "4111-1111-1111-1111", PHONE_1: "(555) 123-4567"}
Step 3 - Replace: "My email is [EMAIL_1] and my card is [CREDIT_CARD_1]. Call me at [PHONE_1]."
Step 4 - Vault: Store mapping encrypted under session key
Step 5 - Return: Redacted text + entity count

Output for LLM: "My email is [EMAIL_1] and my card is [CREDIT_CARD_1]. Call me at [PHONE_1]."
Output for DB: Same (redacted)
Output for User: "My email is john@example.com and my card is 4111-1111-1111-1111. Call me at (555) 123-4567."
```

## PII Regex Patterns

```python
PII_PATTERNS = {
    # Email addresses
    "EMAIL": {
        "pattern": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "placeholder": "EMAIL",
        "priority": 1
    },
    # US Social Security Number (XXX-XX-XXXX)
    "SSN": {
        "pattern": r'\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b',
        "placeholder": "SSN",
        "priority": 2
    },
    # Credit Card Numbers (Visa, Mastercard, Amex, Discover)
    "CREDIT_CARD": {
        "pattern": r'\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|3[47]\d{13}|6(?:011|5\d{2})\d{12})\b',
        "placeholder": "CREDIT_CARD",
        "priority": 2
    },
    # US Phone Numbers (multiple formats)
    "PHONE": {
        "pattern": r'\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        "placeholder": "PHONE",
        "priority": 3
    },
    # International Phone Numbers
    "PHONE_INTL": {
        "pattern": r'\b\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b',
        "placeholder": "PHONE",
        "priority": 3
    },
    # IPv4 Addresses
    "IPV4": {
        "pattern": r'\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b',
        "placeholder": "IP_ADDRESS",
        "priority": 4
    },
    # Date of Birth (MM/DD/YYYY, DD-MM-YYYY)
    "DOB": {
        "pattern": r'\b(?:0[1-9]|1[0-2])[/\-](?:0[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b',
        "placeholder": "DATE_OF_BIRTH",
        "priority": 4
    },
    # US Mailing Address (street + zip pattern)
    "ADDRESS": {
        "pattern": r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Road|Rd|Court|Ct)\b',
        "placeholder": "ADDRESS",
        "priority": 5
    },
    # ZIP Codes (5-digit and ZIP+4)
    "ZIP_CODE": {
        "pattern": r'\b\d{5}(?:[-\s]\d{4})?\b',
        "placeholder": "ZIP_CODE",
        "priority": 5
    },
    # Driver's License (generic pattern for US states)
    "DRIVERS_LICENSE": {
        "pattern": r'\b[A-Z]{1,2}\d{6,8}\b',
        "placeholder": "DRIVERS_LICENSE",
        "priority": 5
    },
    # Bank Account Numbers (8-17 digits)
    "BANK_ACCOUNT": {
        "pattern": r'\b\d{8,17}\b',
        "placeholder": "BANK_ACCOUNT",
        "priority": 5,
        "context_required": True  # Only match near banking keywords
    },
    # Passport Numbers (US format)
    "PASSPORT": {
        "pattern": r'\b\d{9}\b',
        "placeholder": "PASSPORT",
        "priority": 5,
        "context_required": True
    }
}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/pii/redact` | Redact PII from input text |
| `POST` | `/api/pii/restore` | Restore PII from redacted text |
| `POST` | `/api/pii/scan` | Scan text for PII without redacting (audit) |
| `GET` | `/api/pii/vault/{session_id}` | View PII vault for a session (admin/agent only) |
| `DELETE` | `/api/pii/vault/{session_id}` | Purge PII vault for a session (GDPR compliance) |
| `GET` | `/api/pii/stats` | PII detection statistics (admin) |

**POST `/api/pii/redact` Request/Response:**
```json
// Request
{
  "company_id": "uuid",
  "session_id": "uuid",
  "text": "Contact john@example.com or call (555) 123-4567",
  "direction": "ingress"
}

// Response
{
  "redacted_text": "Contact [EMAIL_1] or call [PHONE_1]",
  "entities_found": 2,
  "entities": [
    {"type": "EMAIL", "placeholder": "[EMAIL_1]", "start": 8, "end": 24},
    {"type": "PHONE", "placeholder": "[PHONE_1]", "start": 33, "end": 47}
  ],
  "vault_key": "parwa:{company_id}:pii_vault:{session_id}"
}
```

## Database Tables

### `pii_vault` (Encrypted at rest via pgcrypto)
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Vault entry ID |
| `company_id` | UUID | NOT NULL, FK → companies.id | Tenant |
| `session_id` | UUID | NOT NULL | Session (for grouping) |
| `entity_type` | VARCHAR(30) | NOT NULL | EMAIL / PHONE / SSN / etc. |
| `placeholder` | VARCHAR(30) | NOT NULL | e.g., EMAIL_1 |
| `original_value` | TEXT | NOT NULL | Encrypted original PII value |
| `direction` | VARCHAR(10) | NOT NULL | ingress / egress |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Detection timestamp |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Auto-purge after session close + 30 days |

**Indexes:**
- `idx_pii_vault_session` ON `pii_vault(session_id)`
- `idx_pii_vault_company` ON `pii_vault(company_id)`
- `idx_pii_vault_expires` ON `pii_vault(expires_at)` — for cleanup task

### `pii_detection_stats`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Stat ID |
| `company_id` | UUID | NOT NULL | Tenant |
| `entity_type` | VARCHAR(30) | NOT NULL | PII type |
| `detection_count` | INTEGER | NOT NULL, DEFAULT 0 | Count detected |
| `redaction_count` | INTEGER | NOT NULL, DEFAULT 0 | Count redacted |
| `false_positive_count` | INTEGER | NOT NULL, DEFAULT 0 | Count of false positives reported |
| `date` | DATE | NOT NULL | Aggregation date |

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `PII_VAULT_ENCRYPTION_KEY` | env var | AES-256 key for pgcrypto encryption |
| `PII_VAULT_RETENTION_DAYS` | 30 | Days to retain vault entries after session close |
| `PII_SCAN_CACHE_TTL` | 300 | Seconds to cache redaction results for identical text |
| `PII_CONTEXT_KEYWORDS_BANKING` | `["account", "routing", "bank", " aba"]` | Keywords for contextual PII matching |
| `PII_CONTEXT_KEYWORDS_TRAVEL` | `["passport", "travel", "flight", "visa"]` | Keywords for contextual PII matching |
| `PII_ENABLE_NER` | `false` | Enable Named Entity Recognition model (optional, heavier) |
| `PII_REGEX_MAX_ITERATIONS` | 10 | Max passes for pattern matching (prevents infinite loops) |

## Building Codes Applied

- **BC-007 (AI Model Interaction):** Rule 5 — PII redaction before LLM call and before DB storage — **FULLY IMPLEMENTED**
- **BC-010 (Data Lifecycle & Compliance):** Vault entries auto-purge after retention period; Right to be Forgotten triggers vault purge
- **BC-011 (Authentication & Security):** PII vault encrypted at rest via pgcrypto; vault access requires admin/agent role
- **BC-001 (Multi-Tenant Isolation):** All vault queries scoped by `company_id`; Redis vault keys namespaced with tenant

## Edge Cases

1. **PII in code blocks or technical content:** ZIP codes and account numbers may appear in order IDs or technical references. Context-required patterns (BANK_ACCOUNT, PASSPORT) only match when banking/travel keywords appear within 50 characters.
2. **Nested or overlapping PII:** An email like `john@123.45.67.89.com` could match both EMAIL and IPV4 patterns. Patterns are applied in priority order — EMAIL (priority 1) matches first, and the matched text is excluded from subsequent pattern scans.
3. **PII re-insertion by LLM:** If an LLM generates text containing raw PII (e.g., restating the customer's email from context), the egress redaction pass catches it. The system runs redaction on ALL outgoing text, not just LLM responses.
4. **Vault unavailable:** If the encrypted vault DB is unreachable, the system still performs regex-based redaction (placeholders are generated), but restoration is deferred. An alert is sent to ops. Redacted text is stored and can be restored once the vault is back.
5. **False positives on order IDs:** Order IDs like `1234-5678-9012-3456` could match credit card patterns. The Luhn algorithm is applied as a secondary validation — if the number doesn't pass Luhn check, it is NOT flagged as a credit card.
6. **Multi-language PII:** The regex patterns above cover English/Latin scripts. For non-Latin names and addresses, the optional NER model (spaCy with multilingual model) is available when `PII_ENABLE_NER=true`.

## Acceptance Criteria

1. **Email redaction:** Input: "Contact john.doe+test@example.co.uk". Output: "Contact [EMAIL_1]". Vault contains original value encrypted.
2. **Credit card with Luhn validation:** Input: "Card: 4111-1111-1111-1111" (valid Luhn) → redacted. Input: "Card: 4111-1111-1111-1112" (invalid Luhn) → NOT redacted.
3. **Bidirectional redaction:** Redact text → store in DB → restore for user display. Verify restored text matches original exactly.
4. **SSN false negative prevention:** Input: "My SSN is 078-05-1120" (commonly used test SSN). Verify it is redacted. (Note: 000-XX-XXXX, 666-XX-XXXX, 9XX-XX-XXXX are excluded per regex.)
5. **Nested pattern handling:** Input: "Email john@test.com and IP 192.168.1.1". Verify EMAIL matches first, then IPV4 matches separately — no overlap.
6. **Vault purge compliance:** Close a session. After 30 days, verify vault entries for that session are automatically purged by the Celery cleanup task.
7. **Context-required pattern:** Input: "My reference number is 123456789" (no banking keyword) → NOT flagged as BANK_ACCOUNT. Input: "My bank account is 123456789" → flagged as BANK_ACCOUNT.

---

# F-057: Guardrails AI (Content Safety)

## Overview

Guardrails AI is a multi-layer content safety system that evaluates every AI-generated response before it reaches a customer. It blocks harmful content (violence, hate speech, illegal activity), hallucinated responses (claims not supported by the knowledge base), off-topic responses (unrelated to the customer's query), and policy violations (promises the AI can't fulfill, such as guaranteed refunds beyond policy). When a response is blocked, the system falls back to a safe template, logs the event for manager review, and feeds the data back into the DSPy prompt optimization pipeline (F-061) for continuous improvement.

## Architecture

**Multi-Layer Guardrail Pipeline:**
```
LLM Response Generated
    │
    ├── Layer 1: Toxicity Check (regex + keyword matching)
    │   ├── Block: violence, hate speech, profanity, self-harm language
    │   └── Pass → Layer 2
    │
    ├── Layer 2: Hallucination Detection (RAG grounding check)
    │   ├── Extract factual claims from response
    │   ├── Verify each claim against retrieved knowledge base chunks
    │   ├── If claim confidence < threshold → flag as hallucination
    │   └── Pass → Layer 3
    │
    ├── Layer 3: Topic Relevance Check
    │   ├── Compare response topic with customer's stated intent
    │   ├── If relevance score < threshold → flag as off-topic
    │   └── Pass → Layer 4
    │
    ├── Layer 4: Policy Compliance Check
    │   ├── Check for unauthorized promises (refund guarantees, SLA commitments)
    │   ├── Check for competitor mentions or disparagement
    │   ├── Check for legal/medical/financial advice
    │   └── Pass → Layer 5
    │
    ├── Layer 5: Brand Voice Check
    │   ├── Verify tone matches configured brand guidelines
    │   ├── Check for overly casual or overly formal language
    │   └── Pass → Deliver to customer
    │
    └── Any layer blocks → Safe Fallback + Log + Queue for review
```

**Hallucination Detection Sub-System:**
```
Response: "Your order #12345 was shipped on March 10th via FedEx and will arrive by March 15th."

Step 1 - Extract claims: ["order #12345 exists", "shipped March 10th", "via FedEx", "arrives by March 15th"]
Step 2 - RAG verification:
    claim 1: Knowledge base confirms order #12345 → grounded ✓
    claim 2: Knowledge base says shipped March 12th → CONFLICT ✗
    claim 3: Knowledge base says via UPS → CONFLICT ✗
    claim 4: Knowledge base says arrives by March 17th → CONFLICT ✗
Step 3 - Grounding score: 1/4 = 0.25 (below threshold of 0.6)
Step 4 - Action: BLOCK as hallucination, rewrite with grounded facts only
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/guardrails/evaluate` | Evaluate a response against all guardrail layers |
| `GET` | `/api/guardrails/blocked` | List recently blocked responses (paginated, admin) |
| `GET` | `/api/guardrails/blocked/{block_id}` | Get full details of a blocked response |
| `POST` | `/api/guardrails/blocked/{block_id}/release` | Release a blocked response (passes through 2nd check) |
| `POST` | `/api/guardrails/blocked/{block_id}/ban-pattern` | Permanently ban the blocking pattern |
| `GET` | `/api/guardrails/rules` | List all active guardrail rules |
| `PUT` | `/api/guardrails/rules/{rule_id}` | Update a guardrail rule (threshold, enabled) |
| `GET` | `/api/guardrails/stats` | Guardrail statistics (block rate by layer, trends) |

**POST `/api/guardrails/evaluate` Response:**
```json
{
  "passed": false,
  "layers": [
    {"name": "toxicity", "passed": true, "score": 0.02, "details": null},
    {"name": "hallucination", "passed": false, "score": 0.25, "details": {
      "claims_checked": 4,
      "claims_grounded": 1,
      "conflicts": [
        {"claim": "shipped March 10th", "grounding_fact": "shipped March 12th"},
        {"claim": "via FedEx", "grounding_fact": "via UPS"}
      ]
    }},
    {"name": "relevance", "passed": true, "score": 0.88, "details": null},
    {"name": "policy", "passed": true, "score": 0.0, "details": null},
    {"name": "brand_voice", "passed": true, "score": 0.91, "details": null}
  ],
  "blocking_layer": "hallucination",
  "blocking_reason": "Response contains 3 ungrounded factual claims",
  "fallback_response": "I'd like to help you with your order. Let me verify the shipping details before I provide an update. One moment please.",
  "block_id": "uuid"
}
```

## Database Tables

### `guardrail_blocks`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Block event ID |
| `company_id` | UUID | NOT NULL, FK → companies.id | Tenant |
| `session_id` | UUID | NOT NULL | Session |
| `ticket_id` | UUID | NULLABLE | Ticket |
| `model_id` | VARCHAR(100) | NOT NULL | Model that generated the response |
| `original_prompt` | TEXT | NOT NULL | The prompt sent to the LLM |
| `original_response` | TEXT | NOT NULL | The blocked response |
| `blocking_layer` | VARCHAR(30) | NOT NULL | toxicity / hallucination / relevance / policy / brand_voice |
| `blocking_reason` | TEXT | NOT NULL | Human-readable reason |
| `layer_scores` | JSONB | NOT NULL | Scores from all layers |
| `fallback_used` | TEXT | NOT NULL | Safe template that was sent instead |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'pending_review' | pending_review / released / permanently_banned |
| `reviewed_by` | UUID | NULLABLE, FK → users.id | Admin who reviewed |
| `reviewed_at` | TIMESTAMPTZ | NULLABLE | Review timestamp |
| `review_action` | VARCHAR(20) | NULLABLE | released / confirmed_block / edited_released |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Block timestamp |

**Indexes:**
- `idx_guardrail_blocks_company_status` ON `guardrail_blocks(company_id, status)`
- `idx_guardrail_blocks_layer` ON `guardrail_blocks(blocking_layer, created_at DESC)`
- `idx_guardrail_blocks_session` ON `guardrail_blocks(session_id)`

### `guardrail_rules`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Rule ID |
| `company_id` | UUID | NULLABLE | NULL = global rule, UUID = tenant override |
| `layer` | VARCHAR(30) | NOT NULL | Guardrail layer |
| `rule_type` | VARCHAR(30) | NOT NULL | keyword_list / regex / threshold / policy_pattern |
| `pattern` | TEXT | NOT NULL | Regex pattern, keyword list (JSON), or threshold value |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true | Can be disabled |
| `severity` | VARCHAR(10) | NOT NULL, DEFAULT 'block' | block / warn / log |
| `description` | TEXT | NOT NULL | Human-readable rule description |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Rule creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update |

### `guardrail_stats` (Aggregated daily)
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Stat ID |
| `company_id` | UUID | NOT NULL | Tenant |
| `date` | DATE | NOT NULL | Aggregation date |
| `total_evaluated` | INTEGER | NOT NULL, DEFAULT 0 | Total responses checked |
| `total_blocked` | INTEGER | NOT NULL, DEFAULT 0 | Total blocked |
| `toxicity_blocks` | INTEGER | NOT NULL, DEFAULT 0 | Blocked by toxicity |
| `hallucination_blocks` | INTEGER | NOT NULL, DEFAULT 0 | Blocked by hallucination |
| `relevance_blocks` | INTEGER | NOT NULL, DEFAULT 0 | Blocked by relevance |
| `policy_blocks` | INTEGER | NOT NULL, DEFAULT 0 | Blocked by policy |
| `brand_voice_blocks` | INTEGER | NOT NULL, DEFAULT 0 | Blocked by brand voice |
| `release_rate` | DECIMAL(5,4) | NOT NULL, DEFAULT 0.0 | % of blocked items released by admin |

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `GUARDRAIL_TOXICITY_THRESHOLD` | 0.1 | Score above this blocks (0-1, lower = more strict) |
| `GUARDRAIL_HALLUCINATION_THRESHOLD` | 0.6 | Grounding ratio below this blocks (0-1) |
| `GUARDRAIL_RELEVANCE_THRESHOLD` | 0.5 | Topic relevance below this blocks (0-1) |
| `GUARDRAIL_POLICY_CHECK_ENABLED` | `true` | Enable policy compliance layer |
| `GUARDRAIL_BRAND_VOICE_CHECK_ENABLED` | `true` | Enable brand voice layer |
| `GUARDRAIL_FALLBACK_TEMPLATE` | `"I appreciate your question. Let me look into this further and get back to you with accurate information."` | Default safe fallback |
| `GUARDRAIL_MAX_CLAIMS_TO_VERIFY` | 10 | Max claims extracted for hallucination check |
| `GUARDRAIL_STATS_RETENTION_DAYS` | 90 | Days to keep aggregated stats |

## Building Codes Applied

- **BC-007 (AI Model Interaction):** Rule 6 — Guardrails evaluate every response before delivery — **FULLY IMPLEMENTED**
- **BC-007 Rule 7:** Manager review queue with second-pass check on release — **FULLY IMPLEMENTED**
- **BC-009 (Approval Workflow):** Blocked responses follow review-then-release pattern similar to approval queue
- **BC-010 (Data Lifecycle & Compliance):** Original prompts/responses containing PII are redacted before storage in `guardrail_blocks`
- **BC-001 (Multi-Tenant Isolation):** All guardrail rules and blocks scoped by `company_id`; tenant-specific rule overrides supported
- **BC-004 (Background Jobs):** Stats aggregation runs daily via Celery beat; hallucination claim verification for complex responses runs async

## Edge Cases

1. **Response is 90% correct but has one hallucinated claim:** The grounding score (e.g., 3/4 = 0.75) may be above threshold, allowing it through. If the single conflict is on a material fact (price, date, policy), the policy layer catches it. If immaterial, it passes — balancing safety with usability.
2. **Toxicity in customer's original message:** Guardrails only evaluate AI responses, not user input. However, if the AI echoes back toxic language from the user's message, the toxicity layer catches it in the AI's response.
3. **RAG retrieval returns no results:** If the knowledge base has no matching documents, the hallucination layer cannot ground claims. In this case, the system adds a disclaimer to the response rather than blocking: "I don't have specific information about this in our knowledge base. Here's what I can share based on general knowledge..."
4. **Guardrails layer timeout:** If a layer takes >5 seconds (e.g., hallucination claim extraction on a very long response), it is skipped and logged. The response passes through with a `guardrail_partial: true` flag. Admins see which layers were skipped.
5. **Released response still violates policy:** The second-pass Guardrails check on release may catch issues the admin missed. If the second check blocks, the release is rejected and the admin is notified.
6. **False positive hallucination detection:** If the knowledge base is outdated (e.g., doesn't contain the latest policy update), factual responses may be flagged as hallucinations. Admins can release these and the system logs them as "knowledge gap" signals for KB updating.

## Acceptance Criteria

1. **Toxicity blocking:** Send an LLM response containing profanity. Verify Layer 1 blocks it, fallback is returned, and the event appears in the blocked queue.
2. **Hallucination detection:** Generate a response with 2 grounded claims and 2 ungrounded claims. Verify Layer 2 blocks it with grounding score 0.5 and lists the specific conflicts.
3. **Off-topic response:** Customer asks about refund policy; AI responds with product feature information. Verify Layer 3 (relevance) blocks it with a low relevance score.
4. **Policy violation blocking:** AI response promises "100% money-back guarantee no questions asked" when company policy requires 30-day window. Verify Layer 4 blocks with specific policy reference.
5. **Admin release flow:** Block a response. Admin releases it from the queue. Verify it passes a second Guardrails check before delivery. If second check fails, verify release is rejected.
6. **Tenant-specific rules:** Create a tenant override rule that blocks competitor name mentions. Verify it applies only to that tenant's responses.
7. **Stats accuracy:** Block 10 responses (3 toxicity, 4 hallucination, 2 relevance, 1 policy). Verify `/api/guardrails/stats` shows correct counts per layer and overall block rate.

---

# F-059: Confidence Scoring System

## Overview

The Confidence Scoring System assigns a calibrated 0-100 confidence score to every AI response, computed from multiple weighted sub-scores including retrieval relevance (how well the knowledge base matched the query), intent match confidence (how clearly the customer's intent was classified), historical accuracy (how often similar responses were correct in the past), and context completeness (whether all required information was available). These scores drive the approval routing engine: low-confidence responses require human review, high-confidence responses can be auto-handled, and the scoring data feeds into the DSPy optimization pipeline for continuous model improvement.

## Architecture

**Multi-Signal Confidence Calculation:**

```
confidence_score = Σ (weight_i × signal_i)

Signals:
  1. Retrieval Relevance (R)       — Weight: 0.30
     How well did the RAG search match the query?
     Computed: cosine_similarity(top_chunk_embedding, query_embedding)

  2. Intent Match (I)              — Weight: 0.20
     How confident was the intent classifier?
     Provided by: Smart Router classification response

  3. Historical Accuracy (H)       — Weight: 0.20
     How often were similar responses marked correct by humans?
     Computed: rolling 30-day accuracy for same intent + model combo

  4. Context Completeness (C)      — Weight: 0.15
     Were all required fields in GSD state populated?
     Computed: filled_fields / total_required_fields

  5. Response Coherence (S)        — Weight: 0.10
     Does the response directly address the customer's question?
     Computed: lightweight classifier (Light tier) scoring 0-1

  6. Sentiment Alignment (A)       — Weight: 0.05
     Does the response tone match the customer's sentiment?
     Computed: |response_sentiment - customer_sentiment| mapped to 0-1
```

**Confidence Formula:**
```
confidence_score = round(
    (R × 0.30) + (I × 0.20) + (H × 0.20) + (C × 0.15) + (S × 0.10) + (A × 0.05)
) × 100

Where:
  R = retrieval_relevance (0.0 - 1.0)   — cosine similarity of top RAG chunk
  I = intent_confidence (0.0 - 1.0)     — from classifier probability
  H = historical_accuracy (0.0 - 1.0)   — 30-day rolling accuracy for intent
  C = context_completeness (0.0 - 1.0)  — filled/required fields ratio
  S = response_coherence (0.0 - 1.0)    — semantic similarity of response to query
  A = sentiment_alignment (0.0 - 1.0)   — inverse of sentiment distance
```

**Routing Thresholds (per company, configurable):**
| Score Range | Action | Description |
|-------------|--------|-------------|
| 0 - 49 | Manager Escalation | Mandatory human review by supervisor |
| 50 - 79 | Agent Review | Standard human approval required |
| 80 - 94 | Conditional Auto | Auto-execute if matching auto-approve rule exists |
| 95 - 100 | Auto-Execute | Automatic execution (unless VIP override) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/confidence/calculate` | Calculate confidence score for a response |
| `GET` | `/api/confidence/{response_id}/breakdown` | Get detailed score breakdown |
| `GET` | `/api/confidence/thresholds` | Get confidence thresholds for current company |
| `PUT` | `/api/confidence/thresholds` | Update confidence thresholds (admin) |
| `GET` | `/api/confidence/history` | Historical confidence scores (paginated) |
| `GET` | `/api/confidence/stats` | Aggregated confidence statistics |
| `POST` | `/api/confidence/{response_id}/feedback` | Submit human feedback (correct/incorrect) |

**POST `/api/confidence/calculate` Request:**
```json
{
  "company_id": "uuid",
  "session_id": "uuid",
  "ticket_id": "uuid",
  "query": "What is the refund policy for digital products?",
  "response": "Our refund policy allows returns within 30 days of purchase for digital products...",
  "intent": {"primary": "refund_policy", "confidence": 0.95},
  "retrieval_relevance": 0.82,
  "context_completeness": 1.0,
  "model_id": "meta-llama/llama-3-8b-instruct:free",
  "sentiment": {"customer": -0.2, "response": 0.1}
}
```

**POST `/api/confidence/calculate` Response:**
```json
{
  "confidence_score": 87,
  "breakdown": {
    "retrieval_relevance": {"score": 0.82, "weight": 0.30, "contribution": 24.6},
    "intent_match": {"score": 0.95, "weight": 0.20, "contribution": 19.0},
    "historical_accuracy": {"score": 0.78, "weight": 0.20, "contribution": 15.6},
    "context_completeness": {"score": 1.0, "weight": 0.15, "contribution": 15.0},
    "response_coherence": {"score": 0.88, "weight": 0.10, "contribution": 8.8},
    "sentiment_alignment": {"score": 0.70, "weight": 0.05, "contribution": 3.5}
  },
  "routing_action": "conditional_auto",
  "auto_approve_eligible": true,
  "requires_human_review": false,
  "response_id": "uuid"
}
```

## Database Tables

### `confidence_scores`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Score record ID |
| `company_id` | UUID | NOT NULL, FK → companies.id | Tenant |
| `session_id` | UUID | NOT NULL | Session |
| `ticket_id` | UUID | NULLABLE | Ticket |
| `response_id` | UUID | NOT NULL | Associated AI response |
| `model_id` | VARCHAR(100) | NOT NULL | Model used |
| `overall_score` | INTEGER | NOT NULL, CHECK (0-100) | Final confidence score |
| `retrieval_relevance` | DECIMAL(5,4) | NOT NULL | Sub-score (0.0-1.0) |
| `intent_match` | DECIMAL(5,4) | NOT NULL | Sub-score (0.0-1.0) |
| `historical_accuracy` | DECIMAL(5,4) | NOT NULL | Sub-score (0.0-1.0) |
| `context_completeness` | DECIMAL(5,4) | NOT NULL | Sub-score (0.0-1.0) |
| `response_coherence` | DECIMAL(5,4) | NOT NULL | Sub-score (0.0-1.0) |
| `sentiment_alignment` | DECIMAL(5,4) | NOT NULL | Sub-score (0.0-1.0) |
| `routing_action` | VARCHAR(30) | NOT NULL | manager_escalation / agent_review / conditional_auto / auto_execute |
| `human_feedback` | VARCHAR(10) | NULLABLE | correct / incorrect / null |
| `feedback_given_at` | TIMESTAMPTZ | NULLABLE | When feedback was provided |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Score timestamp |

**Indexes:**
- `idx_confidence_company_date` ON `confidence_scores(company_id, created_at DESC)`
- `idx_confidence_ticket` ON `confidence_scores(ticket_id)` WHERE `ticket_id IS NOT NULL`
- `idx_confidence_model_score` ON `confidence_scores(model_id, overall_score)`

### `confidence_thresholds`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Threshold ID |
| `company_id` | UUID | NOT NULL, FK → companies.id | Tenant |
| `action_type` | VARCHAR(30) | NOT NULL | The action this threshold governs |
| `min_score` | INTEGER | NOT NULL, CHECK (0-100) | Minimum confidence for this action |
| `max_score` | INTEGER | NOT NULL, CHECK (0-100) | Maximum confidence for this action |
| `routing` | VARCHAR(30) | NOT NULL | Routing decision |
| `updated_by` | UUID | NOT NULL, FK → users.id | Admin who configured |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update |

**Default thresholds per company:**
| action_type | min_score | max_score | routing |
|-------------|-----------|-----------|---------|
| all_actions | 0 | 49 | manager_escalation |
| all_actions | 50 | 79 | agent_review |
| all_actions | 80 | 94 | conditional_auto |
| all_actions | 95 | 100 | auto_execute |
| refund | 0 | 100 | agent_review (refund always requires human) |

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CONFIDENCE_WEIGHT_RETRIEVAL` | 0.30 | Weight for retrieval relevance signal |
| `CONFIDENCE_WEIGHT_INTENT` | 0.20 | Weight for intent match signal |
| `CONFIDENCE_WEIGHT_HISTORICAL` | 0.20 | Weight for historical accuracy signal |
| `CONFIDENCE_WEIGHT_CONTEXT` | 0.15 | Weight for context completeness signal |
| `CONFIDENCE_WEIGHT_COHERENCE` | 0.10 | Weight for response coherence signal |
| `CONFIDENCE_WEIGHT_SENTIMENT` | 0.05 | Weight for sentiment alignment signal |
| `CONFIDENCE_HISTORICAL_WINDOW_DAYS` | 30 | Days for rolling historical accuracy |
| `CONFIDENCE_HISTORICAL_MIN_SAMPLES` | 10 | Minimum samples before historical score is used (default 0.5) |
| `CONFIDENCE_FEEDBACK_EXPIRY_DAYS` | 90 | Days until feedback data is anonymized |

## Technique Trigger Integration

Confidence scores serve as a **primary trigger signal** for the Technique Router (BC-013), automatically activating specific reasoning techniques when response quality is uncertain:

| Confidence Range | Techniques Triggered | Rationale |
|------------------|---------------------|-----------|
| < 0.7 (score < 70) | **Reverse Thinking (F-141)** + **Step-Back (F-142)** | Low confidence signals the model may be reasoning incorrectly; reverse validation and perspective broadening improve accuracy |
| 0.7–0.85 (score 70–85) | **Chain-of-Thought (F-140)** | Moderate confidence benefits from explicit step-by-step reasoning to validate the approach |
| > 0.85 (score > 85) | No additional techniques | High confidence indicates the response is reliable; skip technique overhead |

**Integration with Technique Router:**
- Confidence scores are passed to the Technique Router as part of the query signal payload
- The Technique Router evaluates confidence alongside sentiment and intent to determine the optimal technique combination
- When confidence is below 0.7, Reverse Thinking (F-141) generates a secondary reasoning path that is compared against the original response. If the two paths disagree, Step-Back (F-142) re-frames the query with broader context before re-attempting.
- Technique activation does not change the confidence score itself — it changes the reasoning approach used to generate the response, which should naturally produce higher-confidence results.

## Building Codes Applied

- **BC-007 (AI Model Interaction):** Rule 9 — Confidence thresholds stored per company, not hardcoded — **FULLY IMPLEMENTED**
- **BC-008 (State Management):** Context completeness signal reads from GSD state's `collected_info` and `resolution.steps_completed`
- **BC-009 (Approval Workflow):** Confidence scores drive routing decisions — directly integrates with approval routing engine (F-074, F-076)
- **BC-013 (Technique Router Integration):** Confidence scores below 0.7 trigger Reverse Thinking (F-141) and Step-Back (F-142); all scores feed into the Technique Router as primary trigger signals — **FULLY IMPLEMENTED**
- **BC-001 (Multi-Tenant Isolation):** Each company has its own configurable thresholds; scores scoped by `company_id`
- **BC-004 (Background Jobs):** Historical accuracy recalculation runs daily via Celery beat; feedback aggregation runs hourly

## Edge Cases

1. **No historical data for new intent:** When a company has fewer than 10 resolved tickets for an intent, `historical_accuracy` defaults to 0.5 (neutral). This prevents new intents from being unfairly penalized or boosted.
2. **RAG returns no results:** If `retrieval_relevance` is 0.0 (no knowledge base match), the maximum possible confidence is 70 (all other signals maxed). This ensures responses without KB grounding always require human review.
3. **Confidence score drift over time:** If a company's historical accuracy drops (e.g., model quality degrades), new scores automatically reflect this. The DSPy optimization pipeline (F-061) monitors for drift and triggers prompt re-optimization when accuracy drops below 70% for any intent.
4. **Feedback spam or manipulation:** A single user cannot submit more than 5 feedback entries per session. Feedback is weighted by reviewer role — supervisor feedback counts 3x, agent feedback counts 2x, customer implicit feedback (no reply = assume correct) counts 1x.
5. **Contradictory feedback:** If a response receives both "correct" and "incorrect" feedback (e.g., from different reviewers), the most recent feedback from the highest-role reviewer wins.

## Acceptance Criteria

1. **Score calculation accuracy:** Given specific sub-scores (R=0.8, I=0.9, H=0.7, C=1.0, S=0.85, A=0.6), verify the formula produces `round((0.8×0.3 + 0.9×0.2 + 0.7×0.2 + 1.0×0.15 + 0.85×0.1 + 0.6×0.05) × 100) = 83`.
2. **Routing decision correctness:** Score 45 → manager_escalation. Score 60 → agent_review. Score 88 → conditional_auto. Score 97 → auto_execute.
3. **Breakdown endpoint:** GET `/api/confidence/{id}/breakdown` returns all 6 sub-scores with their weights and individual contributions that sum to the overall score.
4. **Threshold customization:** Admin updates refund threshold to require human review for all scores (0-100). Verify a refund action with score 98 still routes to agent_review.
5. **Feedback integration:** Submit "incorrect" feedback on a response. Verify `human_feedback` is recorded. Verify the next historical_accuracy calculation for that intent reflects the new data point.
6. **No-history fallback:** For a brand-new company with zero resolved tickets, verify historical_accuracy defaults to 0.5 and the confidence score is calculated correctly.
7. **Tenant isolation:** Set Company A's auto-execute threshold to 90 and Company B's to 80. Verify each company routes independently.

---

# F-060: LangGraph Workflow Engine

## Overview

The LangGraph Workflow Engine provides graph-based orchestration for complex multi-step AI workflows. Instead of linear prompt → response flows, PARWA defines support resolution as a directed state graph with nodes (processing steps), edges (transitions), conditional branches (routing based on confidence, intent, or state), and human-in-the-loop checkpoints. This enables sophisticated workflows like "classify intent → search knowledge base → draft response → check confidence → auto-approve or queue for review → deliver response" with full visibility into every step, deterministic execution paths, and the ability to pause/resume workflows at any checkpoint.

## Architecture

**LangGraph Integration:**
- PARWA uses LangGraph as the workflow orchestration framework
- Each support workflow is defined as a `StateGraph` with typed state (the GSD State from F-053)
- Nodes are Python async functions that read/write state
- Edges define transitions between nodes (can be conditional)
- Checkpoints are stored in PostgreSQL (LangGraph's built-in checkpointing)
- The engine integrates with Celery for long-running workflow steps

**Core Workflow Graph Structure:**

```
┌──────────────────────────────────────────────────────────────────┐
│                    PARWA Support Resolution Graph                │
│                                                                  │
│  START                                                           │
│    │                                                             │
│    ▼                                                             │
│  [ingest_message]  ← Receives raw message, creates/updates GSD  │
│    │                                                             │
│    ▼                                                             │
│  [pii_redact]  ← Scans and redacts PII (F-056)                  │
│    │                                                             │
│    ▼                                                             │
│  [classify_intent]  ← Routes to correct sub-graph               │
│    │                                                             │
│    ├── refund ──────────→ [refund_subgraph]                      │
│    ├── technical ───────→ [technical_subgraph]                   │
│    ├── billing ─────────→ [billing_subgraph]                     │
│    ├── general ─────────→ [general_subgraph]                     │
│    └── escalation ─────→ [human_handoff_node]                    │
│                                                                  │
│  [refund_subgraph]:                                              │
│    [verify_order] → [check_refund_policy] → [calculate_amount]   │
│    → [draft_response] → [check_confidence]                       │
│      │                                                           │
│      ├── confidence ≥ 80 → [guardrails_check] → [deliver]       │
│      └── confidence < 80 → [queue_for_review] ──→ CHECKPOINT     │
│                                              (human approves)    │
│                                                │                │
│                                                ▼                │
│                                           [deliver]             │
│    │                                                             │
│    ▼                                                             │
│  [log_outcome] → END                                            │
└──────────────────────────────────────────────────────────────────┘
```

**Node Definitions:**
```python
from langgraph.graph import StateGraph, END

class WorkflowState(TypedDict):
    session_id: str
    company_id: str
    messages: list[dict]
    gsd_state: dict
    current_node: str
    confidence_score: int | None
    routing_decision: str | None
    error: str | None
    checkpoint_data: dict

# Node implementations
async def ingest_message(state: WorkflowState) -> WorkflowState:
    """Receives raw message, validates, and updates GSD state."""
    ...

async def pii_redact(state: WorkflowState) -> WorkflowState:
    """Runs PII redaction engine on all text."""
    ...

async def classify_intent(state: WorkflowState) -> WorkflowState:
    """Classifies intent using Smart Router Light tier."""
    ...

async def search_knowledge_base(state: WorkflowState) -> WorkflowState:
    """Runs RAG retrieval pipeline."""
    ...

async def draft_response(state: WorkflowState) -> WorkflowState:
    """Generates AI response using Smart Router Medium/Heavy tier."""
    ...

async def check_confidence(state: WorkflowState) -> WorkflowState:
    """Calculates confidence score and determines routing."""
    ...

async def guardrails_check(state: WorkflowState) -> WorkflowState:
    """Runs all guardrail layers."""
    ...

async def queue_for_review(state: WorkflowState) -> WorkflowState:
    """Creates approval queue entry and pauses workflow."""
    ...

async def deliver_response(state: WorkflowState) -> WorkflowState:
    """Delivers response to customer via appropriate channel."""
    ...

async def human_handoff(state: WorkflowState) -> WorkflowState:
    """Transfers conversation to human agent."""
    ...

async def log_outcome(state: WorkflowState) -> WorkflowState:
    """Logs workflow outcome, updates metrics."""
    ...

# Conditional edge: confidence-based routing
def confidence_router(state: WorkflowState) -> str:
    if state["confidence_score"] >= 80:
        return "guardrails_check"
    elif state["confidence_score"] >= 50:
        return "queue_for_review"
    else:
        return "human_handoff"

# Conditional edge: intent-based routing
def intent_router(state: WorkflowState) -> str:
    intent = state["gsd_state"]["intent"]["primary"]
    if intent in ["refund", "return", "cancellation"]:
        return "refund_subgraph"
    elif intent in ["technical", "bug", "error"]:
        return "technical_subgraph"
    elif intent in ["billing", "invoice", "payment"]:
        return "billing_subgraph"
    elif intent in ["escalation", "complaint", "legal"]:
        return "human_handoff"
    else:
        return "general_subgraph"

# Graph construction
graph = StateGraph(WorkflowState)
graph.add_node("ingest_message", ingest_message)
graph.add_node("pii_redact", pii_redact)
graph.add_node("classify_intent", classify_intent)
graph.add_node("search_knowledge_base", search_knowledge_base)
graph.add_node("draft_response", draft_response)
graph.add_node("check_confidence", check_confidence)
graph.add_node("guardrails_check", guardrails_check)
graph.add_node("queue_for_review", queue_for_review)
graph.add_node("deliver_response", deliver_response)
graph.add_node("human_handoff", human_handoff)
graph.add_node("log_outcome", log_outcome)

graph.set_entry_point("ingest_message")
graph.add_edge("ingest_message", "pii_redact")
graph.add_edge("pii_redact", "classify_intent")
graph.add_conditional_edges("classify_intent", intent_router)
graph.add_edge("refund_subgraph", "check_confidence")
graph.add_edge("technical_subgraph", "check_confidence")
graph.add_edge("billing_subgraph", "check_confidence")
graph.add_edge("general_subgraph", "check_confidence")
graph.add_conditional_edges("check_confidence", confidence_router)
graph.add_edge("guardrails_check", "deliver_response")
graph.add_edge("guardrails_check", "safe_fallback", "queue_for_review")
graph.add_edge("deliver_response", "log_outcome")
graph.add_edge("log_outcome", END)
graph.add_edge("queue_for_review", "deliver_response")  # resumed after approval
graph.add_edge("human_handoff", "log_outcome")
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/workflows/execute` | Execute a workflow for a session |
| `GET` | `/api/workflows/{workflow_id}/status` | Get current workflow execution status |
| `GET` | `/api/workflows/{workflow_id}/graph` | Visualize workflow graph (nodes, edges, state) |
| `GET` | `/api/workflows/{workflow_id}/history` | Step-by-step execution history |
| `POST` | `/api/workflows/{workflow_id}/resume` | Resume a paused workflow (after approval) |
| `POST` | `/api/workflows/{workflow_id}/cancel` | Cancel an in-progress workflow |
| `GET` | `/api/workflows/definitions` | List all registered workflow definitions |
| `POST` | `/api/workflows/definitions` | Register a new workflow definition |

## Database Tables

### `workflow_executions`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Workflow execution ID |
| `company_id` | UUID | NOT NULL, FK → companies.id | Tenant |
| `session_id` | UUID | NOT NULL | Session |
| `ticket_id` | UUID | NULLABLE | Ticket |
| `workflow_type` | VARCHAR(50) | NOT NULL | support_resolution / refund / technical / billing / general |
| `status` | VARCHAR(20) | NOT NULL | running / paused / completed / failed / cancelled |
| `current_node` | VARCHAR(50) | NOT NULL | Currently executing or paused node |
| `state_snapshot` | JSONB | NOT NULL | Full workflow state at current point |
| `checkpoint_id` | VARCHAR(100) | NULLABLE | LangGraph checkpoint ID for resume |
| `error` | TEXT | NULLABLE | Error message if failed |
| `started_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Start time |
| `completed_at` | TIMESTAMPTZ | NULLABLE | Completion time |
| `duration_ms` | INTEGER | NULLABLE | Total execution time |

### `workflow_steps`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Step ID |
| `workflow_id` | UUID | NOT NULL, FK → workflow_executions.id | Parent workflow |
| `node_name` | VARCHAR(50) | NOT NULL | Node that executed |
| `status` | VARCHAR(20) | NOT NULL | running / completed / failed / skipped |
| `input_state` | JSONB | NOT NULL | State before node execution |
| `output_state` | JSONB | NOT NULL | State after node execution |
| `duration_ms` | INTEGER | NOT NULL | Node execution time |
| `model_used` | VARCHAR(100) | NULLABLE | LLM model used (if applicable) |
| `tokens_consumed` | INTEGER | NULLABLE | Tokens used by this step |
| `error` | TEXT | NULLABLE | Error if step failed |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Step timestamp |

**Indexes:**
- `idx_workflow_executions_company` ON `workflow_executions(company_id)`
- `idx_workflow_executions_session` ON `workflow_executions(session_id)`
- `idx_workflow_executions_status` ON `workflow_executions(status)`
- `idx_workflow_steps_workflow` ON `workflow_steps(workflow_id, created_at)`

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `LANGGRAPH_CHECKPOINTER` | `postgres` | Checkpoint storage backend |
| `LANGGRAPH_MAX_STEPS` | 50 | Max steps per workflow (prevents infinite loops) |
| `LANGGRAPH_STEP_TIMEOUT_MS` | 30000 | Per-step execution timeout |
| `LANGGRAPH_MAX_PARALLEL` | 5 | Max concurrent workflow executions per tenant |
| `LANGGRAPH_CHECKPOINT_TTL_DAYS` | 7 | Days to retain paused workflow checkpoints |
| `LANGGRAPH_RETRY_STEPS` | `["draft_response", "classify_intent"]` | Steps eligible for auto-retry on failure |

## Technique Execution Nodes

The LangGraph workflow must incorporate **technique execution** as a first-class workflow concern. When the Technique Router (BC-013) activates one or more reasoning techniques, the workflow dynamically branches to execute those technique-specific nodes before proceeding to response drafting.

**Technique-to-Node Mapping:**

| Technique | Feature ID | LangGraph Node(s) | Tier |
|-----------|-----------|-------------------|------|
| Chain-of-Thought (CoT) | F-140 | `cot_reasoning` | Tier 1 (Always Available) |
| ReAct | F-141 | `react_observe`, `react_act` | Tier 1 (Always Available) |
| Reverse Thinking | F-141 | `reverse_thinking` | Tier 2 (Conditional) |
| Step-Back | F-142 | `step_back_reframe` | Tier 2 (Conditional) |
| Self-Ask | F-143 | `self_ask_decompose` | Tier 1 (Always Available) |
| Universe of Thoughts (UoT) | F-144 | `uot_branch`, `uot_evaluate` | Tier 3 (Premium) |
| Debate | F-145 | `debate_argue`, `debate_judge` | Tier 3 (Premium) |
| Self-Consistency | F-146 | `self_consistency_sample` | Tier 3 (Premium) |
| Reflexion | F-147 | `reflexion_evaluate`, `reflexion_refine` | Tier 3 (Premium) |

**Workflow Branching Logic:**
```
[draft_response]
    │
    ├── No techniques activated ──► [check_confidence]
    │
    └── Technique(s) activated ──► [execute_techniques]
                                      │
                                      ├── CoT only ──► [cot_reasoning] ──► [check_confidence]
                                      │
                                      ├── CoT + ReAct ──► [cot_reasoning] ──► [react_observe] ──► [react_act] ──► [check_confidence]
                                      │
                                      ├── Tier 2+ (Reverse Thinking, UoT, etc.)
                                      │   ──► [technique_executor] ──► [technique_result_merge] ──► [check_confidence]
                                      │
                                      └── Tier 3 (Debate, Self-Consistency, Reflexion)
                                          ──► [technique_executor] ──► [technique_result_merge] ──► [check_confidence]
```

**Key Principles:**
- Each technique (F-140 to F-148) maps to one or more LangGraph nodes in the workflow graph
- The workflow dynamically branches based on which techniques are activated by the Technique Router
- Tier 1 techniques (CoT, ReAct, Self-Ask) are lightweight and execute inline within the standard workflow
- Tier 2 and Tier 3 techniques may require additional LLM calls; their results are merged via a `technique_result_merge` node before confidence checking
- Technique execution nodes inherit the same error handling, timeout, and retry semantics as other workflow nodes
- The `technique_executor` node logs technique activation and execution time to `workflow_steps` for observability

## Building Codes Applied

- **BC-007 (AI Model Interaction):** All LLM calls within workflow nodes go through Smart Router → PII Redaction → Guardrails pipeline
- **BC-008 (State Management):** Workflow state IS the GSD state; dual-storage persistence; context health monitoring integrated
- **BC-004 (Background Jobs):** Long-running workflow steps (RAG search, response drafting) executed via Celery with retry logic; checkpoint-based recovery
- **BC-009 (Approval Workflow):** `queue_for_review` node creates approval record and pauses workflow; resume triggered on approval
- **BC-012 (Error Handling & Resilience):** Step-level error handling; failed steps logged; workflow can resume from last checkpoint; max step limit prevents infinite loops
- **BC-013 (Technique Router Integration):** Workflow branches dynamically based on activated techniques; each technique (F-140 to F-148) maps to one or more LangGraph nodes; technique execution results merge before confidence checking — **FULLY IMPLEMENTED**
- **BC-001 (Multi-Tenant Isolation):** All workflow data scoped by `company_id`; max parallel executions per tenant

## Edge Cases

1. **Workflow stuck in loop:** The `LANGGRAPH_MAX_STEPS` limit (50) prevents infinite loops. If reached, the workflow is marked as `failed` with error "max steps exceeded" and the GSD State Terminal (F-089) shows the loop pattern for debugging.
2. **Checkpoint data becomes stale:** If a workflow is paused for >7 days, the checkpoint expires. On resume attempt, the system creates a new workflow from the current GSD state (recovered from Postgres) rather than using the stale checkpoint.
3. **Node fails mid-execution:** If a node crashes (e.g., LLM timeout), the step is marked as `failed` in `workflow_steps`. Retryable steps (`draft_response`, `classify_intent`) are automatically retried once. Non-retryable steps cause the workflow to pause with an error, and the GSD State Terminal shows the exact failure point.
4. **Concurrent workflow modifications:** If two messages arrive for the same session simultaneously, only one workflow executes. The second message is queued and processed after the first completes. This prevents race conditions in GSD state updates.
5. **Human approval takes >72 hours:** The approval timeout (F-082) auto-rejects the item. The paused workflow receives a "rejected" signal and routes to `human_handoff` node instead of `deliver_response`.
6. **Sub-graph not found:** If the intent classifier returns an intent not mapped to any sub-graph, the workflow falls through to the `general_subgraph` with a lower confidence threshold and broader knowledge base search.

## Acceptance Criteria

1. **End-to-end workflow execution:** Submit a customer message. Verify the workflow progresses through: ingest → pii_redact → classify → search_kb → draft → check_confidence → guardrails → deliver → log. Verify all steps are logged in `workflow_steps`.
2. **Intent-based routing:** Submit 5 refund queries, 5 technical queries, 5 billing queries. Verify each routes to the correct sub-graph (check `workflow_executions.workflow_type`).
3. **Confidence-based pause and resume:** Trigger a workflow that produces confidence score 55. Verify workflow pauses at `queue_for_review`. Approve the item. Verify workflow resumes and delivers response.
4. **Graph visualization:** GET `/api/workflows/{id}/graph` returns a valid graph representation showing all nodes, edges, and the current execution position.
5. **Step-level error handling:** Configure a step to fail. Verify the step is marked as `failed` in `workflow_steps`, the error is logged, and retryable steps are retried automatically.
6. **Max steps protection:** Create a workflow that would loop indefinitely. Verify it stops at 50 steps with appropriate error.
7. **Concurrent message handling:** Send 3 messages to the same session simultaneously. Verify only one workflow executes at a time and all 3 messages are eventually processed in order.

---

# F-064: Knowledge Base RAG (Vector Search)

## Overview

The Knowledge Base RAG (Retrieval-Augmented Generation) pipeline converts uploaded documents into vector embeddings, stores them in PostgreSQL's pgvector extension, performs semantic similarity search at query time, retrieves the most relevant document chunks, and injects them as context into LLM prompts. This grounds AI responses in the company's actual knowledge base rather than relying on model training data alone, dramatically reducing hallucinations and enabling accurate responses about company-specific policies, products, and procedures.

## Architecture

**Five-Stage RAG Pipeline:**

```
Stage 1: EMBED (Document Ingestion)
  Uploaded file → Extract text (PDF/DOCX/TXT/MD/HTML/CSV)
    → Chunk text (512 tokens, 50 token overlap)
    → Generate embeddings (sentence-transformers/all-MiniLM-L6-v2)
    → Store chunks + embeddings in PostgreSQL pgvector

Stage 2: STORE (Indexing)
  Each chunk gets: chunk_id, document_id, company_id, content, embedding (vector),
    metadata (page_number, section_title, chunk_index), created_at
  HNSW index built on embedding column for fast approximate nearest neighbor search
  Full-text search index on content column for hybrid search

Stage 3: SEARCH (Query Time)
  User query → Generate query embedding
    → Parallel search:
      ├── Vector similarity search (pgvector cosine distance)
      ├── Full-text keyword search (PostgreSQL tsvector)
      └── Metadata filter (document_type, date_range, tags)
    → Reciprocal Rank Fusion (RRF) to merge results

Stage 4: RETRIEVE (Context Assembly)
  Top-K chunks (K=5 default) → Re-rank using cross-encoder
    → Filter by relevance threshold (cosine similarity > 0.7)
    → Assemble context block with source citations

Stage 5: INJECT (Prompt Construction)
  Context block + system prompt + conversation history + user query
    → Send to LLM via Smart Router
    → Response includes [source: doc_name, page X] citations
```

**Embedding Model:**
- Primary: `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional, fast, good quality)
- Fallback: `thenlper/gte-base` (768-dimensional, higher quality but slower)
- Hosted locally via FastAPI embedding service (no external API dependency for embeddings)

**Hybrid Search (Reciprocal Rank Fusion):**
```
vector_results = pgvector_cosine_search(query_embedding, top_k=10)
text_results = fulltext_search(query_text, top_k=10)

# Reciprocal Rank Fusion
fused = {}
for rank, doc in enumerate(vector_results):
    fused[doc.id] = fused.get(doc.id, 0) + 1 / (rank + 60)
for rank, doc in enumerate(text_results):
    fused[doc.id] = fused.get(doc.id, 0) + 1 / (rank + 60)

final_results = sort(fused, by=score, descending=True)[:top_k]
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/kb/documents/upload` | Upload documents for ingestion |
| `GET` | `/api/kb/documents` | List all documents (paginated) |
| `GET` | `/api/kb/documents/{doc_id}` | Get document details and status |
| `DELETE` | `/api/kb/documents/{doc_id}` | Delete document and all its chunks |
| `POST` | `/api/kb/documents/{doc_id}/reindex` | Re-index a document (re-chunk + re-embed) |
| `GET` | `/api/kb/chunks` | List chunks (paginated, filterable) |
| `POST` | `/api/kb/search` | Semantic search across knowledge base |
| `POST` | `/api/kb/search/hybrid` | Hybrid vector + keyword search |
| `GET` | `/api/kb/stats` | Knowledge base statistics |

**POST `/api/kb/search/hybrid` Request:**
```json
{
  "company_id": "uuid",
  "query": "What is the refund policy for digital products?",
  "top_k": 5,
  "min_relevance": 0.7,
  "filters": {
    "document_types": ["policy", "faq"],
    "tags": ["refund", "digital"],
    "date_after": "2025-01-01"
  },
  "include_metadata": true
}
```

**POST `/api/kb/search/hybrid` Response:**
```json
{
  "results": [
    {
      "chunk_id": "uuid",
      "content": "Digital products can be refunded within 30 days of purchase...",
      "document_id": "uuid",
      "document_title": "Refund Policy v3.2",
      "document_type": "policy",
      "metadata": {"page_number": 5, "section_title": "Digital Products"},
      "relevance_score": 0.89,
      "search_type": "vector"
    }
  ],
  "total_found": 23,
  "returned": 5,
  "search_metadata": {
    "vector_search_time_ms": 12,
    "text_search_time_ms": 3,
    "rerank_time_ms": 8,
    "total_time_ms": 23
  }
}
```

## Database Tables

### `kb_documents`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Document ID |
| `company_id` | UUID | NOT NULL, FK → companies.id | Tenant |
| `title` | VARCHAR(255) | NOT NULL | Document title |
| `filename` | VARCHAR(255) | NOT NULL | Original filename |
| `document_type` | VARCHAR(30) | NOT NULL | policy / faq / manual / guide / other |
| `file_size_bytes` | INTEGER | NOT NULL | Original file size |
| `mime_type` | VARCHAR(50) | NOT NULL | MIME type |
| `chunk_count` | INTEGER | NOT NULL, DEFAULT 0 | Number of chunks generated |
| `status` | VARCHAR(20) | NOT NULL | processing / indexed / failed / deleted |
| `processing_error` | TEXT | NULLABLE | Error if processing failed |
| `tags` | TEXT[] | DEFAULT '{}' | Searchable tags |
| `storage_path` | VARCHAR(500) | NOT NULL | Path to stored file |
| `indexed_at` | TIMESTAMPTZ | NULLABLE | When indexing completed |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Upload timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update |

### `kb_chunks` (with pgvector)
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Chunk ID |
| `company_id` | UUID | NOT NULL, FK → companies.id | Tenant |
| `document_id` | UUID | NOT NULL, FK → kb_documents.id | Parent document |
| `content` | TEXT | NOT NULL | Chunk text content |
| `embedding` | vector(384) | NOT NULL | Embedding vector (pgvector) |
| `chunk_index` | INTEGER | NOT NULL | Position in document (0-based) |
| `token_count` | INTEGER | NOT NULL | Token count of this chunk |
| `metadata` | JSONB | DEFAULT '{}' | page_number, section_title, headings |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Chunk creation |

**Indexes:**
- `idx_kb_chunks_company_doc` ON `kb_chunks(company_id, document_id)`
- `idx_kb_chunks_embedding` ON `kb_chunks` USING hnsw (`embedding` vector_cosine_ops) WITH (m = 16, ef_construction = 64) — **HNSW vector index**
- `idx_kb_chunks_content_fts` ON `kb_chunks` USING gin (to_tsvector('english', content)) — **Full-text search index**
- `idx_kb_chunks_company` ON `kb_chunks(company_id)` — **Tenant isolation**

### `kb_search_logs`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Log ID |
| `company_id` | UUID | NOT NULL | Tenant |
| `session_id` | UUID | NULLABLE | Session |
| `query` | TEXT | NOT NULL | Search query |
| `results_count` | INTEGER | NOT NULL | Number of results returned |
| `top_relevance_score` | DECIMAL(5,4) | NOT NULL | Highest relevance score |
| `avg_relevance_score` | DECIMAL(5,4) | NOT NULL | Average relevance score |
| `search_type` | VARCHAR(20) | NOT NULL | vector / text / hybrid |
| `latency_ms` | INTEGER | NOT NULL | Search time |
| `chunks_used` | UUID[] | DEFAULT '{}' | Chunk IDs sent to LLM |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Search timestamp |

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RAG_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Primary embedding model |
| `RAG_EMBEDDING_DIMENSIONS` | 384 | Embedding vector dimensions |
| `RAG_CHUNK_SIZE_TOKENS` | 512 | Tokens per chunk |
| `RAG_CHUNK_OVERLAP_TOKENS` | 50 | Overlap between consecutive chunks |
| `RAG_TOP_K` | 5 | Default number of chunks to retrieve |
| `RAG_MIN_RELEVANCE` | 0.7 | Minimum cosine similarity to include in results |
| `RAG_RERANK_ENABLED` | `true` | Enable cross-encoder reranking |
| `RAG_HYBRID_RRF_K` | 60 | Reciprocal Rank Fusion constant |
| `RAG_HNSW_M` | 16 | HNSW index M parameter |
| `RAG_HNSW_EF_CONSTRUCTION` | 64 | HNSW index ef_construction parameter |
| `RAG_HNSW_EF_SEARCH` | 40 | HNSW search ef parameter |
| `RAG_MAX_FILE_SIZE_MB` | 50 | Maximum file size for upload |
| `RAG_SUPPORTED_FORMATS` | `["pdf", "docx", "txt", "md", "html", "csv"]` | Accepted file types |

## Building Codes Applied

- **BC-007 (AI Model Interaction):** RAG retrieval feeds into Smart Router; knowledge context is included in LLM prompts; confidence scoring uses retrieval relevance as a signal
- **BC-001 (Multi-Tenant Isolation):** ALL queries scoped by `company_id`; each tenant's knowledge base is completely isolated; vector search includes `company_id` filter
- **BC-004 (Background Jobs):** Document ingestion (text extraction → chunking → embedding) runs as a Celery task with retry; re-indexing is async
- **BC-010 (Data Lifecycle & Compliance):** Documents can be deleted (and all chunks purged); Right to be Forgotten triggers KB cleanup; PII is redacted from chunks before embedding via F-056
- **BC-012 (Error Handling & Resilience):** Failed document processing logged with specific error; documents in `failed` status can be re-processed; embedding service failure triggers fallback to text-only search

## Edge Cases

1. **Very large documents (>100 pages):** The chunking pipeline processes documents in streaming mode — it does not load the entire document into memory. Chunking progress is tracked, and if the Celery worker crashes mid-processing, the document status remains `processing` and can be resumed.
2. **Duplicate documents:** Before ingestion, the system computes a SHA-256 hash of the file content and checks for duplicates. If a document with the same hash exists for the same company, the upload is rejected with a "duplicate" message.
3. **Empty or near-empty documents:** Documents with <100 tokens of extractable text are accepted but flagged as `low_content`. They are indexed (single chunk) but produce low-relevance results. Admins are notified.
4. **Embedding service unavailable:** If the local embedding service is down, the system falls back to keyword-only full-text search. A degraded search indicator is shown to admins. Chunks are queued for embedding once the service recovers.
5. **Low-relevance search results:** If the top result has relevance < 0.3, the system returns no results (rather than injecting irrelevant context). The response generator is informed that "no relevant knowledge base articles were found" and adjusts its response strategy accordingly.
6. **Knowledge base not yet indexed (new tenant):** If a tenant has no indexed documents, the RAG search returns empty results. The confidence scoring system (F-059) assigns a retrieval_relevance of 0.0, resulting in a low confidence score and mandatory human review.
7. **Cross-language search:** The embedding model handles multilingual text. If the query is in Spanish and the KB is in English, relevance scores will be lower. The system detects language mismatch and includes a note in the context: "Note: The query language differs from the knowledge base language. Results may be less relevant."

## Acceptance Criteria

1. **Document ingestion pipeline:** Upload a 10-page PDF. Verify: text is extracted, document is chunked into ~15-20 chunks (512 tokens each), embeddings are generated, chunks are stored in `kb_chunks` with pgvector vectors, and document status is `indexed`.
2. **Semantic search accuracy:** Index 5 policy documents. Search for "refund deadline". Verify the top result is the chunk containing refund policy information with relevance score > 0.7.
3. **Hybrid search:** Search for a specific term like "SKU-12345" that appears in the KB. Verify keyword search catches it even if vector search misses it (via RRF fusion).
4. **Tenant isolation:** Upload documents for Tenant A. Search from Tenant B's context. Verify zero results from Tenant A's documents.
5. **Context injection:** Search for relevant context → inject into LLM prompt → verify the LLM response includes information from the knowledge base (not hallucinated) and cites the source document.
6. **Duplicate detection:** Upload the same PDF twice. Verify the second upload is rejected with a duplicate warning.
7. **Re-indexing:** Modify a document's content and trigger re-index. Verify old chunks are deleted, new chunks are created, and the vector index is updated. Search returns results from the new content.

---

# Summary

| Feature | ID | Priority | Building Codes | Est. Complexity |
|---------|----|----------|----------------|-----------------|
| GSD State Engine | F-053 | Critical | BC-008, BC-001, BC-004, BC-012 | High |
| Smart Router (3-Tier LLM) | F-054 | Critical | BC-007, BC-001, BC-004, BC-012 | High |
| Model Failover & Rate Limit Handling | F-055 | Critical | BC-007, BC-004, BC-012 | Medium |
| PII Redaction Engine | F-056 | Critical | BC-007, BC-010, BC-011, BC-001 | Medium |
| Guardrails AI (Content Safety) | F-057 | Critical | BC-007, BC-009, BC-010, BC-001, BC-004 | High |
| Confidence Scoring System | F-059 | Critical | BC-007, BC-008, BC-009, BC-001, BC-004 | Medium |
| LangGraph Workflow Engine | F-060 | Critical | BC-007, BC-008, BC-004, BC-009, BC-012, BC-001 | Very High |
| Knowledge Base RAG | F-064 | Critical | BC-007, BC-001, BC-004, BC-010, BC-012 | High |

**Implementation Dependencies:**
```
F-054 (Smart Router) ← no dependencies (foundational)
F-056 (PII Redaction) ← no dependencies (foundational)
F-055 (Model Failover) ← depends on F-054
F-057 (Guardrails AI) ← depends on F-056, F-059
F-059 (Confidence Scoring) ← depends on F-054, F-064
F-053 (GSD State Engine) ← depends on F-060, F-054, F-059
F-064 (Knowledge Base RAG) ← depends on F-056
F-060 (LangGraph Workflow) ← depends on F-053, F-054, F-065
```

**Recommended Build Order:**
1. F-056 (PII Redaction) — foundational, no dependencies
2. F-054 (Smart Router) — foundational, no dependencies
3. F-064 (Knowledge Base RAG) — depends on F-056
4. F-055 (Model Failover) — depends on F-054
5. F-059 (Confidence Scoring) — depends on F-054, F-064
6. F-053 (GSD State Engine) — depends on F-054, F-059
7. F-057 (Guardrails AI) — depends on F-056, F-059
8. F-060 (LangGraph Workflow Engine) — depends on everything above

---

> **Document Version:** 1.1
> **Last Updated:** March 2026
> **Total Features Specified:** 8
> **Total Lines:** ~1,800
> **Status:** Ready for implementation planning
