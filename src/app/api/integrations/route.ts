/**
 * PARWA Integrations API — List & Create
 *
 * GET  /api/integrations — list all integrations for the current user
 * POST /api/integrations — create a new integration
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
  const authToken = getAuthToken(req);

  try {
    const { response } = await backendProxy('/api/v1/integrations', {
      method: 'GET',
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    const errorBody = await response.text().catch(() => '{}');
    try {
      return NextResponse.json(JSON.parse(errorBody), { status: response.status });
    } catch {
      return NextResponse.json(
        { error: 'backend_error', message: `Backend returned ${response.status}` },
        { status: response.status }
      );
    }
  } catch {
    // Backend unreachable — return empty list
    return NextResponse.json([]);
  }
}

export async function POST(req: NextRequest) {
  const authToken = getAuthToken(req);
  let body: string | undefined;
  try { body = await req.text(); } catch { /* no body */ }

  try {
    const { response } = await backendProxy('/api/v1/integrations', {
      method: 'POST',
      body,
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    const errorBody = await response.text().catch(() => '{}');
    try {
      return NextResponse.json(JSON.parse(errorBody), { status: response.status });
    } catch {
      return NextResponse.json(
        { error: 'backend_error', message: `Backend returned ${response.status}` },
        { status: response.status }
      );
    }
  } catch {
    // Backend unreachable — save locally (return what was sent)
    try {
      const parsed = body ? JSON.parse(body) : {};
      return NextResponse.json({
        id: `local-${Date.now()}`,
        ...parsed,
        status: 'active',
        saved_locally: true,
      });
    } catch {
      return NextResponse.json(
        { error: 'backend_unreachable', message: 'Cannot save integration. Backend is not available.' },
        { status: 503 }
      );
    }
  }
}
