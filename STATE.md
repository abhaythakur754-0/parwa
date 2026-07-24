# PARWA — Current State

**Last verified:** 2026-06-24 14:05 UTC

## Git
- Branch: `main`
- Latest commit: `2f5816e` — fix: signup redirect race condition
- All 3 recent commits pushed to GitHub (verified via API):
  - `2f5816e` — signup redirect race condition
  - `ddfe07c` — auth + dashboard + RLS fixes
  - `b4133f7` — trial status + Netflix billing check removed

## Database (Supabase)
- Total DB size used: **18 MB** (3.6% of 500 MB free tier)
- Total tables: 156
- User data: wiped on 2026-06-24 (0 users at wipe time)
- RLS enabled on all 156 public tables (185 Supabase linter warnings resolved)

## Running Services
- Frontend (Next.js 16): port 3000 ✅
- Backend (FastAPI/uvicorn): port 8000 ✅ (connected to Supabase PostgreSQL)
- Backend health: postgresql=healthy, Paddle/Brevo/Twilio=healthy

## Known Issue
- Stale browser cookies may auto-redirect users to /dashboard after a DB wipe.
  Fix planned: stale-session detector (verify cookie against backend on app load,
  auto-clear if user no longer exists).

## Recent Change (2026-06-24)
- **Paddle fully removed.** Razorpay is now the ONLY billing provider.
  - All Paddle backend files deleted (client, service, reconciliation, bridge, handler, schema)
  - 3 billing services rewritten as DB-only (subscription/invoice/overage)
  - billing_webhooks.py router deleted (was Paddle-only)
  - @paddle/paddle-js removed from package.json
  - All PADDLE_* env vars removed
  - DB columns (paddle_subscription_id etc.) kept for backward compat — now store Razorpay IDs
- **Redis IS in use** (33 Celery task modules + celery_app.py). Previous STATE.md claim "no Redis" was stale.
- **Rust parwa_core extension** (rate limiter, circuit breaker, crypto, HMAC) — source exists at backend/parwa_core/src/ but NOT compiled (.so missing). Needs `maturin develop` before prod deploy.
