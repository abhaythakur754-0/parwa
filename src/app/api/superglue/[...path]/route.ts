/**
 * PARWA Superglue Systems Proxy Route
 *
 * Proxies all Superglue system-management requests to the backend.
 * Replaces the removed Nango OAuth layer.
 *
 * Routes (forwards to backend /api/superglue/*):
 *   GET    /api/superglue/systems/catalog   → backend /api/superglue/systems/catalog
 *   GET    /api/superglue/systems           → backend /api/superglue/systems
 *   POST   /api/superglue/systems           → backend /api/superglue/systems
 *   GET    /api/superglue/systems/{id}      → backend /api/superglue/systems/{id}
 *   DELETE /api/superglue/systems/{id}      → backend /api/superglue/systems/{id}
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';
import { getAccessTokenFromCookies } from '@/lib/auth-cookies';

async function proxyToBackend(
  request: NextRequest,
  pathSegments: string[],
  method: 'GET' | 'POST' | 'DELETE' | 'PATCH' | 'PUT',
) {
  const fullPath = pathSegments.join('/');
  const backendPath = `/api/superglue/${fullPath}`;
  const authToken = getAccessTokenFromCookies(request);

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
      return NextResponse.json(data, { status: response.status });
    } catch {
      return NextResponse.json(
        { error: { message: text || 'Backend returned non-JSON response' } },
        { status: response.status },
      );
    }
  } catch (error) {
    console.error('Superglue proxy error:', error);
    return NextResponse.json(
      { detail: 'Superglue service unavailable. Please try again later.' },
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
