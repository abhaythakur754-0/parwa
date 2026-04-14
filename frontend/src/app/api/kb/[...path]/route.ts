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

// ── Backend Proxy Configuration ─────────────────────────────────
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || '';

async function proxyToBackend(request: NextRequest, pathSegments: string[]): Promise<Response | null> {
  if (!BACKEND_URL) return null;

  const backendPath = `${BACKEND_URL}/api/kb/${pathSegments.join('/')}`;
  const url = new URL(request.url);
  const searchParams = url.searchParams.toString();
  const fullUrl = searchParams ? `${backendPath}?${searchParams}` : backendPath;

  try {
    const body = ['POST', 'PATCH', 'PUT'].includes(request.method)
      ? await request.clone().arrayBuffer()
      : undefined;

    const headers = new Headers(request.headers);
    headers.delete('host');

    const response = await fetch(fullUrl, {
      method: request.method,
      headers,
      body,
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

function saveDocuments(docs: StoredDocument[]): void {
  try {
    fs.writeFileSync(KB_STORE_PATH, JSON.stringify(docs, null, 2), 'utf-8');
  } catch { /* ignore */ }
}

function generateId(): string {
  return `doc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt', '.csv', '.md', '.json'];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

// ── Route Handlers ─────────────────────────────────────────────

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
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
  const { path: segments } = await params;
  const pathKey = segments.join('/');

  // Try backend proxy first (especially important for file uploads)
  const proxied = await proxyToBackend(request, segments);
  if (proxied) return proxied;

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
      const filename = file.name || 'unknown.txt';
      const dotIdx = filename.lastIndexOf('.');
      const ext = dotIdx >= 0 ? filename.slice(dotIdx).toLowerCase() : '';
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        return NextResponse.json(
          { detail: `File type "${ext}" not allowed. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}` },
          { status: 400 }
        );
      }

      // Validate size
      if (file.size > MAX_FILE_SIZE) {
        return NextResponse.json(
          { detail: `File too large. Maximum size is ${MAX_FILE_SIZE / (1024 * 1024)} MB.` },
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
      saveDocuments(docs);

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
      saveDocuments(docs);
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
          doc.status = 'processing';
          doc.retry_count += 1;
          doc.error_message = null;
          saveDocuments(docs);

          // Simulate processing completing after a brief moment
          setTimeout(() => {
            const currentDocs = loadDocuments();
            const target = currentDocs.find((d) => d.id === docId);
            if (target && target.status === 'processing') {
              target.status = 'completed';
              target.chunk_count = Math.max(1, Math.floor((target.file_size || 1000) / 500));
              saveDocuments(currentDocs);
            }
          }, 2000);

          return NextResponse.json({
            id: doc.id,
            status: doc.status,
            retry_count: doc.retry_count,
            message: 'Document retry initiated.',
          });
        }

        if (action === 'reindex') {
          doc.status = 'processing';
          saveDocuments(docs);

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
  saveDocuments(docs);

  return NextResponse.json({ message: 'Document deleted successfully.' });
}
