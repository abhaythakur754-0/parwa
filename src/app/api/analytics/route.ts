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
    // Backend unavailable — return empty data (no mock)
  }

  return NextResponse.json({
    summary: {
      total_tickets: 0, open: 0, in_progress: 0, resolved: 0, closed: 0,
      awaiting_client: 0, awaiting_human: 0, critical: 0, high: 0, medium: 0, low: 0,
      resolution_rate: 0, avg_resolution_time_hours: 0, avg_first_response_time_hours: 0,
    },
    sla: {
      total_tickets_with_sla: 0, breached_count: 0, approaching_count: 0,
      compliant_count: 0, compliance_rate: 100, avg_first_response_minutes: 0, avg_resolution_minutes: 0,
    },
    by_category: [],
    trend: [],
    date_range: {
      start_date: new Date(Date.now() - 29 * 86400000).toISOString().split('T')[0],
      end_date: new Date().toISOString().split('T')[0],
    },
  });
}
