/**
 * PARWA useAnalytics Hook
 *
 * Custom hook for analytics and reporting.
 * Handles fetching metrics, chart data, and exports.
 *
 * Features:
 * - Fetch dashboard metrics
 * - Fetch chart data
 * - Date range support
 * - Export to CSV/PDF
 */

import { useState, useCallback } from "react";
import { apiClient } from "../services/api/client";
import { useUIStore } from "../stores/uiStore";

/**
 * Date range interface.
 */
export interface DateRange {
  start: string;
  end: string;
}

/**
 * Preset date range type.
 */
export type PresetRange = "today" | "yesterday" | "last7days" | "last30days" | "last90days" | "custom";

/**
 * Dashboard metrics interface.
 */
export interface DashboardMetrics {
  totalTickets: number;
  openTickets: number;
  resolvedTickets: number;
  avgResponseTime: number;
  avgResolutionTime: number;
  csatScore: number;
  escalationRate: number;
  firstContactResolution: number;
}

/**
 * Chart data point interface.
 */
export interface ChartDataPoint {
  label: string;
  value: number;
  previousValue?: number;
}

/**
 * Chart data type.
 */
export type ChartType = "ticket_volume" | "resolution_time" | "csat_trend" | "agent_performance" | "escalation_rate";

/**
 * Chart data response.
 */
export interface ChartDataResponse {
  chartType: ChartType;
  data: ChartDataPoint[];
  summary?: {
    total: number;
    average: number;
    change: number;
    changePercent: number;
  };
}

/**
 * Agent performance metrics.
 */
export interface AgentPerformance {
  id: string;
  name: string;
  variant: string;
  ticketsResolved: number;
  avgResponseTime: number;
  csatScore: number;
  accuracy: number;
  status: "active" | "idle" | "offline";
}

/**
 * Analytics export format.
 */
export type ExportFormat = "csv" | "pdf" | "json";

/**
 * useAnalytics hook return type.
 */
export interface UseAnalyticsReturn {
  /** Current metrics */
  metrics: DashboardMetrics | null;
  /** Current chart data */
  chartData: ChartDataResponse | null;
  /** Agent performance data */
  agentPerformance: AgentPerformance[];
  /** Selected date range */
  dateRange: DateRange;
  /** Selected preset */
  presetRange: PresetRange;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: string | null;

  // Actions
  /** Fetch dashboard metrics */
  fetchMetrics: (range?: DateRange) => Promise<void>;
  /** Fetch chart data */
  fetchChartData: (chartType: ChartType, range?: DateRange) => Promise<void>;
  /** Fetch agent performance */
  fetchAgentPerformance: (range?: DateRange) => Promise<void>;
  /** Set date range */
  setDateRange: (range: DateRange, preset?: PresetRange) => void;
  /** Export data */
  exportToCSV: (chartType?: ChartType) => Promise<void>;
  /** Export to PDF */
  exportToPDF: (chartType?: ChartType) => Promise<void>;
  /** Export to JSON */
  exportToJSON: (chartType?: ChartType) => Promise<void>;
  /** Clear error */
  clearError: () => void;
}

/**
 * Get default date range (last 30 days).
 */
function getDefaultDateRange(): DateRange {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);

  return {
    start: start.toISOString().split("T")[0],
    end: end.toISOString().split("T")[0],
  };
}

/**
 * Custom hook for analytics and reporting.
 *
 * @returns Analytics state and actions
 *
 * @example
 * ```tsx
 * function AnalyticsDashboard() {
 *   const {
 *     metrics,
 *     chartData,
 *     fetchMetrics,
 *     fetchChartData,
 *     dateRange,
 *     setDateRange
 *   } = useAnalytics();
 *
 *   useEffect(() => {
 *     fetchMetrics();
 *     fetchChartData('ticket_volume');
 *   }, [dateRange]);
 *
 *   return (
 *     <div>
 *       <MetricsCards metrics={metrics} />
 *       <Chart data={chartData} />
 *     </div>
 *   );
 * }
 * ```
 */
export function useAnalytics(): UseAnalyticsReturn {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [chartData, setChartData] = useState<ChartDataResponse | null>(null);
  const [agentPerformance, setAgentPerformance] = useState<AgentPerformance[]>([]);
  const [dateRange, setDateRangeState] = useState<DateRange>(getDefaultDateRange);
  const [presetRange, setPresetRange] = useState<PresetRange>("last30days");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { addToast } = useUIStore();

  /**
   * Fetch dashboard metrics.
   */
  const fetchMetrics = useCallback(
    async (range?: DateRange): Promise<void> => {
      setIsLoading(true);
      setError(null);

      const currentRange = range ?? dateRange;

      try {
        const response = await apiClient.get<DashboardMetrics>("/analytics/metrics", {
          start: currentRange.start,
          end: currentRange.end,
        });

        setMetrics(response.data);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to fetch metrics";
        setError(message);
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [dateRange, addToast]
  );

  /**
   * Fetch chart data.
   */
  const fetchChartData = useCallback(
    async (chartType: ChartType, range?: DateRange): Promise<void> => {
      setIsLoading(true);
      setError(null);

      const currentRange = range ?? dateRange;

      try {
        const response = await apiClient.get<ChartDataResponse>(
          `/analytics/charts/${chartType}`,
          {
            start: currentRange.start,
            end: currentRange.end,
          }
        );

        setChartData(response.data);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to fetch chart data";
        setError(message);
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [dateRange, addToast]
  );

  /**
   * Fetch agent performance.
   */
  const fetchAgentPerformance = useCallback(
    async (range?: DateRange): Promise<void> => {
      setIsLoading(true);
      setError(null);

      const currentRange = range ?? dateRange;

      try {
        const response = await apiClient.get<AgentPerformance[]>(
          "/analytics/agent-performance",
          {
            start: currentRange.start,
            end: currentRange.end,
          }
        );

        setAgentPerformance(response.data);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to fetch agent performance";
        setError(message);
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [dateRange, addToast]
  );

  /**
   * Set date range.
   */
  const setDateRange = useCallback(
    (range: DateRange, preset?: PresetRange): void => {
      setDateRangeState(range);
      if (preset) {
        setPresetRange(preset);
      }
    },
    []
  );

  /**
   * Export data to CSV.
   */
  const exportToCSV = useCallback(
    async (chartType?: ChartType): Promise<void> => {
      setIsLoading(true);

      try {
        const endpoint = chartType
          ? `/analytics/export/csv?chartType=${chartType}`
          : "/analytics/export/csv";

        const response = await apiClient.get<Blob>(endpoint, {
          start: dateRange.start,
          end: dateRange.end,
        });

        // Create download link
        const url = window.URL.createObjectURL(
          response.data as unknown as Blob
        );
        const link = document.createElement("a");
        link.href = url;
        link.download = `analytics-${chartType || "all"}-${dateRange.start}-${dateRange.end}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        addToast({
          title: "Export complete",
          description: "CSV file has been downloaded.",
          variant: "success",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Export failed";
        addToast({
          title: "Export error",
          description: message,
          variant: "error",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [dateRange, addToast]
  );

  /**
   * Export data to PDF.
   */
  const exportToPDF = useCallback(
    async (chartType?: ChartType): Promise<void> => {
      setIsLoading(true);

      try {
        const endpoint = chartType
          ? `/analytics/export/pdf?chartType=${chartType}`
          : "/analytics/export/pdf";

        const response = await apiClient.get<Blob>(endpoint, {
          start: dateRange.start,
          end: dateRange.end,
        });

        const url = window.URL.createObjectURL(
          response.data as unknown as Blob
        );
        const link = document.createElement("a");
        link.href = url;
        link.download = `analytics-${chartType || "all"}-${dateRange.start}-${dateRange.end}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        addToast({
          title: "Export complete",
          description: "PDF file has been downloaded.",
          variant: "success",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Export failed";
        addToast({
          title: "Export error",
          description: message,
          variant: "error",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [dateRange, addToast]
  );

  /**
   * Export data to JSON.
   */
  const exportToJSON = useCallback(
    async (chartType?: ChartType): Promise<void> => {
      setIsLoading(true);

      try {
        const endpoint = chartType
          ? `/analytics/export/json?chartType=${chartType}`
          : "/analytics/export/json";

        const response = await apiClient.get<Record<string, unknown>>(endpoint, {
          start: dateRange.start,
          end: dateRange.end,
        });

        const jsonStr = JSON.stringify(response.data, null, 2);
        const blob = new Blob([jsonStr], { type: "application/json" });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `analytics-${chartType || "all"}-${dateRange.start}-${dateRange.end}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        addToast({
          title: "Export complete",
          description: "JSON file has been downloaded.",
          variant: "success",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Export failed";
        addToast({
          title: "Export error",
          description: message,
          variant: "error",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [dateRange, addToast]
  );

  /**
   * Clear error.
   */
  const clearError = useCallback((): void => {
    setError(null);
  }, []);

  return {
    metrics,
    chartData,
    agentPerformance,
    dateRange,
    presetRange,
    isLoading,
    error,
    fetchMetrics,
    fetchChartData,
    fetchAgentPerformance,
    setDateRange,
    exportToCSV,
    exportToPDF,
    exportToJSON,
    clearError,
  };
}

export default useAnalytics;
