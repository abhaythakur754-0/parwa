/**
 * PARWA Analytics Service
 * Handles analytics and reporting API operations.
 */

import { apiClient } from "./api/client";

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

export interface ChartData {
  label: string;
  value: number;
  previousValue?: number;
}

export const analyticsService = {
  async getMetrics(startDate?: string, endDate?: string) {
    const params: Record<string, string> = {};
    if (startDate) params.start = startDate;
    if (endDate) params.end = endDate;
    const res = await apiClient.get<DashboardMetrics>("/analytics/metrics", params);
    return res.data;
  },

  async getChartData(chartType: string, startDate?: string, endDate?: string) {
    const params: Record<string, string> = {};
    if (startDate) params.start = startDate;
    if (endDate) params.end = endDate;
    const res = await apiClient.get<{ data: ChartData[]; summary: { total: number; average: number } }>(`/analytics/charts/${chartType}`, params);
    return res.data;
  },

  async exportCSV(chartType?: string) {
    const endpoint = chartType ? `/analytics/export/csv?chartType=${chartType}` : "/analytics/export/csv";
    const res = await apiClient.get<Blob>(endpoint);
    return res.data;
  },

  async exportPDF(chartType?: string) {
    const endpoint = chartType ? `/analytics/export/pdf?chartType=${chartType}` : "/analytics/export/pdf";
    const res = await apiClient.get<Blob>(endpoint);
    return res.data;
  },

  async exportJSON(chartType?: string) {
    const endpoint = chartType ? `/analytics/export/json?chartType=${chartType}` : "/analytics/export/json";
    const res = await apiClient.get<Record<string, unknown>>(endpoint);
    return res.data;
  },
};

export default analyticsService;
