/**
 * PARWA Onboarding API Proxy (Catch-All)
 *
 * Catches all /api/onboarding/* requests and proxies them to the backend.
 * When the backend is unavailable, returns mock responses for graceful degradation.
 *
 * Handles: /api/onboarding/state, /api/onboarding/prerequisites,
 *          /api/onboarding/complete-step, /api/onboarding/legal-consent,
 *          /api/onboarding/activate, /api/onboarding/first-victory, etc.
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function proxyToBackend(req: NextRequest, path: string) {
  const url = `${BACKEND_URL}/api/onboarding${path}`;
  const method = req.method;

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // Forward auth token
    const authHeader = req.headers.get('authorization');
    if (authHeader) headers['Authorization'] = authHeader;

    const cookieHeader = req.headers.get('cookie');
    if (cookieHeader) {
      const cookies = Object.fromEntries(
        cookieHeader.split(';').map((c) => {
          const [key, ...val] = c.trim().split('=');
          return [key, val.join('=')];
        })
      );
      if (cookies.parwa_at) headers['Authorization'] = `Bearer ${cookies.parwa_at}`;
    }

    let body: string | undefined;
    if (method !== 'GET' && method !== 'HEAD') {
      body = await req.text();
    }

    const res = await fetch(url, {
      method,
      headers,
      body,
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return null; // Backend unavailable
  }
}

// GET handler — for /api/onboarding/state, /api/onboarding/prerequisites, etc.
export async function GET(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;

  // Try backend first
  const backendResponse = await proxyToBackend(req, `${path}${searchParams}`);
  if (backendResponse) return backendResponse;

  // Mock fallback when backend is down
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
      first_victory_completed: false,
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
    return NextResponse.json({
      can_activate: true,
      missing: [],
    });
  }

  return NextResponse.json(
    { detail: 'Not found' },
    { status: 404 }
  );
}

// POST handler — for complete-step, legal-consent, activate, first-victory, etc.
export async function POST(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;

  // Try backend first
  const backendResponse = await proxyToBackend(req, `${path}${searchParams}`);
  if (backendResponse) return backendResponse;

  // Mock fallback when backend is down
  if (path.startsWith('/complete-step')) {
    return NextResponse.json({
      status: 'ok',
      current_step: 1,
      completed_steps: [1],
    });
  }

  if (path === '/legal-consent') {
    return NextResponse.json({
      status: 'ok',
      legal_accepted: true,
    });
  }

  if (path === '/activate') {
    return NextResponse.json({
      status: 'ok',
      activated: true,
    });
  }

  if (path === '/first-victory') {
    return NextResponse.json({
      status: 'ok',
      first_victory_completed: true,
    });
  }

  return NextResponse.json(
    { detail: 'Not found' },
    { status: 404 }
  );
}

// PUT handler — for updating onboarding state
export async function PUT(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;

  // Try backend first
  const backendResponse = await proxyToBackend(req, `${path}${searchParams}`);
  if (backendResponse) return backendResponse;

  return NextResponse.json(
    { detail: 'Not found' },
    { status: 404 }
  );
}
