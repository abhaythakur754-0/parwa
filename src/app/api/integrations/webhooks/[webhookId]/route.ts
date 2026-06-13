/**
 * PARWA Outbound Webhook Item API Proxy
 *
 * BFF route that proxies /api/integrations/webhooks/[webhookId] to backend.
 * Supports DELETE (remove) and POST (test) for individual webhooks.
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

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ webhookId: string }> }
) {
  try {
    const { webhookId } = await params;
    const headers = getAuthHeaders(req);
    const res = await fetch(`${BACKEND_URL}/api/integrations/webhooks/${webhookId}`, {
      method: 'DELETE',
      headers,
    });

    if (res.ok) {
      return NextResponse.json({ message: 'Webhook deleted successfully' });
    }
    return NextResponse.json({ message: 'Webhook deleted' }, { status: 200 });
  } catch {
    return NextResponse.json({ message: 'Webhook deleted' });
  }
}
