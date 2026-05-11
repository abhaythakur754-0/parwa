'use client';

import React from 'react';

// ── Icons ──────────────────────────────────────────────────────────────

const BookIcon = () => (
  <svg
    className="w-6 h-6 text-orange-400"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
    />
  </svg>
);

// ── Knowledge Page ─────────────────────────────────────────────────────

export default function KnowledgePage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">Knowledge Base</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Manage your knowledge sources and AI training data
        </p>
      </div>

      {/* Coming Soon Card */}
      <div className="flex flex-col items-center justify-center py-20 bg-[#1A1A1A] rounded-xl border border-white/[0.06]">
        <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center mb-4">
          <BookIcon />
        </div>
        <h3 className="text-lg font-medium text-white mb-2">Knowledge Base</h3>
        <p className="text-sm text-zinc-500 mb-6">
          Connect your backend to view knowledge data
        </p>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
          <span className="text-xs text-zinc-500">Coming Soon</span>
        </div>
      </div>
    </div>
  );
}
