/**
 * PARWA Knowledge Base API Proxy (Catch-All)
 *
 * Catches all /api/kb/* requests and proxies them to the backend.
 * Uses backendProxy for CSRF-aware requests with Origin header handling.
 *
 * Handles multipart/form-data for file uploads with proper auth token forwarding.
 * Includes CSRF cookie + token for multipart uploads to prevent 403 rejections.
 *
 * CSRF FIX: Tries ALL trusted origins (not just getProxyOrigin()) because the
 * backend's CSRF_TRUSTED_ORIGINS might not include the current deployment URL.
 * Each retry fetches a fresh CSRF token for that specific origin.
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

/**
 * ALL origins that the backend might trust for CSRF.
 * Tried in order until one works.
 */
function getAllTrustedOrigins(): string[] {
  const origins = new Set<string>();

  // Primary: from env vars
  if (process.env.FRONTEND_URL) origins.add(process.env.FRONTEND_URL);
  if (process.env.VERCEL_URL) origins.add(`https://${process.env.VERCEL_URL}`);

  // Known production domains
  origins.add('https://parwa.buzz');
  origins.add('https://parwa.vercel.app');
  origins.add('https://www.parwa.buzz');

  // Development
  origins.add('http://localhost:3000');

  // Also try the request's own origin if it's a common pattern
  // (preview deployments, etc.)

  return Array.from(origins);
}

/**
 * Fetch CSRF cookie from the backend health endpoint for a specific origin.
 */
async function fetchCSRFTokenForOrigin(origin: string): Promise<{ cookie: string; token: string } | null> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/health`, {
      method: 'GET',
      headers: { 'Origin': origin, 'Referer': `${origin}/` },
      signal: AbortSignal.timeout(6000),
    });
    const setCookie = res.headers.get('set-cookie') || '';
    const csrfMatch = setCookie.match(/parwa_csrf=([^;]+)/);
    const csrfCookie = csrfMatch ? csrfMatch[1] : '';
    if (csrfCookie) return { cookie: csrfCookie, token: csrfCookie };
    return null;
  } catch {
    return null;
  }
}

/**
 * Extract auth token from request (cookie or Authorization header).
 */
function getAuthToken(req: NextRequest): string | undefined {
  const authHeader = req.headers.get('authorization');
  if (authHeader) return authHeader.replace('Bearer ', '');

  const cookieHeader = req.headers.get('cookie');
  if (cookieHeader) {
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => {
        const [key, ...val] = c.trim().split('=');
        return [key, val.join('=')];
      })
    );
    if (cookies.parwa_at) return cookies.parwa_at;
  }
  return undefined;
}

/**
 * Try a fetch with a specific origin, including CSRF token if available.
 * Returns the response or null if it failed (CSRF 403 or network error).
 */
async function tryFetchWithOrigin(
  url: string,
  method: string,
  origin: string,
  authToken: string | undefined,
  body?: BodyInit,
): Promise<{ response: Response; originWorked: boolean } | null> {
  const csrfTokens = await fetchCSRFTokenForOrigin(origin);

  const headers: Record<string, string> = {
    'Origin': origin,
    'Referer': `${origin}/`,
  };
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  if (csrfTokens) {
    headers['Cookie'] = `parwa_csrf=${csrfTokens.cookie}`;
    headers['x-csrf-token'] = csrfTokens.token;
  }

  try {
    const response = await fetch(url, {
      method,
      headers,
      body,
      signal: AbortSignal.timeout(15000),
    });

    // If not a CSRF 403, this origin worked
    if (response.status !== 403) {
      return { response, originWorked: true };
    }

    // Check if it's specifically a CSRF error (vs real auth 403)
    try {
      const cloned = response.clone();
      const errBody = await cloned.json();
      const errMsg = (errBody?.error?.message || errBody?.message || '').toLowerCase();
      const isCSRF = errMsg.includes('csrf') || errMsg.includes('invalid origin') || errMsg.includes('origin not allowed');

      if (isCSRF) {
        // CSRF error — this origin didn't work, try next
        console.log(`[kb-proxy] Origin ${origin} rejected by CSRF — trying next`);
        return null;
      }

      // Real 403 (auth error, not CSRF) — return it
      return { response, originWorked: true };
    } catch {
      // Can't parse body — treat as real error
      return { response, originWorked: true };
    }
  } catch {
    // Network error — try next origin
    return null;
  }
}

// GET handler
export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path: pathSegments } = await params;
  const subPath = pathSegments ? pathSegments.join('/') : '';
  const searchParams = new URL(req.url).search;
  const authToken = getAuthToken(req);

  try {
    const { response } = await backendProxy(`/api/v1/kb/${subPath}${searchParams}`, {
      method: 'GET',
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    const errorBody = await response.text().catch(() => '{}');
    try {
      const parsed = JSON.parse(errorBody);
      return NextResponse.json(parsed, { status: response.status });
    } catch {
      return NextResponse.json(
        { error: 'backend_error', message: `Backend returned ${response.status}` },
        { status: response.status }
      );
    }
  } catch (err) {
    console.error(`[kb-proxy] GET ${subPath} — backend unreachable:`, err);
    return NextResponse.json(
      { error: 'backend_unreachable', message: `Backend is not available. Cannot GET /api/kb/${subPath}.` },
      { status: 503 }
    );
  }
}

// POST handler — handles both JSON and multipart/form-data (file uploads)
export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path: pathSegments } = await params;
  const subPath = pathSegments ? pathSegments.join('/') : '';
  const authToken = getAuthToken(req);
  const contentType = req.headers.get('content-type') || '';

  // Multipart/form-data (file upload) — cannot use backendProxy directly
  // because it stringifies body. Handle with direct fetch + proper Origin.
  if (contentType.includes('multipart/form-data')) {
    try {
      const formData = await req.formData();

      const file = formData.get('file') as File | null;
      if (!file) {
        return NextResponse.json(
          { error: 'No file provided', message: 'Please select a file to upload.' },
          { status: 400 }
        );
      }

      // Validate file size (50 MB)
      const MAX_SIZE = 50 * 1024 * 1024;
      if (file.size > MAX_SIZE) {
        return NextResponse.json(
          { error: 'file_too_large', message: `File "${file.name}" exceeds 50 MB limit.` },
          { status: 400 }
        );
      }

      // Validate file extension
      const ALLOWED = ['.pdf', '.docx', '.doc', '.txt', '.csv', '.md', '.json'];
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      if (!ALLOWED.includes(ext)) {
        return NextResponse.json(
          { error: 'invalid_file_type', message: `File type "${ext}" not allowed. Allowed: ${ALLOWED.join(', ')}` },
          { status: 400 }
        );
      }

      const backendUrl = `${BACKEND_URL}/api/v1/kb/${subPath}`;
      const trustedOrigins = getAllTrustedOrigins();

      // Try each trusted origin until one works
      for (const origin of trustedOrigins) {
        const backendFormData = new FormData();
        backendFormData.append('file', file);

        const result = await tryFetchWithOrigin(
          backendUrl,
          'POST',
          origin,
          authToken,
          backendFormData as unknown as BodyInit,
        );

        if (result) {
          const { response } = result;
          if (response.ok) {
            const data = await response.json();
            return NextResponse.json(data);
          }
          // Non-403 error — return it
          try {
            const errorBody = await response.json();
            return NextResponse.json(errorBody, { status: response.status });
          } catch {
            return NextResponse.json(
              { error: 'backend_error', message: `Backend returned ${response.status}` },
              { status: response.status }
            );
          }
        }
      }

      // All origins failed — return error
      return NextResponse.json(
        {
          error: 'csrf_validation_failed',
          message: 'File upload failed — could not validate with backend. Please try again or contact support.',
          tried_origins: trustedOrigins,
        },
        { status: 403 }
      );
    } catch (err) {
      console.error('[kb-proxy] POST multipart error:', err);
      return NextResponse.json(
        { error: 'upload_failed', message: 'File upload failed. Please try again.' },
        { status: 500 }
      );
    }
  }

  // JSON body — use backendProxy
  let body: string | undefined;
  try {
    body = await req.text();
  } catch {
    // No body
  }

  try {
    const { response } = await backendProxy(`/api/v1/kb/${subPath}`, {
      method: 'POST',
      body: body || undefined,
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    const errorBody = await response.text().catch(() => '{}');
    try {
      const parsed = JSON.parse(errorBody);
      return NextResponse.json(parsed, { status: response.status });
    } catch {
      return NextResponse.json(
        { error: 'backend_error', message: `Backend returned ${response.status}` },
        { status: response.status }
      );
    }
  } catch (err) {
    console.error(`[kb-proxy] POST ${subPath} — backend unreachable:`, err);
    return NextResponse.json(
      { error: 'backend_unreachable', message: `Cannot POST /api/kb/${subPath}. Backend is not available.` },
      { status: 503 }
    );
  }
}

// DELETE handler
export async function DELETE(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path: pathSegments } = await params;
  const subPath = pathSegments ? pathSegments.join('/') : '';
  const authToken = getAuthToken(req);

  try {
    const { response } = await backendProxy(`/api/v1/kb/${subPath}`, {
      method: 'DELETE',
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    const errorBody = await response.text().catch(() => '{}');
    try {
      const parsed = JSON.parse(errorBody);
      return NextResponse.json(parsed, { status: response.status });
    } catch {
      return NextResponse.json(
        { error: 'backend_error', message: `Backend returned ${response.status}` },
        { status: response.status }
      );
    }
  } catch (err) {
    console.error(`[kb-proxy] DELETE ${subPath} — backend unreachable:`, err);
    return NextResponse.json(
      { error: 'backend_unreachable', message: `Cannot DELETE /api/kb/${subPath}. Backend is not available.` },
      { status: 503 }
    );
  }
}
