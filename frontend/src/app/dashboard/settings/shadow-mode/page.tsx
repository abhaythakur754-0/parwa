'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  shadowApi,
  type SystemMode,
  type ShadowPreference,
  type ShadowStats,
} from '@/lib/shadow-api';
import { useSocket } from '@/contexts/SocketContext';
import WhatIfSimulator from '@/components/dashboard/WhatIfSimulator';

// ── Skeleton Helper ────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/[0.06]', className)} />;
}

// ── Inline SVG Icons ───────────────────────────────────────────────────────

function ShieldCheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
    </svg>
  );
}

function EyeIcon({ className }: { className?: string }) {
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

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
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

function ArrowPathIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
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

function ExclamationTriangleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
    </svg>
  );
}

// ── Mode Configuration ─────────────────────────────────────────────────────

const MODE_CONFIG: Record<SystemMode, {
  label: string;
  description: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: React.ReactNode;
}> = {
  shadow: {
    label: 'Shadow Mode',
    description: 'All actions require manual approval. Maximum safety, minimum autonomy.',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/30',
    icon: <EyeIcon className="h-5 w-5" />,
  },
  supervised: {
    label: 'Supervised Mode',
    description: 'High-risk actions require approval. Balanced safety and efficiency.',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    icon: <ShieldCheckIcon className="h-5 w-5" />,
  },
  graduated: {
    label: 'Graduated Mode',
    description: 'AI operates independently. Only critical actions need approval.',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/30',
    icon: <CheckIcon className="h-5 w-5" />,
  },
};

const ACTION_CATEGORIES = [
  { key: 'refund', label: 'Refunds', description: 'Process customer refunds' },
  { key: 'email_reply', label: 'Email Replies', description: 'Automated email responses' },
  { key: 'sms_reply', label: 'SMS Replies', description: 'Automated SMS responses' },
  { key: 'voice_reply', label: 'Voice Responses', description: 'Voice call responses' },
  { key: 'ticket_close', label: 'Ticket Closure', description: 'Resolve and close tickets' },
  { key: 'account_change', label: 'Account Changes', description: 'Modify customer accounts' },
  { key: 'integration_action', label: 'Integrations', description: 'Third-party actions' },
];

const UNDO_WINDOW_OPTIONS = [
  { value: 5, label: '5 minutes' },
  { value: 15, label: '15 minutes' },
  { value: 30, label: '30 minutes' },
  { value: 60, label: '1 hour' },
];

// ── Helper Functions ───────────────────────────────────────────────────────

function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Never';
  try {
    const now = new Date();
    const date = new Date(dateStr);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  } catch {
    return 'Unknown';
  }
}

// ════════════════════════════════════════════════════════════════════════════
// Main Shadow Mode Settings Page
// ════════════════════════════════════════════════════════════════════════════

export default function ShadowModeSettingsPage() {
  const { isConnected } = useSocket();

  // ── State ───────────────────────────────────────────────────────────────
  const [currentMode, setCurrentMode] = useState<SystemMode>('shadow');
  const [preferences, setPreferences] = useState<ShadowPreference[]>([]);
  const [stats, setStats] = useState<ShadowStats | null>(null);
  const [undoWindow, setUndoWindow] = useState(30);
  const [riskThresholdShadow, setRiskThresholdShadow] = useState(0.7);
  const [riskThresholdAuto, setRiskThresholdAuto] = useState(0.3);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);

  const [addPrefModalOpen, setAddPrefModalOpen] = useState(false);
  const [newPrefCategory, setNewPrefCategory] = useState('');
  const [newPrefMode, setNewPrefMode] = useState<SystemMode>('shadow');
  const [deletingCategory, setDeletingCategory] = useState<string | null>(null);

  // ── Load Data ───────────────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const [modeRes, prefsRes, statsRes] = await Promise.all([
        shadowApi.getMode(),
        shadowApi.getPreferences(),
        shadowApi.getStats(),
      ]);

      setCurrentMode(modeRes.mode);
      setPreferences(prefsRes.preferences);
      setStats(statsRes);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── Real-time Sync via Socket.io ────────────────────────────────────────
  useEffect(() => {
    if (!isConnected) return;
    const socket = (window as any).__parwa_socket;
    if (!socket) return;

    const handleModeChange = (data: { mode: SystemMode }) => {
      setCurrentMode(data.mode);
      toast.success(`Shadow mode changed to ${data.mode}`);
    };

    const handlePrefChange = () => {
      shadowApi.getPreferences().then((res) => setPreferences(res.preferences));
    };

    socket.on('shadow:mode_changed', handleModeChange);
    socket.on('shadow:preference_changed', handlePrefChange);

    return () => {
      socket.off('shadow:mode_changed', handleModeChange);
      socket.off('shadow:preference_changed', handlePrefChange);
    };
  }, [isConnected]);

  // ── Handlers ────────────────────────────────────────────────────────────
  const handleModeChange = async (mode: SystemMode) => {
    setSaving(true);
    try {
      await shadowApi.setMode(mode, 'ui');
      setCurrentMode(mode);
      toast.success(`Switched to ${MODE_CONFIG[mode].label}`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleAddPreference = async () => {
    if (!newPrefCategory) {
      toast.error('Please select an action category');
      return;
    }

    setSaving(true);
    try {
      const newPref = await shadowApi.setPreference(newPrefCategory, newPrefMode, 'ui');
      setPreferences((prev) => {
        const filtered = prev.filter((p) => p.action_category !== newPrefCategory);
        return [...filtered, newPref];
      });
      setAddPrefModalOpen(false);
      setNewPrefCategory('');
      setNewPrefMode('shadow');
      toast.success('Preference added');
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePreference = async (category: string) => {
    setDeletingCategory(category);
    try {
      await shadowApi.deletePreference(category);
      setPreferences((prev) => prev.filter((p) => p.action_category !== category));
      toast.success('Preference removed');
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setDeletingCategory(null);
    }
  };

  const handleResetToDefault = async () => {
    if (!confirm('Reset all preferences to default? This will remove all custom settings.')) {
      return;
    }

    setSaving(true);
    try {
      // Delete all preferences
      await Promise.all(preferences.map((p) => shadowApi.deletePreference(p.action_category)));
      setPreferences([]);
      toast.success('All preferences reset to default');
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  // ════════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div className="jarvis-page-body min-h-screen bg-[#0A0A0A]">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        {/* ── Page Header ──────────────────────────────────────────────── */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FF7F11]/10">
              <ShieldCheckIcon className="h-5 w-5 text-[#FF7F11]" />
            </div>
            <h1 className="text-2xl font-bold text-white">Shadow Mode Settings</h1>
          </div>
          <p className="text-sm text-zinc-500 ml-[52px]">
            Configure how Jarvis handles AI actions with safety controls.
          </p>
        </div>

        {loading ? (
          <div className="space-y-6">
            <Skeleton className="h-48" />
            <Skeleton className="h-64" />
            <Skeleton className="h-48" />
          </div>
        ) : error ? (
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6 text-center">
            <ExclamationTriangleIcon className="h-10 w-10 text-red-400 mx-auto mb-4" />
            <p className="text-zinc-400 mb-4">Failed to load settings</p>
            <button
              onClick={loadData}
              className="inline-flex items-center gap-2 rounded-lg bg-[#FF7F11] px-4 py-2 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
            >
              Try Again
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* ═══════════════════════════════════════════════════════════════
                Global Mode Selector
                ═══════════════════════════════════════════════════════════════ */}
            <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6">
              <div className="flex items-center gap-2 mb-4">
                <ShieldCheckIcon className="h-5 w-5 text-[#FF7F11]" />
                <h2 className="text-base font-semibold text-white">Global Mode</h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {(Object.keys(MODE_CONFIG) as SystemMode[]).map((mode) => {
                  const config = MODE_CONFIG[mode];
                  const isActive = currentMode === mode;

                  return (
                    <button
                      key={mode}
                      onClick={() => handleModeChange(mode)}
                      disabled={saving}
                      className={cn(
                        'relative rounded-xl border p-4 text-left transition-all',
                        isActive
                          ? `${config.borderColor} ${config.bgColor} ring-1 ring-current`
                          : 'border-white/[0.06] bg-[#141414] hover:bg-white/[0.04]',
                        saving && 'opacity-50 cursor-not-allowed'
                      )}
                    >
                      {isActive && (
                        <div className={cn('absolute top-3 right-3', config.color)}>
                          <CheckIcon className="h-4 w-4" />
                        </div>
                      )}
                      <div className={cn('mb-2', config.color)}>{config.icon}</div>
                      <h3 className="text-sm font-semibold text-white mb-1">{config.label}</h3>
                      <p className="text-xs text-zinc-500 leading-relaxed">{config.description}</p>
                    </button>
                  );
                })}
              </div>

              {/* Stats Summary */}
              {stats && (
                <div className="mt-4 pt-4 border-t border-white/[0.06]">
                  <div className="flex flex-wrap gap-4 text-xs text-zinc-500">
                    <span>Total actions: <span className="text-zinc-300">{stats.total_actions}</span></span>
                    <span>Pending: <span className="text-yellow-400">{stats.pending_count}</span></span>
                    <span>Approval rate: <span className="text-emerald-400">{(stats.approval_rate * 100).toFixed(1)}%</span></span>
                  </div>
                </div>
              )}
            </div>

            {/* ═══════════════════════════════════════════════════════════════
                Per-Action Preferences
                ═══════════════════════════════════════════════════════════════ */}
            <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <EyeIcon className="h-5 w-5 text-[#FF7F11]" />
                  <h2 className="text-base font-semibold text-white">Per-Action Preferences</h2>
                </div>
                <div className="flex items-center gap-2">
                  {preferences.length > 0 && (
                    <button
                      onClick={handleResetToDefault}
                      disabled={saving}
                      className="text-xs text-zinc-500 hover:text-red-400 transition-colors"
                    >
                      Reset All
                    </button>
                  )}
                  <button
                    onClick={() => setAddPrefModalOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[#FF7F11]/30 bg-[#FF7F11]/10 px-3 py-1.5 text-xs font-medium text-[#FF7F11] hover:bg-[#FF7F11]/20 transition-colors"
                  >
                    <PlusIcon className="h-3.5 w-3.5" />
                    Add Preference
                  </button>
                </div>
              </div>

              {preferences.length === 0 ? (
                <div className="text-center py-8">
                  <EyeIcon className="h-10 w-10 text-zinc-700 mx-auto mb-3" />
                  <p className="text-sm text-zinc-500">No custom preferences configured</p>
                  <p className="text-xs text-zinc-600 mt-1">
                    Actions will use the global mode setting
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/[0.06]">
                        <th className="px-3 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Category</th>
                        <th className="px-3 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Mode</th>
                        <th className="px-3 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Set Via</th>
                        <th className="px-3 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Updated</th>
                        <th className="px-3 py-2 text-right text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.04]">
                      {preferences.map((pref) => {
                        const category = ACTION_CATEGORIES.find((c) => c.key === pref.action_category);
                        const modeConfig = MODE_CONFIG[pref.preferred_mode];

                        return (
                          <tr key={pref.id} className="hover:bg-white/[0.02]">
                            <td className="px-3 py-3">
                              <div>
                                <span className="text-zinc-200 font-medium">
                                  {category?.label || pref.action_category}
                                </span>
                                {category && (
                                  <p className="text-[10px] text-zinc-600">{category.description}</p>
                                )}
                              </div>
                            </td>
                            <td className="px-3 py-3">
                              <span className={cn(
                                'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
                                modeConfig.bgColor,
                                modeConfig.color,
                                modeConfig.borderColor
                              )}>
                                {pref.preferred_mode}
                              </span>
                            </td>
                            <td className="px-3 py-3">
                              <span className={cn(
                                'text-xs',
                                pref.set_via === 'jarvis' ? 'text-[#FF7F11]' : 'text-zinc-400'
                              )}>
                                {pref.set_via === 'jarvis' ? 'Jarvis' : 'UI'}
                              </span>
                            </td>
                            <td className="px-3 py-3 text-xs text-zinc-500">
                              {formatRelativeTime(pref.updated_at)}
                            </td>
                            <td className="px-3 py-3 text-right">
                              <button
                                onClick={() => handleDeletePreference(pref.action_category)}
                                disabled={deletingCategory === pref.action_category}
                                className="text-zinc-500 hover:text-red-400 transition-colors disabled:opacity-50"
                              >
                                {deletingCategory === pref.action_category ? (
                                  <SpinnerIcon className="h-4 w-4 animate-spin" />
                                ) : (
                                  <TrashIcon className="h-4 w-4" />
                                )}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* ═══════════════════════════════════════════════════════════════
                Undo & Threshold Settings
                ═══════════════════════════════════════════════════════════════ */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Undo Window */}
              <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6">
                <div className="flex items-center gap-2 mb-4">
                  <ClockIcon className="h-5 w-5 text-[#FF7F11]" />
                  <h2 className="text-base font-semibold text-white">Undo Window</h2>
                </div>
                <p className="text-sm text-zinc-500 mb-4">
                  Time window during which auto-approved actions can be undone.
                </p>
                <select
                  value={undoWindow}
                  onChange={(e) => setUndoWindow(parseInt(e.target.value))}
                  className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-2.5 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 transition-colors appearance-none cursor-pointer"
                >
                  {UNDO_WINDOW_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              {/* Risk Thresholds */}
              <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6">
                <div className="flex items-center gap-2 mb-4">
                  <ExclamationTriangleIcon className="h-5 w-5 text-[#FF7F11]" />
                  <h2 className="text-base font-semibold text-white">Risk Thresholds</h2>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-xs text-zinc-400 mb-2">
                      Force shadow above risk: <span className="text-orange-400 font-mono">{(riskThresholdShadow * 100).toFixed(0)}%</span>
                    </label>
                    <input
                      type="range"
                      min="0.5"
                      max="1"
                      step="0.05"
                      value={riskThresholdShadow}
                      onChange={(e) => setRiskThresholdShadow(parseFloat(e.target.value))}
                      className="w-full h-2 bg-white/[0.06] rounded-lg appearance-none cursor-pointer accent-[#FF7F11]"
                    />
                    <p className="text-[10px] text-zinc-600 mt-1">Actions above this risk always require approval</p>
                  </div>

                  <div>
                    <label className="block text-xs text-zinc-400 mb-2">
                      Auto-execute below risk: <span className="text-emerald-400 font-mono">{(riskThresholdAuto * 100).toFixed(0)}%</span>
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="0.5"
                      step="0.05"
                      value={riskThresholdAuto}
                      onChange={(e) => setRiskThresholdAuto(parseFloat(e.target.value))}
                      className="w-full h-2 bg-white/[0.06] rounded-lg appearance-none cursor-pointer accent-[#FF7F11]"
                    />
                    <p className="text-[10px] text-zinc-600 mt-1">Actions below this risk are auto-executed</p>
                  </div>
                </div>
              </div>
            </div>

            {/* ═══════════════════════════════════════════════════════════════
                What-If Simulator
                ═══════════════════════════════════════════════════════════════ */}
            <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6">
              <WhatIfSimulator />
            </div>
          </div>
        )}

        {/* ── Add Preference Modal ─────────────────────────────────────────── */}
        {addPrefModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="w-full max-w-md mx-4 rounded-xl border border-white/[0.08] bg-[#1A1A1A] p-6 shadow-2xl">
              <h4 className="text-base font-semibold text-white mb-4">Add Preference</h4>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">Action Category</label>
                  <select
                    value={newPrefCategory}
                    onChange={(e) => setNewPrefCategory(e.target.value)}
                    className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-2.5 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 transition-colors appearance-none cursor-pointer"
                  >
                    <option value="">Select category...</option>
                    {ACTION_CATEGORIES.map((cat) => (
                      <option key={cat.key} value={cat.key}>{cat.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">Preferred Mode</label>
                  <div className="grid grid-cols-3 gap-2">
                    {(Object.keys(MODE_CONFIG) as SystemMode[]).map((mode) => {
                      const config = MODE_CONFIG[mode];
                      return (
                        <button
                          key={mode}
                          onClick={() => setNewPrefMode(mode)}
                          className={cn(
                            'rounded-lg border px-3 py-2 text-xs font-medium transition-all',
                            newPrefMode === mode
                              ? `${config.borderColor} ${config.bgColor} ${config.color}`
                              : 'border-white/[0.06] bg-[#141414] text-zinc-400 hover:bg-white/[0.04]'
                          )}
                        >
                          {config.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 mt-6">
                <button
                  onClick={() => setAddPrefModalOpen(false)}
                  className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-4 py-2 text-sm font-medium text-zinc-400 hover:text-zinc-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddPreference}
                  disabled={saving || !newPrefCategory}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#FF7F11] px-4 py-2 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 disabled:opacity-50 transition-colors"
                >
                  {saving && <SpinnerIcon className="h-4 w-4 animate-spin" />}
                  Add Preference
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
