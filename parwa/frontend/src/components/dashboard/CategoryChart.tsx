'use client';

import React, { useState } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Sector,
} from 'recharts';
import { cn } from '@/lib/utils';
import type { CategoryDistribution } from '@/types/analytics';

interface CategoryChartProps {
  data: CategoryDistribution[];
  className?: string;
}

/** PARWA brand-inspired color palette for categories. */
const COLORS = [
  '#f97316', // orange-500
  '#fbbf24', // amber-400
  '#38bdf8', // sky-500
  '#34d399', // emerald-500
  '#a78bfa', // violet-500
  '#fb7185', // rose-500
  '#2dd4bf', // teal-400
  '#818cf8', // indigo-400
  '#f472b6', // pink-400
  '#a3e635', // lime-400
];

/** Dark-theme custom tooltip for the pie chart. */
function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: CategoryDistribution }>;
}) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;

  return (
    <div className="rounded-lg border border-white/[0.08] bg-[#222]/95 px-3 py-2 shadow-xl backdrop-blur-sm">
      <p className="text-sm font-semibold text-white">{item.category}</p>
      <div className="mt-1 flex items-center gap-3 text-xs">
        <span className="text-zinc-400">{item.count.toLocaleString()} tickets</span>
        <span className="text-zinc-500">({item.percentage.toFixed(1)}%)</span>
      </div>
    </div>
  );
}

/** Active shape for hover effect on pie slices. */
function renderActiveShape(props: unknown) {
  const {
    cx,
    cy,
    innerRadius,
    outerRadius,
    startAngle,
    endAngle,
    fill,
    percent,
  } = props as {
    cx: number;
    cy: number;
    innerRadius: number;
    outerRadius: number;
    startAngle: number;
    endAngle: number;
    fill: string;
    percent: number;
  };

  return (
    <g>
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius}
        outerRadius={(outerRadius as number) + 6}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={0.95}
      />
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius - 2}
        outerRadius={innerRadius + 2}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={0.4}
      />
      <text
        x={cx}
        y={cy - 6}
        textAnchor="middle"
        fill="#fff"
        fontSize={14}
        fontWeight={600}
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    </g>
  );
}

export default function CategoryChart({ data, className }: CategoryChartProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  const chartData = React.useMemo(() => {
    if (!data?.length) return [];
    return data.slice(0, 8); // top 8 categories
  }, [data]);

  return (
    <div
      className={cn(
        'rounded-xl bg-[#1A1A1A]/50 border border-white/[0.06] p-6',
        className
      )}
    >
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-zinc-300">
          Category Distribution
        </h3>
        <p className="text-xs text-zinc-600 mt-0.5">Tickets by category</p>
      </div>

      {chartData.length === 0 ? (
        <div className="h-[260px] flex items-center justify-center text-zinc-600 text-sm">
          No category data available
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <div className="flex-1 min-w-0">
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={62}
                  outerRadius={95}
                  dataKey="count"
                  nameKey="category"
                  paddingAngle={2}
                  activeIndex={activeIndex}
                  activeShape={renderActiveShape}
                  onMouseEnter={(_, index) => setActiveIndex(index)}
                >
                  {chartData.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                      opacity={0.85}
                    />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Legend */}
          <div className="flex-shrink-0 w-[140px] space-y-1.5 max-h-[260px] overflow-y-auto pr-1 scrollbar-thin">
            {chartData.map((cat, index) => (
              <div
                key={cat.category}
                className="flex items-center gap-2 text-xs cursor-pointer group"
                onMouseEnter={() => setActiveIndex(index)}
              >
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: COLORS[index % COLORS.length] }}
                />
                <span className="text-zinc-400 truncate group-hover:text-zinc-200 transition-colors">
                  {cat.category}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
