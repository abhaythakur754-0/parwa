/**
 * PARWA Knowledge Base API — Next.js Catch-All Route Handler
 *
 * Proxies KB requests to the Python backend.
 * Falls back to local JSON-file-based state when backend is unavailable.
 *
 * Endpoints:
 *   POST   /api/kb/upload                   — Upload a document
 *   GET    /api/kb/documents                — List all documents
 *   GET    /api/kb/documents/{id}           — Get document status
 *   DELETE /api/kb/documents/{id}           — Delete a document
 *   POST   /api/kb/documents/{id}/retry     — Retry failed document
 *   POST   /api/kb/documents/{id}/reindex   — Re-index a document
 *   GET    /api/kb/stats                    — Get KB statistics
 *   POST   /api/kb/retry-failed             — Retry all failed documents
 */

import { NextRequest, NextResponse } from 'next/server';
import * as fs from 'fs';
import * as path from 'path';

// ── Auth Guard ──────────────────────────────────────────────────
function checkAuth(request: NextRequest): boolean {
  const sessionCookie = request.cookies.get('parwa_session');
  if (sessionCookie?.value) return true;
  const authHeader = request.headers.get('authorization');
  if (authHeader) return true;
  return false;
}

// ── Backend Proxy Configuration ─────────────────────────────────
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || '';

async function proxyToBackend(request: NextRequest, pathSegments: string[]): Promise<Response | null> {
  if (!BACKEND_URL) return null;

  const backendPath = `${BACKEND_URL}/api/kb/${pathSegments.join('/')}`;
  const url = new URL(request.url);
  const searchParams = url.searchParams.toString();
  const fullUrl = searchParams ? `${backendPath}?${searchParams}` : backendPath;

  try {
    const headers = new Headers(request.headers);
    headers.delete('host');

    const response = await fetch(fullUrl, {
      method: request.method,
      headers,
      body: ['POST', 'PATCH', 'PUT'].includes(request.method)
        ? request.body
        : undefined,
      signal: AbortSignal.timeout(30000),
    });

    if (response.status >= 400) {
      return response;
    }
    return response;
  } catch {
    return null;
  }
}

// ── Local State Persistence ────────────────────────────────────

const KB_STORE_PATH = path.join(process.cwd(), '.parwa_kb_documents.json');

interface StoredDocument {
  id: string;
  filename: string;
  file_type: string | null;
  file_size: number | null;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count: number | null;
  error_message: string | null;
  retry_count: number;
  created_at: string;
}

function loadDocuments(): StoredDocument[] {
  try {
    if (fs.existsSync(KB_STORE_PATH)) {
      const raw = fs.readFileSync(KB_STORE_PATH, 'utf-8');
      return JSON.parse(raw);
    }
  } catch { /* ignore */ }
  return [];
}

// Write queue to prevent race conditions under concurrent requests
let writePromise: Promise<void> = Promise.resolve();

function saveDocuments(docs: StoredDocument[]): Promise<void> {
  writePromise = writePromise
    .then(() => fs.promises.writeFile(KB_STORE_PATH, JSON.stringify(docs, null, 2), 'utf-8'))
    .catch((err) => {
      console.error('Failed to save KB documents:', err);
    });
  return writePromise;
}

// D13-P18: Use crypto.randomUUID() to eliminate collision risk
function generateId(): string {
  return crypto.randomUUID();
}

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt', '.csv', '.md', '.json'];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB
const LOCAL_MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB for local fallback

// ── Filename Sanitization ───────────────────────────────────────
function sanitizeFilename(name: string): string {
  // Replace backslashes with forward slashes, take basename, remove null bytes
  let safe = name.replace(/\\/g, '/');
  const segments = safe.split('/');
  safe = segments[segments.length - 1] || '';
  safe = safe.replace(/\0/g, '');
  if (safe.length > 255) safe = safe.slice(0, 255);
  return safe || 'unnamed_file';
}

// ── Route Handlers ─────────────────────────────────────────────

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  if (!checkAuth(request)) {
    return NextResponse.json({ detail: 'Authentication required.' }, { status: 401 });
  }

  const { path: segments } = await params;
  const pathKey = segments.join('/');

  // Try backend proxy first
  const proxied = await proxyToBackend(request, segments);
  if (proxied) return proxied;

  // Local fallback
  const docs = loadDocuments();

  switch (pathKey) {
    case 'documents':
      return NextResponse.json(docs);

    case 'stats':
      return NextResponse.json({
        total_documents: docs.length,
        total_chunks: docs.reduce((sum, d) => sum + (d.chunk_count || 0), 0),
        completed: docs.filter((d) => d.status === 'completed').length,
        processing: docs.filter((d) => d.status === 'processing').length,
        failed: docs.filter((d) => d.status === 'failed').length,
        pending: docs.filter((d) => d.status === 'pending').length,
      });

    default: {
      // GET /api/kb/documents/{id}
      const docId = pathKey.startsWith('documents/') ? pathKey.replace('documents/', '') : null;
      if (docId) {
        const doc = docs.find((d) => d.id === docId);
        if (!doc) {
          return NextResponse.json({ detail: 'Document not found.' }, { status: 404 });
        }
        return NextResponse.json(doc);
      }
      return NextResponse.json({ detail: 'Not found' }, { status: 404 });
    }
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  if (!checkAuth(request)) {
    return NextResponse.json({ detail: 'Authentication required.' }, { status: 401 });
  }

  const { path: segments } = await params;
  const pathKey = segments.join('/');

  // Try backend proxy first (especially important for file uploads)
  const proxied = await proxyToBackend(request, segments);
  if (proxied) return proxied;

  // D13-P8: In production, don't silently fall back to local for uploads
  if (pathKey === 'upload' && process.env.NODE_ENV === 'production') {
    return NextResponse.json(
      { detail: 'Backend service unavailable. Please try again later.' },
      { status: 503 },
    );
  }
  if (proxied === null && process.env.NODE_ENV !== 'production') {
    console.warn('KB backend unreachable, falling back to local storage (dev only)');
  }

  // Local fallback
  const docs = loadDocuments();

  switch (pathKey) {
    case 'upload': {
      // Parse multipart form data
      const formData = await request.formData();
      const file = formData.get('file') as File | null;

      if (!file) {
        return NextResponse.json({ detail: 'No file provided.' }, { status: 400 });
      }

      // Validate extension
      const filename = sanitizeFilename(file.name || 'unknown.txt');
      const dotIdx = filename.lastIndexOf('.');
      const ext = dotIdx >= 0 ? filename.slice(dotIdx).toLowerCase() : '';
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        return NextResponse.json(
          { detail: `File type "${ext}" not allowed. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}` },
          { status: 400 }
        );
      }

      // Validate size (backend limit)
      if (file.size > MAX_FILE_SIZE) {
        return NextResponse.json(
          { detail: `File too large. Maximum size is ${MAX_FILE_SIZE / (1024 * 1024)} MB.` },
          { status: 400 }
        );
      }

      // D13-P21: In local fallback mode, reject files larger than 10MB
      if (file.size > LOCAL_MAX_FILE_SIZE) {
        return NextResponse.json(
          { detail: `File too large for local storage. Maximum is ${LOCAL_MAX_FILE_SIZE / (1024 * 1024)} MB in local mode.` },
          { status: 400 }
        );
      }

      const newDoc: StoredDocument = {
        id: generateId(),
        filename,
        file_type: ext.replace('.', ''),
        file_size: file.size,
        status: 'completed', // In local mode, mark as completed immediately
        chunk_count: Math.max(1, Math.floor(file.size / 500)),
        error_message: null,
        retry_count: 0,
        created_at: new Date().toISOString(),
      };

      docs.push(newDoc);
      await saveDocuments(docs);

      return NextResponse.json(
        {
          id: newDoc.id,
          filename: newDoc.filename,
          status: newDoc.status,
          message: 'Document uploaded successfully. Processing will begin shortly.',
        },
        { status: 201 }
      );
    }

    case 'retry-failed': {
      let retried = 0;
      for (const doc of docs) {
        if (doc.status === 'failed' && doc.retry_count < 3) {
          doc.status = 'processing';
          doc.retry_count += 1;
          retried += 1;
        }
      }
      await saveDocuments(docs);
      return NextResponse.json({ message: `Retrying ${retried} failed document(s).` });
    }

    default: {
      // POST /api/kb/documents/{id}/retry or /reindex
      const match = pathKey.match(/^documents\/([^/]+)\/(retry|reindex)$/);
      if (match) {
        const docId = match[1];
        const action = match[2];
        const doc = docs.find((d) => d.id === docId);
        if (!doc) {
          return NextResponse.json({ detail: 'Document not found.' }, { status: 404 });
        }

        if (action === 'retry') {
          if (doc.retry_count >= 3) {
            return NextResponse.json(
              { detail: 'Maximum retry limit (3) reached.' },
              { status: 400 }
            );
          }
          doc.status = 'completed';
          doc.retry_count += 1;
          doc.error_message = null;
          doc.chunk_count = Math.max(1, Math.floor((doc.file_size || 1000) / 500));
          await saveDocuments(docs);

          return NextResponse.json({
            id: doc.id,
            status: doc.status,
            retry_count: doc.retry_count,
            message: 'Document retry initiated.',
          });
        }

        if (action === 'reindex') {
          doc.status = 'processing';
          await saveDocuments(docs);

          return NextResponse.json({
            message: `Document re-indexing initiated.`,
          });
        }
      }

      return NextResponse.json({ detail: 'Not found' }, { status: 404 });
    }
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  if (!checkAuth(request)) {
    return NextResponse.json({ detail: 'Authentication required.' }, { status: 401 });
  }

  const { path: segments } = await params;
  const pathKey = segments.join('/');

  // Try backend proxy first
  const proxied = await proxyToBackend(request, segments);
  if (proxied) return proxied;

  // Local fallback — DELETE /api/kb/documents/{id}
  const docId = pathKey.startsWith('documents/') ? pathKey.replace('documents/', '') : null;
  if (!docId) {
    return NextResponse.json({ detail: 'Document ID required.' }, { status: 400 });
  }

  const docs = loadDocuments();
  const idx = docs.findIndex((d) => d.id === docId);
  if (idx === -1) {
    return NextResponse.json({ detail: 'Document not found.' }, { status: 404 });
  }

  docs.splice(idx, 1);
  await saveDocuments(docs);

  return NextResponse.json({ message: 'Document deleted successfully.' });
}
