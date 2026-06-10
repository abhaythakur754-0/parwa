/**
 * PARWA Integration Catalog API Proxy
 *
 * GET /api/integrations/catalog?industry=saas
 * Proxies to backend /api/integrations/catalog with optional industry filter.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

export async function GET(req: NextRequest) {
  try {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const authHeader = req.headers.get('authorization');
    if (authHeader) headers['Authorization'] = authHeader;
    const cookieHeader = req.headers.get('cookie');
    if (cookieHeader) {
      const cookies = Object.fromEntries(
        cookieHeader.split(';').map((c) => { const [k, ...v] = c.trim().split('='); return [k, v.join('=')]; })
      );
      if (cookies.parwa_at) headers['Authorization'] = `Bearer ${cookies.parwa_at}`;
    }

    const industry = req.nextUrl.searchParams.get('industry');
    const url = industry
      ? `${BACKEND_URL}/api/integrations/catalog?industry=${encodeURIComponent(industry)}`
      : `${BACKEND_URL}/api/integrations/catalog`;

    const res = await fetch(url, { headers });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    // Fallback: return empty catalog if backend is down
    return NextResponse.json([], { status: 200 });
  }
}
