/**
 * Vercel Cron — Keep Render Backend Awake
 *
 * Runs once per day at 9 AM UTC via vercel.json cron config.
 * (Vercel Hobby plan limits cron to once-per-day execution.)
 * Pings the Render backend /health endpoint.
 *
 * NOTE: This only keeps Render awake ONCE per day. For continuous
 * keep-alive (every 10 min), use a free external service like
 * cron-job.org or UptimeRobot — they can ping /api/cron/keep-alive
 * at any interval without Vercel restrictions.
 *
 * Free: Vercel cron jobs are free (included in Hobby plan).
 * Schedule: daily at 9 AM UTC
 */

import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const maxDuration = 10;

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
}

export async function GET() {
  const backendUrl = getBackendUrl();
  const startTime = Date.now();

  try {
    const res = await fetch(`${backendUrl}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(8000),
    });

    const elapsed = Date.now() - startTime;

    if (res.ok) {
      return NextResponse.json({
        status: 'ok',
        backend: backendUrl,
        response_time_ms: elapsed,
        timestamp: new Date().toISOString(),
      });
    }

    return NextResponse.json({
      status: 'error',
      backend: backendUrl,
      http_status: res.status,
      response_time_ms: elapsed,
      timestamp: new Date().toISOString(),
    }, { status: 502 });
  } catch (error) {
    const elapsed = Date.now() - startTime;
    return NextResponse.json({
      status: 'error',
      backend: backendUrl,
      error: error instanceof Error ? error.message : 'unknown',
      response_time_ms: elapsed,
      timestamp: new Date().toISOString(),
    }, { status: 502 });
  }
}
