'use client';

import React from 'react';
import Link from 'next/link';

export default function ApprovalsPage() {
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
              d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-zinc-200">Approvals</h2>
        <p className="text-sm text-zinc-500 max-w-xs mx-auto">
          Review and approve pending actions, agent decisions, and workflow escalations.
        </p>
        <span className="inline-block rounded-full bg-[#FF7F11]/10 px-3 py-1 text-xs font-medium text-[#FF7F11]">
          Planned for Day 6
        </span>
        <p className="text-xs text-zinc-600">
          This page is coming in Day 6 of the dashboard build.
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
