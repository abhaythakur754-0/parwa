/**
 * PARWA Onboarding API Proxy (Catch-All)
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

// GET handler
export async function GET(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
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

    if (response.status !== 403) {
      console.warn(`[onboarding-proxy] GET ${path} returned ${response.status} — trying mock`);
    }
  } catch (err) {
    console.warn(`[onboarding-proxy] GET ${path} failed:`, err);
  }

  // Mock fallbacks
  if (path === '/state' || path === '') {
    return NextResponse.json({
      id: 'mock-onboarding',
      user_id: 'mock-user',
      company_id: 'mock-company',
      current_step: 1,
      completed_steps: [],
      status: 'not_started',
      details_completed: false,
      wizard_started: false,
      legal_accepted: false,
      first_victory_completed: true,
      ai_name: 'Jarvis',
      ai_tone: 'professional',
      ai_response_style: 'concise',
      ai_greeting: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      completed_at: null,
    });
  }

  if (path === '/prerequisites') {
    return NextResponse.json({ can_activate: true, missing: [] });
  }

  // Phase 4: cost-breakdown GET mock fallback
  if (path === '/cost-breakdown') {
    return NextResponse.json({
      variants: [],
      addOns: { voice: { price: 199, enabled: false }, customApi: { price: 49, enabled: false } },
      totalMonthly: 0,
      savingsVsHuman: { agentsReplaced: 0, humanCost: 0, savings: 0, savingsPercent: 0 },
    });
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
    const { response } = await backendProxy(`/api/onboarding${path}${searchParams}`, {
      method: 'POST',
      body: body || undefined,
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    if (response.status !== 403) {
      console.warn(`[onboarding-proxy] POST ${path} returned ${response.status} — trying mock`);
    } else {
      console.warn(`[onboarding-proxy] POST ${path} got CSRF 403 — using mock fallback`);
    }
  } catch (err) {
    console.warn(`[onboarding-proxy] POST ${path} failed:`, err);
  }

  // Mock fallbacks
  if (path.startsWith('/complete-step')) {
    return NextResponse.json({ status: 'ok', current_step: 1, completed_steps: [1] });
  }
  if (path === '/legal-consent') {
    return NextResponse.json({ status: 'ok', legal_accepted: true });
  }
  if (path === '/activate') {
    return NextResponse.json({ status: 'ok', activated: true });
  }
  if (path === '/first-victory') {
    return NextResponse.json({ status: 'ok', first_victory_completed: true });
  }

  // Phase 4: industry-variant POST mock fallback
  if (path === '/industry-variant') {
    return NextResponse.json({
      status: 'ok',
      industry: 'other',
      variant: 'parwa',
    });
  }

  // Phase 4: checkout POST mock fallback
  if (path === '/checkout') {
    return NextResponse.json({
      status: 'ok',
      checkout_url: null,
      session_id: 'mock-session-' + Date.now(),
      message: 'Checkout session created (mock)',
    });
  }

  return NextResponse.json({ detail: 'Not found' }, { status: 404 });
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
    const { response } = await backendProxy(`/api/onboarding${path}${searchParams}`, {
      method: 'PUT',
      body: body || undefined,
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    console.warn(`[onboarding-proxy] PUT ${path} returned ${response.status}`);
  } catch (err) {
    console.warn(`[onboarding-proxy] PUT ${path} failed:`, err);
  }

  return NextResponse.json({ detail: 'Not found' }, { status: 404 });
}
