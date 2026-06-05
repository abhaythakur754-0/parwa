# PARWA Feature Specs — Batch 5

> **Public / Auth / Billing / Onboarding / Integrations**
>
> Features: F-003, F-007, F-011, F-014, F-015, F-016, F-017, F-018, F-019, F-021, F-023, F-024, F-025, F-028, F-030, F-031, F-032
>
> Generated: July 2025 | Version 1.0

---

## Table of Contents

1. [F-003: Live AI Demo Widget (Chat)](#f-003-live-ai-demo-widget-chat)
2. [F-007: ROI Calculator](#f-007-roi-calculator)
3. [F-011: Google OAuth Login](#f-011-google-oauth-login)
4. [F-014: Forgot Password / Reset Password](#f-014-forgot-password--reset-password)
5. [F-015: MFA Setup (Authenticator App)](#f-015-mfa-setup-authenticator-app)
6. [F-016: Backup Codes Generation](#f-016-backup-codes-generation)
7. [F-017: Session Management](#f-017-session-management)
8. [F-018: Rate Limiting (Advanced, Per-User)](#f-018-rate-limiting-advanced-per-user)
9. [F-019: API Key Management](#f-019-api-key-management)
10. [F-021: Subscription Management](#f-021-subscription-management)
11. [F-023: Invoice History](#f-023-invoice-history)
12. [F-024: Daily Overage Charging](#f-024-daily-overage-charging)
13. [F-025: Graceful Cancellation Flow](#f-025-graceful-cancellation-flow)
14. [F-028: Onboarding Wizard (5-Step)](#f-028-onboarding-wizard-5-step)
15. [F-030: Pre-built Integration Setup](#f-030-pre-built-integration-setup)
16. [F-031: Custom Integration Builder](#f-031-custom-integration-builder)
17. [F-032: Knowledge Base Document Upload](#f-032-knowledge-base-document-upload)

---

# F-003: Live AI Demo Widget (Chat)

## Overview

An embedded chat widget on public pages that lets visitors interact directly with a live PARWA AI agent, demonstrating natural language understanding, response quality, and conversation flow without requiring sign-up. The widget enforces a strict 20-message limit per session to prevent abuse while showcasing enough AI capability to drive conversion.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/public/demo/chat` | POST | `{session_id, message, widget_token}` | `{reply, message_count, remaining}` |
| `/api/public/demo/session` | POST | `{}` (creates) | `{session_id, expires_at, message_limit: 20}` |

- **Socket.io Events:** `demo:typing` (listen), `demo:message` (emit) — real-time streaming of AI replies.
- Widget authenticates via a short-lived `widget_token` issued on page load (no user account required).
- All responses route through Smart Router (Light tier) with PII redaction enabled.

## DB Tables

### `demo_sessions`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| session_token | VARCHAR(64) | UNIQUE, indexed — anonymous session identifier |
| message_count | INTEGER | DEFAULT 0, max 20 |
| ip_hash | VARCHAR(64) | Rate-limiting key (SHA-256 of IP) |
| user_agent | TEXT | For analytics |
| created_at | TIMESTAMPTZ | Session start |
| expires_at | TIMESTAMPTZ | 30 minutes from creation |

### `demo_messages`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| demo_session_id | UUID | FK → demo_sessions.id |
| role | VARCHAR(10) | `user` or `assistant` |
| content | TEXT | Message body (PII redacted before storage) |
| model_used | VARCHAR(50) | Which LLM tier handled the response |
| created_at | TIMESTAMPTZ | Timestamp |

## BC Rules

- **BC-007:** All AI responses flow through Smart Router (Light tier). PII redacted before LLM call and before DB storage. Guardrails evaluate every response; blocked responses fall back to safe demo template.
- **BC-005:** Real-time streaming via Socket.io. Events buffered in `event_buffer` for reconnection. No tenant scoping needed (public, unauthenticated).
- **BC-012:** If LLM fails, widget shows "I'm having trouble right now — please try again." No stack traces or raw errors exposed.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Message 21 submitted** | API returns HTTP 403 with `{error: "limit_reached", cta: "Sign up for unlimited access"}` linking to registration. |
| **User submits PII (email, SSN)** | PII redaction engine masks it before LLM submission. Response contains `[REDACTED]` placeholders. |
| **LLM completely unavailable** | Widget displays cached sample Q&A pairs as "suggested conversations" with a note "AI demo temporarily unavailable." |
| **Bot/script abuse (rapid fire)** | IP-hash based rate limit: max 60 messages per 5 minutes per IP. Returns HTTP 429. |

## Acceptance Criteria

1. Given an anonymous visitor opens the widget, When they send a message, Then the AI responds within 3 seconds via Socket.io streaming and the message count increments.
2. Given a visitor has sent 20 messages, When they attempt a 21st, Then the API returns 403 with a sign-up CTA and no further AI calls are made.
3. Given a visitor types a credit card number in the chat, When the message is processed, Then the number is redacted before reaching the LLM and stored as `[REDACTED]` in `demo_messages`.
4. Given Socket.io disconnects mid-conversation, When the client reconnects, Then missed messages are recovered and the session resumes with the correct message count.

---

# F-007: ROI Calculator

## Overview

An interactive calculator widget where prospects input their current support metrics (headcount, avg. ticket cost, volume) and receive a personalized projected ROI breakdown showing estimated monthly and annual savings from adopting PARWA. The calculator uses fixed formulas on the frontend with a server-side validation endpoint to prevent tampering and capture lead data.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/public/roi/calculate` | POST | `{agents, avg_ticket_cost, monthly_tickets, avg_salary}` | `{monthly_savings, annual_savings, roi_percentage, payback_months, ai_resolution_pct}` |
| `/api/public/roi/lead` | POST | `{email, company, roi_snapshot, source}` | `{lead_id, status: "captured"}` |

- Calculation is performed server-side to prevent formula tampering via client-side manipulation.
- When annual savings exceed $50K, the lead capture is mandatory before showing full results.

## DB Tables

### `roi_calculations`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| session_id | VARCHAR(64) | Anonymous session or user ID |
| agents | INTEGER | Number of support agents input |
| avg_ticket_cost | DECIMAL(10,2) | Cost per ticket in USD |
| monthly_tickets | INTEGER | Monthly ticket volume |
| avg_salary | DECIMAL(10,2) | Average agent annual salary |
| monthly_savings | DECIMAL(10,2) | Calculated result |
| annual_savings | DECIMAL(10,2) | Calculated result |
| roi_percentage | DECIMAL(5,2) | ROI percentage |
| created_at | TIMESTAMPTZ | Timestamp |

**All amounts stored as `DECIMAL(10,2)` per BC-002 Rule 3.**

## BC Rules

- **BC-002:** All monetary values stored as DECIMAL(10,2). No floating-point arithmetic. Idempotency is not required (read-only calculation).
- **BC-012:** If calculation formula encounters invalid input (negative values, zeros where division occurs), return structured error with field-level validation messages.
- **BC-001:** Not applicable (public, no tenant context).

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Zero monthly tickets entered** | Return validation error: "Monthly ticket volume must be greater than 0." No division-by-zero in savings formula. |
| **Extremely high agent count (>1000)** | Accept input but flag as "enterprise" tier. ROI formula caps at realistic AI resolution rates. |
| **Client-side formula tampering** | Calculation validated server-side. Results from tampered clients are rejected. Only server-returned values are displayed. |
| **Bot submitting thousands of calculations** | IP-based rate limit: 20 calculations per hour per IP. Returns HTTP 429. |

## Acceptance Criteria

1. Given a visitor inputs 10 agents, $8/ticket, 5000 monthly tickets, and $45K salary, When they submit, Then the server returns monthly and annual savings with ROI percentage, all values using DECIMAL precision.
2. Given a visitor submits 0 for monthly tickets, When the server validates, Then a field-level error is returned for `monthly_tickets` and no calculation is performed.
3. Given the calculated annual savings exceed $50,000, When results are ready, Then the lead capture form appears and full results are withheld until a valid email is submitted.
4. Given a client modifies the frontend JavaScript to inject fake savings, When the results are displayed, Then only server-validated values appear — client-side tampering has no effect.

---

# F-011: Google OAuth Login

## Overview

A single sign-on integration with Google Identity Services allowing users to register or log in using their corporate Google account, auto-populating profile fields and supporting both personal and organizational Google accounts with domain verification. Per BC-011 Rule 2, Google OAuth is the ONLY supported authentication method in v1 — email/password login is not implemented.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/auth/google/authorize` | GET | `{redirect_uri, state, code_challenge}` | Redirects to Google consent screen |
| `/api/auth/google/callback` | POST | `{code, state}` | `{access_token, refresh_token, user, is_new_user, mfa_required}` |
| `/api/auth/token/refresh` | POST | `{refresh_token}` | `{access_token, refresh_token (rotated)}` |
| `/api/auth/logout` | POST | `{}` | `{status: "logged_out"}` |

- OAuth flow uses OpenID Connect with PKCE (`code_challenge`/`code_verifier`) to prevent authorization code interception.
- On callback: if user exists → issue JWT pair; if new user → create account with Google profile data, redirect to onboarding wizard (F-028).
- Access token: 15 min TTL. Refresh token: 7 days TTL with rotation (BC-011 Rule 1).

## DB Tables

### `users`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK → companies.id, NOT NULL, indexed |
| email | VARCHAR(255) | UNIQUE, NOT NULL — from Google profile |
| name | VARCHAR(255) | Full name from Google |
| google_sub | VARCHAR(255) | UNIQUE, indexed — Google subject ID |
| avatar_url | VARCHAR(500) | Google profile picture URL |
| role | VARCHAR(20) | `owner`, `admin`, `agent`, `viewer` |
| mfa_enabled | BOOLEAN | DEFAULT false |
| mfa_secret | VARCHAR(255) | NULLABLE — encrypted TOTP secret |
| created_at | TIMESTAMPTZ | Account creation |

### `refresh_tokens`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NOT NULL |
| token_hash | VARCHAR(64) | SHA-256 hash of refresh token |
| device_info | JSONB | User agent, IP, device type |
| revoked | BOOLEAN | DEFAULT false |
| expires_at | TIMESTAMPTZ | 7 days from issuance |
| created_at | TIMESTAMPTZ | Timestamp |

## BC Rules

- **BC-011:** Access tokens expire in 15 min; refresh tokens in 7 days with rotation. PKCE prevents code interception. Google OAuth is the only auth method (D11). MFA enforced after login.
- **BC-001:** Every query scoped by `company_id`. New user registration creates or joins a company.
- **BC-012:** If Google API is unreachable, return clear error: "Unable to contact Google. Please try again." No stack traces.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Google account email already exists under different company** | Reject login with message: "This email is already registered under a different organization. Contact support." |
| **OAuth callback with expired `state` parameter** | Reject with 403. Re-initiate authorization flow. |
| **New user with Google Workspace domain** | Auto-detect domain; offer to create company matching domain or join existing. |
| **Refresh token reused after rotation** | Immediately invalidate ALL refresh tokens for that user. Force re-authentication. |

## Acceptance Criteria

1. Given a new user clicks "Sign in with Google", When they complete the OAuth consent screen, Then a new user record is created with Google profile data, a JWT pair is issued, and they are redirected to the onboarding wizard.
2. Given an existing user signs in, When the OAuth callback completes, Then the JWT pair is issued, the refresh token is rotated, and the old refresh token is invalidated.
3. Given a user's access token expires after 15 minutes, When a request is made with the expired token, Then the server returns 401 and the client uses the refresh token to obtain a new pair.
4. Given a reused refresh token is submitted, When the server detects it has been rotated, Then ALL refresh tokens for that user are revoked and the user must re-authenticate via Google.

---

# F-014: Forgot Password / Reset Password

## Overview

A self-service account recovery flow for users who have lost access to their Google account or need to reset their session credentials. Since PARWA uses Google OAuth exclusively (BC-011 D11), this feature handles session invalidation and re-authorization rather than traditional password reset. For the limited admin password accounts (if any exist per BC-011 Rule 8), a time-limited email-based reset link is provided via Brevo.

> **Note:** Per BC-011 Rule 2, Google OAuth is the only auth method in v1. This feature primarily handles: (1) "Sign in with a different Google account" flow, and (2) admin password reset for any admin accounts that may have local credentials.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/auth/recover/start` | POST | `{email}` | `{status: "email_sent"}` or `{status: "no_account"}` |
| `/api/auth/recover/verify` | POST | `{token, new_password}` (admin only) | `{status: "reset_success"}` |
| `/api/auth/sessions/invalidate-all` | POST | `{email}` (Brevo-verified) | `{status: "all_sessions_revoked"}` |

- The recovery email is sent via Brevo template (BC-006). Token expires in 15 minutes.
- Upon successful reset, ALL existing sessions and refresh tokens for the user are invalidated (BC-011 Rule 1 — used refresh tokens must be invalidated).
- Generic response: always returns "If an account exists, an email has been sent" to prevent account enumeration.

## DB Tables

### `password_reset_tokens`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NOT NULL |
| token_hash | VARCHAR(64) | SHA-256 of the random token |
| used | BOOLEAN | DEFAULT false — single-use |
| expires_at | TIMESTAMPTZ | 15 minutes from creation |
| ip_address | VARCHAR(45) | Requester IP |
| created_at | TIMESTAMPTZ | Timestamp |

## BC Rules

- **BC-006:** Reset email sent via Brevo template. Rate limited: max 3 reset emails per email address per hour. Logged in `email_logs`.
- **BC-011:** Token is single-use, time-limited (15 min). All existing sessions invalidated on reset. Password hashed with bcrypt (cost factor 12) for admin accounts.
- **BC-012:** If Brevo is unavailable, queue the email via Celery retry. Surface "We couldn't send the email right now. Please try again in a few minutes."

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Non-existent email submitted** | Returns generic success message. No email sent. Prevents account enumeration. |
| **Token reused after successful reset** | Returns 403 "Token already used." No action taken. |
| **Token expired (>15 minutes)** | Returns 410 "Token expired." User must request a new one. |
| **3 reset requests within 1 hour** | Returns 429 "Too many requests. Please wait before requesting another reset email." |

## Acceptance Criteria

1. Given a user submits their registered email, When the server processes the request, Then a reset email is sent via Brevo within 10 seconds and the response is generic regardless of account existence.
2. Given a user clicks the reset link within 15 minutes, When they set a new password, Then the password is hashed with bcrypt, all existing sessions are invalidated, and the token is marked as used.
3. Given a user clicks the reset link after 20 minutes, When the server validates the token, Then a 410 "Token expired" response is returned and no password change occurs.
4. Given a user submits 4 reset requests within 1 hour, When the rate limit triggers, Then the 4th request returns HTTP 429 and no email is sent.

---

# F-015: MFA Setup (Authenticator App)

## Overview

A two-factor authentication enrollment flow that guides users through linking a TOTP-compatible authenticator app (Google Authenticator, Authy, 1Password) by displaying a QR code and verifying a generated code before activating MFA on their account. MFA is enforced for all accounts per BC-011 Rule 3 — users must complete setup before accessing platform features.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/auth/mfa/setup/initiate` | POST | `{}` (authenticated) | `{qr_code_data_url, secret_key, backup_codes}` |
| `/api/auth/mfa/setup/verify` | POST | `{code, temp_secret}` | `{status: "enabled", mfa_enabled: true}` |
| `/api/auth/mfa/verify` | POST | `{code}` (during login) | `{status: "verified"}` |

- `setup/initiate` generates a TOTP secret, returns it as a QR code (data URL) for scanning, and generates 10 backup codes (F-016).
- The secret is stored temporarily in Redis (`parwa:{user_id}:mfa_setup`) until verification.
- `setup/verify` validates a TOTP code against the temporary secret, then promotes it to the permanent `users.mfa_secret` field (AES-256 encrypted at rest).
- During login, after Google OAuth, if `mfa_enabled=true`, the user is prompted for a TOTP code before JWT issuance.

## DB Tables

### `users` (relevant columns — see F-011 for full schema)

| Column | Type | Description |
|--------|------|-------------|
| mfa_enabled | BOOLEAN | DEFAULT false — gates access to platform |
| mfa_secret | VARCHAR(255) | NULLABLE — AES-256 encrypted TOTP secret |
| mfa_enabled_at | TIMESTAMPTZ | NULLABLE — when MFA was activated |

### `backup_codes`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NOT NULL |
| code_hash | VARCHAR(64) | SHA-256 hash of the plaintext code |
| used | BOOLEAN | DEFAULT false |
| created_at | TIMESTAMPTZ | Timestamp |

## BC Rules

- **BC-011:** MFA enforced for all accounts. TOTP is the primary method. Minimum 10 backup codes generated. Secret encrypted at rest (AES-256). Progressive delays on failed MFA attempts (1s, 2s, 4s, 8s, lockout after 5 failures for 15 min).
- **BC-012:** If QR code generation fails, return error with manual entry key as fallback. If TOTP verification fails repeatedly, lock MFA setup and require support contact.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **User loses authenticator device before verification** | Temporary secret in Redis expires after 10 minutes. User re-initiates setup — new QR code and secret generated. |
| **Clock drift on user's device** | Accept TOTP codes within a 30-second window (current + 1 prior + 1 next = 3 valid slots). |
| **User submits 5 incorrect MFA codes during login** | Account locked for 15 minutes. Alert sent via email. All existing sessions preserved. |
| **MFA setup initiated but abandoned** | Redis key expires after 10 minutes. No permanent state change. User can re-initiate anytime. |

## Acceptance Criteria

1. Given an authenticated user initiates MFA setup, When the endpoint returns, Then a QR code data URL, secret key, and 10 backup codes are returned within 1 second.
2. Given the user scans the QR code and enters a valid TOTP code, When verification succeeds, Then `mfa_enabled` is set to true, the secret is encrypted and stored, and the user is informed MFA is active.
3. Given a user enters 5 incorrect MFA codes during login, When the 5th attempt fails, Then the account is locked for 15 minutes and an email alert is sent.
4. Given a user's device clock is 25 seconds behind, When they enter the current TOTP code, Then the code is accepted (within the 30-second tolerance window).

---

# F-016: Backup Codes Generation

## Overview

Upon MFA activation, the system generates and displays a set of 10 single-use backup recovery codes that the user must securely store. Each code can be used exactly once to bypass MFA if the authenticator device is lost or inaccessible. When backup code supply drops below 3, the user is prompted to regenerate.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/auth/mfa/backup-codes/regenerate` | POST | `{mfa_code}` (current TOTP to authorize) | `{backup_codes: [10 codes]}` |
| `/api/auth/mfa/backup-codes/use` | POST | `{code}` (during login) | `{status: "verified", remaining: N}` |

- Regeneration requires a valid current TOTP code (prevents unauthorized regeneration).
- Regeneration invalidates ALL existing backup codes and generates a fresh set of 10.
- Each code is a 10-character alphanumeric string (e.g., `A7K3-M9X2-P4L1`). Stored as SHA-256 hashes — plaintext is shown ONLY once during generation.

## DB Tables

### `backup_codes` (see F-015 for schema)

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NOT NULL, indexed |
| code_hash | VARCHAR(64) | SHA-256 hash — plaintext never stored |
| used | BOOLEAN | DEFAULT false — single-use |
| used_at | TIMESTAMPTZ | NULLABLE — when used |
| created_at | TIMESTAMPTZ | Generation timestamp |

## BC Rules

- **BC-011:** Minimum 10 codes per set. Codes hashed with SHA-256 — plaintext shown exactly once. Single-use enforcement. Backup code authentication triggers mandatory MFA re-setup prompt.
- **BC-012:** If backup code is used successfully, emit a warning notification suggesting the user re-setup MFA and regenerate codes. Log the use event.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **User has only 1 backup code remaining** | Login page shows persistent banner: "You have 1 backup code remaining. Please regenerate your codes after signing in." |
| **Backup code used from a new IP/geo-location** | Accept the code but flag the session as "suspicious" — require MFA re-setup before granting full access. |
| **All 10 backup codes used** | User must contact support for account recovery. Support verifies identity via company owner/admin before manual MFA reset. |
| **User tries to use the same backup code twice** | Second attempt returns "Invalid code" — the code_hash check finds `used=true`. No information leaked about which codes are valid. |

## Acceptance Criteria

1. Given a user activates MFA, When the setup completes, Then exactly 10 backup codes are generated, displayed once, and stored as SHA-256 hashes in `backup_codes`.
2. Given a user uses a backup code during login, When the code is validated, Then the code is marked as `used=true` and the remaining count is returned.
3. Given a user has 2 remaining unused backup codes, When they log in, Then a warning banner prompts them to regenerate codes.
4. Given a user requests code regeneration, When they provide a valid current TOTP code, Then all existing codes are invalidated and 10 new codes are returned.

---

# F-017: Session Management

## Overview

A session governance interface allowing authenticated users to view all currently active sessions across devices and browsers, with the ability to selectively revoke individual sessions or terminate all other sessions for security purposes. Per BC-011 Rule 7, maximum 5 concurrent sessions per user — the oldest is automatically terminated when a 6th is created.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/auth/sessions` | GET | — | `{sessions: [{id, device, ip, last_active, location}]}` |
| `/api/auth/sessions/{session_id}/revoke` | DELETE | `{session_id}` | `{status: "revoked"}` |
| `/api/auth/sessions/revoke-others` | DELETE | — | `{status: "all_other_sessions_revoked", count: N}` |

- Session list shows: device type, browser, IP address (last octet masked), last activity timestamp, and geographic location (city-level).
- The current session cannot be self-revoked via the UI (prevents lockout).
- Revoking a session immediately invalidates its associated refresh token (sets `revoked=true`).

## DB Tables

### `refresh_tokens` (see F-011 for schema — also used as session registry)

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK — serves as session ID |
| user_id | UUID | FK → users.id, NOT NULL |
| token_hash | VARCHAR(64) | SHA-256 hash |
| device_info | JSONB | `{browser, os, device_type, ip}` |
| location | VARCHAR(100) | City/country from geo-IP lookup |
| last_active_at | TIMESTAMPTZ | Updated on each API request |
| revoked | BOOLEAN | DEFAULT false |
| expires_at | TIMESTAMPTZ | 7 days |

## BC Rules

- **BC-011:** Max 5 concurrent sessions. On 6th login, oldest session terminated. Refresh token rotation on every use. Revoked sessions immediately invalidated.
- **BC-001:** Session queries scoped by `user_id` (implicitly via JWT). No cross-user session visibility.
- **BC-012:** If session revocation fails (DB error), the session remains active but an alert is logged. Retry is safe (idempotent operation).

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **User revokes their own current session** | UI disables the "revoke" button for the current session. API rejects self-revocation with 400. |
| **User creates 6th session from new device** | Oldest session automatically terminated. User sees notification: "Your session on [device] was signed out because you reached the 5-session limit." |
| **Stale session still has valid refresh token** | Sessions with no API activity for 7 days expire via `expires_at`. Celery beat task cleans up expired sessions daily. |
| **Revoking a session while it's actively processing a request** | The revocation takes effect on the NEXT request (after current JWT expires in ≤15 min). Immediate termination is best-effort via Redis blacklist. |

## Acceptance Criteria

1. Given a user with 3 active sessions, When they view the session list, Then all 3 sessions are displayed with device info, masked IP, location, and last activity timestamp.
2. Given a user revokes session X, When the next request from session X arrives, Then the server rejects the JWT/refresh token and returns 401.
3. Given a user has 5 sessions and creates a 6th, When the 6th session is established, Then the oldest session is terminated and a notification is shown to the user.
4. Given a user clicks "Sign out all other devices", When the API processes the request, Then all sessions except the current one are revoked and the count is returned.

---

# F-018: Rate Limiting (Advanced, Per-User)

## Overview

A sophisticated, per-user rate limiting system that enforces configurable thresholds on authentication endpoints (login, password reset, MFA verification) and API calls using a Redis-backed sliding window algorithm with progressive backoff and automatic temporary lockouts. Rate limits are differentiated by endpoint sensitivity per BC-011 Rule 6.

## APIs

This is a middleware/system feature — no dedicated user-facing endpoints. Applied via FastAPI middleware.

| Endpoint Category | Limit | Scope | Lockout |
|-------------------|-------|-------|---------|
| `POST /api/auth/*` (login, MFA, reset) | 10 req/min | per email | 15 min after 5 failures |
| `POST /api/auth/recover/*` | 3 req/hour | per email | 1 hour after 3 failures |
| `GET /api/*` (general) | 100 req/min | per IP | 1 min cooldown |
| `POST /api/*` (financial) | 20 req/min | per user account | 5 min cooldown |
| `POST /api/integrations/*` | 60 req/min | per API key | 1 min cooldown |
| `POST /api/public/demo/chat` | 60 req/5min | per IP hash | 5 min cooldown |

- **Implementation:** Redis sorted sets for sliding window (`ZADD` with timestamp scores, `ZREMRANGEBYSCORE` to prune, `ZCARD` to count).
- **Progressive lockout:** 1st failure = no delay, 2nd = 2s delay, 3rd = 4s, 4th = 8s, 5th = lockout (15 min for auth, 5 min for financial).
- **Headers:** `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` on every response.

## DB Tables

### `rate_limit_events`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| key | VARCHAR(255) | Rate limit key (email, IP, user_id, api_key) |
| endpoint_category | VARCHAR(50) | `auth_login`, `auth_mfa`, `auth_reset`, `financial`, `general`, `demo` |
| failure_count | INTEGER | Consecutive failures |
| lockout_until | TIMESTAMPTZ | NULLABLE — when lockout expires |
| last_attempt_at | TIMESTAMPTZ | Timestamp |

## BC Rules

- **BC-011:** Differentiated rate limits per endpoint sensitivity. Per-account limits for financial endpoints. Per-API-key limits for integrations. Progressive lockout with delays.
- **BC-012:** Rate limiter failures (Redis unavailable) default to ALLOW with a warning log. Degraded mode: if Redis is down, fall back to in-memory token bucket (less precise but functional).

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Redis down during rate limit check** | Fail-open: allow the request with warning log. Fall back to in-memory token bucket. |
| **Distributed environment clock skew** | Use Redis server time (not application time) for window calculations. |
| **User rotates IP to bypass rate limit** | Auth endpoints use per-email key, not per-IP. General endpoints use per-IP which is the expected behavior. |
| **Lockout expires while request is in-flight** | Evaluate lockout at request start. If lockout was active, reject even if it technically expired mid-request. |

## Acceptance Criteria

1. Given a user submits 6 login attempts in 1 minute, When the 6th attempt arrives, Then the server returns HTTP 429 with `Retry-After` header and progressive delay is applied.
2. Given 5 failed MFA attempts, When the 5th fails, Then the account is locked for 15 minutes and the response includes `lockout_until` timestamp.
3. Given a user makes 21 financial API calls in 1 minute, When the 21st arrives, Then the server returns 429 and the response includes rate limit headers.
4. Given Redis is unavailable, When a rate limit check is performed, Then the request is allowed (fail-open) and a warning is logged for monitoring.

---

# F-019: API Key Management

## Overview

A key lifecycle management module enabling tenants to create, rotate, and revoke API keys for programmatic access to the PARWA API. Each key carries metadata (name, permissions, expiration) and all key usage is audit-logged per tenant. Per BC-011, keys are scoped with read/write/admin permissions and a separate approval scope for financial actions.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/api-keys` | GET | — | `{keys: [{id, name, scope, created_at, last_used, expires_at}]}` |
| `/api/api-keys` | POST | `{name, scope, expires_days}` | `{key: "parwa_live_xxxx..."} (shown once)` |
| `/api/api-keys/{id}/rotate` | POST | `{}` | `{key: "parwa_live_yyyy..."} (old key valid for 24h)` |
| `/api/api-keys/{id}/revoke` | DELETE | `{}` | `{status: "revoked"}` |

- Key format: `parwa_live_<32-char-random>` or `parwa_test_<32-char-random>`.
- Full key is shown ONLY at creation and rotation. Stored as SHA-256 hash.
- Rotation: old key remains valid for 24-hour grace period to allow migration.
- Scopes: `read`, `write`, `admin`. Financial approval requires BOTH `write` AND `approval` scope.

## DB Tables

### `api_keys`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK → companies.id, NOT NULL, indexed |
| name | VARCHAR(100) | Human-readable label (e.g., "Shopify Integration") |
| key_prefix | VARCHAR(20) | `parwa_live_...` or `parwa_test_...` (for display) |
| key_hash | VARCHAR(64) | SHA-256 hash of full key — plaintext never stored |
| scope | VARCHAR(50) | `read`, `write`, `admin`, `approval` |
| last_used_at | TIMESTAMPTZ | NULLABLE — updated on each API call |
| expires_at | TIMESTAMPTZ | NULLABLE — optional expiration |
| revoked | BOOLEAN | DEFAULT false |
| revoked_at | TIMESTAMPTZ | NULLABLE |
| rotated_from_id | UUID | FK → api_keys.id, NULLABLE — for grace period tracking |
| created_at | TIMESTAMPTZ | Timestamp |

### `api_key_audit_log`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| api_key_id | UUID | FK → api_keys.id |
| company_id | UUID | FK → companies.id |
| action | VARCHAR(20) | `created`, `rotated`, `revoked`, `used` |
| endpoint | VARCHAR(255) | API endpoint called (for `used` action) |
| ip_address | VARCHAR(45) | Caller IP |
| created_at | TIMESTAMPTZ | Timestamp |

## BC Rules

- **BC-011:** Scopes enforced server-side on every request. Read-only keys cannot trigger writes. Financial approval requires explicit `approval` scope. Max 10 keys per tenant.
- **BC-001:** All key operations scoped by `company_id`. Keys from one tenant cannot access another tenant's data.
- **BC-012:** If key creation fails mid-operation (e.g., DB error after hash generated), no partial key is stored. Transaction is atomic.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Tenant attempts to create 11th API key** | Returns 400 "Maximum 10 API keys per tenant. Revoke an existing key first." |
| **Key used after expiration** | Returns 401 "API key expired." No audit log entry for `used` action. |
| **Key used during 24-hour rotation grace period** | Old key still accepted. Audit log records the action against the old key ID. |
| **Admin revokes a key while an integration is actively using it** | Key is immediately rejected on next request. Integration receives 401 with message "Key revoked. Contact your administrator." |

## Acceptance Criteria

1. Given an admin creates a new API key with scope `write`, When the creation succeeds, Then the full key is returned exactly once, stored as a SHA-256 hash, and appears in the key list with `last_used: null`.
2. Given an API key with `read` scope attempts a POST to `/api/tickets`, When the scope is checked, Then the server returns 403 "Insufficient permissions: write scope required."
3. Given an admin rotates an API key, When the rotation completes, Then the new key is returned, the old key remains valid for 24 hours, and both keys appear in the audit log.
4. Given a tenant has 10 API keys and attempts to create an 11th, When the limit is checked, Then the server returns 400 with the limit error message and no key is created.

---

# F-021: Subscription Management

## Overview

A self-service subscription management interface allowing tenants to switch between Starter ($999/mo), Growth ($2,499/mo), and High ($3,999/mo) plans with prorated billing calculations delegated to Paddle's API. Feature entitlements update immediately upon plan change confirmation, and agent deprovisioning/downgrade is scheduled via Celery with appropriate delays.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/billing/subscription` | GET | — | `{plan, status, current_period_end, paddle_subscription_id}` |
| `/api/billing/subscription/change` | POST | `{new_plan, billing_cycle}` | `{paddle_url, proration_preview}` |
| `/api/billing/subscription/cancel` | POST | — | Triggers F-025 cancellation flow |
| `/api/billing/plans` | GET | — | `{plans: [{id, name, price, features, limits}]}` |

- `change` delegates to Paddle's subscription update API for proration calculation.
- Downgrade: access to higher-tier features continues until end of current billing period (Paddle proration). Agent deprovisioning scheduled via Celery.
- Upgrade: new features activated immediately.

## DB Tables

### `subscriptions`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK → companies.id, UNIQUE, NOT NULL |
| paddle_subscription_id | VARCHAR(100) | UNIQUE, indexed — Paddle's subscription ID |
| plan | VARCHAR(20) | `starter`, `growth`, `high` (BC-011 Rule 9) |
| status | VARCHAR(20) | `active`, `canceling`, `canceled`, `past_due` |
| billing_cycle | VARCHAR(10) | `monthly`, `annual` |
| current_period_start | DATE | Period start |
| current_period_end | DATE | Period end |
| ticket_limit | INTEGER | Plan's monthly ticket inclusion |
| created_at | TIMESTAMPTZ | Subscription creation |

## BC Rules

- **BC-002:** All financial amounts in DECIMAL(10,2). Paddle API calls idempotent (check `paddle_event_id`). Atomic transactions — if Paddle fails, DB rolls back. Proration delegated to Paddle. Agent deprovisioning on downgrade scheduled via Celery.
- **BC-009:** Plan changes require confirmation. Downgrade from High to Starter triggers a confirmation dialog showing feature loss and agent count impact.
- **BC-003:** Subscription changes processed via Paddle webhooks (BC-003 rules for HMAC verification, idempotency, async processing).

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Downgrade during active trial** | Trial continues with lower plan features. No proration charge. |
| **Paddle API timeout during plan change** | Transaction rolled back. User sees "Unable to change plan right now. Please try again." No partial state. |
| **Downgrade with 8 agents on Starter (limit 3)** | Confirmation shows: "You have 8 agents. Starter supports 3. 5 agents will be deprovisioned on [date]." Agent deprovisioning scheduled via Celery. |
| **Annual to monthly cycle switch mid-year** | Paddle calculates proration credit. User shown credit amount before confirmation. |

## Acceptance Criteria

1. Given a Growth plan tenant requests upgrade to High, When the change is confirmed, Then Paddle's subscription update API is called, features are activated immediately, and the subscription record updates.
2. Given a High plan tenant requests downgrade to Starter, When the change is confirmed, Then the user sees a proration preview, Paddle handles billing adjustment, and agent deprovisioning is scheduled via Celery for the period end.
3. Given a Paddle API timeout during plan change, When the transaction rolls back, Then no database changes persist and the user sees a retry prompt.
4. Given a tenant switches from annual to monthly billing, When Paddle calculates the proration, Then the credit amount is displayed before confirmation and applied to the next charge.

---

# F-023: Invoice History

## Overview

A paginated, searchable list of all invoices associated with a tenant's account — pulled from Paddle and enriched with local metadata — allowing users to view, download PDF copies, and track payment status for each billing period.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/billing/invoices` | GET | `{page, per_page, status, date_from, date_to}` | `{invoices: [...], pagination: {...}, total}` |
| `/api/billing/invoices/{id}` | GET | — | `{id, amount, status, pdf_url, line_items, paid_at}` |
| `/api/billing/invoices/{id}/pdf` | GET | — | Redirect to Paddle-hosted PDF |

- Invoices are synced from Paddle via webhooks and stored locally for fast querying.
- Paddle webhook `transaction.paid` and `invoice.created` events trigger invoice record creation/update.
- PDFs are hosted by Paddle — PARWA stores the URL and redirects.

## DB Tables

### `invoices`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK → companies.id, NOT NULL, indexed |
| paddle_invoice_id | VARCHAR(100) | UNIQUE — Paddle's invoice ID |
| paddle_transaction_id | VARCHAR(100) | NULLABLE — linked transaction |
| amount | DECIMAL(10,2) | Total amount (BC-002 Rule 3) |
| currency | VARCHAR(3) | `USD`, `EUR`, `GBP` |
| status | VARCHAR(20) | `paid`, `pending`, `failed`, `refunded` |
| pdf_url | VARCHAR(500) | Paddle-hosted PDF URL |
| line_items | JSONB | Invoice line items from Paddle |
| billed_at | DATE | Invoice date |
| paid_at | DATE | NULLABLE — payment date |
| created_at | TIMESTAMPTZ | Local record creation |

## BC Rules

- **BC-002:** Amounts stored as DECIMAL(10,2). Invoice data is financial — all updates logged in audit_trail. Paddle webhook idempotency enforced.
- **BC-001:** Invoice queries scoped by `company_id`. Tenants see only their own invoices.
- **BC-003:** Invoices created/updated via Paddle webhooks — HMAC verification, idempotency via `paddle_invoice_id`, async Celery processing.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Paddle webhook delivers invoice before subscription record exists** | Invoice stored with `company_id` derived from webhook payload. Subscription lookup retried in Celery task. |
| **PDF URL expires (Paddle TTL)** | On PDF access, if Paddle returns 404/410, refresh the URL via Paddle API and update `pdf_url`. |
| **Invoice currency differs from tenant's expected currency** | Display the invoice in its original currency. Note: Paddle handles tax/currency based on tenant location. |
| **Pagination request for page 100 with per_page=100** | Cap at page 50. Return 400 "Maximum page number exceeded. Use date filters to narrow results." |

## Acceptance Criteria

1. Given a tenant with 15 invoices, When they request page 1 with per_page=10, Then the first 10 invoices are returned with pagination metadata showing total count and next page URL.
2. Given a Paddle `invoice.created` webhook arrives, When processed, Then the invoice record is created with amount, currency, status, and PDF URL from Paddle payload.
3. Given a tenant filters invoices by status `paid` and date range `2025-01-01` to `2025-06-30`, When the query executes, Then only matching invoices for that tenant are returned.
4. Given a duplicate webhook for the same `paddle_invoice_id`, When the idempotency check runs, Then the event is skipped and 200 is returned without creating a duplicate invoice record.

---

# F-024: Daily Overage Charging

## Overview

A daily Celery beat cron job that calculates ticket volumes exceeding each tenant's plan inclusion threshold, generates prorated overage charges at $0.10 per additional ticket, and submits the charge to Paddle — with email notification and dashboard visibility. Idempotency is enforced on date + company_id to prevent duplicate charges.

## APIs

No direct user-facing endpoints. Driven by Celery beat schedule.

| Internal Task | Trigger | Key Logic |
|---------------|---------|-----------|
| `calculate_daily_overage` | Celery beat, daily at 02:00 UTC | Count tickets beyond plan limit, charge $0.10 each |
| `GET /api/billing/overages` | REST | Paginated overage charge history |

## DB Tables

### `overage_charges`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK → companies.id, NOT NULL, indexed |
| charge_date | DATE | NOT NULL — the billing date |
| plan_ticket_limit | INTEGER | Plan's monthly inclusion |
| tickets_in_period | INTEGER | Total tickets in current billing period |
| overage_tickets | INTEGER | Tickets beyond limit |
| rate_per_ticket | DECIMAL(5,2) | DEFAULT 0.10 |
| total_amount | DECIMAL(10,2) | `overage_tickets * rate_per_ticket` |
| paddle_charge_id | VARCHAR(100) | NULLABLE — Paddle transaction ID |
| status | VARCHAR(20) | `pending`, `charged`, `failed`, `refunded` |
| UNIQUE constraint | — | `(company_id, charge_date)` — idempotency (BC-002 Rule 7) |

## BC Rules

- **BC-002:** Idempotency on `(company_id, charge_date)` — prevents duplicate daily charges. All amounts as DECIMAL(10,2). Paddle API calls idempotent. Atomic DB transaction. If Paddle fails, DB rolls back. Audit trail logged.
- **BC-004:** Celery task with `max_retries=3`, exponential backoff, `company_id` as first parameter. DLQ for failed tasks. Task logged in `task_logs`.
- **BC-006:** Overage notification email sent via Brevo template when charge exceeds $10. Rate-limited: one email per tenant per day.
- **BC-001:** Ticket count query scoped by `company_id`. Overage records tenant-scoped.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Tenant at exactly the plan limit** | Zero overage. No charge created. Skip to next tenant. |
| **Paddle charge succeeds but webhook never arrives** | Celery task checks charge status via Paddle API after 5 minutes. If confirmed, updates local record. If unknown, retries. |
| **Celery beat fires twice on same day** | UNIQUE constraint on `(company_id, charge_date)` prevents duplicate. Second execution returns `already_charged`. |
| **Tenant's subscription is `canceling` or `canceled`** | Skip overage calculation for non-active subscriptions. Canceled tenants retain access until period end (BC-010 Rule 2) but are not charged overages. |

## Acceptance Criteria

1. Given a Growth tenant (5,000 ticket limit) with 5,200 tickets in the current period, When the daily overage job runs, Then an overage charge of $20.00 (200 tickets × $0.10) is submitted to Paddle.
2. Given the Celery beat fires twice for the same date, When the idempotency check runs, Then the second execution finds the existing record and returns without creating a duplicate charge.
3. Given a Paddle API timeout during charge submission, When the Celery task retries with exponential backoff, Then the DB transaction is rolled back and retried up to 3 times before DLQ routing.
4. Given an overage charge exceeds $10, When the charge succeeds, Then a notification email is sent to the account owner via Brevo with the charge details.

---

# F-025: Graceful Cancellation Flow

## Overview

A multi-step cancellation experience that presents departing users with retention options (pause subscription for 30 days, downgrade to Starter, or accept a 20% discount for 3 months) before confirming cancellation. The flow captures cancellation reasons and feedback to inform product improvements, and all outcomes are tracked for churn analysis.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/billing/cancellation/start` | POST | `{reason, feedback}` | `{status: "retention_offers", offers: [...]}` |
| `/api/billing/cancellation/accept-offer` | POST | `{offer_type}` | `{status: "offer_accepted", subscription_update}` |
| `/api/billing/cancellation/confirm` | POST | `{reason, feedback}` | `{status: "canceling", access_until}` |

- Retention offers presented in sequence: Pause (30 days) → Downgrade (to Starter) → Discount (20% for 3 months) → Cancel.
- Each offer is a Paddle subscription modification or a local status change.
- Cancellation reason categories: `too_expensive`, `missing_features`, `switching_competitor`, `low_volume`, `dissatisfied`, `other`.

## DB Tables

### `cancellation_requests`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK → companies.id, NOT NULL, indexed |
| reason | VARCHAR(50) | Cancellation reason category |
| feedback | TEXT | NULLABLE — free-form feedback |
| retention_offer_presented | TEXT[] | Which offers were shown |
| retention_offer_accepted | VARCHAR(50) | NULLABLE — `pause`, `downgrade`, `discount`, `none` |
| final_outcome | VARCHAR(20) | `retained`, `canceled`, `pending` |
| subscription_id | UUID | FK → subscriptions.id |
| created_at | TIMESTAMPTZ | Request start |
| resolved_at | TIMESTAMPTZ | NULLABLE — when resolved |

## BC Rules

- **BC-002:** All plan changes (pause, downgrade, discount) go through Paddle API with proration. Atomic transactions. Audit trail logged.
- **BC-009:** Retention offers are an implicit approval flow — the user must explicitly choose or reject each offer before cancellation is finalized.
- **BC-010:** Cancellation does NOT immediately terminate access. Subscription remains active until end of paid period (BC-010 Rule 2). Agents deprovisioned within 24 hours of actual termination.
- **BC-006:** Confirmation email sent via Brevo on cancellation (or offer acceptance). Includes access_until date.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **User starts cancellation, accepts pause, then requests cancellation again after pause ends** | New cancellation flow starts. Previous pause recorded. No special handling needed. |
| **User is on annual billing with 8 months remaining** | Cancellation stops auto-renewal. Access continues until annual period end. Pro-rated refund handled by Paddle (if applicable per Paddle's policy). |
| **User selects "downgrade" but is already on Starter** | Downgrade offer is hidden. Only "pause" and "discount" offers shown. |
| **Paddle API fails during offer acceptance** | Transaction rolled back. User stays on current plan. Retry prompt shown. |

## Acceptance Criteria

1. Given a user initiates cancellation with reason `too_expensive`, When the flow starts, Then retention offers (pause, downgrade, discount) are presented in sequence before the cancel option.
2. Given a user accepts the 20% discount offer, When Paddle processes the modification, Then the subscription is updated with the discount and the cancellation request is marked as `retained`.
3. Given a user confirms cancellation after seeing all offers, When the cancellation is processed, Then the subscription status changes to `canceling`, `access_until` is set to the end of the paid period, and a confirmation email is sent.
4. Given a Paddle API failure during offer acceptance, When the transaction rolls back, Then the user's subscription remains unchanged and a retry prompt is displayed.

---

# F-028: Onboarding Wizard (5-Step)

## Overview

A guided, multi-step onboarding wizard that walks new users through platform configuration in five sequential stages — company profile, legal consent (TCPA/GDPR), integration setup, knowledge base upload, and AI activation — with progress tracking and the ability to save and resume. The wizard gates full platform access until all steps are complete.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/onboarding/status` | GET | — | `{current_step, completed_steps, progress_pct}` |
| `/api/onboarding/step/{n}` | POST | `{step_data}` | `{status: "completed", next_step: N+1}` |
| `/api/onboarding/skip` | POST | `{step, reason}` | `{status: "skipped"}` — only for non-critical steps |

- **Steps:** 1) Company Profile (name, industry, size), 2) Legal Consent (F-029), 3) Integration Setup (F-030), 4) Knowledge Base Upload (F-032), 5) AI Activation (F-034).
- Steps 2 (consent) and 5 (AI activation) are mandatory — cannot be skipped.
- Steps 1, 3, 4 can be skipped with a reason, allowing users to access the dashboard but with reduced functionality.

## DB Tables

### `onboarding_progress`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK → companies.id, UNIQUE, NOT NULL |
| current_step | INTEGER | DEFAULT 1 |
| step_1_completed | BOOLEAN | DEFAULT false |
| step_2_completed | BOOLEAN | DEFAULT false — mandatory |
| step_3_completed | BOOLEAN | DEFAULT false |
| step_4_completed | BOOLEAN | DEFAULT false |
| step_5_completed | BOOLEAN | DEFAULT false — mandatory |
| skipped_steps | INTEGER[] | DEFAULT [] — steps skipped with reasons |
| completed_at | TIMESTAMPTZ | NULLABLE — when all mandatory steps done |

## BC Rules

- **BC-008:** Onboarding state is persisted as JSON in the wizard. State schema validated on every update. Progress survives browser refresh and tab close.
- **BC-001:** Onboarding state scoped by `company_id`. Tenant isolation enforced.
- **BC-012:** If a step submission fails (e.g., integration test connectivity fails), the error is surfaced with a retry option. No step is marked complete on failure.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **User closes browser mid-wizard** | Progress auto-saved after each step. On return, wizard resumes at `current_step`. |
| **User skips all optional steps** | Allowed. Dashboard accessible with "limited functionality" banners prompting completion. AI activation (step 5) still requires consent (step 2) and at least one integration. |
| **Integration test fails during step 3** | Step not marked complete. Error shown: "Connection test failed. Check your credentials and try again." User can retry or skip. |
| **User navigates directly to dashboard URL** | If onboarding incomplete, redirect to wizard at `current_step`. If all mandatory steps done, allow access. |

## Acceptance Criteria

1. Given a new user completes step 1 (company profile), When they submit, Then `step_1_completed` is true, `current_step` advances to 2, and the legal consent page is displayed.
2. Given a user skips step 3 (integration setup) with reason "will configure later", When the skip is processed, Then step 3 is added to `skipped_steps` and the wizard advances to step 4.
3. Given a user closes the browser at step 3, When they return to the app, Then the wizard resumes at step 3 with all previous steps marked complete.
4. Given a user tries to access `/dashboard` with step 2 (consent) incomplete, When the middleware checks, Then the user is redirected to step 2 of the wizard.

---

# F-030: Pre-built Integration Setup

## Overview

A selection interface offering one-click configuration of pre-built integrations with popular platforms (Shopify, GitHub, Zendesk, Freshdesk, Slack, Intercom). Each integration provides guided OAuth or API key authorization flows, automatic data sync scheduling, and test connectivity validation before activation.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/integrations/available` | GET | — | `{integrations: [{id, name, icon, category, auth_type}]}` |
| `/api/integrations/{id}/configure` | POST | `{credentials}` | `{status: "testing", test_result}` |
| `/api/integrations/{id}/activate` | POST | `{}` | `{status: "active", sync_schedule}` |
| `/api/integrations/{id}/deactivate` | POST | `{}` | `{status: "inactive"}` |
| `/api/integrations` | GET | — | `{active: [...], status_per_integration}` |

- **Auth types:** OAuth (Shopify, GitHub, Zendesk), API Key (Freshdesk, Slack, Intercom).
- After configuration, a test connectivity call validates credentials before activation.
- Active integrations sync data via Celery beat schedules (configurable per integration).

## DB Tables

### `integrations`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK → companies.id, NOT NULL, indexed |
| integration_type | VARCHAR(50) | `shopify`, `github`, `zendesk`, `freshdesk`, `slack`, `intercom` |
| status | VARCHAR(20) | `configuring`, `active`, `inactive`, `error` |
| credentials_encrypted | TEXT | AES-256 encrypted credentials blob |
| auth_type | VARCHAR(20) | `oauth`, `api_key` |
| oauth_token | TEXT | NULLABLE — encrypted OAuth access token |
| oauth_refresh_token | TEXT | NULLABLE — encrypted refresh token |
| sync_cron | VARCHAR(100) | NULLABLE — Celery beat cron expression |
| last_sync_at | TIMESTAMPTZ | NULLABLE |
| last_error | TEXT | NULLABLE |
| created_at | TIMESTAMPTZ | Timestamp |

## BC Rules

- **BC-003:** Incoming webhooks from integrations (Shopify orders, etc.) follow webhook verification rules — HMAC-SHA256 for Shopify, IP allowlists where applicable, idempotency via `webhook_events` table.
- **BC-004:** Data sync runs as Celery tasks. `company_id` as first parameter. `max_retries=3`, exponential backoff, DLQ for failures.
- **BC-001:** Integration records and all sync data scoped by `company_id`. Cross-tenant webhook delivery prevented.
- **BC-011:** Integration credentials encrypted at rest (AES-256). OAuth tokens stored encrypted. Never exposed in API responses.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **OAuth token expires for Shopify integration** | Refresh token used to obtain new access token. If refresh fails, integration marked as `error` with notification to admin. |
| **Shopify sends 1000 order webhooks in 1 minute** | Rate-limited per BC-003 Rule 11. Excess webhooks queued in Celery. No data loss. |
| **Integration test connectivity succeeds but first sync fails** | Integration activated but `last_error` populated. Retry scheduled via Celery (2s, 4s, 8s). Admin notified after 3 failures. |
| **User activates same integration twice** | Returns 400 "Integration already active. Deactivate and reconfigure to change credentials." |

## Acceptance Criteria

1. Given a user selects Shopify integration, When they complete the OAuth flow, Then the access token is stored encrypted, a test connectivity call succeeds, and the integration status is set to `active`.
2. Given a Shopify integration is active, When an order webhook arrives, Then the HMAC signature is verified, the event is stored in `webhook_events`, and a Celery task processes the order data.
3. Given a user deactivates the GitHub integration, When the deactivation completes, Then the sync schedule is removed, credentials are preserved (for reactivation), and the status is `inactive`.
4. Given an integration's OAuth token expires, When a sync task detects the 401, Then the refresh token is used automatically and the new access token is stored encrypted.

---

# F-031: Custom Integration Builder

## Overview

An advanced integration configuration tool enabling users to define custom data connections using REST APIs, GraphQL endpoints, incoming/outgoing webhooks, or direct database connections — with request/response mapping, authentication setup, and test connectivity validation. This is the "bring your own backend" feature for non-standard integrations.

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/integrations/custom` | POST | `{name, type, config}` | `{integration_id, status: "draft"}` |
| `/api/integrations/custom/{id}/test` | POST | `{test_payload}` | `{status: "success", response_preview, latency_ms}` |
| `/api/integrations/custom/{id}/activate` | POST | `{}` | `{status: "active", endpoint_url}` |
| `/api/integrations/custom/{id}` | PUT | `{config}` | `{status: "updated"}` |
| `/api/integrations/custom/{id}/delete` | DELETE | — | `{status: "deleted"}` |

- **Integration types:** `rest`, `graphql`, `webhook_in`, `webhook_out`, `database`.
- **Config schema per type:**
  - REST/GraphQL: `{url, method, headers, auth_type, auth credentials, request_template, response_mapping}`
  - Webhook In: `{expected_payload_schema, field_mapping, secret}`
  - Webhook Out: `{url, method, headers, trigger_events, payload_template}`
  - Database: `{connection_string (encrypted), query_template, field_mapping}`
- Outgoing webhooks generate a unique PARWA endpoint URL for each integration.
- Max 5 custom integrations per tenant (Growth plan), 20 (High plan).

## DB Tables

### `custom_integrations`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK → companies.id, NOT NULL, indexed |
| name | VARCHAR(100) | User-defined label |
| integration_type | VARCHAR(20) | `rest`, `graphql`, `webhook_in`, `webhook_out`, `database` |
| config_encrypted | TEXT | AES-256 encrypted full config JSON |
| status | VARCHAR(20) | `draft`, `active`, `error`, `disabled` |
| endpoint_url | VARCHAR(255) | NULLABLE — generated for webhook_in |
| last_test_at | TIMESTAMPTZ | NULLABLE |
| last_test_result | JSONB | NULLABLE — test response preview |
| last_sync_at | TIMESTAMPTZ | NULLABLE |
| error_count | INTEGER | DEFAULT 0 — consecutive errors |
| created_at | TIMESTAMPTZ | Timestamp |

## BC Rules

- **BC-003:** Incoming webhooks follow HMAC verification using the integration's `secret`. Outgoing webhooks use standard headers. All events logged in `webhook_events`.
- **BC-004:** Sync/test tasks are Celery tasks with `company_id` first parameter, `max_retries=3`. Timeout: 30 seconds for REST/GraphQL tests, 5 minutes for DB queries.
- **BC-011:** Database connection strings and API credentials encrypted at rest (AES-256). Never exposed in API responses. Outgoing webhook URLs use HTTPS only.
- **BC-001:** All custom integration data scoped by `company_id`. Webhook endpoint URLs include tenant-identifiable prefixes.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Custom REST endpoint returns 500 on test** | Test result shows `{status: "error", response_code: 500, body: "..."}`. Integration stays in `draft`. User can fix config and re-test. |
| **Database query timeout (>5 min)** | Celery task killed by `time_limit`. Integration marked as `error`. Admin alerted. Suggestion to optimize query. |
| **Outgoing webhook destination is unreachable** | Retry 3 times with exponential backoff (2s, 4s, 8s). After 3 failures, mark `error` and notify admin. |
| **User submits SQL injection in database query_template** | Query templates are parameterized — raw SQL execution is prohibited. Only predefined query patterns with bound parameters are allowed. |

## Acceptance Criteria

1. Given a user creates a REST custom integration with URL, auth headers, and response mapping, When they run a test, Then the system makes a test request, returns the response preview with latency, and stores the result.
2. Given a user activates a webhook_in integration, When the unique endpoint URL is generated, Then the URL is returned and the integration is ready to receive external webhook payloads.
3. Given a custom integration has 3 consecutive sync failures, When the error count reaches 3, Then the integration status changes to `error` and an admin notification is sent.
4. Given a Growth plan tenant with 5 active custom integrations, When they attempt to create a 6th, Then the server returns 400 "Custom integration limit reached. Upgrade to High plan for up to 20 integrations."

---

# F-032: Knowledge Base Document Upload

## Overview

A document ingestion interface supporting drag-and-drop upload of knowledge base materials in multiple formats (PDF, DOCX, TXT, Markdown, HTML, CSV) — with chunking previews, duplicate detection, and upload progress tracking per document. Uploaded documents are queued for background processing by F-033 (Knowledge Base Processing & Indexing).

## APIs

| Endpoint | Method | Key Params | Response Summary |
|----------|--------|------------|-----------------|
| `/api/kb/upload` | POST | `multipart/form-data: files[]` | `{documents: [{id, filename, status, size}], upload_id}` |
| `/api/kb/upload/{upload_id}/status` | GET | — | `{documents: [{id, status, progress_pct, chunks_preview}]}` |
| `/api/kb/documents` | GET | `{page, per_page, status, search}` | `{documents: [...], pagination}` |
| `/api/kb/documents/{id}` | DELETE | — | `{status: "deleted"}` |

- **Upload flow:** Client uploads files → server stores in S3 (or local storage) → creates `kb_documents` record with status `uploaded` → Celery task (F-033) picks up for processing.
- **File limits:** Max 50MB per file, 100 files per batch upload. Supported formats: `.pdf`, `.docx`, `.txt`, `.md`, `.html`, `.csv`.
- **Duplicate detection:** SHA-256 hash of file content. If hash exists for the same tenant, flag as duplicate — user can confirm re-upload or skip.

## DB Tables

### `kb_documents`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | PK |
| company_id | UUID | FK → companies.id, NOT NULL, indexed |
| upload_id | UUID | NULLABLE — batch upload grouping |
| filename | VARCHAR(255) | Original filename |
| file_type | VARCHAR(10) | `pdf`, `docx`, `txt`, `md`, `html`, `csv` |
| file_size_bytes | INTEGER | File size in bytes |
| content_hash | VARCHAR(64) | SHA-256 for duplicate detection |
| storage_path | VARCHAR(500) | S3 key or local file path |
| status | VARCHAR(20) | `uploaded`, `processing`, `indexed`, `failed`, `duplicate` |
| chunk_count | INTEGER | NULLABLE — number of chunks after processing |
| error_message | TEXT | NULLABLE — processing failure reason |
| uploaded_by | UUID | FK → users.id |
| created_at | TIMESTAMPTZ | Upload timestamp |
| processed_at | TIMESTAMPTZ | NULLABLE — processing completion |

## BC Rules

- **BC-004:** Document processing runs as Celery tasks. `company_id` first parameter. `max_retries=3`, exponential backoff. DLQ for documents that fail all retries. `soft_time_limit=600` (10 min per document).
- **BC-001:** Documents scoped by `company_id`. Duplicate detection is per-tenant (same document can exist in different tenants).
- **BC-012:** If S3 upload fails, return 503 "Storage service temporarily unavailable." If processing fails, document status set to `failed` with error message. User can retry.
- **BC-010:** PII in uploaded documents is NOT automatically redacted (it's the tenant's own KB). However, the AI agent's PII redaction (BC-007 Rule 5) applies when KB content is used in customer-facing responses.

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **File exceeds 50MB limit** | Reject before upload with 413 "File too large. Maximum size is 50MB." No S3 storage consumed. |
| **Duplicate file uploaded** | Flag as `duplicate` with reference to original document. User prompted: "This file already exists. Upload anyway?" |
| **Corrupted PDF that cannot be parsed** | Processing Celery task marks document as `failed` with error: "Unable to parse PDF. File may be corrupted." User can retry or delete. |
| **100+ files in single batch upload** | Cap at 100 files per batch. Return 400 "Maximum 100 files per upload." User must split into multiple batches. |

## Acceptance Criteria

1. Given a user drags 3 files (PDF, DOCX, TXT) onto the upload area, When the upload completes, Then 3 `kb_documents` records are created with status `uploaded`, file metadata is stored, and files are saved to storage.
2. Given a user uploads a file with the same SHA-256 hash as an existing document, When duplicate detection runs, Then the document is flagged as `duplicate` and the user is prompted to confirm or skip.
3. Given a PDF fails processing due to corruption, When the Celery task exhausts retries, Then the document status is `failed` with an error message and the user sees a "Retry" option in the UI.
4. Given a user uploads a 55MB file, When the server validates the size, Then a 413 error is returned before any storage is consumed and no document record is created.

---

## Summary

| Feature | Category | Key BC Rules | Primary Risk |
|---------|----------|--------------|-------------|
| F-003 | Public | BC-007, BC-005, BC-012 | LLM abuse / PII exposure in demo |
| F-007 | Public | BC-002, BC-012 | Formula tampering / lead data loss |
| F-011 | Auth | BC-011, BC-001, BC-012 | OAuth interception / token theft |
| F-014 | Auth | BC-006, BC-011, BC-012 | Account enumeration / token replay |
| F-015 | Auth | BC-011, BC-012 | MFA bypass / clock drift |
| F-016 | Auth | BC-011, BC-012 | Code exhaustion / replay |
| F-017 | Auth | BC-011, BC-001, BC-012 | Session hijack / lockout |
| F-018 | Auth | BC-011, BC-012 | Brute force / Redis failure |
| F-019 | Auth | BC-011, BC-001, BC-012 | Key leak / scope escalation |
| F-021 | Billing | BC-002, BC-009, BC-003 | Double charge / feature leak |
| F-023 | Billing | BC-002, BC-001, BC-003 | Invoice duplication / cross-tenant leak |
| F-024 | Billing | BC-002, BC-004, BC-006, BC-001 | Double charge / Celery failure |
| F-025 | Billing | BC-002, BC-009, BC-010, BC-006 | Premature termination / lost revenue |
| F-028 | Onboarding | BC-008, BC-001, BC-012 | State loss / skipped consent |
| F-030 | Integration | BC-003, BC-004, BC-001, BC-011 | Fake webhooks / token expiry |
| F-031 | Integration | BC-003, BC-004, BC-011, BC-001 | SQL injection / credential leak |
| F-032 | Onboarding | BC-004, BC-001, BC-012, BC-010 | Storage overflow / processing failure |

---

*End of PARWA Feature Specs — Batch 5*
