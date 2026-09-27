/**
 * PARWA Audit Trail API Proxy (Phase 9)
 *
 * Proxies audit trail requests from the frontend to the backend.
 *
 * Key endpoints:
 * - GET  /api/audit/entries       — List audit entries (company-scoped)
 * - GET  /api/audit/entries/{id}  — Get single audit entry
 * - GET  /api/audit/stats         — Get audit statistics
 * - GET  /api/audit/export        — Export audit entries (JSON/CSV)
 * - GET  /api/audit/alerts        — Get security alerts
 * - POST /api/audit/ai-action     — Log an AI action
 * - GET  /api/audit/integrity     — Verify audit log integrity
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';

function getAuthToken(req: NextRequest): string | undefined {
  const authHeader = req.headers.get('authorization');
  if (authHeader) return authHeader.replace('Bearer ', '');

  const cookieHeader = req.headers.get('cookie');
  if (cookieHeader) {
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => {
        const [key, ...val] = c.trim().split('=');
        return [key, val.join('=')];
      })
    );
    if (cookies.parwa_at) return cookies.parwa_at;
  }
  return undefined;
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const url = new URL(req.url);
  const searchParams = url.search;
  const authToken = getAuthToken(req);

  try {
    const { response } = await backendProxy(`/api/v1/audit${path}${searchParams}`, {
      method: 'GET',
      authToken,
    });

    // For CSV export, stream the response directly
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('text/csv')) {
      const csvData = await response.text();
      return new NextResponse(csvData, {
        status: response.status,
        headers: {
          'Content-Type': 'text/csv',
          'Content-Disposition': response.headers.get('content-disposition') || 'attachment; filename=audit_export.csv',
        },
      });
    }

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('[audit][GET] Backend unavailable:', error);
    return NextResponse.json(
      { error: { code: 'BACKEND_UNAVAILABLE', message: 'Audit service unavailable' } },
      { status: 503 }
    );
  }
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ path?: string[] }> }) {
  const { path: pathSegments } = await params;
  const path = pathSegments ? `/${pathSegments.join('/')}` : '';
  const authToken = getAuthToken(req);

  try {
    const body = await req.json();
    const { response } = await backendProxy(`/api/v1/audit${path}`, {
      method: 'POST',
      authToken,
      body: JSON.stringify(body),
      extraHeaders: { 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error('[audit][POST] Backend unavailable:', error);
    return NextResponse.json(
      { error: { code: 'BACKEND_UNAVAILABLE', message: 'Audit service unavailable' } },
      { status: 503 }
    );
  }
}
