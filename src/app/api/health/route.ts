import { NextResponse } from 'next/server';

/**
 * Health-check proxy — forwards to the Render backend's /health endpoint.
 * Used by external pingers (cron-job.org, UptimeRobot) so they can hit
 * either parwa.buzz/api/health or parwa-backend.onrender.com/health.
 */
export async function GET() {
  try {
    const backendUrl = process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
    const res = await fetch(`${backendUrl}/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      // Give the backend enough time to wake from cold start
      signal: AbortSignal.timeout(55_000),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error(
      '[health] Backend unreachable:',
      err instanceof Error ? err.name : 'UnknownError',
    );
    return NextResponse.json(
      {
        status: 'error',
        message: 'Backend unreachable — may be waking from sleep',
      },
      { status: 502, headers: { 'Cache-Control': 'no-store' } },
    );
  }
}
