import { NextRequest, NextResponse } from 'next/server';

/**
 * Approvals root proxy route.
 * Forwards GET /api/approvals (no path) to backend /api/approvals.
 * The [...path] route handles /api/approvals/<something>, but a bare
 * /api/approvals needs its own route file in Next.js App Router.
 */

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
}

function getProxyOrigin(): string {
  if (process.env.FRONTEND_URL) return process.env.FRONTEND_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  if (process.env.NODE_ENV === 'production') return 'https://parwa.buzz';
  return 'http://localhost:3000';
}

function getAccessTokenFromCookie(cookieHeader: string): string | null {
  const match = cookieHeader.match(/(?:^|;\s*)parwa_at=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function proxyRequest(method: string, request: NextRequest) {
  const backendUrl = getBackendUrl();
  const origin = getProxyOrigin();
  const url = new URL(request.url);
  const queryString = url.searchParams.toString();
  const backendPath = `/api/approvals${queryString ? `?${queryString}` : ''}`;

  try {
    let body: string | null = null;
    if (method !== 'GET' && method !== 'DELETE') {
      try { body = await request.text(); } catch { /* no body */ }
    }

    const cookie = request.headers.get('cookie') || '';
    const accessToken = getAccessTokenFromCookie(cookie);

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Origin': origin,
      'Referer': `${origin}/`,
    };
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    const response = await fetch(`${backendUrl}${backendPath}`, {
      method,
      headers,
      body,
      signal: AbortSignal.timeout(15000),
    });

    const text = await response.text();
    return new Response(text, {
      status: response.status,
      headers: { 'Content-Type': response.headers.get('Content-Type') || 'application/json' },
    });
  } catch (err) {
    console.error('[/api/approvals] proxy failed:', err instanceof Error ? err.message : String(err));
    return NextResponse.json(
      { error: { code: 'backend_unavailable', message: 'Approvals backend unavailable.', details: null } },
      { status: 502 }
    );
  }
}

export async function GET(request: NextRequest) {
  return proxyRequest('GET', request);
}

export async function POST(request: NextRequest) {
  return proxyRequest('POST', request);
}
