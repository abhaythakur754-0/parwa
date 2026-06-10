import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

/**
 * System health proxy route.
 * Forwards /api/system/health to backend /api/system/health
 */

export async function GET(request: NextRequest) {
  const backendUrl = getBackendUrl();

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    const cookie = request.headers.get('cookie');
    if (cookie) headers.cookie = cookie;

    const backendRes = await fetch(`${backendUrl}/api/system/health`, {
      headers,
      signal: AbortSignal.timeout(8000),
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
    // Backend unavailable — return degraded status
    return NextResponse.json({
      overall_status: 'degraded',
      services: [
        { name: 'api', status: 'healthy', latency_ms: 0, last_checked: new Date().toISOString(), uptime: 99.9, message: 'Frontend is running' },
        { name: 'database', status: 'down', latency_ms: -1, last_checked: new Date().toISOString(), uptime: 0, message: 'Backend unreachable' },
        { name: 'redis', status: 'down', latency_ms: -1, last_checked: new Date().toISOString(), uptime: 0, message: 'Backend unreachable' },
        { name: 'celery', status: 'down', latency_ms: -1, last_checked: new Date().toISOString(), uptime: 0, message: 'Backend unreachable' },
        { name: 'langgraph', status: 'down', latency_ms: -1, last_checked: new Date().toISOString(), uptime: 0, message: 'Backend unreachable' },
        { name: 'socketio', status: 'down', latency_ms: -1, last_checked: new Date().toISOString(), uptime: 0, message: 'Backend unreachable' },
        { name: 'email', status: 'down', latency_ms: -1, last_checked: new Date().toISOString(), uptime: 0, message: 'Backend unreachable' },
        { name: 'sms', status: 'down', latency_ms: -1, last_checked: new Date().toISOString(), uptime: 0, message: 'Backend unreachable' },
      ],
      queues: [],
      alerts: [],
      is_maintenance: false,
      maintenance_message: null,
    });
  }
}
