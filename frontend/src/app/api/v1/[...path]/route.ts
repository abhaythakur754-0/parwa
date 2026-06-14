import { NextRequest, NextResponse } from 'next/server';

/**
 * Catch-all API proxy — forwards all /api/v1/* requests to the PARWA FastAPI backend.
 *
 * This allows the frontend to make API calls to relative paths like
 * `/api/v1/auth/login` which are automatically proxied to the backend.
 */

const BACKEND_URL = 'http://localhost:8000';

async function proxyRequest(req: NextRequest) {
  try {
    // Extract the path after /api/v1/
    const url = new URL(req.url);
    const pathSegments = url.pathname.replace('/api/v1/', '');
    const queryString = url.searchParams.toString();
    const backendUrl = `${BACKEND_URL}/api/v1/${pathSegments}${queryString ? `?${queryString}` : ''}`;

    // Forward all headers
    const headers: Record<string, string> = {};
    req.headers.forEach((value, key) => {
      // Skip host and connection headers
      if (key.toLowerCase() === 'host' || key.toLowerCase() === 'connection') return;
      headers[key] = value;
    });

    // Build request body for non-GET methods
    let body: string | undefined;
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      body = await req.text();
    }

    const response = await fetch(backendUrl, {
      method: req.method,
      headers,
      body,
    });

    // Build response headers
    const responseHeaders = new Headers();
    response.headers.forEach((value, key) => {
      responseHeaders.set(key, value);
    });

    const responseBody = await response.text();

    return new NextResponse(responseBody, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error: any) {
    console.error('[API Proxy] Error:', error.message);
    return NextResponse.json(
      { detail: 'Backend service unavailable' },
      { status: 503 }
    );
  }
}

export async function GET(req: NextRequest) {
  return proxyRequest(req);
}

export async function POST(req: NextRequest) {
  return proxyRequest(req);
}

export async function PUT(req: NextRequest) {
  return proxyRequest(req);
}

export async function PATCH(req: NextRequest) {
  return proxyRequest(req);
}

export async function DELETE(req: NextRequest) {
  return proxyRequest(req);
}
