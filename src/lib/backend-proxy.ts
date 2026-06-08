/**
 * PARWA — Backend Proxy Helper
 *
 * Handles CSRF token acquisition and forwarding for backend proxy requests.
 *
 * The backend's CSRF middleware requires:
 * 1. Valid Origin header (matching CSRF_TRUSTED_ORIGINS)
 * 2. For cookie-auth paths: CSRF cookie + x-csrf-token header (double-submit)
 * 3. Bearer token auth is exempt from CSRF cookie check
 *
 * OPTIMIZATION: For auth endpoints, we try the request WITHOUT CSRF first
 * (1 round trip). If the backend returns 403 "CSRF token missing", we
 * then fetch CSRF and retry (2 round trips). This saves a full round trip
 * when the backend is warm and processes the request before the CSRF check.
 *
 * Fallback: For Vercel Hobby (10s function limit), we also retry with
 * increased timeout awareness — Render cold starts can take 8-12s.
 */

import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

/**
 * Get the Origin header for proxy requests.
 *
 * Dynamic based on VERCEL_URL or environment, never hardcoded.
 * Falls back to http://localhost:3000 for local development.
 */
function getProxyOrigin(): string {
  // Runtime env var — can be changed without rebuilding
  if (process.env.FRONTEND_URL) {
    return process.env.FRONTEND_URL;
  }
  // Vercel provides VERCEL_URL (e.g. parwa.vercel.app)
  if (process.env.VERCEL_URL) {
    return `https://${process.env.VERCEL_URL}`;
  }
  // Production default — must match a CORS-allowed origin on the backend
  if (process.env.NODE_ENV === 'production') {
    return 'https://parwa.buzz';
  }
  // Local development
  return 'http://localhost:3000';
}

interface CSRFTokens {
  cookie: string;
  token: string;
}

/**
 * Fetch a CSRF cookie from the backend by making a GET request.
 * The backend's CSRF middleware sets a parwa_csrf cookie on ALL responses,
 * so even a 404 will give us the cookie.
 */
async function fetchCSRFToken(): Promise<CSRFTokens | null> {
  const origin = getProxyOrigin();
  try {
    const res = await fetch(`${BACKEND_URL}/api/health`, {
      method: 'GET',
      headers: {
        'Origin': origin,
        'Referer': `${origin}/`,
      },
      signal: AbortSignal.timeout(30000),
    });

    // Extract CSRF cookie from Set-Cookie header
    const setCookie = res.headers.get('set-cookie') || '';
    const csrfMatch = setCookie.match(/parwa_csrf=([^;]+)/);
    const csrfCookie = csrfMatch ? csrfMatch[1] : '';

    if (csrfCookie) {
      return { cookie: csrfCookie, token: csrfCookie };
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Check if a response indicates a CSRF token error.
 */
function isCSRFError(response: Response): boolean {
  // Fast check without consuming the body
  if (response.status !== 403) return false;
  return true; // Will check body in the caller if needed
}

/**
 * Make a CSRF-aware request to the backend.
 *
 * Strategy: Try without CSRF first (1 round trip). If the backend
 * returns 403 with "CSRF token missing", fetch CSRF and retry.
 * This saves ~9 seconds when the backend is warm.
 */
export async function backendProxy(
  path: string,
  options: {
    method: string;
    body?: string;
    /** Forward auth token from the incoming request */
    authToken?: string;
    /** Extra headers */
    extraHeaders?: Record<string, string>;
  }
): Promise<{ response: Response; csrfUsed: boolean }> {
  const { method, body, authToken, extraHeaders = {} } = options;

  const origin = getProxyOrigin();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Origin': origin,
    'Referer': `${origin}/`,
    ...extraHeaders,
  };

  // If we have an auth token, include it (this also bypasses CSRF cookie check)
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  // For cookie-auth paths without a Bearer token, we need CSRF
  const cookieAuthPaths = ['/api/auth/login', '/api/auth/register', '/api/auth/google', '/api/mfa/'];
  const needsCSRF = !authToken && cookieAuthPaths.some(p => path.startsWith(p));

  // ── OPTIMIZATION: Try without CSRF first for auth paths ──
  // This saves a full round trip when the backend is warm.
  // If it fails with 403 CSRF, we'll retry with CSRF.
  if (needsCSRF) {
    try {
      const response = await fetch(`${BACKEND_URL}${path}`, {
        method,
        headers,
        body: method !== 'GET' && method !== 'HEAD' ? body : undefined,
        signal: AbortSignal.timeout(30000),
      });

      // If NOT a CSRF error, return the response immediately
      if (response.status !== 403) {
        return { response, csrfUsed: false };
      }

      // Check if it's specifically a CSRF error
      const cloned = response.clone();
      try {
        const errorBody = await cloned.json();
        const errorMsg = (errorBody?.error?.message || errorBody?.message || '').toLowerCase();
        if (!errorMsg.includes('csrf')) {
          // It's a different 403 error (not CSRF) — return it
          return { response, csrfUsed: false };
        }
      } catch {
        // Can't parse body — return the original response
        return { response, csrfUsed: false };
      }

      // CSRF error — need to retry with CSRF token
      console.log(`[backend-proxy] CSRF required for ${path} — fetching token and retrying`);
    } catch (fetchError) {
      // First attempt timed out or failed — try with CSRF
      console.warn(`[backend-proxy] First attempt failed for ${path}:`, fetchError);
    }

    // ── Retry with CSRF token ──
    const csrfTokens = await fetchCSRFToken();
    if (csrfTokens) {
      headers['Cookie'] = `parwa_csrf=${csrfTokens.cookie}`;
      headers['x-csrf-token'] = csrfTokens.token;
    }

    const response = await fetch(`${BACKEND_URL}${path}`, {
      method,
      headers,
      body: method !== 'GET' && method !== 'HEAD' ? body : undefined,
      signal: AbortSignal.timeout(30000),
    });

    return { response, csrfUsed: !!csrfTokens };
  }

  // ── Non-auth paths: just make the request directly ──
  const response = await fetch(`${BACKEND_URL}${path}`, {
    method,
    headers,
    body: method !== 'GET' && method !== 'HEAD' ? body : undefined,
    signal: AbortSignal.timeout(30000),
  });

  return { response, csrfUsed: false };
}
