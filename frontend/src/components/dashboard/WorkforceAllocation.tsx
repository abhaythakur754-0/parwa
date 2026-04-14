'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { get } from '@/lib/api';

// ── Types ─────────────────────────────────────────────────────────────

interface WorkforceSplit {
  period: string;
  date: string;
  ai_tickets: number;
  human_tickets: number;
  ai_pct: number;
  human_pct: number;
  total: number;
}

interface WorkforceData {
  current_split: WorkforceSplit;
  daily_trend: WorkforceSplit[];
  by_channel: Record<string, WorkforceSplit>;
  by_category: Array<{
    category: string;
    total_tickets: number;
    ai_tickets: number;
    human_tickets: number;
    ai_pct: number;
    human_pct: number;
  }>;
  ai_resolution_rate: number;
  human_resolution_rate: number;
}

// ── Props ─────────────────────────────────────────────────────────────

interface WorkforceAllocationProps {
  initialData?: Partial<WorkforceData>;
  className?: string;
}

// ── Channel Icons ─────────────────────────────────────────────────────

const CHANNEL_ICONS: Record<string, { icon: string; label: string }> = {
  email: { icon: 'Email', label: 'Email' },
  chat: { icon: 'Chat', label: 'Chat' },
  sms: { icon: 'SMS', label: 'SMS' },
  whatsapp: { icon: 'WA', label: 'WhatsApp' },
  voice: { icon: 'Voice', label: 'Voice' },
  widget: { icon: 'Widget', label: 'Widget' },
};

// ── WorkforceAllocation Component ─────────────────────────────────────

export default function WorkforceAllocation({
  initialData,
  className,
}: WorkforceAllocationProps) {
  const [data, setData] = useState<WorkforceData | null>(null);
  const [isLoading, setIsLoading] = useState(!initialData);
  const [activeTab, setActiveTab] = useState<'overview' | 'channels' | 'categories'>('overview');

  // Fetch workforce data
  const fetchWorkforce = useCallback(async () => {
    try {
      setIsLoading(true);
      const result = await get<WorkforceData>('/api/analytics/workforce?days=30');
      setData(result);
    } catch (error) {
      console.error('Failed to fetch workforce data:', error);
      if (initialData) {
        setData(initialData as WorkforceData);
      }
    } finally {
      setIsLoading(false);
    }
  }, [initialData]);

  useEffect(() => {
    if (initialData && Object.keys(initialData).length > 0) {
      setData(initialData as WorkforceData);
      setIsLoading(false);
    } else {
      fetchWorkforce();
    }
  }, [fetchWorkforce, initialData]);

  const d = data;

  return (
    <div className={cn(
      'rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden',
      className
    )}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-[#FF7F11]/10 flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-[#FF7F11]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-zinc-300">Workforce Allocation</h3>
        </div>

        <div className="flex items-center gap-0.5 bg-white/[0.03] rounded-lg p-0.5">
          {(['overview', 'channels', 'categories'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'px-2 py-1 text-[11px] font-medium rounded-md transition-all duration-150 capitalize',
                activeTab === tab
                  ? 'bg-[#FF7F11]/15 text-[#FF7F11]'
                  : 'text-zinc-500 hover:text-zinc-400'
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {isLoading ? (
          <div className="space-y-4 animate-pulse">
            <div className="h-8 w-full bg-white/[0.06] rounded" />
            <div className="grid grid-cols-2 gap-3">
              <div className="h-16 bg-white/[0.06] rounded-lg" />
              <div className="h-16 bg-white/[0.06] rounded-lg" />
            </div>
          </div>
        ) : !d ? (
          <div className="text-center py-8">
            <p className="text-sm text-zinc-600">No allocation data yet</p>
            <p className="text-xs text-zinc-700 mt-1">Data will appear as tickets are assigned</p>
          </div>
        ) : activeTab === 'overview' ? (
          <OverviewTab data={d} />
        ) : activeTab === 'channels' ? (
          <ChannelsTab data={d} />
        ) : (
          <CategoriesTab data={d} />
        )}
      </div>
    </div>
  );
}

// ── Overview Tab ──────────────────────────────────────────────────────

function OverviewTab({ data }: { data: WorkforceData }) {
  const { current_split, ai_resolution_rate, human_resolution_rate } = data;
  const total = current_split.total;

  return (
    <div className="space-y-4">
      {/* Donut-style bar */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-zinc-500">AI vs Human Split</span>
          <span className="text-xs text-zinc-600">{total} total tickets</span>
        </div>

        {/* Stacked bar */}
        <div className="h-3 rounded-full overflow-hidden flex bg-white/[0.05]">
          <div
            className="h-full bg-gradient-to-r from-[#FF7F11] to-[#FF7F11]/70 transition-all duration-700 rounded-l-full"
            style={{ width: `${current_split.ai_pct}%` }}
          />
          <div
            className="h-full bg-zinc-600/50 transition-all duration-700 rounded-r-full"
            style={{ width: `${current_split.human_pct}%` }}
          />
        </div>

        {/* Legend */}
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-sm bg-[#FF7F11]" />
            <span className="text-xs text-zinc-400">
              AI: <span className="text-white font-medium">{current_split.ai_pct}%</span>
            </span>
            <span className="text-[11px] text-zinc-600">({current_split.ai_tickets})</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-sm bg-zinc-600" />
            <span className="text-xs text-zinc-400">
              Human: <span className="text-white font-medium">{current_split.human_pct}%</span>
            </span>
            <span className="text-[11px] text-zinc-600">({current_split.human_tickets})</span>
          </div>
        </div>
      </div>

      {/* Resolution Rate Comparison */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-white/[0.03] border border-white/[0.04] p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <div className="w-2 h-2 rounded-full bg-[#FF7F11]" />
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider">AI Resolution</span>
          </div>
          <p className="text-lg font-bold text-white tabular-nums">{ai_resolution_rate}%</p>
        </div>
        <div className="rounded-lg bg-white/[0.03] border border-white/[0.04] p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <div className="w-2 h-2 rounded-full bg-zinc-500" />
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider">Human Resolution</span>
          </div>
          <p className="text-lg font-bold text-white tabular-nums">{human_resolution_rate}%</p>
        </div>
      </div>

      {/* Mini sparkline (last 7 days) */}
      {data.daily_trend.length > 0 && (
        <div>
          <p className="text-[11px] text-zinc-500 mb-2">Daily Trend (Last 7 days)</p>
          <div className="flex items-end gap-1 h-12">
            {data.daily_trend.slice(-7).map((day, i) => {
              const maxTotal = Math.max(...data.daily_trend.slice(-7).map(d => d.total), 1);
              const height = Math.max((day.total / maxTotal) * 100, 4);
              return (
                <div key={day.date} className="flex-1 flex flex-col items-center gap-0.5">
                  <div className="w-full flex flex-col" style={{ height: '40px' }}>
                    <div
                      className="w-full bg-[#FF7F11]/40 rounded-t-sm transition-all duration-300"
                      style={{ height: `${(day.ai_pct / 100) * height}%` }}
                    />
                    <div
                      className="w-full bg-zinc-600/40 rounded-b-sm transition-all duration-300"
                      style={{ height: `${(day.human_pct / 100) * height}%` }}
                    />
                  </div>
                  <span className="text-[9px] text-zinc-700">
                    {new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' }).charAt(0)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Channels Tab ──────────────────────────────────────────────────────

function ChannelsTab({ data }: { data: WorkforceData }) {
  const channels = Object.entries(data.by_channel);

  if (channels.length === 0) {
    return (
      <div className="text-center py-6">
        <p className="text-sm text-zinc-600">No channel data yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-3 max-h-[280px] overflow-y-auto scrollbar-thin">
      {channels.map(([channel, split]) => {
        const info = CHANNEL_ICONS[channel] || { icon: channel, label: channel };
        return (
          <div key={channel} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-zinc-400">{info.label}</span>
                <span className="text-[11px] text-zinc-600">{split.total} tickets</span>
              </div>
              <span className="text-[11px] text-[#FF7F11] font-medium">{split.ai_pct}% AI</span>
            </div>
            <div className="h-1.5 bg-white/[0.05] rounded-full overflow-hidden flex">
              <div
                className="h-full bg-[#FF7F11]/60 rounded-l-full transition-all duration-500"
                style={{ width: `${split.ai_pct}%` }}
              />
              <div
                className="h-full bg-zinc-600/40 rounded-r-full transition-all duration-500"
                style={{ width: `${split.human_pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Categories Tab ────────────────────────────────────────────────────

function CategoriesTab({ data }: { data: WorkforceData }) {
  if (data.by_category.length === 0) {
    return (
      <div className="text-center py-6">
        <p className="text-sm text-zinc-600">No category data yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-3 max-h-[280px] overflow-y-auto scrollbar-thin">
      {data.by_category.map((cat) => (
        <div key={cat.category} className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-zinc-400">{cat.category}</span>
              <span className="text-[11px] text-zinc-600">{cat.total_tickets}</span>
            </div>
            <span className="text-[11px] text-[#FF7F11] font-medium">{cat.ai_pct}% AI</span>
          </div>
          <div className="h-1.5 bg-white/[0.05] rounded-full overflow-hidden flex">
            <div
              className="h-full bg-[#FF7F11]/60 rounded-l-full transition-all duration-500"
              style={{ width: `${cat.ai_pct}%` }}
            />
            <div
              className="h-full bg-zinc-600/40 rounded-r-full transition-all duration-500"
              style={{ width: `${cat.human_pct}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
