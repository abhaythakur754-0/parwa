/**
 * PARWA Centralized Application Configuration
 *
 * Single source of truth for all environment-dependent settings.
 * Replaces scattered `process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'`
 * patterns across the codebase.
 *
 * Usage:
 *   import { appConfig } from '@/lib/config';
 *   fetch(`${appConfig.apiUrl}/api/v1/tickets`);
 */

export const appConfig = {
  /** Backend API base URL */
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',

  /** WebSocket URL for Socket.io connections */
  wsUrl: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',

  /** Whether the app is running in demo/mock mode */
  isDemo: process.env.NEXT_PUBLIC_DEMO_MODE === 'true',

  /** Current Node environment */
  environment: process.env.NODE_ENV || 'development',
} as const;
