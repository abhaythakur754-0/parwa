# CLAUDE.md — Parwa Project

Behavioral guidelines for AI coding assistants working on the Parwa codebase. Derived from Andrej Karpathy's 4-rule CLAUDE.md framework, extended with Parwa-specific constraints.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### Parwa-Specific:
- NEVER assume a frontend component connects to a real backend API — verify the API call exists and the endpoint is wired.
- NEVER assume mock data is temporary — check if it's intentional or a leftover stub.
- When touching MCP servers, check `VARIANT_CHANNEL_PERMISSIONS` before allowing cross-variant access.
- When touching providers, check `ProviderRegistry` and `ProviderFactory` for existing implementations before creating new ones.

---

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### Parwa-Specific:
- Do NOT create a new integration layer when `ExternalToolBus` already exists. Use it.
- Do NOT create a new provider when one exists in `backend/app/core/providers/`. Register it in `ProviderRegistry`.
- Do NOT duplicate API calls — if the backend has an endpoint, the frontend MUST use it via the BFF proxy, not call external APIs directly.
- Do NOT add new Zustand stores for data that comes from the backend. Use server state (React Query / SWR) or API calls.

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

### Parwa-Specific:
- When fixing a stub MCP server, ONLY replace the stub logic with real backend calls. Do NOT restructure the server class.
- When wiring frontend to backend, ONLY change the data-fetching layer. Do NOT rewrite the UI components.
- When fixing providers, maintain the `base.py` ABC interface exactly. Do NOT change method signatures.
- Preserve all `company_id` scoping — every query MUST be tenant-isolated (BC-001).

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

### Parwa-Specific:
- "Connect integration" → "Verify: API call from frontend reaches backend endpoint, backend returns real data, frontend renders it without mock fallback"
- "Fix stub" → "Verify: MCP server tool returns real data from backend API, not hardcoded placeholder"
- "Wire billing" → "Verify: Frontend billing page calls /api/billing/* endpoints, displays real invoices from Paddle, not MOCK_INVOICES"

---

## Parwa Architecture Rules (Building Codes)

These are INVIOLABLE. Do not break them:

| Code | Rule | Check Before |
|------|------|-------------|
| BC-001 | Every query scoped by `company_id` | Adding any DB query or API call |
| BC-002 | DECIMAL for money, atomic/idempotent/audited financial ops | Touching billing/pricing code |
| BC-003 | HMAC webhook verification, idempotency, <3s response, async Celery | Adding webhook handlers |
| BC-004 | Celery for background jobs, `company_id` first param | Adding any async task |
| BC-005 | Socket.io with room-based tenant isolation | Adding real-time events |
| BC-007 | All LLM calls through Smart Router (3-tier) | Adding AI features |
| BC-008 | GSD Engine states (Redis primary, PostgreSQL fallback) | Touching ticket lifecycle |
| BC-009 | Approval workflow for financial/sensitive actions | Adding auto-action features |
| BC-011 | JWT 15min access + 7d refresh, MFA, max 5 sessions | Touching auth code |
| BC-012 | No stack traces to users, circuit breakers, graceful degradation | Adding error handling |
| BC-013 | AI technique routing is SEPARATE from model routing | Do not merge these |

---

## Known Issues (Do Not Re-discover)

1. **Billing page frontend uses `MOCK_INVOICES`** — backend has full Paddle integration
2. **Tickets page uses localStorage Zustand store** — backend has 20+ ticket API routers
3. **CRM/Ecommerce/Ticketing MCP servers are stubs** — return hardcoded placeholder data
4. **All Knowledge MCP servers (FAQ, RAG, KB) are stubs** — no vector store connection
5. **All Tool MCP servers (Analytics, Monitoring, Notifications, Compliance, SLA) are stubs**
6. **Carrier API Connector is simulated** — random tracking data, no real carrier APIs
7. **ProviderFactory._load_credentials() raises NotImplementedError** — broken credential loading
8. **Three duplicate integration layers** — ExternalToolBus, ProductionConnector, and frontend direct calls
9. **Frontend email.ts/sms.ts bypass provider registry** — call Brevo/Twilio directly from Next.js server
10. **Mailgun variable typo** — `MAILGRID_BASE_URL` should be `MAILGUN_BASE_URL`

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
