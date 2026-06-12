'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  File,
  FileType,
  FileSpreadsheet,
  ArrowRight,
  ArrowLeft,
  Loader2,
  CheckCircle,
  XCircle,
  RefreshCw,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { knowledgeApi, onboardingApi, getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import { KnowledgeDocument, DocumentStatus } from '@/types/onboarding';

/**
 * Accepted file types for knowledge base uploads.
 */
const ACCEPTED_TYPES = [
  { mime: 'application/pdf', ext: '.pdf', icon: FileText, label: 'PDF' },
  { mime: 'text/plain', ext: '.txt', icon: File, label: 'TXT' },
  { mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', ext: '.docx', icon: FileType, label: 'DOCX' },
  { mime: 'text/markdown', ext: '.md', icon: FileText, label: 'MD' },
  { mime: 'text/csv', ext: '.csv', icon: FileSpreadsheet, label: 'CSV' },
];

const ACCEPTED_EXTENSIONS = ACCEPTED_TYPES.map((t) => t.ext);
const ACCEPTED_MIMES = ACCEPTED_TYPES.map((t) => t.mime);

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface LocalUpload {
  file: File;
  progress: number;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  serverId?: string;
  errorMessage?: string;
}

interface KnowledgeBaseStepProps {
  onNext: () => void;
}

/**
 * KnowledgeBaseStep Component (Step 4)
 *
 * Provides a drag-and-drop zone for uploading documents to the
 * knowledge base. Users can also click to browse files. Each
 * uploaded file shows its filename, size, upload progress, and
 * processing status. Failed uploads display retry and remove
 * buttons. This step is optional so a "Skip for now" button
 * is available alongside the "Continue" button.
 */
export function KnowledgeBaseStep({ onNext }: KnowledgeBaseStepProps) {
  const [uploads, setUploads] = useState<LocalUpload[]>([]);
  const [existingDocs, setExistingDocs] = useState<KnowledgeDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [isSkipping, setIsSkipping] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    async function loadDocs() {
      try {
        const docs = await knowledgeApi.list();
        setExistingDocs(Array.isArray(docs) ? docs : []);
      } catch {
        setExistingDocs([]);
      } finally {
        setIsLoading(false);
      }
    }
    loadDocs();
  }, []);

  useEffect(() => {
    const processingUploads = uploads.filter((u) => u.status === 'processing' && u.serverId);
    if (processingUploads.length === 0) return;

    const interval = setInterval(async () => {
      for (const upload of processingUploads) {
        try {
          const status = await knowledgeApi.getStatus(upload.serverId!);
          if (status && typeof status === 'object' && 'status' in status) {
            const docStatus = (status as { status: DocumentStatus }).status;
            if (docStatus === 'completed' || docStatus === 'failed') {
              setUploads((prev) =>
                prev.map((u) =>
                  u.serverId === upload.serverId
                    ? { ...u, status: docStatus, errorMessage: docStatus === 'failed' ? 'Processing failed. Please try again.' : undefined }
                    : u
                )
              );
            }
          }
        } catch {
          // Silently retry on next interval
        }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [uploads]);

  const isAcceptedFile = useCallback((file: File): boolean => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    return ACCEPTED_EXTENSIONS.includes(ext) || ACCEPTED_MIMES.includes(file.type);
  }, []);

  const uploadFile = useCallback(async (file: File) => {
    const localUpload: LocalUpload = { file, progress: 0, status: 'uploading' };
    setUploads((prev) => [...prev, localUpload]);

    try {
      const result = await knowledgeApi.upload(file, (progress) => {
        setUploads((prev) => prev.map((u) => (u.file === file ? { ...u, progress } : u)));
      });

      const serverId = (result as { id?: string })?.id || '';
      setUploads((prev) =>
        prev.map((u) => (u.file === file ? { ...u, progress: 100, status: 'processing', serverId } : u))
      );
    } catch (error) {
      setUploads((prev) =>
        prev.map((u) => (u.file === file ? { ...u, status: 'failed', errorMessage: getErrorMessage(error) } : u))
      );
    }
  }, []);

  const handleFiles = useCallback(
    (files: FileList | File[]) => {
      const fileArray = Array.from(files);
      const accepted = fileArray.filter(isAcceptedFile);
      const rejected = fileArray.filter((f) => !isAcceptedFile(f));

      if (rejected.length > 0) {
        toast.error(`${rejected.length} file(s) skipped: unsupported format. Accepted: ${ACCEPTED_EXTENSIONS.join(', ')}`);
      }

      accepted.forEach((file) => uploadFile(file));
    },
    [isAcceptedFile, uploadFile]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files.length > 0) handleFiles(e.dataTransfer.files);
  };

  const handleRetry = (upload: LocalUpload) => {
    setUploads((prev) => prev.filter((u) => u.file !== upload.file));
    uploadFile(upload.file);
  };

  const handleRemove = async (upload: LocalUpload) => {
    if (upload.serverId) {
      try { await knowledgeApi.delete(upload.serverId); } catch { /* ignore */ }
    }
    setUploads((prev) => prev.filter((u) => u.file !== upload.file));
  };

  const handleContinue = async () => {
    try {
      await onboardingApi.completeStep(4);
      onNext();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const handleSkip = async () => {
    setIsSkipping(true);
    try {
      await onboardingApi.completeStep(4);
      onNext();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setIsSkipping(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-orange-400" />
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto">
      {/* Header */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-orange-500/10 border border-orange-500/20 mb-6">
          <UploadCloud className="w-8 h-8 text-orange-400" />
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
          Knowledge Base
        </h2>
        <p className="text-orange-200/50 text-sm max-w-md mx-auto">
          Upload your documentation, FAQs, and product information so your AI assistant can provide accurate, context-aware responses to customer inquiries.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          'relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-300',
          isDragging
            ? 'border-orange-500 bg-orange-500/5'
            : 'border-white/10 hover:border-orange-500/40 bg-white/[0.02]'
        )}
      >
        <UploadCloud className={cn('w-10 h-10 mx-auto mb-4 transition-colors', isDragging ? 'text-orange-400' : 'text-white/20')} />
        <p className="text-sm font-medium text-white mb-1">Drag and drop files here, or click to browse</p>
        <p className="text-xs text-orange-200/30">Supported formats: {ACCEPTED_TYPES.map((t) => t.label).join(', ')}</p>

        <div className="flex items-center justify-center gap-3 mt-4">
          {ACCEPTED_TYPES.map((type) => {
            const Icon = type.icon;
            return (
              <div key={type.ext} className="w-8 h-8 rounded bg-white/5 flex items-center justify-center">
                <Icon className="w-4 h-4 text-orange-300/40" />
              </div>
            );
          })}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS.join(',')}
          className="hidden"
          onChange={(e) => {
            if (e.target.files) handleFiles(e.target.files);
            e.target.value = '';
          }}
        />
      </div>

      {/* Existing documents */}
      {existingDocs.length > 0 && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold text-orange-200/40 uppercase tracking-wider mb-3">Previously Uploaded</h3>
          <div className="space-y-2">
            {existingDocs.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between p-3 card-parwa rounded-lg">
                <div className="flex items-center gap-3 min-w-0">
                  <FileText className="w-4 h-4 text-orange-300/50 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm text-white truncate">{doc.filename}</p>
                    <p className="text-xs text-orange-200/30">{formatFileSize(doc.file_size)}</p>
                  </div>
                </div>
                <span className={cn('text-xs px-2 py-0.5 rounded-full', doc.status === 'completed' && 'bg-green-500/10 text-green-400', doc.status === 'processing' && 'bg-yellow-500/10 text-yellow-400', doc.status === 'pending' && 'bg-white/5 text-white/40', doc.status === 'failed' && 'bg-red-500/10 text-red-400')}>
                  {doc.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Current upload list */}
      {uploads.length > 0 && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold text-orange-200/40 uppercase tracking-wider mb-3">Uploads</h3>
          <div className="space-y-3 max-h-64 overflow-y-auto scrollbar-premium">
            {uploads.map((upload, index) => (
              <div key={`${upload.file.name}-${index}`} className="p-3 card-parwa rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="w-4 h-4 text-orange-300/50 flex-shrink-0" />
                    <span className="text-sm text-white truncate">{upload.file.name}</span>
                    <span className="text-xs text-orange-200/30 flex-shrink-0">{formatFileSize(upload.file.size)}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    {upload.status === 'completed' && <CheckCircle className="w-4 h-4 text-green-400" />}
                    {upload.status === 'failed' && <XCircle className="w-4 h-4 text-red-400" />}
                    {(upload.status === 'uploading' || upload.status === 'processing') && <Loader2 className="w-4 h-4 text-orange-400 animate-spin" />}
                    {upload.status === 'failed' && (
                      <button type="button" onClick={(e) => { e.stopPropagation(); handleRetry(upload); }} className="ml-1 w-6 h-6 rounded bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors" aria-label="Retry upload">
                        <RefreshCw className="w-3 h-3 text-orange-300" />
                      </button>
                    )}
                    {upload.status === 'failed' && (
                      <button type="button" onClick={(e) => { e.stopPropagation(); handleRemove(upload); }} className="w-6 h-6 rounded bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors" aria-label="Remove upload">
                        <X className="w-3 h-3 text-white/40" />
                      </button>
                    )}
                  </div>
                </div>
                {upload.status === 'uploading' && (
                  <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <div className="h-full rounded-full bg-orange-500 transition-all duration-300" style={{ width: `${upload.progress}%` }} />
                  </div>
                )}
                <p className={cn('text-xs mt-1', upload.status === 'completed' && 'text-green-400/70', upload.status === 'failed' && 'text-red-400/70', upload.status === 'processing' && 'text-yellow-400/70', upload.status === 'uploading' && 'text-orange-200/30')}>
                  {upload.status === 'uploading' && `Uploading... ${upload.progress}%`}
                  {upload.status === 'processing' && 'Processing document...'}
                  {upload.status === 'completed' && 'Upload complete'}
                  {upload.status === 'failed' && upload.errorMessage}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="mt-10 flex items-center justify-center gap-3">
        <button type="button" onClick={handleSkip} disabled={isSkipping} className="btn-ghost-parwa text-sm">
          {isSkipping ? <><Loader2 className="w-4 h-4 mr-1 animate-spin" />Skipping...</> : 'Skip for now'}
        </button>
        <button type="button" onClick={handleContinue} className="btn-primary-parwa py-2.5 px-5">
          Continue
          <ArrowRight className="w-4 h-4 ml-2" />
        </button>
      </div>
    </div>
  );
}

export default KnowledgeBaseStep;
