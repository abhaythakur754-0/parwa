# PROJECT_STATE.md — Live Project State Memory

> **Last Updated:** April 16, 2026
> **Approach:** Part-by-part production readiness. One part at a time, no stubs allowed.

## Project Overview

- **Name:** PARWA AI Workforce
- **Stack:** FastAPI + Next.js 15 + PostgreSQL + Redis + Celery + Socket.io + Paddle + Brevo + Twilio
- **Industries:** E-commerce, SaaS, Logistics (NO healthcare — removed April 2026)
- **Deployment:** Docker (docker-compose for dev, docker-compose.prod.yml for production)
- **Current Phase:** Production Readiness — 18-part systematic plan
- **Currently Building:** Part 18 (Safety — 5-day plan, 63 items) + Part 12 (Dashboard — 8-day plan, 155 items) + Part 15 (Billing — 6-day plan, 105 items, 43 issues found)

## Current Status

Previous approach (Weeks 1-17 roadmap) marked many items as COMPLETE that were actually stubs or partial implementations. The Production Readiness Report revealed the real state. We are now following an 18-part systematic plan — completing each part fully before moving to the next.

## 18-Part Status

| # | Part | Completeness | Priority |
|---|------|-------------|----------|
| 1 | Infrastructure & Foundation | ~55% | P0 |
| 2 | Onboarding System | ~60% | P0 |
| 3 | Three Variants & Billing | ~50% | P0 |
| 4 | Industry-Specific Variants | ~15% | P1 |
| 5 | Variant Orchestration | ~40% | P1 |
| 6 | Agent Lightning (Training) | ~20% | P1 |
| 7 | MAKER Framework | ~15% | P1 |
| 8 | Context Awareness / Memory | ~35% | P1 |
| 9 | AI Technique Engine | ~70% | P1 |
| 10 | Jarvis Control System | ~40% | P1 |
| 11 | Shadow Mode | ~0% | P2 |
| 12 | Dashboard System | ~30% | P1 |
| 13 | Ticket Management | ~65% | P1 |
| 14 | Communication Channels | ~30% | P2 |
| 15 | Billing & Revenue | ~50% | P0 |
| 16 | Training & Analytics | ~25% | P2 |
| 17 | Integrations | ~35% | P2 |
| 18 | Safety & Compliance | ~40% | P0 |

## Key Architecture Decisions

1. **Tenant Isolation:** company_id flows from JWT to middleware to DB queries to Celery tasks to Redis keys
2. **Task Pattern:** All Celery tasks use ParwaBaseTask + @with_company_id + exponential backoff
3. **Webhook Flow:** HMAC verify then store event then dispatch to Celery then provider handler
4. **Event System:** Socket.io with typed events, emit helpers, tenant rooms, reconnection buffer
5. **Health Checks:** Dependency-aware with Prometheus metrics, Grafana dashboards, alerting rules
6. **Smart Router:** 3-tier LLM routing (Light/Medium/Heavy) with variant gating per tenant plan
7. **AI Pipeline:** Signal Extraction then Classification then RAG then Technique Selection then Response Generation then CLARA Quality Gate
8. **GSD Engine:** 6-state machine (NEW then GREETING then DIAGNOSIS then RESOLUTION then FOLLOW-UP then CLOSED)
9. **14 AI Techniques:** Tier 1 (CLARA, CRP, GSD), Tier 2 (CoT, ReAct, ThoT, Reverse, Step-Back), Tier 3 (GST, UoT, ToT, Self-Consistency, Reflexion, Least-to-Most)

## Critical Findings (Technology Verification Report)

- RAG pipeline uses MockVectorStore — generates random similarity scores
- LangGraph is NOT used — custom dataclass state machine instead
- DSPy is effectively disabled — stubs return empty results
- LiteLLM is NOT integrated — Smart Router uses raw httpx calls
- pgvector is NOT used — MockVectorStore replaces all real vector search

## Critical Findings (Production Readiness Report)

- PII redaction only 40% accurate (target 90%+)
- Prompt injection detection only 15% (target 95%+)
- 4 dashboard pages completely missing (tickets, agents, approvals, settings)
- 7 dashboard pages have NO frontend despite backend being fully built (CRM, conversations, knowledge base, billing, integrations, notifications, audit)
- 8 orphaned React components built but never rendered on any page
- Socket.io server has 22 events, frontend has ZERO socket client
- system_status_service.py (867 lines) has no API endpoint or frontend
- Per-agent individual views missing (client requirement: what each agent is doing)
- Call recording playback missing (client requirement: listen to conversations)
- ROI comparison, First Victory, confidence display, logout, emergency pause all missing from dashboard

## Critical Findings (Billing Audit — April 16)

- 5 critical architectural bugs: downgrades never execute, usage not metered, variants disconnected from billing, entitlement enforcement broken (only tickets), calendar month vs billing period mismatch
- 8 code bugs: email says 48hr but code stops immediately, create_transaction() missing on PaddleClient, double-counting in overage, AI agents not stopped on payment failure, ticket status lost on resume, fake variant price IDs, wrong plan names in ReAct tool, HMAC inconsistency
- 33 missing features: no yearly billing, no 30-day periods, no variant add-on management, no resource cleanup on downgrade, no refund system, no chargeback handling, no spending cap, no data export, no retention policy, no trial, no pause, no promo codes, no corporate invoicing, and 21 more
- 10 additional bugs in Celery tasks, reconciliation, and webhook handling
- Shadow mode has zero code
- No yearly billing logic
- Email channel AI loop incomplete

## Execution Plan

Parallel streams with no dependencies:
- Wave 1: Part 18 (Safety — 5 days) + Part 12 (Dashboard — 8 days, 155 items) + Part 15 (Billing — 6 days, 105 items)
- Wave 2: Part 11 (Shadow Mode) + Part 14 (Channels) + Part 3 (Variants)
- Wave 3: Part 10 (Jarvis) + Part 8 (Context) + Part 13 (Tickets) + Part 9 (AI Techniques)
- Wave 4: Part 4 (Industry) + Part 5 (Orchestration) + Part 6 (Training) + Part 16 (Analytics) + Part 17 (Integrations)
- Wave 5: Part 2 (Onboarding) + Part 7 (MAKER Framework)

## Next Steps

- Execute Part 18 Day 1 — PII & Prompt Injection fixes
- OR execute Part 12 Day 1 — Dashboard foundation (header, sidebar, Socket.io)
- OR execute Part 15 Day 1 — Critical billing fixes (usage metering, enforcement, bugs)
- Update PROJECT_STATUS.md daily with progress
