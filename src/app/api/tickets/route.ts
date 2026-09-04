import { NextRequest, NextResponse } from 'next/server';

/**
 * GET /api/tickets
 * Proxies to backend GET /api/v1/tickets (list tickets with filters + pagination).
 *
 * Extracts JWT from cookie and forwards as Authorization: Bearer header.
 * On 401/403 from backend, attempts token refresh via /api/auth/refresh
 * and retries once. Forwards refreshed Set-Cookie headers to the client
 * so the browser updates parwa_at / parwa_rt.
 *
 * NOTE: We deliberately do NOT call requireAuth() here. The backend is the
 * source of truth for auth, and calling requireAuth locally would reject
 * expired-but-refreshable tokens before the refresh retry gets a chance
 * to run. The backend 401 → refresh → retry flow handles expiry cleanly.
 *
 * Query params (all optional, passed through to backend):
 *   status, priority, category, assigned_to, channel, customer_id,
 *   tags, is_spam, is_frozen, search, page, page_size, sort_by, sort_order
 *
 * See backend/app/api/tickets.py:list_tickets for the canonical implementation.
 */

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
}

function extractBearerToken(request: NextRequest): string | null {
  // 1. Try Authorization header (for API clients)
  const authHeader = request.headers.get('authorization');
  if (authHeader && authHeader.startsWith('Bearer ')) {
    return authHeader.slice(7);
  }
  // 2. Try parwa_at cookie (for browser sessions)
  const cookieHeader = request.headers.get('cookie') || '';
  const match = cookieHeader.match(/\bparwa_at=([^;]+)/);
  return match ? match[1] : null;
}

function getProxyOrigin(): string {
  if (process.env.FRONTEND_URL) return process.env.FRONTEND_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  if (process.env.NODE_ENV === 'production') return 'https://parwa.buzz';
  return 'http://localhost:3000';
}

function getAccessTokenFromCookie(cookieHeader: string): string | null {
  const match = cookieHeader.match(/(?:^|;\s*)parwa_at=([^;]+)/);
  return match ? match[1] : null;
}

/**
 * Refresh the access token via /api/auth/refresh using the refresh-token cookie.
 * Returns the new cookie string + Set-Cookie headers to forward to the client,
 * or null on failure. Mirrors /api/v1/[...path]/route.ts.
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
        if (name === 'parwa_at') newAt = val;
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

export async function GET(request: NextRequest) {
  const backendUrl = getBackendUrl();
  const origin = getProxyOrigin();
  const url = new URL(request.url);
  const queryString = url.searchParams.toString();

  // Forward all query params to backend
  const targetUrl = `${backendUrl}/api/v1/tickets${queryString ? '?' + queryString : ''}`;

  const cookie = request.headers.get('cookie') || '';
  let token = extractBearerToken(request) || getAccessTokenFromCookie(cookie);
  let currentCookie = cookie;

  const buildHeaders = (): Record<string, string> => {
    const h: Record<string, string> = {
      'Content-Type': 'application/json',
      Origin: origin,
    };
    if (token) h['Authorization'] = `Bearer ${token}`;
    return h;
  };

  try {
    let backendRes = await fetch(targetUrl, {
      method: 'GET',
      headers: buildHeaders(),
      signal: AbortSignal.timeout(15_000),
      redirect: 'manual',
    });

    // Retry once on 401/403 if we had a token (likely expired)
    let refreshedSetCookies: string[] | null = null;
    if ((backendRes.status === 401 || backendRes.status === 403) && token) {
      const refreshed = await tryRefreshToken(origin, currentCookie);
      if (refreshed) {
        currentCookie = refreshed.cookie;
        token = getAccessTokenFromCookie(refreshed.cookie);
        refreshedSetCookies = refreshed.setCookies;
        backendRes = await fetch(targetUrl, {
          method: 'GET',
          headers: buildHeaders(),
          signal: AbortSignal.timeout(15_000),
          redirect: 'manual',
        });
      }
    }

    const data = await backendRes.json();
    const response = NextResponse.json(data, { status: backendRes.status });
    if (refreshedSetCookies) {
      for (const sc of refreshedSetCookies) {
        response.headers.append('Set-Cookie', sc);
      }
    }
    return response;
  } catch (err) {
    // Timeout / network error — the backend may just be waking up (Render
    // free tier sleeps after idle). Wait briefly and retry ONCE before
    // declaring failure.
    console.error('[/api/tickets] Backend unreachable, retrying once:', err);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    try {
      const retryRes = await fetch(targetUrl, {
        method: 'GET',
        headers: buildHeaders(),
        signal: AbortSignal.timeout(15_000),
        redirect: 'manual',
      });
      const retryData = await retryRes.json();
      return NextResponse.json(retryData, { status: retryRes.status });
    } catch (retryErr) {
      console.error('[/api/tickets] Backend still unreachable:', retryErr);
      // HONEST failure: never fabricate an empty list — the UI must show
      // "service unavailable + Retry", not "No tickets yet" (real tickets
      // may exist in the DB).
      return NextResponse.json(
        {
          error: {
            code: 'BACKEND_UNAVAILABLE',
            message: 'Could not reach the ticket service. Your tickets are safe — please retry.',
          },
        },
        { status: 502 },
      );
    }
  }
}
