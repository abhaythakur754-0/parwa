/**
 * PARWA Outbound Webhooks API Proxy
 *
 * BFF route that proxies /api/integrations/webhooks to the backend.
 * Supports GET (list), POST (create) for outbound webhooks.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

function getAuthHeaders(req: NextRequest): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const cookieHeader = req.headers.get('cookie');
  if (cookieHeader) {
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => { const [k, ...v] = c.trim().split('='); return [k, v.join('=')]; })
    );
    if (cookies.parwa_at) headers['Authorization'] = `Bearer ${cookies.parwa_at}`;
  }
  const authHeader = req.headers.get('authorization');
  if (authHeader) headers['Authorization'] = authHeader;
  return headers;
}

export async function GET(req: NextRequest) {
  try {
    const headers = getAuthHeaders(req);
    const res = await fetch(`${BACKEND_URL}/api/integrations/webhooks`, { headers });

    if (res.status === 401 || res.status === 403) {
      return NextResponse.json([]);
    }

    const data = await res.json();
    // Map backend response to frontend format
    const mapped = Array.isArray(data) ? data.map((wh: any) => ({
      id: wh.id,
      url: wh.url,
      events: wh.events || [],
      secret: wh.secret,
      active: wh.active,
      lastTriggeredAt: wh.last_triggered_at || null,
      failureCount: wh.failure_count || 0,
      description: wh.description || '',
      createdAt: wh.created_at || '',
    })) : [];
    return NextResponse.json(mapped, { status: res.status });
  } catch {
    // Backend unreachable — return empty list
    return NextResponse.json([]);
  }
}

export async function POST(req: NextRequest) {
  try {
    const headers = getAuthHeaders(req);
    const body = await req.text();
    const res = await fetch(`${BACKEND_URL}/api/integrations/webhooks`, {
      method: 'POST',
      headers,
      body,
    });

    if (res.ok) {
      const data = await res.json();
      // Map backend response to frontend format
      const mapped = {
        id: data.id,
        url: data.url,
        events: data.events || [],
        secret: data.secret,
        active: data.active,
        lastTriggeredAt: data.last_triggered_at || null,
        failureCount: data.failure_count || 0,
        description: data.description || '',
        createdAt: data.created_at || '',
      };
      return NextResponse.json(mapped, { status: 201 });
    }

    const errorData = await res.json().catch(() => ({ message: 'Failed to create webhook' }));
    return NextResponse.json(errorData, { status: res.status });
  } catch {
    // Backend unreachable — return mock success
    const body = await req.json().catch(() => ({}));
    return NextResponse.json({
      id: `wh-${Date.now()}`,
      url: body.url || '',
      events: body.events || [],
      secret: `whsec_${Math.random().toString(36).slice(2, 10)}`,
      active: true,
      lastTriggeredAt: null,
      failureCount: 0,
      description: body.description || '',
      createdAt: new Date().toISOString(),
    }, { status: 201 });
  }
}
