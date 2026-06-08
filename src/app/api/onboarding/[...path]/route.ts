/**
 * PARWA Onboarding API Proxy (Catch-All)
 *
 * Catches all /api/onboarding/* requests and proxies them to the backend.
 * When the backend is unavailable, returns mock responses for graceful degradation.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

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
      signal: AbortSignal.timeout(8000),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return null; // Backend unavailable
  }
}

// GET handler
export async function GET(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;

  const backendResponse = await proxyToBackend(req, `${path}${searchParams}`);
  if (backendResponse) return backendResponse;

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
    return NextResponse.json({ can_activate: true, missing: [] });
  }

  return NextResponse.json({ detail: 'Not found' }, { status: 404 });
}

// POST handler
export async function POST(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;

  const backendResponse = await proxyToBackend(req, `${path}${searchParams}`);
  if (backendResponse) return backendResponse;

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

  return NextResponse.json({ detail: 'Not found' }, { status: 404 });
}

// PUT handler
export async function PUT(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;

  const backendResponse = await proxyToBackend(req, `${path}${searchParams}`);
  if (backendResponse) return backendResponse;

  return NextResponse.json({ detail: 'Not found' }, { status: 404 });
}
