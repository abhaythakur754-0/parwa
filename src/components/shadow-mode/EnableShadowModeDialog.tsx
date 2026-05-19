/**
 * EnableShadowModeDialog — Modal dialog for enabling shadow mode
 *
 * Allows user to select live and shadow variants, configure
 * sample rate, auto-graduation settings, and instance IDs.
 */

'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import type { EnableShadowModeRequest } from '@/types/shadow-mode';

// ── Variant Options ─────────────────────────────────────────────────

const variantOptions = [
  { value: 'mini_parwa', label: 'Mini Parwa', description: 'Lightweight agent for simple queries' },
  { value: 'parwa', label: 'Parwa Standard', description: 'Full technique suite with RAG support' },
  { value: 'parwa_high', label: 'Parwa High', description: 'Advanced reasoning and escalation' },
];

// ── Props ───────────────────────────────────────────────────────────

export interface EnableShadowModeDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onEnable: (data: EnableShadowModeRequest) => Promise<boolean>;
  isLoading?: boolean;
  preselectedLiveVariant?: string;
  preselectedShadowVariant?: string;
}

// ── Component ───────────────────────────────────────────────────────

export function EnableShadowModeDialog({
  isOpen,
  onClose,
  onEnable,
  isLoading,
  preselectedLiveVariant,
  preselectedShadowVariant,
}: EnableShadowModeDialogProps) {
  const [liveVariant, setLiveVariant] = useState(preselectedLiveVariant || 'mini_parwa');
  const [shadowVariant, setShadowVariant] = useState(preselectedShadowVariant || 'parwa');
  const [sampleRate, setSampleRate] = useState(1.0);
  const [autoGradThreshold, setAutoGradThreshold] = useState(0.95);
  const [autoGradWindow, setAutoGradWindow] = useState(100);
  const [supervisedTimeout, setSupervisedTimeout] = useState(300);
  const [autoPromoteSupervised, setAutoPromoteSupervised] = useState(true);
  const [autoPromoteGraduated, setAutoPromoteGraduated] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    const success = await onEnable({
      live_variant: liveVariant,
      shadow_variant: shadowVariant,
      sample_rate: sampleRate,
      auto_graduation_threshold: autoGradThreshold,
      auto_graduation_window: autoGradWindow,
      supervised_timeout_seconds: supervisedTimeout,
      auto_promote_to_supervised: autoPromoteSupervised,
      auto_promote_to_graduated: autoPromoteGraduated,
    });
    if (success) onClose();
  };

  // Validate: shadow must be different from live, and ideally higher tier
  const isValid = liveVariant !== shadowVariant;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Dialog */}
      <div className="relative w-full max-w-lg bg-[#1A1A1A] border border-white/10 rounded-2xl shadow-2xl shadow-black/50 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/[0.06]">
          <h2 className="text-lg font-bold text-white">Enable Shadow Mode</h2>
          <p className="text-xs text-zinc-500 mt-0.5">Test a new variant alongside your live variant without affecting customers</p>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-5 max-h-[70vh] overflow-y-auto scrollbar-premium">
          {/* Variant Selection */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1.5 block">Live Variant</label>
              <select
                value={liveVariant}
                onChange={(e) => setLiveVariant(e.target.value)}
                className="w-full text-sm px-3 py-2 rounded-lg bg-white/5 border border-white/[0.06] text-white outline-none focus:border-purple-500/30 transition-colors"
              >
                {variantOptions.map((v) => (
                  <option key={v.value} value={v.value} className="bg-[#1A1A1A] text-white">
                    {v.label}
                  </option>
                ))}
              </select>
              <p className="text-[10px] text-zinc-600 mt-1">
                {variantOptions.find(v => v.value === liveVariant)?.description}
              </p>
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1.5 block">Shadow Variant</label>
              <select
                value={shadowVariant}
                onChange={(e) => setShadowVariant(e.target.value)}
                className={cn(
                  'w-full text-sm px-3 py-2 rounded-lg bg-white/5 border text-white outline-none focus:border-purple-500/30 transition-colors',
                  !isValid ? 'border-red-500/30' : 'border-white/[0.06]'
                )}
              >
                {variantOptions.map((v) => (
                  <option key={v.value} value={v.value} className="bg-[#1A1A1A] text-white">
                    {v.label}
                  </option>
                ))}
              </select>
              <p className="text-[10px] text-zinc-600 mt-1">
                {variantOptions.find(v => v.value === shadowVariant)?.description}
              </p>
              {!isValid && (
                <p className="text-[10px] text-red-400 mt-1">Shadow variant must differ from live variant</p>
              )}
            </div>
          </div>

          {/* Sample Rate */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-zinc-400">Sample Rate</label>
              <span className="text-xs text-zinc-300 font-medium">{Math.round(sampleRate * 100)}%</span>
            </div>
            <input
              type="range"
              min={0.01}
              max={1.0}
              step={0.01}
              value={sampleRate}
              onChange={(e) => setSampleRate(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-purple-500"
            />
            <p className="text-[10px] text-zinc-600 mt-1">Fraction of messages to shadow-process (1-100%)</p>
          </div>

          {/* Auto-Graduation Threshold */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-zinc-400">Auto-Graduation Threshold</label>
              <span className="text-xs text-zinc-300 font-medium">{Math.round(autoGradThreshold * 100)}%</span>
            </div>
            <input
              type="range"
              min={0.5}
              max={1.0}
              step={0.01}
              value={autoGradThreshold}
              onChange={(e) => setAutoGradThreshold(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-emerald-500"
            />
            <p className="text-[10px] text-zinc-600 mt-1">Quality threshold the shadow variant must exceed for auto-graduation</p>
          </div>

          {/* Advanced Settings Toggle */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <svg
              className={cn('w-3.5 h-3.5 transition-transform', showAdvanced && 'rotate-90')}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
            </svg>
            Advanced Settings
          </button>

          {showAdvanced && (
            <div className="space-y-4 pl-2 border-l-2 border-white/[0.06]">
              {/* Graduation Window */}
              <div>
                <label className="text-xs font-medium text-zinc-400 mb-1.5 block">
                  Graduation Window <span className="text-zinc-600">({autoGradWindow} comparisons)</span>
                </label>
                <input
                  type="range"
                  min={10}
                  max={10000}
                  step={10}
                  value={autoGradWindow}
                  onChange={(e) => setAutoGradWindow(parseInt(e.target.value))}
                  className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-purple-500"
                />
                <p className="text-[10px] text-zinc-600 mt-1">Consecutive wins required for auto-graduation</p>
              </div>

              {/* Supervised Timeout */}
              <div>
                <label className="text-xs font-medium text-zinc-400 mb-1.5 block">
                  Supervised Timeout <span className="text-zinc-600">({supervisedTimeout}s)</span>
                </label>
                <input
                  type="range"
                  min={30}
                  max={3600}
                  step={30}
                  value={supervisedTimeout}
                  onChange={(e) => setSupervisedTimeout(parseInt(e.target.value))}
                  className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-amber-500"
                />
                <p className="text-[10px] text-zinc-600 mt-1">Timeout before auto-fallback in supervised mode</p>
              </div>

              {/* Auto-Promote Toggles */}
              <div className="space-y-2">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoPromoteSupervised}
                    onChange={(e) => setAutoPromoteSupervised(e.target.checked)}
                    className="w-4 h-4 rounded bg-white/5 border-white/20 accent-purple-500"
                  />
                  <div>
                    <span className="text-xs text-zinc-300 font-medium">Auto-promote to Supervised</span>
                    <p className="text-[10px] text-zinc-600">Automatically move from Shadow to Supervised phase</p>
                  </div>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoPromoteGraduated}
                    onChange={(e) => setAutoPromoteGraduated(e.target.checked)}
                    className="w-4 h-4 rounded bg-white/5 border-white/20 accent-emerald-500"
                  />
                  <div>
                    <span className="text-xs text-zinc-300 font-medium">Auto-promote to Graduated</span>
                    <p className="text-[10px] text-zinc-600">Automatically graduate from Supervised phase</p>
                  </div>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-white/[0.06] flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isLoading}
            className="text-sm px-4 py-2 rounded-lg bg-white/5 text-zinc-400 hover:text-zinc-200 hover:bg-white/10 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!isValid || isLoading}
            className="text-sm px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-purple-400 text-white font-medium shadow-lg shadow-purple-500/20 hover:shadow-purple-500/30 transition-all disabled:opacity-50"
          >
            {isLoading ? 'Enabling...' : 'Enable Shadow Mode'}
          </button>
        </div>
      </div>
    </div>
  );
}
