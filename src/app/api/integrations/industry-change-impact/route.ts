/**
 * PARWA Industry Change Impact API Proxy
 *
 * POST /api/integrations/industry-change-impact
 * Proxies to backend to check impact of industry change on integrations.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

export async function POST(req: NextRequest) {
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

    const body = await req.text();
    const res = await fetch(`${BACKEND_URL}/api/integrations/industry-change-impact`, {
      method: 'POST',
      headers,
      body,
    });

    // If backend returns auth error, provide mock fallback with the request data
    if (res.status === 401 || res.status === 403) {
      try {
        const parsed = JSON.parse(body);
        return NextResponse.json({
          current_industry: parsed.current_industry || '',
          new_industry: parsed.new_industry || '',
          connected_integrations: [],
          still_recommended: [],
          no_longer_suggested: [],
          newly_suggested: [],
          message: 'Sign in to see full industry change impact analysis.',
        }, { status: 200 });
      } catch {
        // Fall through to default mock
      }
    }

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({
      new_industry: '',
      current_industry: '',
      connected_integrations: [],
      still_recommended: [],
      no_longer_suggested: [],
      newly_suggested: [],
      message: 'Unable to check industry change impact. Backend unavailable.',
    }, { status: 200 });
  }
}
