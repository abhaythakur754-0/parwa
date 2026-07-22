import { NextRequest, NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';

/**
 * GET /api/billing/status
 * Proxies to backend GET /api/billing/status (CompanyBillingStatusResponse).
 *
 * Returns the company's current subscription tier, plan, usage, and limits.
 * Used by the billing page to show current plan + usage stats.
 *
 * See backend/app/api/billing.py:get_billing_status for canonical implementation.
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
  const targetUrl = `${backendUrl}/api/billing/status`;

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
    console.error('[/api/billing/status] Backend unreachable:', err);
    // Return a safe default so the billing page can still render
    return NextResponse.json({
      tier: 'mini',
      plan_name: 'Starter',
      billing_cycle: 'monthly',
      status: 'inactive',
      seats_used: 0,
      seats_limit: 3,
      tickets_used_this_month: 0,
      tickets_limit: 1000,
      tokens_used_this_month: 0,
      tokens_limit: 100000,
    }, { status: 200 });
  }
}
