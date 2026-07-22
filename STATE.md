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
