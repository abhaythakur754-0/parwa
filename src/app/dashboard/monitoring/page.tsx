'use client';

import React from 'react';

// ── Icons ──────────────────────────────────────────────────────────────

const LightningIcon = () => (
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
      d="m3.75 13.5 10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75Z"
    />
  </svg>
);

// ── Monitoring Page ────────────────────────────────────────────────────

export default function MonitoringPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">Monitoring</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Real-time system health and performance monitoring
        </p>
      </div>

      {/* Coming Soon Card */}
      <div className="flex flex-col items-center justify-center py-20 bg-[#1A1A1A] rounded-xl border border-white/[0.06]">
        <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center mb-4">
          <LightningIcon />
        </div>
        <h3 className="text-lg font-medium text-white mb-2">Monitoring</h3>
        <p className="text-sm text-zinc-500 mb-6">
          Connect your backend to view monitoring data
        </p>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
          <span className="text-xs text-zinc-500">Coming Soon</span>
        </div>
      </div>
    </div>
  );
}
