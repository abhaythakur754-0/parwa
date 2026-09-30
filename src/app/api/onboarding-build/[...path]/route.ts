/**
 * PARWA Onboarding Build Proxy Route
 *
 * Proxies agent+tool build orchestration requests to the backend.
 *
 * Routes (forwards to backend /api/onboarding-build/*):
 *   POST /api/onboarding-build/trigger  → create agents + tools from analysis
 *   GET  /api/onboarding-build/status   → poll build status (all agents ready?)
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';
import { getAccessTokenFromCookies } from '@/lib/auth-cookies';

async function proxyToBackend(
  request: NextRequest,
  pathSegments: string[],
  method: 'GET' | 'POST' | 'DELETE',
) {
  const fullPath = pathSegments.join('/');
  const backendPath = `/api/onboarding-build/${fullPath}`;
  const authToken = getAccessTokenFromCookies(request);

  const url = new URL(request.url);
  const searchParams = url.searchParams.toString();
  const fullBackendPath = `${backendPath}${searchParams ? `?${searchParams}` : ''}`;

  let body: string | undefined;
  if (method === 'POST') {
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
      return NextResponse.json(data, { status: response.status });
    } catch {
      return NextResponse.json(
        { error: { message: text || 'Backend returned non-JSON response' } },
        { status: response.status },
      );
    }
  } catch (error) {
    console.error('Onboarding build proxy error:', error);
    return NextResponse.json(
      { detail: 'Build service unavailable. Please try again later.' },
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
