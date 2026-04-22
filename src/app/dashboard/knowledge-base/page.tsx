'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  kbApi,
  type KBDocument,
  type KBDocumentListResponse,
  type KBStats,
  type RAGSearchResult,
  type DocumentStatus,
} from '@/lib/kb-api';

// ── Skeleton Helper ────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/[0.06]', className)} />;
}

// ── Inline SVG Icons ───────────────────────────────────────────────────────

function BookOpenIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
    </svg>
  );
}

function CloudArrowUpIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
    </svg>
  );
}

function MagnifyingGlassIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
    </svg>
  );
}

function DocumentTextIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  );
}

function CubeIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
    </svg>
  );
}

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function XCircleIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function ExclamationCircleIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function ArrowPathIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
    </svg>
  );
}

function XMarkIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
    </svg>
  );
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
    </svg>
  );
}

function FunnelIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z" />
    </svg>
  );
}

function BeakerIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
    </svg>
  );
}

function SparklesIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
    </svg>
  );
}

function LayersIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.429 9.75L2.25 12l4.179 2.25m0-4.5l5.571 3 5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L21.75 12l-4.179 2.25m0 0l4.179 2.25L12 21.75 2.25 16.5l4.179-2.25m11.142 0l-5.571 3-5.571-3" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className={className}>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

// ── Format Helpers ─────────────────────────────────────────────────────────

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return 'N/A';
  }
}

function formatFileSize(bytes: number | undefined): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusBadge(status: DocumentStatus): string {
  switch (status) {
    case 'completed': return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20';
    case 'processing': return 'bg-yellow-500/15 text-yellow-400 border-yellow-500/20';
    case 'pending': return 'bg-zinc-500/15 text-zinc-400 border-zinc-500/20';
    case 'failed': return 'bg-red-500/15 text-red-400 border-red-500/20';
    default: return 'bg-zinc-500/15 text-zinc-400 border-zinc-500/20';
  }
}

function statusLabel(status: DocumentStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function fileTypeBadge(fileType: string | undefined): string {
  if (!fileType) return 'bg-zinc-500/15 text-zinc-400';
  const t = fileType.toLowerCase().replace('.', '');
  if (t === 'pdf') return 'bg-red-500/15 text-red-400';
  if (['doc', 'docx'].includes(t)) return 'bg-blue-500/15 text-blue-400';
  if (['txt', 'md'].includes(t)) return 'bg-zinc-500/15 text-zinc-300';
  if (['csv'].includes(t)) return 'bg-emerald-500/15 text-emerald-400';
  return 'bg-zinc-500/15 text-zinc-400';
}

function fileTypeLabel(fileType: string | undefined): string {
  if (!fileType) return 'File';
  const t = fileType.toLowerCase().replace('.', '');
  return t.toUpperCase() || 'File';
}

function scoreColor(score: number): string {
  if (score >= 0.8) return 'text-emerald-400';
  if (score >= 0.5) return 'text-yellow-400';
  return 'text-red-400';
}

// ── Category Options ───────────────────────────────────────────────────────

const CATEGORIES = [
  { value: '', label: 'All Categories' },
  { value: 'product_info', label: 'Product Info' },
  { value: 'policies', label: 'Policies' },
  { value: 'faqs', label: 'FAQs' },
  { value: 'procedures', label: 'Procedures' },
  { value: 'technical', label: 'Technical Docs' },
  { value: 'training', label: 'Training Material' },
  { value: 'other', label: 'Other' },
];

const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt', '.csv', '.md'];

// ── Error Fallback ─────────────────────────────────────────────────────────

function SectionError({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
      <p className="text-sm text-zinc-500">{message || 'Unable to load data'}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-xs text-[#FF7F11] hover:underline">
          Try again
        </button>
      )}
    </div>
  );
}

// ── Delete Confirmation Modal ──────────────────────────────────────────────

function DeleteModal({
  doc,
  onConfirm,
  onClose,
  loading,
}: {
  doc: KBDocument;
  onConfirm: () => void;
  onClose: () => void;
  loading: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-2xl border border-white/[0.08] bg-[#1A1A1A] p-6 shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-500/10">
            <TrashIcon className="h-5 w-5 text-red-400" />
          </div>
          <h3 className="text-lg font-semibold text-white">Delete Document</h3>
        </div>
        <p className="text-sm text-zinc-400 mb-6">
          Are you sure you want to delete{' '}
          <span className="text-zinc-200 font-medium">{doc.filename}</span>?
          This will permanently remove the document and all its associated chunks from the knowledge base.
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-zinc-300 hover:bg-white/[0.08] disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50 transition-colors"
          >
            {loading ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <TrashIcon className="h-4 w-4" />}
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// Main Knowledge Base Page Component
// ════════════════════════════════════════════════════════════════════════════

export default function KnowledgeBasePage() {
  // ── K5: Stats State ──────────────────────────────────────────────────────
  const [stats, setStats] = useState<KBStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState(false);

  // ── K1: Documents State ─────────────────────────────────────────────────
  const [documents, setDocuments] = useState<KBDocument[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState(false);

  // ── K6: Filters ─────────────────────────────────────────────────────────
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | ''>('');
  const [categoryFilter, setCategoryFilter] = useState('');

  // ── K2: Upload State ────────────────────────────────────────────────────
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [isDragging, setIsDragging] = useState(false);
  const [uploadCategory, setUploadCategory] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── K3: Document Actions ────────────────────────────────────────────────
  const [actionLoadingMap, setActionLoadingMap] = useState<Record<string, boolean>>({});
  const [deleteModalDoc, setDeleteModalDoc] = useState<KBDocument | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // ── K7: Chunk Preview ───────────────────────────────────────────────────
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null);

  // ── K4/K8: Search State ─────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<RAGSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchPerformed, setSearchPerformed] = useState(false);

  // ── RAG Test Panel ──────────────────────────────────────────────────────
  const [testQuestion, setTestQuestion] = useState('');
  const [testResults, setTestResults] = useState<RAGSearchResult[]>([]);
  const [testLoading, setTestLoading] = useState(false);
  const [testPerformed, setTestPerformed] = useState(false);

  // ── Active Tab ──────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<'documents' | 'search' | 'test'>('documents');

  // ── Polling for processing documents ────────────────────────────────────
  const [hasProcessing, setHasProcessing] = useState(false);

  // ── Data Loading ────────────────────────────────────────────────────────

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    setStatsError(false);
    try {
      const data = await kbApi.getStats();
      setStats(data);
    } catch {
      setStatsError(true);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const loadDocuments = useCallback(async () => {
    setDocumentsLoading(true);
    setDocumentsError(false);
    try {
      const params: { status?: DocumentStatus; category?: string } = {};
      if (statusFilter) params.status = statusFilter;
      if (categoryFilter) params.category = categoryFilter;
      const data: KBDocumentListResponse = await kbApi.listDocuments(params);
      const docs = Array.isArray(data) ? data : (data as any).documents || [];
      setDocuments(docs);
      setHasProcessing(docs.some((d: KBDocument) => d.status === 'processing' || d.status === 'pending'));
    } catch {
      setDocumentsError(true);
    } finally {
      setDocumentsLoading(false);
    }
  }, [statusFilter, categoryFilter]);

  useEffect(() => {
    Promise.allSettled([loadStats(), loadDocuments()]);
  }, [loadStats, loadDocuments]);

  // ── Auto-poll when processing docs exist ────────────────────────────────
  useEffect(() => {
    if (!hasProcessing) return;
    const interval = setInterval(() => {
      loadDocuments();
      loadStats();
    }, 5000);
    return () => clearInterval(interval);
  }, [hasProcessing, loadDocuments, loadStats]);

  // ── K2: Upload Handlers ─────────────────────────────────────────────────

  const handleFileUpload = async (files: FileList | File[]) => {
    const validFiles = Array.from(files).filter((f) => {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase();
      return ACCEPTED_EXTENSIONS.includes(ext);
    });

    if (validFiles.length === 0) {
      toast.error('No valid files. Accepted: PDF, DOCX, DOC, TXT, CSV, MD');
      return;
    }

    for (const file of validFiles) {
      const key = `${file.name}-${Date.now()}`;
      setUploadProgress((prev) => ({ ...prev, [key]: 0 }));

      try {
        await kbApi.upload(file, (progress) => {
          setUploadProgress((prev) => ({ ...prev, [key]: progress }));
        }, uploadCategory || undefined);
        toast.success(`${file.name} uploaded successfully`);
      } catch (error) {
        toast.error(`${file.name}: ${getErrorMessage(error)}`);
      } finally {
        setUploadProgress((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      }
    }

    loadDocuments();
    loadStats();
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files.length > 0) {
        handleFileUpload(e.dataTransfer.files);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [uploadCategory],
  );

  // ── K3: Document Action Handlers ────────────────────────────────────────

  const handleReindex = async (docId: string) => {
    setActionLoadingMap((prev) => ({ ...prev, [docId]: true }));
    try {
      await kbApi.reindexDocument(docId);
      toast.success('Document queued for re-indexing');
      loadDocuments();
      loadStats();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setActionLoadingMap((prev) => ({ ...prev, [docId]: false }));
    }
  };

  const handleRetry = async (docId: string) => {
    setActionLoadingMap((prev) => ({ ...prev, [docId]: true }));
    try {
      await kbApi.retryDocument(docId);
      toast.success('Document queued for retry');
      loadDocuments();
      loadStats();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setActionLoadingMap((prev) => ({ ...prev, [docId]: false }));
    }
  };

  const handleDelete = async () => {
    if (!deleteModalDoc) return;
    setDeleteLoading(true);
    try {
      await kbApi.deleteDocument(deleteModalDoc.id);
      toast.success(`${deleteModalDoc.filename} deleted`);
      setDeleteModalDoc(null);
      loadDocuments();
      loadStats();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setDeleteLoading(false);
    }
  };

  // ── K4: Search Handler ──────────────────────────────────────────────────

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      toast.error('Enter a search query');
      return;
    }
    setSearchLoading(true);
    setSearchPerformed(true);
    try {
      const data = await kbApi.search({ query: searchQuery.trim(), top_k: 10 });
      setSearchResults(data.results || []);
    } catch (error) {
      toast.error(getErrorMessage(error));
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  };

  // ── K8: RAG Test Handler ────────────────────────────────────────────────

  const handleRAGTest = async () => {
    if (!testQuestion.trim()) {
      toast.error('Enter a test question');
      return;
    }
    setTestLoading(true);
    setTestPerformed(true);
    try {
      const data = await kbApi.search({ query: testQuestion.trim(), top_k: 5 });
      setTestResults(data.results || []);
    } catch (error) {
      toast.error(getErrorMessage(error));
      setTestResults([]);
    } finally {
      setTestLoading(false);
    }
  };

  // ── Highlight matching text ─────────────────────────────────────────────

  function highlightText(text: string, query: string) {
    if (!query.trim()) return text;
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escaped})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark key={i} className="bg-[#FF7F11]/30 text-[#FF7F11] rounded-sm px-0.5">
          {part}
        </mark>
      ) : (
        <span key={i}>{part}</span>
      ),
    );
  }

  // ── Count of files being uploaded ───────────────────────────────────────
  const uploadingCount = Object.keys(uploadProgress).length;

  // ════════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div className="jarvis-page-body min-h-screen bg-[#0A0A0A]">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Page Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FF7F11]/10">
              <BookOpenIcon className="h-5 w-5 text-[#FF7F11]" />
            </div>
            <h1 className="text-2xl font-bold text-white">Knowledge Base</h1>
          </div>
          <p className="text-sm text-zinc-500 ml-[52px]">
            Upload documents, manage indexing, and search your knowledge base for AI-powered answers.
          </p>
        </div>

        {/* ═══════════════════════════════════════════════════════════════════
            K5: Statistics Strip
            ═══════════════════════════════════════════════════════════════════ */}
        {statsLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        ) : statsError ? (
          <SectionError message="Unable to load KB statistics" onRetry={loadStats} />
        ) : stats ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
            <StatCard
              icon={<DocumentTextIcon className="h-5 w-5 text-[#FF7F11]" />}
              label="Total Documents"
              value={stats.total_documents.toLocaleString()}
              bgColor="bg-[#FF7F11]/10"
            />
            <StatCard
              icon={<CubeIcon className="h-5 w-5 text-blue-400" />}
              label="Total Chunks"
              value={stats.total_chunks.toLocaleString()}
              bgColor="bg-blue-500/10"
            />
            <StatCard
              icon={<CheckCircleIcon className="h-5 w-5 text-emerald-400" />}
              label="Completed"
              value={stats.completed.toLocaleString()}
              bgColor="bg-emerald-500/10"
            />
            <StatCard
              icon={<ClockIcon className="h-5 w-5 text-yellow-400" />}
              label="Processing"
              value={stats.processing.toLocaleString()}
              bgColor="bg-yellow-500/10"
            />
            <StatCard
              icon={<XCircleIcon className="h-5 w-5 text-red-400" />}
              label="Failed"
              value={stats.failed.toLocaleString()}
              bgColor="bg-red-500/10"
            />
          </div>
        ) : null}

        {/* ═══════════════════════════════════════════════════════════════════
            K2: Upload Zone
            ═══════════════════════════════════════════════════════════════════ */}
        <div className="mb-8">
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={cn(
              'relative rounded-xl border-2 border-dashed transition-all cursor-pointer',
              isDragging
                ? 'border-[#FF7F11]/60 bg-[#FF7F11]/5'
                : 'border-white/[0.08] bg-[#1A1A1A] hover:border-white/[0.15]',
            )}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.doc,.txt,.csv,.md"
              className="hidden"
              onChange={(e) => {
                if (e.target.files) handleFileUpload(e.target.files);
                e.target.value = '';
              }}
            />
            <div className="p-8 text-center">
              <CloudArrowUpIcon
                className={cn(
                  'h-10 w-10 mx-auto mb-3',
                  isDragging ? 'text-[#FF7F11]' : 'text-zinc-500',
                )}
              />
              <p className="text-sm font-medium text-zinc-300 mb-1">
                {isDragging ? 'Drop files here' : 'Drag & drop documents or click to browse'}
              </p>
              <p className="text-xs text-zinc-500">
                Supports PDF, DOCX, DOC, TXT, CSV, MD — Max file size per document depends on your plan
              </p>
              {/* Category selector inside upload zone */}
              <div className="mt-4 flex items-center justify-center gap-2">
                <span className="text-xs text-zinc-500">Category:</span>
                <select
                  value={uploadCategory}
                  onChange={(e) => setUploadCategory(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-[#FF7F11]/50"
                >
                  {CATEGORIES.slice(1).map((cat) => (
                    <option key={cat.value} value={cat.value}>
                      {cat.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Upload progress bars */}
          {uploadingCount > 0 && (
            <div className="mt-3 space-y-2">
              {Object.entries(uploadProgress).map(([key, progress]) => (
                <div key={key} className="rounded-lg bg-[#141414] border border-white/[0.04] p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-zinc-400 truncate max-w-[200px]">
                      {key.split('-').slice(0, -1).join('-')}
                    </span>
                    <span className="text-xs text-zinc-500">{progress}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[#FF7F11] transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ═══════════════════════════════════════════════════════════════════
            Tab Navigation
            ═══════════════════════════════════════════════════════════════════ */}
        <div className="mb-6">
          <div className="flex items-center gap-1 rounded-xl border border-white/[0.06] bg-[#141414] p-1">
            {[
              { key: 'documents' as const, label: 'Documents', icon: DocumentTextIcon },
              { key: 'search' as const, label: 'Search', icon: MagnifyingGlassIcon },
              { key: 'test' as const, label: 'RAG Test', icon: BeakerIcon },
            ].map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all flex-1 justify-center',
                  activeTab === key
                    ? 'bg-[#FF7F11] text-white shadow-lg shadow-[#FF7F11]/20'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]',
                )}
              >
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════════════
            K1/K6/K7: Documents Tab
            ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'documents' && (
          <div>
            {/* Filters */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4">
              <div className="flex items-center gap-2 text-xs text-zinc-500">
                <FunnelIcon className="h-4 w-4" />
                <span>Filter:</span>
              </div>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as DocumentStatus | '')}
                className="rounded-lg border border-white/[0.08] bg-[#1A1A1A] px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-[#FF7F11]/50"
              >
                <option value="">All Statuses</option>
                <option value="completed">Completed</option>
                <option value="processing">Processing</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
              </select>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="rounded-lg border border-white/[0.08] bg-[#1A1A1A] px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-[#FF7F11]/50"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Document Table */}
            {documentsLoading ? (
              <div className="space-y-3">
                {[...Array(5)].map((_, i) => (
                  <Skeleton key={i} className="h-16" />
                ))}
              </div>
            ) : documentsError ? (
              <SectionError message="Unable to load documents" onRetry={loadDocuments} />
            ) : documents.length === 0 ? (
              <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-12 text-center">
                <DocumentTextIcon className="h-12 w-12 text-zinc-600 mx-auto mb-4" />
                <p className="text-sm font-medium text-zinc-400 mb-1">No documents yet</p>
                <p className="text-xs text-zinc-500 mb-4">
                  Upload your first document to start building your knowledge base.
                </p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex items-center gap-2 rounded-xl bg-[#FF7F11] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
                >
                  <CloudArrowUpIcon className="h-4 w-4" />
                  Upload Document
                </button>
              </div>
            ) : (
              <div className="rounded-xl border border-white/[0.06] bg-[#111111] overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/[0.06]">
                        <th className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">Name</th>
                        <th className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">Type</th>
                        <th className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider hidden sm:table-cell">Size</th>
                        <th className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">Status</th>
                        <th className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider hidden md:table-cell">Chunks</th>
                        <th className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider hidden lg:table-cell">Uploaded</th>
                        <th className="px-5 py-3 text-right text-xs font-medium text-zinc-500 uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.04]">
                      {documents.map((doc) => {
                        const isExpanded = expandedDocId === doc.id;
                        return (
                          <React.Fragment key={doc.id}>
                            <tr
                              className="hover:bg-white/[0.02] transition-colors cursor-pointer"
                              onClick={() =>
                                setExpandedDocId(isExpanded ? null : doc.id)
                              }
                            >
                              <td className="px-5 py-3.5">
                                <div className="flex items-center gap-2">
                                  <ChevronRightIcon
                                    className={cn(
                                      'h-4 w-4 text-zinc-500 transition-transform shrink-0',
                                      isExpanded && 'rotate-90',
                                    )}
                                  />
                                  <span className="text-zinc-200 truncate max-w-[200px]" title={doc.filename}>
                                    {doc.filename}
                                  </span>
                                </div>
                              </td>
                              <td className="px-5 py-3.5">
                                <span
                                  className={cn(
                                    'inline-flex rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase',
                                    fileTypeBadge(doc.file_type),
                                  )}
                                >
                                  {fileTypeLabel(doc.file_type)}
                                </span>
                              </td>
                              <td className="px-5 py-3.5 text-zinc-400 hidden sm:table-cell whitespace-nowrap">
                                {formatFileSize(doc.file_size)}
                              </td>
                              <td className="px-5 py-3.5">
                                <span
                                  className={cn(
                                    'inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase',
                                    statusBadge(doc.status),
                                  )}
                                >
                                  {statusLabel(doc.status)}
                                </span>
                              </td>
                              <td className="px-5 py-3.5 text-zinc-400 hidden md:table-cell">
                                {doc.chunk_count ?? '—'}
                              </td>
                              <td className="px-5 py-3.5 text-zinc-500 hidden lg:table-cell whitespace-nowrap">
                                {formatDate(doc.created_at)}
                              </td>
                              <td className="px-5 py-3.5 text-right">
                                <div className="flex items-center justify-end gap-1">
                                  {(doc.status === 'completed') && (
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleReindex(doc.id);
                                      }}
                                      disabled={!!actionLoadingMap[doc.id]}
                                      title="Re-index"
                                      className="rounded-lg p-1.5 text-zinc-400 hover:text-[#FF7F11] hover:bg-[#FF7F11]/10 disabled:opacity-40 transition-colors"
                                    >
                                      {actionLoadingMap[doc.id] ? (
                                        <SpinnerIcon className="h-3.5 w-3.5 animate-spin" />
                                      ) : (
                                        <ArrowPathIcon className="h-3.5 w-3.5" />
                                      )}
                                    </button>
                                  )}
                                  {doc.status === 'failed' && (
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleRetry(doc.id);
                                      }}
                                      disabled={!!actionLoadingMap[doc.id]}
                                      title="Retry"
                                      className="rounded-lg p-1.5 text-zinc-400 hover:text-yellow-400 hover:bg-yellow-400/10 disabled:opacity-40 transition-colors"
                                    >
                                      {actionLoadingMap[doc.id] ? (
                                        <SpinnerIcon className="h-3.5 w-3.5 animate-spin" />
                                      ) : (
                                        <ArrowPathIcon className="h-3.5 w-3.5" />
                                      )}
                                    </button>
                                  )}
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setDeleteModalDoc(doc);
                                    }}
                                    title="Delete"
                                    className="rounded-lg p-1.5 text-zinc-400 hover:text-red-400 hover:bg-red-400/10 transition-colors"
                                  >
                                    <TrashIcon className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              </td>
                            </tr>

                            {/* K7: Expanded Chunk Preview */}
                            {isExpanded && (
                              <tr>
                                <td colSpan={7} className="px-5 py-0">
                                  <div className="border-t border-white/[0.04] bg-[#0E0E0E]">
                                    <div className="p-4">
                                      <div className="flex items-center gap-2 mb-3">
                                        <LayersIcon className="h-4 w-4 text-[#FF7F11]" />
                                        <span className="text-xs font-medium text-zinc-300">
                                          Document Details
                                        </span>
                                      </div>
                                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
                                        <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-3">
                                          <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Status</p>
                                          <span className={cn('inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase', statusBadge(doc.status))}>
                                            {statusLabel(doc.status)}
                                          </span>
                                        </div>
                                        <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-3">
                                          <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Chunks</p>
                                          <p className="text-sm font-medium text-zinc-200">
                                            {doc.chunk_count ?? 0} chunks
                                          </p>
                                        </div>
                                        <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-3">
                                          <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Retries</p>
                                          <p className="text-sm font-medium text-zinc-200">
                                            {doc.retry_count ?? 0}
                                          </p>
                                        </div>
                                      </div>
                                      {doc.error_message && (
                                        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 mb-3">
                                          <div className="flex items-center gap-2 mb-1">
                                            <ExclamationCircleIcon className="h-3.5 w-3.5 text-red-400" />
                                            <span className="text-xs font-medium text-red-300">Error</span>
                                          </div>
                                          <p className="text-xs text-red-400/80">{doc.error_message}</p>
                                        </div>
                                      )}
                                      {doc.status === 'completed' && doc.chunk_count && doc.chunk_count > 0 ? (
                                        <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-3">
                                          <div className="flex items-center gap-2 mb-2">
                                            <SparklesIcon className="h-3.5 w-3.5 text-emerald-400" />
                                            <span className="text-xs font-medium text-emerald-300">
                                              Embedding Complete
                                            </span>
                                          </div>
                                          <p className="text-xs text-zinc-400">
                                            {doc.chunk_count} chunks embedded and ready for semantic search.
                                            {doc.file_type && (
                                              <span> Source: <span className="text-zinc-300">{doc.filename}</span></span>
                                            )}
                                          </p>
                                        </div>
                                      ) : doc.status === 'processing' ? (
                                        <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-3">
                                          <div className="flex items-center gap-2">
                                            <SpinnerIcon className="h-3.5 w-3.5 animate-spin text-yellow-400" />
                                            <span className="text-xs text-yellow-300">
                                              Indexing in progress... This page will auto-refresh.
                                            </span>
                                          </div>
                                        </div>
                                      ) : doc.status === 'pending' ? (
                                        <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-3">
                                          <div className="flex items-center gap-2">
                                            <ClockIcon className="h-3.5 w-3.5 text-zinc-400" />
                                            <span className="text-xs text-zinc-400">
                                              Waiting in queue for processing...
                                            </span>
                                          </div>
                                        </div>
                                      ) : null}
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {/* Total count */}
                <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-3">
                  <p className="text-xs text-zinc-500">
                    {documents.length} document{documents.length !== 1 ? 's' : ''}
                  </p>
                  {hasProcessing && (
                    <div className="flex items-center gap-1.5">
                      <SpinnerIcon className="h-3 w-3 animate-spin text-[#FF7F11]" />
                      <span className="text-xs text-zinc-500">Auto-refreshing...</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            K4: Search Knowledge Base Tab
            ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'search' && (
          <div>
            {/* Search Bar */}
            <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4 mb-6">
              <div className="flex items-center gap-3">
                <MagnifyingGlassIcon className="h-5 w-5 text-zinc-500 shrink-0" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSearch();
                  }}
                  placeholder="Search across all your documents..."
                  className="flex-1 bg-transparent text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none"
                />
                <button
                  onClick={handleSearch}
                  disabled={searchLoading}
                  className="shrink-0 inline-flex items-center gap-2 rounded-xl bg-[#FF7F11] px-4 py-2 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 disabled:opacity-50 transition-colors"
                >
                  {searchLoading ? (
                    <SpinnerIcon className="h-4 w-4 animate-spin" />
                  ) : (
                    <MagnifyingGlassIcon className="h-4 w-4" />
                  )}
                  Search
                </button>
              </div>
            </div>

            {/* Search Results */}
            {!searchPerformed && (
              <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-12 text-center">
                <MagnifyingGlassIcon className="h-12 w-12 text-zinc-600 mx-auto mb-4" />
                <p className="text-sm font-medium text-zinc-400 mb-1">Search Your Knowledge Base</p>
                <p className="text-xs text-zinc-500">
                  Enter a query to perform semantic search across all indexed documents.
                </p>
              </div>
            )}

            {searchPerformed && searchLoading && (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-32" />
                ))}
              </div>
            )}

            {searchPerformed && !searchLoading && searchResults.length === 0 && (
              <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-8 text-center">
                <MagnifyingGlassIcon className="h-10 w-10 text-zinc-600 mx-auto mb-3" />
                <p className="text-sm text-zinc-500">No results found for your query.</p>
              </div>
            )}

            {searchPerformed && !searchLoading && searchResults.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs text-zinc-500 mb-2">
                  {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} found
                </p>
                {searchResults.map((result, index) => (
                  <div
                    key={index}
                    className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4 hover:border-white/[0.1] transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-[#FF7F11]/10 text-[10px] font-bold text-[#FF7F11]">
                          {index + 1}
                        </span>
                        <span className="text-xs text-zinc-400 truncate max-w-[250px]" title={result.source}>
                          {result.source}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {result.page && (
                          <span className="text-[10px] text-zinc-500 bg-zinc-500/10 px-1.5 py-0.5 rounded">
                            p.{result.page}
                          </span>
                        )}
                        <span className={cn('text-xs font-semibold', scoreColor(result.score))}>
                          {(result.score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                    <p className="text-sm text-zinc-300 leading-relaxed line-clamp-3">
                      {highlightText(result.content, searchQuery)}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            K8: RAG Test Panel Tab
            ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'test' && (
          <div>
            {/* Test Header */}
            <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5 mb-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/10">
                  <BeakerIcon className="h-4 w-4 text-purple-400" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">Test Your Knowledge Base</h3>
                  <p className="text-xs text-zinc-500">
                    Ask a question and see which chunks the RAG system retrieves.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <SparklesIcon className="h-4 w-4 text-zinc-500 shrink-0" />
                <input
                  type="text"
                  value={testQuestion}
                  onChange={(e) => setTestQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleRAGTest();
                  }}
                  placeholder="What is our refund policy? How do I integrate the API?"
                  className="flex-1 bg-[#141414] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-[#FF7F11]/50"
                />
                <button
                  onClick={handleRAGTest}
                  disabled={testLoading}
                  className="shrink-0 inline-flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2 text-sm font-semibold text-white hover:bg-purple-500 disabled:opacity-50 transition-colors"
                >
                  {testLoading ? (
                    <SpinnerIcon className="h-4 w-4 animate-spin" />
                  ) : (
                    <SparklesIcon className="h-4 w-4" />
                  )}
                  Test
                </button>
              </div>
            </div>

            {/* Test Results */}
            {!testPerformed && (
              <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-12 text-center">
                <BeakerIcon className="h-12 w-12 text-zinc-600 mx-auto mb-4" />
                <p className="text-sm font-medium text-zinc-400 mb-1">RAG Quality Test</p>
                <p className="text-xs text-zinc-500 max-w-md mx-auto">
                  Ask a question your customers might ask. The system will return the top 5 most relevant chunks
                  from your knowledge base with relevance scores.
                </p>
              </div>
            )}

            {testPerformed && testLoading && (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-40" />
                ))}
              </div>
            )}

            {testPerformed && !testLoading && testResults.length === 0 && (
              <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-8 text-center">
                <ExclamationCircleIcon className="h-10 w-10 text-yellow-600 mx-auto mb-3" />
                <p className="text-sm text-zinc-500">No relevant chunks found. Try uploading more documents or rephrasing your question.</p>
              </div>
            )}

            {testPerformed && !testLoading && testResults.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-zinc-500">
                    Top {testResults.length} chunks retrieved
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-zinc-500">Question:</span>
                    <span className="text-xs text-zinc-300 italic">&quot;{testQuestion}&quot;</span>
                  </div>
                </div>
                {testResults.map((result, index) => (
                  <div
                    key={index}
                    className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4 hover:border-white/[0.1] transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-purple-500/10 text-[10px] font-bold text-purple-400">
                          #{index + 1}
                        </span>
                        <span className="text-xs text-zinc-400 truncate max-w-[250px]" title={result.source}>
                          {result.source}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {result.page && (
                          <span className="text-[10px] text-zinc-500 bg-zinc-500/10 px-1.5 py-0.5 rounded">
                            Page {result.page}
                          </span>
                        )}
                        {/* Relevance score bar */}
                        <div className="flex items-center gap-1.5">
                          <div className="h-1.5 w-16 rounded-full bg-white/[0.06] overflow-hidden">
                            <div
                              className={cn(
                                'h-full rounded-full transition-all',
                                result.score >= 0.8 ? 'bg-emerald-500' : result.score >= 0.5 ? 'bg-yellow-500' : 'bg-red-500',
                              )}
                              style={{ width: `${result.score * 100}%` }}
                            />
                          </div>
                          <span className={cn('text-xs font-semibold min-w-[36px] text-right', scoreColor(result.score))}>
                            {(result.score * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-3">
                      <p className="text-sm text-zinc-300 leading-relaxed">
                        {highlightText(result.content.substring(0, 500), testQuestion)}
                        {result.content.length > 500 && (
                          <span className="text-zinc-500">...</span>
                        )}
                      </p>
                    </div>
                    {result.metadata && Object.keys(result.metadata).length > 0 && (
                      <div className="mt-2 flex items-center gap-2 flex-wrap">
                        {Object.entries(result.metadata).map(([key, value]) => (
                          <span
                            key={key}
                            className="text-[10px] text-zinc-500 bg-white/[0.04] px-2 py-0.5 rounded-md"
                          >
                            {key}: {String(value)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Delete Confirmation Modal ─────────────────────────────────── */}
      {deleteModalDoc && (
        <DeleteModal
          doc={deleteModalDoc}
          onConfirm={handleDelete}
          onClose={() => setDeleteModalDoc(null)}
          loading={deleteLoading}
        />
      )}
    </div>
  );
}

// ── Sub-Components ─────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  bgColor,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  bgColor: string;
}) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
      <div className="flex items-center gap-3">
        <div className={cn('flex h-9 w-9 items-center justify-center rounded-lg', bgColor)}>
          {icon}
        </div>
        <div>
          <p className="text-xs text-zinc-500">{label}</p>
          <p className="text-lg font-bold text-white">{value}</p>
        </div>
      </div>
    </div>
  );
}
