'use client';

import React from 'react';
import { Button } from '@/components/ui/button';

export default function DashboardErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#1A1A1A] border border-white/[0.06] rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center shrink-0">
            <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">Something went wrong</h2>
            <p className="text-xs text-zinc-500 mt-0.5">{error.message || 'An unexpected error occurred'}</p>
          </div>
        </div>
        {error.digest && (
          <p className="text-[10px] text-zinc-600 font-mono">Error ID: {error.digest}</p>
        )}
        <Button
          onClick={reset}
          className="w-full text-xs bg-blue-500 text-white hover:bg-blue-600 rounded-lg"
        >
          Try Again
        </Button>
      </div>
    </main>
  );
}
