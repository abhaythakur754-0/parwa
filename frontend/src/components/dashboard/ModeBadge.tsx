'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { shadowApi, type SystemMode } from '@/lib/shadow-api';
import { getErrorMessage } from '@/lib/api';
import toast from 'react-hot-toast';

// ── Mode Config ──────────────────────────────────────────────────────────

const MODE_CONFIG: Record<SystemMode, {
  label: string;
  description: string;
  color: string;
  bgColor: string;
  borderColor: string;
  dotColor: string;
}> = {
  shadow: {
    label: 'Shadow',
    description: 'Preview only — no actions executed',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/15',
    borderColor: 'border-orange-500/25',
    dotColor: 'bg-orange-400',
  },
  supervised: {
    label: 'Supervised',
    description: 'Jarvis suggests, manager approves',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/15',
    borderColor: 'border-blue-500/25',
    dotColor: 'bg-blue-400',
  },
  graduated: {
    label: 'Graduated',
    description: 'Auto-execute low-risk, shadow for high-risk',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/15',
    borderColor: 'border-emerald-500/25',
    dotColor: 'bg-emerald-400',
  },
};

const MODE_ORDER: SystemMode[] = ['shadow', 'supervised', 'graduated'];

// ── Skeleton ─────────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-white/[0.06]', className)} />;
}

// ── Shield/Eye SVG Icon ─────────────────────────────────────────────────

function ShieldEyeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
    </svg>
  );
}

// ── Chevron SVG ──────────────────────────────────────────────────────────

function ChevronIcon({ className, open }: { className?: string; open?: boolean }) {
  return (
    <svg
      className={cn(className, open && 'rotate-180')}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2}
      stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
    </svg>
  );
}

// ── Check SVG ────────────────────────────────────────────────────────────

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// ModeBadge Component
// ════════════════════════════════════════════════════════════════════════════

interface ModeBadgeProps {
  /** Override current mode (for preview/testing) */
  modeOverride?: SystemMode;
  /** Compact mode — no label text, just dot */
  compact?: boolean;
  /** Show dropdown on click */
  interactive?: boolean;
  /** Callback when mode changes */
  onModeChange?: (mode: SystemMode) => void;
  /** Additional CSS classes */
  className?: string;
}

export default function ModeBadge({
  modeOverride,
  compact = false,
  interactive = true,
  onModeChange,
  className,
}: ModeBadgeProps) {
  const [currentMode, setCurrentMode] = useState<SystemMode | null>(null);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const mode = modeOverride || currentMode;
  const config = mode ? MODE_CONFIG[mode] : null;

  // ── Fetch mode ───────────────────────────────────────────────────────
  useEffect(() => {
    if (modeOverride) {
      setCurrentMode(modeOverride);
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const data = await shadowApi.getMode();
        setCurrentMode(data.mode);
      } catch {
        setCurrentMode('shadow'); // Safe default
      } finally {
        setLoading(false);
      }
    })();
  }, [modeOverride]);

  // ── Close dropdown on outside click ──────────────────────────────────
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── Switch mode handler ──────────────────────────────────────────────
  const handleSwitch = useCallback(async (newMode: SystemMode) => {
    if (newMode === currentMode) {
      setDropdownOpen(false);
      return;
    }
    setSwitching(true);
    try {
      await shadowApi.setMode(newMode);
      setCurrentMode(newMode);
      setDropdownOpen(false);
      toast.success(`Switched to ${MODE_CONFIG[newMode].label} mode`);
      onModeChange?.(newMode);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSwitching(false);
    }
  }, [currentMode, onModeChange]);

  // ── Loading skeleton ─────────────────────────────────────────────────
  if (loading || !mode || !config) {
    return <Skeleton className={cn(compact ? 'h-6 w-6 rounded-full' : 'h-7 w-24', className)} />;
  }

  return (
    <div className={cn('relative', className)} ref={dropdownRef}>
      {/* ── Badge ──────────────────────────────────────────────────── */}
      <button
        onClick={interactive ? () => setDropdownOpen(!dropdownOpen) : undefined}
        disabled={switching || !interactive}
        className={cn(
          'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium transition-all duration-200',
          config.bgColor,
          config.borderColor,
          config.color,
          interactive && 'cursor-pointer hover:opacity-90',
          !interactive && 'cursor-default',
          switching && 'opacity-60 cursor-wait',
        )}
        title={config.description}
      >
        {/* Mode dot */}
        <span className={cn('w-1.5 h-1.5 rounded-full', config.dotColor)} />

        {/* Label */}
        {!compact && <span>{config.label}</span>}

        {/* Chevron (if interactive) */}
        {interactive && !compact && (
          <ChevronIcon
            className={cn('w-3 h-3 transition-transform duration-150', config.color)}
            open={dropdownOpen}
          />
        )}
      </button>

      {/* ── Dropdown ────────────────────────────────────────────────── */}
      {dropdownOpen && interactive && (
        <div className="absolute top-full left-0 mt-2 w-64 bg-[#1A1A1A] border border-white/[0.08] rounded-xl shadow-2xl shadow-black/50 overflow-hidden z-50">
          <div className="px-4 py-3 border-b border-white/[0.06]">
            <p className="text-sm font-semibold text-white">Shadow Mode</p>
            <p className="text-[11px] text-zinc-500 mt-0.5">
              Choose how Jarvis handles actions
            </p>
          </div>

          <div className="py-1.5">
            {MODE_ORDER.map((m) => {
              const mc = MODE_CONFIG[m];
              const isActive = m === currentMode;
              return (
                <button
                  key={m}
                  onClick={() => handleSwitch(m)}
                  disabled={switching}
                  className={cn(
                    'w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors',
                    isActive ? 'bg-white/[0.04]' : 'hover:bg-white/[0.02]',
                    switching && 'opacity-50 cursor-wait',
                  )}
                >
                  <span className={cn('w-2 h-2 rounded-full shrink-0', mc.dotColor)} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={cn('text-sm font-medium', isActive ? mc.color : 'text-zinc-300')}>
                        {mc.label}
                      </span>
                      {isActive && (
                        <CheckIcon className={cn('w-3.5 h-3.5', mc.color)} />
                      )}
                    </div>
                    <p className="text-[11px] text-zinc-500 mt-0.5 truncate">
                      {mc.description}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>

          <div className="px-4 py-2 border-t border-white/[0.06]">
            <a
              href="/dashboard/settings"
              className="flex items-center gap-1.5 text-[11px] text-zinc-500 hover:text-[#FF7F11] transition-colors"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
              </svg>
              Configure in Settings
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
