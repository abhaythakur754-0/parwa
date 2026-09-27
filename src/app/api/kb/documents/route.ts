/**
 * PARWA Knowledge Base Documents API Proxy
 *
 * Handles GET /api/kb/documents — lists documents for the current tenant.
 *
 * Backend: GET /api/kb/documents (backend/app/api/knowledge_base.py)
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

function getProxyOrigin(): string {
  if (process.env.FRONTEND_URL) return process.env.FRONTEND_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  if (process.env.NODE_ENV === 'production') return 'https://parwa.buzz';
  return 'http://localhost:3000';
}

export async function GET(req: NextRequest) {
  try {
    const headers: Record<string, string> = {
      'Origin': getProxyOrigin(),
      'Referer': `${getProxyOrigin()}/`,
    };
    const authHeader = req.headers.get('authorization');
    if (authHeader) headers['Authorization'] = authHeader;
    const cookieHeader = req.headers.get('cookie');
    if (cookieHeader) {
      headers['Cookie'] = cookieHeader;
      const cookies = Object.fromEntries(
        cookieHeader.split(';').map((c) => { const [k, ...v] = c.trim().split('='); return [k, v.join('=')]; })
      );
      if (cookies.parwa_at) headers['Authorization'] = `Bearer ${cookies.parwa_at}`;
    }

    // Forward query string (status, limit, offset, etc.)
    const url = new URL(req.url);
    const searchParams = url.searchParams.toString();
    const fullUrl = `${BACKEND_URL}/api/kb/documents${searchParams ? `?${searchParams}` : ''}`;

    const res = await fetch(fullUrl, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(15000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: { message: 'Knowledge Base service unavailable.' } },
      { status: 503 },
    );
  }
}
