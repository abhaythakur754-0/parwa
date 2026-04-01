# PARWA — Project Status Tracker

> Auto-generated. DO NOT modify the 21 source documents in `/documents/`.
> This file tracks build progress, test counts, commits, and per-day completion.

---

## Overall Progress

| Week | Days | Status | Features | Tests |
|------|------|--------|----------|-------|
| Week 1 | Day 1-6 | ✅ DONE | F-001 to F-009 | 713 → 713 |
| Week 2 | Day 7 (W2D1) | ✅ DONE | F-010, F-011, F-013 | 713 → 780 (+67) |
| Week 2 | Day 8 (W2D2) | ✅ DONE | F-012, F-014 | 780 → 866 (+86) |
| Week 2 | Day 9 (W2D3) | ✅ DONE | F-015, F-016, F-017 | 866 → 900 (+34) |
| Week 2 | Day 10 (W2D4) | ✅ DONE | F-018, F-019 | 900 → 976 (+76) |
| Week 2 | Day 11 (W2D5) | ✅ DONE | C5 Phone OTP, S02 Socket.io JWT, G01-G03 gap fixes | 976 → 1062 (+86) |
| Week 2 | Day 12 (W2D6) | ✅ DONE | Admin Panel API + Company Settings (F06) | 1062 → 1091 (+29) |
| Week 2 | Day 13 (W2D7) | ⏳ PENDING | Cross-day integration + loophole check | — |
| Week 3 | Day 14+ | ⏳ NOT STARTED | Celery, Webhook framework, Socket.io JWT (Week 3 roadmap) | — |

**Total Tests: 1091 | Flake8 Errors: 0 | CI: GREEN**

---

## Week 2 Roadmap — 10 Features (F-010 to F-019)

All 10 features built. But gaps remain from spec compliance + infrastructure.

| Feature ID | Title | Day | Status | Notes |
|------------|-------|-----|--------|-------|
| F-010 | User Registration (Email+Password) | Day 7 | ✅ Done | L01-L05 all fixed in Day 8 audit |
| F-011 | Google OAuth Login | Day 7 | ✅ Done | L06-L10 all fixed in Day 8 audit |
| F-012 | Email Verification (Brevo) | Day 8 | ✅ Done | Brevo integration, verification tokens |
| F-013 | Login System | Day 7 | ✅ Done | L11-L15 all fixed in Day 8 audit |
| F-014 | Forgot/Reset Password | Day 8 | ✅ Done | Generic responses (anti-enumeration) |
| F-015 | MFA Setup (TOTP) | Day 9 | ✅ Done | TOTP secret, QR code, 6-digit verify |
| F-016 | Backup Codes | Day 9 | ✅ Done | 10 codes, bcrypt hashed, single-use |
| F-017 | Session Management | Day 9 | ✅ Done | Max 5 sessions, oldest eviction |
| F-018 | Advanced Rate Limiting | Day 10 | ✅ Done (gaps remain) | See Day 10 spec gaps below |
| F-019 | API Key Management | Day 10 | ✅ Done (gaps remain) | See Day 10 spec gaps below |

### Day 10 Spec Gaps — discovered post-build

| # | Severity | Feature | Gap | Spec Requirement |
|---|----------|---------|-----|-----------------|
| G01 | LOW | F-018 | Rate limiter uses `time.time()` (app clock) | Spec says "use Redis server TIME for window calculations" to prevent clock skew |
| G02 | MEDIUM | F-019 | `require_scope` dependency NOT wired into any route | Spec: "Scopes enforced server-side on every request" — dependency exists but never used |
| G03 | MEDIUM | F-019 | Financial approval requires write+approval but no check exists | Spec: "Financial approval requires BOTH write AND approval scope" |

### Infrastructure Gaps — from pre-Week-2 planning

| # | Severity | Gap | Description | Target |
|---|----------|-----|-------------|--------|
| C5 | HIGH | Phone OTP login (Twilio Verify) | `/api/auth/phone/send` + `/api/auth/phone/verify` endpoints. Planned for Day 10 but never built. | Day 11 |
| S02 | HIGH | Socket.io JWT auth middleware | Socket.io `connect` handler reads from `environ` dict but has no real JWT verification. Need to extract + verify JWT token. | Day 11 |
| FP11 | MEDIUM | Audit trail middleware | Auto-log all write operations (POST/PUT/DELETE). Deferred from Week 2. | Week 4+ |
| F06 | LOW | Admin Panel API routes | ✅ DONE: 8 client + 10 admin endpoints, company settings CRUD, team management | Day 12 |
| FP02 | LOW | PaginatedResponse[T] schema | Standardized pagination across all list endpoints. | Week 4+

---

## Day-by-Day Build Log

### Day 7 (Week 2 Day 1) — Authentication Foundation
- **Commit:** `23bf089`
- **Features:** F-010, F-011, F-013
- **Files Created:**
  - `backend/app/core/auth.py` — JWT token creation/verification (HS256)
  - `backend/app/schemas/auth.py` — 8 Pydantic models
  - `backend/app/services/auth_service.py` — Registration, login, refresh, logout, Google OAuth
  - `backend/app/api/auth.py` — 6 endpoints
  - `backend/app/api/deps.py` — FastAPI auth dependencies
  - `tests/unit/test_auth_jwt.py` — 16 tests
  - `tests/unit/test_auth_service.py` — 22 tests
  - `tests/unit/test_auth_api.py` — 29 tests
- **Files Modified:**
  - `database/models/core.py` — Added password_hash, is_active, is_verified, role, mfa columns to User
  - `backend/app/main.py` — Registered auth router
  - `backend/app/middleware/tenant.py` — Bypass /api/auth/ paths
  - `backend/app/middleware/api_key_auth.py` — Skip /api/auth/ paths
  - `tests/conftest.py` — Added StaticPool for SQLite
- **Tests:** 713 → 780 (+67 new)
- **Flake8:** 0 errors
- **Endpoints Built:** 6 (register, login, refresh, google, logout, me)

---

## Day 7 Loophole Audit — F-010, F-011, F-013

### F-010: User Registration — Loopholes Found

| # | Severity | Gap | Spec Requirement | Status |
|---|----------|-----|-----------------|--------|
| L01 | MEDIUM | Missing `confirm_password` field | Body must include `confirm_password` | ❌ Not implemented |
| L02 | HIGH | Missing special char in password validator | "1 special char" required | ❌ Not implemented |
| L03 | LOW | No password strength meter | weak/fair/strong/very strong scoring | ❌ Not implemented |
| L04 | MEDIUM | Missing `GET /api/auth/check-email` endpoint | Returns `{available: true/false}`, 20/IP/min | ❌ Not implemented |
| L05 | LOW | No registration rate limit (5/IP/hour) | Per spec rate limit | ❌ Not implemented |

### F-011: Google OAuth — Loopholes Found

| # | Severity | Gap | Spec Requirement | Status |
|---|----------|-----|-----------------|--------|
| L06 | MEDIUM | Using ID token flow instead of Auth Code + PKCE | Spec says `/google/authorize` + `/google/callback` with code_challenge | ⚠️ Simplified approach |
| L07 | HIGH | Refresh reuse doesn't invalidate ALL tokens | "Refresh reuse → invalidate ALL tokens" | ❌ Only deletes reused token |
| L08 | MEDIUM | Missing `is_new_user` flag in response | Spec response includes `is_new_user` | ❌ Not in AuthResponse |
| L09 | LOW | Google ID token stored in plaintext | OAuthAccount.access_token stores raw id_token | ⚠️ Security concern |
| L10 | LOW | Missing `/api/auth/google/authorize` endpoint | GET endpoint for Google consent redirect | ❌ Not implemented |

### F-013: Login System — Loopholes Found

| # | Severity | Gap | Spec Requirement | Status |
|---|----------|-----|-----------------|--------|
| L11 | HIGH | No progressive lockout (5 failures → 15min lock) | failed_login_count, locked_until, delays 1s/2s/4s/8s | ❌ Not implemented |
| L12 | MEDIUM | No HTTP-only cookies for tokens | `parwa_access` (HTTP-only, Secure, SameSite=Strict) | ❌ Tokens in JSON body |
| L13 | LOW | Missing `plan` claim in JWT | Access token should contain plan | ❌ Not in payload |
| L14 | LOW | No per-account login rate limiting | 20/IP/min + per-account limit | ❌ Not implemented |
| L15 | LOW | User model missing lockout columns | `failed_login_count`, `locked_until`, `last_failed_login_at` | ❌ Not in model |

### Cross-cutting Issues

| # | Severity | Gap | Description |
|---|----------|-----|-------------|
| L16 | LOW | No `nbf` (not-before) claim in JWT | Prevents pre-dated tokens |

---

## Day 8 Loophole Audit — F-012, F-014

All Day 7 loopholes (L01-L16) were fixed. 16/16 closed. Commit: `910f48b`

---

## Day 9 Loophole Audit — F-015, F-016, F-017

No new loopholes found. Commit: `4b2cf60`

---

## Day 10 (Week 2 Day 4) — Advanced Rate Limiting + API Key Management
- **Commit:** pending
- **Features:** F-018, F-019
- **Files Created:**
  - `backend/app/services/rate_limit_service.py` — Per-category rate limiting, progressive backoff
  - `backend/app/services/api_key_service.py` — DB-backed CRUD, rotation, grace period
  - `backend/app/schemas/api_key.py` — Pydantic schemas for API key endpoints
  - `backend/app/api/api_keys.py` — CRUD endpoints (list, create, rotate, revoke)
  - `database/models/api_key_audit.py` — Audit log model for API key events
  - `database/models/core_rate_limit.py` — Rate limit event model
  - `tests/unit/test_rate_limit_service.py` — 35 tests
  - `tests/unit/test_api_key_service.py` — 41 tests
  - `tests/integration/test_api_key_api.py` — Integration tests
- **Files Modified:**
  - `backend/app/middleware/rate_limit.py` — Upgraded to per-category rate limiting
  - `backend/app/middleware/api_key_auth.py` — Upgraded for DB validation, scope enforcement
  - `backend/app/middleware/tenant.py` — Added /test/, /api/mfa/, /api/billing/ to public prefixes; removed X-Company-ID header (L06 fix)
  - `backend/app/main.py` — Registered api_keys router
  - `database/models/core.py` — Added scopes, revoked, revoked_at, rotated_from_id, grace_ends_at, created_by to APIKey
  - `database/models/__init__.py` — Added new models
  - `tests/conftest.py` — Added rate limiter reset fixture
  - `tests/unit/test_health.py` — Updated to not use X-Company-ID header
  - `tests/unit/test_tenant_middleware_deep.py` — Updated for L06 fix
- **Tests:** 900 → 976 (+76 new)
- **Flake8:** 0 errors

---

## Day 10 Loophole Audit — F-018, F-019

| # | Severity | File | Issue | Status |
|---|----------|------|-------|--------|
| L17 | MEDIUM | rate_limit.py | `/api/public/` SKIP_PREFIX bypassed all public rate limits (demo_chat dead code) | ✅ Fixed |
| L18 | HIGH | api_key_service.py | Rotation grace period not enforced — old keys valid forever | ✅ Fixed |
| L19 | LOW | api_key_auth.py | Scope error leaked granted scopes in error message | ✅ Fixed |
| L20 | LOW | api_keys.py | `request: Request = None` should not have default | ✅ Fixed |

All 4 loopholes found and fixed.

### What's DONE correctly ✅
- JWT HS256, 15-min access, 7-day refresh
- SHA-256 hashed refresh tokens in DB
- bcrypt cost 12 password hashing
- Max 5 sessions with oldest eviction
- Token rotation (old deleted on refresh)
- No info leakage on login (same error for wrong email vs wrong password)
- Email lowercased, case-insensitive login
- company_id scoping (BC-001)
- Google audience check + email_verified check
- Auto-create company for Google new users
- Tenant middleware bypass for /api/auth/ paths
- Structured error responses (BC-012)
- 780 tests, 0 flake8 errors

---

## Infrastructure Gaps Tracker Status

### Week 2 Gaps — Updated after Day 10
| ID | Gap | Status | Notes |
|----|-----|--------|-------|
| C3-alt | JWT auth functions | ✅ Done | Day 7 |
| C4 | Brevo email client | ✅ Done | Day 8 |
| C5 | Phone OTP login (Twilio Verify) | ❌ TODO | Day 11 — send OTP + verify OTP endpoints |
| F04 | Google OAuth | ✅ Done | Day 7 |
| F05 | Pydantic schemas directory | ✅ Done | Day 7 |
| F07 | Email template rendering (Jinja2) | ✅ Done | Day 8 |
| S02 | Socket.io JWT auth middleware | ❌ TODO | Day 11 — real JWT verify in connect handler |
| FP11 | Audit trail middleware | ❌ Deferred | Week 4+ |
| `phone` column | Add to users model | ✅ Done | Already exists in core.py |
| requirements.txt | pyotp, qrcode, jinja2, brevo, authlib | ✅ Done | Added in Day 8-9 |

### Day 10 Spec Gaps (G01-G03) — TODO Day 11
| ID | Gap | Status | Notes |
|----|-----|--------|-------|
| G01 | F-018: Use Redis TIME for window calc | ❌ TODO | Low severity, clock skew edge case |
| G02 | F-019: Wire require_scope into routes | ❌ TODO | Medium — scope enforcement not active |
| G03 | F-019: Financial approval dual-scope | ❌ TODO | Medium — write+approval check |
