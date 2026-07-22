/**
 * PARWA User API Proxy (Catch-All)
 *
 * Catches all /api/user/* requests and proxies them to the backend.
 * Uses backendProxy for CSRF-aware requests with Origin header handling.
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

export async function GET(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;
  const authToken = getAuthToken(req);

  try {
    const { response } = await backendProxy(`/api/user${path}${searchParams}`, {
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
    console.error(`[user-proxy] GET ${path} failed:`, err);
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 502 });
  }
}

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

    return NextResponse.json(
      await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` })),
      { status: response.status }
    );
  } catch (err) {
    console.error(`[user-proxy] POST ${path} failed:`, err);
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 502 });
  }
}

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

    return NextResponse.json(
      await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` })),
      { status: response.status }
    );
  } catch (err) {
    console.error(`[user-proxy] PATCH ${path} failed:`, err);
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 502 });
  }
}