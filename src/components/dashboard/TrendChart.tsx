'use client';

import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { cn } from '@/lib/utils';
import type { TrendPoint } from '@/types/analytics';

interface TrendChartProps {
  data: TrendPoint[];
  className?: string;
}

/** Format a timestamp for the X-axis label. */
function formatTick(timestamp: string): string {
  try {
    return format(parseISO(timestamp), 'MMM d');
  } catch {
    return timestamp.slice(0, 10);
  }
}

/** Custom dark-theme tooltip. */
function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  let dateStr = label ?? '';
  try {
    dateStr = format(parseISO(dateStr), 'MMMM d, yyyy');
  } catch {
    // keep original
  }

  return (
    <div className="rounded-lg border border-white/[0.08] bg-[#222]/95 px-3 py-2 shadow-xl backdrop-blur-sm">
      <p className="text-xs text-zinc-400 mb-1">{dateStr}</p>
      <p className="text-sm font-semibold text-white">
        {payload[0].value.toLocaleString()} tickets
      </p>
    </div>
  );
}

export default function TrendChart({ data, className }: TrendChartProps) {
  const chartData = React.useMemo(() => {
    if (!data?.length) return [];
    return data.map((p) => ({
      ...p,
      dateLabel: formatTick(p.timestamp),
    }));
  }, [data]);

  return (
    <div
      className={cn(
        'rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6',
        className
      )}
    >
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-zinc-300">Ticket Trends</h3>
        <p className="text-xs text-zinc-600 mt-0.5">Volume over time</p>
      </div>

      {chartData.length === 0 ? (
        <div className="h-[260px] flex items-center justify-center text-zinc-600 text-sm">
          No trend data available for the selected period
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart
            data={chartData}
            margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
          >
            <defs>
              <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f97316" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#f97316" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#ffffff06"
              vertical={false}
            />
            <XAxis
              dataKey="dateLabel"
              tick={{ fill: '#71717a', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              dy={8}
            />
            <YAxis
              tick={{ fill: '#71717a', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              dx={-4}
              allowDecimals={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={false} />
            <Area
              type="monotone"
              dataKey="count"
              stroke="#f97316"
              strokeWidth={2}
              fill="url(#trendGradient)"
              dot={false}
              activeDot={{
                r: 4,
                fill: '#f97316',
                stroke: '#1A1A1A',
                strokeWidth: 2,
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
