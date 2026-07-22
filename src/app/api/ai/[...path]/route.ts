import { NextRequest, NextResponse } from 'next/server';

/**
 * AI proxy route.
 * Forwards /api/ai/* to backend /api/ai/* (instances, cost/budget, agents, etc.)
 * Includes Origin header and forwards auth cookie as Bearer token.
 *
 * On 401/403 (token expired), automatically refreshes the access token via
 * /api/auth/refresh and retries once (same pattern as /api/pipeline/[...path]
 * and /api/admin/[...path]).
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

function buildHeaders(cookie: string, origin: string, accessToken: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Origin': origin,
    'Referer': `${origin}/`,
  };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  if (cookie) {
    headers['Cookie'] = cookie;
  }
  return headers;
}

/**
 * Refresh the access token via /api/auth/refresh using the refresh-token cookie.
 * Returns the new cookie header string on success, or null on failure.
 *
 * Mirrors the implementation in /api/pipeline/[...path]/route.ts so all
 * proxy routes handle token expiry consistently.
 */
async function tryRefreshToken(
  origin: string,
  cookie: string,
): Promise<{ cookie: string; setCookies: string[] } | null> {
  try {
    const refreshRes = await fetch(
      `${process.env.NEXT_PUBLIC_APP_URL || origin}/api/auth/refresh`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Origin': origin,
          'Cookie': cookie,
        },
        body: '{}',
        signal: AbortSignal.timeout(10000),
      },
    );
    if (!refreshRes.ok) return null;

    const setCookies = refreshRes.headers.getSetCookie?.() || [];
    let newAt: string | null = null;
    const cookieParts: string[] = [];

    for (const sc of setCookies) {
      const nameMatch = sc.match(/^([^=]+)=/);
      if (nameMatch) {
        const name = nameMatch[1].trim();
        const valMatch = sc.match(/=([^;]*)/);
        const val = valMatch ? valMatch[1] : '';
        cookieParts.push(`${name}=${val}`);
        if (name === 'parwa_at') {
          newAt = val;
        }
      }
    }

    if (newAt) {
      return {
        cookie: cookieParts.length > 0 ? cookieParts.join('; ') : cookie,
        setCookies,
      };
    }
    return null;
  } catch {
    return null;
  }
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
    let accessToken = getAccessTokenFromCookie(cookie);
    let currentCookie = cookie;

    // ── First attempt ───────────────────────────────────────
    let backendRes = await fetch(`${backendUrl}${backendPath}`, {
      method,
      headers: buildHeaders(currentCookie, origin, accessToken),
      body,
      signal: AbortSignal.timeout(15000),
    });

    // ── Retry once on 401/403 if we had a token (likely expired) ──
    let refreshedSetCookies: string[] | null = null;
    if ((backendRes.status === 401 || backendRes.status === 403) && accessToken) {
      const refreshed = await tryRefreshToken(origin, currentCookie);
      if (refreshed) {
        currentCookie = refreshed.cookie;
        accessToken = getAccessTokenFromCookie(refreshed.cookie);
        refreshedSetCookies = refreshed.setCookies;
        backendRes = await fetch(`${backendUrl}${backendPath}`, {
          method,
          headers: buildHeaders(currentCookie, origin, accessToken),
          body,
          signal: AbortSignal.timeout(15000),
        });
      }
    }

    // Pass backend response through (success or error)
    const text = await backendRes.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: { message: text || 'Backend returned non-JSON response' } };
    }
    const response = NextResponse.json(data, { status: backendRes.status });
    // Forward refreshed Set-Cookie headers so the browser updates parwa_at / parwa_rt
    if (refreshedSetCookies) {
      for (const sc of refreshedSetCookies) {
        response.headers.append('Set-Cookie', sc);
      }
    }
    return response;
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
