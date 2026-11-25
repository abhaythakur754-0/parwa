import { NextRequest, NextResponse } from 'next/server';
import { verifyAuth } from '@/lib/auth';
import { getAccessTokenFromCookies } from '@/lib/auth-cookies';
import { getBackendUrl } from '@/lib/backend-url';

interface RouteContext {
  params: Promise<{ planId: string; action: string }>;
}

async function authorize(req: NextRequest) {
  const user = await verifyAuth(req);
  if (!user) {
    return { response: NextResponse.json({ error: 'Authentication required' }, { status: 401 }) };
  }
  if (!user.company_id) {
    return { response: NextResponse.json({ error: 'User is not associated with a company' }, { status: 403 }) };
  }
  const token =
    req.headers.get('authorization')?.replace(/^Bearer\\s+/i, '') ||
    getAccessTokenFromCookies(req as unknown as Request);
  if (!token) {
    return { response: NextResponse.json({ error: 'Authentication required' }, { status: 401 }) };
  }
  return { user, token };
}

async function forward(
  req: NextRequest,
  planId: string,
  action: string,
  method: 'GET' | 'POST',
  body?: Record<string, unknown>,
) {
  const auth = await authorize(req);
  if ('response' in auth) return auth.response;

  if (method === 'POST' && !['owner', 'admin'].includes(auth.user.role || '')) {
    return NextResponse.json({ error: 'Owner or admin role required' }, { status: 403 });
  }

  const safePlanId = encodeURIComponent(planId);
  let url = `${getBackendUrl()}/api/flexpay/${safePlanId}/${action}`;
  if (action === 'cancel' && body && typeof body.reason === 'string') {
    const query = new URLSearchParams({ reason: body.reason.slice(0, 500) });
    url += `?${query.toString()}`;
  }

  try {
    const response = await fetch(url, {
      method,
      headers: {
        Authorization: `Bearer ${auth.token}`,
        ...(method === 'POST' && action !== 'cancel' ? { 'Content-Type': 'application/json' } : {}),
      },
      ...(method === 'POST' && action !== 'cancel' ? { body: JSON.stringify(body || {}) } : {}),
      cache: 'no-store',
      signal: AbortSignal.timeout(15000),
    });
    const data = await response.json().catch(() => ({ error: 'Invalid backend response' }));
    return NextResponse.json(data, {
      status: response.status,
      headers: { 'Cache-Control': 'no-store' },
    });
  } catch (error) {
    console.error('[FlexPay/API] Backend request failed:', error);
    return NextResponse.json({ error: 'FlexPay backend is unavailable' }, { status: 503 });
  }
}

export async function GET(req: NextRequest, context: RouteContext) {
  const { planId, action } = await context.params;
  if (action !== 'status') {
    return NextResponse.json({ error: 'Unsupported FlexPay action' }, { status: 404 });
  }
  return forward(req, planId, action, 'GET');
}

export async function POST(req: NextRequest, context: RouteContext) {
  const { planId, action } = await context.params;
  if (!['pause', 'resume', 'cancel'].includes(action)) {
    return NextResponse.json({ error: 'Unsupported FlexPay action' }, { status: 404 });
  }
  let body: Record<string, unknown> = {};
  try {
    const parsed = await req.json();
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) body = parsed;
  } catch {
    body = {};
  }
  return forward(req, planId, action, 'POST', body);
}
