/**
 * PARWA Onboarding API Proxy (Catch-All)
 *
 * Catches all /api/onboarding/* requests and proxies them to the backend.
 * Uses backendProxy for CSRF-aware requests with Origin header handling.
 *
 * NO MOCK FALLBACKS — per CLAUDE.md Rule #5:
 * "Never say it works unless you have PROVEN it works."
 * Mock fallbacks silently hide broken backend connections.
 * If the backend is unreachable, return an explicit 503 error.
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';

/**
 * Extract auth token from request (cookie or Authorization header).
 */
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

// GET handler
export async function GET(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;
  const authToken = getAuthToken(req);

  // Try backend first (CSRF-aware)
  try {
    const { response } = await backendProxy(`/api/v1/onboarding${path}${searchParams}`, {
      method: 'GET',
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    // Backend returned an error — forward the status
    const errorBody = await response.text().catch(() => '{}');
    try {
      const parsed = JSON.parse(errorBody);
      return NextResponse.json(parsed, { status: response.status });
    } catch {
      return NextResponse.json(
        { error: 'backend_error', message: `Backend returned ${response.status}` },
        { status: response.status }
      );
    }
  } catch (err) {
    console.error(`[onboarding-proxy] GET ${path} — backend unreachable:`, err);
  }

  // NO MOCK FALLBACK — return explicit 503 so developer knows backend is down
  return NextResponse.json(
    { error: 'backend_unreachable', message: `Backend is not available. Cannot GET /api/onboarding${path}.` },
    { status: 503 }
  );
}

// POST handler
export async function POST(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;
  const authToken = getAuthToken(req);

  let body: string | undefined;
  try {
    body = await req.text();
  } catch {
    // No body
  }

  // Try backend first (CSRF-aware)
  try {
    const { response } = await backendProxy(`/api/v1/onboarding${path}${searchParams}`, {
      method: 'POST',
      body: body || undefined,
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    // Backend returned an error — forward the status
    const errorBody = await response.text().catch(() => '{}');
    try {
      const parsed = JSON.parse(errorBody);
      return NextResponse.json(parsed, { status: response.status });
    } catch {
      return NextResponse.json(
        { error: 'backend_error', message: `Backend returned ${response.status} for POST ${path}` },
        { status: response.status }
      );
    }
  } catch (err) {
    console.error(`[onboarding-proxy] POST ${path} — backend unreachable:`, err);
  }

  // NO MOCK FALLBACK — return explicit 503 so developer knows backend is down
  return NextResponse.json(
    { error: 'backend_unreachable', message: `Cannot save onboarding data for ${path}. Backend is not available.` },
    { status: 503 }
  );
}

// PUT handler
export async function PUT(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;
  const authToken = getAuthToken(req);

  let body: string | undefined;
  try {
    body = await req.text();
  } catch {
    // No body
  }

  // Try backend first (CSRF-aware)
  try {
    const { response } = await backendProxy(`/api/v1/onboarding${path}${searchParams}`, {
      method: 'PUT',
      body: body || undefined,
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    // Backend returned an error — forward the status
    const errorBody = await response.text().catch(() => '{}');
    try {
      const parsed = JSON.parse(errorBody);
      return NextResponse.json(parsed, { status: response.status });
    } catch {
      return NextResponse.json(
        { error: 'backend_error', message: `Backend returned ${response.status} for PUT ${path}` },
        { status: response.status }
      );
    }
  } catch (err) {
    console.error(`[onboarding-proxy] PUT ${path} — backend unreachable:`, err);
  }

  // NO MOCK FALLBACK — return explicit 503
  return NextResponse.json(
    { error: 'backend_unreachable', message: `Cannot update onboarding data for ${path}. Backend is not available.` },
    { status: 503 }
  );
}
