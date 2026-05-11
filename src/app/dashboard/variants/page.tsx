'use client';

import React from 'react';

// ── Icons ──────────────────────────────────────────────────────────────

const ChipIcon = () => (
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
      d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5M4.5 15.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Zm.75-12h9v9h-9v-9Z"
    />
  </svg>
);

// ── Variants Page ──────────────────────────────────────────────────────

export default function VariantsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">Variant Engine</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Configure and monitor your AI variant instances
        </p>
      </div>

      {/* Coming Soon Card */}
      <div className="flex flex-col items-center justify-center py-20 bg-[#1A1A1A] rounded-xl border border-white/[0.06]">
        <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center mb-4">
          <ChipIcon />
        </div>
        <h3 className="text-lg font-medium text-white mb-2">Variant Engine</h3>
        <p className="text-sm text-zinc-500 mb-6">
          Connect your backend to view variant data
        </p>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
          <span className="text-xs text-zinc-500">Coming Soon</span>
        </div>
      </div>
    </div>
  );
}
