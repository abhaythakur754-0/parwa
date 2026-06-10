/**
 * PARWA Integration Catalog API Proxy
 *
 * GET /api/integrations/catalog?industry=saas
 * Proxies to backend /api/integrations/catalog with optional industry filter.
 * Falls back to the frontend catalog when backend is unreachable.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';
import {
  INTEGRATION_CATALOG,
  getIntegrationsForIndustry,
  type ParwaIndustry,
} from '@/lib/integration-catalog';

const BACKEND_URL = getBackendUrl();

/** Convert frontend IntegrationDefinition to the JSON shape the API returns */
function catalogToJson(items: typeof INTEGRATION_CATALOG) {
  return items.map((i) => ({
    key: i.key,
    name: i.name,
    description: i.description,
    category: i.category,
    tier: i.tier,
    authSchema: i.authSchema,
    testConnection: i.testConnection,
    suggestedIndustries: i.suggestedIndustries,
    availableForVariants: i.availableForVariants || [],
    iconId: i.iconId,
    colorGradient: i.colorGradient,
    available: i.available,
  }));
}

export async function GET(req: NextRequest) {
  const industry = req.nextUrl.searchParams.get('industry');

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

    const url = industry
      ? `${BACKEND_URL}/api/integrations/catalog?industry=${encodeURIComponent(industry)}`
      : `${BACKEND_URL}/api/integrations/catalog`;

    const res = await fetch(url, { headers, signal: AbortSignal.timeout(5000) });

    if (res.ok) {
      const data = await res.json();
      // If backend returns empty array, fall back to frontend catalog
      if (Array.isArray(data) && data.length > 0) {
        return NextResponse.json(data, { status: 200 });
      }
    }
    // Backend returned error or empty — fall through to frontend catalog
  } catch {
    // Backend unreachable — fall through to frontend catalog
  }

  // Fallback: use frontend catalog
  if (industry) {
    const parwaIndustry = industry as ParwaIndustry;
    return NextResponse.json(catalogToJson(getIntegrationsForIndustry(parwaIndustry)));
  }
  return NextResponse.json(catalogToJson(INTEGRATION_CATALOG));
}
