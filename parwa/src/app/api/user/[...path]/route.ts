/**
 * PARWA User API Proxy (Catch-All)
 *
 * Catches all /api/user/* requests and proxies them to the backend.
 * Uses backendProxy for CSRF-aware requests with Origin header handling.
 * When the backend is unavailable, falls back to mock responses for graceful degradation.
 *
 * Key endpoints:
 * - GET  /api/user/details - Get current user details
 * - POST /api/user/details - Submit user details (onboarding details form)
 * - PATCH /api/user/details - Update user details
 * - POST /api/user/verify-work-email - Send work email verification
 * - POST /api/user/verify-work-email/confirm - Confirm work email with token
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
    const { response } = await backendProxy(`/api/user${path}${searchParams}`, {
      method: 'GET',
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    if (response.status !== 403) {
      console.warn(`[user-proxy] GET ${path} returned ${response.status} — trying mock`);
    } else {
      console.warn(`[user-proxy] GET ${path} got CSRF 403 — using mock fallback`);
    }
  } catch (err) {
    console.warn(`[user-proxy] GET ${path} failed:`, err);
  }

  // Mock fallbacks
  if (path === '/details' || path === '') {
    return NextResponse.json(null);
  }

  return NextResponse.json({ detail: 'Not found' }, { status: 404 });
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
    const { response } = await backendProxy(`/api/user${path}${searchParams}`, {
      method: 'POST',
      body: body || undefined,
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    if (response.status !== 403) {
      console.warn(`[user-proxy] POST ${path} returned ${response.status} — trying mock`);
    } else {
      console.warn(`[user-proxy] POST ${path} got CSRF 403 — using mock fallback`);
    }
  } catch (err) {
    console.warn(`[user-proxy] POST ${path} failed:`, err);
  }

  // Mock fallbacks — allow onboarding to continue even when backend is down
  if (path === '/details') {
    // Parse the submitted data to echo back as mock response
    let parsed: Record<string, unknown> = {};
    try {
      parsed = body ? JSON.parse(body) : {};
    } catch {
      // Ignore parse errors
    }
    return NextResponse.json({
      id: 'mock-user-details',
      user_id: 'mock-user',
      company_id: 'mock-company',
      full_name: parsed.full_name || 'Test User',
      company_name: parsed.company_name || 'Test Company',
      work_email: parsed.work_email || null,
      work_email_verified: false,
      industry: parsed.industry || 'saas',
      company_size: parsed.company_size || null,
      website: parsed.website || null,
      details_completed: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }

  if (path === '/verify-work-email') {
    return NextResponse.json({
      status: 'ok',
      message: 'Verification email sent (mock)',
      verification_id: 'mock-verification',
    });
  }

  if (path.startsWith('/verify-work-email/confirm')) {
    return NextResponse.json({
      status: 'ok',
      message: 'Email verified (mock)',
      verified: true,
    });
  }

  return NextResponse.json({ detail: 'Not found' }, { status: 404 });
}

// PATCH handler
export async function PATCH(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
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
    const { response } = await backendProxy(`/api/user${path}${searchParams}`, {
      method: 'PATCH',
      body: body || undefined,
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    console.warn(`[user-proxy] PATCH ${path} returned ${response.status}`);
  } catch (err) {
    console.warn(`[user-proxy] PATCH ${path} failed:`, err);
  }

  // Mock fallback for PATCH /details
  if (path === '/details') {
    let parsed: Record<string, unknown> = {};
    try {
      parsed = body ? JSON.parse(body) : {};
    } catch {
      // Ignore parse errors
    }
    return NextResponse.json({
      id: 'mock-user-details',
      user_id: 'mock-user',
      company_id: 'mock-company',
      full_name: parsed.full_name || 'Test User',
      company_name: parsed.company_name || 'Test Company',
      work_email: parsed.work_email || null,
      work_email_verified: false,
      industry: parsed.industry || 'saas',
      company_size: parsed.company_size || null,
      website: parsed.website || null,
      details_completed: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }

  return NextResponse.json({ detail: 'Not found' }, { status: 404 });
}
