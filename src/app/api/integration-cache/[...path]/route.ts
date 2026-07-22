/**
 * PARWA Integration Cache API Proxy (Phase 7)
 *
 * Proxies integration cache management requests to the backend.
 *
 * Key endpoints:
 * - GET  /api/integration-cache/stats/{integration_type} — Cache statistics
 * - POST /api/integration-cache/invalidate — Invalidate cache entries
 * - GET  /api/integration-cache/health — Cache health for all integrations
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';

function getAuthToken(req: NextRequest): string | undefined {
  const authHeader = req.headers.get('authorization');
  if (authHeader) return authHeader.replace('Bearer ', '');

  const cookieHeader = req.headers.get('cookie');
  if (cookieHeader) {
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => {
        const [key, ...val] = c.trim().split('=');
        return [key, val.join('=')];
      })
    );
    if (cookies.parwa_at) return cookies.parwa_at;
  }
  return undefined;
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;
  const authToken = getAuthToken(req);

  try {
    const { response } = await backendProxy(`/api/v1/integration-cache${path}${searchParams}`, {
      method: 'GET',
      authToken,
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('[integration-cache][GET] Backend unavailable:', error);
    return NextResponse.json(
      { error: { code: 'BACKEND_UNAVAILABLE', message: 'Cache service unavailable' } },
      { status: 503 }
    );
  }
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const authToken = getAuthToken(req);

  try {
    const body = await req.json();
    const { response } = await backendProxy(`/api/v1/integration-cache${path}`, {
      method: 'POST',
      authToken,
      body: JSON.stringify(body),
      extraHeaders: { 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('[integration-cache][POST] Backend unavailable:', error);
    return NextResponse.json(
      { error: { code: 'BACKEND_UNAVAILABLE', message: 'Cache service unavailable' } },
      { status: 503 }
    );
  }
}
