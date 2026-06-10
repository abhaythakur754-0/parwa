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
