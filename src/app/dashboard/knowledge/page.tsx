'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { knowledgeApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Upload,
  FileText,
  FileSpreadsheet,
  FileType2,
  Search,
  Trash2,
  RefreshCw,
  Loader2,
  Database,
  CheckCircle2,
  Clock,
  AlertCircle,
  HardDrive,
  FileUp,
  X,
  CloudUpload,
} from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────────────

type DocStatus = 'processing' | 'indexing' | 'ready' | 'failed';

interface KnowledgeDocument {
  id: string;
  name: string;
  type: string;
  size: number;
  status: DocStatus;
  uploadedAt: string;
  chunks?: number;
}

// ── Mock Data ────────────────────────────────────────────────────────────

const MOCK_DOCUMENTS: KnowledgeDocument[] = [
  {
    id: 'doc-1',
    name: 'Product FAQ.pdf',
    type: 'pdf',
    size: 2516582, // 2.4MB
    status: 'ready',
    uploadedAt: '2025-12-28T10:30:00Z',
    chunks: 47,
  },
  {
    id: 'doc-2',
    name: 'Shipping Policy.docx',
    type: 'docx',
    size: 159744, // 156KB
    status: 'ready',
    uploadedAt: '2025-12-27T14:15:00Z',
    chunks: 12,
  },
  {
    id: 'doc-3',
    name: 'Return Policy.pdf',
    type: 'pdf',
    size: 911360, // 890KB
    status: 'ready',
    uploadedAt: '2025-12-26T09:45:00Z',
    chunks: 23,
  },
  {
    id: 'doc-4',
    name: 'Technical Specs.csv',
    type: 'csv',
    size: 1258291, // 1.2MB
    status: 'processing',
    uploadedAt: '2025-12-30T08:00:00Z',
  },
  {
    id: 'doc-5',
    name: 'Brand Guidelines.pdf',
    type: 'pdf',
    size: 3250585, // 3.1MB
    status: 'indexing',
    uploadedAt: '2025-12-30T07:30:00Z',
  },
];

// ── Helpers ──────────────────────────────────────────────────────────────

const ACCEPTED_TYPES = ['.pdf', '.txt', '.docx', '.csv', '.md'];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getFileExtension(name: string): string {
  return '.' + name.split('.').pop()?.toLowerCase() || '';
}

function getFileIcon(type: string) {
  switch (type) {
    case 'csv':
      return <FileSpreadsheet className="w-4 h-4" />;
    case 'docx':
      return <FileType2 className="w-4 h-4" />;
    default:
      return <FileText className="w-4 h-4" />;
  }
}

function getTypeColor(type: string): string {
  switch (type) {
    case 'pdf':
      return 'bg-red-500/15 text-red-400 border-red-500/20';
    case 'docx':
      return 'bg-blue-500/15 text-blue-400 border-blue-500/20';
    case 'csv':
      return 'bg-green-500/15 text-green-400 border-green-500/20';
    case 'txt':
      return 'bg-zinc-500/15 text-zinc-400 border-zinc-500/20';
    case 'md':
      return 'bg-purple-500/15 text-purple-400 border-purple-500/20';
    default:
      return 'bg-zinc-500/15 text-zinc-400 border-zinc-500/20';
  }
}

// ── Status Badge ─────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: DocStatus }) {
  switch (status) {
    case 'processing':
      return (
        <Badge className="bg-yellow-500/15 text-yellow-400 border-yellow-500/20 gap-1">
          <Loader2 className="w-3 h-3 animate-spin" />
          Processing
        </Badge>
      );
    case 'indexing':
      return (
        <Badge className="bg-blue-500/15 text-blue-400 border-blue-500/20 gap-1">
          <RefreshCw className="w-3 h-3 animate-spin" />
          Indexing
        </Badge>
      );
    case 'ready':
      return (
        <Badge className="bg-green-500/15 text-green-400 border-green-500/20 gap-1">
          <CheckCircle2 className="w-3 h-3" />
          Ready
        </Badge>
      );
    case 'failed':
      return (
        <Badge className="bg-red-500/15 text-red-400 border-red-500/20 gap-1">
          <AlertCircle className="w-3 h-3" />
          Failed
        </Badge>
      );
  }
}

// ── Stats Card ───────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  accent: string;
}) {
  return (
    <div className="bg-[#1A1A1A] rounded-xl border border-white/[0.06] p-4 flex items-center gap-4">
      <div
        className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${accent}`}
      >
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-xs text-zinc-500 truncate">{label}</p>
        <p className="text-lg font-semibold text-white">{value}</p>
      </div>
    </div>
  );
}

// ── Loading Skeleton ─────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="pb-6 border-b border-white/[0.06]">
        <Skeleton className="h-7 w-48 bg-zinc-800" />
        <Skeleton className="h-4 w-72 mt-2 bg-zinc-800" />
      </div>

      {/* Stats cards skeleton */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="bg-[#1A1A1A] rounded-xl border border-white/[0.06] p-4 flex items-center gap-4"
          >
            <Skeleton className="w-10 h-10 rounded-lg bg-zinc-800" />
            <div className="space-y-2">
              <Skeleton className="h-3 w-16 bg-zinc-800" />
              <Skeleton className="h-5 w-10 bg-zinc-800" />
            </div>
          </div>
        ))}
      </div>

      {/* Upload zone skeleton */}
      <div className="bg-[#1A1A1A] rounded-xl border border-white/[0.06] p-8">
        <Skeleton className="h-24 w-full bg-zinc-800 rounded-lg" />
      </div>

      {/* Table skeleton */}
      <div className="bg-[#1A1A1A] rounded-xl border border-white/[0.06] p-4 space-y-3">
        <Skeleton className="h-4 w-32 bg-zinc-800" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 py-2">
            <Skeleton className="h-4 w-4 bg-zinc-800" />
            <Skeleton className="h-4 flex-1 bg-zinc-800" />
            <Skeleton className="h-5 w-16 bg-zinc-800" />
            <Skeleton className="h-5 w-14 bg-zinc-800" />
            <Skeleton className="h-4 w-24 bg-zinc-800" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Empty State ──────────────────────────────────────────────────────────

function EmptyState({ onUploadClick }: { onUploadClick: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 bg-[#1A1A1A] rounded-xl border border-white/[0.06]">
      <div className="w-20 h-20 rounded-2xl bg-orange-500/10 flex items-center justify-center mb-5">
        <CloudUpload className="w-10 h-10 text-orange-400" />
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">
        Upload your first document
      </h3>
      <p className="text-sm text-zinc-500 mb-6 text-center max-w-sm">
        Add PDFs, documents, or data files to build your knowledge base. Your AI
        assistant will use these to provide accurate responses.
      </p>
      <Button
        onClick={onUploadClick}
        className="bg-orange-500 hover:bg-orange-600 text-white gap-2"
      >
        <Upload className="w-4 h-4" />
        Upload Document
      </Button>
    </div>
  );
}

// ── Knowledge Page ───────────────────────────────────────────────────────

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadFileName, setUploadFileName] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeDocument | null>(
    null
  );
  const [isDeleting, setIsDeleting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Load documents ────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function loadDocuments() {
      try {
        const data = await knowledgeApi.list();
        if (!cancelled && Array.isArray(data) && data.length > 0) {
          // Map API data to our format
          setDocuments(
            data.map(
              (doc: Record<string, unknown>) =>
                ({
                  id: doc.id as string,
                  name: (doc.filename as string) || (doc.name as string) || 'Unknown',
                  type: getFileExtension(
                    (doc.filename as string) || (doc.name as string) || ''
                  ).replace('.', ''),
                  size: (doc.file_size as number) || 0,
                  status: mapApiStatus(doc.status as string),
                  uploadedAt: (doc.created_at as string) || new Date().toISOString(),
                  chunks: (doc.chunk_count as number) || undefined,
                }) as KnowledgeDocument
            )
          );
        }
      } catch {
        // API not available — use mock data
        if (!cancelled) {
          setDocuments(MOCK_DOCUMENTS);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    // Simulate a brief loading state for the skeleton
    const timer = setTimeout(loadDocuments, 600);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  function mapApiStatus(status: string): DocStatus {
    switch (status) {
      case 'completed':
      case 'ready':
        return 'ready';
      case 'processing':
        return 'processing';
      case 'indexing':
        return 'indexing';
      case 'failed':
        return 'failed';
      default:
        return 'processing';
    }
  }

  // ── File upload ───────────────────────────────────────────────────────
  const uploadFile = useCallback(
    async (file: File) => {
      const ext = getFileExtension(file.name);
      if (!ACCEPTED_TYPES.includes(ext)) {
        return;
      }
      if (file.size > MAX_FILE_SIZE) {
        return;
      }

      setIsUploading(true);
      setUploadProgress(0);
      setUploadFileName(file.name);

      // Optimistically add to the list
      const tempId = `temp-${Date.now()}`;
      const newDoc: KnowledgeDocument = {
        id: tempId,
        name: file.name,
        type: ext.replace('.', ''),
        size: file.size,
        status: 'processing',
        uploadedAt: new Date().toISOString(),
      };
      setDocuments((prev) => [newDoc, ...prev]);

      try {
        const result = await knowledgeApi.upload(file, (progress) => {
          setUploadProgress(progress);
        });

        // Replace temp doc with real one if API returned data
        if (result) {
          setDocuments((prev) =>
            prev.map((d) =>
              d.id === tempId
                ? {
                    ...d,
                    id: result.id || tempId,
                    status: mapApiStatus(result.status || 'processing'),
                  }
                : d
            )
          );
        }
      } catch {
        // If API fails, keep the optimistic entry with mock progression
        // Simulate processing -> indexing -> ready
        setTimeout(() => {
          setDocuments((prev) =>
            prev.map((d) =>
              d.id === tempId ? { ...d, status: 'indexing' } : d
            )
          );
        }, 2000);
        setTimeout(() => {
          setDocuments((prev) =>
            prev.map((d) =>
              d.id === tempId ? { ...d, status: 'ready', chunks: 18 } : d
            )
          );
        }, 4500);
      } finally {
        setTimeout(() => {
          setIsUploading(false);
          setUploadProgress(0);
          setUploadFileName('');
        }, 500);
      }
    },
    []
  );

  // ── Drag & Drop handlers ──────────────────────────────────────────────
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      const files = Array.from(e.dataTransfer.files);
      files.forEach(uploadFile);
    },
    [uploadFile]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      files.forEach(uploadFile);
      e.target.value = '';
    },
    [uploadFile]
  );

  // ── Delete document ───────────────────────────────────────────────────
  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);

    try {
      await knowledgeApi.delete(deleteTarget.id);
    } catch {
      // API might not be available, still remove from local state
    }

    setDocuments((prev) => prev.filter((d) => d.id !== deleteTarget.id));
    setIsDeleting(false);
    setDeleteTarget(null);
  };

  // ── Refresh status ────────────────────────────────────────────────────
  const refreshStatus = async (doc: KnowledgeDocument) => {
    try {
      const data = await knowledgeApi.getStatus(doc.id) as Record<string, unknown> | null;
      if (data && data.status) {
        setDocuments((prev) =>
          prev.map((d) =>
            d.id === doc.id
              ? { ...d, status: mapApiStatus(data.status as string) }
              : d
          )
        );
      }
    } catch {
      // Simulate status progression for demo
      const nextStatus: Record<DocStatus, DocStatus> = {
        processing: 'indexing',
        indexing: 'ready',
        ready: 'ready',
        failed: 'processing',
      };
      setDocuments((prev) =>
        prev.map((d) =>
          d.id === doc.id
            ? {
                ...d,
                status: nextStatus[d.status],
                ...(nextStatus[d.status] === 'ready' ? { chunks: 15 } : {}),
              }
            : d
        )
      );
    }
  };

  // ── Computed values ───────────────────────────────────────────────────
  const filteredDocs = documents.filter((d) =>
    d.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalDocs = documents.length;
  const readyCount = documents.filter((d) => d.status === 'ready').length;
  const processingCount = documents.filter(
    (d) => d.status === 'processing' || d.status === 'indexing'
  ).length;
  const totalSize = documents.reduce((sum, d) => sum + d.size, 0);

  // ── Loading state ─────────────────────────────────────────────────────
  if (isLoading) {
    return <PageSkeleton />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">Knowledge Base</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Manage your knowledge sources and AI training data
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Database className="w-5 h-5 text-orange-400" />}
          label="Total Documents"
          value={totalDocs}
          accent="bg-orange-500/10"
        />
        <StatCard
          icon={<CheckCircle2 className="w-5 h-5 text-green-400" />}
          label="Ready"
          value={readyCount}
          accent="bg-green-500/10"
        />
        <StatCard
          icon={<Clock className="w-5 h-5 text-yellow-400" />}
          label="Processing"
          value={processingCount}
          accent="bg-yellow-500/10"
        />
        <StatCard
          icon={<HardDrive className="w-5 h-5 text-blue-400" />}
          label="Total Size"
          value={formatFileSize(totalSize)}
          accent="bg-blue-500/10"
        />
      </div>

      {/* Upload Section */}
      <div className="bg-[#1A1A1A] rounded-xl border border-white/[0.06] p-6">
        <h2 className="text-sm font-medium text-white mb-4">Upload Documents</h2>

        {/* Drag & Drop Zone */}
        <div
          className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 cursor-pointer ${
            isDragOver
              ? 'border-orange-500 bg-orange-500/5'
              : 'border-zinc-800 hover:border-zinc-700 hover:bg-white/[0.01]'
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            multiple
            accept={ACCEPTED_TYPES.join(',')}
            onChange={handleFileSelect}
          />

          <div className="flex flex-col items-center gap-3">
            <div
              className={`w-12 h-12 rounded-xl flex items-center justify-center transition-colors ${
                isDragOver
                  ? 'bg-orange-500/20'
                  : 'bg-zinc-800'
              }`}
            >
              <CloudUpload
                className={`w-6 h-6 transition-colors ${
                  isDragOver ? 'text-orange-400' : 'text-zinc-500'
                }`}
              />
            </div>
            <div>
              <p className="text-sm font-medium text-white">
                Drag & drop files here, or{' '}
                <span className="text-orange-400 hover:text-orange-300 underline underline-offset-2">
                  browse
                </span>
              </p>
              <p className="text-xs text-zinc-500 mt-1">
                Maximum file size: 50 MB per file
              </p>
            </div>
          </div>

          {/* File type badges */}
          <div className="flex items-center justify-center gap-2 mt-4">
            {ACCEPTED_TYPES.map((ext) => (
              <Badge
                key={ext}
                variant="outline"
                className="bg-zinc-800/50 text-zinc-400 border-zinc-700/50 text-[10px] px-1.5 py-0"
              >
                {ext.toUpperCase()}
              </Badge>
            ))}
          </div>
        </div>

        {/* Upload Progress */}
        {isUploading && (
          <div className="mt-4 bg-[#0A0A0A] rounded-lg border border-white/[0.06] p-4">
            <div className="flex items-center gap-3 mb-2">
              <Loader2 className="w-4 h-4 text-orange-400 animate-spin shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white truncate">
                  Uploading {uploadFileName}
                </p>
                <p className="text-xs text-zinc-500">
                  {uploadProgress}% complete
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-zinc-500 hover:text-white"
                onClick={(e) => {
                  e.stopPropagation();
                  setIsUploading(false);
                  setUploadProgress(0);
                  setUploadFileName('');
                }}
              >
                <X className="w-3.5 h-3.5" />
              </Button>
            </div>
            <Progress value={uploadProgress} className="h-1.5 bg-zinc-800" />
          </div>
        )}
      </div>

      {/* Empty state or Document List */}
      {documents.length === 0 ? (
        <EmptyState
          onUploadClick={() => fileInputRef.current?.click()}
        />
      ) : (
        <div className="bg-[#1A1A1A] rounded-xl border border-white/[0.06] overflow-hidden">
          {/* Table header with search */}
          <div className="p-4 border-b border-white/[0.06] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <h2 className="text-sm font-medium text-white">
              Documents{' '}
              <span className="text-zinc-500 font-normal">
                ({filteredDocs.length})
              </span>
            </h2>
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <Input
                placeholder="Search documents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 h-9 bg-[#0A0A0A] border-zinc-800 text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:ring-orange-500/20"
              />
            </div>
          </div>

          {/* Table */}
          {filteredDocs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Search className="w-8 h-8 text-zinc-700 mb-3" />
              <p className="text-sm text-zinc-500">
                No documents match &quot;{searchQuery}&quot;
              </p>
              <Button
                variant="ghost"
                size="sm"
                className="mt-2 text-orange-400 hover:text-orange-300"
                onClick={() => setSearchQuery('')}
              >
                Clear search
              </Button>
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden md:block overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="border-white/[0.06] hover:bg-transparent">
                      <TableHead className="text-zinc-500 font-medium">
                        Name
                      </TableHead>
                      <TableHead className="text-zinc-500 font-medium">
                        Type
                      </TableHead>
                      <TableHead className="text-zinc-500 font-medium">
                        Size
                      </TableHead>
                      <TableHead className="text-zinc-500 font-medium">
                        Status
                      </TableHead>
                      <TableHead className="text-zinc-500 font-medium">
                        Uploaded
                      </TableHead>
                      <TableHead className="text-zinc-500 font-medium text-right">
                        Actions
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredDocs.map((doc) => (
                      <TableRow
                        key={doc.id}
                        className="border-white/[0.04] hover:bg-white/[0.02]"
                      >
                        <TableCell>
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center shrink-0 text-zinc-400">
                              {getFileIcon(doc.type)}
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm text-white font-medium truncate max-w-[220px]">
                                {doc.name}
                              </p>
                              {doc.chunks && doc.status === 'ready' && (
                                <p className="text-xs text-zinc-600">
                                  {doc.chunks} chunks
                                </p>
                              )}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={`text-[10px] px-1.5 py-0 ${getTypeColor(doc.type)}`}
                          >
                            {doc.type.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-zinc-400">
                          {formatFileSize(doc.size)}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={doc.status} />
                        </TableCell>
                        <TableCell className="text-sm text-zinc-500">
                          {formatDate(doc.uploadedAt)}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            {(doc.status === 'processing' ||
                              doc.status === 'indexing' ||
                              doc.status === 'failed') && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0 text-zinc-500 hover:text-white hover:bg-white/[0.05]"
                                onClick={() => refreshStatus(doc)}
                                title="Refresh status"
                              >
                                <RefreshCw
                                  className={`w-3.5 h-3.5 ${
                                    doc.status === 'processing' ||
                                    doc.status === 'indexing'
                                      ? 'animate-spin'
                                      : ''
                                  }`}
                                />
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-zinc-500 hover:text-red-400 hover:bg-red-500/10"
                              onClick={() => setDeleteTarget(doc)}
                              title="Delete document"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Mobile card layout */}
              <div className="md:hidden divide-y divide-white/[0.04]">
                {filteredDocs.map((doc) => (
                  <div key={doc.id} className="p-4 space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-9 h-9 rounded-lg bg-zinc-800 flex items-center justify-center shrink-0 text-zinc-400">
                          {getFileIcon(doc.type)}
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm text-white font-medium truncate">
                            {doc.name}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge
                              variant="outline"
                              className={`text-[10px] px-1.5 py-0 ${getTypeColor(doc.type)}`}
                            >
                              {doc.type.toUpperCase()}
                            </Badge>
                            <span className="text-xs text-zinc-600">
                              {formatFileSize(doc.size)}
                            </span>
                          </div>
                        </div>
                      </div>
                      <StatusBadge status={doc.status} />
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-xs text-zinc-600">
                        {formatDate(doc.uploadedAt)}
                        {doc.chunks && doc.status === 'ready' && (
                          <span> · {doc.chunks} chunks</span>
                        )}
                      </span>
                      <div className="flex items-center gap-1">
                        {(doc.status === 'processing' ||
                          doc.status === 'indexing' ||
                          doc.status === 'failed') && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-zinc-500 hover:text-white hover:bg-white/[0.05]"
                            onClick={() => refreshStatus(doc)}
                          >
                            <RefreshCw
                              className={`w-3.5 h-3.5 ${
                                doc.status === 'processing' ||
                                doc.status === 'indexing'
                                  ? 'animate-spin'
                                  : ''
                              }`}
                            />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-zinc-500 hover:text-red-400 hover:bg-red-500/10"
                          onClick={() => setDeleteTarget(doc)}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent className="bg-[#1A1A1A] border-zinc-800">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-white">
              Delete Document
            </AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-400">
              Are you sure you want to delete{' '}
              <span className="text-white font-medium">
                {deleteTarget?.name}
              </span>
              ? This action cannot be undone. The document and all its indexed
              data will be permanently removed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-zinc-800 border-zinc-700 text-white hover:bg-zinc-700 hover:text-white">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700 text-white border-0 disabled:opacity-50"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Deleting...
                </>
              ) : (
                'Delete'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
