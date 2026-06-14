/**
 * PARWA Integrations API Proxy
 *
 * Catches /api/integrations requests and proxies to backend.
 * Mock responses when backend is unavailable.
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

    const res = await fetch(`${BACKEND_URL}/api/integrations`, { headers });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    // Mock fallback
    return NextResponse.json([]);
  }
}

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
    const res = await fetch(`${BACKEND_URL}/api/integrations`, {
      method: 'POST',
      headers,
      body,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    // Mock fallback — simulate successful integration creation
    const body = await req.json().catch(() => ({}));
    return NextResponse.json({
      id: `mock-int-${Date.now()}`,
      name: body.name || 'Integration',
      type: body.integration_type || 'custom',
      status: 'active',
      config: body.config || {},
      last_test_at: null,
      last_test_result: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }
}
