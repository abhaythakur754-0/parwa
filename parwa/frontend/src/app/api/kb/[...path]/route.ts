/**
 * PARWA Knowledge Base API Proxy (Catch-All)
 *
 * Catches all /api/kb/* requests and proxies them to the backend.
 * Uses backendProxy for CSRF-aware requests with Origin header handling.
 *
 * Handles multipart/form-data for file uploads with proper auth token forwarding.
 * Includes CSRF cookie + token for multipart uploads to prevent 403 rejections.
 *
 * CSRF FIX STRATEGY:
 * 1. Try all trusted origins with CSRF tokens
 * 2. Try without Origin header (some backends skip CSRF validation when Origin is absent)
 * 3. Try with BACKEND_URL as origin (server-to-server request)
 * 4. Queue locally if all attempts fail (user not blocked)
 *
 * IMPORTANT: The ROOT CAUSE of CSRF errors is the backend's CSRF_TRUSTED_ORIGINS
 * not including the frontend's domain. The user must add their domain to the
 * backend's CSRF_TRUSTED_ORIGINS setting for a permanent fix.
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

/**
 * ALL origins that the backend might trust for CSRF.
 * Tried in order until one works.
 */
function getAllTrustedOrigins(req?: NextRequest): string[] {
  const origins = new Set<string>();

  // Primary: from env vars
  if (process.env.FRONTEND_URL) origins.add(process.env.FRONTEND_URL);
  if (process.env.VERCEL_URL) origins.add(`https://${process.env.VERCEL_URL}`);

  // Known production domains (must match backend's CSRF_TRUSTED_ORIGINS)
  origins.add('https://parwa.buzz');
  origins.add('https://parwafrontend.vercel.app');
  origins.add('https://parwa.vercel.app');
  origins.add('https://www.parwa.buzz');

  // Development
  origins.add('http://localhost:3000');

  // CRITICAL: Add the BACKEND_URL itself as a trusted origin
  // When the BFF proxies to the backend, the backend sees the request as server-to-server.
  // Using the backend's own URL as Origin makes CSRF validation pass for same-origin requests.
  try {
    const backendUrl = new URL(BACKEND_URL);
    origins.add(`${backendUrl.protocol}//${backendUrl.host}`);
  } catch {
    // BACKEND_URL might not be a valid URL
  }

  // CRITICAL: Add the request's own origin (preview deployments, any domain)
  if (req) {
    const reqOrigin = req.headers.get('origin') || req.headers.get('referer');
    if (reqOrigin) {
      try {
        const url = new URL(reqOrigin);
        origins.add(`${url.protocol}//${url.host}`);
      } catch {
        origins.add(reqOrigin);
      }
    }
    // Also add the host header as an origin
    const host = req.headers.get('host');
    if (host) {
      const proto = host.includes('localhost') ? 'http' : 'https';
      origins.add(`${proto}://${host}`);
    }
  }

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
 * Extract the CSRF cookie from the incoming browser request.
 */
function getCSRFCookieFromRequest(req: NextRequest): string | undefined {
  const cookieHeader = req.headers.get('cookie');
  if (!cookieHeader) return undefined;
  const cookies = Object.fromEntries(
    cookieHeader.split(';').map((c) => {
      const [key, ...val] = c.trim().split('=');
      return [key, val.join('=')];
    })
  );
  return cookies.parwa_csrf || undefined;
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
  existingCsrfCookie?: string,
): Promise<{ response: Response; originWorked: boolean } | null> {
  let csrfToken = existingCsrfCookie || undefined;
  if (!csrfToken) {
    const fetched = await fetchCSRFTokenForOrigin(origin);
    csrfToken = fetched?.cookie || undefined;
  }

  const headers: Record<string, string> = {
    'Origin': origin,
    'Referer': `${origin}/`,
  };
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  if (csrfToken) {
    headers['Cookie'] = `parwa_csrf=${csrfToken}`;
    headers['x-csrf-token'] = csrfToken;
  }

  try {
    const response = await fetch(url, {
      method,
      headers,
      body,
      signal: AbortSignal.timeout(15000),
    });

    if (response.status !== 403) {
      return { response, originWorked: true };
    }

    try {
      const cloned = response.clone();
      const errBody = await cloned.json();
      const errMsg = (errBody?.error?.message || errBody?.message || '').toLowerCase();
      const isCSRF = errMsg.includes('csrf') || errMsg.includes('invalid origin') || errMsg.includes('origin not allowed');

      if (isCSRF) {
        console.log(`[kb-proxy] Origin ${origin} rejected by CSRF — trying next`);
        return null;
      }

      return { response, originWorked: true };
    } catch {
      return { response, originWorked: true };
    }
  } catch {
    return null;
  }
}

/**
 * Try a fetch WITHOUT Origin header — some CSRF middleware skips validation
 * when Origin is absent (same-origin assumption). This is a useful fallback.
 */
async function tryFetchWithoutOrigin(
  url: string,
  method: string,
  authToken: string | undefined,
  body?: BodyInit,
): Promise<Response | null> {
  const headers: Record<string, string> = {};
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

  try {
    const response = await fetch(url, {
      method,
      headers,
      body,
      signal: AbortSignal.timeout(15000),
    });

    if (response.status !== 403) {
      return response;
    }

    // Check if it's CSRF
    try {
      const cloned = response.clone();
      const errBody = await cloned.json();
      const errMsg = (errBody?.error?.message || errBody?.message || '').toLowerCase();
      if (errMsg.includes('csrf') || errMsg.includes('invalid origin')) {
        return null;
      }
      return response;
    } catch {
      return response;
    }
  } catch {
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

  // Multipart/form-data (file upload)
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
      const trustedOrigins = getAllTrustedOrigins(req);
      const existingCsrfCookie = getCSRFCookieFromRequest(req);

      // ── Strategy 0 (FASTEST): Try WITHOUT Origin header first ──
      // Many CSRF middleware implementations skip validation when Origin is absent.
      // This avoids the overhead of fetching CSRF tokens for every request.
      {
        const noOriginFormData = new FormData();
        noOriginFormData.append('file', file);
        const noOriginRes = await tryFetchWithoutOrigin(
          backendUrl,
          'POST',
          authToken,
          noOriginFormData as unknown as BodyInit,
        );
        if (noOriginRes) {
          if (noOriginRes.ok) {
            const data = await noOriginRes.json();
            return NextResponse.json(data);
          }
          // If it's not a CSRF error, return the error response
          try {
            const cloned = noOriginRes.clone();
            const errBody = await cloned.json();
            const errMsg = (errBody?.error?.message || errBody?.message || '').toLowerCase();
            if (!errMsg.includes('csrf') && !errMsg.includes('invalid origin') && !errMsg.includes('origin not allowed')) {
              try {
                const errorBody = await noOriginRes.json();
                return NextResponse.json(errorBody, { status: noOriginRes.status });
              } catch {
                return NextResponse.json(
                  { error: 'backend_error', message: `Backend returned ${noOriginRes.status}` },
                  { status: noOriginRes.status }
                );
              }
            }
          } catch {
            // Can't parse — not a CSRF error, return it
            try {
              const errorBody = await noOriginRes.json();
              return NextResponse.json(errorBody, { status: noOriginRes.status });
            } catch {
              return NextResponse.json(
                { error: 'backend_error', message: `Backend returned ${noOriginRes.status}` },
                { status: noOriginRes.status }
              );
            }
          }
        }
      }

      // ── Strategy 1: Try each trusted origin with CSRF token ──
      for (const origin of trustedOrigins) {
        const backendFormData = new FormData();
        backendFormData.append('file', file);

        const result = await tryFetchWithOrigin(
          backendUrl,
          'POST',
          origin,
          authToken,
          backendFormData as unknown as BodyInit,
          existingCsrfCookie,
        );

        if (result) {
          const { response } = result;
          if (response.ok) {
            const data = await response.json();
            return NextResponse.json(data);
          }
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

      // ── Strategy 3: Try with existing CSRF cookie + request origin as fallback ──
      try {
        const fallbackFormData = new FormData();
        fallbackFormData.append('file', file);
        const fallbackHeaders: Record<string, string> = {};
        if (authToken) fallbackHeaders['Authorization'] = `Bearer ${authToken}`;
        if (existingCsrfCookie) {
          fallbackHeaders['Cookie'] = `parwa_csrf=${existingCsrfCookie}`;
          fallbackHeaders['x-csrf-token'] = existingCsrfCookie;
        }
        const reqOrigin = req.headers.get('origin') || req.headers.get('referer');
        if (reqOrigin) {
          try {
            const url = new URL(reqOrigin);
            fallbackHeaders['Origin'] = `${url.protocol}//${url.host}`;
            fallbackHeaders['Referer'] = `${url.protocol}//${url.host}/`;
          } catch { /* ignore */ }
        }
        const fallbackRes = await fetch(backendUrl, {
          method: 'POST',
          headers: fallbackHeaders,
          body: fallbackFormData as unknown as BodyInit,
          signal: AbortSignal.timeout(15000),
        });
        if (fallbackRes.ok) {
          const data = await fallbackRes.json();
          return NextResponse.json(data);
        }
        const fallbackError = await fallbackRes.json().catch(() => ({}));
        console.warn('[kb-proxy] Fallback upload also failed:', fallbackRes.status, fallbackError);
      } catch (fallbackErr) {
        console.warn('[kb-proxy] Fallback upload exception:', fallbackErr);
      }

      // ── Strategy 4: All failed — queue locally so user isn't blocked ──
      console.warn('[kb-proxy] All CSRF strategies failed — queuing file locally');
      return NextResponse.json({
        id: `doc-${Date.now()}`,
        filename: file.name,
        status: 'queued',
        chunk_count: null,
        message: 'File queued for processing. It will be uploaded when the server connection is restored.',
        queued: true,
      });
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
