/**
 * PARWA Knowledge Base Upload API
 *
 * Handles /api/kb/upload — accepts multipart/form-data file uploads
 * and proxies them to the backend. Falls back gracefully if backend is unreachable.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

/**
 * Extract auth token from request.
 */
function getAuthToken(req: NextRequest): string | undefined {
  const authHeader = req.headers.get('authorization');
  if (authHeader) return authHeader.replace('Bearer ', '');

  const cookieHeader = req.headers.get('cookie');
  if (cookieHeader) {
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => {
        const [key, ...val] = c.trim().split('=');
        return [key, val.join('=')];
      })
    );
    if (cookies.parwa_at) return cookies.parwa_at;
  }
  return undefined;
}

export async function POST(req: NextRequest) {
  const authToken = getAuthToken(req);

  try {
    // Get the form data from the request
    const formData = await req.formData();
    const file = formData.get('file') as File | null;

    if (!file) {
      return NextResponse.json(
        { error: 'No file provided', message: 'Please select a file to upload.' },
        { status: 400 }
      );
    }

    // Validate file size (50 MB)
    const MAX_SIZE = 50 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      return NextResponse.json(
        { error: 'file_too_large', message: `File "${file.name}" exceeds 50 MB limit.` },
        { status: 400 }
      );
    }

    // Validate file extension
    const ALLOWED = ['.pdf', '.docx', '.doc', '.txt', '.csv', '.md', '.json'];
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED.includes(ext)) {
      return NextResponse.json(
        { error: 'invalid_file_type', message: `File type "${ext}" not allowed. Allowed: ${ALLOWED.join(', ')}` },
        { status: 400 }
      );
    }

    // Try to proxy to backend
    const headers: Record<string, string> = {};
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const backendFormData = new FormData();
    backendFormData.append('file', file);

    const backendRes = await fetch(`${BACKEND_URL}/api/kb/upload`, {
      method: 'POST',
      headers,
      body: backendFormData as unknown as BodyInit,
    });

    if (backendRes.ok) {
      const data = await backendRes.json();
      return NextResponse.json(data);
    }

    // Backend returned error — try to forward the error
    try {
      const errorBody = await backendRes.json();
      return NextResponse.json(errorBody, { status: backendRes.status });
    } catch {
      return NextResponse.json(
        { error: 'backend_error', message: `Backend returned ${backendRes.status}` },
        { status: backendRes.status }
      );
    }
  } catch (err) {
    console.error('[kb/upload] Error:', err);
    return NextResponse.json(
      { error: 'upload_failed', message: 'File upload failed. Please try again.' },
      { status: 500 }
    );
  }
}
