'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { FileUp } from 'lucide-react';
import { FileDropZone } from './FileDropZone';
import { FileList } from './FileList';
import { UploadProgress } from './UploadProgress';
import type { KnowledgeDocument } from '@/types/onboarding';

const ALLOWED_EXTENSIONS = '.pdf,.docx,.doc,.txt,.csv,.md,.json';
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

interface KnowledgeUploadProps {
  onComplete: () => void;
}

export function KnowledgeUpload({ onComplete }: KnowledgeUploadProps) {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [uploading, setUploading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  // D13-P14: Record<string, boolean> to track multiple concurrent retries/deletes
  const [retryingId, setRetryingId] = useState<Record<string, boolean>>({});
  const [deletingId, setDeletingId] = useState<Record<string, boolean>>({});
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // D13-P3: Sanitize error messages to avoid leaking internal details
  function sanitizeErrorMessage(raw: string): string {
    const leaked = /(?:https?:\/\/|stack|trace|error|exception|at\s+|\/home\/|\/usr\/|\/var\/)/i;
    if (leaked.test(raw)) return 'Upload failed. Please try again.';
    if (raw.length > 120) return 'Upload failed. Please try again.';
    return raw;
  }

  // D13-P6: Parallel upload with concurrency limit of 3
  const uploadFiles = useCallback(async (files: File[]) => {
    setUploading(true);
    setErrors((prev) => {
      const next = { ...prev };
      for (const f of files) delete next[f.name];
      return next;
    });

    // Add all files in 'pending' status immediately
    const pendingDocs: KnowledgeDocument[] = files.map((file) => ({
      id: `pending_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      filename: file.name,
      file_size: file.size,
      mime_type: file.type || 'application/octet-stream',
      status: 'pending' as const,
      chunk_count: null,
      error_message: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }));
    setDocuments((prev) => [...prev, ...pendingDocs]);

    async function uploadOne(file: File, pendingId: string): Promise<void> {
      try {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch('/api/kb/upload', {
          method: 'POST',
          body: formData,
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          const rawMsg = data?.detail || data?.error?.message || 'Upload failed';
          throw new Error(rawMsg);
        }

        const data = await res.json();
        setDocuments((prev) =>
          prev.map((d) =>
            d.id === pendingId
              ? {
                  ...d,
                  id: data.id,
                  status: data.status ?? 'completed',
                  updated_at: new Date().toISOString(),
                }
              : d,
          ),
        );
      } catch (err) {
        const rawMsg = err instanceof Error ? err.message : 'Upload failed';
        setErrors((prev) => ({ ...prev, [file.name]: sanitizeErrorMessage(rawMsg) }));
        setDocuments((prev) =>
          prev.map((d) =>
            d.id === pendingId
              ? { ...d, status: 'failed' as const, updated_at: new Date().toISOString() }
              : d,
          ),
        );
      }
    }

    // Process in batches of 3
    const CONCURRENCY = 3;
    for (let i = 0; i < files.length; i += CONCURRENCY) {
      const batch = files.slice(i, i + CONCURRENCY);
      await Promise.allSettled(batch.map((file, idx) => uploadOne(file, pendingDocs[i + idx].id)));
    }

    setUploading(false);
  }, []);

  const retryDocument = useCallback(async (docId: string) => {
    setRetryingId((prev) => ({ ...prev, [docId]: true }));
    try {
      setDocuments((prev) =>
        prev.map((d) =>
          d.id === docId ? { ...d, status: 'processing' as const } : d,
        ),
      );
      const res = await fetch(`/api/kb/documents/${docId}/retry`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Retry failed');
    } catch {
      setDocuments((prev) =>
        prev.map((d) =>
          d.id === docId ? { ...d, status: 'failed' as const } : d,
        ),
      );
    } finally {
      setRetryingId((prev) => {
        const next = { ...prev };
        delete next[docId];
        return next;
      });
    }
  }, []);

  // D13-P5: Guard against deleting documents currently being processed
  const deleteDocument = useCallback(async (docId: string) => {
    const doc = documents.find((d) => d.id === docId);
    if (doc?.status === 'processing') return;

    setDeletingId((prev) => ({ ...prev, [docId]: true }));
    try {
      await fetch(`/api/kb/documents/${docId}`, { method: 'DELETE' });
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch {
      // silent fail
    } finally {
      setDeletingId((prev) => {
        const next = { ...prev };
        delete next[docId];
        return next;
      });
    }
  }, [documents]);

  // D13-P4: Poll for document status updates
  useEffect(() => {
    const hasActiveDocs = documents.some(
      (d) => d.status === 'pending' || d.status === 'processing',
    );

    if (!hasActiveDocs) {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      return;
    }

    if (pollingRef.current) return; // already polling

    pollingRef.current = setInterval(async () => {
      try {
        const res = await fetch('/api/kb/documents');
        if (!res.ok) return;
        const freshDocs = await res.json();
        setDocuments((prev) =>
          prev.map((d) => {
            const updated = freshDocs.find((f: KnowledgeDocument) => f.id === d.id);
            if (updated && updated.status !== d.status) {
              return { ...d, ...updated };
            }
            return d;
          }),
        );
      } catch {
        // ignore polling errors
      }
    }, 5000);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [documents]);

  // D13-P16: Fetch existing documents on mount to restore state after navigation
  useEffect(() => {
    async function fetchDocs() {
      try {
        const res = await fetch('/api/kb/documents');
        if (res.ok) {
          const docs = await res.json();
          setDocuments(docs);
        }
      } catch {
        // ignore — documents will remain empty
      }
    }
    fetchDocs();
  }, []);

  // D13-P3: Aggregate errors for display
  const errorEntries = Object.values(errors);
  const displayError = errorEntries.length > 0 ? errorEntries[errorEntries.length - 1] : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-2">
        <FileUp className="h-12 w-12 mx-auto text-emerald-600" />
        <h2 className="text-2xl font-bold">Knowledge Base</h2>
        <p className="text-muted-foreground">
          Upload your documentation so PARWA can learn about your business and
          provide accurate, contextual responses to your customers.
        </p>
      </div>

      {/* Drop Zone */}
      <FileDropZone
        onFilesSelected={uploadFiles}
        acceptedTypes={ALLOWED_EXTENSIONS}
        maxSizeBytes={MAX_FILE_SIZE}
        isUploading={uploading}
      />

      {displayError && (
        <Alert variant="destructive">
          <AlertDescription>{displayError}</AlertDescription>
        </Alert>
      )}

      {/* Progress */}
      <UploadProgress documents={documents} isUploading={uploading} />

      {/* Document List */}
      <FileList
        documents={documents}
        onRetry={retryDocument}
        onDelete={deleteDocument}
        isRetrying={retryingId}
        isDeleting={deletingId}
      />

      {/* Footer */}
      <div className="flex justify-between">
        <p className="text-sm text-muted-foreground">
          {documents.length} document(s) uploaded
        </p>
        <Button onClick={onComplete} size="lg">
          Continue
          {documents.length === 0 && (
            <span className="ml-2 text-xs text-muted-foreground">(optional)</span>
          )}
        </Button>
      </div>
    </div>
  );
}
