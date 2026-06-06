/**
 * PARWA Auth Me Proxy
 *
 * Proxies /api/auth/me-proxy to the backend's /api/auth/me endpoint.
 * Forwards the parwa_at cookie as a Bearer token for JWT verification.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

export async function GET(req: NextRequest) {
  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
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

    const res = await fetch(`${BACKEND_URL}/api/auth/me`, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(8000),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    console.error('[me-proxy] Backend unreachable:', error);
    return NextResponse.json(
      { status: 'error', message: 'Backend unreachable' },
      { status: 503 }
    );
  }
}
