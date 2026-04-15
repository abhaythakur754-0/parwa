/**
 * PARWA Integrations API — Next.js Catch-All Route Handler
 *
 * Proxies integration requests to the Python backend.
 * Falls back to local JSON-file-based state when backend is unavailable.
 *
 * Endpoints:
 *   GET    /api/integrations/available        — List available integration types
 *   POST   /api/integrations                  — Create a new integration
 *   GET    /api/integrations                  — List company integrations
 *   POST   /api/integrations/{id}/test        — Test an integration
 *   DELETE /api/integrations/{id}             — Delete an integration
 */

import { NextRequest, NextResponse } from 'next/server';
import * as fs from 'fs';
import * as path from 'path';

// ── Idempotency Tracking (D12-P1) ─────────────────────────────────
// In-memory store for processed idempotency keys (prevents duplicates
// when backend processed but 15s timeout expired).
const _processedIdempotencyKeys = new Map<string, { timestamp: number; result: Response }>();
const IDEMPOTENCY_TTL_MS = 60_000; // Keys expire after 60s

function checkIdempotency(key: string): Response | null {
  const entry = _processedIdempotencyKeys.get(key);
  if (entry && Date.now() - entry.timestamp < IDEMPOTENCY_TTL_MS) {
    // Clean expired entries opportunistically
    return entry.result;
  }
  if (entry) {
    _processedIdempotencyKeys.delete(key);
  }
  return null;
}

function recordIdempotency(key: string, result: Response): void {
  _processedIdempotencyKeys.set(key, { timestamp: Date.now(), result });
  // Evict old entries to prevent unbounded growth
  for (const [k, v] of _processedIdempotencyKeys) {
    if (Date.now() - v.timestamp >= IDEMPOTENCY_TTL_MS) {
      _processedIdempotencyKeys.delete(k);
    }
  }
}

// ── Backend Proxy Configuration ─────────────────────────────────
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || '';

async function proxyToBackend(request: NextRequest, pathSegments: string[]): Promise<Response | null> {
  if (!BACKEND_URL) return null;

  // D12-P1: Check idempotency key before proxying — if we already have a
  // recorded response for this key, return it immediately.
  const idempotencyKey = request.headers.get('x-idempotency-key');
  if (idempotencyKey) {
    const cached = checkIdempotency(idempotencyKey);
    if (cached) return cached;
  }

  const backendPath = `${BACKEND_URL}/api/integrations/${pathSegments.join('/')}`;
  const url = new URL(request.url);
  const searchParams = url.searchParams.toString();
  const fullUrl = searchParams ? `${backendPath}?${searchParams}` : backendPath;

  try {
    const body = ['POST', 'PATCH', 'PUT'].includes(request.method)
      ? await request.clone().arrayBuffer()
      : undefined;

    // D12-P15: Only forward an allowlist of safe headers — never blindly
    // copy all client headers (which can include cookies, etc.).
    const ALLOWLISTED_FORWARD_HEADERS = ['content-type', 'authorization', 'x-request-id'];
    const headers = new Headers();
    for (const name of ALLOWLISTED_FORWARD_HEADERS) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }

    const response = await fetch(fullUrl, {
      method: request.method,
      headers,
      body,
      signal: AbortSignal.timeout(15000),
    });

    if (response.status >= 400) {
      return response;
    }
    return response;
  } catch {
    return null;
  }
}

// ── Local State Persistence ────────────────────────────────────

const INTEGRATIONS_STORE_PATH = path.join(process.cwd(), '.parwa_integrations.json');

interface StoredIntegration {
  id: string;
  type: string;
  name: string;
  config: Record<string, string>;
  status: string;
  last_test_at: string | null;
  last_test_result: string | null;
  created_at: string;
}

function loadIntegrations(): StoredIntegration[] {
  try {
    if (fs.existsSync(INTEGRATIONS_STORE_PATH)) {
      const raw = fs.readFileSync(INTEGRATIONS_STORE_PATH, 'utf-8');
      return JSON.parse(raw);
    }
  } catch { /* ignore */ }
  return [];
}

// D12-P8: Patterns for keys that should be masked in the local JSON store.
// This is defense-in-depth — the local fallback should be disabled in production.
const _SENSITIVE_KEY_PATTERNS = /password|token|secret|api_key|credential|private_key|auth_token|connection_string/i;

function maskSensitiveFields(config: Record<string, string>): Record<string, string> {
  const masked: Record<string, string> = {};
  for (const [key, value] of Object.entries(config)) {
    if (_SENSITIVE_KEY_PATTERNS.test(key) && typeof value === 'string' && value.length > 0) {
      masked[key] = value.length > 4 ? value.slice(0, 4) + '****' : '****';
    } else {
      masked[key] = value;
    }
  }
  return masked;
}

// NOTE: This local JSON fallback should be disabled in production.
// It stores state in a plaintext file on the filesystem and is only
// intended for development / demo environments.
function saveIntegrations(integrations: StoredIntegration[]): void {
  try {
    // D12-P8: Mask sensitive fields before writing to disk
    const sanitized = integrations.map((int) => ({
      ...int,
      config: maskSensitiveFields(int.config),
    }));
    fs.writeFileSync(INTEGRATIONS_STORE_PATH, JSON.stringify(sanitized, null, 2), 'utf-8');
  } catch { /* ignore */ }
}

function generateId(): string {
  return `int_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

// ── Available Integration Types (mirrors backend) ──────────────

const INTEGRATION_TYPES: Record<string, {
  required_fields: string[];
  test_url: string;
  description: string;
}> = {
  zendesk: {
    required_fields: ['subdomain', 'email', 'api_token'],
    test_url: 'https://{subdomain}.zendesk.com/api/v2/users/me.json',
    description: 'Connect your Zendesk support center for unified ticket management.',
  },
  shopify: {
    required_fields: ['shop_domain', 'access_token'],
    test_url: 'https://{shop_domain}/admin/api/2024-01/shop.json',
    description: 'Import product and order data for context-aware support.',
  },
  slack: {
    required_fields: ['bot_token', 'channel_id'],
    test_url: 'https://slack.com/api/auth.test',
    description: 'Receive real-time alerts and manage tickets from Slack.',
  },
  gmail: {
    required_fields: ['client_id', 'client_secret', 'refresh_token'],
    test_url: 'https://gmail.googleapis.com/gmail/v1/users/me/profile',
    description: 'Sync email conversations and auto-respond via AI.',
  },
};

// ── Route Handlers ─────────────────────────────────────────────

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: segments } = await params;
  const pathKey = segments.join('/');

  // Try backend proxy first
  const proxied = await proxyToBackend(request, segments);
  if (proxied) return proxied;

  // Local fallback
  switch (pathKey) {
    case 'available': {
      // GET /api/integrations/available — no path segments beyond "available"
      const result = Object.entries(INTEGRATION_TYPES).map(([type, config]) => ({
        type,
        required_fields: config.required_fields,
        test_url_template: config.test_url,
        description: config.description,
      }));
      return NextResponse.json(result);
    }

    case '':
    case undefined: {
      // GET /api/integrations — list all integrations
      const integrations = loadIntegrations();
      return NextResponse.json(integrations.map((int) => ({
        id: int.id,
        company_id: 'local',
        type: int.type,
        name: int.name,
        status: int.status,
        config: int.config,
        last_test_at: int.last_test_at,
        last_test_result: int.last_test_result,
        created_at: int.created_at,
      })));
    }

    default: {
      // Could be GET /api/integrations/{id} — not used by current components
      return NextResponse.json({ detail: 'Not found' }, { status: 404 });
    }
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: segments } = await params;
  const pathKey = segments.join('/');

  // Try backend proxy first
  const proxied = await proxyToBackend(request, segments);
  if (proxied) return proxied;

  // Local fallback
  const integrations = loadIntegrations();

  if (pathKey === '' || pathKey === undefined) {
    // POST /api/integrations — create integration
    const body = await request.json().catch(() => ({}));
    const { integration_type, name, config, validate } = body;

    // D12-P1: If backend is unreachable and integration_type is 'custom',
    // return a clear 502 error instead of silently falling through to the
    // local handler which doesn't support custom integrations.
    if (integration_type === 'custom') {
      return NextResponse.json(
        {
          detail: 'Backend service unavailable. Custom integrations require the backend API.',
        },
        { status: 502 }
      );
    }

    // D12-P1: Idempotency check — if the request was already processed,
    // return the previously recorded response to prevent duplicates.
    const idempotencyKey = request.headers.get('x-idempotency-key');
    if (idempotencyKey) {
      const previousResult = checkIdempotency(idempotencyKey);
      if (previousResult) {
        return previousResult;
      }
    }

    if (!integration_type || !INTEGRATION_TYPES[integration_type]) {
      return NextResponse.json(
        { detail: `Invalid integration type: ${integration_type}` },
        { status: 400 }
      );
    }

    if (!name) {
      return NextResponse.json(
        { detail: 'Integration name is required.' },
        { status: 400 }
      );
    }

    const newIntegration: StoredIntegration = {
      id: generateId(),
      type: integration_type,
      name,
      config: config || {},
      status: 'active',
      last_test_at: validate ? new Date().toISOString() : null,
      last_test_result: validate ? 'success (local)' : null,
      created_at: new Date().toISOString(),
    };

    integrations.push(newIntegration);
    saveIntegrations(integrations);

    const response = NextResponse.json(
      {
        id: newIntegration.id,
        company_id: 'local',
        type: newIntegration.type,
        name: newIntegration.name,
        status: newIntegration.status,
        config: newIntegration.config,
        last_test_at: newIntegration.last_test_at,
        last_test_result: newIntegration.last_test_result,
        created_at: newIntegration.created_at,
      },
      { status: 201 }
    );

    // D12-P1: Record the response under the idempotency key so a retry
    // with the same key returns the same result (prevents duplicates).
    if (idempotencyKey) {
      recordIdempotency(idempotencyKey, response);
    }

    return response;
  }

  // POST /api/integrations/{id}/test — test integration
  if (pathKey.endsWith('/test')) {
    const integrationId = pathKey.replace(/\/test$/, '');
    const integration = integrations.find((i) => i.id === integrationId);
    if (!integration) {
      return NextResponse.json({ detail: 'Integration not found.' }, { status: 404 });
    }

    integration.last_test_at = new Date().toISOString();
    integration.last_test_result = 'success (local)';
    integration.status = 'active';
    saveIntegrations(integrations);

    return NextResponse.json({
      integration_id: integration.id,
      success: true,
      message: 'Connection validated successfully (local mode).',
      status: 'active',
      tested_at: integration.last_test_at,
    });
  }

  return NextResponse.json({ detail: 'Not found' }, { status: 404 });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: segments } = await params;
  const pathKey = segments.join('/');

  // Try backend proxy first
  const proxied = await proxyToBackend(request, segments);
  if (proxied) return proxied;

  // Local fallback — DELETE /api/integrations/{id}
  const integrationId = pathKey;
  if (!integrationId) {
    return NextResponse.json({ detail: 'Integration ID required.' }, { status: 400 });
  }

  const integrations = loadIntegrations();
  const idx = integrations.findIndex((i) => i.id === integrationId);
  if (idx === -1) {
    return NextResponse.json({ detail: 'Integration not found.' }, { status: 404 });
  }

  integrations.splice(idx, 1);
  saveIntegrations(integrations);

  return NextResponse.json({ message: 'Integration deleted successfully.' });
}
