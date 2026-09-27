/**
 * PARWA Custom Connector & OpenAPI Import API Proxy
 *
 * Proxies all /api/integrations/custom/* and /api/integrations/openapi-import/* requests to backend.
 *
 * Routes:
 *   POST /api/integrations/custom/connector              — Create Tier 3 Custom REST Connector
 *   GET  /api/integrations/custom/connectors              — List custom connectors
 *   GET  /api/integrations/custom/connectors/[id]         — Get connector
 *   PUT  /api/integrations/custom/connectors/[id]         — Update connector
 *   DELETE /api/integrations/custom/connectors/[id]       — Delete connector
 *   POST /api/integrations/custom/connectors/[id]/test    — Test connector
 *   POST /api/integrations/openapi-import                 — Import OpenAPI spec (Tier 2)
 *   POST /api/integrations/openapi-import/save            — Save OpenAPI import
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

function getAuthHeaders(req: NextRequest): Record<string, string> {
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
  return headers;
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathStr = path.join('/');
  const headers = getAuthHeaders(req);

  try {
    const body = await req.text();

    // Route: /api/integrations/custom/connector → backend /api/integrations/custom/connector
    // Route: /api/integrations/custom/connectors/[id]/test → backend /api/integrations/custom/connectors/[id]/test
    // Route: /api/integrations/openapi-import → backend /api/integrations/openapi-import
    // Route: /api/integrations/openapi-import/save → backend /api/integrations/openapi-import/save
    let endpoint: string;
    if (pathStr.startsWith('openapi-import')) {
      endpoint = `${BACKEND_URL}/api/integrations/${pathStr}`;
    } else {
      endpoint = `${BACKEND_URL}/api/integrations/custom/${pathStr}`;
    }

    const res = await fetch(endpoint, {
      method: 'POST',
      headers,
      body,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    const body = await req.json().catch(() => ({}));
    return NextResponse.json({
      id: `mock-connector-${Date.now()}`,
      name: body.name || 'Custom Connector',
      type: 'custom_connector',
      status: 'pending',
      config: {},
      settings: body.actions ? { actions: body.actions, base_url: body.base_url } : {},
      error_message: null,
      created_at: new Date().toISOString(),
    });
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathStr = path.join('/');
  const headers = getAuthHeaders(req);

  try {
    const endpoint = `${BACKEND_URL}/api/integrations/custom/${pathStr}`;
    const res = await fetch(endpoint, { headers });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json([]);
  }
}

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathStr = path.join('/');
  const headers = getAuthHeaders(req);

  try {
    const body = await req.text();
    const endpoint = `${BACKEND_URL}/api/integrations/custom/${pathStr}`;
    const res = await fetch(endpoint, {
      method: 'PUT',
      headers,
      body,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 502 });
  }
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathStr = path.join('/');
  const headers = getAuthHeaders(req);

  try {
    const endpoint = `${BACKEND_URL}/api/integrations/custom/${pathStr}`;
    const res = await fetch(endpoint, {
      method: 'DELETE',
      headers,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 502 });
  }
}
