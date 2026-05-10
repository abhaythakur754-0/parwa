'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  useTicketStore,
  VARIANT_LABELS,
  VARIANT_COST,
  CATEGORY_LABELS,
  STATUS_LABELS,
  ALL_CATEGORIES,
  PRIORITY_LABELS,
  type TicketVariant,
} from '@/lib/ticket-store';
import toast from 'react-hot-toast';

// ── Variant Config Modal ────────────────────────────────────────────

function VariantConfigModal({
  variant,
  open,
  onClose,
}: {
  variant: TicketVariant;
  open: boolean;
  onClose: () => void;
}) {
  const configs: Record<TicketVariant, {
    name: string;
    tier: string;
    model: string;
    description: string;
    maxTokens: number;
    temperature: number;
    systemPrompt: string;
  }> = {
    light: {
      name: 'PARWA Light',
      tier: 'Entry',
      model: 'Gemini Flash',
      description: 'Fast, cost-effective handling for simple queries',
      maxTokens: 500,
      temperature: 0.3,
      systemPrompt: 'You are a helpful customer support agent for PARWA. Handle simple queries efficiently and directly.',
    },
    medium: {
      name: 'PARWA Medium',
      tier: 'Growth',
      model: 'Gemini Pro',
      description: 'Balanced reasoning for complex multi-step issues',
      maxTokens: 2000,
      temperature: 0.5,
      systemPrompt: 'You are an experienced customer support agent for PARWA. Handle complex queries with careful reasoning and empathy.',
    },
    heavy: {
      name: 'PARWA Heavy',
      tier: 'Enterprise',
      model: 'Claude 3.5 Sonnet',
      description: 'Deep analysis for critical, VIP, and security cases',
      maxTokens: 5000,
      temperature: 0.7,
      systemPrompt: 'You are a senior customer support specialist for PARWA. Handle critical, VIP, and security-sensitive cases with thorough analysis.',
    },
  };

  const config = configs[variant];
  const [maxTokens, setMaxTokens] = useState(config.maxTokens);
  const [temperature, setTemperature] = useState(config.temperature);

  if (!open) return null;

  const handleSave = () => {
    toast.success(`${config.name} configuration saved`);
    onClose();
  };

  const variantColors: Record<TicketVariant, { accent: string; bg: string; text: string; border: string }> = {
    light: { accent: 'bg-zinc-400', bg: 'bg-zinc-500/10', text: 'text-zinc-300', border: 'border-zinc-500/30' },
    medium: { accent: 'bg-sky-400', bg: 'bg-sky-500/10', text: 'text-sky-300', border: 'border-sky-500/30' },
    heavy: { accent: 'bg-orange-400', bg: 'bg-orange-500/10', text: 'text-orange-300', border: 'border-orange-500/30' },
  };
  const c = variantColors[variant];

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          className="relative w-full max-w-md bg-[#1A1A1A] border border-white/[0.06] rounded-2xl shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className={`p-5 ${c.bg} border-b ${c.border}`}>
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-xl ${c.bg} ${c.border} border flex items-center justify-center`}>
                <svg className={`w-5 h-5 ${c.text}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
                </svg>
              </div>
              <div>
                <h2 className="text-white font-semibold">{config.name} Configuration</h2>
                <p className="text-zinc-400 text-xs">{config.model} · {config.description}</p>
              </div>
            </div>
          </div>

          {/* Settings */}
          <div className="p-5 space-y-5">
            {/* Model */}
            <div>
              <label className="text-[11px] text-zinc-400 mb-1.5 block">LLM Model</label>
              <div className="h-9 bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 flex items-center">
                <span className="text-sm text-white">{config.model}</span>
              </div>
            </div>

            {/* Max Tokens */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-[11px] text-zinc-400">Max Tokens</label>
                <span className="text-[11px] text-zinc-300 font-mono">{maxTokens.toLocaleString()}</span>
              </div>
              <input
                type="range"
                min={100}
                max={8000}
                step={100}
                value={maxTokens}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
                className="w-full h-1.5 bg-white/5 rounded-full appearance-none cursor-pointer accent-orange-500"
              />
              <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
                <span>100</span>
                <span>8,000</span>
              </div>
            </div>

            {/* Temperature */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-[11px] text-zinc-400">Temperature</label>
                <span className="text-[11px] text-zinc-300 font-mono">{temperature.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
                className="w-full h-1.5 bg-white/5 rounded-full appearance-none cursor-pointer accent-orange-500"
              />
              <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
                <span>Precise (0)</span>
                <span>Creative (1)</span>
              </div>
            </div>

            {/* System Prompt */}
            <div>
              <label className="text-[11px] text-zinc-400 mb-1.5 block">System Prompt</label>
              <textarea
                defaultValue={config.systemPrompt}
                rows={3}
                className="w-full bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-orange-500/40 resize-none"
              />
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-1">
              <button
                onClick={onClose}
                className="flex-1 h-10 rounded-lg border border-white/[0.06] text-sm text-zinc-400 hover:text-zinc-300 hover:border-white/10 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="flex-1 h-10 rounded-lg bg-orange-500 text-sm text-white font-medium hover:bg-orange-600 transition-colors"
              >
                Save Changes
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ── Main VariantsPage ───────────────────────────────────────────────

export default function VariantsPage() {
  const tickets = useTicketStore((s) => s.tickets);
  const init = useTicketStore((s) => s.init);
  const [initialized, setInitialized] = useState(false);
  const [configVariant, setConfigVariant] = useState<TicketVariant | null>(null);

  useEffect(() => {
    const initialize = () => {
      init();
      setInitialized(true);
    };
    initialize();
  }, []);

  const variantData = useMemo(() => {
    if (!initialized) return null;

    const data: Record<
      TicketVariant,
      {
        name: string;
        tier: string;
        model: string;
        status: 'Active';
        total: number;
        open: number;
        resolved: number;
        inProgress: number;
        resolutionRate: number;
        avgTime: string;
        costPerTicket: number;
        totalCost: number;
        totalSavings: number;
        accuracy: number;
        recentTickets: typeof tickets;
        categoryBreakdown: Record<string, number>;
      }
    > = {
      light: {
        name: 'PARWA Light',
        tier: 'Entry',
        model: 'Gemini Flash',
        status: 'Active',
        total: 0,
        open: 0,
        resolved: 0,
        inProgress: 0,
        resolutionRate: 0,
        avgTime: '<2s',
        costPerTicket: VARIANT_COST.light,
        totalCost: 0,
        totalSavings: 0,
        accuracy: 95.2,
        recentTickets: [],
        categoryBreakdown: {},
      },
      medium: {
        name: 'PARWA Medium',
        tier: 'Growth',
        model: 'Gemini Pro',
        status: 'Active',
        total: 0,
        open: 0,
        resolved: 0,
        inProgress: 0,
        resolutionRate: 0,
        avgTime: '~5s',
        costPerTicket: VARIANT_COST.medium,
        totalCost: 0,
        totalSavings: 0,
        accuracy: 89.7,
        recentTickets: [],
        categoryBreakdown: {},
      },
      heavy: {
        name: 'PARWA Heavy',
        tier: 'Enterprise',
        model: 'Claude 3.5 Sonnet',
        status: 'Active',
        total: 0,
        open: 0,
        resolved: 0,
        inProgress: 0,
        resolutionRate: 0,
        avgTime: '~8s',
        costPerTicket: VARIANT_COST.heavy,
        totalCost: 0,
        totalSavings: 0,
        accuracy: 93.1,
        recentTickets: [],
        categoryBreakdown: {},
      },
    };

    for (const variant of ['light', 'medium', 'heavy'] as TicketVariant[]) {
      const vt = tickets.filter((t) => t.assigned_variant === variant);
      const open = vt.filter((t) => t.status === 'open' || t.status === 'in_progress').length;
      const resolved = vt.filter((t) => t.status === 'resolved' || t.status === 'closed').length;
      const inProgress = vt.filter((t) => t.status === 'in_progress').length;
      const resolutionRate = vt.length > 0 ? Math.round((resolved / vt.length) * 100) : 0;
      const totalCost = vt.reduce((s, t) => s + (t.cost_per_ticket ?? 0), 0);
      const totalSavings = vt.reduce((s, t) => s + (t.savings_per_ticket ?? 0), 0);

      // Category breakdown
      const cats: Record<string, number> = {};
      for (const t of vt) {
        const label = CATEGORY_LABELS[t.category];
        cats[label] = (cats[label] ?? 0) + 1;
      }

      data[variant] = {
        ...data[variant],
        total: vt.length,
        open,
        resolved,
        inProgress,
        resolutionRate,
        totalCost: Math.round(totalCost * 1000) / 1000,
        totalSavings: Math.round(totalSavings * 100) / 100,
        recentTickets: vt.slice(0, 5),
        categoryBreakdown: cats,
      };
    }

    return data;
  }, [tickets, initialized]);

  if (!variantData) {
    return (
      <div className="space-y-6">
        <div className="pb-6 border-b border-white/[0.06]">
          <h1 className="text-xl font-bold text-white">Variant Engine</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Configure and monitor your AI variant instances
          </p>
        </div>
        <div className="flex items-center justify-center py-20">
          <svg className="w-5 h-5 animate-spin text-zinc-500" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      </div>
    );
  }

  const variants = ['light', 'medium', 'heavy'] as TicketVariant[];
  const totalAll = variants.reduce((s, v) => s + variantData[v].total, 0);
  const totalSavings = variants.reduce((s, v) => s + variantData[v].totalSavings, 0);

  const variantColors: Record<TicketVariant, {
    accent: string;
    badge: string;
    bar: string;
    barBg: string;
    border: string;
    bg: string;
    text: string;
  }> = {
    light: {
      accent: 'border-zinc-500/30',
      badge: 'bg-zinc-500/10 text-zinc-300',
      bar: 'bg-zinc-400',
      barBg: 'bg-zinc-500/10',
      border: 'border-zinc-500/20',
      bg: 'bg-zinc-500/10',
      text: 'text-zinc-400',
    },
    medium: {
      accent: 'border-sky-500/30',
      badge: 'bg-sky-500/10 text-sky-300',
      bar: 'bg-sky-400',
      barBg: 'bg-sky-500/10',
      border: 'border-sky-500/20',
      bg: 'bg-sky-500/10',
      text: 'text-sky-400',
    },
    heavy: {
      accent: 'border-orange-500/30',
      badge: 'bg-orange-500/10 text-orange-300',
      bar: 'bg-orange-400',
      barBg: 'bg-orange-500/10',
      border: 'border-orange-500/20',
      bg: 'bg-orange-500/10',
      text: 'text-orange-400',
    },
  };

  return (
    <div className="space-y-6">
      <div className="pb-6 border-b border-white/[0.06]">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-bold text-white">Variant Engine</h1>
            <p className="text-sm text-zinc-500 mt-0.5">
              Configure and monitor your AI variant instances
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <div className="text-center">
              <div className="text-white font-bold">{totalAll}</div>
              <div className="text-zinc-500">Total Tickets</div>
            </div>
            <div className="w-px h-8 bg-white/[0.06]" />
            <div className="text-center">
              <div className="text-emerald-400 font-bold">${totalSavings.toFixed(2)}</div>
              <div className="text-zinc-500">Total Savings</div>
            </div>
          </div>
        </div>
      </div>

      {/* Variant Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {variants.map((variant) => {
          const d = variantData[variant];
          const c = variantColors[variant];

          return (
            <div
              key={variant}
              className={`rounded-xl border border-white/[0.06] ${c.accent} bg-[#1A1A1A] p-5 hover:border-white/[0.1] transition-all duration-300`}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${c.badge}`}>
                      {variant.toUpperCase()}
                    </span>
                    <h3 className="text-sm font-semibold text-white">{d.name}</h3>
                  </div>
                  <span className="text-xs text-zinc-500">{d.tier} · {d.model}</span>
                </div>
                <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {d.status}
                </span>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="bg-white/[0.03] rounded-lg p-2.5 text-center">
                  <div className="text-lg font-bold text-white">{d.total}</div>
                  <div className="text-[10px] text-zinc-500">Tickets</div>
                </div>
                <div className="bg-white/[0.03] rounded-lg p-2.5 text-center">
                  <div className="text-lg font-bold text-emerald-400">{d.resolutionRate}%</div>
                  <div className="text-[10px] text-zinc-500">Resolution</div>
                </div>
              </div>

              {/* Metrics */}
              <div className="space-y-2.5 mb-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-500">Avg Response</span>
                  <span className="text-zinc-300 font-medium">{d.avgTime}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-500">Cost/Ticket</span>
                  <span className="text-zinc-300 font-medium">${d.costPerTicket.toFixed(3)}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-500">Savings/Ticket</span>
                  <span className="text-emerald-400 font-semibold">${(12.5 - d.costPerTicket).toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-500">Total Cost</span>
                  <span className="text-zinc-300 font-medium">${d.totalCost.toFixed(3)}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-500">Accuracy</span>
                  <span className="text-orange-400 font-semibold">{d.accuracy}%</span>
                </div>

                {/* Status breakdown */}
                <div className="flex items-center gap-2 pt-1">
                  <span className="w-2 h-2 rounded-full bg-blue-400" />
                  <span className="text-[10px] text-zinc-500">{d.open} open</span>
                  <span className="w-2 h-2 rounded-full bg-yellow-400" />
                  <span className="text-[10px] text-zinc-500">{d.inProgress} in progress</span>
                  <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  <span className="text-[10px] text-zinc-500">{d.resolved} resolved</span>
                </div>
              </div>

              {/* Category breakdown */}
              {Object.keys(d.categoryBreakdown).length > 0 && (
                <div className="mb-4">
                  <p className="text-[10px] text-zinc-500 mb-2">TOP CATEGORIES</p>
                  <div className="space-y-1.5">
                    {Object.entries(d.categoryBreakdown)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 4)
                      .map(([cat, count]) => {
                        const pct = d.total > 0 ? Math.round((count / d.total) * 100) : 0;
                        return (
                          <div key={cat} className="flex items-center gap-2">
                            <span className="text-[10px] text-zinc-400 w-24 truncate">{cat}</span>
                            <div className={`flex-1 h-1.5 rounded-full ${c.barBg} overflow-hidden`}>
                              <div
                                className={`h-full rounded-full ${c.bar} transition-all duration-700`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-zinc-500 w-4 text-right">{count}</span>
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}

              {/* Recent tickets */}
              {d.recentTickets.length > 0 && (
                <div className="mb-4">
                  <p className="text-[10px] text-zinc-500 mb-2">RECENT TICKETS</p>
                  <div className="space-y-1.5 max-h-32 overflow-y-auto">
                    {d.recentTickets.map((t) => (
                      <div
                        key={t.id}
                        className="flex items-center gap-2 text-[10px] bg-white/[0.02] rounded px-2 py-1.5"
                      >
                        <span className="font-mono text-zinc-500">{t.ticket_number}</span>
                        <span className="text-zinc-300 truncate flex-1">{t.subject}</span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded ${
                          t.status === 'resolved' || t.status === 'closed'
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : t.status === 'open'
                            ? 'bg-blue-500/10 text-blue-400'
                            : 'bg-yellow-500/10 text-yellow-400'
                        }`}>
                          {STATUS_LABELS[t.status]}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2 pt-4 border-t border-white/[0.06]">
                <button
                  onClick={() => setConfigVariant(variant)}
                  className="flex-1 text-xs font-medium py-2 rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20 hover:bg-orange-500/20 transition-colors"
                >
                  Configure
                </button>
                <button className="flex-1 text-xs font-medium py-2 rounded-lg bg-white/5 text-zinc-400 border border-white/10 hover:border-white/20 hover:text-zinc-300 transition-colors">
                  View Logs
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Performance Comparison */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Performance Comparison</h3>
        <div className="space-y-4">
          {/* Resolution Rate */}
          <div>
            <p className="text-xs text-zinc-500 mb-2">Resolution Rate</p>
            <div className="flex items-center gap-3">
              {variants.map((v) => {
                const d = variantData[v];
                const c = variantColors[v];
                const maxRate = 100;
                return (
                  <div key={v} className="flex-1">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-zinc-400">{v.charAt(0).toUpperCase() + v.slice(1)}</span>
                      <span className="text-zinc-300 font-medium">{d.resolutionRate}%</span>
                    </div>
                    <div className={`w-full h-2 rounded-full ${c.barBg} overflow-hidden`}>
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${(d.resolutionRate / maxRate) * 100}%` }}
                        transition={{ duration: 1, ease: 'easeOut', delay: 0.2 }}
                        className={`h-full rounded-full ${c.bar}`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Ticket Volume */}
          <div>
            <p className="text-xs text-zinc-500 mb-2">Ticket Volume Distribution</p>
            <div className="flex items-center gap-3">
              {variants.map((v) => {
                const d = variantData[v];
                const c = variantColors[v];
                const pct = totalAll > 0 ? Math.round((d.total / totalAll) * 100) : 0;
                return (
                  <div key={v} className="flex-1">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-zinc-400">{v.charAt(0).toUpperCase() + v.slice(1)}</span>
                      <span className="text-zinc-300 font-medium">{d.total} ({pct}%)</span>
                    </div>
                    <div className={`w-full h-2 rounded-full ${c.barBg} overflow-hidden`}>
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ duration: 1, ease: 'easeOut', delay: 0.4 }}
                        className={`h-full rounded-full ${c.bar}`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Cost Efficiency */}
          <div>
            <p className="text-xs text-zinc-500 mb-2">Cost Efficiency (lower = better)</p>
            <div className="flex items-center gap-3">
              {variants.map((v) => {
                const d = variantData[v];
                const c = variantColors[v];
                // Normalize: light should show highest efficiency
                const maxCost = 0.05;
                const efficiency = Math.round(((maxCost - d.costPerTicket) / maxCost) * 100);
                return (
                  <div key={v} className="flex-1">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-zinc-400">{v.charAt(0).toUpperCase() + v.slice(1)}</span>
                      <span className="text-zinc-300 font-medium">${d.costPerTicket.toFixed(3)}/tkt</span>
                    </div>
                    <div className={`w-full h-2 rounded-full ${c.barBg} overflow-hidden`}>
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${efficiency}%` }}
                        transition={{ duration: 1, ease: 'easeOut', delay: 0.6 }}
                        className={`h-full rounded-full ${c.bar}`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Accuracy */}
          <div>
            <p className="text-xs text-zinc-500 mb-2">AI Accuracy</p>
            <div className="flex items-center gap-3">
              {variants.map((v) => {
                const d = variantData[v];
                const c = variantColors[v];
                return (
                  <div key={v} className="flex-1">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-zinc-400">{v.charAt(0).toUpperCase() + v.slice(1)}</span>
                      <span className="text-zinc-300 font-medium">{d.accuracy}%</span>
                    </div>
                    <div className={`w-full h-2 rounded-full ${c.barBg} overflow-hidden`}>
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${d.accuracy}%` }}
                        transition={{ duration: 1, ease: 'easeOut', delay: 0.8 }}
                        className={`h-full rounded-full ${c.bar}`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Cost Savings Summary */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Cost Impact Summary</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {variants.map((v) => {
            const d = variantData[v];
            const c = variantColors[v];
            const humanCost = d.total * 12.5;
            return (
              <div key={v} className="bg-white/[0.02] rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${c.badge}`}>{v.toUpperCase()}</span>
                  <span className="text-xs text-zinc-400">{d.model}</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-[10px] text-zinc-500">AI Cost</div>
                    <div className="text-sm text-white font-medium">${d.totalCost.toFixed(3)}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-zinc-500">Human Equiv.</div>
                    <div className="text-sm text-zinc-400">${humanCost.toFixed(2)}</div>
                  </div>
                </div>
                <div className="pt-2 border-t border-white/[0.06]">
                  <div className="text-[10px] text-zinc-500">Total Savings</div>
                  <div className="text-lg font-bold text-emerald-400">${d.totalSavings.toFixed(2)}</div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-4 pt-4 border-t border-white/[0.06] flex items-center justify-between">
          <span className="text-xs text-zinc-500">Combined Savings Across All Variants</span>
          <span className="text-lg font-bold text-emerald-400">${totalSavings.toFixed(2)}</span>
        </div>
      </div>

      {/* Config Modal */}
      <VariantConfigModal
        variant={configVariant ?? 'light'}
        open={configVariant !== null}
        onClose={() => setConfigVariant(null)}
      />
    </div>
  );
}
