/**
 * PARWA ConnectionStatusCard (Integration Setup)
 *
 * Shows connection status after testing a provider integration.
 * States: disconnected → connecting → connected | error
 * Includes disconnect and retry actions.
 * Rendered inline in the Jarvis chat stream during onboarding.
 */

'use client';

import {
  CheckCircle2, XCircle, Loader2, Unplug,
  RefreshCw, AlertTriangle, ShieldOff,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────

export interface ConnectionStatusCardProps {
  providerName: string;
  status: 'disconnected' | 'connecting' | 'connected' | 'error';
  errorMessage?: string;
  troubleshootingSteps?: string[];
  onDisconnect: () => void;
  onRetry: () => void;
}

// ── Component ──────────────────────────────────────────────────────

export function ConnectionStatusCard({
  providerName,
  status,
  errorMessage,
  troubleshootingSteps,
  onDisconnect,
  onRetry,
}: ConnectionStatusCardProps) {
  // ── Connected ─────────────────────────────────────────────────
  if (status === 'connected') {
    return (
      <div className="glass rounded-xl p-4 border border-emerald-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2.5 mb-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-emerald-200">Connected</h3>
            <p className="text-[10px] text-white/40 truncate">{providerName}</p>
          </div>
          <span className="text-[9px] font-medium px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/15">
            Active
          </span>
        </div>

        <p className="text-[11px] text-white/40 mb-3">
          Your {providerName} integration is active and ready to use.
        </p>

        <button
          onClick={onDisconnect}
          className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/40 text-xs hover:bg-red-500/10 hover:text-red-300 hover:border-red-500/15 transition-all"
        >
          <Unplug className="w-3 h-3" />
          Disconnect
        </button>
      </div>
    );
  }

  // ── Connecting (spinner) ──────────────────────────────────────
  if (status === 'connecting') {
    return (
      <div className="glass rounded-xl p-4 border border-violet-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center">
            <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Connecting...</h3>
            <p className="text-[10px] text-white/40">Establishing connection to {providerName}</p>
          </div>
        </div>

        {/* Animated progress bar */}
        <div className="h-1 w-full rounded-full bg-white/5 overflow-hidden">
          <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-violet-400 animate-pulse-bar" style={{ width: '60%' }} />
        </div>

        <style jsx>{`
          @keyframes pulse-bar {
            0%, 100% { opacity: 0.5; transform: translateX(0); }
            50% { opacity: 1; transform: translateX(30%); }
          }
          .animate-pulse-bar {
            animation: pulse-bar 1.5s ease-in-out infinite;
          }
        `}</style>
      </div>
    );
  }

  // ── Error ─────────────────────────────────────────────────────
  if (status === 'error') {
    return (
      <div className="glass rounded-xl p-4 border border-red-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2.5 mb-2">
          <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
            <XCircle className="w-4 h-4 text-red-400" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-red-200">Connection Failed</h3>
            <p className="text-[10px] text-white/40 truncate">{providerName}</p>
          </div>
        </div>

        {/* Error message */}
        {errorMessage && (
          <div className="flex items-start gap-1.5 mb-3 p-2 rounded-lg bg-red-500/5 border border-red-500/10">
            <AlertTriangle className="w-3 h-3 text-red-400/70 mt-0.5 shrink-0" />
            <p className="text-[11px] text-red-200/80">{errorMessage}</p>
          </div>
        )}

        {/* Troubleshooting steps */}
        {troubleshootingSteps && troubleshootingSteps.length > 0 && (
          <div className="mb-3">
            <p className="text-[10px] text-white/30 uppercase tracking-wider mb-1.5">Troubleshooting</p>
            <div className="space-y-1">
              {troubleshootingSteps.map((step, i) => (
                <div key={i} className="flex items-start gap-1.5 px-1">
                  <span className="text-[9px] text-white/20 mt-0.5 shrink-0">{i + 1}.</span>
                  <span className="text-[10px] text-white/40">{step}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={onRetry}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-gradient-to-r from-violet-500 to-violet-600 text-white text-xs font-medium hover:from-violet-400 hover:to-violet-500 transition-all active:scale-[0.98]"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </button>
          <button
            onClick={onDisconnect}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/40 text-xs hover:bg-red-500/10 hover:text-red-300 hover:border-red-500/15 transition-all"
          >
            <ShieldOff className="w-3 h-3" />
            Cancel
          </button>
        </div>
      </div>
    );
  }

  // ── Disconnected (default) ────────────────────────────────────
  return (
    <div className="glass rounded-xl p-4 border border-white/[0.06] max-w-sm w-full">
      <div className="flex items-center gap-2.5 mb-2">
        <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center">
          <Unplug className="w-4 h-4 text-white/30" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white/50">Not Connected</h3>
          <p className="text-[10px] text-white/30 truncate">{providerName}</p>
        </div>
      </div>

      <p className="text-[11px] text-white/30 mb-3">
        Set up your {providerName} integration to get started.
      </p>

      <button
        onClick={onRetry}
        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gradient-to-r from-violet-500 to-violet-600 text-white text-xs font-medium hover:from-violet-400 hover:to-violet-500 transition-all active:scale-[0.98]"
      >
        Connect Now
      </button>
    </div>
  );
}
