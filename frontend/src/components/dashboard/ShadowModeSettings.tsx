'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  shadowApi,
  type SystemMode,
  type ShadowPreference,
} from '@/lib/shadow-api';

// ── Skeleton Helper ────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/[0.06]', className)} />;
}

// ── Inline SVG Icons ───────────────────────────────────────────────────────

function ShieldEyeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

function ArrowPathIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182M2.985 19.644l3.181-3.182" />
    </svg>
  );
}

function ExclamationTriangleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

function LockClosedIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
    </svg>
  );
}

// ── Section Card ───────────────────────────────────────────────────────────

function SectionCard({ title, icon, children, className }: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5', className)}>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-[#FF7F11]">{icon}</span>
        <h3 className="text-base font-semibold text-white">{title}</h3>
      </div>
      {children}
    </div>
  );
}

// ── Format Helpers ─────────────────────────────────────────────────────────

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch { return 'N/A'; }
}

// ── Mode Config ────────────────────────────────────────────────────────────

const MODE_CONFIG: Record<SystemMode, {
  label: string;
  description: string;
  color: string;
  bgColor: string;
  borderColor: string;
  dotColor: string;
  features: string[];
}> = {
  shadow: {
    label: 'Shadow',
    description: 'Preview-only mode. Jarvis evaluates all actions but nothing is executed. Perfect for initial testing and calibration.',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/15',
    borderColor: 'border-orange-500/25',
    dotColor: 'bg-orange-400',
    features: [
      'All actions previewed but never executed',
      'Risk scores calculated for every action',
      'Full audit trail maintained',
      'No impact on customers or data',
    ],
  },
  supervised: {
    label: 'Supervised',
    description: 'Jarvis suggests actions but requires manager approval before execution. Best for building confidence.',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/15',
    borderColor: 'border-blue-500/25',
    dotColor: 'bg-blue-400',
    features: [
      'Jarvis suggests optimal action',
      'Manager approves/rejects each action',
      'Risk scores guide decision-making',
      'Can modify suggested responses',
    ],
  },
  graduated: {
    label: 'Graduated',
    description: 'Auto-execute low-risk actions, shadow-evaluate high-risk ones. For mature deployments with proven accuracy.',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/15',
    borderColor: 'border-emerald-500/25',
    dotColor: 'bg-emerald-400',
    features: [
      'Low-risk actions auto-execute immediately',
      'High-risk actions require approval',
      'Undo window available for auto-actions',
      'Continuous monitoring with alerts',
    ],
  },
};

const MODE_ORDER: SystemMode[] = ['shadow', 'supervised', 'graduated'];

// ── Action Categories ──────────────────────────────────────────────────────

const ACTION_CATEGORIES = [
  { key: 'refund', label: 'Refund Processing', description: 'Issue refunds to customers' },
  { key: 'email_reply', label: 'Email Reply', description: 'Send email responses' },
  { key: 'sms_reply', label: 'SMS Reply', description: 'Send SMS responses' },
  { key: 'voice_reply', label: 'Voice Reply', description: 'Voice call responses' },
  { key: 'ticket_close', label: 'Close Ticket', description: 'Resolve and close tickets' },
  { key: 'account_change', label: 'Account Change', description: 'Modify customer accounts' },
  { key: 'integration_action', label: 'Integration', description: 'Third-party integrations' },
];

// ════════════════════════════════════════════════════════════════════════════
// ShadowModeSettings Component
// ════════════════════════════════════════════════════════════════════════════

export default function ShadowModeSettings() {
  // ── State ───────────────────────────────────────────────────────────────
  const [currentMode, setCurrentMode] = useState<SystemMode | null>(null);
  const [modeLoading, setModeLoading] = useState(true);
  const [switchingMode, setSwitchingMode] = useState(false);

  const [preferences, setPreferences] = useState<ShadowPreference[]>([]);
  const [prefsLoading, setPrefsLoading] = useState(true);
  const [updatingPref, setUpdatingPref] = useState<string | null>(null);
  const [resettingPref, setResettingPref] = useState<string | null>(null);

  // ── Load Mode ──────────────────────────────────────────────────────────
  const loadMode = useCallback(async () => {
    setModeLoading(true);
    try {
      const data = await shadowApi.getMode();
      setCurrentMode(data.mode);
    } catch {
      setCurrentMode('shadow');
    } finally {
      setModeLoading(false);
    }
  }, []);

  // ── Load Preferences ───────────────────────────────────────────────────
  const loadPreferences = useCallback(async () => {
    setPrefsLoading(true);
    try {
      const data = await shadowApi.getPreferences();
      setPreferences(data.preferences || []);
    } catch {
      setPreferences([]);
    } finally {
      setPrefsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMode();
    loadPreferences();
  }, [loadMode, loadPreferences]);

  // ── Handlers ───────────────────────────────────────────────────────────
  const handleModeSwitch = async (newMode: SystemMode) => {
    if (newMode === currentMode) return;
    const mc = MODE_CONFIG[newMode];
    if (!window.confirm(`Switch to ${mc.label} mode?\n\n${mc.description}`)) return;
    setSwitchingMode(true);
    try {
      await shadowApi.setMode(newMode);
      setCurrentMode(newMode);
      toast.success(`Switched to ${mc.label} mode`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSwitchingMode(false);
    }
  };

  const handlePrefChange = async (category: string, mode: SystemMode) => {
    setUpdatingPref(category);
    try {
      const pref = await shadowApi.setPreference(category, mode);
      setPreferences(prev => {
        const idx = prev.findIndex(p => p.action_category === category);
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = pref;
          return updated;
        }
        return [...prev, pref];
      });
      toast.success(`Updated ${category} preference`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setUpdatingPref(null);
    }
  };

  const handleResetPref = async (category: string) => {
    if (!window.confirm(`Reset ${category} to default mode?`)) return;
    setResettingPref(category);
    try {
      await shadowApi.deletePreference(category);
      setPreferences(prev => prev.filter(p => p.action_category !== category));
      toast.success(`Reset ${category} to default`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setResettingPref(null);
    }
  };

  const getPrefMode = (category: string): SystemMode | null => {
    const pref = preferences.find(p => p.action_category === category);
    return pref ? pref.preferred_mode : null;
  };

  // ════════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div className="space-y-6">
      {/* ── Current Mode Selector ──────────────────────────────────────── */}
      <SectionCard title="Shadow Mode" icon={<ShieldEyeIcon className="h-5 w-5" />}>
        {modeLoading ? (
          <Skeleton className="h-24" />
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-400">Current Mode</p>
                {currentMode && (
                  <div className="flex items-center gap-2 mt-1">
                    <span className={cn('w-2.5 h-2.5 rounded-full', MODE_CONFIG[currentMode].dotColor)} />
                    <span className={cn('text-lg font-bold', MODE_CONFIG[currentMode].color)}>
                      {MODE_CONFIG[currentMode].label}
                    </span>
                  </div>
                )}
              </div>
              {switchingMode && (
                <div className="flex items-center gap-2 text-xs text-zinc-500">
                  <SpinnerIcon className="w-4 h-4 animate-spin" />
                  Switching...
                </div>
              )}
            </div>

            {/* Mode Buttons */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {MODE_ORDER.map(m => {
                const mc = MODE_CONFIG[m];
                const isActive = m === currentMode;
                return (
                  <button
                    key={m}
                    onClick={() => handleModeSwitch(m)}
                    disabled={switchingMode || isActive}
                    className={cn(
                      'rounded-xl border p-4 text-left transition-all duration-200',
                      isActive
                        ? cn(mc.bgColor, mc.borderColor, 'ring-1 ring-offset-1 ring-offset-[#1A1A1A]', mc.dotColor.replace('bg-', 'ring-'))
                        : 'border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04]',
                      (switchingMode || isActive) && 'cursor-not-allowed opacity-80',
                    )}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span className={cn('w-2 h-2 rounded-full', mc.dotColor)} />
                      <span className={cn('text-sm font-semibold', isActive ? mc.color : 'text-zinc-300')}>
                        {mc.label}
                      </span>
                      {isActive && <CheckIcon className={cn('w-4 h-4 ml-auto', mc.color)} />}
                    </div>
                    <p className="text-[11px] text-zinc-500 leading-relaxed">{mc.description}</p>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </SectionCard>

      {/* ── Mode Features ──────────────────────────────────────────────── */}
      {currentMode && (
        <SectionCard title="What This Mode Does" icon={
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z" />
          </svg>
        }>
          <ul className="space-y-2">
            {MODE_CONFIG[currentMode].features.map((feat, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-zinc-400">
                <CheckIcon className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                <span>{feat}</span>
              </li>
            ))}
          </ul>
        </SectionCard>
      )}

      {/* ── Per-Category Preferences ───────────────────────────────────── */}
      <SectionCard title="Action Category Preferences" icon={
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" />
        </svg>
      }>
        {prefsLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-12" />)}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="px-3 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Category</th>
                  <th className="px-3 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Mode</th>
                  <th className="px-3 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider hidden sm:table-cell">Set Via</th>
                  <th className="px-3 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider hidden md:table-cell">Updated</th>
                  <th className="px-3 py-2 text-right text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Reset</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {ACTION_CATEGORIES.map(cat => {
                  const prefMode = getPrefMode(cat.key);
                  const pref = preferences.find(p => p.action_category === cat.key);
                  const isUpdating = updatingPref === cat.key;
                  const isResetting = resettingPref === cat.key;

                  return (
                    <tr key={cat.key} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-3 py-3">
                        <div>
                          <span className="text-xs font-medium text-zinc-300">{cat.label}</span>
                          <p className="text-[10px] text-zinc-600 mt-0.5">{cat.description}</p>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <select
                          value={prefMode || ''}
                          onChange={e => {
                            if (e.target.value) handlePrefChange(cat.key, e.target.value as SystemMode);
                          }}
                          disabled={isUpdating}
                          className="rounded-lg border border-white/[0.08] bg-[#141414] px-2.5 py-1.5 text-xs text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 appearance-none cursor-pointer disabled:opacity-50 pr-6 min-w-[120px]"
                        >
                          <option value="">Default</option>
                          {MODE_ORDER.map(m => (
                            <option key={m} value={m}>{MODE_CONFIG[m].label}</option>
                          ))}
                        </select>
                        {isUpdating && (
                          <div className="flex items-center gap-1 mt-1">
                            <SpinnerIcon className="w-3 h-3 animate-spin text-[#FF7F11]" />
                            <span className="text-[10px] text-zinc-500">Updating...</span>
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-3 hidden sm:table-cell">
                        {pref ? (
                          <span className={cn(
                            'inline-flex rounded-md px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider',
                            pref.set_via === 'jarvis'
                              ? 'bg-purple-500/15 text-purple-400'
                              : 'bg-zinc-500/15 text-zinc-400',
                          )}>
                            {pref.set_via === 'jarvis' ? 'Jarvis' : 'UI'}
                          </span>
                        ) : (
                          <span className="text-[10px] text-zinc-600">System default</span>
                        )}
                      </td>
                      <td className="px-3 py-3 hidden md:table-cell">
                        <span className="text-[11px] text-zinc-500">
                          {pref ? formatDate(pref.updated_at) : '—'}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        {pref && (
                          <button
                            onClick={() => handleResetPref(cat.key)}
                            disabled={isResetting}
                            className="inline-flex items-center gap-1 rounded-md bg-white/[0.04] border border-white/[0.06] px-2 py-1 text-[10px] font-medium text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.08] disabled:opacity-50 transition-colors"
                          >
                            {isResetting ? <SpinnerIcon className="w-3 h-3 animate-spin" /> : <ArrowPathIcon className="w-3 h-3" />}
                            Reset
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      {/* ── Safety Floor Info ──────────────────────────────────────────── */}
      <SectionCard title="Hard Safety Floor" icon={<ExclamationTriangleIcon className="h-5 w-5" />}>
        <div className="rounded-xl bg-red-500/5 border border-red-500/15 p-4">
          <p className="text-sm text-zinc-300 font-medium mb-2">Always-On Safety Restrictions</p>
          <p className="text-xs text-zinc-500 leading-relaxed mb-3">
            Regardless of the selected shadow mode, the following safety constraints are always enforced and cannot be overridden:
          </p>
          <ul className="space-y-1.5">
            {[
              'Refunds exceeding $1,000 always require human approval',
              'Account deletion actions are never auto-executed',
              'Bulk operations (50+ items) always require approval',
              'Actions affecting payment methods always require approval',
              'Suspicious activity-flagged actions always require approval',
            ].map((rule, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-zinc-400">
                <LockClosedIcon className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />
                <span>{rule}</span>
              </li>
            ))}
          </ul>
        </div>
      </SectionCard>

      {/* ── Undo Window Config ─────────────────────────────────────────── */}
      <SectionCard title="Undo Configuration" icon={<ClockIcon className="h-5 w-5" />}>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-zinc-300 font-medium">Undo Window</p>
              <p className="text-xs text-zinc-500">Time available to undo auto-approved actions in Graduated mode</p>
            </div>
            <span className="inline-flex rounded-lg bg-[#141414] border border-white/[0.06] px-3 py-1.5 text-sm font-mono text-zinc-300">
              30 minutes
            </span>
          </div>
          <p className="text-[11px] text-zinc-600">
            This value is configured by your account manager. Contact support to adjust the undo window.
          </p>
        </div>
      </SectionCard>
    </div>
  );
}
