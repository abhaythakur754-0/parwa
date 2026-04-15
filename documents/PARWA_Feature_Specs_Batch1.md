# PARWA Feature Specs — Batch 1 (Auth & Billing)

> **AI-Powered Customer Support Platform**
>
> Document Version: 1.0 | March 2026
>
> This document contains detailed implementation specifications for 8 critical features in the Auth and Billing domains. Each spec is designed to be complete enough for an AI coding agent to implement without additional questions.

---

## Table of Contents

1. [F-004: Pricing Page with Variant Cards](#f-004-pricing-page-with-variant-cards)
2. [F-010: User Registration (Email + Password)](#f-010-user-registration-email--password)
3. [F-012: Email Verification](#f-012-email-verification)
4. [F-013: Login System](#f-013-login-system)
5. [F-020: Paddle Checkout Integration](#f-020-paddle-checkout-integration)
6. [F-022: Paddle Webhook Handler (All Events)](#f-022-paddle-webhook-handler-all-events)
7. [F-027: Payment Confirmation & Verification](#f-027-payment-confirmation--verification)
8. [F-029: Legal Consent Collection (TCPA, GDPR, Call Recording)](#f-029-legal-consent-collection-tcpa-gdpr-call-recording)

---

# F-004: Pricing Page with Variant Cards

## Overview
A dedicated pricing page displaying three subscription tier cards — Starter ($999/mo), Growth ($2,499/mo), and High ($3,999/mo) — each with a detailed feature comparison matrix, an annual billing toggle with discount, and a CTA to initiate checkout. This is the primary conversion page that translates visitor interest into paying customers.

## User Journey
1. Visitor navigates to `/pricing` from the main navigation or a marketing CTA.
2. The page loads with three tier cards displayed side-by-side (responsive: stacks on mobile).
3. By default, monthly billing is shown. A toggle at the top switches between "Monthly" and "Annual (Save 20%)" views.
4. Each card lists included features with checkmarks, excluded features with "–", and ticket limits.
5. The Growth card is visually highlighted as "Most Popular" with a badge and a slightly elevated design.
6. The High card has a "Premium" badge.
7. Clicking "Get Started" on any card triggers F-020 (Paddle Checkout Integration) by opening the Paddle checkout overlay.
8. If the user is not authenticated, they are redirected to the registration flow first, then returned to pricing with their selected plan pre-selected.

## Frontend Components

| Component | File Path | Description |
|-----------|-----------|-------------|
| `PricingPage` | `src/app/(public)/pricing/page.tsx` | Main pricing page wrapper with SEO metadata and layout |
| `BillingToggle` | `src/components/pricing/BillingToggle.tsx` | Monthly/Annual toggle switch with 20% savings label |
| `PlanCard` | `src/components/pricing/PlanCard.tsx` | Reusable card component rendering a single tier with features, price, and CTA |
| `FeatureMatrix` | `src/components/pricing/FeatureMatrix.tsx` | Detailed comparison table below the cards (rows: features, columns: tiers) |
| `PlanConfig` | `src/config/plans.ts` | Static plan configuration (prices, features, Paddle plan IDs, ticket limits) |

### Plan Configuration Data (`src/config/plans.ts`)

```typescript
export const PLANS = [
  {
    id: "starter",
    name: "Starter",
    paddlePlanId: process.env.NEXT_PUBLIC_PADDLE_STARTER_PLAN_ID,
    monthlyPrice: 999,
    annualPrice: 799, // 20% off
    ticketLimit: 2000,
    badge: null,
    highlight: false,
    features: [
      { name: "AI Ticket Resolution", included: true },
      { name: "Email Channel", included: true },
      { name: "Live Chat Channel", included: true },
      { name: "Knowledge Base (500 docs)", included: true },
      { name: "SMS Channel", included: false },
      { name: "Voice AI Channel", included: false },
      { name: "Smart Router (Light + Medium)", included: true },
      { name: "Approval Queue", included: true },
      { name: "Jarvis Command Center", included: true },
      { name: "Agent Lightning Training", included: false },
      { name: "Custom Integration Builder", included: false },
      { name: "Quality Coach", included: false },
    ],
  },
  {
    id: "growth",
    name: "Growth",
    paddlePlanId: process.env.NEXT_PUBLIC_PADDLE_GROWTH_PLAN_ID,
    monthlyPrice: 2499,
    annualPrice: 1999,
    ticketLimit: 10000,
    badge: "Most Popular",
    highlight: true,
    features: [
      { name: "AI Ticket Resolution", included: true },
      { name: "Email Channel", included: true },
      { name: "Live Chat Channel", included: true },
      { name: "Knowledge Base (2000 docs)", included: true },
      { name: "SMS Channel", included: true },
      { name: "Voice AI Channel", included: false },
      { name: "Smart Router (All Tiers)", included: true },
      { name: "Approval Queue", included: true },
      { name: "Jarvis Command Center", included: true },
      { name: "Agent Lightning Training", included: true },
      { name: "Custom Integration Builder", included: true },
      { name: "Quality Coach", included: false },
    ],
  },
  {
    id: "high",
    name: "High",
    paddlePlanId: process.env.NEXT_PUBLIC_PADDLE_HIGH_PLAN_ID,
    monthlyPrice: 3999,
    annualPrice: 3199,
    ticketLimit: 25000,
    badge: "Premium",
    highlight: false,
    features: [
      { name: "AI Ticket Resolution", included: true },
      { name: "Email Channel", included: true },
      { name: "Live Chat Channel", included: true },
      { name: "Knowledge Base (Unlimited)", included: true },
      { name: "SMS Channel", included: true },
      { name: "Voice AI Channel", included: true },
      { name: "Smart Router (All Tiers)", included: true },
      { name: "Approval Queue", included: true },
      { name: "Jarvis Command Center", included: true },
      { name: "Agent Lightning Training", included: true },
      { name: "Custom Integration Builder", included: true },
      { name: "Quality Coach", included: true },
    ],
  },
];
```

## Backend APIs

No dedicated backend API is required for the pricing page itself. The page reads from the static plan configuration. The checkout CTA triggers the Paddle client-side SDK directly (see F-020).

**Optional: Plan metadata API (for dynamic pricing)**

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/public/plans` |
| **Auth** | None (public endpoint) |
| **Response** | `200 OK` |
| **Body** | `{ "plans": [ { "id": "starter", "name": "Starter", "monthly_price": 999, "annual_price": 799, "ticket_limit": 2000, "features": [...] } ] }` |

This endpoint is useful if plan prices need to be updated without a frontend deployment. In v1, static config is acceptable.

## Database Tables

No new tables required. The pricing page is a static frontend feature. Plan metadata is stored in the `plans` configuration table (if backend API is used):

```sql
CREATE TABLE plans (
    id              VARCHAR(20) PRIMARY KEY,   -- 'starter', 'growth', 'high'
    name            VARCHAR(50) NOT NULL,
    paddle_plan_id  VARCHAR(100) NOT NULL,
    monthly_price   DECIMAL(10,2) NOT NULL,
    annual_price    DECIMAL(10,2) NOT NULL,
    ticket_limit    INTEGER NOT NULL,
    features        JSONB NOT NULL DEFAULT '[]',
    badge           VARCHAR(50),
    sort_order      INTEGER NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Building Codes Applied

| Code | Rules Applied |
|------|--------------|
| **BC-001** | Rule 9 — Tier names must use "starter", "growth", "high" (never legacy names "trivya", "mini", "junior"). |
| **BC-002** | Rule 3 — All financial amounts displayed as DECIMAL(10,2); no floating-point for prices. Annual discount (20%) is applied via integer math: `monthly * 12 * 0.8 / 12`. |
| **BC-012** | Rule 4 — External API calls (Paddle SDK load) wrapped in try/catch with user-friendly error messaging if the Paddle script fails to load. |

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Paddle SDK script fails to load | Show a graceful fallback: "Our payment system is temporarily unavailable. Please try again or contact sales@parwa.ai" with a mailto link. Never show a broken CTA. |
| User selects a plan while on mobile | Cards stack vertically; toggle remains sticky at the top. CTA is full-width on mobile. |
| Annual price calculation produces non-integer | Display as `$1,999/mo` — always round down and absorb any cents. The actual Paddle checkout handles precise amounts. |
| User is already on an active subscription | The CTA text changes from "Get Started" to "Current Plan" (disabled) or "Upgrade"/"Downgrade" if the selected plan differs from their current plan. This requires reading the user's subscription from the session. |
| Plan IDs not set in environment variables | On startup, log a warning. The pricing page renders but CTAs are disabled with "Contact Sales" text. |

## Acceptance Criteria

1. The pricing page loads at `/pricing` with three cards: Starter ($999/mo), Growth ($2,499/mo, highlighted as "Most Popular"), and High ($3,999/mo, "Premium" badge).
2. Toggling to "Annual" billing recalculates all prices to show a 20% discount ($799, $1,999, $3,199 respectively).
3. Each card lists all 12 features with correct included/excluded status per the plan configuration above.
4. Clicking "Get Started" on any card opens the Paddle checkout overlay with the correct plan ID and billing cycle.
5. The page is fully responsive: 3-column on desktop, stacked single-column on mobile with sticky billing toggle.
6. No legacy tier names ("trivya", "mini", "junior") appear anywhere in the rendered HTML, component code, or plan configuration.
7. If the Paddle SDK fails to load, a user-friendly error message is displayed instead of a broken or missing CTA button.

---

# F-010: User Registration (Email + Password)

## Overview
A secure registration flow collecting email, password (with strength validation), company name, and full name — creating a tenant-scoped user account with email uniqueness enforcement, password hashing via bcrypt, and initial `email_verified=false` state tracking. This is the first step of the PARWA customer journey and gates all subsequent authenticated features.

> **⚠️ CONFLICT NOTE:** BC-011 Rule #2 states: "Google OAuth is the ONLY supported authentication method per decision D11. Email/password login MUST NOT be implemented in v1." However, the Feature Catalog (F-010, F-013) defines email/password registration and login as Critical features. **This conflict must be resolved before implementation.** The spec below is written for email/password as cataloged; if D11 takes precedence, this feature becomes F-011 (Google OAuth) with appropriate modifications.

## User Journey
1. User navigates to `/register` from the pricing page CTA or a direct link.
2. The registration form displays fields: Full Name, Email, Company Name, Password, Confirm Password.
3. User fills in all fields. Real-time validation shows:
   - Name: required, min 2 chars
   - Email: valid format, checks availability on blur (debounced API call)
   - Company Name: required, min 2 chars
   - Password: strength meter (weak/fair/strong/very strong) with requirements listed
   - Confirm Password: must match
4. User submits the form. Frontend validates all fields before sending.
5. Backend creates a `companies` record, a `users` record linked to that company, and dispatches an email verification via Celery + Brevo (F-012).
6. User sees a "Check your email" confirmation screen with instructions to verify.
7. User cannot log in or access any authenticated feature until email is verified.

## Frontend Components

| Component | File Path | Description |
|-----------|-----------|-------------|
| `RegisterPage` | `src/app/(public)/register/page.tsx` | Registration page with form and link to login |
| `RegisterForm` | `src/components/auth/RegisterForm.tsx` | Form with validation, password strength meter, and submit handler |
| `PasswordStrength` | `src/components/auth/PasswordStrength.tsx` | Visual strength meter (bar + label) based on password complexity |
| `EmailCheckIndicator` | `src/components/auth/EmailCheckIndicator.tsx` | Shows available/taken status next to email field (debounced) |

### Password Requirements
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number
- At least 1 special character (!@#$%^&*)
- **Strength levels:**
  - Weak: 8 chars, meets only 1-2 requirements
  - Fair: 8+ chars, meets 3 requirements
  - Strong: 8+ chars, meets all 4 requirements
  - Very Strong: 12+ chars, meets all 4 requirements

## Backend APIs

### `POST /api/auth/register`

| Field | Value |
|-------|-------|
| **Method** | POST |
| **Auth** | None (public endpoint) |
| **Rate Limit** | 5 registrations per IP per hour (BC-011 Rule 6) |

**Request Body:**
```json
{
  "full_name": "Jane Doe",
  "email": "jane@company.com",
  "company_name": "Acme Corp",
  "password": "Str0ngP@ss!",
  "confirm_password": "Str0ngP@ss!"
}
```

**Response (201 Created):**
```json
{
  "status": "success",
  "message": "Registration successful. Please check your email to verify your account.",
  "user_id": "usr_a1b2c3d4",
  "company_id": "cmp_x1y2z3w4"
}
```

**Error Cases:**

| HTTP Code | Condition | Response |
|-----------|-----------|----------|
| 400 | Missing required field | `{ "status": "error", "message": "full_name is required", "field": "full_name" }` |
| 400 | Password too weak | `{ "status": "error", "message": "Password does not meet strength requirements", "field": "password", "requirements": ["min 8 chars", "1 uppercase", "1 lowercase", "1 number", "1 special"] }` |
| 400 | Passwords do not match | `{ "status": "error", "message": "Passwords do not match", "field": "confirm_password" }` |
| 409 | Email already registered | `{ "status": "error", "message": "An account with this email already exists", "field": "email" }` |
| 429 | Rate limit exceeded | `{ "status": "error", "message": "Too many registration attempts. Please try again later." }` |
| 500 | Database error or Celery dispatch failure | `{ "status": "error", "message": "Registration failed. Please try again." }` |

### `GET /api/auth/check-email?email={email}`

| Field | Value |
|-------|-------|
| **Method** | GET |
| **Auth** | None |
| **Rate Limit** | 20 requests per IP per minute |
| **Response (200)** | `{ "available": true }` or `{ "available": false }` |

## Database Tables

```sql
CREATE TABLE companies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(100) UNIQUE NOT NULL,  -- generated from name, used in URLs
    plan            VARCHAR(20) NOT NULL DEFAULT 'free',  -- 'free', 'starter', 'growth', 'high'
    paddle_subscription_id  VARCHAR(100),
    paddle_customer_id      VARCHAR(100),
    status          VARCHAR(20) NOT NULL DEFAULT 'trial',  -- 'trial', 'active', 'canceling', 'churned'
    onboarding_step INTEGER NOT NULL DEFAULT 0,  -- 0-5 progress through onboarding wizard
    settings        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_companies_slug ON companies(slug);
CREATE INDEX idx_companies_plan ON companies(plan);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    full_name       VARCHAR(255) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,  -- bcrypt hash, cost factor 12
    email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    role            VARCHAR(20) NOT NULL DEFAULT 'owner',  -- 'owner', 'admin', 'agent', 'viewer'
    mfa_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret      VARCHAR(255),  -- encrypted TOTP secret
    backup_codes    TEXT[],  -- hashed backup codes array
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(email)
);

CREATE INDEX idx_users_company_id ON users(company_id);
CREATE INDEX idx_users_email ON users(email);
```

## Building Codes Applied

| Code | Rules Applied |
|------|--------------|
| **BC-001** | Rules 1, 5, 8 — All queries scoped by company_id. RLS middleware injects tenant filter. Indexes on company_id on users table. |
| **BC-004** | Rules 1, 2, 10 — Email verification Celery task receives company_id as first param. max_retries=3. Task logs start_time/end_time/duration. |
| **BC-010** | Rule 7 — No KYC logic. Only name and email collected at registration. |
| **BC-011** | Rules 1, 7, 8 — Password hashed with bcrypt cost factor 12. Max 5 concurrent sessions per user. Progressive lockout on failed login. **Rule 2 conflict noted above (D11).** |
| **BC-012** | Rule 1 — Circuit breaker on Brevo API call for verification email. Structured error logging on registration failures. |

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| User registers with email already in use | Return 409 with clear message. Do NOT reveal whether an account exists (security best practice) — actually for registration, it's acceptable to say "email taken" to prevent frustration. For login, always say "invalid credentials." |
| Email verification email fails to send | Registration still succeeds. User sees the "check email" screen. A "Resend verification" link is available. Celery retries 3 times. If all fail, DLQ alert fires. |
| Company name slug collision | Auto-append a numeric suffix: `acme-corp-1`, `acme-corp-2`. Check uniqueness in a loop. |
| User submits form with XSS in name | Backend sanitizes all string inputs. Frontend also escapes. Use parameterized SQL queries (SQLAlchemy). |
| Two users register simultaneously with same email | The UNIQUE constraint on users.email causes one to fail with 409. The first writer wins. |
| Password contains the user's email or name | Password strength validator checks for common patterns and penalizes the score, but does NOT reject. Display a warning. |

## Acceptance Criteria

1. A new user can register at `/register` with full name, email, company name, and a password meeting all strength requirements (min 8 chars, uppercase, lowercase, number, special char).
2. On successful registration, a `companies` record and a `users` record are created with the user linked to the company via `company_id`, and `email_verified` is `false`.
3. A verification email is dispatched via Celery + Brevo within 3 seconds of registration (logged in `email_logs` table).
4. The password is stored as a bcrypt hash (cost factor 12), never in plaintext. The raw password never appears in logs.
5. Duplicate email registration returns HTTP 409 with a clear error message.
6. The registration endpoint is rate-limited to 5 requests per IP per hour.
7. The user cannot access any authenticated route or log in until `email_verified` is set to `true` via F-012.

---

# F-012: Email Verification

## Overview
An automated verification flow that sends a time-limited, single-use confirmation link to newly registered users via Brevo, blocking access to all authenticated features until the email is verified. The flow includes a resend capability with rate limiting and token expiration handling (24-hour expiry). This is the gate between registration and the full PARWA experience.

## User Journey
1. After registration (F-010), the user sees a "Check your email" page at `/verify-email`.
2. The page displays the user's email (masked: j***@company.com) and a "Resend email" button.
3. User clicks the verification link in their email (e.g., `https://parwa.ai/verify?token=abc123`).
4. The backend validates the token: checks it exists, is not expired (24h), is not already used, and belongs to the expected user.
5. If valid: `users.email_verified` is set to `true`. User is redirected to `/login` with a flash message "Email verified! You can now log in."
6. If expired: User sees "This link has expired" with a button to request a new one.
7. If already verified: User sees "This email is already verified" with a link to login.
8. Resend is rate-limited to 3 requests per email per hour.

## Frontend Components

| Component | File Path | Description |
|-----------|-----------|-------------|
| `VerifyEmailPage` | `src/app/(public)/verify-email/page.tsx` | Post-registration screen showing "check your email" with resend button |
| `VerifyCallbackPage` | `src/app/(public)/verify/page.tsx` | Handles the token callback: validates, shows success/error state |
| `ResendButton` | `src/components/auth/ResendButton.tsx` | Button with cooldown timer (60s) and rate limit display |

## Backend APIs

### `GET /api/auth/verify?token={token}`

| Field | Value |
|-------|-------|
| **Method** | GET |
| **Auth** | None (public endpoint) |

**Response (200 - Success):**
```json
{
  "status": "success",
  "message": "Email verified successfully. You can now log in.",
  "redirect_to": "/login"
}
```

**Response (200 - Expired):**
```json
{
  "status": "error",
  "message": "This verification link has expired.",
  "error_code": "TOKEN_EXPIRED",
  "can_resend": true
}
```

**Response (200 - Already verified):**
```json
{
  "status": "info",
  "message": "This email is already verified.",
  "redirect_to": "/login"
}
```

**Response (404 - Invalid token):**
```json
{
  "status": "error",
  "message": "Invalid verification link.",
  "error_code": "TOKEN_INVALID"
}
```

### `POST /api/auth/resend-verification`

| Field | Value |
|-------|-------|
| **Method** | POST |
| **Auth** | None |
| **Rate Limit** | 3 requests per email per hour |

**Request Body:**
```json
{
  "email": "jane@company.com"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Verification email sent. Check your inbox.",
  "retry_after": 60
}
```

**Error Cases:**

| HTTP Code | Condition | Response |
|-----------|-----------|----------|
| 400 | Email not provided | `{ "status": "error", "message": "Email is required" }` |
| 404 | No account found with this email | `{ "status": "error", "message": "No account found with this email" }` |
| 409 | Email already verified | `{ "status": "error", "message": "This email is already verified" }` |
| 429 | Rate limit exceeded | `{ "status": "error", "message": "Too many resend requests. Please wait before trying again.", "retry_after_seconds": 3600 }` |

## Database Tables

```sql
CREATE TABLE email_verification_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       VARCHAR(255) UNIQUE NOT NULL,       -- cryptographically secure random token
    used_at     TIMESTAMPTZ,                         -- NULL until used
    expires_at  TIMESTAMPTZ NOT NULL,                -- created_at + 24 hours
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_evt_token ON email_verification_tokens(token);
CREATE INDEX idx_evt_user_id ON email_verification_tokens(user_id);
CREATE INDEX idx_evt_expires_at ON email_verification_tokens(expires_at);
```

**Token generation:** Use `secrets.token_urlsafe(32)` (256-bit entropy). Store the raw token in the database; the URL contains the raw token (not hashed). This is acceptable because verification tokens are single-use and time-limited.

## Building Codes Applied

| Code | Rules Applied |
|------|--------------|
| **BC-004** | Rules 1, 2, 3, 4, 10 — Email sending is a Celery task: `send_verification_email_task(company_id, user_id, token)`. max_retries=3, exponential backoff. Task logs start_time/end_time/duration in task_logs. DLQ on failure with alert. |
| **BC-006** | Rules 4, 5 — Verification email uses Brevo template `tpl_verification_email` (one of the 10 allowed templates). Every send logged in `email_logs` table. |
| **BC-011** | Rule 8 — Verification tokens are single-use. After use, `used_at` is set. Re-using a used token returns "already verified." |
| **BC-012** | Rules 4, 5 — Circuit breaker on Brevo API. Structured JSON error logging if email sending fails. |

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| User clicks verification link after already verifying via a resend | Returns "already verified" message and redirects to login. The second token is marked as used. |
| Token expires before user clicks it | Token `expires_at` is checked. Expired tokens return `TOKEN_EXPIRED`. User can request a new one via resend. |
| User requests multiple verification emails | Each new request creates a new token and invalidates the previous unused one (set `used_at` on old tokens for the same user). Only the latest token is valid. |
| Brevo is down when verification email needs to send | Circuit breaker on Brevo API (BC-012). Celery retries 3 times. If all fail, DLQ alert fires. User can manually click "Resend" later. |
| User registers but never verifies, then tries to register again with same email | The existing account (unverified) is found. Instead of 409, the system re-sends a verification email to the existing account and returns: "An account exists with this email. We've sent a new verification link." |
| Verification link is clicked from a different device/IP | Token validation does not check IP or device. Only checks: token exists, not expired, not used, user exists. This is intentional for usability. |

## Acceptance Criteria

1. After registration, a verification email is sent to the user's email address within 3 seconds via Brevo using template `tpl_verification_email`.
2. Clicking the verification link sets `users.email_verified = true` and redirects the user to `/login` with a success message.
3. A verification token expires after 24 hours. Attempting to use an expired token shows a clear expiration message with a resend option.
4. Each verification token can only be used once. Re-using a used token returns an "already verified" response.
5. The resend endpoint is rate-limited to 3 requests per email per hour. The 4th attempt within the hour returns 429.
6. Requesting a new verification email invalidates all previous unused tokens for that user.
7. If Brevo is unavailable, the email send retries 3 times via Celery with exponential backoff, and a DLQ alert fires if all retries fail.

---

# F-013: Login System

## Overview
The primary authentication endpoint accepting email/password credentials with rate-limited attempts, credential validation against bcrypt-hashed storage, JWT token issuance (access + refresh), and secure cookie-based session establishment with HTTP-only and SameSite flags. This is the gateway to every authenticated feature in PARWA and has 12 downstream feature dependencies.

> **⚠️ CONFLICT NOTE:** BC-011 Rule #2 states Google OAuth is the only supported method per D11. See F-010 conflict note. This spec is written for email/password as cataloged.

## User Journey
1. User navigates to `/login` or is redirected there after attempting to access a protected route.
2. The login form displays fields: Email and Password. A "Forgot password?" link is present.
3. User enters credentials and submits.
4. If credentials are valid AND email is verified:
   - Server issues an access token (JWT, 15-min expiry) and a refresh token (JWT, 7-day expiry).
   - Both tokens are set as HTTP-only, Secure, SameSite=Strict cookies.
   - User is redirected to `/dashboard` (or the originally requested page via `next` query param).
5. If credentials are invalid: show generic "Invalid email or password" message. Increment failed attempt counter.
6. After 5 failed attempts: lock the account for 15 minutes. Show "Account temporarily locked. Try again in X minutes."
7. If email is not verified: show "Please verify your email first" with a resend verification link.
8. If MFA is enabled (post-setup, F-015): after successful credential check, redirect to MFA verification page.

## Frontend Components

| Component | File Path | Description |
|-----------|-----------|-------------|
| `LoginPage` | `src/app/(public)/login/page.tsx` | Login page with form, forgot password link, and Google OAuth button |
| `LoginForm` | `src/components/auth/LoginForm.tsx` | Form with email/password fields, submit handler, loading states |
| `AuthRedirect` | `src/components/auth/AuthRedirect.tsx` | Checks if user is already authenticated and redirects to dashboard |
| `MfaVerifyPage` | `src/app/(auth)/mfa/verify/page.tsx` | MFA code entry page (6-digit input) — gates dashboard after login |

### JWT Token Structure

**Access Token (15 min):**
```json
{
  "sub": "usr_a1b2c3d4",
  "company_id": "cmp_x1y2z3w4",
  "email": "jane@company.com",
  "role": "owner",
  "plan": "growth",
  "token_type": "access",
  "iat": 1709312400,
  "exp": 1709313300
}
```

**Refresh Token (7 days):**
```json
{
  "sub": "usr_a1b2c3d4",
  "company_id": "cmp_x1y2z3w4",
  "token_type": "refresh",
  "jti": "tok_r1s2t3u4",   // unique ID for rotation tracking
  "iat": 1709312400,
  "exp": 1709917200
}
```

## Backend APIs

### `POST /api/auth/login`

| Field | Value |
|-------|-------|
| **Method** | POST |
| **Auth** | None (public endpoint) |
| **Rate Limit** | 20 attempts per IP per minute; per-account progressive lockout |

**Request Body:**
```json
{
  "email": "jane@company.com",
  "password": "Str0ngP@ss!"
}
```

**Response (200 - Success):**
```json
{
  "status": "success",
  "user": {
    "id": "usr_a1b2c3d4",
    "full_name": "Jane Doe",
    "email": "jane@company.com",
    "role": "owner",
    "company_id": "cmp_x1y2z3w4",
    "plan": "growth",
    "email_verified": true,
    "mfa_enabled": false
  },
  "requires_mfa": false
}
```
Cookies set: `parwa_access` (access token), `parwa_refresh` (refresh token).

**Response (200 - MFA Required):**
```json
{
  "status": "success",
  "user": { "id": "usr_a1b2c3d4", "mfa_enabled": true },
  "requires_mfa": true,
  "mfa_token": "mfa_temp_xyz"  // temporary token, valid 5 minutes, for MFA verification step
}
```
Only `parwa_refresh` cookie is set. Access token is issued after MFA verification.

**Error Cases:**

| HTTP Code | Condition | Response |
|-----------|-----------|----------|
| 401 | Invalid credentials | `{ "status": "error", "message": "Invalid email or password" }` |
| 401 | Email not verified | `{ "status": "error", "message": "Please verify your email first", "error_code": "EMAIL_NOT_VERIFIED" }` |
| 401 | Account locked | `{ "status": "error", "message": "Account temporarily locked. Try again in 15 minutes.", "error_code": "ACCOUNT_LOCKED", "lockout_expires_at": "2026-03-01T12:30:00Z" }` |
| 401 | Account deactivated | `{ "status": "error", "message": "This account has been deactivated", "error_code": "ACCOUNT_DEACTIVATED" }` |
| 429 | Rate limit exceeded | `{ "status": "error", "message": "Too many login attempts. Please try again later." }` |

### `POST /api/auth/refresh`

| Field | Value |
|-------|-------|
| **Method** | POST |
| **Auth** | Requires valid refresh token in `parwa_refresh` cookie |

**Response (200):**
```json
{
  "status": "success",
  "access_token": "new_jwt_access_token..."
}
```
Cookies updated: `parwa_access` (new access token), `parwa_refresh` (rotated refresh token). Old refresh token is immediately invalidated.

**Error Cases:**
- 401: Refresh token expired or revoked → `{ "status": "error", "message": "Session expired. Please log in again." }`

### `POST /api/auth/logout`

| Field | Value |
|-------|-------|
| **Method** | POST |
| **Auth** | Requires valid access token |

Clears both `parwa_access` and `parwa_refresh` cookies. Invalidates the refresh token in the database.

**Response (200):**
```json
{
  "status": "success",
  "message": "Logged out successfully"
}
```

## Database Tables

```sql
-- Extend the users table with login tracking fields (alter existing table)
-- These columns are in addition to the F-010 users table schema

ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_failed_login_at TIMESTAMPTZ;

CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    token_jti       VARCHAR(255) UNIQUE NOT NULL,   // JWT ID for rotation
    is_revoked      BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX idx_rt_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_rt_jti ON refresh_tokens(token_jti);
CREATE INDEX idx_rt_expires_at ON refresh_tokens(expires_at);

CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    ip_address      INET,
    user_agent      TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_activity   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_company_id ON sessions(company_id);
CREATE INDEX idx_sessions_active ON sessions(is_active) WHERE is_active = TRUE;
```

## Building Codes Applied

| Code | Rules Applied |
|------|--------------|
| **BC-001** | Rules 1, 5, 8 — All session/refresh token queries scoped by company_id. RLS middleware on all queries. Indexes on company_id. |
| **BC-011** | Rules 1, 7, 8 — Access token expires in 15 min, refresh token in 7 days. Refresh token rotation: old token invalidated immediately on use. Max 5 concurrent sessions — oldest terminated when 6th created. Progressive lockout: 1s, 2s, 4s, 8s delay, then 15-min lockout after 5 failures. |
| **BC-012** | Rule 10 — Health check endpoints (`/health`, `/ready`) do not require authentication. Login page must still render if all backend services are down. |

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| User has 5 active sessions and logs in from a 6th device | The oldest session is terminated: `sessions.is_active = false` for the oldest record. The user on that device gets a 401 on next request. |
| Refresh token is used after being rotated (replay attack) | The `refresh_tokens.is_revoked` check catches this. Return 401. Invalidate ALL refresh tokens for that user (security measure — potential token theft). |
| User's account is locked and they try to log in | Return 401 with `ACCOUNT_LOCKED` code. Frontend shows a countdown timer until `locked_until`. Backend rejects all login attempts until `locked_until < NOW()`. |
| Access token expires mid-request | The auth middleware catches the expired token and returns 401. The frontend automatically calls `/api/auth/refresh` with the refresh token cookie. If refresh succeeds, the original request is retried. If refresh fails, redirect to `/login`. |
| Database is down during login | Return 503 with a generic "Service temporarily unavailable" message. Circuit breaker on DB connection pool (BC-012). Frontend shows a maintenance page. |
| User logs in, then admin deactivates their account | On the next request, the auth middleware checks `users.is_active`. If false, return 401 with `ACCOUNT_DEACTIVATED`. Clear cookies. |
| Brute force attack from multiple IPs on same email | Per-account lockout still applies. Even from different IPs, after 5 failures the account is locked for 15 minutes. |

## Acceptance Criteria

1. A registered, email-verified user can log in with correct email and password, receiving HTTP 200 with user data and both token cookies set.
2. The access token expires in 15 minutes. The refresh token expires in 7 days. Expired tokens return 401.
3. After 5 consecutive failed login attempts, the account is locked for 15 minutes. The 6th attempt (within the lockout window) returns 401 with `ACCOUNT_LOCKED` and the `lockout_expires_at` timestamp.
4. Refresh token rotation works: using a refresh token issues a new access token AND a new refresh token, and the old refresh token is immediately invalidated. Re-using the old refresh token returns 401.
5. Maximum 5 concurrent sessions per user. The 6th login automatically terminates the oldest session.
6. Tokens are set as HTTP-only, Secure, SameSite=Strict cookies. The access token is NOT exposed in the response body.
7. An unverified user attempting to log in receives 401 with `EMAIL_NOT_VERIFIED` error code and is directed to the verification flow.

---

# F-020: Paddle Checkout Integration

## Overview
A tightly integrated checkout experience using Paddle's overlay checkout that initiates subscription purchases from the pricing page, passing plan IDs, tenant metadata, and custom attributes — handling tax calculations and localization automatically via Paddle's built-in capabilities. This is the primary revenue capture mechanism for PARWA.

## User Journey
1. User selects a plan on the pricing page (F-004) and clicks "Get Started."
2. If not authenticated, user is redirected to registration/login flow first. After auth, they return to pricing with `?plan=growth&cycle=monthly` pre-filled.
3. The frontend initializes the Paddle.js SDK (loaded from `https://cdn.paddle.com/paddle/v2/paddle.js`) with the Paddle vendor ID and client token.
4. On button click, `Paddle.Checkout.open()` is called with the plan's Paddle price ID, custom data (company_id, user_id), and success/cancel callback URLs.
5. Paddle's overlay checkout opens with tax calculation, payment method selection, and order summary — all handled by Paddle.
6. User completes payment. Paddle redirects to the success URL: `/checkout/success?session_id={paddle_session_id}`.
7. If the user cancels, Paddle redirects to: `/checkout/cancelled`.
8. The success page (F-027) handles post-payment verification.

## Frontend Components

| Component | File Path | Description |
|-----------|-----------|-------------|
| `PaddleProvider` | `src/providers/PaddleProvider.tsx` | Context provider that initializes Paddle.js SDK on app load |
| `CheckoutButton` | `src/components/billing/CheckoutButton.tsx` | Button component that calls `Paddle.Checkout.open()` with correct params |
| `CheckoutSuccessPage` | `src/app/(auth)/checkout/success/page.tsx` | Post-payment page — calls F-027 verification, then redirects to onboarding |
| `CheckoutCancelledPage` | `src/app/(auth)/checkout/cancelled/page.tsx` | Cancelled checkout — shows "Your checkout was cancelled" with return to pricing link |

### Paddle SDK Initialization

```typescript
// src/providers/PaddleProvider.tsx
import { useEffect } from 'react';

export function PaddleProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const script = document.createElement('script');
      script.src = 'https://cdn.paddle.com/paddle/v2/paddle.js';
      script.async = true;
      script.onload = () => {
        (window as any).Paddle.Setup({
          vendor: parseInt(process.env.NEXT_PUBLIC_PADDLE_VENDOR_ID!),
          token: process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN,
        });
      };
      script.onerror = () => {
        console.error('Failed to load Paddle SDK');
        // Dispatch error event for components to react
        window.dispatchEvent(new CustomEvent('paddle-sdk-error'));
      };
      document.head.appendChild(script);
    }
  }, []);

  return <>{children}</>;
}
```

### Checkout Parameters

```typescript
// When calling Paddle.Checkout.open()
const checkoutParams = {
  items: [{ priceId: plan.paddlePriceId, quantity: 1 }],
  customData: {
    company_id: user.company_id,
    user_id: user.id,
    plan_id: plan.id,       // 'starter', 'growth', 'high'
    billing_cycle: 'monthly' // or 'annual'
  },
  customer: {
    email: user.email,
    name: user.full_name,
  },
  successUrl: `${window.location.origin}/checkout/success?session_id={checkout_id}`,
  cancelUrl: `${window.location.origin}/checkout/cancelled`,
};
```

## Backend APIs

### `POST /api/billing/checkout-url` (Optional — for server-side checkout creation)

| Field | Value |
|-------|-------|
| **Method** | POST |
| **Auth** | Required (valid access token) |
| **Rate Limit** | 10 requests per user per minute |

This endpoint is optional — the frontend can use `Paddle.Checkout.open()` directly. However, a server-side endpoint adds security by not exposing Paddle configuration in the frontend.

**Request Body:**
```json
{
  "plan_id": "growth",
  "billing_cycle": "monthly"
}
```

**Response (200):**
```json
{
  "status": "success",
  "checkout_url": "https://checkout.paddle.com/checkout/xyz...",
  "session_id": "ses_abc123"
}
```

### `GET /api/billing/checkout-status?session_id={id}`

Used by the success page to verify checkout status before calling F-027.

| Field | Value |
|-------|-------|
| **Method** | GET |
| **Auth** | Required |
| **Response (200)** | `{ "status": "completed" }` or `{ "status": "pending" }` |

## Database Tables

No new tables are required for the checkout integration itself. The checkout session data is managed by Paddle. The `companies` table (from F-010) will be updated after successful payment via the webhook handler (F-022):

```sql
-- companies table columns updated after successful checkout:
-- paddle_customer_id  VARCHAR(100)  -- set from Paddle webhook
-- plan                VARCHAR(20)   -- updated to purchased plan
-- status              VARCHAR(20)   -- updated to 'active'
```

## Building Codes Applied

| Code | Rules Applied |
|------|--------------|
| **BC-001** | Rule 5 — All checkout-related API calls scoped by company_id via auth middleware. |
| **BC-002** | Rules 2, 3, 9 — All financial amounts processed by Paddle (never client-side). Idempotency handled by Paddle session IDs. No floating-point monetary math. |
| **BC-003** | Rule 10 — Webhook endpoint responds within 3 seconds. Checkout-related webhooks processed asynchronously. |
| **BC-012** | Rule 4 — Circuit breaker on Paddle SDK initialization. If Paddle CDN is unreachable, fallback UI shows "Payment system unavailable." |

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Paddle SDK fails to load | The `PaddleProvider` dispatches a `paddle-sdk-error` event. All `CheckoutButton` components listen for this and render a fallback: "Payment system temporarily unavailable. Please contact sales@parwa.ai." |
| User has an active subscription and tries to checkout again | The backend checks the user's company subscription status. If already `active`, return 400 with `{ "message": "You already have an active subscription. Visit Settings to manage your plan." }`. Frontend checks this before opening Paddle checkout. |
| User closes the Paddle overlay mid-checkout | Paddle's `cancelUrl` is triggered. The cancelled page is shown with options to retry or return to pricing. No partial state is created in PARWA's database. |
| Paddle returns a checkout error (e.g., card declined) | Paddle handles this within their overlay. PARWA receives no webhook. No database state change occurs. The user can retry within Paddle's checkout. |
| Browser blocks the Paddle popup (popup blocker) | Paddle overlay uses an iframe, not a popup, so popup blockers are not an issue. If the iframe fails to load, the error handler shows the fallback message. |
| Checkout initiated with wrong plan ID | The backend validates the `plan_id` against the `plans` table before creating the checkout URL. Invalid plan IDs return 400. |
| Network drops during checkout | Paddle handles payment processing server-side. If the user's connection drops after payment but before redirect, the webhook (F-022) still fires and updates the database. The success page verifies on load. |

## Acceptance Criteria

1. The Paddle.js SDK initializes on page load without errors, using the vendor ID and client token from environment variables.
2. Clicking "Get Started" on any pricing card opens the Paddle overlay checkout with the correct plan's Paddle price ID and the user's company_id/user_id as custom data.
3. The checkout handles tax calculation and payment method selection entirely within the Paddle overlay — PARWA does not implement any payment UI.
4. If the user is not authenticated when clicking "Get Started," they are redirected to registration/login, and after auth they return to the pricing page with the selected plan pre-filled.
5. Successful checkout redirects to `/checkout/success?session_id={checkout_id}`. Cancelled checkout redirects to `/checkout/cancelled`.
6. If the user already has an active subscription, the checkout CTA is replaced with "Current Plan" (disabled) or "Change Plan" (links to subscription management).
7. If the Paddle SDK fails to load, a user-friendly fallback message is displayed instead of a broken checkout button.

---

# F-022: Paddle Webhook Handler (All Events)

## Overview
A comprehensive, idempotent webhook receiver that processes all Paddle event types — including `subscription.created`, `subscription.updated`, `subscription.cancelled`, `subscription.past_due`, `payment.succeeded`, `payment.failed`, `transaction.created`, and more. Every webhook is HMAC-SHA256 verified, deduplicated, and processed asynchronously via Celery. This is the single most critical backend feature in the billing domain — every financial state change flows through it.

## User Journey (System Journey — no direct user interaction)
1. Paddle sends a webhook POST to `/webhooks/paddle` when any billing event occurs.
2. The FastAPI endpoint receives the raw body, extracts the `paddle-signature` header.
3. HMAC-SHA256 verification: compute signature using `PADDLE_WEBHOOK_SECRET` and compare with constant-time comparison.
4. If invalid: return 403. Log the attempt with IP and payload hash.
5. If valid: extract `event_id` from payload. Check `webhook_events` table for duplicates.
6. If duplicate: return 200 `{ "status": "already_processed" }`.
7. If new: insert into `webhook_events` with `status=pending`, dispatch Celery task `process_paddle_webhook.delay(event_id)`.
8. Return 200 `{ "status": "accepted" }` within 3 seconds.
9. Celery task processes the event based on `event_type`:
   - `subscription.created` → Update company plan, create subscription record
   - `payment.succeeded` → Confirm payment, update subscription status
   - `payment.failed` → Flag subscription as `past_due`, notify user
   - `subscription.cancelled` → Trigger cancellation flow (F-025)
   - `subscription.updated` → Handle plan changes, update entitlements
10. Update `webhook_events.status` to `completed` or `failed` (with `error_message`).

## Frontend Components
None — this is a purely backend feature. No UI is rendered for webhook handling.

## Backend APIs

### `POST /webhooks/paddle`

| Field | Value |
|-------|-------|
| **Method** | POST |
| **Auth** | HMAC-SHA256 signature verification (no JWT/API key) |
| **Rate Limit** | 100 requests per minute per IP (Paddle IPs should be allowlisted) |
| **Response Time** | MUST return 200 within 3 seconds (processing is async) |

**Processing is fully asynchronous — the endpoint only validates, stores, and queues.**

**Paddle Webhook Payload Structure (example):**
```json
{
  "event_id": "evt_01hxyz123456",
  "event_type": "subscription.created",
  "occurred_at": "2026-03-01T12:00:00.000000Z",
  "data": {
    "id": "sub_01habc123",
    "customer_id": "ctm_01hdef456",
    "status": "active",
    "items": [
      {
        "price": {
          "id": "pri_01hghi789",
          "product_id": "pro_01hjkl012"
        },
        "quantity": 1
      }
    ],
    "custom_data": {
      "company_id": "cmp_x1y2z3w4",
      "user_id": "usr_a1b2c3d4",
      "plan_id": "growth",
      "billing_cycle": "monthly"
    },
    "next_billed_at": "2026-04-01T12:00:00.000000Z",
    "current_billing_period": {
      "starts_at": "2026-03-01T12:00:00.000000Z",
      "ends_at": "2026-04-01T12:00:00.000000Z"
    }
  },
  "notification_origin": "api"
}
```

**Response (200 - New Event):**
```json
{
  "status": "accepted"
}
```

**Response (200 - Duplicate):**
```json
{
  "status": "already_processed"
}
```

**Response (403 - Invalid Signature):**
```json
{
  "status": "error",
  "message": "Invalid signature"
}
```

### Supported Event Types and Their Handlers

| Event Type | Handler Action |
|------------|---------------|
| `subscription.created` | Create subscription record, update company plan to `active`, store `paddle_subscription_id` and `paddle_customer_id` on company, trigger welcome email (F-027) |
| `subscription.updated` | Update subscription status, handle plan changes (upgrade/downgrade), update company plan if tier changed, trigger entitlement update |
| `subscription.cancelled` | Set subscription status to `canceling`, trigger cancellation flow (F-025), schedule agent deprovisioning via Celery |
| `subscription.past_due` | Flag subscription as `past_due`, send payment failure notification email, start grace period countdown |
| `subscription.paused` | Set company status to `paused`, pause AI processing, disable ticket creation |
| `subscription.resumed` | Set company status to `active`, resume AI processing |
| `payment.succeeded` | Confirm payment, update subscription `current_period_end`, log in `audit_trail`, trigger confirmation email |
| `payment.failed` | Flag payment failure, increment retry counter, notify user, update subscription to `past_due` if applicable |
| `transaction.completed` | Log transaction in `transactions` table, update billing dashboard data |

## Database Tables

```sql
CREATE TABLE webhook_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        VARCHAR(20) NOT NULL,        -- 'paddle', 'brevo', 'twilio', 'shopify'
    event_id        VARCHAR(255) NOT NULL,        -- provider-specific event ID
    event_type      VARCHAR(100) NOT NULL,        -- 'subscription.created', 'payment.succeeded', etc.
    payload         JSONB NOT NULL,               -- raw webhook payload
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    processing_attempts INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ,
    UNIQUE(provider, event_id)                    -- prevents duplicate processing
);

CREATE INDEX idx_we_provider_status ON webhook_events(provider, status);
CREATE INDEX idx_we_event_type ON webhook_events(event_type);
CREATE INDEX idx_we_created_at ON webhook_events(created_at);

CREATE TABLE subscriptions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id              UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    paddle_subscription_id  VARCHAR(100) UNIQUE,
    paddle_customer_id      VARCHAR(100),
    plan                    VARCHAR(20) NOT NULL,           -- 'starter', 'growth', 'high'
    billing_cycle           VARCHAR(10) NOT NULL DEFAULT 'monthly',  -- 'monthly', 'annual'
    status                  VARCHAR(20) NOT NULL,           -- 'active', 'past_due', 'canceling', 'cancelled', 'paused'
    current_period_start    TIMESTAMPTZ,
    current_period_end      TIMESTAMPTZ,
    next_billing_date       TIMESTAMPTZ,
    cancelled_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sub_company_id ON subscriptions(company_id);
CREATE INDEX idx_sub_paddle_id ON subscriptions(paddle_subscription_id);
CREATE INDEX idx_sub_status ON subscriptions(status);

CREATE TABLE transactions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    subscription_id     UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    paddle_transaction_id VARCHAR(100) UNIQUE,
    paddle_event_id     VARCHAR(255),             -- links back to webhook_events
    amount              DECIMAL(10,2) NOT NULL,
    currency            VARCHAR(3) NOT NULL DEFAULT 'USD',
    status              VARCHAR(20) NOT NULL,     -- 'completed', 'failed', 'refunded'
    transaction_type    VARCHAR(20) NOT NULL,     -- 'subscription', 'overage', 'one_time'
    description         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_txn_company_id ON transactions(company_id);
CREATE INDEX idx_txn_subscription_id ON transactions(subscription_id);
CREATE INDEX idx_txn_created_at ON transactions(created_at);
```

## Building Codes Applied

| Code | Rules Applied |
|------|--------------|
| **BC-002** | Rules 2, 5, 8, 9 — Idempotency via UNIQUE constraint on `(provider, event_id)`. All financial DB updates in atomic transactions. Audit trail logged for every financial action. Paddle webhook double-fire prevented. |
| **BC-003** | Rules 1-11 (ALL) — HMAC-SHA256 verification with constant-time comparison. Idempotency check before processing. Async processing via Celery. Retry 3x with exponential backoff (60s, 300s, 900s). Webhook logged in `webhook_events`. Response within 3 seconds. Rate limiting on endpoint. |
| **BC-004** | Rules 1, 2, 3, 4, 5, 10 — Celery task `process_paddle_webhook(company_id, event_id)` receives company_id as first param. max_retries=3. 300s timeout. DLQ on exhaustion. DLQ alert to ops team. Task logs start/end/duration. |
| **BC-012** | Rule 5 — All webhook processing errors logged in structured JSON format with timestamp, event_type, error_message, and payload hash. |

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Paddle sends the same webhook twice (network retry) | The UNIQUE constraint on `(provider, event_id)` prevents duplicate insertion. The endpoint returns `already_processed`. No side effects. |
| Webhook arrives before the user's registration is complete | The `custom_data.company_id` may not exist yet. The Celery task checks if the company exists. If not, it retries in 60s (up to 3 times). If still not found, marks event as `failed` with error "Company not found" and alerts ops. |
| Webhook payload has unexpected schema | The Celery task validates the payload structure against a Pydantic model. If validation fails, the task marks the event as `failed` with the validation error. The raw payload is preserved in `webhook_events.payload` for debugging. |
| Multiple webhooks arrive out of order (e.g., `payment.succeeded` before `subscription.created`) | Each handler is idempotent and tolerant of ordering. `subscription.created` creates the subscription record. `payment.succeeded` upserts the transaction. If `payment.succeeded` arrives first and no subscription exists, it creates a pending transaction and the subscription handler fills in the reference later. |
| Paddle webhook secret is rotated | Store webhook secrets with version numbers. When a new secret is deployed, accept signatures from both the old and new secret for a 24-hour overlap period. |
| Database is down when a webhook arrives | The endpoint still validates the signature and returns 200. The `webhook_events` insert fails and is retried by Celery. If the DB is down for extended period, events queue in Redis and are processed when DB recovers. |
| A `subscription.cancelled` event arrives for a company that was already cancelled | Idempotency: the handler checks the current subscription status. If already `cancelled`, it no-ops and marks the event as `completed`. |

## Acceptance Criteria

1. The webhook endpoint at `/webhooks/paddle` validates HMAC-SHA256 signatures using `PADDLE_WEBHOOK_SECRET` with constant-time comparison. Invalid signatures return 403.
2. Duplicate webhooks (same `event_id`) are detected via the UNIQUE constraint and return 200 `{ "status": "already_processed" }` without re-executing any side effects.
3. The endpoint returns 200 within 3 seconds for every request, regardless of processing complexity. All processing is deferred to a Celery task.
4. A `subscription.created` event creates a `subscriptions` record, updates the company's `plan` and `status`, and stores the `paddle_subscription_id` and `paddle_customer_id`.
5. A `payment.succeeded` event creates a `transactions` record and logs the action in the `audit_trail` table.
6. Failed webhook processing retries 3 times with exponential backoff (60s, 300s, 900s). After all retries fail, the event is marked `failed` and an alert is sent to the operations team.
7. Every webhook is logged in the `webhook_events` table with provider, event_id, event_type, full payload, status, and timestamps.

---

# F-027: Payment Confirmation & Verification

## Overview
A post-checkout verification flow that confirms successful payment processing with Paddle, updates tenant entitlements and plan status in the local database, sends a welcome/confirmation email via Brevo, and redirects the user to the onboarding wizard. This feature bridges the gap between Paddle's checkout completion and the user's first authenticated experience in PARWA.

## User Journey
1. User completes Paddle checkout and is redirected to `/checkout/success?session_id={checkout_id}`.
2. The success page loads and calls `GET /api/billing/verify-checkout?session_id={checkout_id}`.
3. The backend checks if the webhook for this session has been processed (event in `webhook_events` with `status=completed`).
4. **If processed:** Return the company's updated plan and status. Frontend redirects to `/onboarding` (step based on `companies.onboarding_step`).
5. **If pending:** Return `{ "status": "processing" }`. Frontend polls every 3 seconds (max 60 seconds) until the webhook is processed.
6. **If failed:** Return `{ "status": "failed" }`. Frontend shows an error with a "Contact Support" option.
7. After verification, a welcome email is sent via Brevo (template: `tpl_welcome_email`) containing the plan details, next steps, and a link to the onboarding wizard.
8. The company's `onboarding_step` is set to 0 (beginning of the 5-step onboarding wizard, F-028).

## Frontend Components

| Component | File Path | Description |
|-----------|-----------|-------------|
| `CheckoutSuccessPage` | `src/app/(auth)/checkout/success/page.tsx` | Polling-based verification page with spinner, success animation, and redirect |
| `CheckoutVerification` | `src/components/billing/CheckoutVerification.tsx` | Polling logic: calls verify endpoint every 3s, max 60s, handles success/failure/timeout |
| `WelcomeBanner` | `src/components/onboarding/WelcomeBanner.tsx` | Shown briefly on first onboarding page load after successful checkout |

### Checkout Verification Polling Logic

```typescript
// src/components/billing/CheckoutVerification.tsx
const MAX_POLL_ATTEMPTS = 20;   // 20 * 3s = 60 seconds
const POLL_INTERVAL = 3000;     // 3 seconds

async function pollCheckoutStatus(sessionId: string): Promise<VerifyResult> {
  for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt++) {
    const response = await fetch(`/api/billing/verify-checkout?session_id=${sessionId}`);
    const data = await response.json();

    if (data.status === 'completed') return data;
    if (data.status === 'failed') throw new Error('Checkout failed');
    if (data.status === 'processing') {
      await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
      continue;
    }
  }
  throw new Error('Verification timeout — please check your email for confirmation.');
}
```

## Backend APIs

### `GET /api/billing/verify-checkout?session_id={session_id}`

| Field | Value |
|-------|-------|
| **Method** | GET |
| **Auth** | Required (valid access token) |
| **Rate Limit** | 30 requests per user per minute |

**Response (200 - Completed):**
```json
{
  "status": "completed",
  "company": {
    "id": "cmp_x1y2z3w4",
    "name": "Acme Corp",
    "plan": "growth",
    "billing_cycle": "monthly",
    "current_period_end": "2026-04-01T12:00:00Z"
  },
  "redirect_to": "/onboarding"
}
```

**Response (200 - Processing):**
```json
{
  "status": "processing",
  "message": "Payment is being verified. Please wait..."
}
```

**Response (200 - Failed):**
```json
{
  "status": "failed",
  "message": "Payment verification failed. Please contact support.",
  "error_code": "CHECKOUT_FAILED"
}
```

**Error Cases:**

| HTTP Code | Condition | Response |
|-----------|-----------|----------|
| 400 | Missing session_id | `{ "status": "error", "message": "session_id is required" }` |
| 404 | Session not found | `{ "status": "error", "message": "Checkout session not found" }` |
| 403 | Session belongs to different company | `{ "status": "error", "message": "Unauthorized" }` |
| 429 | Rate limit exceeded | `{ "status": "error", "message": "Too many verification attempts" }` |

### `POST /api/billing/welcome-email` (Internal — called by webhook handler)

| Field | Value |
|-------|-------|
| **Method** | POST |
| **Auth** | Internal (service-to-service, no user JWT) |
| **Caller** | `process_paddle_webhook` Celery task, after `subscription.created` |

**Request Body:**
```json
{
  "company_id": "cmp_x1y2z3w4",
  "user_id": "usr_a1b2c3d4",
  "plan": "growth",
  "billing_cycle": "monthly"
}
```

**Response (200):**
```json
{
  "status": "queued",
  "task_id": "celery_task_uuid"
}
```

This endpoint dispatches a Celery task to send the welcome email via Brevo.

## Database Tables

No new tables. This feature reads from and updates existing tables:

- **`webhook_events`** — Checks for completed webhook with matching `session_id` in payload
- **`companies`** — Reads `plan`, `status`, `onboarding_step`; updates `onboarding_step` to 0
- **`subscriptions`** — Reads subscription details for confirmation display
- **`transactions`** — Reads payment amount and date for confirmation

**Company state after successful verification:**
```sql
UPDATE companies
SET plan = 'growth',
    status = 'active',
    onboarding_step = 0
WHERE id = 'cmp_x1y2z3w4';
```

## Building Codes Applied

| Code | Rules Applied |
|------|--------------|
| **BC-001** | Rules 1, 4 — Verification query scoped by `company_id`. Cross-tenant session check: verify the session's `custom_data.company_id` matches the authenticated user's company. |
| **BC-002** | Rules 5, 8 — Plan update wrapped in atomic transaction with audit trail logging. All financial state changes are auditable. |
| **BC-004** | Rules 1, 2, 3, 10 — Welcome email sent via Celery task: `send_welcome_email_task(company_id, user_id, plan)`. company_id as first param. max_retries=3. 300s timeout. Task logged. |
| **BC-006** | Rules 4, 5 — Welcome email uses Brevo template `tpl_welcome_email`. Logged in `email_logs` with template_used, recipient, status. |
| **BC-012** | Rules 4, 5 — Circuit breaker on Brevo API. Structured error logging if verification or email fails. |

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| User closes the success page before verification completes | The webhook still processes in the background. When the user next logs in, the system checks their subscription status. If active, they are redirected to onboarding. No data loss. |
| Webhook is delayed (Paddle sends it 30+ seconds after checkout) | The polling mechanism handles this: it polls for up to 60 seconds. If the webhook arrives within that window, verification succeeds. If not, the user sees a timeout message with "Check your email for confirmation." The welcome email is still sent when the webhook eventually processes. |
| User tries to access `/checkout/success` directly (without a real checkout) | If no `session_id` is provided, redirect to `/pricing`. If `session_id` doesn't match any webhook event, return 404. |
| Payment succeeded but webhook processing failed (all Celery retries exhausted) | The `webhook_events` record is marked `failed`. The verification endpoint returns `failed`. The user sees an error message with a "Contact Support" button. The ops team is alerted via DLQ. Manual webhook replay can be triggered from the admin panel. |
| User upgrades plan — second successful checkout | The verification page shows plan upgrade confirmation. The webhook handler (F-022) updates the subscription. Onboarding step is NOT reset (user has already onboarded). |
| Paddle reports payment succeeded but later reverses it (chargeback) | This arrives as a separate webhook event (`transaction.payment_refunded`). The webhook handler updates the transaction status to `refunded` and flags the subscription. The user's access continues until the next billing period, per BC-010 Rule 2. |

## Acceptance Criteria

1. After Paddle checkout completion, the success page polls the verification endpoint every 3 seconds until the webhook is confirmed as processed (max 60 seconds).
2. On successful verification, the company's `plan` and `status` are updated in the database, and the user is redirected to `/onboarding`.
3. A welcome email is sent via Brevo template `tpl_welcome_email` within 5 seconds of webhook processing, containing the plan details and onboarding link.
4. The verification endpoint rejects requests where the session's `company_id` does not match the authenticated user's company (returns 403).
5. If webhook processing fails (after all retries), the verification returns `failed` status, and the user sees an error with a "Contact Support" option.
6. If the user navigates away from the success page before verification, their subscription is still activated (via webhook), and they can access the dashboard on next login.
7. The welcome email send is logged in the `email_logs` table with the correct template ID, recipient, and status.

---

# F-029: Legal Consent Collection (TCPA, GDPR, Call Recording)

## Overview
A consent management step within the onboarding wizard (F-028, Step 2) that presents and collects explicit opt-in for TCPA compliance, GDPR data processing agreement, and call recording permissions. Each consent is stored as an individual, timestamped, IP-addressed record with the full consent text version — creating an audit-ready legal trail. This is a Critical feature because PARWA cannot process any customer data or enable voice features without proper consent.

## User Journey
1. User is in the onboarding wizard (F-028) at Step 2: "Legal & Compliance."
2. The page displays three consent sections, each with:
   - A clear heading and brief plain-language explanation
   - A "Read full policy" expandable link (opens policy text in a modal)
   - A checkbox with explicit opt-in text (e.g., "I consent to automated SMS messages per TCPA regulations")
   - The current date and user's IP address displayed for transparency
3. The three consent sections are:
   - **TCPA Consent:** Required for SMS and voice features. Text covers automated communications, consent to receive SMS/calls, opt-out instructions.
   - **GDPR Data Processing Agreement:** Required for all EU users (auto-detected from IP or company address). Covers data controller/processor relationship, data retention, data subject rights. Non-EU users see a simplified privacy consent.
   - **Call Recording Consent:** Required for voice AI features. Covers recording of customer calls, storage, access controls, retention period.
4. User must check all applicable consent boxes. The "Continue" button is disabled until all required consents are accepted.
5. On clicking "Continue," the backend stores each consent as an individual record with:
   - `consent_type`: 'tcpa', 'gdpr', 'call_recording'
   - `consent_text`: Full text of the consent at the time of acceptance (versioned)
   - `consented_at`: Timestamp
   - `ip_address`: User's IP
   - `user_agent`: Browser user agent
6. The company's `onboarding_step` is updated to 3.
7. A confirmation email with all accepted consent texts is sent to the user for their records.

## Frontend Components

| Component | File Path | Description |
|-----------|-----------|-------------|
| `ConsentStep` | `src/components/onboarding/steps/ConsentStep.tsx` | Step 2 of onboarding wizard — renders all consent sections |
| `ConsentCard` | `src/components/legal/ConsentCard.tsx` | Reusable card for a single consent section (title, description, checkbox) |
| `PolicyModal` | `src/components/legal/PolicyModal.tsx` | Full-screen modal displaying the complete policy text for a consent type |
| `ConsentSummary` | `src/components/legal/ConsentSummary.tsx` | Summary of all collected consents with timestamps (viewable in Settings later) |

### Consent Text Templates

**TCPA Consent Text:**
```
By checking this box, I consent to receive automated text messages (SMS) and
pre-recorded or artificial voice messages at the phone number(s) I have provided
from PARWA AI ("Company") and its affiliates. I understand that consent is not a
condition of purchasing any goods or services. Message and data rates may apply.
I can revoke this consent at any time by texting STOP to the originating number,
contacting support@parwa.ai, or updating my account settings. For more information,
see our TCPA Policy at https://parwa.ai/legal/tcpa.

This consent was given on [DATE] from IP [IP_ADDRESS].
```

**GDPR Data Processing Text:**
```
By checking this box, I acknowledge and agree that PARWA AI acts as a Data Processor
on behalf of my company (the Data Controller) for the processing of personal data
included in customer support interactions (names, email addresses, phone numbers,
communication content, and related metadata). PARWA AI processes this data solely
for the purpose of providing AI-powered customer support services as described in
our Data Processing Agreement (DPA) at https://parwa.ai/legal/dpa.

I confirm that my company has the legal basis to share this personal data with
PARWA AI and that appropriate data protection impact assessments have been
conducted where required under Article 35 of the GDPR.

Data retention: Personal data is retained for the duration of the subscription
plus 30 days, except for audit trail records retained for 5 years per applicable
regulations. For data export or deletion requests, contact privacy@parwa.ai.

This consent was given on [DATE] from IP [IP_ADDRESS].
```

**Call Recording Consent Text:**
```
By checking this box, I consent to the recording of phone calls processed through
PARWA AI's voice support features. Recordings are stored securely with AES-256
encryption, accessible only to authorized personnel of my company, and retained
for a period of 90 days unless a longer retention period is required by applicable
law. Recordings may be used for quality assurance, training of AI models (with PII
redacted), and dispute resolution.

I understand that callers will be notified of call recording via a pre-call
announcement. I am responsible for ensuring compliance with applicable call
recording laws in my jurisdiction, including one-party and two-party consent
requirements.

For our full Call Recording Policy, see https://parwa.ai/legal/call-recording.

This consent was given on [DATE] from IP [IP_ADDRESS].
```

## Backend APIs

### `POST /api/onboarding/consent`

| Field | Value |
|-------|-------|
| **Method** | POST |
| **Auth** | Required (valid access token) |
| **Rate Limit** | 10 requests per user per hour |

**Request Body:**
```json
{
  "consents": [
    {
      "consent_type": "tcpa",
      "consented": true,
      "consent_version": "2026-03-01"
    },
    {
      "consent_type": "gdpr",
      "consented": true,
      "consent_version": "2026-03-01"
    },
    {
      "consent_type": "call_recording",
      "consented": true,
      "consent_version": "2026-03-01"
    }
  ]
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Consent recorded successfully",
  "consent_records": [
    {
      "consent_type": "tcpa",
      "consented_at": "2026-03-01T12:00:00Z",
      "ip_address": "203.0.113.42"
    },
    {
      "consent_type": "gdpr",
      "consented_at": "2026-03-01T12:00:00Z",
      "ip_address": "203.0.113.42"
    },
    {
      "consent_type": "call_recording",
      "consented_at": "2026-03-01T12:00:00Z",
      "ip_address": "203.0.113.42"
    }
  ],
  "next_step": 3
}
```

**Error Cases:**

| HTTP Code | Condition | Response |
|-----------|-----------|----------|
| 400 | Missing required consent | `{ "status": "error", "message": "TCPA consent is required to continue", "missing_consents": ["tcpa"] }` |
| 400 | Invalid consent_type | `{ "status": "error", "message": "Invalid consent type: spam", "valid_types": ["tcpa", "gdpr", "call_recording"] }` |
| 409 | Consent already recorded | `{ "status": "error", "message": "Consent already recorded for tcpa", "error_code": "ALREADY_CONSENTED" }` |
| 403 | User is not company owner/admin | `{ "status": "error", "message": "Only company owners or admins can accept legal consents" }` |

### `GET /api/legal/consent-history`

| Field | Value |
|-------|-------|
| **Method** | GET |
| **Auth** | Required |
| **Response (200)** | Array of consent records for the authenticated user's company |

```json
{
  "status": "success",
  "consents": [
    {
      "id": "con_a1b2c3",
      "consent_type": "tcpa",
      "consent_version": "2026-03-01",
      "consented_at": "2026-03-01T12:00:00Z",
      "ip_address": "203.0.113.42",
      "user_agent": "Mozilla/5.0...",
      "consented_by": "usr_a1b2c3d4",
      "consented_by_name": "Jane Doe",
      "revoked_at": null
    }
  ]
}
```

### `POST /api/legal/revoke-consent`

| Field | Value |
|-------|-------|
| **Method** | POST |
| **Auth** | Required (owner/admin only) |

**Request Body:**
```json
{
  "consent_type": "call_recording",
  "reason": "Company no longer uses voice features"
}
```

**Response (200):**
```json
{
  "status": "success",
  "message": "Call recording consent revoked. Voice features will be disabled within 24 hours.",
  "effects": ["voice_ai_disabled", "call_recordings_scheduled_for_deletion"]
}
```

## Database Tables

```sql
CREATE TABLE consent_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id          UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id),      -- who consented
    consent_type        VARCHAR(30) NOT NULL,                     -- 'tcpa', 'gdpr', 'call_recording'
    consent_version     VARCHAR(20) NOT NULL,                     -- '2026-03-01' (date-based versioning)
    consent_text        TEXT NOT NULL,                            -- full text at time of consent (immutable)
    consented_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address          INET NOT NULL,                            -- user's IP at time of consent
    user_agent          TEXT,                                     -- browser user agent
    revoked_at          TIMESTAMPTZ,                              -- NULL if active
    revoked_by          UUID REFERENCES users(id),                -- who revoked
    revoke_reason       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_consent_active UNIQUE(company_id, consent_type, consent_version)
        WHERE revoked_at IS NULL                                 -- only one active consent per type per company
);

CREATE INDEX idx_cr_company_id ON consent_records(company_id);
CREATE INDEX idx_cr_consent_type ON consent_records(consent_type);
CREATE INDEX idx_cr_active ON consent_records(company_id, consent_type) WHERE revoked_at IS NULL;
CREATE INDEX idx_cr_created_at ON consent_records(created_at);
```

## Building Codes Applied

| Code | Rules Applied |
|------|--------------|
| **BC-001** | Rules 1, 4, 5, 8 — All consent queries scoped by company_id. RLS middleware on all queries. Indexes on company_id. No cross-tenant consent visibility. |
| **BC-009** | Rule 1 — Legal consent is an approval-like action: requires owner/admin role. The consent record captures the approver (user_id), timestamp, and full context (IP, user agent, consent text). |
| **BC-010** | Rules 1, 3, 5 — GDPR consent text explicitly describes data retention periods, data subject rights (export, erasure), and audit trail preservation. Right to be Forgotten uses anonymization (SHA-256), not deletion, per BC-010 Rule 3. Audit trail records (including consent records) preserved for 5 years. |
| **BC-012** | Rule 5 — All consent actions logged in structured JSON. Consent revocation effects (e.g., voice feature disable) are auditable. |

## Edge Cases

| Edge Case | Handling |
|-----------|----------|
| User declines a required consent | The "Continue" button remains disabled. A tooltip explains why: "TCPA consent is required to enable SMS and voice features." The user cannot proceed to Step 3 without it. |
| Consent text is updated after a user has already consented | Old consent records remain valid. New consent is stored with the new `consent_version`. The latest active consent (highest version where `revoked_at IS NULL`) is the one in effect. If the new consent includes materially different terms, the onboarding wizard may prompt the user to re-consent. |
| EU user (detected by IP) does not provide GDPR consent | GDPR consent is mandatory for all users, not just EU users. The consent text adapts based on detected region (full GDPR text for EU, simplified privacy consent for others), but the consent checkbox is always present and required. |
| Company owner changes — does new owner need to re-consent? | No. Consent is recorded at the company level, not the individual level. The new owner inherits existing consents. However, the new owner is shown the consent history in Settings and can revoke/re-consent if desired. |
| User revokes TCPA consent | SMS and voice features are disabled within 24 hours via a Celery task. Existing SMS messages in flight are allowed to complete. The revocation is logged in the audit trail. |
| User revokes GDPR consent | This is a complex legal action. The system warns: "Revoking GDPR consent will disable all AI processing and initiate data anonymization for your account." The user must confirm via a modal. Upon confirmation, AI processing is paused, and the Right to be Forgotten flow (BC-010 Rule 3) is initiated. |
| Consent page loads but user navigates away before accepting | The onboarding step remains at 2. No consent is recorded. The user can return to complete it later. No features are enabled. |

## Acceptance Criteria

1. The consent step displays three consent sections (TCPA, GDPR, Call Recording) with plain-language explanations, expandable full-policy links, and opt-in checkboxes.
2. The "Continue" button is disabled until all required consent checkboxes are checked. Attempting to submit without all consents returns 400 with `missing_consents`.
3. On consent submission, individual `consent_records` are created for each consent type with the full consent text, timestamp, IP address, and user agent.
4. Only users with `owner` or `admin` role can submit consent. Other roles receive 403.
5. Each consent record stores the full consent text at the time of acceptance, ensuring the historical record is immutable even if policy text changes later.
6. The consent history endpoint (`GET /api/legal/consent-history`) returns all consent records for the company, including active and revoked consents.
7. Revoking a consent (e.g., TCPA) updates the record with `revoked_at` and triggers the appropriate downstream effect (e.g., disabling SMS features within 24 hours).

---

## Dependency Map — Batch 1 Features

```
F-004 (Pricing Page)
  └── F-020 (Paddle Checkout)
        ├── F-022 (Paddle Webhook Handler)
        │     └── F-027 (Payment Confirmation)
        └── F-010 (User Registration) ─── F-012 (Email Verification)
              └── F-013 (Login System)
                    └── F-029 (Legal Consent — via Onboarding)
```

## Conflict Notes

| Feature | Conflict | Resolution Required |
|---------|----------|-------------------|
| F-010, F-013 | BC-011 Rule #2 says "Google OAuth is the ONLY supported authentication method per decision D11." Email/password login MUST NOT be implemented in v1. | **Product decision needed.** Either: (A) Remove F-010/F-013 and use F-011 (Google OAuth) as the sole auth method, or (B) Override D11 to allow email/password alongside Google OAuth. This must be resolved before implementation begins. |

---

*Document generated: March 2026 | PARWA Engineering*
*Building Codes: BC-001 through BC-012 applied throughout*
*Tech Stack: Next.js 16 (Frontend), FastAPI (Backend), PostgreSQL (Database), Paddle (Payments), Brevo (Email), Redis (Cache), Celery (Background Jobs)*
