/**
 * PARWA Integration Instance API Proxy
 *
 * Proxies /api/integrations/{id} requests to backend.
 * Handles: POST /{id}/test, DELETE /{id}
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

function getAuthHeaders(req: NextRequest): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const authHeader = req.headers.get('authorization');
  if (authHeader) {
    headers['Authorization'] = authHeader;
  } else {
    const cookieHeader = req.headers.get('cookie');
    if (cookieHeader) {
      const cookies = Object.fromEntries(
        cookieHeader.split(';').map((c) => {
          const [k, ...v] = c.trim().split('=');
          return [k, v.join('=')];
        })
      );
      if (cookies.parwa_at) {
        headers['Authorization'] = `Bearer ${cookies.parwa_at}`;
      }
    }
  }
  return headers;
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const headers = getAuthHeaders(req);

  try {
    const res = await fetch(`${BACKEND_URL}/api/integrations/${id}/test`, {
      method: 'POST',
      headers,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 502 });
  }
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const headers = getAuthHeaders(req);

  try {
    const res = await fetch(`${BACKEND_URL}/api/integrations/${id}`, {
      method: 'DELETE',
      headers,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 502 });
  }
}
