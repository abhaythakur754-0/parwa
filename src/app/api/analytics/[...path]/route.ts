import { NextRequest, NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';

/**
 * Analytics catch-all proxy route.
 *
 * Proxies /api/analytics/* to backend /analytics/tickets/*
 * Extracts JWT from cookie and forwards as Authorization: Bearer header
 * because the backend's tenant middleware reads Bearer tokens, not cookies.
 */

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
}

/**
 * Extract the access token (JWT) from the parwa_at cookie.
 */
function extractBearerToken(request: NextRequest): string | null {
  const cookieHeader = request.headers.get('cookie') || '';
  const match = cookieHeader.match(/\bparwa_at=([^;]+)/);
  return match ? match[1] : null;
}

export async function GET(request: NextRequest) {
  const authError = await requireAuth(request);
  if (authError) return authError;

  const backendUrl = getBackendUrl();
  const url = new URL(request.url);

  // Extract the catch-all path segments
  const pathSegments = url.pathname
    .replace('/api/analytics/', '')
    .split('/')
    .filter(Boolean);

  const backendPath = pathSegments.join('/');
  const queryString = url.searchParams.toString();
  const fullBackendUrl = `${backendUrl}/analytics/tickets/${backendPath}${queryString ? '?' + queryString : ''}`;

  // Get JWT from cookie for Authorization header
  const token = extractBearerToken(request);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Origin: process.env.FRONTEND_URL || 'https://parwa.buzz',
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

  const token = extractBearerToken(request);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Origin: process.env.FRONTEND_URL || 'https://parwa.buzz',
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
