import { NextRequest, NextResponse } from 'next/server';
import { verifyAuth } from '@/lib/auth';
import { getAccessTokenFromCookies } from '@/lib/auth-cookies';
import { getBackendUrl } from '@/lib/backend-url';

interface RouteContext {
  params: Promise<{ planId: string }>;
}

async function getAuth(req: NextRequest) {
  const user = await verifyAuth(req);
  if (!user) {
    return { response: NextResponse.json({ success: false, error: 'Authentication required' }, { status: 401 }) };
  }
  if (!user.company_id) {
    return { response: NextResponse.json({ success: false, error: 'User is not associated with a company' }, { status: 403 }) };
  }
  const token =
    req.headers.get('authorization')?.replace(/^Bearer\\s+/i, '') ||
    getAccessTokenFromCookies(req as unknown as Request);
  if (!token) {
    return { response: NextResponse.json({ success: false, error: 'Authentication required' }, { status: 401 }) };
  }
  return { user, token };
}

function backendError(status: number, data: Record<string, unknown>) {
  return NextResponse.json(
    { success: false, error: data.detail || data.error || 'FlexPay request failed' },
    { status, headers: { 'Cache-Control': 'no-store' } }
  );
}

export async function GET(req: NextRequest, context: RouteContext) {
  const auth = await getAuth(req);
  if ('response' in auth) return auth.response;
  const { planId } = await context.params;

  try {
    const response = await fetch(
      `${getBackendUrl()}/api/flexpay/${encodeURIComponent(planId)}/status`,
      {
        headers: { Authorization: `Bearer ${auth.token}` },
        cache: 'no-store',
        signal: AbortSignal.timeout(10000),
      }
    );
    const data = await response.json().catch(() => ({}));
    if (!response.ok) return backendError(response.status, data);
    return NextResponse.json({ success: true, plan: data }, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    console.error('[FlexPay/API] Backend status request failed:', error);
    return NextResponse.json({ success: false, error: 'FlexPay backend is unavailable' }, { status: 503 });
  }
}

export async function POST(req: NextRequest, context: RouteContext) {
  const auth = await getAuth(req);
  if ('response' in auth) return auth.response;
  if (!['owner', 'admin'].includes(auth.user.role || '')) {
    return NextResponse.json({ success: false, error: 'Owner or admin role required' }, { status: 403 });
  }

  const { planId } = await context.params;
  let body: { action?: string; reason?: string; notes?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ success: false, error: 'Invalid JSON in request body' }, { status: 400 });
  }

  if (body.action !== 'pause' && body.action !== 'resume') {
    return NextResponse.json({ success: false, error: 'Action must be pause or resume' }, { status: 400 });
  }

  const endpoint = body.action === 'pause' ? 'pause' : 'resume';
  const payload = body.action === 'pause'
    ? { reason: typeof body.reason === 'string' ? body.reason.slice(0, 500) : 'Plan paused by owner' }
    : { notes: typeof body.notes === 'string' ? body.notes.slice(0, 500) : 'Plan resumed by owner' };

  try {
    const response = await fetch(
      `${getBackendUrl()}/api/flexpay/${encodeURIComponent(planId)}/${endpoint}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${auth.token}`,
        },
        body: JSON.stringify(payload),
        cache: 'no-store',
        signal: AbortSignal.timeout(15000),
      }
    );
    const data = await response.json().catch(() => ({}));
    if (!response.ok) return backendError(response.status, data);
    return NextResponse.json({ success: true, ...data }, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    console.error('[FlexPay/API] Backend plan update failed:', error);
    return NextResponse.json({ success: false, error: 'FlexPay backend is unavailable' }, { status: 503 });
  }
}

export async function DELETE(req: NextRequest, context: RouteContext) {
  const auth = await getAuth(req);
  if ('response' in auth) return auth.response;
  if (!['owner', 'admin'].includes(auth.user.role || '')) {
    return NextResponse.json({ success: false, error: 'Owner or admin role required' }, { status: 403 });
  }

  const { planId } = await context.params;
  const reason = req.nextUrl.searchParams.get('reason') || 'Customer requested cancellation';
  const query = new URLSearchParams({ reason: reason.slice(0, 500) });

  try {
    const response = await fetch(
      `${getBackendUrl()}/api/flexpay/${encodeURIComponent(planId)}/cancel?${query.toString()}`,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${auth.token}` },
        cache: 'no-store',
        signal: AbortSignal.timeout(15000),
      }
    );
    const data = await response.json().catch(() => ({}));
    if (!response.ok) return backendError(response.status, data);
    return NextResponse.json({ success: true, ...data }, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    console.error('[FlexPay/API] Backend plan cancellation failed:', error);
    return NextResponse.json({ success: false, error: 'FlexPay backend is unavailable' }, { status: 503 });
  }
}
