/**
 * PARWA Sentry Edge Configuration (Phase 6)
 *
 * Initializes Sentry for edge runtime in Next.js.
 * Only activates when NEXT_PUBLIC_SENTRY_DSN is configured.
 *
 * Features:
 *   - Performance tracing at 10% sample rate
 *   - GDPR compliance: no default PII sent
 *   - Environment-aware configuration
 */

import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_ENV || 'development',
  tracesSampleRate: 0.1,
  sendDefaultPii: false,
});
