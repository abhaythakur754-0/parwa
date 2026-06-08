/**
 * PARWA MFA Proxy Route
 *
 * Proxies all MFA-related requests to the backend.
 * This avoids CORS issues and prevents exposing the backend URL in client-side JS.
 *
 * Routes:
 *   POST /api/mfa/setup   → backend /api/v1/auth/mfa/setup
 *   POST /api/mfa/verify  → backend /api/v1/auth/mfa/verify
 *   POST /api/mfa/login   → backend /api/v1/auth/mfa/login
 *   POST /api/mfa/backup  → backend /api/v1/auth/mfa/backup
 *   POST /api/mfa/disable → backend /api/v1/auth/mfa/disable
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';
import { getAccessTokenFromCookies } from '@/lib/auth-cookies';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const action = path[0] || '';

  const validActions = ['setup', 'verify', 'login', 'backup', 'disable'];
  if (!validActions.includes(action)) {
    return NextResponse.json(
      { detail: `Invalid MFA action: ${action}` },
      { status: 400 }
    );
  }

  const backendPath = `/api/v1/auth/mfa/${action}`;
  const body = await request.text();
  const authToken = getAccessTokenFromCookies(request);

  try {
    const { response } = await backendProxy(backendPath, {
      method: 'POST',
      body,
      authToken: authToken || undefined,
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('MFA proxy error:', error);
    return NextResponse.json(
      { detail: 'MFA service unavailable. Please try again later.' },
      { status: 503 }
    );
  }
}
