import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';

/**
 * KB catch-all proxy — forwards /api/kb/* to backend /api/kb/*
 * Handles: import-text, import-url, and any future KB endpoints
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
