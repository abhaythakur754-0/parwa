import { NextRequest, NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';
import { getBackendUrl } from '@/lib/backend-url';
import { getBearerToken, getProxyOrigin } from '@/lib/bff-proxy';

/**
 * Analytics catch-all proxy route.
 * Proxies /api/analytics/* to backend /analytics/tickets/*
 */

export async function GET(request: NextRequest) {
  const authError = await requireAuth(request);
  if (authError) return authError;

  const backendUrl = getBackendUrl();
  const url = new URL(request.url);

  const pathSegments = url.pathname
    .replace('/api/analytics/', '')
    .split('/')
    .filter(Boolean);

  const backendPath = pathSegments.join('/');
  const queryString = url.searchParams.toString();
  const fullBackendUrl = `${backendUrl}/analytics/tickets/${backendPath}${queryString ? '?' + queryString : ''}`;

  const token = getBearerToken(request);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Origin: getProxyOrigin(),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const backendRes = await fetch(fullBackendUrl, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(15_000),
      redirect: 'manual',
    });

    const data = await backendRes.json();
    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    return NextResponse.json(
      { error: 'Backend unavailable', message: err instanceof Error ? err.message : 'Unknown error' },
      { status: 502 },
    );
  }
}

export async function POST(request: NextRequest) {
  const authError = await requireAuth(request);
  if (authError) return authError;

  const backendUrl = getBackendUrl();
  const url = new URL(request.url);

  const pathSegments = url.pathname
    .replace('/api/analytics/', '')
    .split('/')
    .filter(Boolean);

  const backendPath = pathSegments.join('/');
  const queryString = url.searchParams.toString();
  const fullBackendUrl = `${backendUrl}/analytics/tickets/${backendPath}${queryString ? '?' + queryString : ''}`;

  const token = getBearerToken(request);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Origin: getProxyOrigin(),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const body = await request.text();
    const backendRes = await fetch(fullBackendUrl, {
      method: 'POST',
      headers,
      body,
      signal: AbortSignal.timeout(15_000),
      redirect: 'manual',
    });

    const data = await backendRes.json();
    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    return NextResponse.json(
      { error: 'Backend unavailable', message: err instanceof Error ? err.message : 'Unknown error' },
      { status: 502 },
    );
  }
}
