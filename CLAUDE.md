# CLAUDE.md — PARWA Project Behavioral Guidelines

> Derived from Andrej Karpathy's LLM coding observations (91K+ GitHub stars).
> These rules bias toward caution over speed. For trivial tasks, use judgment.

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing ANY change:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, STOP. Name what's confusing. Ask.

**PARWA-specific:**
- This project was vibe-coded for 4 months. NOTHING works as-is. Every feature needs verification.
- The spec documents (in `/documents/`) describe what SHOULD exist — not what actually works.
- Always verify against actual code, not against docs. Docs lie in this project.
- When you find a discrepancy between docs and code, flag it explicitly.
- **Don't assume a frontend page connects to the backend — CHECK it.** Many pages have API calls that 404 or hit dead routes. Trace the full path: frontend store → Next.js proxy → backend router → service → DB.
- **Don't assume a backend route is registered — CHECK main.py.** Several router files exist but are never imported (shadow_mode.py, jarvis_chat.py). A file existing does NOT mean the route works.

---

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

**PARWA-specific:**
- This project has 1,690 source files, 213 components, 154 DB tables, 130 features spec'd.
- Most of this is dead/broken code. DO NOT add complexity. REMOVE it.
- Prefer fixing what exists over building new abstractions.
- If a component imports 20 things and renders nothing useful, it needs surgery, not wrapping.
- No new npm packages without explicit justification.
- **Don't create a new integration layer when one already exists.** Check `backend-proxy.ts`, `api.ts`, and the Zustand stores before building any new API client. There are already 3 different HTTP patterns in this codebase — don't add a 4th.

---

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

**PARWA-specific:**
- The dashboard has known structural bugs (e.g., double-nested routes like `dashboard/calls/calls/page.tsx`).
- Fix the specific bug, don't restructure the entire routing system.
- When fixing a component, don't touch other components in the same folder.
- The project has duplicate directories (`/database/` AND `/backend/database/`). Note it, don't merge it unless asked.
- **Every database query MUST be scoped to the customer's company (BC-001).** This is a multi-tenant SaaS. If you write any backend query, it MUST filter by `company_id`. A missing company_id filter means data leakage between customers. No exceptions.

---

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

**PARWA-specific:**
- Every fix MUST have proof: build proof (no compile errors), logic proof (code trace), or runtime proof (test output).
- When you fix a dashboard page, verify: does it render? Does it call the right API? Does the data flow correctly?
- Before marking anything "done", ask: "If a user clicked this right now, would it work?"
- Known working: Auth (signup/login) — fixed by user. Everything else is unverified.

---

## Project Context — PARWA

### What is PARWA?
AI-powered customer support workforce platform. 3 subscription tiers:
- Mini PARWA ($999/mo)
- PARWA ($2,499/mo)
- PARWA High ($3,999/mo)

### Tech Stack
- **Frontend**: Next.js 16, React, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI (Python), PostgreSQL 15 + pgvector, Redis 7, Celery (8 queues)
- **AI Pipeline**: LangGraph GSD State Engine (19 nodes)
- **Billing**: Paddle
- **Channels**: Email (Brevo), SMS (Twilio), Voice, Chat Widget
- **AI Assistant**: Jarvis (awareness, commands, proactive alerts)

### Deployment
- Frontend: Vercel (parwa.buzz)
- Backend: Render (parwa-backend.onrender.com)

### Architecture
- Multi-tenant with `company_id` isolation
- Omnichannel support (email, SMS, voice, chat)
- AI variants handle customer conversations autonomously

### Key Directories
- `/src/app/` — Next.js app router pages
- `/src/components/` — React components (ui/, dashboard/, shared/)
- `/src/lib/` — Utilities, API clients, hooks
- `/backend/` — FastAPI backend
- `/documents/` — Spec documents (NOT source of truth for working state)
- `/graphify-out/` — Dashboard structure diagrams
- `/prisma/` — Database schema (deprecated, use `/backend/database/`)
- `/database/` — Legacy database files (duplicate of `/backend/database/`)

### Known Issues
- Double-nested route bug: `dashboard/calls/calls/page.tsx`
- Duplicate database directories
- Deprecated Prisma schema
- Most features spec'd but not working
- Cloudflare adapter may still be in package.json (should be removed)

### Working State
- Auth: FIXED (signup/login works)
- Dashboard: UNVERIFIED (this is what we're fixing)
- Integration: UNVERIFIED (separate chat)
- Frontend/Landing: UNVERIFIED (separate chat)

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## PARWA Building Codes (BC) — Rules That Must NEVER Be Broken

These are non-negotiable. Violating any of these is a critical bug, not a style choice.

| Code | Rule | Why |
|------|------|-----|
| **BC-001** | Every DB query MUST be scoped to `company_id` | Multi-tenant isolation. Missing filter = data leakage between customers. |
| **BC-002** | Don't assume a frontend page connects to the backend — CHECK it | Many pages call APIs that 404 or hit dead routes. Trace the full path. |
| **BC-003** | Don't assume a backend route is registered — CHECK main.py | Several router files exist but are never imported (shadow_mode.py, jarvis_chat.py). |
| **BC-004** | Don't create a new integration layer when one already exists | Check `backend-proxy.ts`, `api.ts`, and existing stores before building new API clients. |
| **BC-005** | Never trust frontend-only data as source of truth | localStorage/Zustand without backend sync = data that disappears. Ticket store is the worst offender. |
| **BC-006** | API path prefixes must match between frontend and backend | `/api/billing/*` vs `/api/v1/billing/*` will cause 404s. Verify the actual backend path before calling. |
| **BC-007** | Mock data must be clearly labeled in the UI | Users must know when they're seeing demo data vs real data. The `_mock` flag must be surfaced. |
