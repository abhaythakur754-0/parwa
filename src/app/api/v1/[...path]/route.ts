import { NextRequest, NextResponse } from 'next/server';

/**
 * V1 API proxy route.
 * Forwards /api/v1/* to backend /api/v1/*
 * On 401/403, attempts token refresh then retries once.
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
 * Attempt to refresh the access token via /api/auth/refresh.
 * Returns an object with:
 *   - cookie: string to use for the retry request (new parwa_at merged)
 *   - setCookies: raw Set-Cookie header values to forward to the client browser
 * Or null on failure.
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

    // Extract new set-cookie headers to get the refreshed parwa_at
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
  const backendPath = `/api/v1/${fullPath}${queryString ? `?${queryString}` : ''}`;

  try {
    let body: string | null = null;
    if (method !== 'GET' && method !== 'DELETE') {
      try { body = await request.text(); } catch { /* no body */ }
    }

    const cookie = request.headers.get('cookie') || '';
    let accessToken = getAccessTokenFromCookie(cookie);
    let currentCookie = cookie;

    // POST requests trigger the sync pipeline (3-5s per ticket); when
    // multiple tickets are created in quick succession they queue on the
    // single uvicorn worker and need more than 15s to complete.
    // GET requests for ticket lists (page_size=50+) can be slow when the
    // DB is under load from pipeline workers — give them more time too.
    const isTicketList = method === 'GET' && fullPath.startsWith('tickets');
    const requestTimeout = method === 'POST' ? 45000 : (isTicketList ? 30000 : 15000);

    // ── First attempt ───────────────────────────────────────
    let backendRes = await fetch(`${backendUrl}${backendPath}`, {
      method,
      headers: buildHeaders(currentCookie, origin, accessToken),
      body,
      signal: AbortSignal.timeout(requestTimeout),
    });

    // ── Retry once on 401/403 if we had a token (likely expired) ──
    if ((backendRes.status === 401 || backendRes.status === 403) && accessToken) {
      const refreshed = await tryRefreshToken(origin, currentCookie);
      if (refreshed) {
        const newAccessToken = getAccessTokenFromCookie(refreshed.cookie);
        backendRes = await fetch(`${backendUrl}${backendPath}`, {
          method,
          headers: buildHeaders(refreshed.cookie, origin, newAccessToken),
          body,
          signal: AbortSignal.timeout(requestTimeout),
        });

        // If retry succeeded, forward the response AND the new cookies to the client
        if (backendRes.ok || backendRes.status < 500) {
          const text = await backendRes.text();
          let data: unknown;
          try {
            data = JSON.parse(text);
          } catch {
            data = { error: { message: text || 'Backend returned non-JSON response' } };
          }
          const response = NextResponse.json(data, { status: backendRes.status });
          // Forward Set-Cookie headers from the refresh response so the
          // browser updates its parwa_at / parwa_rt cookies. Without this,
          // the next request would 401 again (old expired cookie still in browser).
          for (const sc of refreshed.setCookies) {
            response.headers.append('Set-Cookie', sc);
          }
          return response;
        }
      }
    }

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
  } catch (error) {
    // ── Retry once on timeout — backend may be busy processing tickets ──
    // The queue stores all tickets, but the list endpoint can be slow when
    // workers are processing. Wait 2s and try again before giving up.
    if (method === 'GET') {
      try {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const retryRes = await fetch(`${backendUrl}${backendPath}`, {
          method,
          headers: buildHeaders(currentCookie, origin, accessToken),
          signal: AbortSignal.timeout(requestTimeout),
        });
        const retryText = await retryRes.text();
        try {
          const retryData = JSON.parse(retryText);
          return NextResponse.json(retryData, { status: retryRes.status });
        } catch {
          return NextResponse.json(
            { error: { message: retryText || 'Backend returned non-JSON response' } },
            { status: retryRes.status },
          );
        }
      } catch {
        // Retry also failed — fall through to 503
      }
    }
    return NextResponse.json(
      { error: { message: 'V1 API service unavailable. Please try again later.' } },
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