import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

/**
 * KB catch-all proxy — forwards /api/kb/* to backend /api/kb/*
 * Handles: upload (multipart), import-text, import-url, and any future KB endpoints
 */
function getProxyOrigin(): string {
  if (process.env.FRONTEND_URL) return process.env.FRONTEND_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  if (process.env.NODE_ENV === 'production') return 'https://parwa.buzz';
  return 'http://localhost:3000';
}

function buildAuthHeaders(req: NextRequest): Record<string, string> {
  const headers: Record<string, string> = {
    'Origin': getProxyOrigin(),
    'Referer': `${getProxyOrigin()}/`,
  };
  const authHeader = req.headers.get('authorization');
  if (authHeader) headers['Authorization'] = authHeader;
  const cookieHeader = req.headers.get('cookie');
  if (cookieHeader) {
    headers['Cookie'] = cookieHeader;
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => {
        const [k, ...v] = c.trim().split('=');
        return [k, v.join('=')];
      })
    );
    if (cookies.parwa_at) headers['Authorization'] = `Bearer ${cookies.parwa_at}`;
  }
  return headers;
}

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

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const path = url.pathname.replace('/api/kb', '');
  const searchParams = url.search;
  const authToken = getAuthToken(req);

  try {
    const { response } = await backendProxy(`/api/kb${path}${searchParams}`, {
      method: 'GET',
      authToken,
    });
    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }
    return NextResponse.json(
      await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` })),
      { status: response.status }
    );
  } catch (err) {
    console.error(`[kb-proxy] GET ${path} failed:`, err);
    return NextResponse.json(
      { error: 'backend_unreachable', message: 'Backend is not available.' },
      { status: 503 }
    );
  }
}

export async function POST(req: NextRequest) {
  const url = new URL(req.url);
  const path = url.pathname.replace('/api/kb', '');
  const searchParams = url.search;
  const authToken = getAuthToken(req);
  const contentType = req.headers.get('content-type') || '';

  // ── MULTIPART PASSTHROUGH (file uploads) ─────────────────────
  // 2026-09-10 FIX: backendProxy reads the body as text and hardcodes
  // 'Content-Type: application/json', destroying multipart/form-data
  // uploads — FastAPI answered 422 and a phantom "Failed" KB row was
  // created. For multipart we stream the RAW bytes through with the
  // ORIGINAL content-type header (boundary included), mirroring the
  // working create-text route pattern.
  if (contentType.startsWith('multipart/form-data')) {
    try {
      const bodyBytes = await req.arrayBuffer();
      const headers = buildAuthHeaders(req);
      headers['Content-Type'] = contentType; // keep original boundary
      const res = await fetch(`${BACKEND_URL}/api/kb${path}${searchParams}`, {
        method: 'POST',
        headers,
        body: bodyBytes,
        signal: AbortSignal.timeout(60000),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const payload =
          typeof data === 'object' && data !== null && Object.keys(data).length > 0
            ? data
            : { detail: `Request failed with status ${res.status}` };
        return NextResponse.json(payload, { status: res.status });
      }
      return NextResponse.json(data);
    } catch (err) {
      console.error(`[kb-proxy] POST(multipart) ${path} failed:`, err);
      return NextResponse.json(
        { error: 'backend_unreachable', message: 'Backend is not available.' },
        { status: 503 }
      );
    }
  }

  // ── JSON PATH (import-text, import-url, etc.) ────────────────
  let body: string | undefined;
  try {
    body = await req.text();
  } catch {
    // No body
  }

  try {
    const { response } = await backendProxy(`/api/kb${path}${searchParams}`, {
      method: 'POST',
      body: body || undefined,
      authToken,
    });
    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }
    return NextResponse.json(
      await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` })),
      { status: response.status }
    );
  } catch (err) {
    console.error(`[kb-proxy] POST ${path} failed:`, err);
    return NextResponse.json(
      { error: 'backend_unreachable', message: 'Backend is not available.' },
      { status: 503 }
    );
  }
}

export async function DELETE(req: NextRequest) {
  const url = new URL(req.url);
  const path = url.pathname.replace('/api/kb', '');
  const searchParams = url.search;
  const authToken = getAuthToken(req);

  try {
    const { response } = await backendProxy(`/api/kb${path}${searchParams}`, {
      method: 'DELETE',
      authToken,
    });
    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }
    return NextResponse.json(
      await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` })),
      { status: response.status }
    );
  } catch (err) {
    console.error(`[kb-proxy] DELETE ${path} failed:`, err);
    return NextResponse.json(
      { error: 'backend_unreachable', message: 'Backend is not available.' },
      { status: 503 }
    );
  }
}
