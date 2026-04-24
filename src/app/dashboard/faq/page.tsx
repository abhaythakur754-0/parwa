'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';

// ── Types ────────────────────────────────────────────────────────────────

interface FAQ {
  id: string;
  question: string;
  answer: string;
  category: string;
  keywords: string[];
  created_at?: string;
  updated_at?: string;
}

interface FAQListResponse {
  faqs: FAQ[];
  total: number;
  categories: string[];
}

// ── Inline Icons ────────────────────────────────────────────────────────

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
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

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
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

function BookOpenIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
    </svg>
  );
}

function ArrowDownTrayIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
    </svg>
  );
}

// ── Skeleton ─────────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/[0.06]', className)} />;
}

// ── Components ────────────────────────────────────────────────────────────

function FAQCard({
  faq,
  onEdit,
  onDelete,
}: {
  faq: FAQ;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5 hover:border-white/[0.1] transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center rounded-full bg-[#FF7F11]/15 px-2.5 py-0.5 text-xs font-medium text-[#FF7F11]">
              {faq.category}
            </span>
          </div>
          <h3 className="text-white font-medium mb-2">{faq.question}</h3>
          <p className="text-sm text-zinc-400 leading-relaxed">{faq.answer}</p>
          {faq.keywords && faq.keywords.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {faq.keywords.map((kw, idx) => (
                <span
                  key={idx}
                  className="text-xs text-zinc-500 bg-white/[0.03] px-2 py-0.5 rounded"
                >
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onEdit}
            className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <PencilIcon className="w-4 h-4" />
          </button>
          <button
            onClick={onDelete}
            className="p-2 rounded-lg text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <TrashIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function FAQModal({
  isOpen,
  onClose,
  faq,
  categories,
  onSave,
}: {
  isOpen: boolean;
  onClose: () => void;
  faq: FAQ | null;
  categories: string[];
  onSave: (data: { question: string; answer: string; category: string; keywords: string[] }) => void;
}) {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [category, setCategory] = useState('General');
  const [keywords, setKeywords] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (faq) {
      setQuestion(faq.question);
      setAnswer(faq.answer);
      setCategory(faq.category);
      setKeywords(faq.keywords?.join(', ') || '');
    } else {
      setQuestion('');
      setAnswer('');
      setCategory('General');
      setKeywords('');
    }
  }, [faq, isOpen]);

  const handleSubmit = async () => {
    if (!question.trim() || !answer.trim()) {
      toast.error('Question and answer are required');
      return;
    }

    setLoading(true);
    try {
      await onSave({
        question: question.trim(),
        answer: answer.trim(),
        category: category.trim() || 'General',
        keywords: keywords.split(',').map(k => k.trim()).filter(Boolean),
      });
      onClose();
    } catch (error) {
      console.error('Failed to save FAQ:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-[#1A1A1A] rounded-2xl border border-white/[0.08] p-6">
        <h2 className="text-xl font-bold text-white mb-4">
          {faq ? 'Edit FAQ' : 'Add New FAQ'}
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-zinc-400 mb-1.5">Question</label>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="w-full rounded-xl bg-[#141414] border border-white/[0.06] px-4 py-2.5 text-white placeholder-zinc-500 focus:border-[#FF7F11]/50 focus:outline-none"
              placeholder="Enter the question"
            />
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1.5">Answer</label>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              rows={4}
              className="w-full rounded-xl bg-[#141414] border border-white/[0.06] px-4 py-2.5 text-white placeholder-zinc-500 focus:border-[#FF7F11]/50 focus:outline-none resize-none"
              placeholder="Enter the answer"
            />
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1.5">Category</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="flex-1 rounded-xl bg-[#141414] border border-white/[0.06] px-4 py-2.5 text-white placeholder-zinc-500 focus:border-[#FF7F11]/50 focus:outline-none"
                placeholder="Category name"
              />
              {categories.length > 0 && (
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="rounded-xl bg-[#141414] border border-white/[0.06] px-3 py-2.5 text-white focus:border-[#FF7F11]/50 focus:outline-none"
                >
                  <option value="">Select...</option>
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1.5">
              Keywords <span className="text-zinc-500">(comma-separated)</span>
            </label>
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              className="w-full rounded-xl bg-[#141414] border border-white/[0.06] px-4 py-2.5 text-white placeholder-zinc-500 focus:border-[#FF7F11]/50 focus:outline-none"
              placeholder="password, reset, login"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-5 py-2 rounded-xl text-sm font-medium bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90 transition-colors disabled:opacity-50"
          >
            {loading ? 'Saving...' : faq ? 'Update' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────

export default function FAQPage() {
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingFaq, setEditingFaq] = useState<FAQ | null>(null);

  const loadFaqs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (selectedCategory) params.append('category', selectedCategory);
      
      const response = await fetch(`/api/v1/faqs?${params.toString()}`, {
        credentials: 'include',
      });

      if (!response.ok) throw new Error('Failed to load FAQs');

      const data: FAQListResponse = await response.json();
      setFaqs(data.faqs);
      setCategories(data.categories);
    } catch (error) {
      console.error('Failed to load FAQs:', error);
      toast.error('Failed to load FAQs');
    } finally {
      setLoading(false);
    }
  }, [search, selectedCategory]);

  useEffect(() => {
    loadFaqs();
  }, [loadFaqs]);

  const handleCreate = () => {
    setEditingFaq(null);
    setModalOpen(true);
  };

  const handleEdit = (faq: FAQ) => {
    setEditingFaq(faq);
    setModalOpen(true);
  };

  const handleDelete = async (faq: FAQ) => {
    if (!confirm(`Delete "${faq.question}"?`)) return;

    try {
      const response = await fetch(`/api/v1/faqs/${faq.id}`, {
        method: 'DELETE',
        credentials: 'include',
      });

      if (!response.ok) throw new Error('Failed to delete FAQ');

      toast.success('FAQ deleted');
      loadFaqs();
    } catch (error) {
      console.error('Failed to delete FAQ:', error);
      toast.error('Failed to delete FAQ');
    }
  };

  const handleSave = async (data: { question: string; answer: string; category: string; keywords: string[] }) => {
    const url = editingFaq ? `/api/v1/faqs/${editingFaq.id}` : '/api/v1/faqs';
    const method = editingFaq ? 'PUT' : 'POST';

    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data),
    });

    if (!response.ok) throw new Error('Failed to save FAQ');

    toast.success(editingFaq ? 'FAQ updated' : 'FAQ created');
    loadFaqs();
  };

  const handleExport = async () => {
    try {
      const response = await fetch('/api/v1/faqs/export', {
        credentials: 'include',
      });

      if (!response.ok) throw new Error('Failed to export FAQs');

      const data = await response.json();
      const blob = new Blob([data.data], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'faqs_export.json';
      a.click();
      URL.revokeObjectURL(url);

      toast.success('FAQs exported');
    } catch (error) {
      console.error('Failed to export FAQs:', error);
      toast.error('Failed to export FAQs');
    }
  };

  return (
    <div className="jarvis-page-body min-h-screen bg-[#0A0A0A]">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FF7F11]/10">
              <BookOpenIcon className="h-5 w-5 text-[#FF7F11]" />
            </div>
            <h1 className="text-2xl font-bold text-white">FAQ Management</h1>
          </div>
          <p className="text-sm text-zinc-500 ml-[52px]">
            Manage FAQs that AI uses for quick answers to common questions.
          </p>
        </div>

        {/* Toolbar */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          {/* Search */}
          <div className="relative flex-1">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search FAQs..."
              className="w-full rounded-xl bg-[#1A1A1A] border border-white/[0.06] pl-10 pr-4 py-2.5 text-white placeholder-zinc-500 focus:border-[#FF7F11]/50 focus:outline-none"
            />
          </div>

          {/* Category Filter */}
          {categories.length > 0 && (
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] px-4 py-2.5 text-white focus:border-[#FF7F11]/50 focus:outline-none"
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          )}

          {/* Actions */}
          <button
            onClick={handleExport}
            className="inline-flex items-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-sm text-zinc-300 hover:bg-white/[0.08] transition-colors"
          >
            <ArrowDownTrayIcon className="w-4 h-4" />
            Export
          </button>

          <button
            onClick={handleCreate}
            className="inline-flex items-center gap-2 rounded-xl bg-[#FF7F11] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
          >
            <PlusIcon className="w-4 h-4" />
            Add FAQ
          </button>
        </div>

        {/* FAQ List */}
        {loading ? (
          <div className="space-y-4">
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
          </div>
        ) : faqs.length === 0 ? (
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-12 text-center">
            <BookOpenIcon className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-zinc-300 mb-2">No FAQs Yet</h3>
            <p className="text-sm text-zinc-500 mb-6">
              Add FAQs to help AI provide quick answers to common questions.
            </p>
            <button
              onClick={handleCreate}
              className="inline-flex items-center gap-2 rounded-xl bg-[#FF7F11] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
            >
              <PlusIcon className="w-4 h-4" />
              Add Your First FAQ
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {faqs.map((faq) => (
              <FAQCard
                key={faq.id}
                faq={faq}
                onEdit={() => handleEdit(faq)}
                onDelete={() => handleDelete(faq)}
              />
            ))}
          </div>
        )}

        {/* Stats */}
        {!loading && faqs.length > 0 && (
          <div className="mt-6 text-center text-sm text-zinc-500">
            {faqs.length} FAQ{faqs.length !== 1 ? 's' : ''} in {categories.length} categories
          </div>
        )}
      </div>

      {/* Modal */}
      <FAQModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        faq={editingFaq}
        categories={categories}
        onSave={handleSave}
      />
    </div>
  );
}
