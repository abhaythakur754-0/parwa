# PROJECT_STATE.md — Live Project State Memory

> **Last Updated:** April 16, 2026
> **Approach:** Part-by-part production readiness. One part at a time, no stubs allowed.

## Project Overview

- **Name:** PARWA AI Workforce
- **Stack:** FastAPI + Next.js 15 + PostgreSQL + Redis + Celery + Socket.io + Paddle + Brevo + Twilio
- **Repo:** https://github.com/abhaythakur754-0/parwa.git
- **Current Phase:** Production Readiness — 18-part systematic plan

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
- No cancel/upgrade/downgrade UI
- Shadow mode has zero code
- No yearly billing logic
- Email channel AI loop incomplete

## Execution Plan

Parallel streams with no dependencies:
- Wave 1: Part 18 (Safety) + Part 12 (Dashboard) + Part 15 (Billing) + Part 1 (Infrastructure)
- Wave 2: Part 11 (Shadow Mode) + Part 14 (Channels) + Part 3 (Variants)
- Wave 3: Part 10 (Jarvis) + Part 8 (Context) + Part 13 (Tickets) + Part 9 (AI Techniques)
- Wave 4: Part 4 (Industry) + Part 5 (Orchestration) + Part 6 (Training) + Part 16 (Analytics) + Part 17 (Integrations)
- Wave 5: Part 2 (Onboarding) + Part 7 (MAKER Framework)

## Next Steps

- Decide which part(s) to start building first
- Build each part completely before moving to the next
- Update PROJECT_STATUS.md daily with progress
