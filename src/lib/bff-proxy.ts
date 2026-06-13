/**
 * PARWA — BFF Proxy Shared Utilities
 *
 * Consolidates the duplicated URL resolution, origin detection,
 * and cookie extraction that was copy-pasted across 12+ BFF routes.
 *
 * BC-004: Don't create a new integration layer when one already exists.
 * This uses the existing getBackendUrl() and getAccessTokenFromCookies()
 * rather than reimplementing them.
 */

import { getBackendUrl } from '@/lib/backend-url';
import { getAccessTokenFromCookies } from '@/lib/auth-cookies';
import { NextRequest, NextResponse } from 'next/server';

/** Get the Origin header for proxy requests (matches backend's CSRF_TRUSTED_ORIGINS). */
export function getProxyOrigin(): string {
  if (process.env.FRONTEND_URL) return process.env.FRONTEND_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  if (process.env.NODE_ENV === 'production') return 'https://parwa.buzz';
  return 'http://localhost:3000';
}

/**
 * Extract Bearer token from the request's httpOnly cookies.
 * Delegates to the centralized getAccessTokenFromCookies() in auth-cookies.ts.
 */
export function getBearerToken(request: NextRequest | Request): string | null {
  return getAccessTokenFromCookies(request);
}

/**
 * Build standard proxy headers for a backend request.
 * Includes Origin, Referer, and Authorization if a token is found.
 */
export function buildProxyHeaders(request: NextRequest | Request): Record<string, string> {
  const origin = getProxyOrigin();
  const token = getBearerToken(request);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Origin': origin,
    'Referer': `${origin}/`,
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Proxy a request to the backend and return a NextResponse.
 *
 * @param backendPath - The full path on the backend (e.g. "/api/v1/billing/subscription")
 * @param method - HTTP method
 * @param request - The incoming Next.js request (for headers/body)
 * @param options - Optional: extraHeaders, timeout (default 15000ms)
 */
export async function proxyToBackend(
  backendPath: string,
  method: string,
  request: NextRequest | Request,
  options?: {
    extraHeaders?: Record<string, string>;
    timeout?: number;
  },
): Promise<NextResponse> {
  const backendUrl = getBackendUrl();
  const headers = buildProxyHeaders(request);
  const { extraHeaders = {}, timeout = 15000 } = options || {};

  // Forward cookies for session-based auth
  const cookie = request.headers.get('cookie') || '';
  if (cookie) {
    headers['Cookie'] = cookie;
  }

  Object.assign(headers, extraHeaders);

  let body: string | null = null;
  if (method !== 'GET' && method !== 'DELETE' && method !== 'HEAD') {
    try { body = await request.text(); } catch { /* no body */ }
  }

  try {
    const backendRes = await fetch(`${backendUrl}${backendPath}`, {
      method,
      headers,
      body,
      signal: AbortSignal.timeout(timeout),
    });

    const text = await backendRes.text();
    try {
      const data = JSON.parse(text);
      return NextResponse.json(data, { status: backendRes.status });
    } catch {
      return NextResponse.json(
        { error: { message: text || 'Backend returned non-JSON response' } },
        { status: backendRes.status },
      );
    }
  } catch {
    return NextResponse.json(
      { error: { message: 'Backend service unavailable. Please try again later.' } },
      { status: 503 },
    );
  }
}
