'use client';

import React from 'react';
import Link from 'next/link';

export default function TicketsPage() {
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
              d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125V6.375c0-.621-.504-1.125-1.125-1.125H3.375z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-zinc-200">Tickets</h2>
        <p className="text-sm text-zinc-500 max-w-xs mx-auto">
          Support ticket management, tracking, and resolution workflows.
        </p>
        <span className="inline-block rounded-full bg-[#FF7F11]/10 px-3 py-1 text-xs font-medium text-[#FF7F11]">
          Planned for Day 3
        </span>
        <p className="text-xs text-zinc-600">
          This page is coming in Day 3 of the dashboard build.
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
