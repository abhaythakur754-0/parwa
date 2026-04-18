'use client';

import React, { useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table';
import { ArrowUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { AgentMetrics } from '@/types/analytics';

interface AgentPerformanceTableProps {
  data: AgentMetrics[];
  className?: string;
}

type ColumnSortable = {
  enableSorting: true;
};

const columnHelper = createColumnHelper<AgentMetrics>();

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
  const starStr = '★'.repeat(stars) + '☆'.repeat(5 - stars);

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
  const [sorting, setSorting] = React.useState<SortingState>([]);

  const columns = useMemo(
    () => [
      columnHelper.accessor('agent_name', {
        header: ({ column }) => (
          <button
            className="flex items-center gap-1.5 hover:text-zinc-200 transition-colors"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Agent Name
            <SortIcon isSorted={column.getIsSorted()} />
          </button>
        ),
        cell: ({ getValue }) => (
          <span className="text-sm text-zinc-300 font-medium">
            {getValue() || 'Unknown Agent'}
          </span>
        ),
      } as ColumnSortable & ReturnType<typeof columnHelper.accessor<'agent_name'>>),

      columnHelper.accessor('tickets_assigned', {
        header: ({ column }) => (
          <button
            className="flex items-center gap-1.5 hover:text-zinc-200 transition-colors"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Assigned
            <SortIcon isSorted={column.getIsSorted()} />
          </button>
        ),
        cell: ({ getValue }) => (
          <span className="text-sm text-zinc-400 tabular-nums">{getValue()}</span>
        ),
      } as ColumnSortable & ReturnType<typeof columnHelper.accessor<'tickets_assigned'>>),

      columnHelper.accessor('tickets_resolved', {
        header: ({ column }) => (
          <button
            className="flex items-center gap-1.5 hover:text-zinc-200 transition-colors"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Resolved
            <SortIcon isSorted={column.getIsSorted()} />
          </button>
        ),
        cell: ({ getValue }) => (
          <span className="text-sm text-zinc-400 tabular-nums">{getValue()}</span>
        ),
      } as ColumnSortable & ReturnType<typeof columnHelper.accessor<'tickets_resolved'>>),

      columnHelper.accessor('tickets_open', {
        header: ({ column }) => (
          <button
            className="flex items-center gap-1.5 hover:text-zinc-200 transition-colors"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Open
            <SortIcon isSorted={column.getIsSorted()} />
          </button>
        ),
        cell: ({ getValue }) => {
          const v = getValue() as number;
          return (
            <span
              className={cn(
                'text-sm tabular-nums',
                v > 0 ? 'text-amber-400' : 'text-zinc-600'
              )}
            >
              {v}
            </span>
          );
        },
      } as ColumnSortable & ReturnType<typeof columnHelper.accessor<'tickets_open'>>),

      columnHelper.accessor('resolution_rate', {
        header: ({ column }) => (
          <button
            className="flex items-center gap-1.5 hover:text-zinc-200 transition-colors"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Resolution Rate
            <SortIcon isSorted={column.getIsSorted()} />
          </button>
        ),
        cell: ({ getValue }) => <ResolutionBar rate={getValue() as number} />,
      } as ColumnSortable & ReturnType<typeof columnHelper.accessor<'resolution_rate'>>),

      columnHelper.accessor('avg_resolution_time_hours', {
        header: ({ column }) => (
          <button
            className="flex items-center gap-1.5 hover:text-zinc-200 transition-colors"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            Avg Time
            <SortIcon isSorted={column.getIsSorted()} />
          </button>
        ),
        cell: ({ getValue }) => (
          <span className="text-sm text-zinc-400 tabular-nums">
            {getValue() != null ? formatResolutionTime(getValue() as number) : '—'}
          </span>
        ),
      } as ColumnSortable & ReturnType<typeof columnHelper.accessor<'avg_resolution_time_hours'>>),

      columnHelper.accessor('csat_avg', {
        header: ({ column }) => (
          <button
            className="flex items-center gap-1.5 hover:text-zinc-200 transition-colors"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          >
            CSAT
            <SortIcon isSorted={column.getIsSorted()} />
          </button>
        ),
        cell: ({ row }) => (
          <CSATBadge avg={row.original.csat_avg} count={row.original.csat_count} />
        ),
      } as ColumnSortable & ReturnType<typeof columnHelper.accessor<'csat_avg'>>),
    ],
    []
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div
      className={cn(
        'rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6',
        className
      )}
    >
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-zinc-300">
          Agent Performance
        </h3>
        <p className="text-xs text-zinc-600 mt-0.5">
          Individual metrics per support agent
        </p>
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
              {table.getHeaderGroups().map((headerGroup) => (
                <tr
                  key={headerGroup.id}
                  className="border-b border-white/[0.06] bg-white/[0.02]"
                >
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider whitespace-nowrap"
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row, rowIndex) => (
                <tr
                  key={row.id}
                  className={cn(
                    'border-b border-white/[0.03] transition-colors',
                    'hover:bg-white/[0.02]',
                    rowIndex % 2 === 1 && 'bg-white/[0.01]'
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-4 py-3 whitespace-nowrap"
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
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
