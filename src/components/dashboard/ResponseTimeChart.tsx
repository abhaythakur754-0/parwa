'use client';

import React, { useState, useEffect } from 'react';
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
import type { ResponseTimeBucket, ResponseTimeDistribution } from '@/types/analytics';
import { analyticsApi } from '@/lib/analytics-api';
import type { DateRange } from '@/types/analytics';

interface ResponseTimeChartProps {
  dateRange?: Partial<DateRange>;
  className?: string;
}

/** Color each bar based on response time urgency. */
function getBarColor(index: number, total: number): string {
  // Gradient from green (fast) through amber to red (slow)
  if (total <= 1) return '#34d399';
  const ratio = index / (total - 1);
  if (ratio < 0.3) return '#34d399'; // emerald - fast
  if (ratio < 0.5) return '#fbbf24'; // amber - moderate
  if (ratio < 0.7) return '#f97316'; // orange - slow
  return '#ef4444'; // red - very slow
}

/** Custom dark tooltip. */
function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ResponseTimeBucket; value: number }>;
}) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;

  return (
    <div className="rounded-lg border border-white/[0.08] bg-[#222]/95 px-3 py-2 shadow-xl backdrop-blur-sm">
      <p className="text-sm font-semibold text-white">{item.label}</p>
      <p className="text-xs text-zinc-400 mt-1">
        {item.count.toLocaleString()} tickets
      </p>
    </div>
  );
}

export default function ResponseTimeChart({
  dateRange,
  className,
}: ResponseTimeChartProps) {
  const [distData, setDistData] = useState<ResponseTimeDistribution | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Track dateRange as a string for stable comparison
  const rangeKey = dateRange
    ? `${dateRange.start_date || ''}-${dateRange.end_date || ''}`
    : 'initial';

  useEffect(() => {
    let cancelled = false;

    // Mark loading at the start of fetch (in async callback, not synchronously)
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const result = await analyticsApi.getResponseTime(dateRange);
        if (!cancelled) {
          setDistData(result);
        }
      } catch {
        if (!cancelled) {
          setDistData(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      cancelled = true;
    };
  }, [rangeKey, dateRange]);

  // Use real data if available, otherwise show empty chart
  const chartData = React.useMemo(() => {
    return distData?.buckets ?? [];
  }, [distData]);

  const avgResp = distData?.avg_response_minutes ?? 0;
  const medianResp = distData?.median_response_minutes ?? 0;
  const p95Resp = distData?.p95_response_minutes ?? 0;

  function formatMinutes(m: number): string {
    if (m < 60) return `${Math.round(m)}m`;
    const h = Math.floor(m / 60);
    const mins = Math.round(m % 60);
    return mins > 0 ? `${h}h ${mins}m` : `${h}h`;
  }

  return (
    <div
      className={cn(
        'rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6',
        className
      )}
    >
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-zinc-300">
          Response Time Distribution
        </h3>
        <p className="text-xs text-zinc-600 mt-0.5">
          How quickly tickets get first responses
        </p>
      </div>

      {isLoading ? (
        <div className="h-[220px] flex items-center justify-center text-zinc-600 text-sm animate-pulse">
          Loading response times…
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={chartData}
              margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
            >
              <defs>
                {chartData.map((_, index) => (
                  <linearGradient
                    key={`bar-grad-${index}`}
                    id={`barGrad-${index}`}
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stopColor={getBarColor(index, chartData.length)}
                      stopOpacity={0.9}
                    />
                    <stop
                      offset="100%"
                      stopColor={getBarColor(index, chartData.length)}
                      stopOpacity={0.4}
                    />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#ffffff06"
                vertical={false}
              />
              <XAxis
                dataKey="label"
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
              <Bar
                dataKey="count"
                radius={[4, 4, 0, 0]}
                maxBarSize={40}
              >
                {chartData.map((_, index) => (
                  <Cell
                    key={`bar-${index}`}
                    fill={`url(#barGrad-${index})`}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Summary stats */}
          <div className="grid grid-cols-3 gap-3 mt-4">
            <div className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-3 py-2">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <div>
                <p className="text-[10px] text-zinc-500 uppercase">Avg</p>
                <p className="text-sm font-medium text-zinc-300">
                  {avgResp > 0 ? formatMinutes(avgResp) : '—'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-3 py-2">
              <div className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              <div>
                <p className="text-[10px] text-zinc-500 uppercase">Median</p>
                <p className="text-sm font-medium text-zinc-300">
                  {medianResp > 0 ? formatMinutes(medianResp) : '—'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-3 py-2">
              <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
              <div>
                <p className="text-[10px] text-zinc-500 uppercase">P95</p>
                <p className="text-sm font-medium text-zinc-300">
                  {p95Resp > 0 ? formatMinutes(p95Resp) : '—'}
                </p>
              </div>
            </div>
          </div>

          {chartData.length === 0 && !isLoading && (
            <p className="text-xs text-zinc-600 text-center mt-3">
              No response time data yet — data will appear once tickets are processed.
            </p>
          )}
        </>
      )}
    </div>
  );
}
