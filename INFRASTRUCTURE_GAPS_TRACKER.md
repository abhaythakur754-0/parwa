# PARWA Infrastructure Gaps Tracker

> Discovered during Day 6 (Week 1) Cross-Day Audit.
> Items marked with target week should be addressed when that week begins.
> Items without a week are notes for future reference.

---

## CRITICAL - Must Fix Before Week 2

These are infrastructure items that should be built in Week 1 (Day 6 fixes) to unblock future development.

- [x] C1: Generate Alembic migration stubs (0 exist)
- [x] C2: Add CORS middleware to main.py
- [x] Fix alembic.ini -> PostgreSQL
- [x] Fix .env.example missing vars
- [x] Fix Docker compose: remove OPENAI_API_KEY, STRIPE_SECRET_KEY, STRIPE references
- [x] Remove Qdrant config (use pgvector only)
- [x] Add missing packages to requirements.txt
- [x] Fix Socket.io cors_allowed_origins
- [x] Wire API Key Auth middleware in main.py
- [x] Add security headers middleware
- [x] Fix rate limiter MD5 -> SHA-256
- [x] Fix document_chunks embedding column type
- [x] Add API versioning prefix /api/v1/
- [x] Fix Docker compose PADDLE_VENDOR_ID/PADDLE_AUTH_CODE -> correct env names

---

## Week 2 GAPS - Auth System

- [ ] C3-alt: JWT auth functions (create/verify/refresh tokens) -> `backend/app/core/auth.py`
- [ ] C4: Brevo email client + email service -> `backend/app/services/email_service.py`
- [ ] C5: Phone OTP login (Twilio Verify) -> new endpoints under /api/v1/auth/phone
- [ ] F04: Google OAuth implementation -> authlib or httpx-oauth
- [ ] F05: Pydantic schemas directory -> `backend/app/schemas/`
- [ ] F07: Email template rendering (Jinja2) -> `backend/app/templates/emails/`
- [ ] S02: Socket.io JWT auth middleware (real auth, not placeholder)
- [ ] FP11: Audit trail auto-logging middleware (log all write ops)
- [ ] Add `phone` column to users model
- [ ] Add pyotp, qrcode, jinja2, brevo-python, authlib to requirements.txt

## Week 3 GAPS - Background Jobs + Real-Time

- [ ] C3: Celery app + worker entry point -> `backend/app/celery_app.py`, `backend/worker/main.py`
- [ ] FP03: Celery task base class with company_id first param (BC-004)
- [ ] FP04: Webhook processing framework (HMAC verify + idempotency + async)
- [ ] S06: HMAC webhook verification utility (Paddle, Twilio, Brevo, Shopify)
- [ ] FP10: Celery health check in /health endpoint
- [ ] Add Celery Beat service to docker-compose.prod.yml
- [ ] Create 7 queues: default, ai_heavy, ai_light, email, webhook, analytics, training

## Week 4-5 GAPS - Tickets + Billing

- [ ] F06: API route files and router registration in main.py
- [ ] FP02: Standardized PaginatedResponse[T] schema
- [ ] S05: IP allowlist middleware for admin routes
- [ ] Paddle checkout integration (one-time for $1 voice demo)
- [ ] Paddle subscription management

## Week 6 GAPS - Onboarding

- [ ] FP05: File/media storage service (GCP Cloud Storage)
- [ ] Knowledge base upload processing pipeline
- [ ] pgvector extension enablement in PostgreSQL

## Week 8+ GAPS - AI Engine

- [ ] LLM provider management (store provider configs, API keys, rate limits)
- [ ] Prompt template management system
- [ ] Context compression + health meter

## Week 13 GAPS - Channels

- [ ] FP08: SMS template system (Twilio)
- [ ] Email outbound rate limiting (5 replies/thread/24h)
- [ ] Channel-specific message formatting

## Week 17 GAPS - Integrations

- [ ] Circuit breaker wrapping all outbound calls
- [ ] Integration health monitor (60s interval)

## Week 19 GAPS - Training

- [ ] Training data export pipeline
- [ ] Model comparison endpoints

## Week 20 GAPS - Polish

- [ ] FP06: GDPR data export/deletion job
- [ ] Full security audit
- [ ] Load testing (10K concurrent tickets)

---

## Database Gaps (Tables Missing from Models)

- [ ] DB03: `human_corrections` table -> training.py (needed Week 19)
- [ ] DB04: `approval_batches` table -> approval.py (needed Week 7)
- [ ] DB05: `notifications` table -> new model (needed Week 7+)
- [ ] DB06: `first_victories` table -> new model (needed Week 6)
- [ ] `user_notification_preferences` unique constraint on (user_id, channel, event_type)

---

## Doc Conflicts Resolved

- [x] DC1: F-008 Stripe -> Paddle (all docs updated)
- [x] DC3: OPENAI_API_KEY in Docker -> removed, using correct env names
- [x] DC6: Qdrant config removed, pgvector only
- [ ] DC2: Some docs say `tenant_id` vs `company_id` -> standardize to company_id (deferred - requires doc edits in /documents/)
- [ ] DC4: `sessions` table rename to `support_sessions` (deferred - requires model + migration change)
- [ ] DC5: Table count "50+" vs actual ~45 (deferred - update after missing tables added)

---

## User Decisions Made

1. **Auth method**: Google OAuth OR email/password for account creation. Phone number only for instant demo flow (not for login).
2. **Payment provider**: Paddle for EVERYTHING (subscriptions + $1 voice demo). NO Stripe anywhere.
3. **Voice demo**: 3 minutes for $1, re-pay $1 for additional time.
4. **Vector DB**: pgvector (no Qdrant).
5. **LLM Keys**: User has own set of provider keys (not OpenAI/OpenRouter). Will provide when needed.
6. **$1 demo re-payment**: After initial 3-min demo expires, visitor can pay another $1 for more time.

## Unresolved Decisions (Still Blocked)

1. **Smart Router tiers**: Light/Medium/Heavy (specs) vs Light/Heavy/Ultra (tech assistant) -> Before Week 8
2. **Rename `sessions` table** to `support_sessions`? -> User confirmation needed
