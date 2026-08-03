/**
 * Vercel Cron — Keep Render Backend Awake
 *
 * Runs every 10 minutes via vercel.json cron config.
 * Pings the Render backend /health endpoint to prevent
 * the free tier from sleeping after 15 min of inactivity.
 *
 * Free: Vercel cron jobs are free (included in Hobby plan).
 * Schedule: every 10 minutes (see vercel.json crons config)
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
