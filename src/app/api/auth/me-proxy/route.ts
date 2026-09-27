/**
 * PARWA Auth Me Proxy
 *
 * Proxies /api/auth/me-proxy to the backend's /api/auth/me endpoint.
 * Forwards the parwa_at cookie as a Bearer token for JWT verification.
 *
 * This is used by the AuthContext to verify the current session.
 * Since parwa_at now contains the BACKEND's JWT token, the backend
 * can successfully verify it.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

export async function GET(req: NextRequest) {
  try {
    const backendUrl = getBackendUrl();
    // Dynamic origin — matches whatever deployment we're on
    const origin = process.env.FRONTEND_URL
      || (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : '')
      || (process.env.NODE_ENV === 'production' ? 'https://parwa.buzz' : 'http://localhost:3000');
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Origin': origin,
      'Referer': `${origin}/`,
    };

    // Forward auth token from cookie
    const cookieHeader = req.headers.get('cookie');
    if (cookieHeader) {
      const cookies = Object.fromEntries(
        cookieHeader.split(';').map((c) => {
          const [key, ...val] = c.trim().split('=');
          return [key, val.join('=')];
        })
      );
      if (cookies.parwa_at) {
        headers['Authorization'] = `Bearer ${cookies.parwa_at}`;
      }
    }

    // Also check Authorization header
    const authHeader = req.headers.get('authorization');
    if (authHeader && !headers['Authorization']) {
      headers['Authorization'] = authHeader;
    }

    if (!headers['Authorization']) {
      return NextResponse.json(
        { status: 'error', message: 'Authentication required.' },
        { status: 401 }
      );
    }

    const res = await fetch(`${backendUrl}/api/auth/me`, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(8000),
    });

    // Safely parse JSON — guard against non-JSON responses (e.g. from proxy/gateway)
    let data: Record<string, unknown>;
    try {
      const text = await res.text();
      data = JSON.parse(text);
    } catch {
      console.error('[me-proxy] Backend returned non-JSON:', res.status);
      return NextResponse.json(
        { status: 'error', message: 'Authentication service unavailable.' },
        { status: 502 },
      );
    }

    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error('[me-proxy] Backend unreachable:', error);
    return NextResponse.json(
      { status: 'error', message: 'Backend unreachable' },
      { status: 503 }
    );
  }
}
