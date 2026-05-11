# PARWA Feature Specs — Batch 10: Final Features

> **14 features** across Quick Commands (F-090), Dynamic Instructions (F-096), Communications (F-126, F-127, F-128), Social (F-130), GraphQL (F-133), Mobile UX (F-086), Marketing (F-002, F-009, F-043), Help (F-045), Peer Review (F-108), and Proactive Outreach (F-129).
>
> **Priority:** 8 MEDIUM · 6 LOW
>
> **Stack:** Next.js · FastAPI · PostgreSQL + pgvector · Redis · Paddle · Brevo · Twilio · Celery · Socket.io · LiteLLM/OpenRouter · DSPy

---

# F-090: Quick Command Buttons (Presets)

## Overview
One-click preset buttons rendered alongside the Jarvis chat panel that execute common commands without typing. Presets include "pause all agents," "export weekly report," "check system health," "escalate all urgent tickets," and tenant-customizable commands. Buttons reduce cognitive load for supervisors managing high-volume operations and enable rapid response during incidents.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/commands/presets` | GET | — | `{ presets: [{ id, label, icon, action_type, params, position, is_system }] }` |
| `/api/commands/presets` | POST | `label`, `icon`, `action_type`, `params` (JSONB), `position` | `{ preset_id, status: "created" }` |
| `/api/commands/presets/{id}` | PUT | `id`, `label`, `icon`, `params`, `position` | `{ preset_id, status: "updated" }` |
| `/api/commands/presets/{id}` | DELETE | `id` | `{ status: "deleted" }` |
| `/api/commands/presets/{id}/execute` | POST | `id` | `{ execution_id, status: "completed", result_summary }` |

## DB Tables
- **`command_presets`** — `id` UUID, `company_id` UUID NOT NULL, `label` VARCHAR(100) NOT NULL, `icon` VARCHAR(50), `action_type` VARCHAR(50) NOT NULL (pause_agents/export_report/health_check/escalate_tickets/custom), `params` JSONB NOT NULL, `position` INT DEFAULT 0, `is_system` BOOL DEFAULT false, `created_by` UUID, `created_at` TIMESTAMPTZ DEFAULT NOW(), `updated_at` TIMESTAMPTZ
  - **Indexes:** `idx_command_presets_company_id ON command_presets(company_id)`, `UNIQUE(company_id, label)`
- **`command_executions`** — `id` UUID, `company_id` UUID NOT NULL, `preset_id` UUID, `executed_by` UUID, `action_type` VARCHAR(50), `params` JSONB, `status` VARCHAR(20) (pending/completed/failed), `result` JSONB, `error_message` TEXT, `started_at` TIMESTAMPTZ, `completed_at` TIMESTAMPTZ, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_command_executions_company_id ON command_executions(company_id)`, `idx_command_executions_preset_id ON command_executions(preset_id)`

## BC Rules
- **BC-005** (Real-Time): Command execution results are pushed via Socket.io to `tenant_{company_id}` room. If the user disconnects mid-execution, results are buffered in `event_buffer` and delivered on reconnection.
- **BC-001** (Multi-Tenant Isolation): All presets and executions scoped by `company_id`. System presets (is_system=true) are available to all tenants but executed in tenant context. No cross-tenant command sharing.
- **BC-004** (Background Jobs): Long-running commands (export_report, health_check) execute as Celery tasks with `company_id` as first param, `max_retries=3`, exponential backoff. Results stored in `command_executions.result`.
- **BC-012** (Error Handling): Failed executions return structured error in `result` with `error_code` and human-readable `message`. Circuit breaker triggers after 5 consecutive failures on the same preset, disabling it with admin notification.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| User clicks a preset while previous execution is still running | Second click is debounced (500ms); if still running, returns HTTP 409 with `{ status: "already_running", execution_id }`. UI shows spinner on the button. |
| System preset conflicts with tenant-customized preset of same action_type | Tenant version takes precedence; system preset is hidden. User can "reset to default" to restore system preset. |
| "Pause all agents" is executed during an active AI resolution | Agents finish current in-flight resolution before pausing. New ticket assignments are blocked immediately. Socket.io broadcasts `agents_paused` event. |
| Export report command generates a large file (> 50MB) | Report generation runs as async Celery task. User receives a notification with download link when complete. Auto-cleanup after 24 hours per BC-010. |
| Tenant attempts to create more than 50 custom presets | Soft limit at 50; HTTP 413 returned with suggestion to archive unused presets. System presets do not count toward limit. |

## Acceptance Criteria
1. **GIVEN** a supervisor is on the dashboard with the Jarvis chat panel open, **WHEN** they click "Pause All Agents" quick command, **THEN** all agents for their tenant are set to paused status within 2 seconds and a confirmation is displayed with affected agent count.
2. **GIVEN** a tenant admin configures a custom preset with label "Escalate Urgent" and action_type "escalate_tickets", **WHEN** any agent clicks that preset, **THEN** all tickets with priority=urgent and status=open are moved to escalation queue and assigned to the next available senior agent.
3. **GIVEN** a long-running "Export Weekly Report" command is executing, **WHEN** the user navigates away and returns, **THEN** the execution status and result (or download link) are still accessible via the command history panel.
4. **GIVEN** a preset execution fails (e.g., health check times out), **WHEN** the user views the execution result, **THEN** a structured error message is displayed with `error_code`, human-readable description, and a "Retry" button that re-executes with the same parameters.

---

# F-096: Dynamic Instruction Workflow

## Overview
Version-controlled instruction management system enabling tenants to create, modify, and A/B test instruction sets that AI agents follow during ticket resolution. Each instruction set defines behavioral rules, tone guidelines, escalation triggers, and response templates. A/B testing routes a configurable percentage of tickets to each variant, measuring resolution quality and customer satisfaction to determine the winning variant.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/instructions/sets` | GET | `agent_id`, `status` (active/draft/archived) | `{ sets: [{ id, name, version, status, agent_id, is_default }] }` |
| `/api/instructions/sets` | POST | `name`, `agent_id`, `instructions` (JSONB), `metadata` | `{ set_id, version: 1, status: "draft" }` |
| `/api/instructions/sets/{id}` | PUT | `id`, `instructions`, `change_summary` | `{ set_id, version: N+1, status: "draft" }` |
| `/api/instructions/sets/{id}/publish` | POST | `id` | `{ set_id, status: "active", version }` |
| `/api/instructions/sets/{id}/archive` | POST | `id` | `{ set_id, status: "archived" }` |
| `/api/instructions/ab-tests` | POST | `set_a_id`, `set_b_id`, `agent_id`, `traffic_split` (0-100), `duration_days`, `success_metric` | `{ test_id, status: "running" }` |
| `/api/instructions/ab-tests/{id}` | GET | `id` | `{ test_id, status, variants: [{ set_id, traffic_pct, tickets, csat_avg, resolution_pct }], winner }` |
| `/api/instructions/ab-tests/{id}/stop` | POST | `id`, `winner_id` (optional) | `{ test_id, status: "completed", winner }` |
| `/api/instructions/sets/{id}/versions` | GET | `id` | `{ versions: [{ version, change_summary, published_by, published_at }] }` |

## DB Tables
- **`instruction_sets`** — `id` UUID, `company_id` UUID NOT NULL, `agent_id` UUID NOT NULL, `name` VARCHAR(200) NOT NULL, `version` INT NOT NULL DEFAULT 1, `status` VARCHAR(20) NOT NULL DEFAULT 'draft' (draft/active/archived), `instructions` JSONB NOT NULL, `is_default` BOOL DEFAULT false, `created_by` UUID, `published_by` UUID, `published_at` TIMESTAMPTZ, `change_summary` TEXT, `created_at` TIMESTAMPTZ DEFAULT NOW(), `updated_at` TIMESTAMPTZ
  - **Indexes:** `idx_instruction_sets_company ON instruction_sets(company_id)`, `idx_instruction_sets_agent ON instruction_sets(agent_id, status)`, `UNIQUE(company_id, agent_id, name, version)`
  - **Constraints:** `CHECK (instructions IS NOT NULL AND jsonb_typeof(instructions) = 'object')`
- **`instruction_versions`** — `id` UUID, `set_id` UUID NOT NULL, `company_id` UUID NOT NULL, `version` INT NOT NULL, `instructions` JSONB NOT NULL, `change_summary` TEXT, `published_by` UUID, `published_at` TIMESTAMPTZ, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_instruction_versions_set ON instruction_versions(set_id, version)`
- **`instruction_ab_tests`** — `id` UUID, `company_id` UUID NOT NULL, `agent_id` UUID NOT NULL, `set_a_id` UUID NOT NULL, `set_b_id` UUID NOT NULL, `traffic_split` INT NOT NULL (percentage for set_a), `success_metric` VARCHAR(50) DEFAULT 'csat', `duration_days` INT DEFAULT 14, `status` VARCHAR(20) DEFAULT 'running' (running/completed/cancelled), `winner_id` UUID, `tickets_a` INT DEFAULT 0, `tickets_b` INT DEFAULT 0, `csat_a` FLOAT, `csat_b` FLOAT, `resolution_a` FLOAT, `resolution_b` FLOAT, `started_at` TIMESTAMPTZ DEFAULT NOW(), `ended_at` TIMESTAMPTZ
  - **Indexes:** `idx_ab_tests_company ON instruction_ab_tests(company_id)`, `idx_ab_tests_agent ON instruction_ab_tests(agent_id, status)`
- **`instruction_ab_assignments`** — `id` UUID, `test_id` UUID, `ticket_id` UUID, `variant` VARCHAR(1) (A/B), `set_id` UUID, `csat_score` FLOAT, `resolved` BOOL, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_ab_assignments_test ON instruction_ab_assignments(test_id)`, `UNIQUE(test_id, ticket_id)`

## BC Rules
- **BC-007** (AI Model Interaction): Instruction sets are injected into the Smart Router's prompt pipeline. The active instruction set (or A/B variant) is part of the GSD state machine context. PII redaction rules within instructions are enforced before any LLM call. Confidence thresholds defined in instructions override global per-company thresholds.
- **BC-008** (State Management): Active instruction set version is stored in Redis as `instruction:{company_id}:{agent_id}` with PostgreSQL as fallback. A/B test routing decision cached in Redis for session consistency.
- **BC-001** (Multi-Tenant Isolation): All instruction sets, versions, and A/B tests scoped by `company_id`. No cross-tenant instruction sharing or visibility.
- **BC-004** (Background Jobs): A/B test evaluation runs as a daily Celery task computing statistical significance (chi-squared or t-test). Auto-completion triggers when p-value < 0.05 with minimum 100 tickets per variant.
- **BC-012** (Error Handling): Publishing instructions validates the JSONB schema; malformed instructions are rejected with specific field-level errors. A/B test with invalid set references is blocked at creation.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Publishing a new instruction set while agents are actively resolving tickets | Active resolutions continue with old instructions. New tickets immediately use the newly published set. No mid-ticket instruction swap. |
| A/B test is stopped early with < 30 tickets per variant | System warns that results may not be statistically significant. Winner selection requires explicit manual confirmation; auto-winner is not computed. |
| Instruction set contains instructions that conflict with system-level guardrails (e.g., "always offer 100% refund") | System validates against guardrail rules at publish time. Conflicting instructions are flagged with specific warnings but not blocked (tenant is authoritative). |
| Two A/B tests are created for the same agent simultaneously | Second creation is rejected with HTTP 409: "Only one active A/B test per agent." Existing test must be stopped first. |
| Instruction set version exceeds 100 revisions | System suggests archiving old versions. Full version history is retained in `instruction_versions` but the GET /versions endpoint paginates at 50 per page. |
| Agent is deleted while A/B test is running | A/B test is auto-cancelled with status="cancelled" and reason="agent_deleted." Assignments remain for historical analysis. |

## Acceptance Criteria
1. **GIVEN** a tenant admin creates a draft instruction set with escalation rules and tone guidelines, **WHEN** they publish it, **THEN** the instruction set becomes the active version for the assigned agent, and a new version record is created with the publisher's identity and timestamp.
2. **GIVEN** two instruction sets (v1 and v2) exist for an agent, **WHEN** an A/B test is started with 50/50 traffic split for 14 days, **THEN** each incoming ticket is deterministically routed to either variant A or B, and CSAT scores and resolution rates are tracked per variant.
3. **GIVEN** an A/B test has accumulated 150 tickets per variant with a statistically significant difference (p < 0.05), **WHEN** the daily evaluation task runs, **THEN** the test auto-completes, the winning variant is promoted to active, and the test creator is notified via Socket.io and email.
4. **GIVEN** an instruction set has 10 published versions, **WHEN** the admin views the version history, **THEN** all versions are listed with change summaries, publishers, and timestamps, and any previous version can be re-published to roll back.

---

# F-126: SMS Handling (Twilio)

## Overview
End-to-end SMS support via Twilio enabling PARWA to receive and send text messages as a customer support channel. Incoming SMS creates or links to existing tickets, AI generates contextual responses, and outbound SMS is sent back to the customer. Full TCPA compliance with opt-in/opt-out management, message rate limiting, and consent tracking per phone number.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/webhooks/twilio/sms/inbound` | POST | `From`, `To`, `Body`, `MessageSid` (Twilio params) | TwiML `<Response><Message>...</Message></Response>` |
| `/api/sms/send` | POST | `ticket_id`, `message`, `recipient_number` | `{ message_id, status: "sent", sid }` |
| `/api/sms/conversations/{number}` | GET | `number`, `limit`, `offset` | `{ messages: [{ sid, direction, body, timestamp }], ticket_id }` |
| `/api/sms/opt-in` | POST | `phone_number`, `consent_source` (webform/keyword/sms_reply), `consent_text` | `{ status: "opted_in", consent_record_id }` |
| `/api/sms/opt-out` | POST | `phone_number`, `reason` (reply_stop/webform/support) | `{ status: "opted_out" }` |
| `/api/sms/consent/{number}` | GET | `number` | `{ phone_number, status: "opted_in"/"opted_out", consent_records: [], last_interaction }` |
| `/api/sms/templates` | GET | — | `{ templates: [{ id, name, body, variables }] }` |

## DB Tables
- **`sms_messages`** — `id` UUID, `company_id` UUID NOT NULL, `ticket_id` UUID, `twilio_sid` VARCHAR(64) UNIQUE, `direction` VARCHAR(10) NOT NULL (inbound/outbound), `from_number` VARCHAR(20) NOT NULL, `to_number` VARCHAR(20) NOT NULL, `body` TEXT NOT NULL, `status` VARCHAR(20) (queued/sent/delivered/undelivered/failed), `error_code` VARCHAR(20), `media_urls` JSONB, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_sms_company ON sms_messages(company_id)`, `idx_sms_ticket ON sms_messages(ticket_id)`, `idx_sms_twilio_sid ON sms_messages(twilio_sid)`, `idx_sms_from_number ON sms_messages(from_number, created_at DESC)`
- **`sms_consent`** — `id` UUID, `company_id` UUID NOT NULL, `phone_number` VARCHAR(20) NOT NULL, `status` VARCHAR(20) NOT NULL DEFAULT 'opted_out' (opted_in/opted_out), `consent_source` VARCHAR(30), `consent_text` TEXT, `consented_at` TIMESTAMPTZ, `opted_out_at` TIMESTAMPTZ, `opt_out_reason` VARCHAR(50), `created_at` TIMESTAMPTZ DEFAULT NOW(), `updated_at` TIMESTAMPTZ
  - **Indexes:** `UNIQUE(company_id, phone_number)`
- **`sms_opt_log`** — `id` UUID, `company_id` UUID, `phone_number` VARCHAR(20), `action` VARCHAR(10) (opt_in/opt_out), `source` VARCHAR(30), `ip_address` INET, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_sms_opt_log_phone ON sms_opt_log(phone_number, created_at DESC)`

## BC Rules
- **BC-003** (Webhook Handling): Twilio inbound SMS webhook validates the `X-Twilio-Signature` HMAC header against the shared auth token. Idempotency enforced via `twilio_sid` UNIQUE constraint. Processing is async via Celery; HTTP 200 with TwiML acknowledgment returned within 3 seconds.
- **BC-006** (Email/SMS): SMS counts toward the same engagement philosophy — max 5 automated SMS per conversation thread per 24 hours. Rate limiting applied per `from_number` + `company_id`.
- **BC-001** (Multi-Tenant Isolation): SMS messages and consent records scoped by `company_id`. Twilio phone numbers are provisioned per-tenant; no shared numbers.
- **BC-010** (Data Lifecycle & GDPR): Phone numbers are classified as PII. Right-to-erasure removes all `sms_messages`, `sms_consent`, and `sms_opt_log` records for the requester. Consent records retained for 7 years per TCPA documentation requirements unless explicitly deleted.
- **BC-011** (Auth & Security): Webhook endpoint does not require JWT (Twilio validates via HMAC). Admin endpoints for opt-in/opt-out management require supervisor+ role.
- **BC-012** (Error Handling): Twilio delivery failures (status=failed/undelivered) trigger retry logic (max 3 retries with exponential backoff). Permanent failures (invalid number, carrier blocked) are flagged on the ticket for agent review.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Customer sends STOP, STOPALL, UNSUBSCRIBE, CANCEL, or QUIT keyword | Auto-processed as opt-out regardless of context. Reply with TCPA-compliant confirmation: "You've been opted out. Reply HELP for info or START to re-subscribe." No further messages sent. |
| Customer sends HELP keyword | Reply with company name, support contact, and opt-in/opt-out instructions. Does not create a ticket. |
| Incoming SMS from an opted-out number | Message is received and logged but no automated response is sent. A ticket is created with status="blocked_sms" and agent is notified to handle manually if needed. |
| Twilio webhook receives the same MessageSid twice | Idempotency check via `twilio_sid` UNIQUE constraint returns HTTP 200 silently. No duplicate ticket or message created. |
| SMS body exceeds 160 characters (GSM-7) or 70 characters (Unicode) | Message is automatically split into concatenated SMS segments by Twilio. PARWA logs the full body as a single message record. AI response generation targets < 320 characters (2 segments). |
| Customer replies to an SMS more than 72 hours after last message | Conversation context is expired. AI generates a re-engagement message acknowledging the gap and asks the customer to confirm their issue is still relevant. |

## Acceptance Criteria
1. **GIVEN** an opted-in customer sends an SMS to the tenant's Twilio number, **WHEN** the Twilio webhook is received, **THEN** a ticket is created (or linked to existing open ticket by phone number) with channel=sms, and an AI-generated response is sent back within 30 seconds.
2. **GIVEN** a customer replies "STOP" to any SMS thread, **WHEN** the keyword is detected, **THEN** the customer's consent status is immediately set to "opted_out" in `sms_consent`, a TCPA-compliant confirmation is sent, and no further automated SMS messages are delivered to that number.
3. **GIVEN** a customer who was previously opted-out sends "START", **WHEN** the keyword is processed, **THEN** the consent status is set to "opted_in" with source="sms_reply", the opt-in timestamp is recorded, and the customer receives a welcome message.
4. **GIVEN** the SMS rate limit of 5 messages per thread per 24 hours has been reached, **WHEN** an automated outbound SMS is attempted, **THEN** the message is suppressed, the suppression is logged in `sms_messages` with status="rate_limited", and the assigned agent is notified via Socket.io.

---

# F-127: Voice Call Handling (Twilio)

## Overview
Bi-directional voice call management via Twilio Voice API supporting inbound and outbound calls with AI voice agent integration. Calls are logged with full event tracking (ringing, answered, transferred, ended), routed to AI voice agents or human agents based on intent and availability, and all calls are recorded and transcribed for quality and compliance. Supports warm transfers between AI and human agents.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/webhooks/twilio/voice/inbound` | POST | `CallSid`, `From`, `To`, `CallStatus` (Twilio params) | TwiML `<Response><Dial>...</Dial></Response>` |
| `/webhooks/twilio/voice/status` | POST | `CallSid`, `CallStatus`, `Duration`, `RecordingUrl` | HTTP 200 (async processing via Celery) |
| `/api/voice/calls` | GET | `status`, `direction`, `from`, `to`, `from_date`, `to_date`, `limit`, `offset` | `{ calls: [{ id, call_sid, direction, from, to, status, duration, recording_url, transcript }] }` |
| `/api/voice/calls/{id}` | GET | `id` | `{ call details, events[], transcript, ticket_id, agent_id }` |
| `/api/voice/calls/{id}/transfer` | POST | `id`, `target_agent_id` | `{ status: "transferring" }` |
| `/api/voice/calls/{id}/recording` | GET | `id` | `{ recording_url, duration, transcript }` |
| `/api/voice/outbound` | POST | `recipient_number`, `ticket_id`, `agent_id` (optional) | `{ call_id, call_sid, status: "initiated" }` |

## DB Tables
- **`voice_calls`** — `id` UUID, `company_id` UUID NOT NULL, `call_sid` VARCHAR(64) UNIQUE, `ticket_id` UUID, `direction` VARCHAR(10) NOT NULL (inbound/outbound), `from_number` VARCHAR(20) NOT NULL, `to_number` VARCHAR(20) NOT NULL, `status` VARCHAR(20) NOT NULL (queued/ringing/in-progress/completed/no-answer/failed/busy), `duration` INT, `recording_url` TEXT, `recording_sid` VARCHAR(64), `transcript` TEXT, `ai_agent_id` UUID, `human_agent_id` UUID, `transfer_from_call_id` UUID, `transfer_reason` TEXT, `disposition` VARCHAR(30) (resolved/transferred/voicemail/callback_scheduled), `quality_score` FLOAT, `created_at` TIMESTAMPTZ DEFAULT NOW(), `ended_at` TIMESTAMPTZ, `updated_at` TIMESTAMPTZ
  - **Indexes:** `idx_voice_company ON voice_calls(company_id)`, `idx_voice_ticket ON voice_calls(ticket_id)`, `idx_voice_call_sid ON voice_calls(call_sid)`, `idx_voice_from ON voice_calls(from_number, created_at DESC)`
- **`voice_call_events`** — `id` UUID, `call_id` UUID NOT NULL, `company_id` UUID NOT NULL, `event_type` VARCHAR(30) NOT NULL (initiated/ringing/answered/hangup/transfer/recording_started/transcription_completed), `event_data` JSONB, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_voice_events_call ON voice_call_events(call_id, created_at)`
- **`voice_transcripts`** — `id` UUID, `call_id` UUID NOT NULL, `company_id` UUID NOT NULL, `speaker` VARCHAR(20) (caller/agent/ai), `text` TEXT, `confidence` FLOAT, `timestamp_offset` FLOAT (seconds into call), `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_transcript_call ON voice_transcripts(call_id, timestamp_offset)`

## BC Rules
- **BC-003** (Webhook Handling): Twilio webhook signature validated via `X-Twilio-Signature` HMAC. Call status callbacks processed asynchronously via Celery with `company_id` as first param. Response within 3 seconds (TwiML generation only).
- **BC-005** (Real-Time): Live call status changes pushed to `tenant_{company_id}` Socket.io room. Agents see real-time call queue with ringing/active calls. Transfer requests are real-time.
- **BC-001** (Multi-Tenant Isolation): Voice calls, events, and transcripts scoped by `company_id`. Twilio numbers are per-tenant provisioned. No cross-tenant call data access.
- **BC-010** (Data Lifecycle & GDPR): Call recordings and transcripts contain PII (voice). Retention policy configurable per-tenant (default 90 days). Right-to-erasure deletes recordings from Twilio and all DB records.
- **BC-006** (Email/SMS): Post-call summary emails sent to customers when call ends (configurable). Rate limited to 1 post-call email per call.
- **BC-012** (Error Handling): Call recording upload failure is retried (max 3). Transcription failure falls back to "transcription unavailable" note on the call record. Twilio API errors trigger circuit breaker after 5 consecutive failures.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Inbound call when all agents are offline or busy | Call enters queue with wait music (configurable). After 60 seconds (configurable), option to leave voicemail or schedule callback. Queue position announced every 30 seconds. |
| AI voice agent encounters a query it cannot handle | AI initiates warm transfer: asks customer to hold, notifies available human agent, and bridges the call. Transcript and context passed to human agent. |
| Call drops mid-conversation (network issue) | Call status webhook fires with "completed" and duration. System logs the drop event. If ticket exists, agent is notified to follow up via SMS or callback. |
| Recording consent is required by jurisdiction but not given | Call proceeds but recording is not started. Transcript is marked as "consent_not_given." Agent is trained to ask for consent at call start via IVR prompt. |
| Caller ID is spoofed or blocked | System still processes the call. `from_number` stored as "blocked" or "unknown." Ticket is created with anonymized caller info. No lookup attempted. |
| Outbound call to a number on DNC (Do Not Call) list | Outbound call is blocked at initiation. Agent/admin is notified with reason "number_on_dnc_list." DNC list maintained per-tenant with import capability. |

## Acceptance Criteria
1. **GIVEN** a customer calls the tenant's Twilio number, **WHEN** the inbound webhook fires, **THEN** the call is logged in `voice_calls`, routed to the AI voice agent or queued for a human agent, and the call status is pushed in real-time to the agent dashboard via Socket.io.
2. **GIVEN** an active call with the AI voice agent, **WHEN** the AI detects a complex issue requiring human intervention, **THEN** the AI performs a warm transfer to an available human agent with the call transcript and ticket context passed along.
3. **GIVEN** a call ends with recording enabled, **WHEN** the status callback fires, **THEN** the recording URL is stored, an async Celery task transcribes the audio, and the transcript is linked to the call record and ticket within 5 minutes.
4. **GIVEN** a customer requests right-to-erasure, **WHEN** the erasure process executes, **THEN** all call recordings are deleted from Twilio storage, and all `voice_calls`, `voice_call_events`, and `voice_transcripts` records for that customer are purged from the database.

---

# F-128: Incoming Call System (Voice-First)

## Overview
Full IVR (Interactive Voice Response) system for incoming voice calls providing self-service routing, AI-powered intent recognition, queue management, and callback scheduling. The IVR presents configurable menu trees, collects caller input via DTMF and speech recognition, and routes to the appropriate AI agent, human agent, or self-service flow. Queue management includes priority queuing, estimated wait time announcements, and voicemail fallback.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/webhooks/twilio/ivr/welcome` | POST | `CallSid`, `From` | TwiML `<Gather>` with IVR menu |
| `/webhooks/twilio/ivr/menu` | POST | `CallSid`, `Digits`, `SpeechResult` | TwiML for next IVR node or transfer |
| `/api/ivr/config` | GET | — | `{ menus: [{ id, prompt_audio_url, options: [{ digit, action, target }] }] }` |
| `/api/ivr/config` | PUT | `menus` (JSONB) | `{ status: "updated", version }` |
| `/api/ivr/callbacks/schedule` | POST | `customer_number`, `preferred_time`, `ticket_id` | `{ callback_id, scheduled_for }` |
| `/api/ivr/callbacks` | GET | `status` (pending/completed/cancelled) | `{ callbacks: [{ id, number, scheduled_for, status }] }` |
| `/api/ivr/queue/status` | GET | — | `{ queue_depth, avg_wait_seconds, longest_wait_seconds }` |

## DB Tables
- **`ivr_configs`** — `id` UUID, `company_id` UUID NOT NULL, `name` VARCHAR(100) NOT NULL, `menu_tree` JSONB NOT NULL, `version` INT DEFAULT 1, `default_prompt_audio_url` TEXT, `timeout_seconds` INT DEFAULT 5, `max_retries` INT DEFAULT 3, `fallback_action` VARCHAR(30) DEFAULT 'queue', `status` VARCHAR(20) DEFAULT 'active', `created_by` UUID, `created_at` TIMESTAMPTZ DEFAULT NOW(), `updated_at` TIMESTAMPTZ
  - **Indexes:** `UNIQUE(company_id, name)`, `idx_ivr_configs_company ON ivr_configs(company_id, status)`
  - **Constraints:** `CHECK (jsonb_typeof(menu_tree) = 'object')`
- **`ivr_sessions`** — `id` UUID, `company_id` UUID NOT NULL, `call_id` UUID, `call_sid` VARCHAR(64), `caller_number` VARCHAR(20), `current_node` VARCHAR(100), `inputs` JSONB (array of {node, input, timestamp}), `route_decision` VARCHAR(30) (ai_agent/human_agent/self_service/voicemail/callback), `routed_agent_id` UUID, `created_at` TIMESTAMPTZ DEFAULT NOW(), `ended_at` TIMESTAMPTZ
  - **Indexes:** `idx_ivr_sessions_call ON ivr_sessions(call_sid)`, `idx_ivr_sessions_company ON ivr_sessions(company_id, created_at DESC)`
- **`call_queue`** — `id` UUID, `company_id` UUID NOT NULL, `call_id` UUID NOT NULL, `caller_number` VARCHAR(20), `priority` INT DEFAULT 5, `position` INT, `entered_at` TIMESTAMPTZ DEFAULT NOW(), `estimated_wait_seconds` INT, `status` VARCHAR(20) (waiting/ringing/answered/abandoned/expired), `answered_by` UUID, `answered_at` TIMESTAMPTZ, `abandoned_at` TIMESTAMPTZ
  - **Indexes:** `idx_call_queue_company_status ON call_queue(company_id, status)`, `idx_call_queue_priority ON call_queue(company_id, priority, entered_at)`
- **`scheduled_callbacks`** — `id` UUID, `company_id` UUID NOT NULL, `ticket_id` UUID, `customer_number` VARCHAR(20) NOT NULL, `customer_name` VARCHAR(100), `reason` TEXT, `scheduled_for` TIMESTAMPTZ NOT NULL, `assigned_agent_id` UUID, `status` VARCHAR(20) DEFAULT 'pending' (pending/in_progress/completed/cancelled/failed), `attempt_count` INT DEFAULT 0, `max_attempts` INT DEFAULT 3, `last_attempt_at` TIMESTAMPTZ, `created_at` TIMESTAMPTZ DEFAULT NOW(), `completed_at` TIMESTAMPTZ
  - **Indexes:** `idx_callbacks_company_status ON scheduled_callbacks(company_id, status)`, `idx_callbacks_scheduled ON scheduled_callbacks(scheduled_for, status)`

## BC Rules
- **BC-003** (Webhook Handling): All Twilio IVR webhooks validate HMAC signature. TwiML generation is synchronous and fast (< 500ms). Post-routing processing (ticket creation, agent notification) is async via Celery.
- **BC-005** (Real-Time): Queue status (depth, wait times) pushed to `tenant_{company_id}` Socket.io room every 5 seconds. New queue entries and dequeues are pushed immediately. Agents see real-time queue widget.
- **BC-007** (AI Model Interaction): AI-powered intent recognition from speech input uses the Smart Router (Fast tier for latency < 2s). Speech-to-text via Twilio transcription; intent classification via LLM. PII redacted from speech transcripts before storage.
- **BC-004** (Background Jobs): Callback execution runs as a scheduled Celery beat task (every 1 minute). Failed callbacks retry with exponential backoff (5m, 15m, 60m). After 3 failed attempts, status="failed" and ticket is flagged.
- **BC-001** (Multi-Tenant Isolation): IVR configs, sessions, queues, and callbacks scoped by `company_id`. No cross-tenant queue mixing.
- **BC-008** (State Management): Active call queue state stored in Redis (`call_queue:{company_id}` sorted set by priority+timestamp) for O(1) enqueue/dequeue. PostgreSQL as persistent record.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Caller doesn't press any digit or speak for 3 consecutive prompts | After max_retries (default 3), route to fallback_action (default: queue for human agent). Log as "ivr_timeout" in session. |
| Queue has 20+ callers and all agents are busy | Estimated wait time announced (e.g., "Estimated wait time is 15 minutes"). Option to leave voicemail or schedule callback offered at each 30-second interval. |
| Caller says "representative" or "agent" at any IVR node | Bypass remaining IVR tree and route directly to queue for human agent. Log intent as "escalate_to_human." |
| Callback scheduled for outside business hours | Callback is accepted but flagged as "off_hours." Execution deferred until next business hours window (configurable per-tenant). Customer notified via SMS of the scheduled time. |
| IVR menu tree has a circular reference (node A → B → A) | Config validation at PUT rejects circular references with specific error: "Circular reference detected: A → B → A." IVR cannot be saved with circular paths. |
| Power outage or Twilio outage during active IVR calls | Calls are dropped (unavoidable). Once service restores, customers who were in queue receive an SMS apology with callback scheduling link. Queue is auto-cleared; no phantom entries. |

## Acceptance Criteria
1. **GIVEN** a customer calls the tenant's Twilio number, **WHEN** the IVR welcome webhook fires, **THEN** the customer hears the configured IVR menu prompt and can navigate via DTMF digits or speech input within 2 seconds of each prompt.
2. **GIVEN** a customer selects "Check order status" via the IVR, **WHEN** the AI intent recognition confirms the selection, **THEN** the customer is routed to a self-service flow that speaks their order status using TTS, and the interaction is logged in `ivr_sessions` with route_decision="self_service."
3. **GIVEN** 5 callers are in the queue with priorities 3, 5, 1, 5, 2, **WHEN** an agent becomes available, **THEN** the caller with priority 1 (highest) is dequeued first, followed by priority 2, then 3, then the two priority-5 callers in FIFO order.
4. **GIVEN** a caller opts to schedule a callback for 2:00 PM tomorrow, **WHEN** the callback time arrives and no agent is available, **THEN** the system retries up to 3 times with exponential backoff (5m, 15m, 60m), and after exhausting retries, marks the callback as "failed" and flags the ticket for follow-up.

---

# F-130: Social Media Integration

## Overview
Unified social media channel support connecting Twitter (X), Instagram, and Facebook as customer support channels. Social media mentions, DMs, and comments are ingested as ticket threads within PARWA, enabling AI and human agents to respond directly through the PARWA dashboard. Supports sentiment analysis, SLA tracking, and response approval workflows for public-facing social interactions.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/webhooks/social/twitter` | POST | `for_user_id`, `tweet_create_events[]` (Twitter webhook) | `{ status: "accepted" }` |
| `/webhooks/social/instagram` | POST | `entry[].changes[]` (Instagram webhook) | `{ status: "accepted" }` |
| `/webhooks/social/facebook` | POST | `entry[].messaging[]` (Facebook webhook) | `{ status: "accepted" }` |
| `/api/social/channels` | GET | — | `{ channels: [{ id, platform, account_name, status, connected_at }] }` |
| `/api/social/channels` | POST | `platform`, `oauth_code`, `redirect_uri` | `{ channel_id, status: "connected" }` |
| `/api/social/channels/{id}/disconnect` | POST | `id` | `{ status: "disconnected" }` |
| `/api/social/tickets/{ticket_id}/reply` | POST | `ticket_id`, `message`, `is_public` (bool) | `{ reply_id, status: "posted" }` |
| `/api/social/tickets` | GET | `platform`, `status`, `sentiment`, `from_date`, `to_date` | `{ tickets: [{ id, platform, author, content, sentiment, ticket_id }] }` |

## DB Tables
- **`social_channels`** — `id` UUID, `company_id` UUID NOT NULL, `platform` VARCHAR(20) NOT NULL (twitter/instagram/facebook), `platform_account_id` VARCHAR(100), `platform_account_name` VARCHAR(100), `access_token` TEXT (encrypted), `refresh_token` TEXT (encrypted), `token_expires_at` TIMESTAMPTZ, `webhook_secret` TEXT (encrypted), `status` VARCHAR(20) DEFAULT 'active' (active/disconnected/expired), `connected_at` TIMESTAMPTZ, `disconnected_at` TIMESTAMPTZ, `created_at` TIMESTAMPTZ DEFAULT NOW(), `updated_at` TIMESTAMPTZ
  - **Indexes:** `UNIQUE(company_id, platform, platform_account_id)`, `idx_social_channels_company ON social_channels(company_id, status)`
- **`social_messages`** — `id` UUID, `company_id` UUID NOT NULL, `channel_id` UUID NOT NULL, `ticket_id` UUID, `platform_message_id` VARCHAR(100) UNIQUE, `platform` VARCHAR(20) NOT NULL, `message_type` VARCHAR(20) NOT NULL (dm/mention/comment/reply), `author_id` VARCHAR(100), `author_username` VARCHAR(100), `content` TEXT NOT NULL, `is_public` BOOL DEFAULT true, `sentiment` VARCHAR(10) (positive/neutral/negative/mixed), `sentiment_score` FLOAT, `media_urls` JSONB, `in_reply_to_message_id` VARCHAR(100), `platform_created_at` TIMESTAMPTZ, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_social_messages_company ON social_messages(company_id)`, `idx_social_messages_ticket ON social_messages(ticket_id)`, `idx_social_messages_platform ON social_messages(channel_id, platform_message_id)`, `idx_social_messages_time ON social_messages(company_id, platform_created_at DESC)`
- **`social_oauth_states`** — `id` UUID, `company_id` UUID, `platform` VARCHAR(20), `state_token` VARCHAR(128) UNIQUE, `redirect_uri` TEXT, `expires_at` TIMESTAMPTZ, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_oauth_state_token ON social_oauth_states(state_token)`

## BC Rules
- **BC-003** (Webhook Handling): All social platform webhooks validate HMAC signatures (Twitter CRC, Instagram App Secret, Facebook App Secret). Idempotency via `platform_message_id` UNIQUE constraint. Async processing via Celery. Response within 3 seconds.
- **BC-001** (Multi-Tenant Isolation): Social channels, messages, and OAuth states scoped by `company_id`. A social account can only be connected to one tenant at a time.
- **BC-005** (Real-Time): New social messages pushed via Socket.io to `tenant_{company_id}` room. Mentions with negative sentiment trigger urgent notification. Real-time counter of unread social messages on dashboard.
- **BC-006** (Email/SMS): High-priority social mentions (negative sentiment, large follower count) trigger email/SMS notifications to supervisors. Rate limited per BC-006 rules.
- **BC-010** (Data Lifecycle & GDPR): Social media usernames and profile data are PII. Right-to-erasure removes all linked `social_messages`. Retention policy default 2 years for social conversations.
- **BC-011** (Auth & Security): OAuth tokens encrypted at rest (AES-256). Token refresh is automatic before expiry. Social channel connections require admin+ role.
- **BC-012** (Error Handling): OAuth token expiry triggers automatic refresh. If refresh fails, channel marked "expired" and admin notified. Platform API rate limits are respected with 429 backoff.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Social media post is deleted by the author before PARWA processes it | Webhook may fire but platform API returns 404 when fetching details. Message logged as "deleted" with available metadata. Ticket annotated with "original content unavailable." |
| Customer sends the same complaint via Twitter DM and Facebook Messenger | Two separate tickets are created (different channels). System detects same customer (via linked identity if available) and cross-references tickets. Not auto-merged. |
| Twitter rate limit (429) is hit during reply posting | Reply is queued in Redis with retry after rate limit window. Agent sees "pending delivery" status. Auto-retry at window reset. |
| Public reply on Twitter exceeds 280 characters | System auto-truncates with "..." and adds a link to the full response hosted on PARWA. Warning shown to agent before posting. |
| Instagram DM contains an image with no text | Image is downloaded and stored as media_url. AI vision model (via Smart Router) analyzes the image for intent. Ticket created with image context. |
| Facebook page is unlinked/unpublished by the page owner | Webhooks fail silently. Channel status set to "disconnected." Admin notified. Incoming messages from before disconnection are still processed. |

## Acceptance Criteria
1. **GIVEN** a tenant has connected their Twitter account, **WHEN** a customer mentions the tenant's handle in a tweet, **THEN** a ticket is created with channel=twitter, the tweet content is stored in `social_messages`, and the agent dashboard shows the new ticket in real-time via Socket.io.
2. **GIVEN** a tenant has connected Instagram and Facebook, **WHEN** a customer sends a DM on either platform, **THEN** the message is ingested, sentiment analysis is run, and a ticket is created with the sentiment score displayed to the responding agent.
3. **GIVEN** an agent is replying to a public Twitter mention, **WHEN** the reply exceeds 280 characters, **THEN** the system truncates the reply, shows a preview with character count, and provides a link to the full response before the agent confirms posting.
4. **GIVEN** a customer exercises GDPR right-to-erasure and their social messages are linked to their profile, **WHEN** the erasure process runs, **THEN** all `social_messages` records for that customer are deleted, and any remaining references are anonymized.

---

# F-133: GraphQL Integration

## Overview
Custom GraphQL API layer enabling tenants to query PARWA data (tickets, customers, agents, analytics) via configurable GraphQL endpoints with tenant-scoped schemas and permission-based field access. Provides a self-service data exploration tool for tenants who need custom reporting, dashboard integrations, or data synchronization with external BI tools.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/graphql/{tenant_token}` | POST | GraphQL query/mutation in request body | `{ data: {}, errors: [] }` |
| `/api/graphql/admin/schema` | GET | — | `{ schema: { types, queries, mutations } }` |
| `/api/graphql/admin/permissions` | PUT | `role_id`, `allowed_types[]`, `allowed_fields{} (per type)` | `{ status: "updated" }` |
| `/api/graphql/admin/introspection` | GET | `enable` (bool) | `{ introspection_enabled: bool }` |
| `/api/graphql/admin/query-logs` | GET | `from_date`, `to_date`, `status` | `{ logs: [{ query_hash, execution_time_ms, complexity, user_id }] }` |

## DB Tables
- **`graphql_schemas`** — `id` UUID, `company_id` UUID NOT NULL, `schema_version` INT DEFAULT 1, `schema_definition` JSONB NOT NULL (SDL or programmatic schema), `custom_types` JSONB (tenant-defined types), `custom_resolvers` JSONB (field-level resolver mappings), `status` VARCHAR(20) DEFAULT 'active', `created_by` UUID, `created_at` TIMESTAMPTZ DEFAULT NOW(), `updated_at` TIMESTAMPTZ
  - **Indexes:** `UNIQUE(company_id, schema_version)`, `idx_graphql_schemas_company ON graphql_schemas(company_id, status)`
- **`graphql_permissions`** — `id` UUID, `company_id` UUID NOT NULL, `role_id` UUID NOT NULL, `allowed_types` JSONB NOT NULL (array of type names), `allowed_fields` JSONB NOT NULL (object: type_name → array of field names), `max_complexity` INT DEFAULT 500, `max_depth` INT DEFAULT 5, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `UNIQUE(company_id, role_id)`
- **`graphql_query_logs`** — `id` UUID, `company_id` UUID NOT NULL, `user_id` UUID, `query_hash` VARCHAR(64), `query` TEXT, `variables` JSONB, `operation_name` VARCHAR(100), `execution_time_ms` INT, `complexity_score` INT, `depth` INT, `status` VARCHAR(20) (success/error/timeout), `error_message` TEXT, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_graphql_logs_company ON graphql_query_logs(company_id, created_at DESC)`, `idx_graphql_logs_hash ON graphql_query_logs(query_hash)`
- **`graphql_api_tokens`** — `id` UUID, `company_id` UUID NOT NULL, `token_hash` VARCHAR(128) UNIQUE, `name` VARCHAR(100), `role_id` UUID, `permissions_scope` VARCHAR(20) (read_only/read_write), `rate_limit_rpm` INT DEFAULT 60, `last_used_at` TIMESTAMPTZ, `expires_at` TIMESTAMPTZ, `status` VARCHAR(20) DEFAULT 'active', `created_by` UUID, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_graphql_tokens_company ON graphql_api_tokens(company_id, status)`, `idx_graphql_tokens_hash ON graphql_api_tokens(token_hash)`

## BC Rules
- **BC-001** (Multi-Tenant Isolation): Every GraphQL query is scoped by `company_id` extracted from the API token or JWT. Schema introspection and field resolution automatically inject `company_id` filters. No query can access data outside its tenant scope — enforced at the resolver level, not just the schema level.
- **BC-011** (Auth & Security): GraphQL API tokens are separate from JWT tokens. Tokens are hashed (SHA-256) before storage. Token-based auth requires `Authorization: Bearer <token>` or `X-API-Token: <token>` header. Max 5 active tokens per company. Introspection is disabled by default for security.
- **BC-012** (Error Handling): GraphQL errors follow structured format: `{ message, code, path, extensions: { timestamp, request_id } }`. No stack traces. Queries exceeding `max_complexity` or `max_depth` are rejected before execution. Query timeout at 10 seconds.
- **BC-005** (Real-Time): GraphQL subscriptions supported via WebSocket transport for real-time data (new tickets, status changes). Subscriptions scoped by `company_id`. Subscription events use Socket.io under the hood.
- **BC-010** (Data Lifecycle & GDPR): PII fields (email, phone) are not included in default schema. Tenants must explicitly enable PII fields via permissions configuration. Query logs containing PII are retained for 30 days then purged.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Query exceeds max_complexity (500) or max_depth (5) | Query is rejected with `{ error: { code: "COMPLEXITY_EXCEEDED", message: "Query complexity 832 exceeds limit of 500" } }` before any database access. |
| Tenant tries to query another tenant's data via crafted query | Resolvers enforce `company_id` filter at the database level. Even if the schema somehow exposes a cross-tenant field, the resolver's WHERE clause includes `company_id = :current_company_id`. Return empty result, log security event. |
| GraphQL subscription client disconnects and reconnects | Subscription events buffered in `event_buffer` (Redis) for up to 60 seconds. On reconnect, missed events are replayed. Connection heartbeat every 15 seconds. |
| Recursive query (type A references type B which references type A) | Depth limit prevents infinite recursion. At max_depth, circular references return null for the nested field with `{ error: { code: "DEPTH_LIMIT" } }` in the path. |
| API token is expired but still being used | Request rejected with HTTP 401 and `{ error: { code: "TOKEN_EXPIRED" } }`. Token owner notified via email to renew or rotate. Expired tokens auto-deactivated in daily cleanup task. |
| Tenant customizes schema with a field name that conflicts with a reserved system field | Schema validation rejects the field with `{ error: "Reserved field name: 'id'. Use a prefix or suffix." }`. Reserved names: `id`, `company_id`, `created_at`, `updated_at`, `deleted_at`. |

## Acceptance Criteria
1. **GIVEN** a tenant creates a GraphQL API token with read_only scope, **WHEN** they send a query for `{ tickets { id subject status customer { name } } }`, **THEN** the response returns tickets scoped to their `company_id` only, with execution time < 1 second for up to 100 tickets.
2. **GIVEN** a tenant's admin configures field-level permissions allowing the "agent" role to access `tickets{ id, subject, status }` but NOT `tickets{ customer { email } }`, **WHEN** an agent queries `tickets { id subject status customer { email } }`, **THEN** the response returns `{ data: { tickets: [{ id, subject, status, customer: null }] }, errors: [{ path: ["tickets", 0, "customer", "email"], code: "FIELD_NOT_PERMITTED" }] }`.
3. **GIVEN** a GraphQL subscription is active for `ticketCreated`, **WHEN** a new ticket is created in the tenant's account, **THEN** the subscription client receives the new ticket payload within 2 seconds via WebSocket.
4. **GIVEN** a query takes longer than 10 seconds to execute, **WHEN** the timeout is reached, **THEN** the query is cancelled, a `{ code: "TIMEOUT" }` error is returned, and the query is logged in `graphql_query_logs` with `status="timeout"` for performance analysis.

---

# F-086: Swipe Gestures (Mobile Approve/Reject)

## Overview
Mobile-native swipe gesture interface for rapid approval and rejection of tickets, refund requests, and escalation items. Swipe-right triggers approval, swipe-left triggers rejection, with haptic feedback on gesture completion. Designed for supervisors and agents who process high volumes of approval items on mobile devices, reducing time-per-decision from taps to a single fluid gesture.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/approvals/queue` | GET | `type`, `status`, `limit` (default 50), `offset` | `{ items: [{ id, type, summary, amount, requester, urgency }] }` |
| `/api/approvals/{id}/approve` | POST | `id`, `note` (optional) | `{ status: "approved", ticket_updated: true }` |
| `/api/approvals/{id}/reject` | POST | `id`, `reason`, `note` (optional) | `{ status: "rejected", ticket_updated: true }` |
| `/api/approvals/{id}` | GET | `id` | `{ id, type, summary, amount, details, requester, history[] }` |
| `/api/mobile/swipe-stats` | GET | `date_from`, `date_to` | `{ approved: 45, rejected: 12, avg_time_per_decision_ms: 1800 }` |

## DB Tables
- **`approval_queue`** — `id` UUID, `company_id` UUID NOT NULL, `ticket_id` UUID NOT NULL, `type` VARCHAR(30) NOT NULL (refund/escalation/credit/override), `summary` TEXT, `details` JSONB, `amount` DECIMAL(10,2), `requester_id` UUID, `assignee_id` UUID, `status` VARCHAR(20) NOT NULL DEFAULT 'pending' (pending/approved/rejected/cancelled), `priority` INT DEFAULT 5, `resolved_by` UUID, `resolution_note` TEXT, `rejection_reason` VARCHAR(50), `swipe_gesture_used` BOOL DEFAULT false, `resolved_at` TIMESTAMPTZ, `expires_at` TIMESTAMPTZ, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_approval_queue_company ON approval_queue(company_id, status)`, `idx_approval_queue_assignee ON approval_queue(assignee_id, status)`, `idx_approval_queue_priority ON approval_queue(company_id, priority, created_at)`
- **`swipe_gesture_logs`** — `id` UUID, `company_id` UUID NOT NULL, `user_id` UUID NOT NULL, `approval_id` UUID NOT NULL, `direction` VARCHAR(10) NOT NULL (left/right), `swipe_velocity` FLOAT, `swipe_duration_ms` INT, `haptic_pattern` VARCHAR(20), `device_info` JSONB, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_swipe_logs_user ON swipe_gesture_logs(user_id, created_at DESC)`, `UNIQUE(approval_id)` — one gesture per approval

## BC Rules
- **BC-009** (Approval Workflow): Financial approvals (refund, credit) require supervisor+ role. Approval actions are logged in `audit_trail` with `swipe_gesture_used=true` flag. Rejection requires a `rejection_reason` (mandatory field). Consequences of approval (e.g., refund amount) are displayed before the swipe completes.
- **BC-005** (Real-Time): Approval status changes pushed via Socket.io to `tenant_{company_id}` room. Queue depth updates pushed in real-time. When an item is approved/rejected, it's removed from all connected mobile views within 1 second.
- **BC-001** (Multi-Tenant Isolation): Approval queue and swipe logs scoped by `company_id`. Users can only approve/reject items assigned to them or visible to their role.
- **BC-012** (Error Handling): Swipe gesture with insufficient velocity (< 50px/s) does not trigger action — card snaps back. Network failure during swipe action queues the action locally and retries when connectivity restores. Offline swipes synced with conflict resolution (last-write-wins with server timestamp).

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| User swipes but network is offline | Action queued in local storage (IndexedDB). On reconnect, actions are synced. If the approval was already resolved by another user, a conflict notification is shown: "This item was already resolved by [name]. Your action was not applied." |
| User accidentally swipes (fast accidental gesture) | Minimum swipe distance threshold (30% of card width) and velocity threshold prevent accidental triggers. Confirmation for items with amount > $500 (configurable). |
| Approval item expires while in the queue | Expired items are marked `status="cancelled"` with reason "expired." Removed from queue automatically. Requester notified via Socket.io and email. |
| User has 100+ items in approval queue | Pagination loads 50 items at a time with infinite scroll. Swipe on last visible item loads next 50. Total count displayed at top of queue. |
| Swipe right on a refund approval for amount > $1,000 | Additional confirmation modal appears before action is committed: "Approve refund of $1,247.50?" with Cancel/Confirm buttons. This overrides the no-confirmation swipe UX for high-value items. |
| Device does not support haptic feedback (older mobile or web) | Feature gracefully degrades — swipe still works, but haptic feedback is skipped. Visual feedback (card color change: green for approve, red for reject) is the primary indicator. |

## Acceptance Criteria
1. **GIVEN** a supervisor opens the approval queue on their mobile device, **WHEN** they swipe right on a refund approval item, **THEN** haptic feedback triggers, the item turns green and animates off screen, the approval is committed, and the next item slides into view within 500ms.
2. **GIVEN** a supervisor swipes left to reject an escalation item, **WHEN** the rejection requires a reason, **THEN** a bottom sheet slides up with a reason picker (duplicate/spam/out_of_scope/other) and optional note field, and the rejection is committed only after the reason is selected.
3. **GIVEN** the mobile device loses network connectivity, **WHEN** the supervisor swipes to approve 3 items, **THEN** all 3 actions are stored locally, and upon reconnection, all 3 are synced to the server with the correct timestamps.
4. **GIVEN** an approval item has an amount > $1,000, **WHEN** the supervisor swipes right, **THEN** a confirmation modal appears showing the amount and ticket details, requiring explicit tap confirmation before the approval is committed.

---

# F-002: Dogfooding Banner

## Overview
A prominent banner on the PARWA public website (landing page) announcing that PARWA's own customer support is powered by PARWA AI. This serves as a live proof-of-concept, demonstrating confidence in the product and providing a transparent trust signal to prospective customers. The banner links to the live PARWA-powered support experience.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/public/dogfood-banner` | GET | — | `{ enabled: bool, variant: "A"/"B", text, cta_url, cta_label, stats: { ai_resolved_pct, avg_response_time_s } }` |
| `/api/admin/dogfood-banner` | PUT | `enabled`, `variant`, `text`, `cta_url`, `cta_label` | `{ status: "updated" }` |
| `/api/public/dogfood-stats` | GET | — | `{ tickets_today: 847, ai_resolved_pct: 78.3, avg_response_time_s: 4.2, csat: 4.6 }` |

## DB Tables
- **`dogfood_banner_config`** — `id` UUID, `company_id` UUID (NULL for system-level), `enabled` BOOL DEFAULT true, `variant` VARCHAR(1) DEFAULT 'A', `text_template` VARCHAR(500), `cta_url` VARCHAR(500), `cta_label` VARCHAR(100), `show_live_stats` BOOL DEFAULT true, `stats_refresh_interval_s` INT DEFAULT 300, `created_at` TIMESTAMPTZ DEFAULT NOW(), `updated_at` TIMESTAMPTZ
  - **Constraints:** Single row only — `CHECK (id = '00000000-0000-0000-0000-000000000001'::uuid)` (system singleton)
- **`dogfood_banner_analytics`** — `id` UUID, `variant` VARCHAR(1), `event_type` VARCHAR(20) (impression/click/dismiss), `session_id` VARCHAR(128), `referrer` TEXT, `user_agent` TEXT, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_dogfood_analytics ON dogfood_banner_analytics(variant, event_type, created_at)`

## BC Rules
- **BC-012** (Error Handling): Banner gracefully degrades if the stats API is unavailable — shows static text without live metrics. Circuit breaker disables live stats after 3 consecutive failures and shows cached stats from last successful fetch.
- **BC-010** (Data Lifecycle & GDPR): Banner analytics do not collect PII. Session IDs are hashed. Analytics data retained for 90 days. No cookies — uses sessionStorage only.
- **BC-001** (Multi-Tenant Isolation): This is a system-level feature (PARWA's own site), not tenant-scoped. The `company_id` is NULL. Only PARWA system admins can modify the banner configuration.
- **BC-005** (Real-Time): Live stats (AI resolution rate, avg response time) are cached in Redis and refreshed every 5 minutes via scheduled task. Public endpoint reads from Redis for < 10ms response time.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| AI resolution rate drops below 50% | Banner automatically switches to a less specific message: "Powered by PARWA AI" without displaying the percentage. Admin is notified to review AI performance. |
| Banner stats API times out (> 3s) | Banner renders with cached stats from Redis. If Redis is also empty, banner renders with "Powered by PARWA AI" static text and no stats. |
| User dismisses the banner | Banner is hidden for the session (sessionStorage). Reappears on next visit or new session. Dismissal is logged as analytics event. |
| A/B test between two banner variants | Variant assignment is deterministic (based on session ID hash % 2) for consistency within a session. Click-through rates tracked per variant. |

## Acceptance Criteria
1. **GIVEN** the dogfooding banner is enabled, **WHEN** a visitor loads the PARWA landing page, **THEN** a visually prominent banner is displayed with the text "Our support is powered by PARWA AI — [stats]" including live AI resolution percentage.
2. **GIVEN** the banner displays live stats, **WHEN** a visitor clicks the CTA button, **THEN** they are directed to the PARWA-powered support experience (chat widget or help center), and the click is logged in `dogfood_banner_analytics`.
3. **GIVEN** the stats API is temporarily unavailable, **WHEN** the banner loads, **THEN** it renders with the last known cached stats or degrades to static text without displaying an error to the visitor.
4. **GIVEN** a visitor dismisses the banner, **WHEN** they navigate to another page on the same site, **THEN** the banner remains hidden for the duration of the session but reappears on their next visit.

---

# F-009: Newsletter Subscription (Footer)

## Overview
Email capture form integrated into the public website footer and select landing pages, connected to Brevo for marketing drip campaigns. Implements double opt-in flow, preference management (frequency, topics), and GDPR-compliant consent tracking. Serves as the primary lead generation mechanism for marketing communications.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/public/newsletter/subscribe` | POST | `email`, `consent_text`, `source` (footer/landing/popup), `preferences` (JSONB) | `{ status: "pending_confirmation", message: "Check your email to confirm" }` |
| `/api/public/newsletter/confirm` | GET | `token` (URL param) | `{ status: "confirmed", message: "Welcome!" }` |
| `/api/public/newsletter/unsubscribe` | GET | `token` (URL param) | `{ status: "unsubscribed" }` |
| `/api/public/newsletter/preferences` | GET | `token` | `{ email, frequency, topics[], status }` |
| `/api/public/newsletter/preferences` | PUT | `token`, `frequency`, `topics[]` | `{ status: "updated" }` |
| `/webhooks/brevo/marketing` | POST | `event` (unsubscribe/spam/complaint), `email` | HTTP 200 |

## DB Tables
- **`newsletter_subscriptions`** — `id` UUID, `email` VARCHAR(255) NOT NULL, `status` VARCHAR(20) NOT NULL DEFAULT 'pending' (pending/confirmed/unsubscribed/spam/complaint/bounced), `consent_text` TEXT, `consent_ip` INET, `source` VARCHAR(30), `double_opt_in_token` VARCHAR(128) UNIQUE, `double_opt_in_sent_at` TIMESTAMPTZ, `confirmed_at` TIMESTAMPTZ, `unsubscribed_at` TIMESTAMPTZ, `unsubscribed_reason` VARCHAR(50), `preferences` JSONB DEFAULT '{"frequency": "weekly", "topics": ["product_updates", "tips"]}', `brevo_contact_id` VARCHAR(100), `created_at` TIMESTAMPTZ DEFAULT NOW(), `updated_at` TIMESTAMPTZ
  - **Indexes:** `UNIQUE(email)`, `idx_newsletter_status ON newsletter_subscriptions(status)`, `idx_newsletter_token ON newsletter_subscriptions(double_opt_in_token)`
  - **Constraints:** `CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')`
- **`newsletter_events`** — `id` UUID, `subscription_id` UUID, `event_type` VARCHAR(30) (subscribed/confirmed/unsubscribed/bounced/spam/complaint/opened/clicked), `metadata` JSONB, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_newsletter_events_sub ON newsletter_events(subscription_id, created_at DESC)`, `idx_newsletter_events_type ON newsletter_events(event_type, created_at DESC)`

## BC Rules
- **BC-006** (Email): Double opt-in email sent via Brevo with branded template. Confirmation email within 60 seconds of subscribe call. Unsubscribe link in every marketing email (required by CAN-SPAM and GDPR). Brevo contact sync on status change.
- **BC-010** (Data Lifecycle & GDPR): Explicit consent recorded with consent text and IP address. Unsubscription is immediate and irrevocable without re-consent. Right-to-erasure deletes the subscription record from both PARWA and Brevo via API. No data sharing with third parties.
- **BC-012** (Error Handling): Brevo API failure during subscription sync is retried (max 3). Duplicate email on subscribe returns `{ status: "already_subscribed" }` with current status. Bounced emails auto-set status="bounced."
- **BC-001** (Multi-Tenant Isolation): This is a system-level feature (PARWA marketing). No `company_id` scoping. Separate Brevo list for PARWA marketing vs. tenant communications.
- **BC-004** (Background Jobs): Brevo sync runs as a Celery task. Double opt-in email sending is async. Daily cleanup of unconfirmed subscriptions older than 7 days.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| User subscribes with an email already in "unsubscribed" status | Re-subscription requires fresh double opt-in. Previous consent is not reused. Status changes from "unsubscribed" to "pending." User is informed they previously unsubscribed. |
| User reports email as spam in their email client | Brevo webhook fires `event=spam`. Subscription auto-set to "spam." No further emails sent. Logged in `newsletter_events.` |
| Double opt-in confirmation link expires (> 7 days) | Token is invalidated. User must re-subscribe. Link shows "This link has expired. Please subscribe again." |
| Subscribe API is called with a disposable/temporary email domain | Email is accepted (we don't block domains), but Brevo may bounce it later. Bounce webhook updates status. |
| User subscribes from a GDPR-restricted country (EU) | Consent text must include GDPR-compliant language. Additional checkbox for marketing consent is required. Cookie consent banner must be acknowledged before form is submittable. |

## Acceptance Criteria
1. **GIVEN** a visitor enters their email in the footer newsletter form, **WHEN** they submit the form, **THEN** the email is stored with status="pending", a double opt-in confirmation email is sent via Brevo within 60 seconds, and the visitor sees a confirmation message.
2. **GIVEN** a pending subscriber clicks the confirmation link in their email, **WHEN** the confirm endpoint processes the valid token, **THEN** the subscription status changes to "confirmed," the contact is synced to Brevo as active, and a welcome email is triggered.
3. **GIVEN** a confirmed subscriber clicks "Unsubscribe" in any marketing email, **WHEN** the unsubscribe webhook or link is processed, **THEN** the subscription status immediately changes to "unsubscribed," the Brevo contact is updated, and no further marketing emails are sent to that address.
4. **GIVEN** a subscriber updates their preferences to "monthly" frequency and deselects "tips" topic, **WHEN** the preference update is saved, **THEN** the Brevo contact attributes are synced, and the subscriber only receives monthly product update emails.

---

# F-043: Feature Discovery Teaser

## Overview
Contextual banner and tooltip system that highlights underused or newly released features based on the tenant's current configuration and usage patterns. The system analyzes feature adoption metrics and surfaces relevant feature teasers at strategic points in the UI, driving engagement with capabilities the tenant may not be aware of.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/features/teasers` | GET | `context` (dashboard/tickets/agents/settings) | `{ teasers: [{ id, feature_id, title, description, position, cta_url, priority }] }` |
| `/api/features/teasers/{id}/dismiss` | POST | `id` | `{ status: "dismissed" }` |
| `/api/features/teasers/{id}/engage` | POST | `id` | `{ status: "engaged", feature_id }` |
| `/api/admin/feature-teasers` | POST | `feature_id`, `title`, `description`, `position`, `context`, `targeting_rules` (JSONB), `cta_url` | `{ teaser_id }` |
| `/api/admin/feature-teasers/{id}` | PUT | `id`, `updates` | `{ status: "updated" }` |
| `/api/features/usage-insights` | GET | — | `{ underused_features: [{ feature_id, name, activation_pct, potential_benefit }] }` |

## DB Tables
- **`feature_teasers`** — `id` UUID, `company_id` UUID (NULL for global teasers), `feature_id` VARCHAR(20) NOT NULL, `title` VARCHAR(200) NOT NULL, `description` TEXT, `position` VARCHAR(30) (top_banner/sidebar_tooltip/modal/inline), `context` VARCHAR(30) (dashboard/tickets/agents/settings/any), `targeting_rules` JSONB (min_plan, not_activated_features, activation_date_before, usage_below_pct), `cta_url` VARCHAR(500), `cta_label` VARCHAR(100), `priority` INT DEFAULT 5, `status` VARCHAR(20) DEFAULT 'active', `start_date` DATE, `end_date` DATE, `max_impressions` INT, `current_impressions` INT DEFAULT 0, `dismiss_count` INT DEFAULT 0, `engage_count` INT DEFAULT 0, `created_at` TIMESTAMPTZ DEFAULT NOW(), `updated_at` TIMESTAMPTZ
  - **Indexes:** `idx_teasers_company ON feature_teasers(company_id, status)`, `idx_teasers_context ON feature_teasers(context, status)`
- **`feature_teaser_dismissals`** — `id` UUID, `teaser_id` UUID NOT NULL, `company_id` UUID NOT NULL, `user_id` UUID NOT NULL, `dismissed_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `UNIQUE(teaser_id, user_id)`
- **`feature_usage_metrics`** — `id` UUID, `company_id` UUID NOT NULL, `feature_id` VARCHAR(20) NOT NULL, `activated` BOOL DEFAULT false, `activation_date` DATE, `last_used_date` DATE, `usage_count_30d` INT DEFAULT 0, `usage_count_total` INT DEFAULT 0, `computed_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `UNIQUE(company_id, feature_id)`

## BC Rules
- **BC-001** (Multi-Tenant Isolation): Teasers are either global (company_id=NULL, shown to all) or tenant-specific. Targeting rules evaluate per-tenant. Dismissals tracked per-user per-tenant.
- **BC-012** (Error Handling): If usage metrics are unavailable (new tenant, no data), teaser system shows general "new feature" teasers rather than usage-based ones. No UI errors.
- **BC-010** (Data Lifecycle & GDPR): Teaser dismissal data is not PII. Retained for 90 days. Usage metrics are aggregated — no individual user tracking for targeting.
- **BC-005** (Real-Time): New teaser availability pushed via Socket.io when a feature is activated or usage patterns change significantly. Teaser dismissals are instant (local + API).

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| User has dismissed 5 teasers in the last 7 days | Teaser frequency is throttled — no new teasers shown for 48 hours. Prevents "notification fatigue." Counter resets weekly. |
| Targeting rules conflict (e.g., "not_activated: SMS" but tenant has SMS active) | Rule engine evaluates all rules with AND logic. If any rule fails, teaser is not shown. Rules are validated at creation time for logical consistency. |
| Teaser's end_date has passed | Teaser auto-deactivated. Not shown to any users. Admin can reactivate by updating the end_date. |
| Tenant is on the free plan and teaser promotes a Pro-only feature | Targeting rule `min_plan: "pro"` prevents showing. Instead, teaser is replaced with an upsell teaser: "Upgrade to Pro to unlock [feature]." |
| Multiple teasers qualify for the same position | Priority ordering applies. Only one teaser shown per position at a time. Others queued in rotation (round-robin on page reload). |

## Acceptance Criteria
1. **GIVEN** a tenant has not activated the SMS channel (F-126), **WHEN** the admin loads the dashboard, **THEN** a teaser banner is displayed promoting SMS integration with a CTA button linking to the SMS setup wizard.
2. **GIVEN** a user dismisses a teaser, **WHEN** they reload the page or navigate within the app, **THEN** the dismissed teaser does not reappear for that user, and the dismissal is recorded in `feature_teaser_dismissals`.
3. **GIVEN** a teaser has `max_impressions=1000` and `current_impressions=998`, **WHEN** 3 more users view the teaser, **THEN** 2 see the teaser (reaching 1000) and the 3rd does not, because the teaser is auto-deactivated after reaching the impression cap.
4. **GIVEN** the feature usage metrics show that a tenant has activated "Knowledge Base" but has < 10 articles, **WHEN** the admin visits the settings page, **THEN** a tooltip teaser appears next to the Knowledge Base menu item suggesting "Add more articles to improve AI resolution rates."

---

# F-045: Contextual Help System

## Overview
In-app help overlay that provides relevant documentation, video tutorials, and support options based on the user's current location within the application. The system detects the current page, feature context, and user role to surface the most relevant help content without requiring the user to search. Includes a persistent help button, searchable knowledge base overlay, and guided tours for new features.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/help/context` | GET | `page_path`, `feature_area`, `user_role` | `{ articles: [{ id, title, excerpt, url }], videos: [{ id, title, thumbnail, url, duration }], guided_tour: { id, steps[] } }` |
| `/api/help/search` | GET | `query`, `category`, `limit` | `{ results: [{ id, title, excerpt, category, url }] }` |
| `/api/help/articles/{id}` | GET | `id` | `{ id, title, content_html, related_articles[], updated_at }` |
| `/api/help/guided-tours/{id}/progress` | PUT | `id`, `step_index`, `completed` | `{ progress_pct, next_step }` |
| `/api/help/feedback` | POST | `article_id`, `helpful` (bool), `comment` | `{ status: "recorded" }` |
| `/api/admin/help/articles` | POST | `title`, `content_html`, `categories[]`, `context_tags[]`, `video_url` | `{ article_id }` |
| `/api/admin/help/guided-tours` | POST | `name`, `feature_id`, `steps[]` (JSONB with selector, title, content) | `{ tour_id }` |

## DB Tables
- **`help_articles`** — `id` UUID, `company_id` UUID (NULL for global articles), `title` VARCHAR(300) NOT NULL, `content_html` TEXT NOT NULL, `excerpt` VARCHAR(500), `categories` JSONB (e.g., ["getting-started", "agents", "billing"]), `context_tags` JSONB (e.g., ["page:dashboard", "feature:chat", "role:admin"]), `video_url` TEXT, `video_duration_s` INT, `thumbnail_url` TEXT, `sort_order` INT DEFAULT 0, `status` VARCHAR(20) DEFAULT 'published' (draft/published/archived), `helpful_count` INT DEFAULT 0, `not_helpful_count` INT DEFAULT 0, `view_count` INT DEFAULT 0, `created_by` UUID, `published_at` TIMESTAMPTZ, `created_at` TIMESTAMPTZ DEFAULT NOW(), `updated_at` TIMESTAMPTZ
  - **Indexes:** `idx_help_articles_context ON help_articles USING GIN(context_tags)`, `idx_help_articles_categories ON help_articles USING GIN(categories)`, `idx_help_articles_company ON help_articles(company_id, status)`
- **`help_guided_tours`** — `id` UUID, `company_id` UUID (NULL for global), `name` VARCHAR(200) NOT NULL, `feature_id` VARCHAR(20), `steps` JSONB NOT NULL (array of { selector, title, content, position }), `trigger_rules` JSONB (e.g., { "new_user": true, "feature_first_use": "chat" }), `status` VARCHAR(20) DEFAULT 'active', `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_help_tours_company ON help_guided_tours(company_id, status)`
- **`help_tour_progress`** — `id` UUID, `tour_id` UUID NOT NULL, `user_id` UUID NOT NULL, `current_step` INT DEFAULT 0, `completed` BOOL DEFAULT false, `completed_at` TIMESTAMPTZ, `started_at` TIMESTAMPTZ, `updated_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `UNIQUE(tour_id, user_id)`
- **`help_article_feedback`** — `id` UUID, `article_id` UUID NOT NULL, `user_id` UUID NOT NULL, `helpful` BOOL, `comment` TEXT, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `UNIQUE(article_id, user_id)`

## BC Rules
- **BC-012** (Error Handling): Help overlay loads asynchronously and does not block page rendering. If the help API fails, the help button remains clickable but shows "Help is temporarily unavailable" with a fallback link to the external docs site. Circuit breaker after 5 consecutive failures.
- **BC-001** (Multi-Tenant Isolation): Help articles can be global (company_id=NULL, available to all) or tenant-specific (custom help for tenant's branded experience). Context detection is per-user.
- **BC-011** (Auth & Security): Admin endpoints for creating/editing articles require admin+ role. Help content does not expose any tenant data. Context tags are predefined — no arbitrary values accepted.
- **BC-010** (Data Lifecycle & GDPR): Article feedback does not collect PII. User IDs in `help_tour_progress` and `help_article_feedback` are anonymized after 90 days. Tour progress is personal preference data — can be deleted on request.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| No help articles match the current context | System falls back to "Getting Started" and general help articles. Help button shows a search interface instead of contextual suggestions. |
| User has already completed a guided tour | Tour does not auto-trigger. Tour is available in "Help > Restart Tour" menu. Tour progress is preserved — restarting resets to step 0. |
| Help article references a feature that has been deprecated | Article status is auto-set to "archived" when the referenced feature_id is removed. Archived articles are excluded from contextual suggestions but available via search. |
| Context tag matching is ambiguous (user on /tickets page which matches both "tickets" and "queue" tags) | Multiple relevant articles shown, prioritized by sort_order and view_count (most popular first). Maximum 5 articles shown in overlay. |
| Help overlay conflicts with modal dialogs (e.g., ticket detail modal) | Help overlay auto-closes when a modal opens. Help button shows a badge count of available articles for the current context, accessible after modal closes. |

## Acceptance Criteria
1. **GIVEN** a user navigates to the Agent Configuration page, **WHEN** they click the help button, **THEN** the contextual help overlay displays articles and videos specifically tagged with `context_tags` matching "page:agents" and "feature:configuration," sorted by relevance.
2. **GIVEN** a new user logs in for the first time, **WHEN** they land on the dashboard, **THEN** a guided tour auto-triggers (after a 2-second delay) highlighting the main dashboard widgets with step-by-step tooltips and a "Next" button.
3. **GIVEN** a user searches for "how to set up SMS" in the help search, **WHEN** they submit the query, **THEN** results are returned with articles matching the query, ranked by relevance (full-text search on title + content), with the most relevant article highlighted.
4. **GIVEN** a user clicks "No, this wasn't helpful" on an article, **WHEN** they optionally add a comment, **THEN** the feedback is recorded in `help_article_feedback`, the `not_helpful_count` increments, and the article is flagged for review by the help content team.

---

# F-108: Peer Review (Junior asks Senior)

## Overview
Internal collaboration system allowing junior agents to request peer review from senior agents before sending a customer response on complex or high-stakes tickets. Junior agents can attach a draft response, select a senior reviewer, and include notes explaining their uncertainty. Senior agents can approve, edit, or reject the draft with feedback, creating a mentorship loop that improves junior agent quality over time.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/peer-review/requests` | POST | `ticket_id`, `reviewer_id`, `draft_response`, `notes`, `urgency` (normal/high) | `{ review_id, status: "pending" }` |
| `/api/peer-review/requests` | GET | `status`, `role` (requester/reviewer), `ticket_id` | `{ requests: [{ id, ticket_id, requester, reviewer, status, urgency, created_at }] }` |
| `/api/peer-review/requests/{id}` | GET | `id` | `{ id, ticket, draft_response, notes, feedback, status, history[] }` |
| `/api/peer-review/requests/{id}/approve` | POST | `id`, `final_response` (optional edits), `feedback` | `{ status: "approved", response_sent: bool }` |
| `/api/peer-review/requests/{id}/reject` | POST | `id`, `feedback`, `suggested_response` | `{ status: "rejected", ticket_reassigned: bool }` |
| `/api/peer-review/requests/{id}/cancel` | POST | `id` | `{ status: "cancelled" }` |
| `/api/peer-review/suggest-reviewers` | GET | `ticket_id` | `{ reviewers: [{ id, name, expertise[], availability, avg_review_time_min }] }` |

## DB Tables
- **`peer_review_requests`** — `id` UUID, `company_id` UUID NOT NULL, `ticket_id` UUID NOT NULL, `requester_id` UUID NOT NULL, `reviewer_id` UUID NOT NULL, `draft_response` TEXT NOT NULL, `notes` TEXT, `urgency` VARCHAR(10) DEFAULT 'normal', `status` VARCHAR(20) NOT NULL DEFAULT 'pending' (pending/approved/rejected/cancelled/expired), `final_response` TEXT, `reviewer_feedback` TEXT, `suggested_response` TEXT, `response_sent` BOOL DEFAULT false, `requested_at` TIMESTAMPTZ DEFAULT NOW(), `reviewed_at` TIMESTAMPTZ, `expires_at` TIMESTAMPTZ (default: requested_at + 2h), `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_peer_review_company ON peer_review_requests(company_id, status)`, `idx_peer_review_reviewer ON peer_review_requests(reviewer_id, status)`, `idx_peer_review_requester ON peer_review_requests(requester_id, status)`, `idx_peer_review_ticket ON peer_review_requests(ticket_id)`
- **`peer_review_history`** — `id` UUID, `request_id` UUID NOT NULL, `company_id` UUID NOT NULL, `actor_id` UUID NOT NULL, `action` VARCHAR(20) (requested/approved/rejected/cancelled/commented), `comment` TEXT, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_peer_history_request ON peer_review_history(request_id, created_at)`
- **`agent_mentorship_stats`** — `id` UUID, `company_id` UUID NOT NULL, `agent_id` UUID NOT NULL, `reviews_requested` INT DEFAULT 0, `reviews_received` INT DEFAULT 0, `avg_review_time_min` FLOAT, `approval_rate` FLOAT, `period_start` DATE, `period_end` DATE, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `UNIQUE(company_id, agent_id, period_start, period_end)`

## BC Rules
- **BC-005** (Real-Time): Review requests pushed via Socket.io to the reviewer's personal room (`user_{user_id}`) and `tenant_{company_id}` room. Reviewer sees a real-time notification badge. Status changes (approved/rejected) pushed to requester.
- **BC-009** (Approval Workflow): Peer review does NOT replace the formal approval workflow for financial actions. If a ticket involves a refund > $100, both peer review AND formal approval may be required. Peer review status is tracked separately from approval status.
- **BC-001** (Multi-Tenant Isolation): Review requests, history, and mentorship stats scoped by `company_id`. Reviewers must be in the same company as the requester. No cross-tenant reviews.
- **BC-012** (Error Handling): Review request to an unavailable (offline) reviewer is accepted but flagged with "reviewer_offline" — suggestion to choose an available reviewer. Expired reviews (2h timeout) auto-cancel and notify both parties.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Reviewer is offline when request is created | Request is created with status="pending." Reviewer receives notification on next login. If reviewer remains offline for > 2 hours (expires_at), request auto-expires and requester is notified to choose a different reviewer. |
| Reviewer rejects the draft and suggests a response | Ticket remains with the original requester. Suggested response is pre-populated in the ticket reply box. Requester can edit and send, or request another review. |
| Junior agent sends the response before the review is completed | If response_sent=true, review is auto-cancelled with status="cancelled" and note "Response already sent." Reviewer notified that review is no longer needed. |
| Multiple junior agents request review from the same senior simultaneously | Senior sees all pending requests in a prioritized queue (by urgency then timestamp). No limit on concurrent reviews, but senior's workload indicator shows pending count. |
| Reviewer is also a junior agent (role mismatch) | Request validation rejects at creation: "Reviewer must have senior or supervisor role." Suggested reviewers endpoint only returns eligible senior+ agents. |
| Ticket is resolved by another agent while review is pending | Review auto-cancelled. Requester notified: "Ticket was resolved by [agent_name] while your review was pending." |

## Acceptance Criteria
1. **GIVEN** a junior agent is composing a response to a complex technical ticket, **WHEN** they click "Request Peer Review" and select a senior agent with their draft response and notes, **THEN** a review request is created with status="pending" and the senior agent receives a real-time Socket.io notification.
2. **GIVEN** a senior agent receives a peer review request, **WHEN** they open the request and approve it with a minor edit to the response and feedback "Good response, just fix the typo in the product name," **THEN** the edited response is sent to the customer, the requester is notified of the approval, and the feedback is stored in review history.
3. **GIVEN** a peer review request has been pending for 2 hours (expires_at reached), **WHEN** the expiration check runs (Celery beat every 1 minute), **THEN** the request status is set to "expired," both the requester and reviewer are notified, and the requester can choose to re-request or respond directly.
4. **GIVEN** a junior agent has requested 10 peer reviews in the current month, **WHEN** the admin views the mentorship stats, **THEN** the stats show the agent's review request count, approval rate, and average review turnaround time compared to team averages.

---

# F-129: Proactive Outbound Voice (Abandoned Carts)

## Overview
Automated outbound voice call system for abandoned cart recovery, payment reminders, subscription renewal outreach, and proactive customer engagement. Integrates with Twilio to initiate calls, uses AI voice agents for natural conversation, and connects to human agents when the customer requests or the AI detects complexity. Includes TCPA compliance controls, call scheduling, DNC list management, and conversion tracking.

## APIs
| Endpoint | Method | Key Params | Response |
|----------|--------|------------|----------|
| `/api/proactive/campaigns` | POST | `name`, `type` (abandoned_cart/payment_reminder/renewal/custom), `criteria` (JSONB), `script_template`, `schedule`, `max_calls_per_day` | `{ campaign_id, status: "draft" }` |
| `/api/proactive/campaigns/{id}/activate` | POST | `id` | `{ campaign_id, status: "active", scheduled_calls_count }` |
| `/api/proactive/campaigns/{id}/pause` | POST | `id` | `{ campaign_id, status: "paused" }` |
| `/api/proactive/campaigns` | GET | `status`, `type`, `from_date`, `to_date` | `{ campaigns: [{ id, name, type, status, stats }] }` |
| `/api/proactive/campaigns/{id}` | GET | `id` | `{ campaign details, call_results: [], conversion_stats }` |
| `/api/proactive/calls` | GET | `campaign_id`, `status`, `outcome` | `{ calls: [{ id, recipient, status, outcome, duration, recording_url }] }` |
| `/api/proactive/dnc` | POST | `phone_numbers[]`, `reason` | `{ added: N }` |
| `/api/proactive/dnc/{number}` | DELETE | `number` | `{ status: "removed" }` |
| `/api/proactive/dnc` | GET | `search`, `limit`, `offset` | `{ entries: [{ number, reason, added_at, added_by }] }` |

## DB Tables
- **`proactive_campaigns`** — `id` UUID, `company_id` UUID NOT NULL, `name` VARCHAR(200) NOT NULL, `type` VARCHAR(30) NOT NULL (abandoned_cart/payment_reminder/renewal/reengagement/custom), `criteria` JSONB NOT NULL (e.g., { "cart_value_min": 50, "abandoned_hours_ago_min": 2, "abandoned_hours_ago_max": 48 }), `script_template` TEXT NOT NULL, `ai_voice_id` VARCHAR(50), `schedule` JSONB (days_of_week, time_window_start, time_window_end, timezone), `max_calls_per_day` INT DEFAULT 100, `max_attempts_per_recipient` INT DEFAULT 2, `status` VARCHAR(20) DEFAULT 'draft' (draft/active/paused/completed/cancelled), `tcpa_consent_required` BOOL DEFAULT true, `total_calls` INT DEFAULT 0, `answered_calls` INT DEFAULT 0, `conversions` INT DEFAULT 0, `created_by` UUID, `activated_at` TIMESTAMPTZ, `completed_at` TIMESTAMPTZ, `created_at` TIMESTAMPTZ DEFAULT NOW(), `updated_at` TIMESTAMPTZ
  - **Indexes:** `idx_proactive_campaigns_company ON proactive_campaigns(company_id, status)`, `idx_proactive_campaigns_type ON proactive_campaigns(company_id, type)`
- **`proactive_call_results`** — `id` UUID, `company_id` UUID NOT NULL, `campaign_id` UUID NOT NULL, `recipient_name` VARCHAR(100), `recipient_number` VARCHAR(20) NOT NULL, `call_sid` VARCHAR(64) UNIQUE, `ticket_id` UUID, `status` VARCHAR(20) (queued/ringing/in-progress/completed/no-answer/busy/failed), `outcome` VARCHAR(30) (answered_machine/answered_human/converted/opted_out/dnc/not_interested/callback_requested/failed), `duration` INT, `recording_url` TEXT, `transcript` TEXT, `ai_summary` TEXT, `attempt_number` INT DEFAULT 1, `scheduled_at` TIMESTAMPTZ, `called_at` TIMESTAMPTZ, `created_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `idx_proactive_results_campaign ON proactive_call_results(campaign_id, created_at DESC)`, `idx_proactive_results_number ON proactive_call_results(recipient_number, campaign_id)`, `UNIQUE(campaign_id, recipient_number, attempt_number)`
- **`dnc_list`** — `id` UUID, `company_id` UUID NOT NULL, `phone_number` VARCHAR(20) NOT NULL, `reason` VARCHAR(50) (customer_request/tcpa_compliance/unsubscribed/failed_contact), `added_by` UUID, `added_at` TIMESTAMPTZ DEFAULT NOW()
  - **Indexes:** `UNIQUE(company_id, phone_number)`

## BC Rules
- **BC-003** (Webhook Handling): Twilio voice status callbacks processed asynchronously via Celery with `company_id` as first param. Call status updates are idempotent via `call_sid`. Response within 3 seconds.
- **BC-004** (Background Jobs): Campaign execution runs as a scheduled Celery beat task. Each campaign batch processes calls at a configurable rate (max 10 concurrent calls per campaign). Failed calls retry per `max_attempts_per_recipient`. Campaign completion tracked as background task.
- **BC-006** (Email/SMS): Pre-call SMS notification sent 5 minutes before outbound call (configurable). Post-call summary email sent to customer (opt-in). Rate limited per BC-006 rules.
- **BC-010** (Data Lifecycle & GDPR): DNC list entries are permanent unless explicitly removed. Customer data in call results is PII — retention policy default 1 year. Right-to-erasure removes all call results and recordings for the requester. TCPA consent records retained for 5 years.
- **BC-011** (Auth & Security): Campaign creation requires admin+ role. DNC list management requires supervisor+ role. All outbound calls are logged in `audit_trail` with campaign_id, recipient, and outcome.
- **BC-012** (Error Handling): Twilio API failures trigger campaign pause and admin alert. Circuit breaker after 10 consecutive call failures within a campaign. DNC check happens before every call initiation — no exceptions.

## Edge Cases
| Edge Case | Handling |
|-----------|----------|
| Recipient's number is on the DNC list | Call is skipped before initiation. Logged as "skipped_dnc." Not counted toward campaign totals. No notification sent to recipient. |
| Recipient answers but is a voicemail machine | AI voice agent detects voicemail (Twilio AMD — Answering Machine Detection). Short message left: "This is a courtesy call from [Company]. For assistance, call [number] or reply HELP to [SMS number]." |
| Customer requests to be removed from all calls during the call | AI voice agent immediately ends call. Number added to DNC list with reason="customer_request." Confirmation SMS sent: "You've been added to our Do Not Call list." |
| Campaign calls a number that has been ported to another carrier | Twilio handles carrier routing transparently. If number is invalid, call fails with status="failed" and error code. Number flagged for removal from future campaigns. |
| Campaign reaches max_calls_per_day limit mid-batch | Remaining calls in the batch are queued for the next day's execution window. Campaign status remains "active." Admin notified of daily limit reached. |
| Recipient converts (e.g., completes purchase) during the AI call | Conversion tracked via webhook from the e-commerce platform or AI-detected intent confirmation. Call result outcome="converted." Ticket created with high priority. Follow-up confirmation email sent. |

## Acceptance Criteria
1. **GIVEN** an admin creates an abandoned cart campaign targeting carts abandoned 2-48 hours ago with value > $50, **WHEN** the campaign is activated, **THEN** the system generates a call list from matching criteria, schedules calls within the configured time window, and initiates the first batch within 5 minutes.
2. **GIVEN** the outbound call is answered by a human, **WHEN** the AI voice agent engages, **THEN** the agent follows the script template, mentions the specific abandoned items and cart total, and offers to complete the purchase or transfer to a human agent.
3. **GIVEN** a recipient is on the company's DNC list, **WHEN** the campaign execution engine evaluates the call list, **THEN** the recipient's number is skipped, logged as "skipped_dnc," and no call is initiated to that number.
4. **GIVEN** a campaign has completed 1,000 calls with 150 conversions, **WHEN** the admin views the campaign report, **THEN** the dashboard shows total calls, answered rate, conversion rate (15%), average call duration, and cost per conversion based on Twilio call charges.

---

> **End of Batch 10 — 14 features specified**
>
> **Summary:** 8 MEDIUM-priority features (F-090, F-096, F-126, F-127, F-128, F-130, F-133, F-086) and 6 LOW-priority features (F-002, F-009, F-043, F-045, F-108, F-129).
>
> **Building Codes Coverage:** BC-001 (Multi-Tenant Isolation) — all 14 features · BC-003 (Webhooks) — 5 features · BC-004 (Background Jobs) — 8 features · BC-005 (Real-Time) — 10 features · BC-006 (Email/SMS) — 5 features · BC-007 (AI Model) — 3 features · BC-008 (State Management) — 2 features · BC-009 (Approval Workflow) — 2 features · BC-010 (GDPR/Data Lifecycle) — 7 features · BC-011 (Auth & Security) — 6 features · BC-012 (Error Handling) — all 14 features.
