/**
 * ShadowModeStatusCard — Large status indicator for shadow mode state
 *
 * Shows the current phase (SHADOW / SUPERVISED / GRADUATED / DISABLED),
 * live vs shadow variant names, and quick action buttons.
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { ShadowModeStatus as ShadowModeStatusType, ShadowModeStatusType as StatusPhase } from '@/types/shadow-mode';

// ── Phase Configuration ─────────────────────────────────────────────

const phaseConfig: Record<StatusPhase, { label: string; color: string; bg: string; border: string; glow: string; description: string }> = {
  shadow: {
    label: 'SHADOW',
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/30',
    glow: 'shadow-purple-500/10',
    description: 'Shadow variant is processing sampled messages alongside live variant',
  },
  supervised: {
    label: 'SUPERVISED',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    glow: 'shadow-amber-500/10',
    description: 'Shadow variant responses require human review before delivery',
  },
  graduated: {
    label: 'GRADUATED',
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    glow: 'shadow-emerald-500/10',
    description: 'Shadow variant has been promoted to live — graduation complete!',
  },
  disabled: {
    label: 'DISABLED',
    color: 'text-zinc-500',
    bg: 'bg-zinc-500/5',
    border: 'border-zinc-500/20',
    glow: '',
    description: 'Shadow mode is not active. Enable it to start testing variants.',
  },
};

// ── Props ───────────────────────────────────────────────────────────

export interface ShadowModeStatusCardProps {
  status: ShadowModeStatusType | null;
  onEnable?: () => void;
  onDisable?: () => void;
  onPromote?: () => void;
  onGraduate?: () => void;
  isActionLoading?: boolean;
  className?: string;
}

// ── Component ───────────────────────────────────────────────────────

export function ShadowModeStatusCard({
  status,
  onEnable,
  onDisable,
  onPromote,
  onGraduate,
  isActionLoading,
  className,
}: ShadowModeStatusCardProps) {
  const phase = status?.status || 'disabled';
  const config = phaseConfig[phase];
  const isActive = status?.active ?? false;

  return (
    <div
      className={cn(
        'rounded-xl border p-6 transition-all duration-300',
        config.bg,
        config.border,
        isActive && `shadow-lg ${config.glow}`,
        className
      )}
    >
      {/* Phase Badge */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={cn(
            'w-12 h-12 rounded-xl flex items-center justify-center',
            config.bg,
            isActive ? 'animate-pulse' : ''
          )}>
            {phase === 'shadow' && (
              <svg className="w-6 h-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456Z" />
              </svg>
            )}
            {phase === 'supervised' && (
              <svg className="w-6 h-6 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0Z" />
              </svg>
            )}
            {phase === 'graduated' && (
              <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.746 3.746 0 011.043 3.296A3.745 3.745 0 0121 12Z" />
              </svg>
            )}
            {phase === 'disabled' && (
              <svg className="w-6 h-6 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
            )}
          </div>
          <div>
            <h2 className={cn('text-xl font-bold', config.color)}>{config.label}</h2>
            <p className="text-xs text-zinc-500 mt-0.5">{config.description}</p>
          </div>
        </div>

        {/* Active Indicator */}
        {isActive && (
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-emerald-400 font-medium">Active</span>
          </div>
        )}
      </div>

      {/* Variant Comparison */}
      {isActive && status && (
        <div className="flex items-center gap-4 mt-4 pt-4 border-t border-white/[0.06]">
          <div className="flex-1 text-center">
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Live Variant</p>
            <p className="text-sm font-semibold text-white">{status.live_variant}</p>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-zinc-600 text-lg">VS</span>
          </div>
          <div className="flex-1 text-center">
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Shadow Variant</p>
            <p className="text-sm font-semibold text-purple-400">{status.shadow_variant}</p>
          </div>
        </div>
      )}

      {/* Progress to Next Phase */}
      {isActive && status && phase !== 'graduated' && (
        <div className="mt-4 pt-4 border-t border-white/[0.06]">
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-zinc-500">Auto-graduation progress</span>
            <span className="text-zinc-300 font-medium">
              {Math.round(status.auto_graduation_progress * 100)}%
            </span>
          </div>
          <div className="h-2 bg-white/5 rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-700',
                status.auto_graduation_progress >= 0.9
                  ? 'bg-gradient-to-r from-emerald-500 to-emerald-400'
                  : status.auto_graduation_progress >= 0.5
                  ? 'bg-gradient-to-r from-amber-500 to-orange-400'
                  : 'bg-gradient-to-r from-purple-500 to-purple-400'
              )}
              style={{ width: `${Math.min(status.auto_graduation_progress * 100, 100)}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-[10px] text-zinc-600 mt-1">
            <span>Quality streak: {status.quality_streak}</span>
            <span>Required: {status.auto_graduation_window}</span>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-white/[0.06]">
        {!isActive && onEnable && (
          <button
            onClick={onEnable}
            disabled={isActionLoading}
            className="flex-1 text-sm px-4 py-2.5 rounded-lg bg-gradient-to-r from-purple-500 to-purple-400 text-white font-medium shadow-lg shadow-purple-500/20 hover:shadow-purple-500/30 transition-all disabled:opacity-50"
          >
            Enable Shadow Mode
          </button>
        )}
        {isActive && phase === 'shadow' && onPromote && (
          <button
            onClick={onPromote}
            disabled={isActionLoading}
            className="flex-1 text-sm px-4 py-2.5 rounded-lg bg-amber-500/10 text-amber-400 font-medium hover:bg-amber-500/20 transition-all disabled:opacity-50"
          >
            Promote to Supervised
          </button>
        )}
        {isActive && phase === 'supervised' && onGraduate && (
          <button
            onClick={onGraduate}
            disabled={isActionLoading}
            className="flex-1 text-sm px-4 py-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 font-medium hover:bg-emerald-500/20 transition-all disabled:opacity-50"
          >
            Complete Graduation
          </button>
        )}
        {isActive && onDisable && (
          <button
            onClick={onDisable}
            disabled={isActionLoading}
            className="text-sm px-4 py-2.5 rounded-lg bg-red-500/10 text-red-400 font-medium hover:bg-red-500/20 transition-all disabled:opacity-50"
          >
            Disable
          </button>
        )}
      </div>
    </div>
  );
}
