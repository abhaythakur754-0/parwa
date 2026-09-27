/**
 * POST /api/kb/create-text — Create a Knowledge Base article from plain text.
 *
 * Accepts JSON: { title: string, content: string, category?: string }
 * Converts the text content into a virtual .txt file and forwards it to
 * the backend's existing /api/kb/upload endpoint (multipart/form-data).
 *
 * This lets users add KB articles directly via a text editor without
 * needing to create and upload a file — much faster for FAQs, policies,
 * and quick knowledge entries.
 *
 * Backend: POST /api/kb/upload (backend/app/api/knowledge_base.py)
 */

import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

function getProxyOrigin(): string {
  if (process.env.FRONTEND_URL) return process.env.FRONTEND_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  if (process.env.NODE_ENV === 'production') return 'https://parwa.buzz';
  return 'http://localhost:3000';
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { title, content, category } = body as {
      title?: string;
      content?: string;
      category?: string;
    };

    // ── Validate ──────────────────────────────────────────────
    if (!title || typeof title !== 'string' || title.trim().length === 0) {
      return NextResponse.json(
        { status: 'error', message: 'Title is required.' },
        { status: 400 }
      );
    }
    if (!content || typeof content !== 'string' || content.trim().length < 10) {
      return NextResponse.json(
        { status: 'error', message: 'Content must be at least 10 characters.' },
        { status: 400 }
      );
    }

    // ── Sanitize ──────────────────────────────────────────────
    const cleanTitle = title.trim().slice(0, 200);
    const cleanContent = content.trim().slice(0, 500_000); // 500KB max
    const cleanCategory = (category || 'general').trim().slice(0, 50).toLowerCase();

    // Build a slug-safe filename from the title
    const slug = cleanTitle
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'article';
    const filename = `${slug}.txt`;

    // Prepend a header so the KB processor has context about the article
    const fullText = `# ${cleanTitle}\nCategory: ${cleanCategory}\n\n${cleanContent}\n`;
    const textBytes = new TextEncoder().encode(fullText);

    // ── Build multipart/form-data ─────────────────────────────
    // We construct it manually because the backend expects an UploadFile.
    const boundary = `----parwa-kb-text-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const before = `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${filename}"\r\nContent-Type: text/plain\r\n\r\n`;
    const after = `\r\n--${boundary}--\r\n`;

    const beforeBytes = new TextEncoder().encode(before);
    const afterBytes = new TextEncoder().encode(after);
    const bodyBytes = new Uint8Array(beforeBytes.length + textBytes.length + afterBytes.length);
    bodyBytes.set(beforeBytes, 0);
    bodyBytes.set(textBytes, beforeBytes.length);
    bodyBytes.set(afterBytes, beforeBytes.length + textBytes.length);

    // ── Forward auth ──────────────────────────────────────────
    const headers: Record<string, string> = {
      'Origin': getProxyOrigin(),
      'Referer': `${getProxyOrigin()}/`,
      'Content-Type': `multipart/form-data; boundary=${boundary}`,
    };
    const authHeader = req.headers.get('authorization');
    if (authHeader) headers['Authorization'] = authHeader;
    const cookieHeader = req.headers.get('cookie');
    if (cookieHeader) {
      headers['Cookie'] = cookieHeader;
      const cookies = Object.fromEntries(
        cookieHeader.split(';').map((c) => {
          const [k, ...v] = c.trim().split('=');
          return [k, v.join('=')];
        })
      );
      if (cookies.parwa_at) headers['Authorization'] = `Bearer ${cookies.parwa_at}`;
    }

    // ── Send to backend ───────────────────────────────────────
    const res = await fetch(`${BACKEND_URL}/api/kb/upload`, {
      method: 'POST',
      headers,
      body: bodyBytes,
      signal: AbortSignal.timeout(30000),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return NextResponse.json(
        { status: 'error', message: data?.detail || data?.message || 'Backend rejected the article.', detail: data },
        { status: res.status }
      );
    }

    return NextResponse.json({
      status: 'success',
      message: `Article "${cleanTitle}" created successfully.`,
      document: data,
    });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error('[KB create-text] error:', msg?.slice(0, 200));
    return NextResponse.json(
      { status: 'error', message: 'Failed to create article. Please try again.' },
      { status: 500 }
    );
  }
}
