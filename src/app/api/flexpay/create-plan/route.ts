import { NextRequest, NextResponse } from 'next/server';
import { verifyAuth } from '@/lib/auth';
import { getAccessTokenFromCookies } from '@/lib/auth-cookies';
import { getBackendUrl } from '@/lib/backend-url';

async function getVerifiedRequest(req: NextRequest) {
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

export async function POST(req: NextRequest) {
  const auth = await getVerifiedRequest(req);
  if ('response' in auth) return auth.response;

  let body: { variant_tier?: string; tier?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ success: false, error: 'Invalid JSON in request body' }, { status: 400 });
  }

  const variantTier = body.variant_tier || body.tier;
  if (!variantTier || !['mini', 'parwa', 'high'].includes(variantTier.toLowerCase())) {
    return NextResponse.json({ success: false, error: 'Invalid variant_tier' }, { status: 400 });
  }

  try {
    const response = await fetch(`${getBackendUrl()}/api/flexpay/create-plan`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${auth.token}`,
      },
      body: JSON.stringify({ variant_tier: variantTier.toLowerCase() }),
      cache: 'no-store',
      signal: AbortSignal.timeout(20000),
    });
    const data = await response.json().catch(() => ({ error: 'Invalid backend response' }));
    return NextResponse.json(data, { status: response.status, headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    console.error('[FlexPay/API] Backend plan creation failed:', error);
    return NextResponse.json(
      { success: false, error: 'FlexPay backend is unavailable; no plan was created.' },
      { status: 503, headers: { 'Cache-Control': 'no-store' } }
    );
  }
}

export async function GET(req: NextRequest) {
  const auth = await getVerifiedRequest(req);
  if ('response' in auth) return auth.response;

  try {
    const response = await fetch(`${getBackendUrl()}/api/flexpay/company-plans`, {
      headers: { Authorization: `Bearer ${auth.token}` },
      cache: 'no-store',
      signal: AbortSignal.timeout(10000),
    });
    const data = await response.json().catch(() => ({ error: 'Invalid backend response' }));
    if (!response.ok) {
      return NextResponse.json(
        { success: false, error: data.detail || data.error || 'FlexPay plan query failed' },
        { status: response.status, headers: { 'Cache-Control': 'no-store' } }
      );
    }
    return NextResponse.json(
      { success: true, plans: data, stats: { totalPlans: Array.isArray(data) ? data.length : 0 } },
      { headers: { 'Cache-Control': 'no-store' } }
    );
  } catch (error) {
    console.error('[FlexPay/API] Backend plan query failed:', error);
    return NextResponse.json(
      { success: false, error: 'FlexPay backend is unavailable.' },
      { status: 503, headers: { 'Cache-Control': 'no-store' } }
    );
  }
}
