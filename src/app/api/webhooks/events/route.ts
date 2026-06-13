/**
 * PARWA Webhook Event Log API Proxy
 *
 * BFF route that proxies GET /api/webhooks/events to the backend
 * to fetch recent inbound webhook events for the event log viewer.
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
    const res = await fetch(`${BACKEND_URL}/api/webhooks/events?limit=50`, { headers });

    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }

    // If backend doesn't have this endpoint yet, try the generic webhook status endpoint
    if (res.status === 404) {
      const statusRes = await fetch(`${BACKEND_URL}/api/webhooks/status/recent`, { headers }).catch(() => null);
      if (statusRes && statusRes.ok) {
        const data = await statusRes.json();
        return NextResponse.json(data);
      }
    }

    return NextResponse.json({ events: [] });
  } catch {
    // Backend unreachable — return empty list
    return NextResponse.json({ events: [] });
  }
}
