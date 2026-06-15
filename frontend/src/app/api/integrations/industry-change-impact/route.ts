/**
 * PARWA Industry Change Impact API Proxy
 *
 * POST /api/integrations/industry-change-impact
 * Proxies to backend to check impact of industry change on integrations.
 * Falls back to frontend catalog comparison when backend is unreachable.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';
import {
  INTEGRATION_CATALOG,
  getIntegrationsForIndustry,
  type ParwaIndustry,
} from '@/lib/integration-catalog';

const BACKEND_URL = getBackendUrl();

/** Compute industry change impact from the frontend catalog */
function computeImpact(currentIndustry: string, newIndustry: string) {
  const curr = getIntegrationsForIndustry(currentIndustry as ParwaIndustry);
  const next = getIntegrationsForIndustry(newIndustry as ParwaIndustry);

  const currKeys = new Set(curr.map((i) => i.key));
  const nextKeys = new Set(next.map((i) => i.key));

  const stillRecommended = curr.filter((i) => nextKeys.has(i.key)).map((i) => ({ key: i.key, name: i.name }));
  const noLongerSuggested = curr.filter((i) => !nextKeys.has(i.key)).map((i) => ({ key: i.key, name: i.name }));
  const newlySuggested = next.filter((i) => !currKeys.has(i.key)).map((i) => ({ key: i.key, name: i.name }));

  return {
    current_industry: currentIndustry,
    new_industry: newIndustry,
    connected_integrations: [],
    still_recommended: stillRecommended,
    no_longer_suggested: noLongerSuggested,
    newly_suggested: newlySuggested,
  };
}

export async function POST(req: NextRequest) {
  let requestBody: { current_industry?: string; new_industry?: string } = {};
  try {
    requestBody = await req.json();
  } catch {
    // ignore parse error
  }

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

    const body = JSON.stringify(requestBody);
    const res = await fetch(`${BACKEND_URL}/api/integrations/industry-change-impact`, {
      method: 'POST',
      headers,
      body,
      signal: AbortSignal.timeout(5000),
    });

    if (res.ok) {
      const data = await res.json();
      if (data && data.current_industry && data.new_industry) {
        return NextResponse.json(data, { status: 200 });
      }
    }
    // Backend error — fall through to frontend computation
  } catch {
    // Backend unreachable — fall through to frontend computation
  }

  // Fallback: compute from frontend catalog
  const currentIndustry = requestBody.current_industry || '';
  const newIndustry = requestBody.new_industry || '';

  if (currentIndustry && newIndustry) {
    return NextResponse.json(computeImpact(currentIndustry, newIndustry));
  }

  return NextResponse.json({
    current_industry: currentIndustry,
    new_industry: newIndustry,
    connected_integrations: [],
    still_recommended: [],
    no_longer_suggested: [],
    newly_suggested: [],
    message: 'Unable to compute industry change impact.',
  }, { status: 200 });
}
