import { NextRequest, NextResponse } from 'next/server';

/**
 * Escalation API proxy route.
 *
 * Forwards requests to the backend escalation endpoints:
 *
 * GET  /api/escalations?action=list          → /api/escalations/list
 * GET  /api/escalations?action=stats          → /api/escalations/stats
 * GET  /api/escalations?action=pending        → /api/escalations/pending
 * POST /api/escalations  { action: "guidance" }                    → /api/escalations/{id}/guidance
 * POST /api/escalations  { action: "guidance-by-notification" }    → /api/escalations/guidance-by-notification
 * POST /api/escalations  { action: "resume" }                      → /api/escalations/resume
 * POST /api/escalations  { action: "auto-resume" }                 → /api/escalations/auto-resume
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

function buildHeaders(request: NextRequest): Record<string, string> {
  const origin = getProxyOrigin();
  const cookie = request.headers.get('cookie') || '';
  const accessToken = getAccessTokenFromCookie(cookie);

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Origin': origin,
    'Referer': `${origin}/`,
  };

  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  if (cookie) {
    headers['Cookie'] = cookie;
  }

  return headers;
}

// ── GET Handler ─────────────────────────────────────────────────────

export async function GET(request: NextRequest) {
  const backendUrl = getBackendUrl();
  const headers = buildHeaders(request);
  const url = new URL(request.url);
  const action = url.searchParams.get('action') || 'list';
  const tenantId = url.searchParams.get('tenant_id') || '';
  const humanStatus = url.searchParams.get('human_status') || '';
  const reprocessStatus = url.searchParams.get('reprocess_status') || '';
  const search = url.searchParams.get('search') || '';

  let backendPath = '';

  switch (action) {
    case 'stats':
      backendPath = `/api/escalations/stats?tenant_id=${encodeURIComponent(tenantId)}`;
      break;
    case 'pending':
      backendPath = `/api/escalations/pending?tenant_id=${encodeURIComponent(tenantId)}`;
      break;
    case 'list':
    default: {
      const params = new URLSearchParams();
      if (tenantId) params.set('tenant_id', tenantId);
      if (humanStatus) params.set('human_status', humanStatus);
      if (reprocessStatus) params.set('reprocess_status', reprocessStatus);
      if (search) params.set('search', search);
      backendPath = `/api/escalations/list${params.toString() ? `?${params.toString()}` : ''}`;
      break;
    }
  }

  try {
    const backendRes = await fetch(`${backendUrl}${backendPath}`, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(15000),
    });

    const text = await backendRes.text();
    try {
      const data = JSON.parse(text);
      return NextResponse.json(data, { status: backendRes.status });
    } catch {
      return NextResponse.json(
        { error: { message: text || 'Backend returned non-JSON response' } },
        { status: backendRes.status },
      );
    }
  } catch {
    return NextResponse.json(
      { error: { message: 'Escalation service unavailable. Please try again later.' } },
      { status: 503 },
    );
  }
}

// ── POST Handler ────────────────────────────────────────────────────

export async function POST(request: NextRequest) {
  const backendUrl = getBackendUrl();
  const headers = buildHeaders(request);

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: { message: 'Invalid JSON body' } },
      { status: 400 },
    );
  }

  const action = body.action as string;
  let backendPath = '';

  switch (action) {
    case 'guidance': {
      const id = body.escalation_id as string;
      if (!id) {
        return NextResponse.json(
          { error: { message: 'escalation_id is required' } },
          { status: 400 },
        );
      }
      backendPath = `/api/escalations/${encodeURIComponent(id)}/guidance`;
      break;
    }
    case 'guidance-by-notification':
      backendPath = '/api/escalations/guidance-by-notification';
      break;
    case 'resume':
      backendPath = '/api/escalations/resume';
      break;
    case 'auto-resume':
      backendPath = '/api/escalations/auto-resume';
      break;
    case 'guidance-ticket':
      backendPath = '/api/escalations/guidance-ticket';
      break;
    case 'batch-guidance-tickets':
      backendPath = '/api/escalations/batch-guidance-tickets';
      break;
    default:
      return NextResponse.json(
        { error: { message: `Unknown action: ${action}` } },
        { status: 400 },
      );
  }

  try {
    const backendRes = await fetch(`${backendUrl}${backendPath}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });

    const text = await backendRes.text();
    try {
      const data = JSON.parse(text);
      return NextResponse.json(data, { status: backendRes.status });
    } catch {
      return NextResponse.json(
        { error: { message: text || 'Backend returned non-JSON response' } },
        { status: backendRes.status },
      );
    }
  } catch {
    return NextResponse.json(
      { error: { message: 'Escalation service unavailable. Please try again later.' } },
      { status: 503 },
    );
  }
}