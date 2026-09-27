/**
 * PARWA ErrorBanner Component (Week 6 — Day 3 Phase 5)
 *
 * Dismissible error banner for chat API failures.
 * Displays a red-tinted alert with icon, message text, and close button.
 * Supports optional retry callback.
 */

'use client';

import { AlertCircle, RefreshCw, X } from 'lucide-react';

interface ErrorBannerProps {
  /** Error message to display (null/empty hides the banner) */
  error: string | null;
  /** Callback to dismiss the banner */
  onDismiss: () => void;
  /** Optional callback to retry the failed action */
  onRetry?: () => void;
}

export function ErrorBanner({ error, onDismiss, onRetry }: ErrorBannerProps) {
  if (!error) return null;

  return (
    <div className="mx-4 mt-3 flex items-start gap-2.5 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-200 text-sm animate-fade-in backdrop-blur-sm">
      <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-red-400" />

      <p className="flex-1 text-[13px] leading-relaxed">{error}</p>

      <div className="flex items-center gap-1 shrink-0">
        {onRetry && (
          <button
            onClick={onRetry}
            className="hover:bg-red-500/20 rounded-lg p-1 transition-colors"
            title="Retry"
            aria-label="Retry failed action"
          >
            <RefreshCw className="w-3.5 h-3.5 text-red-300" />
          </button>
        )}

        <button
          onClick={onDismiss}
          className="hover:bg-red-500/20 rounded-lg p-1 transition-colors"
          title="Dismiss"
          aria-label="Dismiss error"
        >
          <X className="w-3.5 h-3.5 text-red-300" />
        </button>
      </div>
    </div>
  );
}
