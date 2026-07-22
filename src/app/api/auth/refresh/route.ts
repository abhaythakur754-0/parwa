/**
 * PARWA Token Refresh API Route
 *
 * Proxies POST /api/auth/refresh to the backend.
 * The backend reads the refresh token from the httpOnly parwa_rt cookie
 * and sets new httpOnly cookies (parwa_at, parwa_rt) on the response.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

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

export async function POST(request: NextRequest) {
  const backendUrl = getBackendUrl();
  const origin = getProxyOrigin();

  const cookie = request.headers.get('cookie') || '';
  const accessToken = getAccessTokenFromCookie(cookie);

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

  try {
    const backendRes = await fetch(`${backendUrl}/api/auth/refresh`, {
      method: 'POST',
      headers,
      body: '{}',
      signal: AbortSignal.timeout(15000),
    });

    const text = await backendRes.text();

    try {
      const data = JSON.parse(text);
      const response = NextResponse.json(data, { status: backendRes.status });

      // Forward any Set-Cookie headers from the backend (new tokens)
      const setCookies = backendRes.headers.getSetCookie?.() || [];
      for (const sc of setCookies) {
        response.headers.append('Set-Cookie', sc);
      }

      return response;
    } catch {
      return NextResponse.json(
        { error: { message: text || 'Backend returned non-JSON response' } },
        { status: backendRes.status },
      );
    }
  } catch {
    return NextResponse.json(
      { error: { message: 'Refresh service unavailable.' } },
      { status: 503 },
    );
  }
}