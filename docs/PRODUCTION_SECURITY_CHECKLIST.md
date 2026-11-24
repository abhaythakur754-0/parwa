# Production security and launch checklist

This checklist is deliberately separate from CI. A green GitHub Actions run does not prove that the live Render, Supabase, Vercel, Razorpay, Twilio, or LLM-provider configuration is correct.

## Required Render secrets

Set `ENVIRONMENT=production` on the backend and worker. The Render blueprint already declares this.

Generate cryptographically random values (at least 32 characters) for:

- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `DATA_ENCRYPTION_KEY`
- `PRICING_SIGNING_KEY`
- `REFRESH_TOKEN_PEPPER`

Keep each value private. Do not reuse one key for another purpose. The backend and worker must use the same values for keys that protect shared tokens or encrypted records.

### Redis

The Redis container now refuses to start without `REDIS_PASSWORD` and starts Redis with `requirepass`. Generate a URL-safe value with `openssl rand -hex 32`; the container rejects characters outside letters, numbers, `_`, and `-`.

Set the **same strong random `REDIS_PASSWORD`** on all three Render services:

1. `parwa-redis`
2. `parwa-backend`
3. `parwa-worker`

The backend Redis client and Celery broker/result-backend URLs apply this password at connection time. The Redis password is separate from the application signing/encryption keys.

## Required Vercel environment

Configure these as server-side environment variables in the Vercel project:

- `BACKEND_URL` pointing to the production Render API.
- `JWT_SECRET_KEY` matching the backend when HS256 is used. If RS256 is selected, configure the matching public-key variables and `NEXT_PUBLIC_JWT_ALGORITHM=RS256` instead; never expose a private signing key.
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for server-side database routes. The service-role key must never use a `NEXT_PUBLIC_` prefix.
- `FRONTEND_URL` set to the canonical production origin.
- `SUPERGLUE_LLM_API_KEY` only if the Superglue-backed chat integration is enabled.

Do not copy secrets into build arguments, source files, client-side variables, or logs. Keep the Vercel and Render token-verification configuration aligned.

## Required database migration

Before enabling the updated Razorpay verification flow, apply:

`supabase/migrations/0002_razorpay_subscription_idempotency.sql`

It adds `subscriptions.razorpay_order_id` and a unique index so concurrent verification retries cannot create duplicate subscription rows for one Razorpay order.

Apply the migration to the actual Supabase project used by production, then verify the column and index exist. CI does not apply this migration to the live database.

## Credential rotation

The old committed Superglue credential was removed from application code. Removing a credential from the current source does not invalidate copies in Git history. Revoke and rotate that credential in the Superglue provider, then set the replacement only in the deployment secret store.

Review provider keys and webhook secrets (Razorpay, Twilio, email, CRM, LLM providers) and rotate any value that has ever been committed or shared outside the secret store.

## Legacy guest Jarvis sessions

The legacy Next.js marketing/guest Jarvis flow still uses a process-local Map for local development and tests. It is not durable or shared across instances and must not be treated as production-grade persistence.

The production route guard now returns HTTP 410 for the legacy guest session, message, history, context, ticket, and payment-status handlers before they can read or mutate the in-memory store. The persistent authenticated Customer Care Jarvis `/cc/*` routes and backend handoff routes remain available.

Keep this production guard enabled until the guest flow is migrated to durable, tenant-safe storage and verified across multiple instances. Do not add an environment override that re-enables the in-memory implementation in production.

## Required live smoke tests

Run these against staging with real test credentials before production:

- Sign up, login, refresh, logout, password reset, and MFA.
- Verify onboarding cannot complete or activate until the backend confirms the exact saved work email through OTP.
- Verify cross-user and cross-company access is rejected for onboarding, tickets, knowledge base, integrations, and billing.
- Complete a Razorpay test payment; confirm amount/currency/order ownership and captured status; replay verification concurrently and confirm exactly one subscription is created.
- Send a Razorpay webhook with a valid signature and confirm invalid signatures are rejected.
- Verify Twilio inbound, status, and gather callbacks with real provider signatures.
- Create, test, and deliver an outbound webhook to a controlled public HTTPS endpoint; verify private IPs and redirects are rejected.
- Create, pause, resume, cancel, and process a FlexPay plan using a test payment method.
- Confirm Redis authentication and Celery worker connectivity after deployment.
- Confirm debug/setup routes return 404 outside local development and the database-wipe route always returns 410.

## Release rule

Do not mark production-ready until:

1. The latest PR checks are green.
2. The Supabase migration is applied.
3. Required secrets are configured consistently on Render.
4. The leaked credential is rotated.
5. The live smoke tests above pass.
6. The legacy guest Jarvis flow remains disabled in production until durable, tenant-safe storage is implemented and tested across multiple instances.

A static code review and GitHub Actions run alone cannot verify these external systems.
