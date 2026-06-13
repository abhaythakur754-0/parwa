/**
 * PARWA Knowledge Base API Proxy (Catch-All)
 *
 * Catches all /api/kb/* requests and proxies them to the backend.
 * Uses backendProxy for CSRF-aware requests with Origin header handling.
 *
 * Handles multipart/form-data for file uploads with proper auth token forwarding.
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

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
      const origin = process.env.FRONTEND_URL ||
        (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : null) ||
        (process.env.NODE_ENV === 'production' ? 'https://parwa.buzz' : 'http://localhost:3000');

      const headers: Record<string, string> = {
        'Origin': origin,
        'Referer': `${origin}/`,
      };
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

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

      // Try fallback origins if CSRF rejected
      if (backendRes.status === 403) {
        const fallbackOrigins = [
          'https://parwa.buzz',
          'https://parwa.vercel.app',
          'https://www.parwa.buzz',
        ].filter((o) => o !== origin);

        for (const fallbackOrigin of fallbackOrigins) {
          try {
            const retryHeaders: Record<string, string> = {
              'Origin': fallbackOrigin,
              'Referer': `${fallbackOrigin}/`,
            };
            if (authToken) retryHeaders['Authorization'] = `Bearer ${authToken}`;

            const retryRes = await fetch(`${BACKEND_URL}/api/v1/kb/${subPath}`, {
              method: 'POST',
              headers: retryHeaders,
              body: backendFormData as unknown as BodyInit,
            });

            if (retryRes.ok) {
              const data = await retryRes.json();
              return NextResponse.json(data);
            }

            if (retryRes.status !== 403) {
              // Non-CSRF error — return the error
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
