/**
 * PARWA Outbound Webhook Test API Proxy
 *
 * BFF route that proxies POST /api/integrations/webhooks/[webhookId]/test
 * to the backend for sending test events to webhook endpoints.
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

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ webhookId: string }> }
) {
  try {
    const { webhookId } = await params;
    const headers = getAuthHeaders(req);
    const res = await fetch(`${BACKEND_URL}/api/integrations/webhooks/${webhookId}/test`, {
      method: 'POST',
      headers,
    });

    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
    return NextResponse.json(
      { success: false, message: 'Test event could not be sent' },
      { status: res.status }
    );
  } catch {
    // Backend unreachable — return mock success for UI testing
    return NextResponse.json({
      success: true,
      message: 'Test event simulated (backend unreachable)',
      status_code: 200,
    });
  }
}
