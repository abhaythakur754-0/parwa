/**
 * PARWA KnowledgeBaseUpload Component
 *
 * File upload UI for knowledge base documents that Jarvis uses
 * for shadow mode learning. Appears as a card in the chat area
 * with drag-and-drop + click-to-upload support.
 *
 * Supports: PDF, TXT, CSV, DOCX, MD files
 */

'use client';

import { useState, useRef, useCallback } from 'react';
import { Upload, FileText, X, CheckCircle2, Loader2, AlertCircle, CloudUpload, BookOpen } from 'lucide-react';

interface KnowledgeBaseUploadProps {
  /** Callback when files are uploaded — sends file data to the API */
  onUpload?: (files: File[]) => Promise<void>;
  /** Whether upload is in progress */
  isUploading?: boolean;
  /** Currently uploaded files for display */
  uploadedFiles?: Array<{ name: string; size: number; status: 'pending' | 'uploading' | 'done' | 'error' }>;
  /** Whether this is for a specific variant/industry context */
  variantName?: string;
  industryName?: string;
  /** Compact mode — show as a small inline card */
  compact?: boolean;
}

const ACCEPTED_TYPES = [
  'application/pdf',
  'text/plain',
  'text/csv',
  'text/markdown',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/msword',
];

const ACCEPTED_EXTENSIONS = '.pdf,.txt,.csv,.md,.docx,.doc';
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_FILES = 5;

export function KnowledgeBaseUpload({
  onUpload,
  isUploading,
  uploadedFiles = [],
  variantName,
  industryName,
  compact = false,
}: KnowledgeBaseUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback((file: File): string | null => {
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    const validExts = ['pdf', 'txt', 'csv', 'md', 'docx', 'doc'];
    if (!validExts.includes(ext)) {
      return `"${ext}" files are not supported. Use PDF, TXT, CSV, MD, or DOCX.`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `"${file.name}" is too large (max 10MB).`;
    }
    return null;
  }, []);

  const handleFiles = useCallback((files: FileList | File[]) => {
    setError(null);
    const fileArray = Array.from(files);

    if (selectedFiles.length + fileArray.length > MAX_FILES) {
      setError(`Maximum ${MAX_FILES} files at a time.`);
      return;
    }

    const valid: File[] = [];
    for (const f of fileArray) {
      const err = validateFile(f);
      if (err) {
        setError(err);
        continue;
      }
      valid.push(f);
    }

    if (valid.length > 0) {
      setSelectedFiles(prev => [...prev, ...valid]);
    }
  }, [selectedFiles, validateFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  }, [handleFiles]);

  const handleRemoveFile = useCallback((index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0) return;
    try {
      await onUpload?.(selectedFiles);
      setSelectedFiles([]);
    } catch {
      setError('Upload failed. Please try again.');
    }
  }, [selectedFiles, onUpload]);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  // ── Compact mode: Small card for inline chat ──
  if (compact) {
    return (
      <div className="rounded-xl border border-orange-500/15 bg-orange-500/[0.04] p-3 max-w-sm w-full">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-7 h-7 rounded-lg bg-orange-500/10 flex items-center justify-center">
            <BookOpen className="w-3.5 h-3.5 text-orange-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-white/80 truncate">
              Upload Knowledge Base
            </p>
            <p className="text-[10px] text-white/40">
              Help Jarvis learn from your data
            </p>
          </div>
        </div>

        {/* File list */}
        {uploadedFiles.length > 0 && (
          <div className="space-y-1 mb-2">
            {uploadedFiles.slice(0, 3).map((f, i) => (
              <div key={i} className="flex items-center gap-1.5 text-[10px]">
                {f.status === 'done' ? (
                  <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                ) : f.status === 'uploading' ? (
                  <Loader2 className="w-3 h-3 text-orange-400 animate-spin shrink-0" />
                ) : (
                  <FileText className="w-3 h-3 text-white/30 shrink-0" />
                )}
                <span className="text-white/50 truncate">{f.name}</span>
              </div>
            ))}
          </div>
        )}

        {/* Upload button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-orange-500/10 border border-orange-500/20 text-orange-300 text-xs font-medium hover:bg-orange-500/15 disabled:opacity-40 transition-all active:scale-[0.98]"
        >
          <CloudUpload className="w-3.5 h-3.5" />
          {isUploading ? 'Uploading...' : 'Choose Files'}
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          multiple
          className="hidden"
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
        />
      </div>
    );
  }

  // ── Full mode: Expanded card with drag-drop ──
  return (
    <div className="rounded-xl border border-orange-500/15 bg-gradient-to-b from-orange-500/[0.04] to-transparent p-4 max-w-sm w-full">
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-3">
        <div className="w-9 h-9 rounded-lg bg-orange-500/10 flex items-center justify-center">
          <BookOpen className="w-4.5 h-4.5 text-orange-400" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-white">
            Knowledge Base
          </h3>
          <p className="text-[11px] text-white/40">
            {variantName
              ? `For ${variantName}${industryName ? ` · ${industryName}` : ''} shadow mode`
              : 'Help Jarvis learn from your data'}
          </p>
        </div>
      </div>

      {/* Description */}
      <p className="text-xs text-white/50 mb-3 leading-relaxed">
        Upload your docs, FAQs, or support transcripts. Jarvis will learn from them and respond like a trained agent for your business.
      </p>

      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-4 text-center transition-all duration-200 ${
          isDragging
            ? 'border-orange-400/60 bg-orange-500/10'
            : 'border-white/10 hover:border-orange-400/30 hover:bg-white/[0.02]'
        }`}
      >
        <CloudUpload className={`w-6 h-6 mx-auto mb-2 transition-colors ${isDragging ? 'text-orange-400' : 'text-white/20'}`} />
        <p className="text-xs text-white/50 mb-0.5">
          {isDragging ? 'Drop files here' : 'Drag & drop or click to upload'}
        </p>
        <p className="text-[10px] text-white/25">
          PDF, TXT, CSV, DOCX, MD · Max 10MB each
        </p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS}
        multiple
        className="hidden"
        onChange={(e) => e.target.files && handleFiles(e.target.files)}
      />

      {/* Selected files */}
      {selectedFiles.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {selectedFiles.map((file, i) => (
            <div key={i} className="flex items-center gap-2 p-2 rounded-lg bg-white/[0.03] border border-white/5">
              <FileText className="w-4 h-4 text-orange-400/60 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-white/70 truncate">{file.name}</p>
                <p className="text-[10px] text-white/30">{formatSize(file.size)}</p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); handleRemoveFile(i); }}
                className="w-5 h-5 rounded flex items-center justify-center hover:bg-white/10 transition-colors"
              >
                <X className="w-3 h-3 text-white/30" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Uploaded files */}
      {uploadedFiles.length > 0 && (
        <div className="mt-3 space-y-1">
          {uploadedFiles.map((f, i) => (
            <div key={i} className="flex items-center gap-2 px-1">
              {f.status === 'done' ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              ) : f.status === 'uploading' ? (
                <Loader2 className="w-3.5 h-3.5 text-orange-400 animate-spin shrink-0" />
              ) : f.status === 'error' ? (
                <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
              ) : (
                <FileText className="w-3.5 h-3.5 text-white/30 shrink-0" />
              )}
              <span className="text-[11px] text-white/50 truncate">{f.name}</span>
              {f.status === 'done' && (
                <span className="text-[10px] text-emerald-400/60 shrink-0">ready</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="text-[11px] text-red-300/70 mt-2 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          {error}
        </p>
      )}

      {/* Upload button */}
      {selectedFiles.length > 0 && (
        <button
          onClick={handleUpload}
          disabled={isUploading || selectedFiles.length === 0}
          className="mt-3 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-orange-600 text-white text-xs font-semibold hover:from-orange-400 hover:to-orange-500 disabled:opacity-40 transition-all shadow-lg shadow-orange-500/15 active:scale-[0.98]"
        >
          {isUploading ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Uploading...
            </>
          ) : (
            <>
              <Upload className="w-3.5 h-3.5" />
              Upload {selectedFiles.length} file{selectedFiles.length !== 1 ? 's' : ''}
            </>
          )}
        </button>
      )}
    </div>
  );
}

export default KnowledgeBaseUpload;
