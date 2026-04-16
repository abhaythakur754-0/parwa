'use client';

import React from 'react';
import Link from 'next/link';

export default function TicketDetailPage() {
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
              d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Zm3.75 11.625a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-zinc-200">Ticket Detail</h2>
        <p className="text-sm text-zinc-500 max-w-xs mx-auto">
          Individual ticket view with conversation history, notes, and resolution actions.
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
