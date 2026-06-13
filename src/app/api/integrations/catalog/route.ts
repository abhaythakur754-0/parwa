/**
 * PARWA Integration Catalog API Proxy
 *
 * GET /api/integrations/catalog?industry=saas
 * Proxies to backend /api/integrations/catalog with optional industry filter.
 *
 * NO MOCK FALLBACK — per CLAUDE.md Rule #5:
 * If backend is unreachable, return 503 so the developer knows.
 * The frontend IntegrationStep component can fall back to its
 * local catalog import client-side (which is the same data).
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

export async function GET(req: NextRequest) {
  const industry = req.nextUrl.searchParams.get('industry');

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

    const url = industry
      ? `${BACKEND_URL}/api/integrations/catalog?industry=${encodeURIComponent(industry)}`
      : `${BACKEND_URL}/api/integrations/catalog`;

    const res = await fetch(url, { headers, signal: AbortSignal.timeout(5000) });

    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        return NextResponse.json(data, { status: 200 });
      }
      // Backend returned empty array — return it (no mock fallback)
      return NextResponse.json(data, { status: 200 });
    }

    // Backend returned error — forward the status
    const errorBody = await res.text().catch(() => '{}');
    try {
      return NextResponse.json(JSON.parse(errorBody), { status: res.status });
    } catch {
      return NextResponse.json(
        { error: 'backend_error', message: `Backend returned ${res.status}` },
        { status: res.status }
      );
    }
  } catch (err) {
    console.error('[integrations-catalog] Backend unreachable:', err);
  }

  // NO MOCK FALLBACK — return explicit 503
  return NextResponse.json(
    { error: 'backend_unreachable', message: 'Backend is not available. Integration catalog cannot be loaded from backend.' },
    { status: 503 }
  );
}
