import { NextRequest, NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';

/**
 * Analytics base proxy route.
 * Proxies /api/analytics (no sub-path) to backend /analytics/tickets/dashboard
 * Extracts JWT from cookie and forwards as Authorization: Bearer header.
 */

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
}

function extractBearerToken(request: NextRequest): string | null {
  const cookieHeader = request.headers.get('cookie') || '';
  const match = cookieHeader.match(/\bparwa_at=([^;]+)/);
  return match ? match[1] : null;
}

export async function GET(request: NextRequest) {
  const authError = await requireAuth(request);
  if (authError) return authError;

  const backendUrl = getBackendUrl();
  const url = new URL(request.url);
  const queryString = url.searchParams.toString();

  const token = extractBearerToken(request);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Origin: process.env.FRONTEND_URL || 'https://parwa.buzz',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const backendRes = await fetch(
      `${backendUrl}/analytics/tickets/dashboard${queryString ? '?' + queryString : ''}`,
      {
        method: 'GET',
        headers,
        signal: AbortSignal.timeout(15_000),
        redirect: 'manual',
      },
    );

    const data = await backendRes.json();
    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    // Backend unavailable — return 503 so the UI shows empty/error state
    return NextResponse.json(
      { status: "error", message: "Analytics backend unavailable. Please try again later." },
      { status: 503 }
    );
  }
}
