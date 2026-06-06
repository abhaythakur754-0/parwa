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
 * For unauthenticated requests (login, register), we need to first
 * get a CSRF cookie from the backend, then include it in the request.
 */

import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

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
  try {
    const res = await fetch(`${BACKEND_URL}/api/health`, {
      method: 'GET',
      headers: {
        'Origin': 'https://parwa.buzz',
        'Referer': 'https://parwa.buzz/',
      },
      signal: AbortSignal.timeout(10000),
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
 * Make a CSRF-aware request to the backend.
 * For cookie-auth paths, automatically fetches and includes CSRF tokens.
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

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Origin': 'https://parwa.buzz',
    'Referer': 'https://parwa.buzz/',
    ...extraHeaders,
  };

  // If we have an auth token, include it (this also bypasses CSRF cookie check)
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  // For cookie-auth paths without a Bearer token, we need CSRF
  const cookieAuthPaths = ['/api/auth/login', '/api/auth/register', '/api/auth/google', '/api/mfa/'];
  const needsCSRF = !authToken && cookieAuthPaths.some(p => path.startsWith(p));

  let csrfTokens: CSRFTokens | null = null;
  if (needsCSRF) {
    csrfTokens = await fetchCSRFToken();
    if (csrfTokens) {
      headers['Cookie'] = `parwa_csrf=${csrfTokens.cookie}`;
      headers['x-csrf-token'] = csrfTokens.token;
    }
  }

  const response = await fetch(`${BACKEND_URL}${path}`, {
    method,
    headers,
    body: method !== 'GET' && method !== 'HEAD' ? body : undefined,
    signal: AbortSignal.timeout(15000),
  });

  return { response, csrfUsed: !!csrfTokens };
}
