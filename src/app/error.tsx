'use client';

import React from 'react';

/**
 * Root Error Boundary
 *
 * Catches runtime errors anywhere in the app and shows a
 * friendly error message instead of the default Next.js page.
 */
export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  console.error('[RootError]', error);

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}>
      <div className="max-w-md w-full mx-auto p-8 text-center">
        <div className="w-16 h-16 rounded-full bg-red-500/15 border border-red-500/25 flex items-center justify-center mx-auto mb-6">
          <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-white mb-3">Something went wrong</h1>
        <p className="text-orange-200/60 text-sm mb-2">An unexpected error occurred.</p>
        <p className="text-orange-200/40 text-xs mb-6 max-w-sm mx-auto break-words">{error?.message || 'Unknown error'}</p>
        <button
          onClick={reset}
          className="px-6 py-2.5 bg-gradient-to-r from-orange-500 to-orange-400 text-[#1A1A1A] font-semibold rounded-xl hover:from-orange-400 hover:to-orange-300 transition-all shadow-lg shadow-orange-500/20"
        >
          Try Again
        </button>
      </div>
    </div>
  );
}
