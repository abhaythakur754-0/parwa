'use client';

import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from 'recharts';
import { cn } from '@/lib/utils';
import type { SLAMetrics } from '@/types/analytics';

interface SLAChartProps {
  data: SLAMetrics;
  className?: string;
}

function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

export default function SLAChart({ data, className }: SLAChartProps) {
  const { breached_count, approaching_count, compliant_count, compliance_rate } = data;

  const pieData = React.useMemo(() => {
    const total = breached_count + approaching_count + compliant_count;
    if (total === 0) {
      return [
        { name: 'Compliant', value: 1, color: '#34d399', real: false },
      ];
    }
    return [
      { name: 'Compliant', value: compliant_count, color: '#34d399', real: true },
      { name: 'Approaching', value: approaching_count, color: '#fbbf24', real: true },
      { name: 'Breached', value: breached_count, color: '#ef4444', real: true },
    ].filter((d) => d.value > 0);
  }, [breached_count, approaching_count, compliant_count]);

  const totalWithSLA = data.total_tickets_with_sla || 1;

  return (
    <div
      className={cn(
        'rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6',
        className
      )}
    >
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-zinc-300">SLA Compliance</h3>
        <p className="text-xs text-zinc-600 mt-0.5">Service level adherence</p>
      </div>

      {/* Donut Gauge */}
      <div className="relative flex justify-center">
        <ResponsiveContainer width={180} height={180}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={58}
              outerRadius={78}
              dataKey="value"
              startAngle={90}
              endAngle={-270}
              paddingAngle={2}
              animationBegin={0}
              animationDuration={800}
            >
              {pieData.map((entry, index) => (
                <Cell
                  key={`sla-cell-${index}`}
                  fill={entry.color}
                  opacity={entry.real ? 0.85 : 0.12}
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>

        {/* Center text */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center">
            <span className="text-2xl font-bold text-white">
              {compliance_rate.toFixed(0)}%
            </span>
            <p className="text-[10px] text-zinc-500 mt-0.5">compliance</p>
          </div>
        </div>
      </div>

      {/* SLA Breakdown Stats */}
      <div className="grid grid-cols-3 gap-3 mt-4">
        <div className="rounded-lg bg-red-500/[0.08] border border-red-500/[0.12] p-3 text-center">
          <p className="text-lg font-bold text-red-400">{breached_count}</p>
          <p className="text-[10px] text-red-400/70 uppercase tracking-wide mt-0.5">
            Breached
          </p>
        </div>
        <div className="rounded-lg bg-amber-500/[0.08] border border-amber-500/[0.12] p-3 text-center">
          <p className="text-lg font-bold text-amber-400">{approaching_count}</p>
          <p className="text-[10px] text-amber-400/70 uppercase tracking-wide mt-0.5">
            Approaching
          </p>
        </div>
        <div className="rounded-lg bg-emerald-500/[0.08] border border-emerald-500/[0.12] p-3 text-center">
          <p className="text-lg font-bold text-emerald-400">{compliant_count}</p>
          <p className="text-[10px] text-emerald-400/70 uppercase tracking-wide mt-0.5">
            Compliant
          </p>
        </div>
      </div>

      {/* Avg times */}
      <div className="grid grid-cols-2 gap-3 mt-3">
        <div className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-3 py-2">
          <div className="w-1.5 h-1.5 rounded-full bg-orange-500" />
          <div>
            <p className="text-xs text-zinc-500">Avg First Response</p>
            <p className="text-sm font-medium text-zinc-300">
              {data.avg_first_response_minutes != null ? formatMinutes(data.avg_first_response_minutes) : '—'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-3 py-2">
          <div className="w-1.5 h-1.5 rounded-full bg-sky-500" />
          <div>
            <p className="text-xs text-zinc-500">Avg Resolution</p>
            <p className="text-sm font-medium text-zinc-300">
              {data.avg_resolution_minutes != null ? formatMinutes(data.avg_resolution_minutes) : '—'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
