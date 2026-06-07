import { NextRequest, NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';

/**
 * Analytics proxy route.
 * Proxies /api/analytics/* to backend /analytics/tickets/*
 * Falls back to mock data when backend is unavailable.
 */

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
}

export async function GET(request: NextRequest) {
  const authError = await requireAuth(request);
  if (authError) return authError;

  const backendUrl = getBackendUrl();
  const url = new URL(request.url);
  const path = url.searchParams.toString() ? `?${url.searchParams.toString()}` : '';

  try {
    const backendRes = await fetch(`${backendUrl}/analytics/tickets/dashboard${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...Object.fromEntries(request.headers.entries()),
      },
      signal: AbortSignal.timeout(8000),
    });

    if (backendRes.ok) {
      const data = await backendRes.json();
      return NextResponse.json({ data });
    }
  } catch {
    // Backend unavailable — fall through to mock
  }

  // Mock fallback
  const mockData = {
    summary: {
      total_tickets: 1247,
      open: 89,
      in_progress: 156,
      resolved: 834,
      closed: 168,
      awaiting_client: 45,
      awaiting_human: 23,
      critical: 12,
      high: 67,
      medium: 423,
      low: 745,
      resolution_rate: 87.3,
      avg_resolution_time_hours: 2.4,
      avg_first_response_time_hours: 0.3,
    },
    sla: {
      total_tickets_with_sla: 1247,
      breached_count: 23,
      approaching_count: 45,
      compliant_count: 1179,
      compliance_rate: 94.5,
      avg_first_response_minutes: 18,
      avg_resolution_minutes: 144,
    },
    by_category: [
      { category: 'Billing', count: 312, percentage: 25.0 },
      { category: 'Technical', count: 280, percentage: 22.5 },
      { category: 'Account', count: 198, percentage: 15.9 },
      { category: 'Returns', count: 175, percentage: 14.0 },
      { category: 'Shipping', count: 142, percentage: 11.4 },
      { category: 'Other', count: 140, percentage: 11.2 },
    ],
    trend: Array.from({ length: 30 }, (_, i) => ({
      timestamp: new Date(Date.now() - (29 - i) * 86400000).toISOString(),
      count: Math.floor(30 + Math.random() * 40),
      label: new Date(Date.now() - (29 - i) * 86400000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    })),
    date_range: {
      start_date: new Date(Date.now() - 29 * 86400000).toISOString().split('T')[0],
      end_date: new Date().toISOString().split('T')[0],
    },
  };

  return NextResponse.json({ data: mockData, _mock: true });
}
