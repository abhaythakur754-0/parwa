import { NextRequest, NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';

/**
 * Analytics catch-all proxy route.
 *
 * Proxies /api/analytics/* to backend /analytics/tickets/*
 * Examples:
 *   /api/analytics/dashboard  → /analytics/tickets/dashboard
 *   /api/analytics/summary    → /analytics/tickets/summary
 *   /api/analytics/agents     → /analytics/tickets/agents
 *   /api/analytics/trends     → /analytics/tickets/trends
 *   /api/analytics/sla        → /analytics/tickets/sla
 *   /api/analytics/category   → /analytics/tickets/category
 *
 * Falls back to mock data when backend is unavailable.
 */

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
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

  // Forward auth cookies to the backend
  const cookieHeader = request.headers.get('cookie') || '';
  const authCookies = cookieHeader
    .split(';')
    .filter((c: string) => {
      const name = c.trim().split('=')[0];
      return name === 'parwa_at' || name === 'parwa_rt' || name === 'parwa_user';
    })
    .join('; ');

  try {
    const backendRes = await fetch(fullBackendUrl, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Cookie: authCookies,
        Origin: process.env.FRONTEND_URL || 'https://parwa.buzz',
      },
      signal: AbortSignal.timeout(15_000),
      redirect: 'manual',
    });

    const data = await backendRes.json();
    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    // Backend unavailable — return error so client can use mock fallback
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

  const cookieHeader = request.headers.get('cookie') || '';
  const authCookies = cookieHeader
    .split(';')
    .filter((c: string) => {
      const name = c.trim().split('=')[0];
      return name === 'parwa_at' || name === 'parwa_rt' || name === 'parwa_user';
    })
    .join('; ');

  try {
    const body = await request.text();
    const backendRes = await fetch(fullBackendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Cookie: authCookies,
        Origin: process.env.FRONTEND_URL || 'https://parwa.buzz',
      },
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
