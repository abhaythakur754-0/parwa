/**
 * PARWA Voice API — Next.js Catch-All Proxy Route
 *
 * Proxies all /api/voice/* requests to the backend FastAPI server
 * at BACKEND_URL/api/v1/voice/*.
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || '';

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyToBackend(request, path);
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyToBackend(request, path);
}

export async function PUT(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyToBackend(request, path);
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyToBackend(request, path);
}

async function proxyToBackend(request: NextRequest, pathSegments: string[]): Promise<NextResponse> {
  if (!BACKEND_URL) {
    return NextResponse.json(
      { error: { code: 'BACKEND_NOT_CONFIGURED', message: 'Voice service is not configured. Set BACKEND_URL environment variable.' } },
      { status: 503 }
    );
  }

  const backendPath = `${BACKEND_URL}/api/v1/voice/${pathSegments.join('/')}`;
  const url = new URL(request.url);
  const searchParams = url.searchParams.toString();
  const fullUrl = searchParams ? `${backendPath}?${searchParams}` : backendPath;

  try {
    const body = ['POST', 'PATCH', 'PUT'].includes(request.method)
      ? await request.arrayBuffer()
      : undefined;

    const headers = new Headers(request.headers);
    headers.delete('host');

    const response = await fetch(fullUrl, {
      method: request.method,
      headers,
      body,
      signal: AbortSignal.timeout(20000),
    });

    const data = await response.text();
    return new NextResponse(data, {
      status: response.status,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'application/json',
      },
    });
  } catch (err) {
    console.error('[Voice] Backend proxy failed:', (err instanceof Error ? err.message : String(err))?.slice(0, 150));
    return NextResponse.json(
      { error: { code: 'BACKEND_UNREACHABLE', message: 'Voice service is currently unavailable. Please try again later.' } },
      { status: 502 }
    );
  }
}