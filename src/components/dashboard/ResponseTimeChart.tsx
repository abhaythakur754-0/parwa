'use client';

import React, { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { cn } from '@/lib/utils';
import { analyticsApi } from '@/lib/analytics-api';
import type { DateRange, ResponseTimeDistribution } from '@/types/analytics';

interface ResponseTimeChartProps {
  dateRange?: Partial<DateRange>;
  className?: string;
}

const BUCKET_COLORS: Record<string, string> = {
  '< 5 min': '#34d399',
  '5 - 15 min': '#6ee7b7',
  '15 - 30 min': '#fbbf24',
  '30 - 60 min': '#f59e0b',
  '1 - 2 hrs': '#f97316',
  '2 - 4 hrs': '#ef4444',
  '> 4 hrs': '#dc2626',
};

export default function ResponseTimeChart({ dateRange, className }: ResponseTimeChartProps) {
  const [data, setData] = useState<ResponseTimeDistribution | null>(null);
  const [status, setStatus] = useState<'loading' | 'error' | 'success'>('loading');

  useEffect(() => {
    let cancelled = false;
    async function fetch() {
      try {
        setStatus('loading');
        const result = await analyticsApi.getResponseTime(dateRange);
        if (!cancelled) {
          setData(result);
          setStatus('success');
        }
      } catch {
        if (!cancelled) setStatus('error');
      }
    }
    fetch();
    return () => { cancelled = true; };
  }, [dateRange?.start_date, dateRange?.end_date]);

  const formatMinutes = (mins: number): string => {
    if (mins < 60) return `${Math.round(mins)}m`;
    const h = Math.floor(mins / 60);
    const m = Math.round(mins % 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  };

  if (status === 'loading') {
    return (
      <div className={cn('rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6', className)}>
        <div className="animate-pulse space-y-4">
          <div className="h-4 w-40 bg-white/[0.06] rounded" />
          <div className="h-4 w-56 bg-white/[0.04] rounded" />
          <div className="h-48 bg-white/[0.03] rounded-lg" />
        </div>
      </div>
    );
  }

  if (status === 'error' || !data) {
    return (
      <div className={cn('rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6', className)}>
        <h3 className="text-sm font-semibold text-zinc-300">Response Time Distribution</h3>
        <p className="text-xs text-zinc-500 mt-0.5">How quickly tickets get responded to</p>
        <div className="flex items-center justify-center h-48 text-xs text-zinc-600">
          Could not load response time data
        </div>
      </div>
    );
  }

  const hasData = data.buckets && data.buckets.length > 0 && data.buckets.some((b) => b.count > 0);

  return (
    <div className={cn('rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6', className)}>
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-zinc-300">Response Time Distribution</h3>
        <p className="text-xs text-zinc-500 mt-0.5">How quickly tickets get responded to</p>
      </div>

      {hasData ? (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data.buckets} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="bucket"
              tick={{ fill: '#71717a', fontSize: 10 }}
              axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#71717a', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#27272a',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                fontSize: '12px',
                color: '#e4e4e7',
              }}
              cursor={{ fill: 'rgba(255,255,255,0.03)' }}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={40}>
              {data.buckets.map((entry, index) => (
                <Cell
                  key={`rt-cell-${index}`}
                  fill={BUCKET_COLORS[entry.bucket] || '#71717a'}
                  opacity={0.8}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex items-center justify-center h-48 text-xs text-zinc-600">
          No response time data for this period
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3 mt-4">
        <div className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-3 py-2">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <div>
            <p className="text-[10px] text-zinc-500">Avg</p>
            <p className="text-sm font-medium text-zinc-300">
              {data.avg_response_minutes != null ? formatMinutes(data.avg_response_minutes) : '—'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-3 py-2">
          <div className="w-1.5 h-1.5 rounded-full bg-sky-400" />
          <div>
            <p className="text-[10px] text-zinc-500">Median</p>
            <p className="text-sm font-medium text-zinc-300">
              {data.median_response_minutes != null ? formatMinutes(data.median_response_minutes) : '—'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-3 py-2">
          <div className="w-1.5 h-1.5 rounded-full bg-amber-400" />
          <div>
            <p className="text-[10px] text-zinc-500">P95</p>
            <p className="text-sm font-medium text-zinc-300">
              {data.p95_response_minutes != null ? formatMinutes(data.p95_response_minutes) : '—'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}