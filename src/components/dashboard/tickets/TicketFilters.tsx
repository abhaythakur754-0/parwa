'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { TicketFilters, TicketChannel, TicketPriority, TicketStatus } from '@/types/ticket';
import { mockAgents } from '@/lib/mock/ticket-mock-data';

interface TicketFiltersBarProps {
  filters: Partial<TicketFilters>;
  onChange: (filters: Partial<TicketFilters>) => void;
  className?: string;
}

const statusOptions: { value: TicketStatus; label: string; color: string }[] = [
  { value: 'open', label: 'Open', color: 'bg-blue-500/15 text-blue-400' },
  { value: 'in_progress', label: 'In Progress', color: 'bg-amber-500/15 text-amber-400' },
  { value: 'awaiting_customer', label: 'Awaiting Customer', color: 'bg-purple-500/15 text-purple-400' },
  { value: 'escalated', label: 'Escalated', color: 'bg-red-500/15 text-red-400' },
  { value: 'resolved', label: 'Resolved', color: 'bg-emerald-500/15 text-emerald-400' },
  { value: 'closed', label: 'Closed', color: 'bg-zinc-500/15 text-zinc-400' },
];

const channelOptions: { value: TicketChannel; label: string }[] = [
  { value: 'email', label: 'Email' },
  { value: 'chat', label: 'Chat' },
  { value: 'sms', label: 'SMS' },
  { value: 'voice', label: 'Voice' },
  { value: 'slack', label: 'Slack' },
  { value: 'webchat', label: 'Webchat' },
];

const priorityOptions: { value: TicketPriority; label: string; color: string }[] = [
  { value: 'critical', label: 'Critical', color: 'bg-red-500/15 text-red-400' },
  { value: 'high', label: 'High', color: 'bg-orange-500/15 text-orange-400' },
  { value: 'medium', label: 'Medium', color: 'bg-amber-500/15 text-amber-400' },
  { value: 'low', label: 'Low', color: 'bg-zinc-500/15 text-zinc-400' },
];

const confidenceRanges = [
  { label: 'High (80%+)', min: 0.8, max: 1 },
  { label: 'Medium (60-79%)', min: 0.6, max: 0.79 },
  { label: 'Low (<60%)', min: 0, max: 0.59 },
];

function FilterPill({
  label,
  active,
  onClick,
  color,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  color?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-2.5 py-1 rounded-lg text-xs font-medium transition-all whitespace-nowrap',
        active
          ? color || 'bg-orange-500/15 text-orange-400 border border-orange-500/25'
          : 'bg-white/[0.03] text-zinc-500 border border-white/[0.06] hover:bg-white/[0.06] hover:text-zinc-300'
      )}
    >
      {label}
    </button>
  );
}

export default function TicketFiltersBar({ filters, onChange, className }: TicketFiltersBarProps) {
  const toggleStatus = (s: TicketStatus) => {
    const current = filters.status || [];
    const next = current.includes(s) ? current.filter((x) => x !== s) : [...current, s];
    onChange({ ...filters, status: next.length ? next : undefined });
  };

  const toggleChannel = (c: TicketChannel) => {
    const current = filters.channel || [];
    const next = current.includes(c) ? current.filter((x) => x !== c) : [...current, c];
    onChange({ ...filters, channel: next.length ? next : undefined });
  };

  const togglePriority = (p: TicketPriority) => {
    const current = filters.priority || [];
    const next = current.includes(p) ? current.filter((x) => x !== p) : [...current, p];
    onChange({ ...filters, priority: next.length ? next : undefined });
  };

  const toggleAgent = (a: string) => {
    const current = filters.agent_id || [];
    const next = current.includes(a) ? current.filter((x) => x !== a) : [...current, a];
    onChange({ ...filters, agent_id: next.length ? next : undefined });
  };

  const setConfidenceRange = (min: number, max: number) => {
    const isActive = filters.ai_confidence_min === min && filters.ai_confidence_max === max;
    onChange({
      ...filters,
      ai_confidence_min: isActive ? undefined : min,
      ai_confidence_max: isActive ? undefined : max,
    });
  };

  const setDateFrom = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...filters, date_from: e.target.value || undefined });
  };

  const setDateTo = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...filters, date_to: e.target.value || undefined });
  };

  const clearAll = () => {
    onChange({});
  };

  const hasActiveFilters = !!(filters.status?.length || filters.channel?.length || filters.priority?.length || filters.agent_id?.length || filters.ai_confidence_min !== undefined || filters.date_from || filters.date_to);

  return (
    <div className={cn('space-y-3', className)}>
      {/* Filter rows */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Status */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mr-1">Status</span>
          {statusOptions.map((opt) => (
            <FilterPill
              key={opt.value}
              label={opt.label}
              active={filters.status?.includes(opt.value) || false}
              onClick={() => toggleStatus(opt.value)}
              color={opt.color}
            />
          ))}
        </div>

        <div className="w-px h-5 bg-white/[0.06] hidden sm:block" />

        {/* Priority */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mr-1">Priority</span>
          {priorityOptions.map((opt) => (
            <FilterPill
              key={opt.value}
              label={opt.label}
              active={filters.priority?.includes(opt.value) || false}
              onClick={() => togglePriority(opt.value)}
              color={opt.color}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Channel */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mr-1">Channel</span>
          {channelOptions.map((opt) => (
            <FilterPill
              key={opt.value}
              label={opt.label}
              active={filters.channel?.includes(opt.value) || false}
              onClick={() => toggleChannel(opt.value)}
            />
          ))}
        </div>

        <div className="w-px h-5 bg-white/[0.06] hidden sm:block" />

        {/* Agent */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mr-1">Agent</span>
          {mockAgents.map((agent) => (
            <FilterPill
              key={agent.id}
              label={agent.name.split(' ')[0]}
              active={filters.agent_id?.includes(agent.id) || false}
              onClick={() => toggleAgent(agent.id)}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Confidence */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mr-1">Confidence</span>
          {confidenceRanges.map((range) => (
            <FilterPill
              key={range.label}
              label={range.label}
              active={filters.ai_confidence_min === range.min && filters.ai_confidence_max === range.max}
              onClick={() => setConfidenceRange(range.min, range.max)}
            />
          ))}
        </div>

        <div className="w-px h-5 bg-white/[0.06] hidden sm:block" />

        {/* Date Range */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mr-1">Date</span>
          <input
            type="date"
            value={filters.date_from || ''}
            onChange={setDateFrom}
            className="h-7 px-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-xs text-zinc-300 focus:outline-none focus:border-orange-500/40 transition-all"
          />
          <span className="text-xs text-zinc-600">→</span>
          <input
            type="date"
            value={filters.date_to || ''}
            onChange={setDateTo}
            className="h-7 px-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-xs text-zinc-300 focus:outline-none focus:border-orange-500/40 transition-all"
          />
        </div>

        {/* Clear */}
        {hasActiveFilters && (
          <button
            onClick={clearAll}
            className="ml-auto px-2.5 py-1 rounded-lg text-xs font-medium text-red-400/70 hover:text-red-400 hover:bg-red-500/10 transition-all"
          >
            Clear all
          </button>
        )}
      </div>
    </div>
  );
}
