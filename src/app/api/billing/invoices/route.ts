import { NextRequest, NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';

/**
 * GET /api/billing/invoices
 * Proxies to backend GET /api/billing/invoices (paginated invoice list).
 *
 * Extracts JWT from cookie and forwards as Authorization: Bearer header.
 *
 * Query params (optional, passed through):
 *   page (default 1), page_size (default 20, max 50)
 *
 * See backend/app/api/billing.py:list_invoices for canonical implementation.
 */

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
}

function extractBearerToken(request: NextRequest): string | null {
  const authHeader = request.headers.get('authorization');
  if (authHeader && authHeader.startsWith('Bearer ')) {
    return authHeader.slice(7);
  }
  const cookieHeader = request.headers.get('cookie') || '';
  const match = cookieHeader.match(/\bparwa_at=([^;]+)/);
  return match ? match[1] : null;
}

export async function GET(request: NextRequest) {
  const authError = await requireAuth(request);
  if (authError) return authError;

  const backendUrl = getBackendUrl();
  const url = new URL(request.url);
  const queryString = url.searchParams.toString();

  const targetUrl = `${backendUrl}/api/billing/invoices${queryString ? '?' + queryString : ''}`;

  const token = extractBearerToken(request);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Origin: process.env.FRONTEND_URL || 'https://parwa.buzz',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const backendRes = await fetch(targetUrl, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(15_000),
      redirect: 'manual',
    });

    const data = await backendRes.json();
    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    console.error('[/api/billing/invoices] Backend unreachable:', err);
    // HONEST failure: never fabricate an empty invoice list — the billing
    // page must show an error state, not "No invoices yet" (real invoices
    // may exist). Mirrors /api/tickets/route.ts.
    return NextResponse.json(
      {
        error: {
          code: 'BACKEND_UNAVAILABLE',
          message: 'Could not reach the billing service. Please retry in a moment.',
        },
      },
      { status: 502 },
    );
  }
}
