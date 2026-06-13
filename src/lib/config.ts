/**
 * PARWA — Centralized Configuration Exports
 *
 * Re-exports commonly used configuration values so that BFF route
 * handlers can import from a single path (@/lib/config).
 */

import { getBackendUrl } from '@/lib/backend-url';

/** Backend base URL (resolved at import time for server-side routes). */
export const BACKEND_URL = getBackendUrl();
