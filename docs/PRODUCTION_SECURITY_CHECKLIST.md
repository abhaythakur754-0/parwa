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

The Redis container now refuses to start without `REDIS_PASSWORD` and starts Redis with `requirepass`.

Set the **same strong random `REDIS_PASSWORD`** on all three Render services:

1. `parwa-redis`
2. `parwa-backend`
3. `parwa-worker`

The backend Redis client and Celery broker/result-backend URLs apply this password at connection time. The Redis password is separate from the application signing/encryption keys.

## Required database migration

Before enabling the updated Razorpay verification flow, apply:

`supabase/migrations/0002_razorpay_subscription_idempotency.sql`

It adds `subscriptions.razorpay_order_id` and a unique index so concurrent verification retries cannot create duplicate subscription rows for one Razorpay order.

Apply the migration to the actual Supabase project used by production, then verify the column and index exist. CI does not apply this migration to the live database.

## Credential rotation

The old committed Superglue credential was removed from application code. Removing a credential from the current source does not invalidate copies in Git history. Revoke and rotate that credential in the Superglue provider, then set the replacement only in the deployment secret store.

Review provider keys and webhook secrets (Razorpay, Twilio, email, CRM, LLM providers) and rotate any value that has ever been committed or shared outside the secret store.

## Required live smoke tests

Run these against staging with real test credentials before production:

- Sign up, login, refresh, logout, password reset, and MFA.
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

A static code review and GitHub Actions run alone cannot verify these external systems.
