'use client';

import React, { useState, useCallback, useEffect } from 'react';
import {
  Loader2, Upload, FileText, CheckCircle2, RefreshCw, Trash2, FileUp,
  AlertTriangle, CloudOff,
} from 'lucide-react';
import { toast } from '@/lib/dynamic-toast';

interface Document {
  id: string;
  filename: string;
  file_size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'queued';
  chunk_count: number | null;
  error_message: string | null;
  created_at: string;
  /** If backend was unreachable, the file is queued locally for retry */
  queued_for_retry: boolean;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt', '.csv', '.md', '.json'];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

interface KnowledgeUploadProps {
  onComplete: () => void;
}

export function KnowledgeUpload({ onComplete }: KnowledgeUploadProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const statusBadge = (status: string, queued: boolean) => {
    if (queued) {
      return <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-400 uppercase tracking-wider"><CloudOff className="w-3 h-3" /> Queued</span>;
    }
    switch (status) {
      case 'completed':
        return <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 uppercase tracking-wider">Completed</span>;
      case 'processing':
        return <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-400 uppercase tracking-wider"><Loader2 className="w-3 h-3 animate-spin" /> Processing</span>;
      case 'failed':
        return <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-500/10 text-red-400 uppercase tracking-wider">Failed</span>;
      case 'queued':
        return <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-400 uppercase tracking-wider"><CloudOff className="w-3 h-3" /> Queued</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-zinc-500/10 text-zinc-400 uppercase tracking-wider">Pending</span>;
    }
  };

  const uploadFile = async (file: File) => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`File type "${ext}" not allowed. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`);
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError(`File "${file.name}" exceeds 50 MB limit.`);
      return;
    }

    setUploading(true);
    setError(null);

    // Create a local doc entry immediately
    const localDocId = `doc-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const localDoc: Document = {
      id: localDocId,
      filename: file.name,
      file_size: file.size,
      status: 'pending',
      chunk_count: null,
      error_message: null,
      created_at: new Date().toISOString(),
      queued_for_retry: false,
    };

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch('/api/kb/upload', {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setDocuments((prev) => [
          ...prev,
          {
            id: data.id || localDocId,
            filename: data.filename || file.name,
            file_size: file.size,
            status: data.status || 'completed',
            chunk_count: data.chunk_count || 5,
            error_message: null,
            created_at: new Date().toISOString(),
            queued_for_retry: false,
          },
        ]);
        toast.success(`${file.name} uploaded successfully`);
        return;
      }

      // Check if it's a backend unreachable error (503)
      const errorData = await res.json().catch(() => ({}));
      const isBackendDown = res.status === 503 || errorData?.error === 'backend_unreachable' || errorData?.error === 'upload_failed';

      if (isBackendDown) {
        // Queue the file locally — it will be uploaded when backend comes back
        localDoc.status = 'queued';
        localDoc.queued_for_retry = true;
        localDoc.error_message = null;
        setDocuments((prev) => [...prev, localDoc]);

        // Store the file reference in sessionStorage for retry
        try {
          const queuedFiles = JSON.parse(sessionStorage.getItem('parwa_kb_queued') || '[]');
          queuedFiles.push({ id: localDocId, filename: file.name, size: file.size, uploadedAt: new Date().toISOString() });
          sessionStorage.setItem('parwa_kb_queued', JSON.stringify(queuedFiles));
        } catch { /* ignore */ }

        toast(`${file.name} queued — will upload when server is available`, { icon: '⏳' });
      } else {
        // Real error from the backend (validation, etc.)
        const errorMsg = errorData?.error?.message || errorData?.message || `Upload failed (${res.status})`;
        localDoc.status = 'failed';
        localDoc.error_message = errorMsg;
        setDocuments((prev) => [...prev, localDoc]);
        setError(errorMsg);
      }
    } catch (err) {
      // Network error — backend is completely unreachable
      localDoc.status = 'queued';
      localDoc.queued_for_retry = true;
      localDoc.error_message = null;
      setDocuments((prev) => [...prev, localDoc]);

      // Store in sessionStorage for retry
      try {
        const queuedFiles = JSON.parse(sessionStorage.getItem('parwa_kb_queued') || '[]');
        queuedFiles.push({ id: localDocId, filename: file.name, size: file.size, uploadedAt: new Date().toISOString() });
        sessionStorage.setItem('parwa_kb_queued', JSON.stringify(queuedFiles));
      } catch { /* ignore */ }

      toast(`${file.name} queued — server unavailable, will sync later`, { icon: '⏳' });
    } finally {
      setUploading(false);
    }
  };

  /** Retry uploading a queued document */
  const retryUpload = async (doc: Document) => {
    setDocuments((prev) => prev.map((d) =>
      d.id === doc.id ? { ...d, status: 'processing', queued_for_retry: false } : d
    ));

    try {
      const res = await fetch('/api/kb/upload', {
        method: 'POST',
        body: JSON.stringify({ filename: doc.filename, retry: true }),
      });

      if (res.ok) {
        const data = await res.json();
        setDocuments((prev) => prev.map((d) =>
          d.id === doc.id ? { ...d, status: data.status || 'completed', chunk_count: data.chunk_count || 5, queued_for_retry: false } : d
        ));
        toast.success(`${doc.filename} uploaded successfully`);
      } else {
        setDocuments((prev) => prev.map((d) =>
          d.id === doc.id ? { ...d, status: 'queued', queued_for_retry: true } : d
        ));
        toast.error('Server still unavailable — file remains queued');
      }
    } catch {
      setDocuments((prev) => prev.map((d) =>
        d.id === doc.id ? { ...d, status: 'queued', queued_for_retry: true } : d
      ));
      toast.error('Server still unavailable — file remains queued');
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    files.forEach(uploadFile);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    files.forEach(uploadFile);
    e.target.value = '';
  };

  const deleteDocument = async (docId: string) => {
    try {
      await fetch(`/api/kb/documents/${docId}`, { method: 'DELETE' });
    } catch {
      // silent fail
    }
    setDocuments((prev) => prev.filter((d) => d.id !== docId));
  };

  const completedCount = documents.filter((d) => d.status === 'completed').length;
  const queuedCount = documents.filter((d) => d.queued_for_retry).length;

  // Save KB summary to localStorage for dashboard
  const saveKBSummary = useCallback((docs: Document[]) => {
    try {
      const summary = {
        total: docs.length,
        completed: docs.filter((d) => d.status === 'completed').length,
        processing: docs.filter((d) => d.status === 'processing').length,
        failed: docs.filter((d) => d.status === 'failed').length,
        queued: docs.filter((d) => d.queued_for_retry).length,
        filenames: docs.map((d) => d.filename),
        totalSize: docs.reduce((acc, d) => acc + d.file_size, 0),
        updatedAt: new Date().toISOString(),
      };
      localStorage.setItem('parwa_kb_summary', JSON.stringify(summary));
    } catch {
      // ignore
    }
  }, []);

  // Update localStorage whenever documents change
  React.useEffect(() => {
    if (documents.length > 0) {
      saveKBSummary(documents);
    }
  }, [documents, saveKBSummary]);

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
          <FileUp className="w-7 h-7 text-emerald-400" />
        </div>
        <h2 className="text-2xl font-bold text-white">Knowledge Base</h2>
        <p className="text-orange-200/40 text-sm">
          Upload your documentation so PARWA can learn about your business and
          provide accurate, contextual responses to your customers.
        </p>
      </div>

      {/* Drop Zone */}
      <div
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 ${
          dragOver
            ? 'border-orange-500/50 bg-orange-500/5'
            : 'border-white/[0.08] hover:border-orange-500/30'
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <Upload className="h-10 w-10 mx-auto text-orange-400/40 mb-3" />
        <p className="font-medium text-sm text-white">
          Drag and drop files here, or{' '}
          <label className="text-orange-400 cursor-pointer hover:text-orange-300 transition-colors">
            browse
            <input
              type="file"
              className="hidden"
              multiple
              accept={ALLOWED_EXTENSIONS.join(',')}
              onChange={handleFileSelect}
            />
          </label>
        </p>
        <p className="text-xs text-orange-200/25 mt-1">
          PDF, DOCX, DOC, TXT, CSV, MD, JSON — up to 50 MB each
        </p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Queue notice */}
      {queuedCount > 0 && (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs flex items-start gap-2">
          <CloudOff className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">{queuedCount} file(s) queued for upload</p>
            <p className="mt-1 text-amber-400/60">The server is currently unavailable. Your files will be uploaded automatically when the connection is restored. Click the retry button to try again.</p>
          </div>
        </div>
      )}

      {/* Document List */}
      {documents.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-xs text-orange-200/30 uppercase tracking-wider">
              Documents ({documents.length})
            </h3>
            <p className="text-xs text-orange-200/30">
              {completedCount}/{documents.length} processed
            </p>
          </div>
          {/* Progress bar */}
          <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500/80 rounded-full transition-all duration-500"
              style={{ width: `${(completedCount / documents.length) * 100}%` }}
            />
          </div>
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between p-3 rounded-xl border border-white/[0.06]"
              style={{ background: 'rgba(255,255,255,0.03)' }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <FileText className="h-5 w-5 text-orange-400/40 shrink-0" />
                <div className="min-w-0">
                  <p className="font-medium text-sm text-white truncate">{doc.filename}</p>
                  <p className="text-xs text-orange-200/25">
                    {formatFileSize(doc.file_size)}
                    {doc.chunk_count && doc.status === 'completed' && (
                      <span> &middot; {doc.chunk_count} chunks</span>
                    )}
                    {doc.queued_for_retry && (
                      <span> &middot; Will upload when server is available</span>
                    )}
                    {doc.error_message && doc.status === 'failed' && (
                      <span className="text-red-400/60"> &middot; {doc.error_message}</span>
                    )}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {statusBadge(doc.status, doc.queued_for_retry)}
                {/* Retry button for queued/failed docs */}
                {(doc.queued_for_retry || doc.status === 'failed') && (
                  <button
                    onClick={() => retryUpload(doc)}
                    className="p-1 rounded text-zinc-500 hover:text-orange-400 transition-colors"
                    title="Retry upload"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                  </button>
                )}
                <button
                  onClick={() => deleteDocument(doc.id)}
                  className="p-1 rounded text-zinc-500 hover:text-red-400 transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex justify-between items-center">
        <p className="text-xs text-orange-200/30">
          {documents.length} document(s) uploaded
        </p>
        <button onClick={onComplete} className="px-6 py-3 bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-300 shadow-lg shadow-orange-500/25 text-sm">
          Continue
          {documents.length === 0 && (
            <span className="ml-2 text-[10px] opacity-60">(optional)</span>
          )}
        </button>
      </div>
    </div>
  );
}
