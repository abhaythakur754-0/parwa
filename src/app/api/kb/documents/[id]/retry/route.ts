/**
 * PARWA Knowledge Base Document Retry API Proxy
 *
 * Handles POST /api/kb/documents/:id/retry
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const headers: Record<string, string> = {};
    const authHeader = req.headers.get('authorization');
    if (authHeader) headers['Authorization'] = authHeader;
    const cookieHeader = req.headers.get('cookie');
    if (cookieHeader) {
      const cookies = Object.fromEntries(
        cookieHeader.split(';').map((c) => { const [k, ...v] = c.trim().split('='); return [k, v.join('=')]; })
      );
      if (cookies.parwa_at) headers['Authorization'] = `Bearer ${cookies.parwa_at}`;
    }

    const res = await fetch(`${BACKEND_URL}/api/kb/documents/${id}/retry`, {
      method: 'POST',
      headers,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    // Mock fallback
    return NextResponse.json({
      id,
      status: 'processing',
      message: 'Retry initiated',
    });
  }
}
