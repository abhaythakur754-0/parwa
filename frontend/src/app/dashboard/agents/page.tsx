'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import {
  agentsApi,
  type AgentCardData,
  type AgentStatusCounts,
  type AgentCreateRequest,
  type AgentComparisonResult,
} from '@/lib/agents-api';
import { getErrorMessage } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

// ── Constants ─────────────────────────────────────────────────────────

const SPECIALTY_OPTIONS = [
  { value: 'billing_specialist', label: 'Billing Specialist' },
  { value: 'returns_specialist', label: 'Returns Specialist' },
  { value: 'technical_support', label: 'Technical Support' },
  { value: 'general_support', label: 'General Support' },
  { value: 'sales_assistant', label: 'Sales Assistant' },
  { value: 'onboarding_guide', label: 'Onboarding Guide' },
  { value: 'vip_concierge', label: 'VIP Concierge' },
  { value: 'feedback_collector', label: 'Feedback Collector' },
  { value: 'custom', label: 'Custom' },
];

const CHANNEL_OPTIONS = [
  { value: 'chat', label: 'Chat' },
  { value: 'email', label: 'Email' },
  { value: 'sms', label: 'SMS' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'voice', label: 'Voice' },
];

const STATUS_FILTER_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'error', label: 'Error' },
  { value: 'initializing', label: 'Initializing' },
];

const PERMISSION_OPTIONS = [
  { value: 'basic', label: 'Basic' },
  { value: 'standard', label: 'Standard' },
  { value: 'advanced', label: 'Advanced' },
  { value: 'admin', label: 'Admin' },
];

// ── Helpers ────────────────────────────────────────────────────────────

function formatSpecialty(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function statusColor(status: string): string {
  const map: Record<string, string> = {
    active: 'bg-emerald-500',
    paused: 'bg-amber-500',
    error: 'bg-red-500',
    initializing: 'bg-blue-500',
    training: 'bg-zinc-500',
    deprovisioned: 'bg-zinc-500',
  };
  return map[status] || 'bg-zinc-500';
}

function statusBadgeStyle(status: string): string {
  const map: Record<string, string> = {
    active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    paused: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    error: 'bg-red-500/10 text-red-400 border-red-500/20',
    initializing: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    training: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    deprovisioned: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
  };
  return map[status] || 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20';
}

function confidenceColor(c: number): string {
  if (c >= 75) return 'text-emerald-400';
  if (c >= 50) return 'text-amber-400';
  return 'text-red-400';
}

function confidenceBarColor(c: number): string {
  if (c >= 75) return 'bg-emerald-500';
  if (c >= 50) return 'bg-amber-500';
  return 'bg-red-500';
}

function channelIcon(channel: string): { icon: string; label: string } {
  const map: Record<string, { icon: string; label: string }> = {
    chat: { icon: 'C', label: 'Chat' },
    email: { icon: 'E', label: 'Email' },
    sms: { icon: 'S', label: 'SMS' },
    whatsapp: { icon: 'W', label: 'WhatsApp' },
    voice: { icon: 'V', label: 'Voice' },
  };
  return map[channel] || { icon: '?', label: channel };
}

// ── Inline SVG Icons ──────────────────────────────────────────────────

const SearchIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
  </svg>
);

const FilterIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0 1 12 3Z" />
  </svg>
);

const PlusIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
  </svg>
);

const PauseIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25v13.5m-7.5-13.5v13.5" />
  </svg>
);

const PlayIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
  </svg>
);

const BotIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
  </svg>
);

const CompareIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
  </svg>
);

const BarChartIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
  </svg>
);

// ── Confidence Gauge Component ────────────────────────────────────────

function ConfidenceGauge({ value, size = 'sm' }: { value: number; size?: 'sm' | 'md' }) {
  const radius = size === 'sm' ? 20 : 32;
  const stroke = size === 'sm' ? 3 : 4;
  const circumference = 2 * Math.PI * radius;
  const progress = (value / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={radius * 2 + 8} height={radius * 2 + 8} className="-rotate-90">
        <circle
          cx={radius + 4}
          cy={radius + 4}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={stroke}
        />
        <circle
          cx={radius + 4}
          cy={radius + 4}
          r={radius}
          fill="none"
          className={confidenceBarColor(value)}
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
        />
      </svg>
      <span className={`absolute text-xs font-bold ${confidenceColor(value)}`}>
        {Math.round(value)}%
      </span>
    </div>
  );
}

// ── Agent Card Component (A1) ─────────────────────────────────────────

function AgentCard({
  data,
  isComparing,
  isSelected,
  onToggleSelect,
  onTogglePause,
  onPauseLoading,
}: {
  data: AgentCardData;
  isComparing: boolean;
  isSelected: boolean;
  onToggleSelect: (id: string) => void;
  onTogglePause: (id: string, currentlyPaused: boolean) => void;
  onPauseLoading: boolean;
}) {
  const { agent } = data;
  const isPaused = agent.status === 'paused';
  const activeChannels = Object.entries(agent.channels || {})
    .filter(([, v]) => v === true || v === 1)
    .map(([k]) => k);

  return (
    <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl p-4 hover:border-white/[0.1] transition-colors group">
      {/* Top row: checkbox (comparison mode), name, status, pause */}
      <div className="flex items-start gap-3 mb-3">
        {isComparing && (
          <Checkbox
            checked={isSelected}
            onCheckedChange={() => onToggleSelect(agent.id)}
            className="mt-1 border-zinc-600 data-[state=checked]:bg-[#FF7F11] data-[state=checked]:border-[#FF7F11]"
          />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-[#FF7F11]/10 flex items-center justify-center shrink-0">
              <BotIcon />
            </div>
            <div className="min-w-0">
              <Link
                href={`/dashboard/agents/${agent.id}`}
                className="text-sm font-semibold text-zinc-200 hover:text-[#FF7F11] transition-colors truncate block"
              >
                {agent.name}
              </Link>
              <div className="flex items-center gap-2 mt-0.5">
                <Badge variant="outline" className={`text-[10px] ${statusBadgeStyle(agent.status)}`}>
                  {agent.status}
                </Badge>
                <Badge variant="outline" className="text-[10px] bg-violet-500/10 text-violet-400 border-violet-500/20">
                  {formatSpecialty(agent.specialty)}
                </Badge>
              </div>
            </div>
          </div>
        </div>
        {/* Pause/Resume button (A2) */}
        <Button
          size="sm"
          variant="ghost"
          disabled={agent.status === 'initializing' || agent.status === 'error' || onPauseLoading}
          onClick={() => onTogglePause(agent.id, isPaused)}
          className={`text-xs h-7 px-2 ${
            isPaused
              ? 'text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300'
              : 'text-amber-400 hover:bg-amber-500/10 hover:text-amber-300'
          }`}
          title={isPaused ? 'Resume agent' : 'Pause agent'}
        >
          {isPaused ? <PlayIcon /> : <PauseIcon />}
        </Button>
      </div>

      {/* Model + Confidence */}
      <div className="flex items-center justify-between mb-3 px-1">
        <span className="text-[11px] text-zinc-500">
          {agent.base_model || 'Default Model'}
        </span>
        <ConfidenceGauge value={data.avg_confidence} />
      </div>

      {/* Ticket stats */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="bg-[#0F0F0F] rounded-lg p-2 text-center">
          <p className="text-sm font-bold text-zinc-200">{data.tickets_assigned}</p>
          <p className="text-[10px] text-zinc-500">Assigned</p>
        </div>
        <div className="bg-[#0F0F0F] rounded-lg p-2 text-center">
          <p className="text-sm font-bold text-emerald-400">{data.tickets_resolved}</p>
          <p className="text-[10px] text-zinc-500">Resolved</p>
        </div>
        <div className="bg-[#0F0F0F] rounded-lg p-2 text-center">
          <p className="text-sm font-bold text-amber-400">{data.tickets_open}</p>
          <p className="text-[10px] text-zinc-500">Open</p>
        </div>
      </div>

      {/* Resolution Rate + CSAT */}
      <div className="flex items-center gap-4 mb-3 px-1">
        <div className="flex items-center gap-1.5">
          <BarChartIcon />
          <span className="text-[11px] text-zinc-500">Resolution:</span>
          <span className="text-xs font-semibold text-zinc-200">{data.resolution_rate.toFixed(1)}%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-zinc-500">CSAT:</span>
          <span className="text-xs font-semibold text-zinc-200">{data.csat_avg.toFixed(1)}/5</span>
        </div>
      </div>

      {/* Channels */}
      {activeChannels.length > 0 && (
        <div className="flex items-center gap-1.5 pt-2 border-t border-white/[0.04]">
          {activeChannels.map(ch => {
            const info = channelIcon(ch);
            return (
              <span
                key={ch}
                className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-medium"
                title={info.label}
              >
                {info.icon}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Comparison Table (A4) ─────────────────────────────────────────────

function ComparisonTable({ data }: { data: AgentComparisonResult }) {
  if (!data.agents || data.agents.length === 0) return null;

  const metrics = [
    { key: 'resolution_rate', label: 'Resolution Rate' },
    { key: 'csat_avg', label: 'CSAT Avg' },
    { key: 'avg_confidence', label: 'Avg Confidence' },
    { key: 'tickets_handled', label: 'Tickets Handled' },
    { key: 'avg_response_time', label: 'Avg Response Time' },
  ];

  return (
    <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b border-white/[0.06] flex items-center gap-2">
        <CompareIcon />
        <h3 className="text-sm font-semibold text-zinc-200">Agent Comparison</h3>
        <span className="text-xs text-zinc-500">({data.agents.length} agents)</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/[0.04]">
              <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-500 uppercase">Metric</th>
              {data.agents.map(a => (
                <th key={a.agent_id} className="px-4 py-2.5 text-left text-xs font-medium text-zinc-500 uppercase min-w-[140px]">
                  {a.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {metrics.map(m => (
              <tr key={m.key} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-4 py-2.5 text-xs text-zinc-400">{m.label}</td>
                {data.agents.map(a => {
                  const val = a.metrics?.[m.key];
                  const displayVal = val !== undefined && val !== null
                    ? typeof val === 'number'
                      ? m.key.includes('rate') || m.key.includes('confidence')
                        ? `${(val * 100).toFixed(1)}%`
                        : m.key === 'csat_avg'
                          ? `${val.toFixed(1)}/5`
                          : m.key.includes('time')
                            ? `${Math.round(val)}s`
                            : val.toLocaleString()
                      : String(val)
                    : '\u2014';
                  return (
                    <td key={a.agent_id} className="px-4 py-2.5 text-xs font-medium text-zinc-200">
                      {displayVal}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Add Agent Dialog (A3) ─────────────────────────────────────────────

function AddAgentDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [form, setForm] = useState<AgentCreateRequest>({
    name: '',
    specialty: 'general_support',
    description: '',
    channels: [],
    permission_level: 'standard',
    requires_approval: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleChannelToggle = (ch: string) => {
    setForm(prev => {
      const current = prev.channels || [];
      const updated = current.includes(ch)
        ? current.filter(c => c !== ch)
        : [...current, ch];
      return { ...prev, channels: updated };
    });
  };

  const handleSubmit = async () => {
    if (!form.name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await agentsApi.createAgent(form);
      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        setForm({
          name: '',
          specialty: 'general_support',
          description: '',
          channels: [],
          permission_level: 'standard',
          requires_approval: false,
        });
        onClose();
        window.location.reload();
      }, 1000);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="bg-[#1A1A1A] border-white/[0.06] max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-zinc-200">Add New Agent</DialogTitle>
          <DialogDescription className="text-zinc-500">
            Create a new AI agent with specific configuration and permissions.
          </DialogDescription>
        </DialogHeader>

        {success ? (
          <div className="flex flex-col items-center justify-center py-8 gap-3">
            <div className="w-12 h-12 rounded-full bg-emerald-500/15 flex items-center justify-center">
              <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
              </svg>
            </div>
            <p className="text-sm text-emerald-400 font-medium">Agent created successfully!</p>
          </div>
        ) : (
          <div className="space-y-4">
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                <p className="text-xs text-red-400">{error}</p>
              </div>
            )}

            {/* Name */}
            <div className="space-y-1.5">
              <Label className="text-xs text-zinc-400">Agent Name</Label>
              <Input
                value={form.name}
                onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g. BillingBot Pro"
                className="bg-[#0F0F0F] border-white/[0.06] text-zinc-200 text-sm placeholder:text-zinc-600 focus-visible:border-[#FF7F11]/50"
              />
            </div>

            {/* Specialty */}
            <div className="space-y-1.5">
              <Label className="text-xs text-zinc-400">Specialty</Label>
              <Select
                value={form.specialty}
                onValueChange={v => setForm(prev => ({ ...prev, specialty: v }))}
              >
                <SelectTrigger className="bg-[#0F0F0F] border-white/[0.06] text-zinc-200 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                  {SPECIALTY_OPTIONS.map(opt => (
                    <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <Label className="text-xs text-zinc-400">Description</Label>
              <Textarea
                value={form.description || ''}
                onChange={e => setForm(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Brief description of this agent's role..."
                rows={3}
                className="bg-[#0F0F0F] border-white/[0.06] text-zinc-200 text-sm placeholder:text-zinc-600 focus-visible:border-[#FF7F11]/50 resize-none"
              />
            </div>

            {/* Channels */}
            <div className="space-y-2">
              <Label className="text-xs text-zinc-400">Channels</Label>
              <div className="flex flex-wrap gap-2">
                {CHANNEL_OPTIONS.map(ch => (
                  <label
                    key={ch.value}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs cursor-pointer transition-colors ${
                      (form.channels || []).includes(ch.value)
                        ? 'bg-[#FF7F11]/10 border-[#FF7F11]/30 text-[#FF7F11]'
                        : 'bg-[#0F0F0F] border-white/[0.06] text-zinc-400 hover:border-white/[0.1]'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={(form.channels || []).includes(ch.value)}
                      onChange={() => handleChannelToggle(ch.value)}
                      className="sr-only"
                    />
                    {ch.label}
                  </label>
                ))}
              </div>
            </div>

            {/* Permission Level */}
            <div className="space-y-1.5">
              <Label className="text-xs text-zinc-400">Permission Level</Label>
              <Select
                value={form.permission_level || 'standard'}
                onValueChange={v => setForm(prev => ({ ...prev, permission_level: v }))}
              >
                <SelectTrigger className="bg-[#0F0F0F] border-white/[0.06] text-zinc-200 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                  {PERMISSION_OPTIONS.map(opt => (
                    <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Requires Approval */}
            <div className="flex items-center justify-between py-1">
              <Label className="text-xs text-zinc-400">Requires Human Approval</Label>
              <Switch
                checked={form.requires_approval || false}
                onCheckedChange={v => setForm(prev => ({ ...prev, requires_approval: v }))}
              />
            </div>
          </div>
        )}

        {!success && (
          <DialogFooter>
            <Button variant="ghost" onClick={onClose} className="text-zinc-400 hover:text-zinc-200 text-xs">
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!form.name.trim() || submitting}
              className="bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90 text-xs"
            >
              {submitting ? 'Creating...' : 'Create Agent'}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── Stats Strip (A6) ───────────────────────────────────────────────────

function StatsStrip({ statusCounts, agentCards }: { statusCounts: AgentStatusCounts | null; agentCards: AgentCardData[] }) {
  const totalAgents = statusCounts?.total ?? agentCards.length;
  const activeAgents = statusCounts?.active ?? agentCards.filter(a => a.agent.status === 'active').length;

  const avgConfidence = agentCards.length > 0
    ? agentCards.reduce((s, a) => s + a.avg_confidence, 0) / agentCards.length
    : 0;

  const avgResolution = agentCards.length > 0
    ? agentCards.reduce((s, a) => s + a.resolution_rate, 0) / agentCards.length
    : 0;

  const avgCsat = agentCards.length > 0
    ? agentCards.reduce((s, a) => s + a.csat_avg, 0) / agentCards.length
    : 0;

  const stats = [
    { label: 'Total Agents', value: totalAgents, icon: 'B' },
    { label: 'Active', value: activeAgents, icon: 'A', accent: true },
    { label: 'Avg Confidence', value: `${avgConfidence.toFixed(1)}%`, icon: 'C' },
    { label: 'Avg Resolution', value: `${avgResolution.toFixed(1)}%`, icon: 'R' },
    { label: 'Avg CSAT', value: `${avgCsat.toFixed(1)}/5`, icon: 'S' },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {stats.map(s => (
        <div
          key={s.label}
          className={`rounded-lg border p-3 ${
            s.accent
              ? 'border-emerald-500/20 bg-emerald-500/[0.03]'
              : 'border-white/[0.06] bg-[#1A1A1A]'
          }`}
        >
          <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-1">{s.label}</p>
          <p className={`text-lg font-bold ${s.accent ? 'text-emerald-400' : 'text-zinc-100'}`}>
            {s.value}
          </p>
        </div>
      ))}
    </div>
  );
}

// ── Loading Skeleton ───────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl p-4 space-y-3">
      <div className="flex items-start gap-3">
        <Skeleton className="w-8 h-8 rounded-lg bg-white/[0.06]" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-32 bg-white/[0.06]" />
          <Skeleton className="h-5 w-20 bg-white/[0.04]" />
        </div>
      </div>
      <Skeleton className="h-3 w-full bg-white/[0.04]" />
      <div className="grid grid-cols-3 gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 rounded-lg bg-white/[0.04]" />
        ))}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────

export default function AgentsPage() {
  const [agentCards, setAgentCards] = useState<AgentCardData[]>([]);
  const [statusCounts, setStatusCounts] = useState<AgentStatusCounts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter / search state (A5)
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [specialtyFilter, setSpecialtyFilter] = useState<string>('all');

  // Comparison mode (A4)
  const [comparisonMode, setComparisonMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [comparisonData, setComparisonData] = useState<AgentComparisonResult | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);

  // Add agent dialog (A3)
  const [addAgentOpen, setAddAgentOpen] = useState(false);

  // Pause/resume (A2)
  const [pauseLoadingId, setPauseLoadingId] = useState<string | null>(null);

  // ── Fetch Data ───────────────────────────────────────────────────

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cardsRes, countsRes] = await Promise.all([
        agentsApi.getAgentCards().catch(() => ({ agents: [], total: 0 })),
        agentsApi.getStatusCounts().catch(() => null),
      ]);
      setAgentCards(cardsRes.agents || []);
      setStatusCounts(countsRes);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const fn = async () => { await fetchData(); };
    fn();
  }, [fetchData]);

  // ── Pause/Resume Handler (A2) ────────────────────────────────────

  const handleTogglePause = useCallback(async (id: string, currentlyPaused: boolean) => {
    setPauseLoadingId(id);
    // Optimistic UI update
    setAgentCards(prev => prev.map(card =>
      card.agent.id === id
        ? { ...card, agent: { ...card.agent, status: currentlyPaused ? 'active' : 'paused' } }
        : card
    ));
    try {
      if (currentlyPaused) {
        await agentsApi.resumeAgent(id);
      } else {
        await agentsApi.pauseAgent(id);
      }
    } catch (err) {
      // Revert on error
      setAgentCards(prev => prev.map(card =>
        card.agent.id === id
          ? { ...card, agent: { ...card.agent, status: currentlyPaused ? 'paused' : 'active' } }
          : card
      ));
      console.error('Failed to toggle agent:', err);
    } finally {
      setPauseLoadingId(null);
    }
  }, []);

  // ── Comparison Handler (A4) ─────────────────────────────────────

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (next.size < 5) next.add(id);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    const fn = async () => {
      if (selectedIds.size >= 2) {
        setComparisonLoading(true);
        try {
          const result = await agentsApi.compareAgents(Array.from(selectedIds));
          setComparisonData(result);
        } catch {
          setComparisonData(null);
        } finally {
          setComparisonLoading(false);
        }
      } else {
        setComparisonData(null);
      }
    };
    fn();
  }, [selectedIds]);

  // ── Filtered Cards (A5) ─────────────────────────────────────────

  const filteredCards = useMemo(() => {
    let cards = agentCards;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      cards = cards.filter(c =>
        c.agent.name.toLowerCase().includes(q) ||
        c.agent.specialty.toLowerCase().includes(q) ||
        (c.agent.base_model || '').toLowerCase().includes(q)
      );
    }
    if (statusFilter !== 'all') {
      cards = cards.filter(c => c.agent.status === statusFilter);
    }
    if (specialtyFilter !== 'all') {
      cards = cards.filter(c => c.agent.specialty === specialtyFilter);
    }
    return cards;
  }, [agentCards, searchQuery, statusFilter, specialtyFilter]);

  // ── Render ──────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#0F0F0F]">
      {/* Page Header */}
      <div className="border-b border-white/[0.04] bg-[#0F0F0F]/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-screen-2xl mx-auto px-4 md:px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-zinc-200 flex items-center gap-2">
              <span className="text-[#FF7F11]">AI Agents</span>
              {!loading && <span className="text-xs text-zinc-500 font-normal">({agentCards.length})</span>}
            </h1>
            <p className="text-xs text-zinc-500 mt-0.5">Monitor, manage, and compare your AI workforce</p>
          </div>
          <div className="flex items-center gap-2">
            {/* Comparison Mode Toggle (A4) */}
            <Button
              size="sm"
              variant={comparisonMode ? 'default' : 'ghost'}
              onClick={() => {
                setComparisonMode(!comparisonMode);
                if (comparisonMode) {
                  setSelectedIds(new Set());
                  setComparisonData(null);
                }
              }}
              className={`text-xs h-8 ${
                comparisonMode
                  ? 'bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]'
              }`}
            >
              <CompareIcon />
              {comparisonMode ? 'Exit Compare' : 'Compare'}
              {comparisonMode && selectedIds.size > 0 && (
                <span className="ml-1.5 text-[10px] bg-white/20 px-1.5 rounded-full">{selectedIds.size}</span>
              )}
            </Button>
            {/* Add Agent Button (A3) */}
            <Button
              size="sm"
              onClick={() => setAddAgentOpen(true)}
              className="bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90 text-xs h-8"
            >
              <PlusIcon />
              Add Agent
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-screen-2xl mx-auto px-4 md:px-6 py-5 space-y-5">
        {/* Aggregate Stats Strip (A6) */}
        {!loading && agentCards.length > 0 && (
          <StatsStrip statusCounts={statusCounts} agentCards={agentCards} />
        )}

        {/* Search & Filters (A5) */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <SearchIcon />
            <div className="absolute left-8 top-1/2 -translate-y-1/2 text-zinc-500">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
              </svg>
            </div>
            <Input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search agents by name, specialty, or model..."
              className="pl-10 bg-[#1A1A1A] border-white/[0.06] text-zinc-200 text-sm placeholder:text-zinc-600 focus-visible:border-[#FF7F11]/50"
            />
          </div>
          <div className="flex gap-2">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[140px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs h-9">
                <FilterIcon />
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                <SelectItem value="all" className="text-zinc-300">All Status</SelectItem>
                {STATUS_FILTER_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={specialtyFilter} onValueChange={setSpecialtyFilter}>
              <SelectTrigger className="w-[160px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs h-9">
                <SelectValue placeholder="Specialty" />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                <SelectItem value="all" className="text-zinc-300">All Specialties</SelectItem>
                {SPECIALTY_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value} className="text-zinc-300">
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Comparison hint */}
        {comparisonMode && selectedIds.size < 2 && (
          <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-2.5">
            <svg className="w-4 h-4 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z" />
            </svg>
            <p className="text-xs text-amber-400">
              Select at least 2 agents to compare. Click on agent cards to select them.
            </p>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center">
              <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
              </svg>
            </div>
            <p className="text-sm text-red-400">{error}</p>
            <Button variant="ghost" onClick={fetchData} className="text-zinc-400 text-xs">
              Try Again
            </Button>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && filteredCards.length === 0 && agentCards.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div className="w-16 h-16 rounded-2xl bg-[#FF7F11]/10 flex items-center justify-center">
              <BotIcon />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-zinc-200">No agents yet</p>
              <p className="text-xs text-zinc-500 mt-1">Create your first AI agent to get started</p>
            </div>
            <Button
              onClick={() => setAddAgentOpen(true)}
              className="bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90 text-xs"
            >
              <PlusIcon />
              Add Your First Agent
            </Button>
          </div>
        )}

        {/* No Results State */}
        {!loading && !error && filteredCards.length === 0 && agentCards.length > 0 && (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <SearchIcon />
            <p className="text-sm text-zinc-500">No agents match your search criteria</p>
            <Button
              variant="ghost"
              onClick={() => { setSearchQuery(''); setStatusFilter('all'); setSpecialtyFilter('all'); }}
              className="text-zinc-400 text-xs"
            >
              Clear Filters
            </Button>
          </div>
        )}

        {/* Agent Cards Grid (A1) */}
        {!loading && filteredCards.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredCards.map(card => (
              <AgentCard
                key={card.agent.id}
                data={card}
                isComparing={comparisonMode}
                isSelected={selectedIds.has(card.agent.id)}
                onToggleSelect={handleToggleSelect}
                onTogglePause={handleTogglePause}
                onPauseLoading={pauseLoadingId === card.agent.id}
              />
            ))}
          </div>
        )}

        {/* Comparison Table (A4) */}
        {comparisonMode && comparisonLoading && (
          <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl p-6">
            <div className="flex items-center gap-3">
              <Skeleton className="w-9 h-9 rounded-lg bg-white/[0.06]" />
              <div className="space-y-1.5">
                <Skeleton className="h-4 w-40 bg-white/[0.06]" />
                <Skeleton className="h-3 w-24 bg-white/[0.04]" />
              </div>
            </div>
            <Skeleton className="w-full h-[200px] rounded-lg mt-4 bg-white/[0.04]" />
          </div>
        )}
        {!comparisonMode && comparisonData && selectedIds.size >= 2 && (
          <ComparisonTable data={comparisonData} />
        )}
      </div>

      {/* Add Agent Dialog (A3) */}
      <AddAgentDialog open={addAgentOpen} onClose={() => setAddAgentOpen(false)} />
    </div>
  );
}
