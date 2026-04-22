import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT || process.env.NODE_ENV,
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 0,
  debug: false,
  // Don't send PII
  sendDefaultPii: false,
  // Filter out localhost
  denyUrls: [/localhost/],
  beforeSend(event) {
    // Filter health checks and noise
    if (event.request && event.request.url) {
      if (event.request.url.includes("/health")) return null;
    }
    return event;
  },
  ignoreErrors: [
    "ResizeObserver loop limit exceeded",
    "Non-Error promise rejection captured",
  ],
});
