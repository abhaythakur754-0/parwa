"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Download, ZoomIn, ZoomOut } from "lucide-react";

export type ChartType = "line" | "bar" | "pie" | "area";

export interface ChartDataPoint {
  name: string;
  [key: string]: string | number;
}

export interface ChartSeries {
  key: string;
  name: string;
  color: string;
}

export interface ChartProps {
  type?: ChartType;
  data: ChartDataPoint[];
  series?: ChartSeries[];
  height?: number;
  showGrid?: boolean;
  showLegend?: boolean;
  showTooltip?: boolean;
  className?: string;
  title?: string;
  animate?: boolean;
  onExport?: () => void;
}

const DEFAULT_COLORS = [
  "#3b82f6", // blue
  "#22c55e", // green
  "#f97316", // orange
  "#a855f7", // purple
  "#ef4444", // red
  "#14b8a6", // teal
];

export function Chart({
  type = "line",
  data,
  series,
  height = 300,
  showGrid = true,
  showLegend = true,
  showTooltip = true,
  className,
  title,
  animate = true,
  onExport,
}: ChartProps) {
  const [isZoomed, setIsZoomed] = React.useState(false);

  // Auto-detect series from data if not provided
  const chartSeries = React.useMemo(() => {
    if (series) return series;

    if (data.length === 0) return [];

    const keys = Object.keys(data[0]).filter((k) => k !== "name");
    return keys.map((key, index) => ({
      key,
      name: key.charAt(0).toUpperCase() + key.slice(1),
      color: DEFAULT_COLORS[index % DEFAULT_COLORS.length],
    }));
  }, [data, series]);

  const toggleZoom = () => setIsZoomed(!isZoomed);

  const renderChart = () => {
    const commonProps = {
      data,
    };

    switch (type) {
      case "line":
        return (
          <LineChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
            <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="#9ca3af" />
            <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
            {showTooltip && <Tooltip />}
            {showLegend && <Legend />}
            {chartSeries.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.name}
                stroke={s.color}
                strokeWidth={2}
                dot={{ fill: s.color, strokeWidth: 2 }}
                activeDot={{ r: 6 }}
                animationDuration={animate ? 500 : 0}
              />
            ))}
          </LineChart>
        );

      case "bar":
        return (
          <BarChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
            <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="#9ca3af" />
            <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
            {showTooltip && <Tooltip />}
            {showLegend && <Legend />}
            {chartSeries.map((s) => (
              <Bar
                key={s.key}
                dataKey={s.key}
                name={s.name}
                fill={s.color}
                radius={[4, 4, 0, 0]}
                animationDuration={animate ? 500 : 0}
              />
            ))}
          </BarChart>
        );

      case "area":
        return (
          <AreaChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
            <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="#9ca3af" />
            <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
            {showTooltip && <Tooltip />}
            {showLegend && <Legend />}
            {chartSeries.map((s) => (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.name}
                stroke={s.color}
                fill={s.color}
                fillOpacity={0.2}
                animationDuration={animate ? 500 : 0}
              />
            ))}
          </AreaChart>
        );

      case "pie":
        return (
          <PieChart>
            {showTooltip && <Tooltip />}
            {showLegend && <Legend />}
            <Pie
              data={data.map((d, i) => ({
                ...d,
                fill: chartSeries[0]?.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
              }))}
              dataKey={chartSeries[0]?.key || "value"}
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={100}
              innerRadius={40}
              animationDuration={animate ? 500 : 0}
              label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
            >
              {data.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={DEFAULT_COLORS[index % DEFAULT_COLORS.length]}
                />
              ))}
            </Pie>
          </PieChart>
        );

      default:
        return null;
    }
  };

  const chartContent = (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      {(title || onExport) && (
        <div className="flex items-center justify-between">
          {title && <h3 className="text-lg font-semibold">{title}</h3>}
          <div className="flex gap-2">
            <Button variant="ghost" size="icon" onClick={toggleZoom}>
              {isZoomed ? (
                <ZoomOut className="h-4 w-4" />
              ) : (
                <ZoomIn className="h-4 w-4" />
              )}
            </Button>
            {onExport && (
              <Button variant="ghost" size="icon" onClick={onExport}>
                <Download className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Chart */}
      <div style={{ height: isZoomed ? height * 1.5 : height }}>
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>
    </div>
  );

  if (isZoomed) {
    return (
      <div className="fixed inset-4 z-50 bg-background border rounded-lg shadow-lg p-6 overflow-auto">
        {chartContent}
      </div>
    );
  }

  return chartContent;
}

export default Chart;
