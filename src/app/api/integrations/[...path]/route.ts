/**
 * PARWA Integrations Actions API Proxy (catch-all)
 *
 * Forwards /api/integrations/{crm,ecommerce,carrier}/* to the backend's
 * corresponding action routers (backend/app/api/{crm,ecommerce,carrier}_actions.py).
 *
 * Specific routes like /api/integrations/[id], /api/integrations/available,
 * /api/integrations/catalog, /api/integrations/custom/*, and
 * /api/integrations/webhooks/* are handled by their own route.ts files and
 * take priority over this catch-all (Next.js routing rule).
 *
 * On 401/403, attempts token refresh then retries once (same pattern as
 * the v1/[...path] proxy).
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

function getAccessTokenFromCookie(cookieHeader: string): string | null {
  const match = cookieHeader.match(/(?:^|;\s*)parwa_at=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function buildHeaders(cookie: string, accessToken: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  if (cookie) {
    headers['Cookie'] = cookie;
  }
  return headers;
}

async function tryRefreshToken(origin: string, cookie: string): Promise<string | null> {
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
      return cookieParts.length > 0 ? cookieParts.join('; ') : cookie;
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
  const origin = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
  const fullPath = pathSegments.join('/');
  const url = new URL(request.url);
  const queryString = url.searchParams.toString();
  const backendPath = `/api/integrations/${fullPath}${queryString ? `?${queryString}` : ''}`;

  try {
    let body: string | null = null;
    if (method !== 'GET' && method !== 'DELETE') {
      try { body = await request.text(); } catch { /* no body */ }
    }

    const cookie = request.headers.get('cookie') || '';
    let accessToken = getAccessTokenFromCookie(cookie);
    let currentCookie = cookie;

    // ── First attempt ───────────────────────────────────────
    let backendRes = await fetch(`${BACKEND_URL}${backendPath}`, {
      method,
      headers: buildHeaders(currentCookie, accessToken),
      body,
      signal: AbortSignal.timeout(15000),
    });

    // ── Retry once on 401/403 if we had a token (likely expired) ──
    if ((backendRes.status === 401 || backendRes.status === 403) && accessToken) {
      const refreshedCookie = await tryRefreshToken(origin, currentCookie);
      if (refreshedCookie) {
        const newAccessToken = getAccessTokenFromCookie(refreshedCookie);
        backendRes = await fetch(`${BACKEND_URL}${backendPath}`, {
          method,
          headers: buildHeaders(refreshedCookie, newAccessToken),
          body,
          signal: AbortSignal.timeout(15000),
        });
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
  } catch {
    return NextResponse.json(
      { error: { message: 'Integrations API service unavailable. Please try again later.' } },
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

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest('PUT', request, path);
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
