'use client';

import React from 'react';
import Link from 'next/link';

export default function BillingPage() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center space-y-4">
        <div className="mx-auto w-16 h-16 rounded-2xl bg-[#FF7F11]/10 flex items-center justify-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="w-8 h-8 text-[#FF7F11]"
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
        </div>
        <h2 className="text-xl font-semibold text-zinc-200">Billing</h2>
        <p className="text-sm text-zinc-500 max-w-xs mx-auto">
          Subscription plans, invoices, usage tracking, and payment method management.
        </p>
        <span className="inline-block rounded-full bg-[#FF7F11]/10 px-3 py-1 text-xs font-medium text-[#FF7F11]">
          Under Construction
        </span>
        <p className="text-xs text-zinc-600">
          The billing page is built but being integrated into the dashboard layout.
        </p>
        <Link
          href="/dashboard"
          className="inline-block text-sm text-[#FF7F11] hover:underline transition-colors"
        >
          &larr; Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
