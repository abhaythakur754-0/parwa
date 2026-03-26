"use client";

/**
 * PARWA Metric Card Component
 *
 * Displays a metric with title, value, sparkline chart, and trend.
 */

import { cn } from "@/utils/utils";

/**
 * Props for MetricCard component.
 */
interface MetricCardProps {
  /** Card title */
  title: string;
  /** Current value */
  value: number | string;
  /** Sparkline data (last 7 days) */
  data?: number[];
  /** Trend percentage */
  trend?: number;
  /** Loading state */
  isLoading?: boolean;
  /** Additional class names */
  className?: string;
}

/**
 * Simple SVG sparkline component.
 */
function Sparkline({ data, width = 120, height = 40 }: { data: number[]; width?: number; height?: number }) {
  if (!data || data.length === 0) return null;

  // Calculate min/max for scaling
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  // Create points for the path
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - ((value - min) / range) * height * 0.8 - height * 0.1;
    return `${x},${y}`;
  });

  // Determine if trend is up or down
  const isUp = data[data.length - 1] >= data[0];
  const strokeColor = isUp ? "#22c55e" : "#ef4444";

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="overflow-visible"
    >
      {/* Gradient fill */}
      <defs>
        <linearGradient id={`gradient-${title}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.3" />
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Fill area */}
      <path
        d={`M0,${height} L${points.join(" L")} L${width},${height} Z`}
        fill={`url(#gradient-${title})`}
      />

      {/* Line */}
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={strokeColor}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Last point dot */}
      <circle
        cx={(data.length - 1) / (data.length - 1) * width}
        cy={height - ((data[data.length - 1] - min) / range) * height * 0.8 - height * 0.1}
        r="3"
        fill={strokeColor}
      />
    </svg>
  );
}

/**
 * Get a unique key for the gradient (workaround for component name)
 */
let sparklineId = 0;
const title = "sparkline";

/**
 * Metric card component.
 */
export default function MetricCard({
  title,
  value,
  data,
  trend,
  isLoading = false,
  className,
}: MetricCardProps) {
  sparklineId++;

  /**
   * Loading skeleton.
   */
  if (isLoading) {
    return (
      <div
        className={cn(
          "rounded-xl border bg-card p-6 animate-pulse",
          className
        )}
      >
        <div className="space-y-3">
          <div className="h-4 w-24 bg-muted rounded" />
          <div className="h-8 w-16 bg-muted rounded" />
          <div className="h-10 w-full bg-muted rounded" />
        </div>
      </div>
    );
  }

  /**
   * Calculate trend direction and color.
   */
  const trendInfo = () => {
    if (trend === undefined || trend === 0) {
      return { color: "text-muted-foreground", text: "No change" };
    }
    const isPositive = trend > 0;
    return {
      color: isPositive ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400",
      text: `${isPositive ? "+" : ""}${trend.toFixed(1)}%`,
    };
  };

  return (
    <div
      className={cn(
        "rounded-xl border bg-card p-6 transition-shadow hover:shadow-md",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        {trend !== undefined && (
          <span className={cn("text-sm font-medium", trendInfo().color)}>
            {trendInfo().text}
          </span>
        )}
      </div>

      {/* Value */}
      <p className="text-3xl font-bold tracking-tight mb-4">
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>

      {/* Sparkline */}
      {data && data.length > 0 && (
        <div className="mt-2">
          <Sparkline data={data} width={200} height={50} />
        </div>
      )}

      {/* Data points labels */}
      {data && data.length > 0 && (
        <div className="flex justify-between mt-2 text-xs text-muted-foreground">
          <span>7 days ago</span>
          <span>Today</span>
        </div>
      )}
    </div>
  );
}
