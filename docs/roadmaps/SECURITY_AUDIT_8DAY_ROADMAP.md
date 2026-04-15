# PARWA Complete Security Audit — 8-Day Fix Roadmap

> **Created:** April 16, 2026
> **Author:** Security Team Audit
> **Scope:** Full codebase — Backend (FastAPI), Frontend (Next.js), Infrastructure (Docker/Nginx), AI Pipeline
> **Source:** Cross-referenced Technology Verification Report + deep code audit of 92 service files, 74 core modules, 49 API routes, 43 test files
> **Total Findings:** 76 gaps (12 CRITICAL, 24 HIGH, 25 MEDIUM, 15 LOW)
> **Existing Coverage:** PART18_SAFETY_5DAY_PLAN.md had 63 items — this roadmap adds 13 NEW gaps found during code-level audit + reorganizes everything into 8 days

---

## FINDINGS OVERVIEW

| Area | CRITICAL | HIGH | MEDIUM | LOW | Total |
|------|----------|------|--------|-----|-------|
| Backend (FastAPI) | 2 | 5 | 7 | 4 | 18 |
| Frontend (Next.js) | 2 | 6 | 6 | 4 | 18 |
| Infrastructure (Docker/Nginx/DB) | 7 | 10 | 10 | 6 | 33 |
| AI Pipeline | 1 | 3 | 2 | 1 | 7 |
| **GRAND TOTAL** | **12** | **24** | **25** | **15** | **76** |

### What Already Works (No Action Needed)
- JWT auth with HS256, refresh token rotation, reuse detection
- bcrypt password hashing with passlib
- MFA with TOTP + backup codes (SHA-256 hashed)
- Progressive lockout (5 fails → 15min)
- httpOnly/Secure/SameSite cookies (backend side)
- HMAC webhook verification (Paddle/Shopify/Twilio)
- Rate limiting (Redis-backed, sliding window, per-category)
- API key rotation (24h grace, audit logged)
- Security headers on backend (X-Content-Type-Options, X-Frame-Options, HSTS)
- Tenant isolation middleware with ContextVar propagation
- Prompt injection defense (25+ rules, needs accuracy improvement)
- PII redaction engine (15+ types, needs accuracy improvement)

---

## ALL 76 GAPS — Organized by Category

### Category A: Authentication & Session Security (10 gaps)

| ID | Severity | Gap | File(s) | Details |
|----|----------|-----|---------|---------|
| A1 | CRITICAL | Hardcoded refresh token pepper with insecure default | `backend/app/core/auth.py:29-31` | Default `"parwa-refresh-pepper-change-in-prod"` embedded in source. If REFRESH_TOKEN_PEPPER env not set, attackers with DB access can reverse SHA-256 hashes. **Fix:** Remove default, make env var required, fail at startup if missing. |
| A2 | CRITICAL | Frontend tokens in localStorage (XSS-extractable) | `frontend/src/contexts/AuthContext.tsx:21-23,92-96` | Both access + refresh tokens stored in localStorage. Any XSS = full session hijack. Login route already sets httpOnly cookie `parwa_session` but AuthContext ignores it. **Fix:** Use `parwa_session` httpOnly cookie exclusively, remove all localStorage token storage. |
| A3 | CRITICAL | No CSRF protection anywhere | Entire frontend codebase | Zero CSRF tokens, no double-submit cookies, no Origin/Referer validation on mutating endpoints. **Fix:** Implement double-submit cookie pattern, add Origin header validation. |
| A4 | HIGH | Middleware checks wrong cookie name | `frontend/src/middleware.ts:6` | Checks for `parwa_access_token` but login route sets `parwa_session`. Auth check always fails. API route protection logic is dead code (matcher only covers `/dashboard/:path*`). **Fix:** Change cookie name to `parwa_session`, expand matcher to include API routes. |
| A5 | HIGH | Registration auto-verifies users | `frontend/src/app/api/auth/register/route.ts:104` | `is_verified: true` set on registration. Bypasses email verification entirely. Login checks `is_verified` but it's dead code. **Fix:** Set `is_verified: false`, require email verification before login. |
| A6 | HIGH | User enumeration via multiple endpoints | `frontend/src/app/api/auth/check-email/route.ts`, `register/route.ts`, `forgot-password/route.ts` | check-email returns `{ available: true/false }`, register returns `409 "already exists"`, forgot-password returns `400 "No account found"`. **Fix:** Use ambiguous responses like "If an account exists, a message has been sent." |
| A7 | HIGH | Admin endpoints use role="owner" not platform_admin | `backend/app/api/admin.py:7-13` | Any owner of ANY company can access ALL admin endpoints, view/modify other companies' data. **Fix:** Add `is_platform_admin` boolean column on users, replace all owner checks in admin routes. |
| A8 | HIGH | Webhook retry/status endpoints unauthenticated | `backend/app/api/webhooks.py:468-519` | `/api/webhooks/retry/{id}` and `/api/webhooks/status/{id}` have zero auth. Anyone can retry or view webhook events. **Fix:** Add `Depends(get_current_user)` or admin auth dependency. |
| A9 | MEDIUM | Phone OTP fragile entropy generation | `backend/app/services/phone_otp_service.py:52` | `secrets.token_hex(3)[:6]` works but fragile. **Fix:** Use `secrets.randbelow(1000000)` with explicit 6-digit format. |
| A10 | MEDIUM | OTP code leaked in email subject line | `backend/app/services/business_email_otp_service.py:163-167` | OTP visible in mobile notification previews without unlocking phone. **Fix:** Remove OTP from subject, put only in body. |

### Category B: Authorization & Access Control (6 gaps)

| ID | Severity | Gap | File(s) | Details |
|----|----------|-----|---------|---------|
| B1 | HIGH | Tenant middleware skips too many paths | `backend/app/middleware/tenant.py:42-55` | Skips `/api/billing/`, `/api/api-keys`, `/api/mfa/`, `/api/client/`, `/api/admin/` — no tenant validation on these. **Fix:** Reduce PUBLIC_PREFIXES to only truly public paths. |
| B2 | HIGH | IP allowlist trusts unvalidated X-Forwarded-For | `backend/app/middleware/ip_allowlist.py:148-164` | Takes first IP blindly, spoofable. Rate limiter correctly uses TRUSTED_PROXY_COUNT but IP allowlist doesn't. **Fix:** Apply same TRUSTED_PROXY_COUNT logic. |
| B3 | HIGH | Admin search ilike() with unescaped wildcards | `backend/app/api/admin.py:119` | `%` and `_` in search param not escaped. Searching `%` returns all records. **Fix:** Escape special chars before interpolation. |
| B4 | HIGH | Chat API completely unauthenticated + unbounded | `frontend/src/app/api/chat/route.ts:169-256` | No auth check, no rate limiting. Anyone can call `/api/chat` to burn AI API credits (Google/Cerebras/Groq). **Fix:** Add auth, rate limiting, input length validation. |
| B5 | MEDIUM | Rate limiter fails open on exception | `backend/app/middleware/rate_limit.py:87-89` | When Redis fails, rate limiting stops entirely. Under DoS, if Redis dies, all requests pass. **Fix:** Fail-closed for auth endpoints (login, MFA, reset), fail-open for general endpoints. |
| B6 | MEDIUM | Socket.io mount has no visible auth | `backend/app/main.py:173-183` | Mounted at `/ws` without auth guards at middleware level. **Fix:** Verify Socket.io server implements per-connection JWT validation. |

### Category C: Input Validation & Injection Prevention (8 gaps)

| ID | Severity | Gap | File(s) | Details |
|----|----------|-----|---------|---------|
| C1 | HIGH | PII redaction only 40% accurate | `backend/app/core/pipeline/pii_redaction_engine.py` | Short email detection broken, IP detection partial, names in context missing, partial phone missing. **Fix:** Fix regex patterns, add NER heuristic for names, add real data test suite. |
| C2 | HIGH | Prompt injection detection only 15% | `backend/app/core/pipeline/prompt_injection_defense.py` | SQL injection patterns missing, XSS patterns missing, command injection missing, system prompt extraction missing, multi-turn tracking missing, token smuggling missing. Only 7 of 12+ needed categories exist. **Fix:** Add all missing categories, test with 100+ real attack patterns. |
| C3 | MEDIUM | Weak email validation in frontend API routes | All auth API routes | Only checks `!email.includes("@")`. Accepts `@`, `@@`, `test@.`. **Fix:** Use proper email regex or validation library. |
| C4 | MEDIUM | Server-side password only checks length, not complexity | `frontend/src/app/api/auth/register/route.ts:61-73` | Only `password.length < 8`. Client-side checks complexity but server doesn't. Bypass via direct API call. **Fix:** Enforce uppercase + lowercase + digit + special char server-side. |
| C5 | MEDIUM | No rate limiting on OTP endpoints | `frontend/src/app/api/auth/verify-otp/route.ts`, `reset-password/route.ts`, `forgot-password/route.ts` | OTP brute-force possible (1M combinations, no throttle). **Fix:** Add 5 attempts per 15 minutes per email/IP. |
| C6 | MEDIUM | Unsanitized user name in email HTML | `frontend/src/app/api/forgot-password/route.ts:19-81` | `userName` interpolated directly into HTML. XSS if name contains script tags. **Fix:** HTML-escape before interpolation. |
| C7 | MEDIUM | dangerouslySetInnerHTML in chart component | `frontend/src/components/ui/chart.tsx:83` | Low risk currently (internal data), but dangerous if user input ever flows into config. **Fix:** Verify no user data flows in, consider CSS-in-JS. |
| C8 | LOW | Bare Exception in session revocation | `backend/app/api/mfa.py:251` | `raise Exception("No refresh token found")` instead of typed error. Could leak stack traces. **Fix:** Replace with `AuthenticationError`. |

### Category D: CORS, Headers & Security Headers (7 gaps)

| ID | Severity | Gap | File(s) | Details |
|----|----------|-----|---------|---------|
| D1 | CRITICAL | CORS wildcard fallback with credentials | `backend/app/main.py:258-274` | If CORS_ORIGINS empty or settings fail, falls back to `["*"]` with `allow_credentials=True`. Any website can steal cookies. **Fix:** Never fallback to `["*"]`, use empty list on error (deny all). |
| D2 | HIGH | No security headers in next.config.mjs | `frontend/next.config.mjs` | Missing CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, HSTS. **Fix:** Add `headers()` function with all standard security headers. |
| D3 | MEDIUM | No Content-Security-Policy in backend security headers | `backend/app/middleware/security_headers.py` | Sets X-Content-Type-Options, X-Frame-Options but NOT CSP. **Fix:** Add minimum `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`. |
| D4 | MEDIUM | CSP allows unsafe-inline and unsafe-eval in Nginx | `nginx/nginx.conf:112` | Negates XSS protection that CSP should provide. **Fix:** Use nonces/hashes for inline scripts, remove unsafe-eval. |
| D5 | MEDIUM | Deprecated X-XSS-Protection header in Nginx | `nginx/nginx.conf`, `infra/docker/nginx.conf`, `infra/docker/nginx-default.conf` | Deprecated, can introduce XSS in older browsers. **Fix:** Remove header, rely on CSP instead. |
| D6 | LOW | No server_tokens off in Nginx | `nginx/nginx.conf`, `infra/docker/nginx.conf` | Response headers leak exact Nginx version. **Fix:** Add `server_tokens off;` in http block. |
| D7 | LOW | HSTS missing includeSubDomains and preload in infra config | `infra/docker/nginx-default.conf:46` | Subdomains not covered by HSTS. **Fix:** Align with main config: `max-age=63072000; includeSubDomains; preload`. |

### Category E: Data Protection & Privacy (7 gaps)

| ID | Severity | Gap | File(s) | Details |
|----|----------|-----|---------|---------|
| E1 | CRITICAL | PostgreSQL internal SSL disabled | `infra/docker/postgresql.conf:47` | `ssl = off`. All credentials/PII travel unencrypted between containers. **Fix:** Enable SSL with self-signed certs minimum. |
| E2 | HIGH | PostgreSQL exporter uses sslmode=disable | `docker-compose.prod.yml:385` | DB credentials pass plaintext over Docker network. **Fix:** Change to `sslmode=require`. |
| E3 | HIGH | Missing GDPR endpoints | Not implemented | `/api/gdpr/erase` and `/api/gdpr/export` missing. No consent tracking, no data retention enforcement, no audit log retention. **Fix:** Build all GDPR endpoints + background tasks. |
| E4 | MEDIUM | Lockout duration leaked in error message | `backend/app/services/auth_service.py:249` | Reveals exact lock duration in seconds, helps attackers time brute-force. **Fix:** Use generic "Account temporarily locked. Please try again later." |
| E5 | MEDIUM | Silent JSON parse error swallowing | `backend/app/api/webhooks.py:316-324` | `except Exception: payload = {}` silently swallows malformed JSON. **Fix:** Return 400 for malformed JSON. |
| E6 | MEDIUM | Google OAuth token passed as query parameter | `backend/app/services/auth_service.py:712-713` | Token appears in access logs, browser history, proxy logs. **Fix:** Use POST with token in body. |
| E7 | LOW | Hardcoded reset URL domain | `backend/app/services/password_reset_service.py:136` | `https://parwa.ai/reset-password` hardcoded. Breaks if deployed elsewhere. **Fix:** Derive from FRONTEND_URL config. |

### Category F: Infrastructure & Docker Security (20 gaps)

| ID | Severity | Gap | File(s) | Details |
|----|----------|-----|---------|---------|
| F1 | CRITICAL | All service ports exposed to 0.0.0.0 in dev compose | `docker-compose.yml:16,34,53,117` | PostgreSQL (5432), Redis (6379), Backend (8000), Frontend (3000) published to all interfaces. Single flat network, no isolation. **Fix:** Bind to `127.0.0.1` only, create separate backend/frontend networks. |
| F2 | CRITICAL | No Redis authentication in dev compose | `docker-compose.yml:30-34` | Redis started without `--requirepass`. Any process on port 6379 has full access. **Fix:** Add `--requirepass ${REDIS_PASSWORD:-redis_dev}`. |
| F3 | CRITICAL | Weak default database password | `docker-compose.yml:13,55,89` | PostgreSQL defaults to `parwa_dev` across 3 services. **Fix:** Remove defaults, require explicit env vars. |
| F4 | CRITICAL | Prometheus lifecycle API exposed | `docker-compose.prod.yml:260` | `--web.enable-lifecycle` enables PUT/DELETE to shut down/reconfigure Prometheus. Backend on same network. **Fix:** Remove flag or protect with basic_auth. |
| F5 | CRITICAL | Production frontend port 3000 exposed without TLS | `docker-compose.prod.yml:209-210` | Users bypass Nginx security headers and TLS by hitting port 3000 directly. **Fix:** Remove `ports:` from frontend service, access only via internal network through Nginx. |
| F6 | CRITICAL | Celery worker no health check in production | `docker-compose.prod.yml:124-159` | Crashed worker never detected. Queue processing silently stops. **Fix:** Add `healthcheck:` directive. |
| F7 | HIGH | Nginx/Postgres/Redis Dockerfiles run as root | `infra/docker/nginx.Dockerfile`, `postgres.Dockerfile`, `redis.Dockerfile` | No USER directive. Container compromise = root access inside container. **Fix:** Add `USER nginx`/`USER postgres`/`USER redis`. |
| F8 | HIGH | API docs exposed without authentication | `infra/docker/nginx-default.conf:72-85` | `/docs` (Swagger) and `/openapi.json` proxied without auth or IP restriction. Full attack surface map public. **Fix:** Restrict to internal IPs. |
| F9 | HIGH | No network isolation in dev compose | `docker-compose.yml:137-139` | All services share single `parwa_network`. Compromised service = lateral movement. **Fix:** Add separate network definitions. |
| F10 | HIGH | Grafana defaults to admin username | `docker-compose.prod.yml:294` | Most commonly guessed credential in brute-force. **Fix:** Remove default, require explicit env var. |
| F11 | HIGH | Celery worker disables heartbeat | `scripts/run_worker.py:41` | `--without-heartbeat` flag. Stuck workers appear healthy to monitoring. **Fix:** Remove flag, increase heartbeat interval if needed. |
| F12 | HIGH | Redis exporter auth config gap | `docker-compose.prod.yml:358` | `REDIS_ADDR=redis://redis:6379` missing password. May fall back to no-auth. **Fix:** Use `redis://:${REDIS_PASSWORD}@redis:6379`. |
| F13 | HIGH | Missing Dockerfiles directory | `infra/docker/` | Multiple references but directory incomplete. **Fix:** Create all missing Dockerfiles with non-root users. |
| F14 | MEDIUM | No Docker image pinning by digest | All compose files | Tags are mutable. Compromised upstream image = vulnerability. **Fix:** Pin critical images by SHA256 digest. |
| F15 | MEDIUM | No read_only filesystems on containers | All compose files | All writable. Attacker can plant persistence. **Fix:** Add `read_only: true` + `tmpfs` for writable paths. |
| F16 | MEDIUM | No cap_drop ALL on containers | All compose files | Containers retain unnecessary Linux capabilities. **Fix:** Add `cap_drop: ALL`, add back only specific needed capabilities. |
| F17 | MEDIUM | Node exporter broad host filesystem access | `docker-compose.prod.yml:416-419` | Mounts `/proc`, `/sys`, `/` as read-only. **Fix:** Scope mount more tightly. |
| F18 | MEDIUM | .env points to local SQLite instead of Docker PostgreSQL | `.env:1` | `DATABASE_URL=file:/home/z/my-project/db/custom.db`. Backend uses wrong DB. **Fix:** Update to PostgreSQL URL. |
| F19 | MEDIUM | Prisma schema uses SQLite while backend uses PostgreSQL | `prisma/schema.prisma:11-14` | Schema drift. Prisma operations fail in production. **Fix:** Add PostgreSQL datasource for production. |
| F20 | LOW | No automated SSL cert renewal | `nginx/nginx.conf:68-70` | Let's Encrypt path configured but no certbot or cron job. **Fix:** Add certbot sidecar or cron renewal. |

### Category G: Logging, Monitoring & Operational Security (6 gaps)

| ID | Severity | Gap | File(s) | Details |
|----|----------|-----|---------|---------|
| G1 | MEDIUM | No PII/secrets verification in application logs | Logger config | Not verified that passwords, tokens, PII never logged. **Fix:** Audit all log statements, add log scrubbing. |
| G2 | MEDIUM | Security event logging incomplete | Audit service | Failed auth, blocked injections, rate limit hits not fully logged. **Fix:** Add comprehensive security event logging. |
| G3 | LOW | Console.error leaks in production | Multiple frontend files | Detailed error messages including stack traces logged to console. **Fix:** Use structured logging with appropriate log levels. |
| G4 | LOW | No log rotation on containers | All compose files | No `logging:` driver config. Disk exhaustion risk. **Fix:** Add `max-size: "10m" max-file: "3"` to all services. |
| G5 | LOW | No pids_limit on containers | All compose files | Fork bomb could crash host. **Fix:** Add `pids_limit: 100` to all services. |
| G6 | LOW | Deploy script stops dev compose, not prod | `deploy.sh:124-128` | Operator may stop wrong compose. **Fix:** Track active mode, use correct compose file. |

### Category H: Frontend Architecture & Configuration (6 gaps)

| ID | Severity | Gap | File(s) | Details |
|----|----------|-----|---------|---------|
| H1 | HIGH | In-memory session store not production-safe | `frontend/src/app/api/auth/login/route.ts:12-14` | Sessions stored in `Map()`. Not shared across server instances/serverless. Users randomly lose sessions. **Fix:** Use Redis or DB-backed session store. |
| H2 | MEDIUM | ignoreBuildErrors: true in next.config.mjs | `frontend/next.config.mjs:5` | TypeScript errors silently ignored. Can mask security type issues. **Fix:** Set to `false` for production. |
| H3 | MEDIUM | React strict mode disabled | `frontend/next.config.mjs` | Reduces detection of side-effect bugs. **Fix:** Set to `true`. |
| H4 | LOW | NEXT_PUBLIC_BACKEND_URL could leak internal URL | Multiple proxy routes | Fallback to NEXT_PUBLIC_* embeds in client bundle. **Fix:** Remove NEXT_PUBLIC_BACKEND_URL fallback for server-only routes. |
| H5 | LOW | Open redirect via redirect query parameter | `frontend/src/app/(auth)/login/page.tsx:28` | `redirectTo` from searchParams used unsanitized with router.push(). **Fix:** Validate starts with `/` and not `//`. |
| H6 | LOW | reset-password/page.tsx has broken imports | `frontend/src/app/(auth)/reset-password/page.tsx:42` | Uses undefined `axios` and `API_BASE_URL`. Page fails at runtime. **Fix:** Fix imports or use fetch(). |

### Category I: AI Pipeline Security (6 gaps)

| ID | Severity | Gap | File(s) | Details |
|----|----------|-----|---------|---------|
| I1 | CRITICAL | RAG pipeline uses MockVectorStore | `backend/app/shared/knowledge_base/vector_search.py` | Random similarity scores instead of real pgvector cosine similarity. Core selling point ("learns from your docs") is non-functional. **Fix:** Implement real pgvector integration with cosine similarity queries, proper indexes, metadata filtering. |
| I2 | HIGH | Information leakage prevention at 0% | System prompt layer | No blocking of LLM name/model revelation, routing strategy, system prompt extraction, other tenants' existence. **Fix:** Build info leakage prevention layer. |
| I3 | HIGH | Guardrails exist but not wired to production pipeline | AI pipeline | 8 guardrail layers are test-only, not running on live AI responses. **Fix:** Wire all layers into production pipeline. |
| I4 | HIGH | Framework documentation mismatch | Multiple files | Docs claim LangGraph, DSPy, LiteLLM — none actually used in production. Trust risk for investors/clients. **Fix:** Either integrate frameworks or update docs to reflect reality. |
| I5 | MEDIUM | Training data cross-tenant isolation unverified | Training tasks | No enforcement that training data stays within tenant boundary. **Fix:** Add tenant scoping to all training operations. |
| I6 | LOW | Technique nodes have varying implementation depth | `backend/app/core/techniques/*.py` | 12 technique nodes, some fully implemented, some stubs. **Fix:** Per-node audit before claiming production-ready. |

---

## 8-DAY EXECUTION PLAN

### DAY 1 — Critical Auth & Session Security (P0)

**Focus:** Fix the 5 most exploitable gaps that would allow active attacks today.

**Tasks:**
- [ ] A1: Remove hardcoded refresh token pepper default in `backend/app/core/auth.py:29-31`. Make REFRESH_TOKEN_PEPPER required env var, fail at startup if missing.
- [ ] A2: Migrate frontend from localStorage tokens to httpOnly `parwa_session` cookie exclusively. Remove all `localStorage.setItem/getItem` for tokens in `AuthContext.tsx` and `api.ts`. Update API client to use `withCredentials: true` only (already done), remove localStorage Authorization header.
- [ ] A4: Fix middleware cookie name from `parwa_access_token` to `parwa_session` in `frontend/src/middleware.ts:6`. Expand matcher to cover API routes.
- [ ] D1: Fix CORS wildcard fallback in `backend/app/main.py:258-274`. Never use `["*"]` with credentials. On error, use empty list (deny all) + log warning.
- [ ] A3: Implement CSRF protection — double-submit cookie pattern on all mutating API routes. Add Origin/Referer header validation middleware.
- [ ] A5: Fix registration to set `is_verified: false` in `frontend/src/app/api/auth/register/route.ts:104`. Ensure email verification flow is required before login.
- [ ] A6: Fix user enumeration — ambiguous responses on check-email, register, forgot-password endpoints.

**Deliverables:** Session hijacking via XSS blocked, CSRF protection active, CORS properly locked down, email verification enforced.
**Files touched:** `auth.py`, `AuthContext.tsx`, `api.ts`, `middleware.ts`, `main.py`, `register/route.ts`, `check-email/route.ts`, `forgot-password/route.ts`, new CSRF middleware.

---

### DAY 2 — Infrastructure & Docker Hardening (P0)

**Focus:** Lock down all exposed ports, credentials, and container security.

**Tasks:**
- [ ] F1: Bind all dev compose ports to `127.0.0.1` only. Add `127.0.0.1:5432:5432`, `127.0.0.1:6379:6379`, etc. in `docker-compose.yml`.
- [ ] F2: Add `--requirepass ${REDIS_PASSWORD:-redis_dev}` to Redis in dev compose.
- [ ] F3: Remove default passwords from PostgreSQL in `docker-compose.yml`. Require explicit env vars.
- [ ] F5: Remove port `3000:3000` from frontend in production compose. Access only via internal network through Nginx.
- [ ] F4: Remove `--web.enable-lifecycle` from Prometheus or add basic_auth protection.
- [ ] F6: Add healthcheck to Celery worker in production compose.
- [ ] F7: Add `USER nginx`/`USER postgres`/`USER redis` to all custom Dockerfiles in `infra/docker/`.
- [ ] F8: Restrict `/docs` and `/openapi.json` to internal IPs in `infra/docker/nginx-default.conf`.
- [ ] F9: Add network isolation in dev compose (separate backend_network and frontend_network).
- [ ] F10: Remove Grafana admin default, require explicit env var.
- [ ] F11: Remove `--without-heartbeat` from Celery worker in `scripts/run_worker.py`.
- [ ] F12: Fix Redis exporter to include password in connection URL.

**Deliverables:** No ports exposed to 0.0.0.0, all containers run as non-root, Redis authenticated everywhere, monitoring secured.
**Files touched:** `docker-compose.yml`, `docker-compose.prod.yml`, `infra/docker/*.Dockerfile`, `infra/docker/nginx-default.conf`, `scripts/run_worker.py`.

---

### DAY 3 — Database SSL, Access Control & API Security (P0)

**Focus:** Encrypt internal traffic, fix authorization gaps, secure API endpoints.

**Tasks:**
- [ ] E1: Enable PostgreSQL internal SSL in `infra/docker/postgresql.conf`. Generate self-signed certs in init script.
- [ ] E2: Fix PostgreSQL exporter `sslmode=disable` to `sslmode=require` in production compose.
- [ ] A7: Add `is_platform_admin` boolean column on User model via Alembic migration. Replace all `require_roles("owner")` in admin routes with platform admin check in `backend/app/api/admin.py`.
- [ ] A8: Add `Depends(get_current_user)` to webhook retry/status endpoints in `backend/app/api/webhooks.py`.
- [ ] B1: Reduce tenant middleware PUBLIC_PREFIXES in `backend/app/middleware/tenant.py`. Remove billing, API keys, MFA, client from skip list.
- [ ] B2: Apply TRUSTED_PROXY_COUNT logic to IP allowlist middleware in `backend/app/middleware/ip_allowlist.py`.
- [ ] B3: Escape `%` and `_` in admin search before ilike interpolation in `backend/app/api/admin.py`.
- [ ] B4: Add authentication + rate limiting to `/api/chat` endpoint in `frontend/src/app/api/chat/route.ts`.
- [ ] E3: Build GDPR endpoints — `/api/gdpr/erase` (cascade delete all user data), `/api/gdpr/export` (export as JSON). Add consent tracking fields.

**Deliverables:** Internal traffic encrypted, admin access properly controlled, chat API secured, GDPR endpoints live.
**Files touched:** `postgresql.conf`, `docker-compose.prod.yml`, `admin.py`, `webhooks.py`, `tenant.py`, `ip_allowlist.py`, `chat/route.ts`, new `gdpr.py`.

---

### DAY 4 — PII Redaction & Prompt Injection Defense (P1)

**Focus:** Fix the two biggest AI safety accuracy gaps.

**Tasks:**
- [ ] C1: Fix PII redaction engine to 90%+ accuracy:
  - Fix short email regex (handle a@b.co, a@b.c)
  - Fix IP address detection (v4+v6, reduce false positives)
  - Add partial phone detection (last 4 digits, masked formats)
  - Add name-in-context heuristic (common first/last names + title patterns)
  - Add address detection improvement
  - Ensure PII check runs on LLM OUTPUT (not just input)
  - Write 50+ real-world PII test cases
- [ ] C2: Expand prompt injection defense to 95%+ detection:
  - Add SQL injection patterns (SELECT/DROP/DELETE/INSERT/UPDATE/UNION)
  - Add XSS patterns (script tags, onerror, onclick, javascript: URI)
  - Add command injection patterns (rm -rf, /etc/passwd, curl, wget, exec)
  - Add system prompt extraction detection ("repeat your instructions", "what are your rules")
  - Add multi-turn injection tracking (session-level injection score)
  - Add token smuggling detection (base64, ROT13, unicode escapes)
  - Add role-play attack patterns (DAN, AIM, dev mode)
  - Test with 100+ real attack patterns
- [ ] I2: Build information leakage prevention layer:
  - Block revealing which LLMs are used
  - Block revealing routing strategy
  - Block revealing internal workflow details
  - Block revealing system prompts
  - Block revealing other tenants' existence
  - Add canned response: "I cannot discuss PARWA's internal systems"

**Deliverables:** PII 90%+ accuracy, injection 95%+ detection, info leakage blocked.
**Files touched:** `pii_redaction_engine.py`, `prompt_injection_defense.py`, `test_pii_redaction.py`, `test_prompt_injection.py`, new `info_leak_guard.py`.

---

### DAY 5 — Security Headers, Input Validation & Frontend Hardening (P1)

**Focus:** Defense-in-depth through headers, validation, and frontend fixes.

**Tasks:**
- [ ] D2: Add all security headers to `frontend/next.config.mjs` — CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, HSTS.
- [ ] D3: Add Content-Security-Policy to backend security headers middleware.
- [ ] D4: Fix CSP in `nginx/nginx.conf` — replace `unsafe-inline`/`unsafe-eval` with nonces/hashes.
- [ ] D5: Remove deprecated X-XSS-Protection from all Nginx configs.
- [ ] D6: Add `server_tokens off;` to all Nginx configs.
- [ ] D7: Add `includeSubDomains; preload` to HSTS in infra Nginx config.
- [ ] C3: Add proper email validation (regex or library) to all frontend auth API routes.
- [ ] C4: Enforce password complexity server-side in `register/route.ts` (uppercase + lowercase + digit + special + 8 chars).
- [ ] C5: Add rate limiting to OTP endpoints (5 attempts per 15 min per email/IP).
- [ ] C6: HTML-escape userName before interpolation in forgot-password email template.
- [ ] H1: Migrate in-memory session Map to Redis-backed store in `login/route.ts`.
- [ ] H2: Set `ignoreBuildErrors: false` and `reactStrictMode: true` in `frontend/next.config.mjs`.
- [ ] H5: Validate redirectTo starts with `/` and not `//` in login page.
- [ ] H6: Fix broken imports in `reset-password/page.tsx`.
- [ ] H4: Remove NEXT_PUBLIC_BACKEND_URL fallback from server-only proxy routes.

**Deliverables:** Complete security headers across all layers, input validation hardened, frontend production-ready.
**Files touched:** `next.config.mjs`, `nginx/nginx.conf`, `infra/docker/nginx*.conf`, `security_headers.py`, `register/route.ts`, `login/route.ts`, `verify-otp/route.ts`, `reset-password/route.ts`, `forgot-password/route.ts`, `login/page.tsx`, `reset-password/page.tsx`, multiple proxy routes.

---

### DAY 6 — AI Pipeline & RAG Fix (P1)

**Focus:** Make the AI intelligence layer actually functional.

**Tasks:**
- [ ] I1: Replace MockVectorStore with real pgvector integration:
  - Implement real pgvector SQL queries with cosine similarity
  - Create proper vector indexes (IVFFlat or HNSW)
  - Add metadata filtering per tenant
  - Wire embedding service output to pgvector storage
  - Test retrieval quality with real documents
- [ ] I3: Wire all 8 guardrail layers into the live AI production pipeline (not just tests):
  - Content Safety, Topic Relevance, Hallucination Check, Policy Compliance, Tone Validation, Length Control, PII Leak Prevention, Confidence Gate
  - Validate each with 20+ real LLM output samples
- [ ] I5: Add tenant scoping to all training operations. Ensure training data never crosses tenants.
- [ ] I6: Per-node audit of 12 AI technique implementations. Document which are fully implemented vs stubs.
- [ ] I4: Update documentation to accurately reflect framework usage (custom implementations vs LangGraph/DSPy/LiteLLM). Remove misleading claims.

**Deliverables:** RAG pipeline functional with real vector search, guardrails live in production, documentation honest.
**Files touched:** `vector_search.py`, `rag_retrieval.py`, `ai_pipeline.py`, `guardrails_engine.py`, training task files, docs.

---

### DAY 7 — Docker Hardening Deep Dive & Monitoring (P2)

**Focus:** Container security best practices, operational readiness.

**Tasks:**
- [ ] F14: Pin critical Docker images by SHA256 digest (postgres, redis, nginx, python).
- [ ] F15: Add `read_only: true` to all production containers + `tmpfs` for writable paths.
- [ ] F16: Add `cap_drop: ALL` to all containers + `cap_add` only specific needed capabilities.
- [ ] F13: Create all missing Dockerfiles in `infra/docker/` with non-root users and minimal base images.
- [ ] F17: Scope node exporter mounts more tightly, exclude sensitive paths.
- [ ] F18: Fix `.env` to use Docker PostgreSQL URL instead of local SQLite.
- [ ] F19: Add PostgreSQL datasource to Prisma schema for production (or remove Prisma if unused).
- [ ] G1: Audit ALL log statements — verify no PII, passwords, tokens logged.
- [ ] G2: Add comprehensive security event logging (failed auth, blocked injections, rate limit hits).
- [ ] G4: Add log rotation to all Docker services (`max-size: "10m" max-file: "3"`).
- [ ] G5: Add `pids_limit` to all containers.
- [ ] G6: Fix deploy script to track active mode and use correct compose file.
- [ ] F20: Add certbot sidecar or cron for automated SSL cert renewal.
- [ ] B5: Implement fail-closed rate limiting for auth endpoints (login, MFA, reset), fail-open for general endpoints.
- [ ] B6: Verify Socket.io server implements per-connection JWT validation.
- [ ] A9: Fix phone OTP to use `secrets.randbelow(1000000)`.
- [ ] A10: Remove OTP from email subject line.
- [ ] C8: Replace bare Exception with AuthenticationError in MFA session revocation.
- [ ] E4: Fix lockout duration leaked in error message.
- [ ] E5: Return 400 for malformed JSON in webhook handler.
- [ ] E6: Use POST instead of GET for Google OAuth token validation.
- [ ] E7: Derive reset URL from FRONTEND_URL config instead of hardcoded domain.

**Deliverables:** Containers fully hardened, logging clean and structured, all remaining MEDIUM/LOW items resolved.
**Files touched:** All compose files, all Dockerfiles, `.env`, `prisma/schema.prisma`, logger config, `rate_limit.py`, `phone_otp_service.py`, `business_email_otp_service.py`, `webhooks.py`, `auth_service.py`, `password_reset_service.py`, `mfa.py`, `socketio.py`, `deploy.sh`.

---

### DAY 8 — Full Integration Testing & Verification

**Focus:** End-to-end validation of everything fixed in Days 1-7.

**Tasks:**
- [ ] Run full PII redaction test suite — verify 90%+ accuracy on 200+ test cases
- [ ] Run full prompt injection test suite — verify 95%+ detection on 200+ attack patterns
- [ ] Run cross-tenant isolation test — verify zero data leakage between 5 test tenants
- [ ] Run GDPR erasure test — verify complete data deletion with cascade
- [ ] Run GDPR export test — verify export matches all stored data
- [ ] Run guardrail validation — verify all 8 layers fire on real LLM outputs
- [ ] Run information leakage test — verify AI never reveals LLM names, strategy, workflows
- [ ] Run CSRF test — verify all mutating endpoints reject cross-origin requests
- [ ] Run session security test — verify tokens only in httpOnly cookies, not localStorage
- [ ] Run Docker security scan — verify non-root, Redis auth, network isolation, no exposed ports
- [ ] Run rate limit stress test — verify burst protection works under load
- [ ] Run security header validation — verify all headers present on API + frontend responses
- [ ] Run RAG retrieval test — verify real pgvector returns relevant results
- [ ] Run multi-tenant load test — verify isolation under concurrent access
- [ ] Run password reset flow — verify ambiguous responses (no enumeration)
- [ ] Run admin access test — verify only platform_admin can access admin endpoints
- [ ] Fix any bugs found during testing
- [ ] Update all test files with real test data (no stubs)
- [ ] Update PART18_SAFETY_5DAY_PLAN.md status — mark completed items
- [ ] Update MAIN_ROADMAP.md — Part 18 to 100%

**Deliverables:** All 76 items verified, Part 18 COMPLETE, PARWA production-ready from security perspective.
**Files touched:** All test files, PROJECT_STATUS.md, MAIN_ROADMAP.md, PART18_SAFETY_5DAY_PLAN.md.

---

## SUMMARY — 76 Items Across 8 Days

| Day | Focus | Gaps Covered | Priority | Key Outcome |
|-----|-------|-------------|----------|-------------|
| 1 | Auth & Session Security | A1-A10, D1, A3 (13 items) | P0 | Session hijack blocked, CSRF active, CORS locked |
| 2 | Infrastructure & Docker | F1-F13 (13 items) | P0 | No exposed ports, non-root containers, Redis auth |
| 3 | DB SSL, Access Control, API | E1-E3, A7-A8, B1-B4 (10 items) | P0 | Internal traffic encrypted, admin access controlled |
| 4 | PII, Injection, Info Leakage | C1-C2, I2-I3 (3 items, but large) | P1 | PII 90%+, Injection 95%+, info leakage blocked |
| 5 | Headers, Validation, Frontend | D2-D7, C3-C7, H1-H6 (14 items) | P1 | Security headers complete, input validated |
| 6 | AI Pipeline & RAG | I1, I3-I6 (4 items, critical) | P1 | RAG functional, guardrails live, docs honest |
| 7 | Docker Deep Dive & Remaining | F14-F20, G1-G6, B5-B6, A9-A10, C8, E4-E7 (18 items) | P2 | All MEDIUM/LOW resolved, containers hardened |
| 8 | Testing & Verification | All 76 items validated | P0 | Everything verified, Part 18 COMPLETE |

---

## SUCCESS CRITERIA

| Metric | Current | Target |
|--------|---------|--------|
| Critical gaps | 12 | 0 |
| High gaps | 24 | 0 |
| Medium gaps | 25 | Resolved |
| Low gaps | 15 | Resolved |
| PII redaction accuracy | 40% | 90%+ |
| Prompt injection detection | 15% | 95%+ |
| Tenant data isolation | Partial | 100% verified |
| Information leakage blocked | 0% | 100% |
| GDPR compliance | Missing | Endpoints live |
| RAG pipeline | MockVectorStore | Real pgvector |
| Guardrails in production | Test-only | All 8 layers live |
| Docker security | Partial | Fully hardened |
| Auth session storage | localStorage | httpOnly cookies only |
| CSRF protection | None | Active on all mutating routes |
| Security headers | Partial | Complete (backend + frontend + Nginx) |
| CORS configuration | Wildcard fallback | Explicit origins only |
| Admin access control | role=owner | is_platform_admin flag |

---

## DEPENDENCIES

**None.** This security roadmap has zero dependencies on other parts. Can start immediately on Day 1.

## PARALLEL WORK POSSIBLE

While security work is happening, these can run in parallel:
- Part 12 (Dashboard) — no security dependency
- Part 15 (Billing) — no security dependency
- Part 13 (Ticket Management) — no security dependency
