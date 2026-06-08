import { NextRequest, NextResponse } from 'next/server';

/**
 * Approvals proxy route.
 * Forwards /api/approvals/* to backend /api/approvals/*
 */

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
}

async function proxyRequest(
  method: string,
  request: NextRequest,
  pathSegments: string[],
) {
  const backendUrl = getBackendUrl();
  const fullPath = pathSegments.join('/');
  const url = new URL(request.url);
  const queryString = url.searchParams.toString();
  const backendPath = `/api/approvals/${fullPath}${queryString ? `?${queryString}` : ''}`;

  try {
    let body: string | null = null;
    if (method !== 'GET' && method !== 'DELETE') {
      try { body = await request.text(); } catch { /* no body */ }
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    const cookie = request.headers.get('cookie');
    if (cookie) headers.cookie = cookie;

    const backendRes = await fetch(`${backendUrl}${backendPath}`, {
      method,
      headers,
      body,
      signal: AbortSignal.timeout(10000),
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
      { error: { message: 'Approvals service unavailable. Please try again later.' } },
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
