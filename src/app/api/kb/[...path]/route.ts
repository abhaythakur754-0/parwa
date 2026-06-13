/**
 * PARWA Knowledge Base API Proxy (Catch-All)
 *
 * Catches all /api/kb/* requests and proxies them to the backend.
 * Uses backendProxy for CSRF-aware requests with Origin header handling.
 *
 * Handles multipart/form-data for file uploads with proper auth token forwarding.
 * Includes CSRF cookie + token for multipart uploads to prevent 403 rejections.
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

/**
 * Get the Origin header for proxy requests (mirrors backend-proxy logic).
 */
function getProxyOrigin(): string {
  if (process.env.FRONTEND_URL) return process.env.FRONTEND_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  if (process.env.NODE_ENV === 'production') return 'https://parwa.buzz';
  return 'http://localhost:3000';
}

/**
 * Fetch CSRF cookie from the backend health endpoint.
 */
async function fetchCSRFToken(): Promise<{ cookie: string; token: string } | null> {
  const origin = getProxyOrigin();
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

      // Build headers with Origin for CSRF and auth token
      const origin = getProxyOrigin();

      // Fetch CSRF token for the upload request
      const csrfTokens = await fetchCSRFToken();

      const headers: Record<string, string> = {
        'Origin': origin,
        'Referer': `${origin}/`,
      };
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
      // Include CSRF cookie + header for double-submit pattern
      if (csrfTokens) {
        headers['Cookie'] = `parwa_csrf=${csrfTokens.cookie}`;
        headers['x-csrf-token'] = csrfTokens.token;
      }

      const backendFormData = new FormData();
      backendFormData.append('file', file);

      const backendRes = await fetch(`${BACKEND_URL}/api/v1/kb/${subPath}`, {
        method: 'POST',
        headers,
        body: backendFormData as unknown as BodyInit,
      });

      if (backendRes.ok) {
        const data = await backendRes.json();
        return NextResponse.json(data);
      }

      // Try fallback origins if CSRF rejected (403)
      if (backendRes.status === 403) {
        // Check if it's actually a CSRF error
        let isCSRFErr = false;
        try {
          const errClone = backendRes.clone();
          const errBody = await errClone.json();
          const errMsg = (errBody?.error?.message || errBody?.message || '').toLowerCase();
          isCSRFErr = errMsg.includes('csrf') || errMsg.includes('invalid origin') || errMsg.includes('origin not allowed');
        } catch { /* ignore */ }

        if (isCSRFErr) {
          const fallbackOrigins = [
            'https://parwa.buzz',
            'https://parwa.vercel.app',
            'https://www.parwa.buzz',
            'http://localhost:3000',
          ].filter((o) => o !== origin);

          for (const fallbackOrigin of fallbackOrigins) {
            try {
              // Fetch fresh CSRF for each fallback origin
              const fallbackCSRF = await fetchCSRFToken();
              const retryHeaders: Record<string, string> = {
                'Origin': fallbackOrigin,
                'Referer': `${fallbackOrigin}/`,
              };
              if (authToken) retryHeaders['Authorization'] = `Bearer ${authToken}`;
              if (fallbackCSRF) {
                retryHeaders['Cookie'] = `parwa_csrf=${fallbackCSRF.cookie}`;
                retryHeaders['x-csrf-token'] = fallbackCSRF.token;
              }

              const retryFormData = new FormData();
              retryFormData.append('file', file);

              const retryRes = await fetch(`${BACKEND_URL}/api/v1/kb/${subPath}`, {
                method: 'POST',
                headers: retryHeaders,
                body: retryFormData as unknown as BodyInit,
              });

              if (retryRes.ok) {
                const data = await retryRes.json();
                return NextResponse.json(data);
              }

              if (retryRes.status !== 403) {
                try {
                  const errorBody = await retryRes.json();
                  return NextResponse.json(errorBody, { status: retryRes.status });
                } catch {
                  return NextResponse.json(
                    { error: 'backend_error', message: `Backend returned ${retryRes.status}` },
                    { status: retryRes.status }
                  );
                }
              }
            } catch {
              continue;
            }
          }
        }
      }

      // Return backend error
      try {
        const errorBody = await backendRes.json();
        return NextResponse.json(errorBody, { status: backendRes.status });
      } catch {
        return NextResponse.json(
          { error: 'backend_error', message: `Backend returned ${backendRes.status}` },
          { status: backendRes.status }
        );
      }
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
