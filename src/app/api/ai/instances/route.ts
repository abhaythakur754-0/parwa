import { NextRequest, NextResponse } from 'next/server';

/**
 * /api/ai/instances — Variant instances endpoint
 *
 * Returns variant instances for the company. Tries the backend first,
 * falls back to an in-memory store when the backend is unavailable.
 *
 * Phase 5 FIX: Gracefully handles empty variant_limits table.
 * When no variants exist yet (pre-onboarding), returns empty array
 * instead of erroring.
 */

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
}

function getProxyOrigin(): string {
  if (process.env.FRONTEND_URL) return process.env.FRONTEND_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  if (process.env.NODE_ENV === 'production') return 'https://parwa.buzz';
  return 'http://localhost:3000';
}

function getAccessTokenFromCookie(cookieHeader: string): string | null {
  const match = cookieHeader.match(/(?:^|;\s*)parwa_at=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function extractCompanyIdFromToken(token: string): string | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString());
    return payload.company_id || payload.companyId || null;
  } catch {
    return null;
  }
}

// ── In-memory variant instance store ──────────────────────────────────

interface LocalInstance {
  id: string;
  company_id: string;
  instance_name: string;
  variant_type: string;
  status: string;
  created_at: string;
}

// In-memory store (survives across requests within same server process)
const memoryStore: LocalInstance[] = [];

export function writeLocalInstance(instance: LocalInstance): void {
  // Remove existing instance for same company+variant (update)
  const idx = memoryStore.findIndex(
    (i) => i.company_id === instance.company_id && i.variant_type === instance.variant_type
  );
  if (idx >= 0) {
    memoryStore[idx] = instance;
  } else {
    memoryStore.push(instance);
  }
  console.log(`[instances] Stored variant ${instance.variant_type} for company ${instance.company_id}`);
}

// Variant defaults for enrichment
const VARIANT_DEFAULTS: Record<string, Record<string, unknown>> = {
  mini: { maxConcurrent: 50, techniqueTier: 1, model: 'gpt-4o-mini', accuracyRate: 92.5, avgLatencyMs: 340, costPerQuery: 0.012 },
  parwa: { maxConcurrent: 200, techniqueTier: 2, model: 'gpt-4o', accuracyRate: 96.8, avgLatencyMs: 520, costPerQuery: 0.034 },
  high: { maxConcurrent: 500, techniqueTier: 3, model: 'claude-3.5-sonnet', accuracyRate: 98.2, avgLatencyMs: 680, costPerQuery: 0.058 },
};

function serializeLocalInstance(row: LocalInstance): Record<string, unknown> {
  const variantType = String(row.variant_type || 'parwa');
  const defaults = VARIANT_DEFAULTS[variantType] || VARIANT_DEFAULTS.parwa;
  const maxConcurrent = Number(defaults.maxConcurrent);

  return {
    id: row.id,
    name: row.instance_name,
    variant_type: variantType,
    status: row.status || 'active',
    channel_assignment: 'all',
    capacity_config: { max_concurrent: maxConcurrent },
    current_load: 0,
    accuracy_rate: defaults.accuracyRate,
    avg_latency_ms: defaults.avgLatencyMs,
    cost_per_query: defaults.costPerQuery,
    technique_tier: defaults.techniqueTier,
    model: defaults.model,
  };
}

function readLocalInstances(companyId: string): Record<string, unknown>[] {
  const companyInstances = memoryStore.filter(
    (i) => i.company_id === companyId && i.status === 'active'
  );
  return companyInstances.map(serializeLocalInstance);
}

export async function GET(request: NextRequest) {
  const cookie = request.headers.get('cookie') || '';
  const accessToken = getAccessTokenFromCookie(cookie);

  let companyId = accessToken
    ? extractCompanyIdFromToken(accessToken)
    : null;

  const url = new URL(request.url);
  if (!companyId) {
    companyId = url.searchParams.get('company_id');
  }

  // Try backend first
  try {
    const origin = getProxyOrigin();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Origin': origin,
      'Referer': `${origin}/`,
    };

    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    const backendUrl = getBackendUrl();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);

    const res = await fetch(`${backendUrl}/api/ai/instances`, {
      method: 'GET',
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (res.ok) {
      const data = await res.json();
      // Backend may return items array or empty — both are valid
      if (data.items && Array.isArray(data.items)) {
        // Even if empty, that's valid (user hasn't completed onboarding yet)
        return NextResponse.json(data);
      }
      // Backend returned unexpected shape — wrap it
      if (Array.isArray(data)) {
        return NextResponse.json({ items: data, total: data.length });
      }
    }
  } catch (err) {
    console.warn('[instances-route] Backend failed, using local:', err);
  }

  // Fallback: in-memory store
  if (companyId) {
    const localInstances = readLocalInstances(companyId);
    if (localInstances.length > 0) {
      return NextResponse.json({ items: localInstances, total: localInstances.length });
    }
  }

  // No variants exist yet — this is valid for pre-onboarding state
  // Return empty array instead of error
  return NextResponse.json({ items: [], total: 0 });
}
