/**
 * Shadow Mode Dashboard Page (/dashboard/shadow-mode)
 *
 * Full shadow mode management UI with:
 *  - Status indicator and phase progression
 *  - Key metrics grid
 *  - Comparison history with human review
 *  - Enable/disable/configure controls
 *  - Integration with Jarvis CC quick actions
 */

'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { useShadowMode } from '@/hooks/useShadowMode';
import { ShadowModeStatusCard } from '@/components/shadow-mode/ShadowModeStatusCard';
import { ComparisonTable } from '@/components/shadow-mode/ComparisonTable';
import { EnableShadowModeDialog } from '@/components/shadow-mode/EnableShadowModeDialog';
import { ShadowModeMetricsGrid } from '@/components/shadow-mode/ShadowModeMetricsGrid';
import { toast } from 'sonner';
import type { EnableShadowModeRequest, HumanVerdict } from '@/types/shadow-mode';

// ── Phase Progress Steps ────────────────────────────────────────────

const phaseSteps = [
  { key: 'shadow', label: 'Shadow', description: 'Silent comparison' },
  { key: 'supervised', label: 'Supervised', description: 'Human review required' },
  { key: 'graduated', label: 'Graduated', description: 'Variant promoted to live' },
];

// ── Page Component ──────────────────────────────────────────────────

export default function ShadowModePage() {
  const {
    status,
    statistics,
    comparisons,
    isLoading,
    isActionLoading,
    error,
    enableShadowMode,
    disableShadowMode,
    promoteShadowMode,
    graduateShadowMode,
    submitReview,
    refreshAll,
  } = useShadowMode(15000); // Auto-refresh every 15s

  const [isEnableDialogOpen, setIsEnableDialogOpen] = useState(false);
  const [isDisableConfirmOpen, setIsDisableConfirmOpen] = useState(false);

  const currentPhase = status?.status || 'disabled';
  const isActive = status?.active ?? false;

  // ── Handlers ──────────────────────────────────────────────────────

  const handleEnable = async (data: EnableShadowModeRequest): Promise<boolean> => {
    const success = await enableShadowMode(data);
    if (success) {
      toast.success('Shadow Mode Enabled', {
        description: `Testing ${data.shadow_variant} against ${data.live_variant}`,
      });
    } else {
      toast.error('Failed to Enable', {
        description: error || 'Could not enable shadow mode',
      });
    }
    return success;
  };

  const handleDisable = async () => {
    const success = await disableShadowMode('Disabled by user from dashboard');
    if (success) {
      toast.success('Shadow Mode Disabled');
      setIsDisableConfirmOpen(false);
    } else {
      toast.error('Failed to Disable', { description: error || 'Could not disable shadow mode' });
    }
  };

  const handlePromote = async () => {
    const success = await promoteShadowMode();
    if (success) {
      toast.success('Shadow Mode Promoted', {
        description: `Now in ${currentPhase === 'shadow' ? 'Supervised' : 'Graduated'} phase`,
      });
    } else {
      toast.error('Failed to Promote', { description: error || 'Could not promote shadow mode' });
    }
  };

  const handleGraduate = async () => {
    const success = await graduateShadowMode();
    if (success) {
      toast.success('Graduation Complete!', {
        description: 'Shadow variant is now the live variant',
      });
    } else {
      toast.error('Failed to Graduate', { description: error || 'Could not complete graduation' });
    }
  };

  const handleReview = async (resultId: string, verdict: HumanVerdict, notes: string) => {
    const success = await submitReview({ result_id: resultId, verdict, notes });
    if (success) {
      toast.success('Review Submitted', {
        description: `Verdict: ${verdict.replace('_', ' ')}`,
      });
    } else {
      toast.error('Failed to Submit Review');
    }
  };

  // ── Compute Phase Step Index ──────────────────────────────────────

  const currentStepIndex = currentPhase === 'disabled' ? -1 : phaseSteps.findIndex(s => s.key === currentPhase);

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <svg className="w-6 h-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456Z" />
            </svg>
            Shadow Mode
          </h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Safely test new AI variants against your live variant before promoting
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refreshAll()}
            disabled={isLoading}
            className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Loading...' : 'Refresh'}
          </button>
          {!isActive && (
            <button
              onClick={() => setIsEnableDialogOpen(true)}
              className="text-xs px-4 py-1.5 rounded-lg bg-gradient-to-r from-purple-500 to-purple-400 text-white font-medium shadow-lg shadow-purple-500/20 hover:shadow-purple-500/30 transition-all"
            >
              Enable Shadow Mode
            </button>
          )}
        </div>
      </div>

      {/* Phase Progress Stepper */}
      {isActive && (
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
          <div className="flex items-center justify-between">
            {phaseSteps.map((step, index) => {
              const isCompleted = currentStepIndex > index;
              const isCurrent = currentStepIndex === index;

              return (
                <React.Fragment key={step.key}>
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all',
                        isCompleted
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : isCurrent
                          ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30 animate-pulse'
                          : 'bg-zinc-800 text-zinc-600 border border-zinc-700'
                      )}
                    >
                      {isCompleted ? (
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                        </svg>
                      ) : (
                        index + 1
                      )}
                    </div>
                    <div>
                      <p className={cn(
                        'text-sm font-medium',
                        isCompleted ? 'text-emerald-400' : isCurrent ? 'text-purple-400' : 'text-zinc-600'
                      )}>
                        {step.label}
                      </p>
                      <p className="text-[10px] text-zinc-600">{step.description}</p>
                    </div>
                  </div>
                  {index < phaseSteps.length - 1 && (
                    <div className={cn(
                      'flex-1 h-0.5 mx-4 rounded-full transition-all',
                      isCompleted ? 'bg-emerald-500/30' : 'bg-zinc-800'
                    )} />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      )}

      {/* Status Card */}
      <ShadowModeStatusCard
        status={status}
        onEnable={() => setIsEnableDialogOpen(true)}
        onDisable={() => setIsDisableConfirmOpen(true)}
        onPromote={handlePromote}
        onGraduate={handleGraduate}
        isActionLoading={isActionLoading}
      />

      {/* Metrics Grid */}
      {isActive && <ShadowModeMetricsGrid statistics={statistics} />}

      {/* Sample Rate & Configuration Info */}
      {isActive && status && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Sample Rate</p>
            <p className="text-lg font-bold text-white">{Math.round(status.sample_rate * 100)}%</p>
            <p className="text-[10px] text-zinc-600">of messages are shadow-processed</p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Total Comparisons</p>
            <p className="text-lg font-bold text-white">{status.total_comparisons}</p>
            <p className="text-[10px] text-zinc-600">
              {status.shadow_wins} shadow wins ({status.total_comparisons > 0 ? Math.round((status.shadow_wins / status.total_comparisons) * 100) : 0}%)
            </p>
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Quality Streak</p>
            <p className="text-lg font-bold text-white">{status.quality_streak}</p>
            <p className="text-[10px] text-zinc-600">
              of {status.auto_graduation_window} required for auto-graduation
            </p>
          </div>
        </div>
      )}

      {/* Comparison History */}
      {isActive && (
        <ComparisonTable
          comparisons={comparisons}
          onReview={handleReview}
          isReviewLoading={isActionLoading}
        />
      )}

      {/* Disabled State — Empty State */}
      {!isActive && !isLoading && (
        <div className="flex flex-col items-center justify-center py-16 bg-[#1A1A1A] rounded-xl border border-white/[0.06]">
          <div className="w-16 h-16 rounded-2xl bg-purple-500/10 flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456Z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-white mb-2">Shadow Mode is Not Active</h3>
          <p className="text-sm text-zinc-500 mb-6 text-center max-w-md">
            Shadow mode lets you safely test a new AI variant alongside your live variant. The shadow variant processes a sample of messages silently, and you can compare quality, latency, and token usage before deciding to promote.
          </p>
          <button
            onClick={() => setIsEnableDialogOpen(true)}
            className="text-sm px-6 py-2.5 rounded-lg bg-gradient-to-r from-purple-500 to-purple-400 text-white font-medium shadow-lg shadow-purple-500/20 hover:shadow-purple-500/30 transition-all"
          >
            Enable Shadow Mode
          </button>

          {/* How It Works */}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl w-full">
            <div className="text-center p-4">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center mx-auto mb-2">
                <span className="text-purple-400 text-sm font-bold">1</span>
              </div>
              <h4 className="text-sm font-medium text-zinc-300 mb-1">Shadow Phase</h4>
              <p className="text-[10px] text-zinc-600 leading-relaxed">
                Shadow variant processes sampled messages silently. Quality and latency are compared automatically.
              </p>
            </div>
            <div className="text-center p-4">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center mx-auto mb-2">
                <span className="text-amber-400 text-sm font-bold">2</span>
              </div>
              <h4 className="text-sm font-medium text-zinc-300 mb-1">Supervised Phase</h4>
              <p className="text-[10px] text-zinc-600 leading-relaxed">
                Shadow variant responses require human review before delivery. Your team validates quality.
              </p>
            </div>
            <div className="text-center p-4">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center mx-auto mb-2">
                <span className="text-emerald-400 text-sm font-bold">3</span>
              </div>
              <h4 className="text-sm font-medium text-zinc-300 mb-1">Graduation</h4>
              <p className="text-[10px] text-zinc-600 leading-relaxed">
                Shadow variant passes all checks and becomes the new live variant. Safe, verified promotion.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Enable Dialog */}
      <EnableShadowModeDialog
        isOpen={isEnableDialogOpen}
        onClose={() => setIsEnableDialogOpen(false)}
        onEnable={handleEnable}
        isLoading={isActionLoading}
      />

      {/* Disable Confirmation Dialog */}
      {isDisableConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setIsDisableConfirmOpen(false)} />
          <div className="relative w-full max-w-sm bg-[#1A1A1A] border border-white/10 rounded-2xl shadow-2xl p-6">
            <h3 className="text-lg font-bold text-white mb-2">Disable Shadow Mode?</h3>
            <p className="text-sm text-zinc-400 mb-6">
              This will immediately stop shadow processing. The live variant will continue handling all messages normally. No data will be lost.
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsDisableConfirmOpen(false)}
                className="flex-1 text-sm px-4 py-2.5 rounded-lg bg-white/5 text-zinc-400 hover:text-zinc-200 hover:bg-white/10 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDisable}
                disabled={isActionLoading}
                className="flex-1 text-sm px-4 py-2.5 rounded-lg bg-red-500/10 text-red-400 font-medium hover:bg-red-500/20 transition-colors disabled:opacity-50"
              >
                {isActionLoading ? 'Disabling...' : 'Disable'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
