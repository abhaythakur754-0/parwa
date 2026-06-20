'use client';

import { useQuery } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';
import { getCurrentTenantId } from '@/lib/auth-context';

export interface MetricsData {
  total_tasks: number;
  auto_resolved: number;
  batched: number;
  escalated: number;
  avg_resolution_time: number;
  accuracy_score: number;
  daily_metrics?: Array<{
    date: string;
    tasks: number;
    auto_resolved: number;
    accuracy: number;
    [key: string]: any;
  }>;
  [key: string]: any;
}

export function useMetrics(days = 7) {
  return useQuery<MetricsData>({
    queryKey: ['metrics', days],
    queryFn: () => jarvisApi.getMetrics(getCurrentTenantId(), days),
    refetchInterval: 30000,
  });
}
