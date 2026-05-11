'use client';

import React from 'react';

// ── Icons ──────────────────────────────────────────────────────────────

const CreditCardIcon = () => (
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
      d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Z"
    />
  </svg>
);

// ── Billing Page ───────────────────────────────────────────────────────

export default function BillingPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">Billing</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Manage your subscription, invoices, and payment methods
        </p>
      </div>

      {/* Coming Soon Card */}
      <div className="flex flex-col items-center justify-center py-20 bg-[#1A1A1A] rounded-xl border border-white/[0.06]">
        <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center mb-4">
          <CreditCardIcon />
        </div>
        <h3 className="text-lg font-medium text-white mb-2">Billing</h3>
        <p className="text-sm text-zinc-500 mb-6">
          Connect your backend to view billing data
        </p>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
          <span className="text-xs text-zinc-500">Coming Soon</span>
        </div>
      </div>
    </div>
  );
}
