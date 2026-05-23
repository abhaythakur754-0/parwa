/**
 * PARWA ConnectionErrorCard (Integration Setup)
 *
 * Dedicated error card with troubleshooting steps for failed integrations.
 * Shows common fixes, retry, support link, and skip option.
 * Rendered inline in the Jarvis chat stream during onboarding.
 */

'use client';

import {
  AlertTriangle, RefreshCw, ExternalLink,
  SkipForward, Wrench, ChevronDown, ChevronUp,
} from 'lucide-react';
import { useState } from 'react';

// ── Types ──────────────────────────────────────────────────────────

export interface ConnectionErrorCardProps {
  errorMessage: string;
  commonFixes?: string[];
  onRetry: () => void;
  onContactSupport?: () => void;
  supportUrl?: string;
  onSkip: () => void;
}

// ── Default common fixes by error type ─────────────────────────────

const DEFAULT_FIXES = [
  'Check if your API key has the correct permissions',
  'Verify the key is for production, not sandbox/test mode',
  'Ensure your account is active and in good standing',
  'Check if IP allowlisting is required for your provider',
  'Try regenerating a new API key from your provider dashboard',
];

// ── Component ──────────────────────────────────────────────────────

export function ConnectionErrorCard({
  errorMessage,
  commonFixes,
  onRetry,
  onContactSupport,
  supportUrl,
  onSkip,
}: ConnectionErrorCardProps) {
  const [showFixes, setShowFixes] = useState(false);
  const fixes = commonFixes && commonFixes.length > 0 ? commonFixes : DEFAULT_FIXES;

  return (
    <div className="glass rounded-xl p-4 border border-red-500/15 max-w-sm w-full">
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-3">
        <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
          <AlertTriangle className="w-4 h-4 text-red-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-red-200">Connection Error</h3>
          <p className="text-[10px] text-white/35">We couldn&apos;t connect to your provider</p>
        </div>
      </div>

      {/* Error message */}
      <div className="p-2.5 rounded-lg bg-red-500/5 border border-red-500/10 mb-3">
        <p className="text-[11px] text-red-200/80 leading-relaxed">{errorMessage}</p>
      </div>

      {/* Common fixes (collapsible) */}
      <div className="mb-3">
        <button
          onClick={() => setShowFixes(!showFixes)}
          className="w-full flex items-center justify-between gap-2 py-1.5 text-left group"
        >
          <div className="flex items-center gap-1.5">
            <Wrench className="w-3 h-3 text-amber-400/60" />
            <span className="text-[11px] text-white/50 group-hover:text-white/70 transition-colors">
              Common fixes ({fixes.length})
            </span>
          </div>
          {showFixes ? (
            <ChevronUp className="w-3 h-3 text-white/30" />
          ) : (
            <ChevronDown className="w-3 h-3 text-white/30" />
          )}
        </button>

        {showFixes && (
          <div className="mt-1.5 space-y-1.5 pl-1">
            {fixes.map((fix, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="text-[9px] text-amber-400/50 mt-0.5 shrink-0">{i + 1}.</span>
                <span className="text-[11px] text-white/45 leading-relaxed">{fix}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="space-y-2">
        <button
          onClick={onRetry}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 text-white text-xs font-medium hover:from-amber-400 hover:to-amber-500 transition-all active:scale-[0.98]"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Try Again
        </button>

        {/* Contact support */}
        {(onContactSupport || supportUrl) && (
          <button
            onClick={onContactSupport}
            className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/40 text-xs hover:bg-white/[0.06] hover:text-white/60 transition-all"
          >
            <ExternalLink className="w-3 h-3" />
            Contact Support
          </button>
        )}

        {/* Skip */}
        <button
          onClick={onSkip}
          className="w-full flex items-center justify-center gap-1.5 text-[11px] text-white/30 hover:text-white/50 transition-colors py-1"
        >
          <SkipForward className="w-3 h-3" />
          Skip for now
        </button>
      </div>
    </div>
  );
}
