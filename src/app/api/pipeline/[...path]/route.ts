import { NextRequest, NextResponse } from 'next/server';

/**
 * Jarvis Pipeline API proxy route.
 *
 * Forwards /api/pipeline/* to backend root /* (strips /api/pipeline prefix).
 *
 * The backend's jarvis_routes router (backend/app/api/jarvis_routes.py) is
 * mounted WITHOUT a prefix and serves pipeline endpoints at root:
 *   - /jarvis/status, /jarvis/metrics, /jarvis/notifications/*, /jarvis/flags/*,
 *     /jarvis/command/*, /jarvis/audit, /jarvis/customer-health, /jarvis/roi, /jarvis/chat
 *   - /quality/scores, /quality/alerts/*, /quality/recommendations, /quality/feedback,
 *     /quality/weekly-report, /quality/health-score, /quality/drift-check
 *   - /sla/status, /sla/credits
 *   - /approvals/pending, /approvals/batch
 *   - /wave8/agents, /wave8/skills, /wave8/provisioning-logs, /wave8/provision,
 *     /wave8/teach, /wave8/copilot/draft, /wave8/copilot/edit, /wave8/proactive, /wave8/correction
 *   - /emergency/shutdown, /pause_all_refunds
 *   - /tickets/submit
 *
 * This BFF route strips /api/pipeline and forwards to backend root.
 * Example: frontend GET /api/pipeline/jarvis/status → backend GET /jarvis/status
 *
 * Auth is via the parwa_at httpOnly cookie (extracted and re-injected as
 * `Authorization: Bearer` for the backend). On 401/403, attempts a token
 * refresh via /api/auth/refresh then retries once (same pattern as
 * /api/admin/[...path]/route.ts).
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

function buildHeaders(cookie: string, origin: string, accessToken: string | null): Record<string, string> {
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

async function tryRefreshToken(origin: string, cookie: string): Promise<string | null> {
  try {
    const refreshRes = await fetch(
      `${process.env.NEXT_PUBLIC_APP_URL || origin}/api/auth/refresh`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Origin': origin,
          'Cookie': cookie,
        },
        body: '{}',
        signal: AbortSignal.timeout(10000),
      },
    );
    if (!refreshRes.ok) return null;

    const setCookies = refreshRes.headers.getSetCookie?.() || [];
    let newAt: string | null = null;
    const cookieParts: string[] = [];

    for (const sc of setCookies) {
      const nameMatch = sc.match(/^([^=]+)=/);
      if (nameMatch) {
        const name = nameMatch[1].trim();
        const valMatch = sc.match(/=([^;]*)/);
        const val = valMatch ? valMatch[1] : '';
        cookieParts.push(`${name}=${val}`);
        if (name === 'parwa_at') {
          newAt = val;
        }
      }
    }

    if (newAt) {
      return cookieParts.length > 0 ? cookieParts.join('; ') : cookie;
    }
    return null;
  } catch {
    return null;
  }
}

async function proxyRequest(
  method: string,
  request: NextRequest,
  pathSegments: string[],
) {
  const backendUrl = getBackendUrl();
  const origin = getProxyOrigin();
  // Strip /api/pipeline prefix — forward to backend root
  // Example: ['jarvis','status'] → '/jarvis/status'
  const fullPath = pathSegments.join('/');
  const url = new URL(request.url);
  const queryString = url.searchParams.toString();
  const backendPath = `/${fullPath}${queryString ? `?${queryString}` : ''}`;

  try {
    let body: string | null = null;
    if (method !== 'GET' && method !== 'DELETE') {
      try { body = await request.text(); } catch { /* no body */ }
    }

    const cookie = request.headers.get('cookie') || '';
    let accessToken = getAccessTokenFromCookie(cookie);
    let currentCookie = cookie;

    // ── First attempt ───────────────────────────────────────
    let backendRes = await fetch(`${backendUrl}${backendPath}`, {
      method,
      headers: buildHeaders(currentCookie, origin, accessToken),
      body,
      signal: AbortSignal.timeout(15000),
    });

    // ── Retry once on 401/403 if we had a token (likely expired) ──
    if ((backendRes.status === 401 || backendRes.status === 403) && accessToken) {
      const refreshedCookie = await tryRefreshToken(origin, currentCookie);
      if (refreshedCookie) {
        const newAccessToken = getAccessTokenFromCookie(refreshedCookie);
        backendRes = await fetch(`${backendUrl}${backendPath}`, {
          method,
          headers: buildHeaders(refreshedCookie, origin, newAccessToken),
          body,
          signal: AbortSignal.timeout(15000),
        });
      }
    }

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
      { error: { message: 'Pipeline API service unavailable. Please try again later.' } },
      { status: 503 },
    );
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest('GET', request, path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest('POST', request, path);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest('PATCH', request, path);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest('PUT', request, path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxyRequest('DELETE', request, path);
}
