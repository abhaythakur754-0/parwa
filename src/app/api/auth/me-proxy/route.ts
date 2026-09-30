/**
 * PARWA Auth Me Proxy
 *
 * Proxies /api/auth/me-proxy to the backend's /api/auth/me endpoint.
 * Forwards the parwa_at cookie as a Bearer token for JWT verification.
 *
 * This is used by the AuthContext to verify the current session.
 * Since parwa_at now contains the BACKEND's JWT token, the backend
 * can successfully verify it.
 *
 * Local fallback (ENABLE_LOCAL_GOOGLE_AUTH=1 only): when the backend is
 * unreachable or rejects a locally-issued session token, the token is
 * verified locally (lib/jwt) and the user is loaded from the local DB.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';
import { getLocalUserFromToken } from '@/lib/local-auth';

function extractToken(req: NextRequest): string | null {
  const authHeader = req.headers.get('authorization');
  if (authHeader && authHeader.startsWith('Bearer ')) {
    return authHeader.slice(7);
  }
  const cookieToken = req.cookies.get('parwa_at')?.value;
  return cookieToken || null;
}

export async function GET(req: NextRequest) {
  const token = extractToken(req);

  if (!token) {
    return NextResponse.json(
      { status: 'error', message: 'Authentication required.' },
      { status: 401 }
    );
  }

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
      'Authorization': `Bearer ${token}`,
    };

    const res = await fetch(`${backendUrl}/api/auth/me`, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(8000),
    });

    if (res.ok) {
      // Safely parse JSON — guard against non-JSON responses (e.g. from proxy/gateway)
      try {
        const text = await res.text();
        const data = JSON.parse(text);
        return NextResponse.json(data, { status: 200 });
      } catch {
        console.error('[me-proxy] Backend returned 200 but non-JSON body');
      }
    }

    // ── Local fallback (gated) before surfacing the backend error ──
    const localUser = await getLocalUserFromToken(token, 'access');
    if (localUser) {
      return NextResponse.json(localUser, { status: 200 });
    }

    return NextResponse.json(
      { status: 'error', message: 'Authentication failed.' },
      { status: res.status === 401 ? 401 : 502 },
    );
  } catch (error) {
    console.error('[me-proxy] Backend unreachable:', error);

    // ── Local fallback (gated): backend is unreachable ──
    const localUser = await getLocalUserFromToken(token, 'access');
    if (localUser) {
      return NextResponse.json(localUser, { status: 200 });
    }

    return NextResponse.json(
      { status: 'error', message: 'Backend unreachable' },
      { status: 503 }
    );
  }
}
