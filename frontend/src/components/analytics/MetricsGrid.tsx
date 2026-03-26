"use client";

import * as React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/utils/utils";
import { TrendingUp, TrendingDown, Minus, ArrowUpRight, ArrowDownRight } from "lucide-react";

export interface MetricData {
  id: string;
  title: string;
  value: string | number;
  previousValue?: string | number;
  change?: number;
  trend?: "up" | "down" | "neutral";
  sparklineData?: number[];
  format?: "number" | "currency" | "percentage" | "time";
  icon?: React.ReactNode;
  color?: string;
}

export interface MetricsGridProps {
  metrics: MetricData[];
  columns?: 2 | 3 | 4;
  loading?: boolean;
  onMetricClick?: (metric: MetricData) => void;
  className?: string;
}

function SparklineChart({ data, color }: { data: number[]; color: string }) {
  if (!data || data.length === 0) return null;

  const width = 80;
  const height = 30;
  const padding = 2;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data.map((value, index) => {
    const x = padding + (index / (data.length - 1)) * (width - padding * 2);
    const y = height - padding - ((value - min) / range) * (height - padding * 2);
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function MetricCard({
  metric,
  loading,
  onClick,
}: {
  metric: MetricData;
  loading?: boolean;
  onClick?: () => void;
}) {
  const getTrendIcon = () => {
    switch (metric.trend) {
      case "up":
        return metric.change && metric.change > 0 ? (
          <ArrowUpRight className="h-4 w-4 text-green-500" />
        ) : (
          <ArrowUpRight className="h-4 w-4 text-red-500" />
        );
      case "down":
        return metric.change && metric.change > 0 ? (
          <ArrowDownRight className="h-4 w-4 text-green-500" />
        ) : (
          <ArrowDownRight className="h-4 w-4 text-red-500" />
        );
      default:
        return <Minus className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getTrendColor = () => {
    if (metric.trend === "neutral") return "text-muted-foreground";

    // For metrics like "Resolution Time", down is good
    const isInverseMetric = metric.title.toLowerCase().includes("time");

    if (metric.trend === "up") {
      return isInverseMetric ? "text-red-500" : "text-green-500";
    }
    if (metric.trend === "down") {
      return isInverseMetric ? "text-green-500" : "text-red-500";
    }
    return "text-muted-foreground";
  };

  if (loading) {
    return (
      <Card className="animate-pulse">
        <CardContent className="pt-4">
          <div className="h-4 bg-muted rounded w-1/2 mb-2" />
          <div className="h-8 bg-muted rounded w-3/4 mb-2" />
          <div className="h-3 bg-muted rounded w-1/3" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      className={cn(
        "transition-all hover:shadow-md",
        onClick && "cursor-pointer hover:border-primary/50"
      )}
      onClick={onClick}
    >
      <CardContent className="pt-4">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">{metric.title}</p>
            <p
              className={cn(
                "text-2xl font-bold",
                metric.color && `text-${metric.color}-600`
              )}
            >
              {metric.value}
            </p>
          </div>
          {metric.icon && (
            <div className="p-2 rounded-lg bg-muted">{metric.icon}</div>
          )}
        </div>

        <div className="flex items-center justify-between mt-3">
          <div className="flex items-center gap-1">
            {getTrendIcon()}
            {metric.change !== undefined && (
              <span className={cn("text-sm font-medium", getTrendColor())}>
                {Math.abs(metric.change)}%
              </span>
            )}
            {metric.previousValue && (
              <span className="text-xs text-muted-foreground ml-1">
                vs {metric.previousValue}
              </span>
            )}
          </div>

          {metric.sparklineData && metric.sparklineData.length > 0 && (
            <SparklineChart
              data={metric.sparklineData}
              color={metric.color || "#3b82f6"}
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function MetricsGrid({
  metrics,
  columns = 4,
  loading = false,
  onMetricClick,
  className,
}: MetricsGridProps) {
  const gridCols = {
    2: "sm:grid-cols-2",
    3: "sm:grid-cols-2 lg:grid-cols-3",
    4: "sm:grid-cols-2 lg:grid-cols-4",
  };

  return (
    <div className={cn("grid gap-4", gridCols[columns], className)}>
      {metrics.map((metric) => (
        <MetricCard
          key={metric.id}
          metric={metric}
          loading={loading}
          onClick={onMetricClick ? () => onMetricClick(metric) : undefined}
        />
      ))}
    </div>
  );
}

export default MetricsGrid;
