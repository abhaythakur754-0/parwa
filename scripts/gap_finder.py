#!/usr/bin/env python3
"""
PARWA Gap Finder - Reusable tool for finding testing gaps
Usage: python scripts/gap_finder.py "<feature description>" [--output json|text]
"""

import sys
import json
import argparse
import asyncio
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

SYSTEM_PROMPT = """You are a senior software testing engineer. Your job is to find loopholes, bugs, and missing test cases in any software project.

You think in 4 layers:
1. UNIT GAPS — individual functions with edge cases
2. INTEGRATION GAPS — two systems talking to each other, what breaks at the seams
3. FLOW GAPS — full user journeys nobody tested end to end
4. BREAK TESTS — adversarial scenarios where users do unexpected things

You know these failure patterns:
- Race conditions (two things at same time)
- Idempotency failures (same request sent twice)
- Tenant isolation leaks (one customer sees another's data)
- Webhook double-fires (payment systems sending same event twice)
- State loss (in-memory data gone on restart)
- Missing rollback (partial success leaving broken state)
- Silent failures (errors swallowed, never surfaced)
- Cascade failures (one system down takes others down)

PARWA CONTEXT:
- Multi-tenant SaaS platform for AI-powered customer support
- Three pricing tiers: Starter ($999/2K tickets), Growth ($2,499/5K tickets), High ($3,999/15K tickets)
- Payment model: Netflix-style - payment fails = STOP immediately, no refunds, no trials, no grace period
- Uses Paddle for billing, PostgreSQL for database, Redis for caching, Celery for background jobs
- Tenant isolation via company_id on all tables

IMPORTANT: You MUST respond in this EXACT format:

GAPS FOUND: [number]

GAP 1
Severity: CRITICAL
Title: [short title]
What breaks: [one sentence]
Real scenario: [concrete example with actual data]
AI agent prompt: [exact prompt to paste into coding AI to write this test]

GAP 2
Severity: HIGH
Title: [short title]
What breaks: [one sentence]
Real scenario: [concrete example]
AI agent prompt: [exact prompt]

[continue for all gaps]

Keep it tight and actionable. Every gap needs an AI agent prompt they can copy paste directly.
Find 3-7 gaps for any feature described."""


async def find_gaps(feature_description: str) -> str:
    """Use z-ai-web-dev-sdk to find gaps in the feature."""
    try:
        # Create a temporary Node.js script to call the SDK
        node_script = f'''
const ZAI = require('z-ai-web-dev-sdk').default || require('z-ai-web-dev-sdk');

async function main() {{
    const zai = await ZAI.create();
    
    const completion = await zai.chat.completions.create({{
        messages: [
            {{ role: 'system', content: {json.dumps(SYSTEM_PROMPT)} }},
            {{ role: 'user', content: {json.dumps(feature_description)} }}
        ],
        max_tokens: 4000
    }});
    
    console.log(completion.choices[0]?.message?.content || 'No response');
}}

main().catch(e => {{ console.error('Error:', e.message); process.exit(1); }});
'''
        
        # Write to temp file and execute
        with NamedTemporaryFile(mode='w', suffix='.cjs', delete=False, dir='/home/z/my-project/parwa') as f:
            f.write(node_script)
            temp_path = f.name
        
        node_env = {**__import__('os').environ, 'NODE_PATH': '/home/z/.bun/install/global/node_modules'}
        result = subprocess.run(
            ['node', temp_path],
            capture_output=True,
            text=True,
            cwd='/home/z/my-project/parwa',
            env=node_env,
            timeout=120
        )
        
        # Clean up temp file
        Path(temp_path).unlink(missing_ok=True)
        
        if result.returncode != 0:
            return f"Error calling AI: {result.stderr}"
        
        return result.stdout.strip()
        
    except subprocess.TimeoutExpired:
        return "Error: AI request timed out"
    except Exception as e:
        return f"Error: {str(e)}"


def parse_gaps(text: str) -> dict:
    """Parse the AI response into structured gaps."""
    lines = text.split("\n")
    gaps = []
    current = None
    found_count = None
    
    for line in lines:
        line = line.strip()
        if line.startswith("GAPS FOUND:"):
            found_count = line.replace("GAPS FOUND:", "").strip()
            continue
        if line.startswith("GAP ") and len(line) > 4:
            # Extract number from "GAP 1" or "GAP 2" etc
            parts = line[4:].strip().split()
            if parts and parts[0].isdigit():
                if current:
                    gaps.append(current)
                current = {"severity": "MEDIUM", "title": "", "breaks": "", "scenario": "", "prompt": ""}
                continue
        if not current:
            continue
        if line.startswith("Severity:"):
            current["severity"] = line.replace("Severity:", "").strip().upper()
        elif line.startswith("Title:"):
            current["title"] = line.replace("Title:", "").strip()
        elif line.startswith("What breaks:"):
            current["breaks"] = line.replace("What breaks:", "").strip()
        elif line.startswith("Real scenario:"):
            current["scenario"] = line.replace("Real scenario:", "").strip()
        elif line.startswith("AI agent prompt:"):
            current["prompt"] = line.replace("AI agent prompt:", "").strip()
    
    if current:
        gaps.append(current)
    
    return {"found_count": found_count or len(gaps), "gaps": gaps, "raw_response": text}


def print_gaps(result: dict):
    """Pretty print the gaps to console."""
    print(f"\n{'='*60}")
    print(f"⚡ {result['found_count']} GAPS FOUND")
    print('='*60)
    
    if not result['gaps']:
        print("\nNo gaps found. Either:")
        print("  1. Your tests are comprehensive (great!)")
        print("  2. The feature description needs more detail")
        print("\nRaw AI response saved to JSON file.")
        return
    
    for i, gap in enumerate(result['gaps'], 1):
        sev_colors = {
            "CRITICAL": "\033[91m",  # Red
            "HIGH": "\033[93m",      # Yellow
            "MEDIUM": "\033[92m",    # Green
            "LOW": "\033[94m",       # Blue
        }
        color = sev_colors.get(gap['severity'], "\033[0m")
        reset = "\033[0m"
        
        print(f"\n┌─ GAP {i} ─────────────────────────────────────")
        print(f"│ {color}[{gap['severity']}]{reset} {gap['title']}")
        if gap['breaks']:
            print(f"│ Breaks: {gap['breaks']}")
        if gap['scenario']:
            print(f"│ Scenario: {gap['scenario']}")
        if gap['prompt']:
            print(f"│")
            print(f"│ AI PROMPT:")
            prompt_display = gap['prompt'][:150] + "..." if len(gap['prompt']) > 150 else gap['prompt']
            print(f"│ {prompt_display}")
        print(f"└──────────────────────────────────────────────")


# Pre-defined prompts for Week 5 Payment features and Week 8 AI Engine
W_PROMPTS = {
    "w5d1": """Week 5 Day 1: Paddle Client + Database Tables

I'm building the Paddle billing client and database tables for PARWA:
- PaddleClient class with methods: create_subscription, cancel_subscription, update_subscription, get_subscription
- Database tables: subscriptions, billing_events, invoices, payment_methods, overage_records
- Tenant isolation via company_id on all billing tables
- Paddle webhook signature verification using HMAC-SHA256

What testing gaps exist? Focus on: idempotency, tenant isolation, webhook security, race conditions.""",

    "w5d2": """Week 5 Day 2: Subscription Lifecycle + Webhook Handler

I'm building subscription lifecycle management and Paddle webhook handler:
- Subscription states: active, past_due, canceled, expired
- Webhook events: subscription_created, subscription_updated, subscription_canceled, payment_failed
- PaddleHandler.process_event() routing to correct handlers
- Automatic subscription state transitions on webhook events
- Tenant context propagation in webhook processing

What testing gaps exist? Focus on: state machine edge cases, webhook replay attacks, double-processing, partial failures.""",

    "w5d3": """Week 5 Day 3: Overage Detection + Auto-Charge

I'm building ticket overage detection and automatic charging:
- Daily Celery task checking ticket counts vs plan limits
- Overage rate: $0.10 per ticket over limit
- Automatic Paddle charge for overages
- Overage notification emails to customers
- Overage tracking in database

What testing gaps exist? Focus on: race conditions in counting, charge failures, partial overage handling, notification failures.""",

    "w5d4": """Week 5 Day 4: Payment Failure Handling

I'm building payment failure handling with Netflix-style immediate stop:
- Payment fails = subscription stops immediately (no grace period)
- No refunds, no trials, no second chances
- Automatic service suspension on payment failure
- Email notifications for payment failures
- Manual reactivation flow after payment update

What testing gaps exist? Focus on: timing of suspension, partial service states, reactivation edge cases, tenant data access after suspension.""",

    "w5d5": """Week 5 Day 5: Billing API Endpoints + Frontend Integration

I'm building billing API endpoints and frontend integration:
- GET /api/billing/subscription - current subscription details
- POST /api/billing/upgrade - upgrade plan
- POST /api/billing/cancel - cancel subscription
- GET /api/billing/invoices - invoice history
- Frontend components: pricing page, billing dashboard, plan comparison

What testing gaps exist? Focus on: API authorization, tenant isolation, race conditions in upgrades, frontend state sync.""",

    "w5d6": """Week 5 Day 6: Full Payment Flow E2E Testing

I'm building end-to-end tests for the complete payment flow:
- Customer signup → plan selection → Paddle checkout → subscription activation
- Monthly renewal → overage detection → auto-charge
- Payment failure → immediate suspension → payment update → reactivation
- Plan upgrade mid-cycle → prorated billing
- Subscription cancellation → service termination

What testing gaps exist? Focus on: full user journeys, timing edge cases, state consistency across services, recovery from failures.""",

    "w8d1": """Week 8 Day 1: AI Routing Engine - Variant Engine + 3-Tier Routing + Provider Clients

Building AI routing with variant-specific config, 3-tier routing (LIGHT/MEDIUM/HEAVY), provider failover, and free provider clients (Google AI Studio, Cerebras, Groq).
What testing gaps exist? Focus on: routing logic, failover, concurrent routing, variant isolation.""",

    "w8d2": """Week 8 Day 2: AI Response Generation + Prompt Template System

Building AI response generation with prompt template rendering (Jinja2), A/B testing variants, template versioning, and response caching.
What testing gaps exist? Focus on: template rendering, caching, version conflicts, injection prevention.""",

    "w8d3": """Week 8 Day 3: Confidence Scoring + Guardrails Pipeline

Building multi-dimensional confidence scoring (relevance, completeness, accuracy, sentiment) and a 5-layer guardrails pipeline (PII detection, content policy, hallucination detection, prompt injection, confidence-based blocking).
What testing gaps exist? Focus on: scoring edge cases, guardrail bypass, false positives/negatives, pipeline failures.""",

    "w8d4": """Week 8 Day 4: Response Cache + Cost Tracker + Performance Optimizations

Building Redis-backed response cache with TTL, cost tracking per provider/model/variant, token counting, budget limits, and performance optimizations for the AI pipeline.
What testing gaps exist? Focus on: cache invalidation, cost calculation, concurrent access, memory management.""",

    "w8d5": """Week 8 Day 5: AI Monitoring Service (SG-19) + Self-Healing Engine (SG-20)

Building real-time AI monitoring and self-healing system:

SG-19 AI Monitoring Service:
- Tracks latency, confidence scores, guardrails hits, token usage, error rates per provider/model/variant
- Rolling-window analytics (1h, 6h, 24h, 7d) with time-based filtering
- Alert condition detection (error rate > 10/25%, confidence drop < 60%, P90 latency > 5000ms, provider unhealthy > 50%)
- Dashboard snapshot API aggregating all metrics
- Thread-safe in-memory storage with max 50 data points per company
- BC-001: company_id always first parameter on public methods
- BC-008: Never crash - every method wrapped in try/except
- Data classes: MetricPoint, LatencyStats, ConfidenceDistribution, GuardrailStats, ProviderComparison, AlertCondition, DashboardSnapshot

SG-20 Self-Healing Engine:
- Per-variant healing rules (mini_parwa, parwa, parwa_high)
- Auto-disable providers on consecutive errors (configurable threshold, default 5)
- Staged recovery: disabled -> recovering_10% -> recovering_25% -> recovering_50% -> active
- Confidence threshold auto-adjustment on consecutive low confidence scores (default 3 consecutive below 50%)
- Error rate spike detection with cooldown periods (300s default)
- Latency spike detection with cooldown periods (300s default)
- RLock for reentrant locking (recovery triggered inside locked context)
- deepcopy for rule isolation between variants
- HealingRule dataclass with provider, state, consecutive_errors, error_threshold, etc.

Existing test counts: 106 tests for monitoring, 91 tests for self-healing (197 total)

What testing gaps exist? Focus on: race conditions, state machine edge cases, cooldown bypass, tenant isolation, concurrent healing actions, recovery rollbacks, alert false positives, metric pruning edge cases.""",

    "w9d6": """Week 9 Day 6: Signal Extraction (SG-13) + Intent Classification (F-062) + Intent×Technique Mapping (F-149) + CLARA Quality Gate (F-150)

Building 4 systems:

1. Signal Extraction Layer (SG-13): Extract 10 signals from ticket text (intent, sentiment, complexity, monetary value, customer tier, turn count, previous response status, reasoning loop detection, resolution path count, query breadth). Configurable weights per variant. Signal cache with 60s TTL in Redis. Signal quality validation.

2. F-062 Intent Classification: Multi-label classifier outputting primary + secondary intents (refund/technical/billing/complaint/feature_request/general). Uses Smart Router Light tier. Confidence per intent.

3. F-149 Intent×Technique Mapping: Maps 6 intent types → recommended AI techniques. E.g., Refund→Self-Consistency, Complaint→UoT+Reflexion. Wire classifier output to technique router.

4. F-150 CLARA Quality Gate: 5-stage pipeline (Structure→Logic→Brand→Tone→Delivery). Each stage pass/fail+reason. Failed → regenerate or human review. Tier 1 always-active.

What testing gaps exist? Focus on: signal extraction accuracy, classification edge cases (ambiguous intents), technique mapping correctness, CLARA pipeline bypass/failure, variant weight differences, cache staleness, concurrent classification requests.""",

    "w9d7": """Week 9 Day 7: Sentiment Analysis (F-063) + RAG Retrieval (F-064) + Sentiment×Technique (F-151) + Knowledge Base Module (F-152) + Re-Indexing (F-153)

Building 5 systems:

1. F-063 Sentiment/Empathy Engine: 0-100 frustration score. Escalation at 60+, VIP routing at 80+. Tone adjustment: empathetic at 40+, urgent at 70+, de-escalation at 90+.

2. F-064 RAG Retrieval: pgvector search, top-k retrieval, similarity threshold. Tenant-isolated. Variant complexity: Mini=basic vector, Parwa=+metadata filtering, High=full pipeline.

3. F-151 Sentiment×Technique Mapping: Maps sentiment ranges→techniques. <0.3→UoT+Step-Back, 0.3-0.5→Step-Back only. Priority overrides.

4. F-152 shared/knowledge_base/ Module: Shared vector search module. Reusable pgvector operations across services. Tenant isolation in queries.

5. F-153 RAG Re-Indexing Triggers: Cache invalidation on KB document CRUD. Auto re-embedding via Celery queue.

What testing gaps exist? Focus on: sentiment score accuracy, RAG tenant isolation leaks, vector search edge cases, re-indexing race conditions, cache staleness, sentiment technique override conflicts, concurrent document updates.""",

    "w9d8": """Week 9 Day 8: RAG Reranking (F-064) + Auto-Response (F-065) + Brand Voice (F-154) + Response Templates (F-155) + Token Budget (F-156) + ReAct Tools (F-157) + AI Assignment (F-050) + Rule→AI Migration (F-158)

Building 8 systems:

1. F-064 RAG Reranking: Cross-encoder reranking, metadata filtering, context window assembly, citation tracking. Variant differentiation: Mini=skip reranking, Parwa=cross-encoder, High=retrieve-rewrite-rerank.

2. F-065 Auto-Response: Combine intent + RAG context + sentiment → brand-aligned response. Runs through CLARA quality gate. Smart Router Medium tier.

3. F-154 Brand Voice: Per-company config: tone (professional/friendly/casual), formality, prohibited words, response length, industry terminology.

4. F-155 Response Templates: CRUD for pre-written response bodies per tenant. Distinct from prompt templates.

5. F-156 Token Budget: Track per-conversation token usage. Alert at 70%, compress at 85%, hard stop at 95%.

6. F-157 ReAct Tools: 4 tool adapters (Order API, Billing API, CRM, Ticket System). Each has schema, execute(), validate_input(), format_output().

7. F-050 AI Assignment: Score-based: specialty(40)+workload(30)+accuracy(20)+jitter(10).

8. F-158 Rule→AI Migration: Migrate rule-based classification/assignment to AI with fallback.

What testing gaps exist? Focus on: RAG reranking accuracy, auto-response quality, brand voice enforcement, token budget overflow, ReAct tool failures, assignment scoring fairness, migration rollback, concurrent response generation.""",

    "w9d9": """Week 9 Day 9: Draft Composer (F-066) + Training Data Isolation (SG-12) + Edge Cases (SG-28) + Data Freshness (SG-34) + Technique Tier Access (SG-02)

Building 5 systems:

1. F-066 Draft Composer: Suggest drafts to human agents via Socket.io. Accept/edit/regenerate. Real-time streaming.

2. SG-12 Training Data Isolation: Per-variant datasets. Isolation at: storage (S3 prefixes), processing (variant tag in Celery), vector index (tenant+variant metadata), model configs.

3. SG-28 Edge-Case Handlers: 20 handlers for: empty query, too long, unsupported language, emojis only, code blocks, duplicate, embedded images, multi-question, non-existent ticket, malicious HTML, FAQ match, below confidence, maintenance mode, expired context, blocked user, pricing request, legal terminology, competitor mention, system commands, timeout.

4. SG-34 Data Freshness: Cache invalidation on KB updates. Signal staleness detection (>5min→re-extract). Context freshness check.

5. SG-02 Technique Tier Access: Check variant before technique selection. Mini=Tier1, Parwa=T1+T2, High=all.

What testing gaps exist? Focus on: draft generation quality, Socket.io race conditions, training data cross-contamination, edge case handler ordering, freshness staleness, technique tier bypass, concurrent draft sessions.""",

    "w10d12": """Week 10 Day 12: LangGraph Workflow Engine (F-060) + Variant-Aware Pipeline Routing (SG-18) + Context Compression (F-067) + Context Health Meter (F-068)

Building 4 systems:

1. F-060 LangGraph Workflow Engine: Graph-based orchestration for multi-step AI workflows as directed state machines with conditional branching and human checkpoints. LangGraphWorkflowEngine class that builds graph nodes, executes workflows, manages state transitions, supports per-variant graphs (Mini=linear chain, Parwa=conditional branching, High=full graph with human checkpoints+loops+technique nodes).

2. SG-18 Variant-Aware Pipeline Routing: Per-variant workflow graphs. Mini PARWA: linear chain only (intake -> classify -> respond). PARWA: conditional branching (intake -> classify -> [simple|complex] -> respond/approve). PARWA High: full graph with human checkpoints + loops + technique nodes. Store graph configs per variant.

3. F-067 Context Compression Trigger: Monitor token usage per conversation, compress prior context when approaching window limits. Trigger compression at 80% of context window. ContextCompressor class with strategies: summarization-based, truncation-based, extractive.

4. F-068 Context Health Meter: Real-time context quality indicator (healthy/warning/critical). Pushes via Socket.io. ContextHealthMeter class that tracks signal staleness, response relevance, context age, compression ratio.

CURRENT STATE: Source code AND test files exist for all 4 modules. Need to find gaps in existing tests.

What testing gaps exist? Focus on: workflow graph construction edge cases, conditional branching correctness, human checkpoint timeout, context compression quality at different ratios, health meter false positives/negatives, variant-specific graph validation, workflow state persistence, concurrent workflow execution, compression-triggered state transitions.""",

    "w10d11": """Week 10 Day 11: State Serialization (SG-15) + GSD State Engine (F-053) + Data Freshness (SG-34)

Building 3 systems:

1. SG-15 State Serialization/Deserialization Layer: Redis primary + PostgreSQL fallback persistence. Serialize LangGraph state for crash recovery, cross-worker handoff, debug replay, audit trail. State schema: current_node, variables, history, technique_stack, model_used, token_count, timestamps. Distributed locks for concurrent access. Named checkpoints with 7d TTL. State diff tracking. PipelineStateSnapshot table. BC-001 company_id scoping. BC-004 retry with backoff. BC-008 never crash. StateSerializer class with save_state, load_state, save_checkpoint, load_checkpoint, list_checkpoints, delete_state, get_state_history, compute_diff, restore_from_checkpoint, get_stats methods. Dataclasses: SaveResult, StateDiff, CheckpointMeta, StateHistoryEntry, StateSerializerConfig.

2. F-053 GSD State Engine: Guided Support Dialogue - structured state machine for multi-step conversations. States: NEW -> GREETING -> DIAGNOSIS -> RESOLUTION -> FOLLOW_UP -> CLOSED. ESCALATE branch to HUMAN_HANDOFF. Per-variant config: mini_parwa (linear, no escalation), parwa (full with escalation), parwa_high (full + human handoff loop). Transition validation with transition tables. Auto-escalation on frustration>80, VIP tier, legal intent, diagnosis loop>3. Escalation cooldown (5 min default). Diagnostic questions per intent. Resolution time estimation. Conversation summary. Satisfaction detection. GSDEngine class with transition, get_next_state, is_terminal, can_transition, get_available_transitions, handle_escalation, reset_conversation, get_conversation_summary, estimate_resolution_time, should_auto_close methods. GSDConfig, TransitionRecord, TransitionEvent dataclasses.

3. SG-34 AI Engine Data Freshness: Cache invalidation on KB updates. RAG re-indexing on document change. Signal staleness detection (>5min old -> re-extract). Context window freshness check. Model capability version check. DataFreshnessChecker class.

CURRENT STATE: Source code exists for all 3 modules. But there are ZERO test files for state_serialization.py and gsd_engine.py. DataFreshness test file exists (test_data_freshness.py).

What testing gaps exist? Focus on: state serialization round-trip fidelity, Redis/PostgreSQL failover, distributed lock contention, checkpoint name sanitization, state diff accuracy, GSD transition validation edge cases, variant-specific transition restrictions, escalation cooldown timing, auto-escalation trigger conditions, diagnosis loop detection, concurrent state modification, recovery from corrupted state data, tenant isolation in state keys, history ring buffer overflow, transition reason accuracy.""",

    "w6d1_jarvis": """Week 6 Day 1: Jarvis Onboarding Database + Models

I'm building the Jarvis Onboarding Chat system for PARWA SaaS. Phase 1 (Database + Models) is done:

MODELS (database/models/jarvis.py):
- JarvisSession: id, user_id (FK users), company_id (FK companies), type (onboarding/customer_care), context_json (TEXT), message_count_today, last_message_date, total_message_count, pack_type (free/demo), pack_expiry, demo_call_used, is_active, payment_status (none/pending/completed/failed), handoff_completed, created_at, updated_at
- JarvisMessage: id, session_id (FK jarvis_sessions CASCADE), role (user/jarvis/system), content, message_type (text/bill_summary/payment_card/otp_card/handoff_card/demo_call_card/error/limit_reached/pack_expired), metadata_json, created_at
- JarvisKnowledgeUsed: id, message_id (FK jarvis_messages CASCADE), knowledge_file, relevance_score, created_at
- JarvisActionTicket: id, session_id (FK jarvis_sessions CASCADE), message_id (FK jarvis_messages SET NULL), ticket_type (otp_verification/otp_verified/payment_demo_pack/payment_variant/payment_variant_completed/demo_call/demo_call_completed/roi_import/handoff), status (pending/in_progress/completed/failed), result_json, metadata_json, created_at, updated_at, completed_at

MIGRATION (012_jarvis_system.py):
- All 4 tables with foreign keys, CASCADE deletes, named indexes
- ix_jarvis_sess_user_active on (user_id, is_active)
- ix_jarvis_msg_session_ts on (session_id, created_at)
- ix_jarvis_ku_message on (message_id)
- ix_jarvis_ticket_session on (session_id)
- ix_jarvis_ticket_sess_status on (session_id, status)

CURRENT STATE:
- No CHECK constraints on enum-like columns (type, pack_type, payment_status, role, message_type, ticket_type, status)
- JSON fields stored as TEXT not JSONB
- Models exported from database/models/__init__.py
- ZERO test files for jarvis models
- Old onboarding tests exist (test_w6d1_onboarding.py) but test user_details/onboarding_session NOT jarvis

What testing gaps exist? Focus on: CHECK constraint validation, JSON serialization, cascade delete, default values, index usage, enum value enforcement, context_json schema, tenant isolation, race conditions in session creation, daily counter reset logic.""",

    "w6d2_jarvis": """Week 6 Day 2: Jarvis Schemas + Service Layer + API Endpoints + Frontend Hook

I'm building the Jarvis Onboarding Chat system for PARWA SaaS. Day 2 (Phases 2-4) is done:

SCHEMAS (backend/app/schemas/jarvis.py) — 17 Pydantic schemas:
- JarvisSessionCreate, JarvisSessionResponse, JarvisContextUpdate, JarvisEntryContextRequest
- JarvisMessageSend, JarvisMessageResponse, JarvisHistoryResponse
- JarvisOtpRequest, JarvisOtpVerify, JarvisOtpResponse
- JarvisDemoPackPurchase, JarvisDemoPackStatusResponse
- JarvisPaymentCreate, JarvisPaymentStatusResponse, JarvisPaymentWebhookPayload
- JarvisDemoCallRequest, JarvisDemoCallVerifyOtp, JarvisDemoCallSummaryResponse
- JarvisHandoffRequest, JarvisHandoffStatusResponse
- JarvisActionTicketCreate, JarvisActionTicketUpdateStatus, JarvisActionTicketResponse, JarvisActionTicketListResponse
- JarvisErrorResponse
- Validators: email, phone, industry, stage, entry_source, ticket_type, ticket_status, variants

SERVICE (backend/app/services/jarvis_service.py) — 25 functions:
- Session: create_or_resume_session, get_session, get_session_context, update_context, set_entry_context
- Messages: send_message, get_history, check_message_limit, _maybe_reset_daily_counter
- OTP: send_business_otp, verify_business_otp
- Demo Pack: purchase_demo_pack, get_demo_pack_status
- Payment: create_payment_session, handle_payment_webhook, get_payment_status
- Demo Call: initiate_demo_call, get_call_summary
- Handoff: execute_handoff, get_handoff_status
- Tickets: create_action_ticket, get_tickets, get_ticket, update_ticket_status, complete_ticket
- AI: build_system_prompt, detect_stage, _call_ai_provider (placeholder)
- Entry: get_entry_context, build_context_aware_welcome
- Error: handle_error
- Constants: FREE_DAILY_LIMIT=20, DEMO_DAILY_LIMIT=500, OTP_LENGTH=6, MAX_OTP_ATTEMPTS=3

API ROUTER (backend/app/api/jarvis.py) — 22 endpoints on /api/jarvis/*:
- POST/GET /session, GET /history, POST /message
- PATCH /context, POST /context/entry
- POST /demo-pack/purchase, GET /demo-pack/status
- POST /verify/send-otp, POST /verify/verify-otp
- POST /payment/create, POST /payment/webhook (no auth), GET /payment/status
- POST /demo-call/initiate, POST /demo-call/otp, GET /demo-call/summary
- POST /handoff, GET /handoff/status
- POST /tickets, GET /tickets, GET /tickets/{id}, PATCH /tickets/{id}/status

FRONTEND HOOK (frontend/src/hooks/useJarvisChat.ts) — ~580 lines:
- State: messages, session, isLoading, isTyping, remainingToday, isLimitReached, isDemoPackActive
- Flow states: otpState, paymentState, handoffState, demoCallState, error
- Actions: initSession, sendMessage, retryLastMessage, updateContext, sendOtp, verifyOtp, purchaseDemoPack, createPayment, initiateDemoCall, executeHandoff, clearError
- API helper with auth token injection, error parsing

CURRENT STATE:
- All Python compiles. TypeScript has zero new errors.
- NO tests for schemas, service, or API endpoints
- _call_ai_provider is a placeholder returning context-aware responses
- Paddle webhook has no signature verification (comment says "in production")
- OTP stored in session context_json (not in separate table/Redis)
- No rate limiting on POST /message (roadmap requires it)

What testing gaps exist? Focus on: service layer business logic, API endpoint auth/error handling, webhook idempotency, OTP replay attacks, session hijacking, race conditions in daily counter reset, concurrent session creation, demo pack expiry edge cases, handoff data leakage, frontend hook error recovery, optimistic update rollback, message ordering.""",

    "w9d10": """Week 9 Day 10: Cross-Variant Routing (SG-06/SG-11) + Anti-Arbitrage (F-159) + Conversation Summarization (F-160) + Integration Testing

Building 4 systems:

1. SG-06 Cross-Variant Routing Rules: Channel→variant mapping, escalation path (lower→higher), shared context, billing per variant.

2. SG-11 Cross-Variant Ticket Routing: Algorithm: channel match→highest variant→auto-escalate if exceeds capability→bill to originating variant unless escalated.

3. F-159 Anti-Arbitrage: Detect tier gaming (10 Mini instances to get 1 PARWA High capacity). Cap total capacity per tenant. Alert ops on suspicious patterns.

4. F-160 Conversation Summarization: Multi-turn summarization. Modes: extractive, abstractive, hybrid. Context management for long conversations.

What testing gaps exist? Focus on: cross-variant escalation correctness, billing accuracy during escalation, anti-arbitrage bypass, summarization accuracy, concurrent routing conflicts, capacity gaming detection, escalation rollback.""",
}


def main():
    parser = argparse.ArgumentParser(description="PARWA Gap Finder - Find testing gaps in features")
    parser.add_argument("feature", nargs="?", help="Feature description or day code (w5d1-w5d6, w8d1-w8d5, w9d6-w9d10)")
    parser.add_argument("--output", "-o", choices=["json", "text"], default="text", help="Output format")
    parser.add_argument("--list", "-l", action="store_true", help="List available W5 prompts")
    parser.add_argument("--raw", "-r", action="store_true", help="Show raw AI response")
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable prompts:")
        for code, desc in W_PROMPTS.items():
            print(f"  {code}: {desc.split(chr(10))[0].strip()}")
        print("\nUsage: python scripts/gap_finder.py w5d1")
        return
    
    if not args.feature:
        print("Usage: python scripts/gap_finder.py \"<feature description>\"")
        print("       python scripts/gap_finder.py w5d1  # for pre-defined Week 5 prompts")
        print("       python scripts/gap_finder.py w9d6  # for Week 9 AI Core")
        print("       python scripts/gap_finder.py --list  # show all prompts")
        sys.exit(1)
    
    # Check if it's a pre-defined prompt code
    feature = W_PROMPTS.get(args.feature.lower(), args.feature)
    
    print(f"\n🔍 Analyzing: {args.feature if args.feature in W_PROMPTS else feature[:60]}...")
    print("⏳ Calling AI (this may take 10-30 seconds)...\n")
    
    # Run the gap finder
    result_text = asyncio.run(find_gaps(feature))
    
    if args.raw:
        print("\n" + "="*60)
        print("RAW AI RESPONSE:")
        print("="*60)
        print(result_text)
        print("="*60 + "\n")
    
    parsed = parse_gaps(result_text)
    
    if args.output == "json":
        print(json.dumps(parsed, indent=2))
    else:
        print_gaps(parsed)
    
    # Save to file
    output_file = Path("/home/z/my-project/parwa") / f"gap_analysis_{args.feature.replace(' ', '_')}.json"
    with open(output_file, "w") as f:
        json.dump(parsed, f, indent=2)
    print(f"\n📁 Full results saved to: {output_file}")


if __name__ == "__main__":
    main()
