import { NextRequest, NextResponse } from 'next/server';

/**
 * AI proxy route.
 * Forwards /api/ai/* to backend /api/ai/* (instances, cost/budget, agents, etc.)
 * Includes Origin header and forwards auth cookie as Bearer token.
 *
 * NOTE: /api/ai/instances has a dedicated route with local DB fallback.
 * This catch-all handles all other /api/ai/* paths.
 */

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
}

function getProxyOrigin(): string {
  if (process.env.FRONTEND_URL) return process.env.FRONTEND_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  if (process.env.NODE_ENV === 'production') return 'https://parwa.buzz';
  return 'http://localhost:3000';
}

/**
 * Extract access token from cookies.
 */
function getAccessTokenFromCookie(cookieHeader: string): string | null {
  const match = cookieHeader.match(/(?:^|;\s*)parwa_at=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function proxyRequest(
  method: string,
  request: NextRequest,
  pathSegments: string[],
) {
  const backendUrl = getBackendUrl();
  const origin = getProxyOrigin();
  const fullPath = pathSegments.join('/');
  const url = new URL(request.url);
  const queryString = url.searchParams.toString();
  const backendPath = `/api/ai/${fullPath}${queryString ? `?${queryString}` : ''}`;

  try {
    let body: string | null = null;
    if (method !== 'GET' && method !== 'DELETE') {
      try { body = await request.text(); } catch { /* no body */ }
    }

    const cookie = request.headers.get('cookie') || '';
    const accessToken = getAccessTokenFromCookie(cookie);

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Origin': origin,
      'Referer': `${origin}/`,
    };

    // Forward auth token — Bearer auth bypasses CSRF
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    // Also forward cookies for session-based auth
    if (cookie) {
      headers['Cookie'] = cookie;
    }

    const backendRes = await fetch(`${backendUrl}${backendPath}`, {
      method,
      headers,
      body,
      signal: AbortSignal.timeout(15000),
    });

    // If backend returned a successful response, pass it through
    if (backendRes.ok) {
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
    }

    // Backend returned an error — return it to the client
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
      { error: { message: 'AI service unavailable. Please try again later.' } },
      { status: 503 },
    );
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest('GET', request, path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest('POST', request, path);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest('PATCH', request, path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest('DELETE', request, path);
}
