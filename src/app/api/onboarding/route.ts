/**
 * PARWA Onboarding API Proxy
 *
 * Catches all /api/onboarding/* requests and proxies them to the backend.
 * Uses backendProxy for CSRF-aware requests with Origin header handling.
 * When the backend is unavailable or returns CSRF errors, falls back to
 * mock responses for graceful degradation.
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

// GET handler — for /api/onboarding/state, /api/onboarding/prerequisites, etc.
export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const path = url.pathname.replace('/api/onboarding', '');
  const searchParams = url.search;
  const authToken = getAuthToken(req);

  // Try backend first (CSRF-aware)
  try {
    const { response } = await backendProxy(`/api/onboarding${path}${searchParams}`, {
      method: 'GET',
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    // If backend returned non-403 error, try mock fallback
    if (response.status !== 403) {
      console.warn(`[onboarding-proxy] GET ${path} returned ${response.status} — trying mock`);
    }
  } catch (err) {
    console.warn(`[onboarding-proxy] GET ${path} failed:`, err);
  }

  // NO MORE SILENT MOCK FALLBACKS — per CLAUDE.md Rule #5
  // If the backend is unreachable, return an explicit error so the
  // developer knows the frontend is NOT connected to the backend.
  console.error(`[onboarding-proxy] GET ${path} — backend unreachable, returning error (no mock fallback)`);
  
  return NextResponse.json(
    { error: 'backend_unreachable', message: 'Backend is not available. Onboarding data cannot be loaded.' },
    { status: 503 }
  );

  // Unreachable code after the return above, but kept for reference
  return NextResponse.json(
    { error: 'not_found', message: 'Endpoint not found' },
    { status: 404 }
  );
}

// POST handler — for complete-step, legal-consent, activate, first-victory, etc.
export async function POST(req: NextRequest) {
  const url = new URL(req.url);
  const path = url.pathname.replace('/api/onboarding', '');
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
    const { response } = await backendProxy(`/api/onboarding${path}${searchParams}`, {
      method: 'POST',
      body: body || undefined,
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    // If backend returned non-403 error, try mock fallback
    if (response.status !== 403) {
      console.warn(`[onboarding-proxy] POST ${path} returned ${response.status} — trying mock`);
    } else {
      // CSRF 403 — still fall through to mock so the wizard can proceed
      console.warn(`[onboarding-proxy] POST ${path} got CSRF 403 — using mock fallback`);
    }
  } catch (err) {
    console.warn(`[onboarding-proxy] POST ${path} failed:`, err);
  }

  // NO MORE SILENT MOCK FALLBACKS — per CLAUDE.md Rule #5
  // If backend is unreachable, return an explicit error instead of
  // silently returning fake "ok" responses that hide the broken connection.
  console.error(`[onboarding-proxy] POST ${path} — backend unreachable, returning error (no mock fallback)`);
  
  return NextResponse.json(
    { error: 'backend_unreachable', message: `Cannot save onboarding data for ${path}. Backend is not available.` },
    { status: 503 }
  );
}
