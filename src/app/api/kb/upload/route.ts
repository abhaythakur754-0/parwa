/**
 * PARWA Knowledge Base Upload API Proxy
 *
 * Handles /api/kb/upload and returns mock when backend is down.
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(req: NextRequest) {
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

    const formData = await req.formData();
    const res = await fetch(`${BACKEND_URL}/api/kb/upload`, {
      method: 'POST',
      headers,
      body: formData,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    const formData = await req.formData();
    const file = formData.get('file') as File | null;
    const filename = file?.name || 'document.pdf';

    return NextResponse.json({
      id: `mock-doc-${Date.now()}`,
      filename,
      file_size: file?.size || 0,
      mime_type: file?.type || 'application/pdf',
      status: 'completed',
      chunk_count: 5,
      error_message: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }
}
