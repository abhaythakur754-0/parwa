"use client";

/**
 * PARWA Stats Card Component
 *
 * Displays a stat with title, value, trend indicator, and icon.
 * Supports multiple color variants and loading/error states.
 */

import { cn } from "@/utils/utils";

/**
 * Stats card color variants.
 */
export type StatsCardColor = "blue" | "green" | "yellow" | "red";

/**
 * Props for StatsCard component.
 */
interface StatsCardProps {
  /** Card title */
  title: string;
  /** Main value to display */
  value: number | string;
  /** Trend percentage (positive = up, negative = down) */
  trend?: number;
  /** Icon to display */
  icon?: React.ReactNode;
  /** Color variant */
  color?: StatsCardColor;
  /** Loading state */
  isLoading?: boolean;
  /** Error state */
  error?: string;
  /** Invert trend meaning (e.g., for response time where down is good) */
  invertTrend?: boolean;
  /** Additional class names */
  className?: string;
}

/**
 * Color classes for different variants.
 */
const colorClasses: Record<StatsCardColor, { bg: string; icon: string }> = {
  blue: {
    bg: "bg-blue-50 dark:bg-blue-950/30",
    icon: "bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400",
  },
  green: {
    bg: "bg-green-50 dark:bg-green-950/30",
    icon: "bg-green-100 dark:bg-green-900/50 text-green-600 dark:text-green-400",
  },
  yellow: {
    bg: "bg-yellow-50 dark:bg-yellow-950/30",
    icon: "bg-yellow-100 dark:bg-yellow-900/50 text-yellow-600 dark:text-yellow-400",
  },
  red: {
    bg: "bg-red-50 dark:bg-red-950/30",
    icon: "bg-red-100 dark:bg-red-900/50 text-red-600 dark:text-red-400",
  },
};

/**
 * Stats card component.
 */
export default function StatsCard({
  title,
  value,
  trend,
  icon,
  color = "blue",
  isLoading = false,
  error,
  invertTrend = false,
  className,
}: StatsCardProps) {
  /**
   * Calculate trend direction and color.
   */
  const getTrendInfo = () => {
    if (trend === undefined || trend === 0) {
      return {
        direction: "neutral",
        color: "text-muted-foreground",
        icon: null,
      };
    }

    // Determine if the trend is positive or negative
    // For some metrics (like response time), a decrease is good (invertTrend = true)
    const isPositive = invertTrend ? trend < 0 : trend > 0;
    const absTrend = Math.abs(trend);

    return {
      direction: isPositive ? "up" : "down",
      color: isPositive ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400",
      icon: isPositive ? (
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
        </svg>
      ) : (
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
      ),
      percentage: absTrend.toFixed(1),
    };
  };

  const trendInfo = getTrendInfo();

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
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="h-4 w-24 bg-muted rounded" />
            <div className="h-8 w-16 bg-muted rounded" />
          </div>
          <div className="h-12 w-12 bg-muted rounded-lg" />
        </div>
      </div>
    );
  }

  /**
   * Error state.
   */
  if (error) {
    return (
      <div
        className={cn(
          "rounded-xl border border-destructive/50 bg-destructive/5 p-6",
          className
        )}
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-sm text-destructive mt-1">{error}</p>
          </div>
          <div className="h-12 w-12 rounded-lg bg-destructive/10 flex items-center justify-center text-destructive">
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-xl border bg-card p-6 transition-shadow hover:shadow-md",
        className
      )}
    >
      <div className="flex items-center justify-between">
        {/* Content */}
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="text-3xl font-bold tracking-tight">
            {typeof value === "number" ? value.toLocaleString() : value}
          </p>
          {trend !== undefined && trend !== 0 && (
            <div className={cn("flex items-center gap-1 text-sm", trendInfo.color)}>
              {trendInfo.icon}
              <span>{trendInfo.percentage}%</span>
              <span className="text-muted-foreground text-xs">vs last week</span>
            </div>
          )}
        </div>

        {/* Icon */}
        {icon && (
          <div
            className={cn(
              "h-12 w-12 rounded-lg flex items-center justify-center",
              colorClasses[color].icon
            )}
          >
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
