/**
 * PARWA Onboarding API Proxy
 *
 * Catches all /api/onboarding/* requests and proxies them to the backend.
 * Uses backendProxy for CSRF-aware requests with Origin header handling.
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';

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

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const path = url.pathname.replace('/api/onboarding', '');
  const searchParams = url.search;
  const authToken = getAuthToken(req);

  try {
    const { response } = await backendProxy(`/api/onboarding${path}${searchParams}`, {
      method: 'GET',
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    return NextResponse.json(
      await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` })),
      { status: response.status }
    );
  } catch (err) {
    console.error(`[onboarding-proxy] GET ${path} failed:`, err);
    return NextResponse.json(
      { error: 'backend_unreachable', message: 'Backend is not available. Onboarding data cannot be loaded.' },
      { status: 503 }
    );
  }
}

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

    return NextResponse.json(
      await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` })),
      { status: response.status }
    );
  } catch (err) {
    console.error(`[onboarding-proxy] POST ${path} failed:`, err);
    return NextResponse.json(
      { error: 'backend_unreachable', message: `Cannot save onboarding data for ${path}. Backend is not available.` },
      { status: 503 }
    );
  }
}