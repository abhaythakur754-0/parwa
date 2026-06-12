# PARWA Onboarding Flow — HONEST EVIDENCE REPORT

> Per CLAUDE.md Rule #5: "Do not say 'it works' unless you have PROVEN it works."

## Test Date: 2026-06-12

## Executive Summary

**THE ONBOARDING FLOW IS NOT FULLY WORKING.** While backend APIs all return correct data when called directly, the frontend-to-backend connection through the BFF proxy has critical issues. Multiple bugs were discovered and partially fixed.

---

## What Was Actually Proven (with evidence)

### ✅ Backend APIs: 11/11 WORKING

All backend APIs return real data when called directly with proper auth:

| API | Status | Evidence |
|-----|--------|----------|
| POST /api/auth/login | ✅ 200 | Returns user + tokens (access_token, refresh_token) |
| GET /api/onboarding/state | ✅ 200 | Returns current_step:2, completed_steps:[1], legal_accepted:false |
| GET /api/onboarding/prerequisites | ✅ 200 | Returns can_activate:false, missing:[legal_consent, integration_or_kb] |
| GET /api/integrations/catalog?industry=saas | ✅ 200 | Returns 17 real integrations (HubSpot, Salesforce, etc.) |
| GET /api/integrations/available | ✅ 200 | Returns real integration catalog |
| GET /api/pricing/industries | ✅ 200 | Returns 4 industries: ecommerce, saas, logistics, other |
| GET /api/pricing/variants/saas | ✅ 200 | Returns real SaaS pricing variants |
| GET /api/ai/instances | ✅ 200 | Returns 1 instance: PARWA (parwa variant, active) |
| GET /api/billing/status | ✅ 200 | Returns subscription_status:"none" |
| GET /api/billing/subscription | ✅ 200 | Returns has_subscription:false |
| GET /api/auth/me | ✅ 200 | Returns user profile with company_id |

### ✅ BFF Proxy (Unauthenticated): WORKING

| API | Status | Data Source |
|-----|--------|-------------|
| GET /api/integrations/catalog | ✅ 200 | Real backend data (17 integrations) |
| GET /api/onboarding/state | ❌ 200 | **MOCK FALLBACK** (mock-onboarding, mock-user) |

### ❌ BFF Proxy (Authenticated): NOT WORKING

| API | Status | Issue |
|-----|--------|-------|
| POST /api/auth/login | ❌ FAIL | Returns "Login temporarily unavailable" or falls to local Prisma |

---

## Bugs Found and Fixed

### Bug 1: `variant_limits` Table Was EMPTY
- **Impact**: `/api/ai/instances` returned 500 Internal Server Error
- **Root Cause**: The `variant_limits` table had no rows — no pricing data for any variant
- **Fix**: Seeded with mini_parwa ($999/500 tickets), parwa ($2,499/2,000 tickets), parwa_high ($4,999/10,000 tickets)
- **Status**: ✅ FIXED — AI instances now returns 200

### Bug 2: Missing `celery_queue_namespace` and `redis_partition_key` Columns
- **Impact**: `_serialize_instance()` crashed with AttributeError when accessing ORM model attributes
- **Root Cause**: The SQLAlchemy model defined columns that didn't exist in the actual SQLite table
- **Fix**: Added missing columns via ALTER TABLE
- **Status**: ✅ FIXED — AI instances now serializes correctly

### Bug 3: BFF Proxy Sends Wrong Origin Header
- **Impact**: CSRF middleware rejects all POST requests from the frontend
- **Root Cause**: `getProxyOrigin()` in `backend-proxy.ts` returns `https://parwa.buzz` in production mode, even when running locally
- **Fix Needed**: Must set `FRONTEND_URL=http://localhost:3000` env var when running locally
- **Status**: ⚠️ PARTIALLY FIXED — env var fix works, but the BFF proxy's CSRF token fetch still fails due to timing issues

### Bug 4: Backend CSRF Middleware Rejects BFF Proxy Requests  
- **Impact**: Login through BFF fails → all authenticated endpoints fall back to mock data
- **Root Cause**: BFF proxy's 2-step CSRF flow (try without → fetch CSRF → retry) fails because the CSRF token fetch itself gets ECONNREFUSED
- **Status**: ❌ NOT FIXED

### Bug 5: BFF Onboarding Route Falls Back to MOCK Data
- **Impact**: Frontend onboarding wizard shows mock data instead of real backend state
- **Root Cause**: When BFF proxy fails (CSRF), the onboarding route.ts returns hardcoded mock responses
- **Evidence**: `{"id":"mock-onboarding","user_id":"mock-user","company_id":"mock-company"}`
- **Status**: ❌ NOT FIXED

### Bug 6: Backend Was Running Without CSRF_TRUSTED_ORIGINS
- **Impact**: All POST requests from any origin were being rejected
- **Root Cause**: The backend was started without loading the `.env` file, so CSRF_TRUSTED_ORIGINS was empty
- **Fix**: Restarted with `source .env` before starting uvicorn
- **Status**: ✅ FIXED — Direct backend login with Origin: http://localhost:3000 now works

---

## What the User Would See in the Browser

Based on the BFF proxy behavior, here's what actually happens:

1. **Landing Page**: ✅ Loads fine (static page)
2. **Login Page**: ⚠️ Login MIGHT work intermittently — CSRF proxy is flaky
3. **Onboarding Page**: ❌ Shows MOCK data (not connected to backend) 
   - Industry/variant selection doesn't persist to backend
   - Legal consent doesn't save to backend
4. **Dashboard**: ⚠️ May show some data from public APIs, but authenticated data is mock
5. **Cost Breakdown**: ❌ No real billing/variant data

---

## Key Issues Blocking Phase 5

1. **BFF Login is Broken** — The CSRF proxy flow fails, causing all authenticated features to fall back to mock data
2. **Onboarding Wizard Uses MOCK Data** — The onboarding page shows mock state instead of real backend state
3. **No Paddle Frontend Integration** — The checkout component is still missing from Phase 4
4. **Server Stability** — The Next.js production server keeps dying (likely memory-related)

## Recommendation

Before starting Phase 5, the following MUST be fixed:

1. Fix the BFF proxy CSRF handling so login works reliably
2. Remove mock fallbacks from onboarding route.ts — fail loudly instead of silently serving fake data
3. Ensure the onboarding wizard actually saves data to the backend (industry, variant, legal consent)
4. Add the Paddle checkout frontend component (Phase 4 gap)
