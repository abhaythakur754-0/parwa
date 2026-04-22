'use client';

import React, { useMemo, useState } from 'react';
import { ArrowUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { AgentMetrics } from '@/types/analytics';

interface AgentPerformanceTableProps {
  data: AgentMetrics[];
  className?: string;
}

type SortField = keyof AgentMetrics;
type SortDir = 'asc' | 'desc';

/** Format hours into human-readable string. */
function formatResolutionTime(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

/** Render a CSAT badge with color based on score. */
function CSATBadge({ avg, count }: { avg: number | null; count: number }) {
  if (count === 0 || avg == null) {
    return <span className="text-zinc-600 text-sm">N/A</span>;
  }

  const color =
    avg >= 4
      ? 'text-emerald-400 bg-emerald-500/[0.1]'
      : avg >= 3
        ? 'text-amber-400 bg-amber-500/[0.1]'
        : 'text-red-400 bg-red-500/[0.1]';

  const stars = Math.round(avg);
  const starStr = '\u2605'.repeat(stars) + '\u2606'.repeat(5 - stars);

  return (
    <div className="flex flex-col gap-0.5">
      <span className={cn('text-xs font-medium px-2 py-0.5 rounded-md w-fit', color)}>
        {avg.toFixed(1)}
      </span>
      <span className="text-[10px] text-zinc-500 leading-none">
        {starStr}{' '}
        <span className="text-zinc-600">({count})</span>
      </span>
    </div>
  );
}

/** Inline resolution rate progress bar. */
function ResolutionBar({ rate }: { rate: number }) {
  const pct = Math.min(Math.max(rate, 0), 100);
  const color =
    pct >= 80
      ? 'bg-emerald-500'
      : pct >= 50
        ? 'bg-amber-500'
        : 'bg-red-500';

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden min-w-[60px]">
        <div
          className={cn('h-full rounded-full transition-all duration-500', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-zinc-400 tabular-nums w-12 text-right">
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

/** Sort indicator icon. */
function SortIcon({ isSorted }: { isSorted: false | 'asc' | 'desc' }) {
  if (!isSorted) return <ArrowUpDown className="w-3 h-3 text-zinc-600" />;
  return (
    <ArrowUpDown
      className={cn(
        'w-3 h-3',
        isSorted === 'asc' ? 'text-orange-400 rotate-180' : 'text-orange-400'
      )}
    />
  );
}

export default function AgentPerformanceTable({
  data,
  className,
}: AgentPerformanceTableProps) {
  const [sortField, setSortField] = useState<SortField | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const sortedData = useMemo(() => {
    if (!sortField) return data;
    return [...data].sort((a, b) => {
      const aVal = a[sortField] ?? 0;
      const bVal = b[sortField] ?? 0;
      const cmp = typeof aVal === 'string' ? aVal.localeCompare(bVal as string) : (aVal as number) - (bVal as number);
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [data, sortField, sortDir]);

  type Col = { key: SortField; label: string };
  const columns: Col[] = [
    { key: 'agent_name', label: 'Agent Name' },
    { key: 'tickets_assigned', label: 'Assigned' },
    { key: 'tickets_resolved', label: 'Resolved' },
    { key: 'tickets_open', label: 'Open' },
    { key: 'resolution_rate', label: 'Resolution Rate' },
    { key: 'avg_resolution_time_hours', label: 'Avg Time' },
    { key: 'csat_avg', label: 'CSAT' },
  ];

  const renderCell = (row: AgentMetrics, col: Col) => {
    switch (col.key) {
      case 'agent_name':
        return (
          <span className="text-sm text-zinc-300 font-medium">
            {row.agent_name || 'Unknown Agent'}
          </span>
        );
      case 'tickets_assigned':
        return <span className="text-sm text-zinc-400 tabular-nums">{row.tickets_assigned}</span>;
      case 'tickets_resolved':
        return <span className="text-sm text-zinc-400 tabular-nums">{row.tickets_resolved}</span>;
      case 'tickets_open': {
        const v = row.tickets_open;
        return (
          <span className={cn('text-sm tabular-nums', v > 0 ? 'text-amber-400' : 'text-zinc-600')}>
            {v}
          </span>
        );
      }
      case 'resolution_rate':
        return <ResolutionBar rate={row.resolution_rate} />;
      case 'avg_resolution_time_hours':
        return (
          <span className="text-sm text-zinc-400 tabular-nums">
            {row.avg_resolution_time_hours != null ? formatResolutionTime(row.avg_resolution_time_hours) : '\u2014'}
          </span>
        );
      case 'csat_avg':
        return <CSATBadge avg={row.csat_avg} count={row.csat_count} />;
      default:
        return null;
    }
  };

  return (
    <div className={cn('rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6', className)}>
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-zinc-300">Agent Performance</h3>
        <p className="text-xs text-zinc-600 mt-0.5">Individual metrics per support agent</p>
      </div>

      {data.length === 0 ? (
        <div className="text-center py-12 text-zinc-600 text-sm">
          <p>No agent data available for this period</p>
          <p className="text-xs text-zinc-700 mt-1">
            Agent metrics will appear once agents start resolving tickets
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-white/[0.04]">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className="px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider whitespace-nowrap"
                  >
                    <button
                      className="flex items-center gap-1.5 hover:text-zinc-200 transition-colors"
                      onClick={() => handleSort(col.key)}
                    >
                      {col.label}
                      <SortIcon isSorted={sortField === col.key ? sortDir : false} />
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedData.map((row, rowIndex) => (
                <tr
                  key={row.agent_id || rowIndex}
                  className={cn(
                    'border-b border-white/[0.03] transition-colors',
                    'hover:bg-white/[0.02]',
                    rowIndex % 2 === 1 && 'bg-white/[0.01]'
                  )}
                >
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-3 whitespace-nowrap">
                      {renderCell(row, col)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
