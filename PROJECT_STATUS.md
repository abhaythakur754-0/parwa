# PARWA — Project Status Tracker

> Auto-generated. DO NOT modify the 21 source documents in `/documents/`.
> This file tracks build progress, test counts, commits, and per-day completion.

---

## Overall Progress

| Week | Days | Status | Features | Tests |
|------|------|--------|----------|-------|
| Week 1 | Day 1-6 | ✅ DONE | F-001 to F-009 | 713 → 713 |
| Week 2 | Day 7 (W2D1) | ✅ DONE | F-010, F-011, F-013 | 713 → 780 (+67) |
| Week 2 | Day 8 (W2D2) | ⏳ PENDING | F-012, F-014, F-07 | — |
| Week 2 | Day 9 (W2D3) | ⏳ PENDING | F-015, F-016, F-017 | — |
| Week 2 | Day 10 (W2D4) | ⏳ PENDING | C5, F-018 | — |
| Week 2 | Day 11 (W2D5) | ⏳ PENDING | F-019, F-008 | — |
| Week 2 | Day 12 (W2D6) | ⏳ PENDING | Admin Panel API | — |
| Week 2 | Day 13 (W2D7) | ⏳ PENDING | Cross-day integration + loophole check | — |

**Total Tests: 780 | Flake8 Errors: 0 | CI: GREEN**

---

## Week 2 Roadmap — 10 Features (F-010 to F-019)

| Feature ID | Title | Day | Status | Notes |
|------------|-------|-----|--------|-------|
| F-010 | User Registration (Email+Password) | Day 7 | ✅ Done | Missing confirm_password, special char, check-email |
| F-011 | Google OAuth Login | Day 7 | ✅ Done | Uses ID token flow (not auth code PKCE) |
| F-012 | Email Verification (Brevo) | Day 8 | ⏳ Pending | — |
| F-013 | Login System | Day 7 | ✅ Done | Missing progressive lockout, cookies |
| F-014 | Forgot/Reset Password | Day 8 | ⏳ Pending | — |
| F-015 | MFA Setup (TOTP) | Day 9 | ⏳ Pending | — |
| F-016 | Backup Codes | Day 9 | ⏳ Pending | — |
| F-017 | Session Management | Day 9 | ⏳ Pending | — |
| F-018 | Auth Rate Limiting (per-user) | Day 10 | ⏳ Pending | — |
| F-019 | API Key CRUD Endpoints | Day 11 | ⏳ Pending | — |

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

### Week 2 Gaps — Updated after Day 7
| ID | Gap | Status |
|----|-----|--------|
| C3-alt | JWT auth functions | ✅ Done |
| C4 | Brevo email client | ❌ Day 8 |
| C5 | Phone OTP login | ❌ Day 10 |
| F04 | Google OAuth | ✅ Done |
| F05 | Pydantic schemas directory | ✅ Done |
| F07 | Email templates (Jinja2) | ❌ Day 8 |
| S02 | Socket.io JWT middleware | ❌ Later |
| FP11 | Audit trail middleware | ❌ Later |
| `phone` column | Add to users model | ⚠️ Already exists in model |
| requirements.txt | pyotp, qrcode, jinja2, brevo, authlib | ❌ Day 8-9 |
