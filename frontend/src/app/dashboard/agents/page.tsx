'use client';

import React from 'react';
import Link from 'next/link';

export default function AgentsPage() {
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
              d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-zinc-200">Agents</h2>
        <p className="text-sm text-zinc-500 max-w-xs mx-auto">
          AI agent management, configuration, performance monitoring, and status overview.
        </p>
        <span className="inline-block rounded-full bg-[#FF7F11]/10 px-3 py-1 text-xs font-medium text-[#FF7F11]">
          Planned for Day 5
        </span>
        <p className="text-xs text-zinc-600">
          This page is coming in Day 5 of the dashboard build.
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
