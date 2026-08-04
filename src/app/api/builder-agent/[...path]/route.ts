import { NextRequest, NextResponse } from 'next/server';

function getBackendUrl(): string {
  return process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
}

function getAccessTokenFromCookie(cookieHeader: string): string | null {
  const match = cookieHeader.match(/(?:^|;\s*)parwa_at=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const fullPath = (await params).path.join('/');
  const backendUrl = getBackendUrl();
  const cookie = request.headers.get('cookie') || '';
  const accessToken = getAccessTokenFromCookie(cookie);

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  if (cookie) {
    headers['Cookie'] = cookie;
  }

  try {
    const body = await request.text();
    const res = await fetch(`${backendUrl}/api/builder-agent/${fullPath}`, {
      method: 'POST',
      headers,
      body,
      signal: AbortSignal.timeout(120000),
    });
    const text = await res.text();
    try {
      const data = JSON.parse(text);
      return NextResponse.json(data, { status: res.status });
    } catch {
      return NextResponse.json({ error: text }, { status: res.status });
    }
  } catch (error) {
    return NextResponse.json(
      { error: { message: 'Builder API unavailable' } },
      { status: 503 },
    );
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const fullPath = (await params).path.join('/');
  const backendUrl = getBackendUrl();
  const cookie = request.headers.get('cookie') || '';
  const accessToken = getAccessTokenFromCookie(cookie);

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  if (cookie) {
    headers['Cookie'] = cookie;
  }

  try {
    const res = await fetch(`${backendUrl}/api/builder-agent/${fullPath}`, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(30000),
    });
    const text = await res.text();
    try {
      const data = JSON.parse(text);
      return NextResponse.json(data, { status: res.status });
    } catch {
      return NextResponse.json({ error: text }, { status: res.status });
    }
  } catch (error) {
    return NextResponse.json(
      { error: { message: 'Builder API unavailable' } },
      { status: 503 },
    );
  }
}
