'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { knowledgeApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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
import { toast } from 'sonner';
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
  PenLine,
  Sparkles,
  FilePlus2,
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

function EmptyState({ onUploadClick, onCreateClick }: { onUploadClick: () => void; onCreateClick: () => void }) {
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
      <div className="flex flex-col sm:flex-row gap-3">
        <Button
          onClick={onUploadClick}
          className="bg-orange-500 hover:bg-orange-600 text-white gap-2"
        >
          <Upload className="w-4 h-4" />
          Upload Document
        </Button>
        <Button
          onClick={onCreateClick}
          variant="outline"
          className="border-white/10 bg-white/[0.02] hover:bg-white/[0.06] text-zinc-200 gap-2"
        >
          <PenLine className="w-4 h-4" />
          Write an Article
        </Button>
      </div>
    </div>
  );
}

// ── Create Article Dialog ───────────────────────────────────────────────

const ARTICLE_CATEGORIES = [
  { value: 'general', label: 'General' },
  { value: 'faq', label: 'FAQ' },
  { value: 'policy', label: 'Policy' },
  { value: 'shipping', label: 'Shipping' },
  { value: 'returns', label: 'Returns & Refunds' },
  { value: 'billing', label: 'Billing' },
  { value: 'technical', label: 'Technical Support' },
  { value: 'product', label: 'Product Info' },
];

const TEMPLATE_CONTENT: Record<string, { title: string; content: string }> = {
  '': { title: '', content: '' },
  faq: {
    title: 'Frequently Asked Questions',
    content: 'Q: What are your business hours?\nA: We are available 24/7 via our AI support. Human agents are available Monday-Friday, 9 AM to 6 PM EST.\n\nQ: How do I track my order?\nA: Once your order ships, you will receive a tracking number via email. Click the tracking link to see real-time updates.\n\nQ: What is your return policy?\nA: Items can be returned within 30 days of delivery in original condition for a full refund.',
  },
  policy: {
    title: 'Company Policy',
    content: 'ORDER PROCESSING:\nAll orders are processed within 1-2 business days.\n\nPAYMENT:\nWe accept all major credit cards, PayPal, and Apple Pay.\n\nPRIVACY:\nWe never share customer data with third parties. All information is encrypted and stored securely.\n\nCONTACT:\nFor policy questions, email support@company.com.',
  },
  shipping: {
    title: 'Shipping Information',
    content: 'SHIPPING TIMEFRAMES:\n- Standard Shipping: 5-7 business days\n- Express Shipping: 2-3 business days\n- Same-Day Delivery: Available in select cities (order before 12 PM)\n\nLOST PACKAGES:\nIf your package has not arrived within 7 days of the expected delivery date and tracking shows no updates, contact us for a replacement or full refund.\n\nINTERNATIONAL SHIPPING:\nAvailable to 40+ countries. Customs fees may apply.',
  },
  returns: {
    title: 'Returns & Refund Policy',
    content: 'RETURN WINDOW:\nItems can be returned within 30 days of delivery.\n\nCONDITION:\nItems must be in original condition with tags attached.\n\nREFUND PROCESS:\nRefunds are processed within 3-5 business days of receiving the returned item. The refund will be issued to the original payment method.\n\nEXCHANGES:\nFree exchanges for size/color changes within 30 days.',
  },
};

function CreateArticleDialog({
  open,
  onOpenChange,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('general');
  const [isSaving, setIsSaving] = useState(false);

  const handleCategoryChange = (newCat: string) => {
    setCategory(newCat);
    // Auto-fill template if content is empty or matches a template
    const template = TEMPLATE_CONTENT[newCat === 'general' ? '' : newCat];
    if (template && (content.trim() === '' || Object.values(TEMPLATE_CONTENT).some(t => t.content === content))) {
      setTitle(template.title || title);
      setContent(template.content);
    }
  };

  const handleSave = async () => {
    if (!title.trim()) {
      toast.error('Please enter a title for your article.');
      return;
    }
    if (content.trim().length < 10) {
      toast.error('Content must be at least 10 characters.');
      return;
    }
    setIsSaving(true);
    try {
      const result = await knowledgeApi.createText(title, content, category);
      toast.success(`Article "${title.trim()}" created successfully!`);
      setTitle('');
      setContent('');
      setCategory('general');
      onOpenChange(false);
      onSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create article';
      // Extract detail from axios error
      const detail = (err as { response?: { data?: { message?: string; detail?: string } } })?.response?.data?.message
        || (err as { response?: { data?: { message?: string; detail?: string } } })?.response?.data?.detail
        || msg;
      toast.error(typeof detail === 'string' ? detail : 'Failed to create article. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
  const charCount = content.length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-[#1A1A1A] border-white/10 text-white p-0 gap-0 max-h-[90vh] flex flex-col">
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-white/[0.06]">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <div className="w-8 h-8 rounded-lg bg-orange-500/15 flex items-center justify-center">
              <PenLine className="w-4 h-4 text-orange-400" />
            </div>
            Create Knowledge Article
          </DialogTitle>
          <DialogDescription className="text-zinc-500 text-sm">
            Write an article directly — no file needed. Your AI will use this to answer customer questions.
          </DialogDescription>
        </DialogHeader>

        <div className="px-6 py-5 space-y-4 overflow-y-auto flex-1">
          {/* Title */}
          <div className="space-y-1.5">
            <Label htmlFor="article-title" className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
              Title <span className="text-orange-400">*</span>
            </Label>
            <Input
              id="article-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Order Tracking & Shipping Policy"
              className="bg-white/[0.03] border-white/10 text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:ring-orange-500/20"
              maxLength={200}
            />
          </div>

          {/* Category */}
          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
              Category
            </Label>
            <div className="flex flex-wrap gap-2">
              {ARTICLE_CATEGORIES.map((cat) => (
                <button
                  key={cat.value}
                  type="button"
                  onClick={() => handleCategoryChange(cat.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${
                    category === cat.value
                      ? 'bg-orange-500/20 border-orange-500/40 text-orange-300'
                      : 'bg-white/[0.02] border-white/8 text-zinc-400 hover:bg-white/[0.06] hover:text-zinc-200'
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          {/* Content */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="article-content" className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
                Content <span className="text-orange-400">*</span>
              </Label>
              <div className="flex items-center gap-2 text-[10px] text-zinc-600">
                {category !== 'general' && (
                  <span className="inline-flex items-center gap-1 text-violet-400">
                    <Sparkles className="w-3 h-3" />
                    Template loaded
                  </span>
                )}
                <span>{wordCount} words · {charCount} chars</span>
              </div>
            </div>
            <Textarea
              id="article-content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Write your article content here...&#10;&#10;Example:&#10;ORDER TRACKING:&#10;All orders ship within 1-2 business days. You'll receive a tracking number via email.&#10;&#10;REFUND POLICY:&#10;Full refunds within 30 days of delivery."
              className="bg-white/[0.03] border-white/10 text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:ring-orange-500/20 min-h-[260px] font-mono text-[13px] leading-relaxed resize-y"
              maxLength={50000}
            />
            <p className="text-[10px] text-zinc-600">
              Tip: Use clear headings (ALL CAPS) and short paragraphs. The AI reads this to answer customer tickets.
            </p>
          </div>
        </div>

        <DialogFooter className="px-6 py-4 border-t border-white/[0.06] flex items-center justify-between gap-3">
          <div className="text-[10px] text-zinc-600">
            {isSaving ? 'Saving to knowledge base...' : 'Article is processed instantly and available to the AI pipeline.'}
          </div>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={isSaving}
              className="text-zinc-400 hover:text-white hover:bg-white/5"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={isSaving || !title.trim() || content.trim().length < 10}
              className="bg-orange-500 hover:bg-orange-600 text-white gap-2 min-w-[120px]"
            >
              {isSaving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <FilePlus2 className="w-4 h-4" />
                  Create Article
                </>
              )}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
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
  const [createArticleOpen, setCreateArticleOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Load documents ────────────────────────────────────────────────────
  const reloadDocuments = useCallback(async () => {
    try {
      const data = await knowledgeApi.list();
      if (Array.isArray(data) && data.length > 0) {
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
      // API not available
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => { reloadDocuments(); }, 600);
    return () => clearTimeout(timer);
  }, [reloadDocuments]);

  // ── Manual refresh (shows spinner + toast) ───────────────────────────
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await reloadDocuments();
    setIsRefreshing(false);
    toast.success('Knowledge base refreshed');
  }, [reloadDocuments]);

  // ── Auto-poll while any document is still processing ─────────────────
  const hasProcessing = documents.some((d) => d.status === 'processing' || d.status === 'indexing');
  useEffect(() => {
    if (!hasProcessing) return;
    const interval = setInterval(() => { reloadDocuments(); }, 10000); // poll every 10s
    return () => clearInterval(interval);
  }, [hasProcessing, reloadDocuments]);

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
        setDocuments((prev) =>
          prev.map((d) =>
            d.id === tempId ? { ...d, status: 'failed' as const } : d
          )
        );
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
      // Status check failed — leave current status as-is
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
      <div className="pb-6 border-b border-white/[0.06] flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">Knowledge Base</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Manage your knowledge sources and AI training data
          </p>
        </div>
        <Button
          onClick={handleRefresh}
          disabled={isRefreshing}
          variant="outline"
          size="sm"
          className="border-white/10 bg-white/[0.02] hover:bg-white/[0.06] text-zinc-200 gap-1.5 h-9 shrink-0"
        >
          {isRefreshing ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RefreshCw className="w-3.5 h-3.5" />
          )}
          <span className="hidden sm:inline">Refresh</span>
        </Button>
      </div>

      {/* Processing banner — shows when any document is still processing */}
      {hasProcessing && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-500/[0.06] border border-amber-500/15">
          <div className="relative w-5 h-5 shrink-0">
            <Loader2 className="w-5 h-5 text-amber-400 animate-spin" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-amber-200">
              Processing documents…
            </p>
            <p className="text-xs text-amber-200/60 mt-0.5">
              The AI is reading and indexing your content. This usually takes 1-3 minutes. The page updates automatically.
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] font-medium text-amber-300/80 px-2 py-1 rounded-md bg-amber-500/10">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            LIVE
          </div>
        </div>
      )}

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
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-medium text-white">Upload Documents</h2>
          <Button
            onClick={() => setCreateArticleOpen(true)}
            variant="outline"
            size="sm"
            className="border-white/10 bg-white/[0.02] hover:bg-white/[0.06] text-zinc-200 gap-1.5 h-8 text-xs"
          >
            <PenLine className="w-3.5 h-3.5" />
            Write Article
          </Button>
        </div>

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
          onCreateClick={() => setCreateArticleOpen(true)}
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

      {/* Create Article Dialog */}
      <CreateArticleDialog
        open={createArticleOpen}
        onOpenChange={setCreateArticleOpen}
        onSuccess={reloadDocuments}
      />
    </div>
  );
}
