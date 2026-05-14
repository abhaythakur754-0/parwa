/**
 * PARWA Sentry Client Configuration (Phase 6)
 *
 * Initializes Sentry for the client-side (browser) in Next.js.
 * Only activates when NEXT_PUBLIC_SENTRY_DSN is configured.
 *
 * Features:
 *   - Performance tracing at 10% sample rate
 *   - Session replay at 10% for normal sessions, 100% on errors
 *   - GDPR compliance: no default PII sent
 *   - Environment-aware configuration
 */

import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_ENV || 'development',
  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
  debug: false,
  sendDefaultPii: false,
});
