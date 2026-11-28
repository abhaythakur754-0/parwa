/**
 * SHOBH MFA Proxy Route
 *
 * Proxies all MFA-related requests to the backend.
 * This avoids CORS issues and prevents exposing the backend URL in client-side JS.
 *
 * Routes (forwards full path to backend /api/auth/mfa/*):
 *   POST /api/mfa/setup/initiate   → backend /api/auth/mfa/setup/initiate
 *   POST /api/mfa/setup/verify     → backend /api/auth/mfa/setup/verify
 *   POST /api/mfa/verify           → backend /api/auth/mfa/verify
 *   POST /api/mfa/login            → backend /api/auth/mfa/login
 *   GET  /api/mfa/backup-codes     → backend /api/auth/mfa/backup-codes
 *   POST /api/mfa/backup-codes/use → backend /api/auth/mfa/backup-codes/use
 *   POST /api/mfa/backup-codes/regenerate → backend /api/auth/mfa/backup-codes/regenerate
 *   DELETE /api/mfa/sessions/{id}/revoke → backend /api/auth/mfa/sessions/{id}/revoke
 *   GET  /api/mfa/sessions         → backend /api/auth/mfa/sessions
 *
 * Backend router (backend/app/api/mfa.py) is mounted with prefix="/api/auth".
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';
import { getAccessTokenFromCookies, setAuthCookies } from '@/lib/auth-cookies';

async function proxyToBackend(
  request: NextRequest,
  pathSegments: string[],
  method: 'GET' | 'POST' | 'DELETE' | 'PATCH' | 'PUT',
) {
  const fullPath = pathSegments.join('/');
  const backendPath = `/api/auth/mfa/${fullPath}`;
  const authToken = getAccessTokenFromCookies(request);

  // Capture query string
  const url = new URL(request.url);
  const searchParams = url.searchParams.toString();
  const fullBackendPath = `${backendPath}${searchParams ? `?${searchParams}` : ''}`;

  let body: string | undefined;
  if (method !== 'GET' && method !== 'DELETE') {
    try { body = await request.text(); } catch { /* no body */ }
  }

  try {
    const { response } = await backendProxy(fullBackendPath, {
      method,
      body,
      authToken: authToken || undefined,
    });

    const text = await response.text();
    try {
      const data = JSON.parse(text);
      const isPreAuthCompletion =
        (pathSegments.length === 1 && pathSegments[0] === 'verify') ||
        (pathSegments.length === 2 && pathSegments[0] === 'backup' && pathSegments[1] === 'verify');
      if (response.ok && isPreAuthCompletion) {
        if (data.verified !== true || typeof data.access_token !== 'string' ||
            typeof data.refresh_token !== 'string' || !data.user) {
          return NextResponse.json({ detail: 'MFA verification did not produce a valid authenticated session.' }, { status: 502 });
        }
        const userData = { id: data.user.id, email: data.user.email, fullName: data.user.full_name, isVerified: data.user.is_verified ?? false };
        const authenticated = NextResponse.json({ verified: true, user: userData, remaining: data.remaining });
        setAuthCookies(authenticated, data.access_token, data.refresh_token, userData, Number(data.expires_in) || undefined);
        return authenticated;
      }
      return NextResponse.json(data, { status: response.status });
    } catch {
      return NextResponse.json(
        { error: { message: text || 'Backend returned non-JSON response' } },
        { status: response.status },
      );
    }
  } catch (error) {
    console.error('MFA proxy error:', error);
    return NextResponse.json(
      { detail: 'MFA service unavailable. Please try again later.' },
      { status: 503 },
    );
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyToBackend(request, path, 'POST');
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyToBackend(request, path, 'GET');
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyToBackend(request, path, 'DELETE');
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyToBackend(request, path, 'PATCH');
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyToBackend(request, path, 'PUT');
}
