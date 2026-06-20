'use client';

import { useQuery } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';
import { getCurrentTenantId } from '@/lib/auth-context';

export interface JarvisStatus {
  system_status: string;
  mode: string;
  uptime_seconds: number;
  load_status: Array<{
    variant: string;
    status: string;
    current_concurrent: number;
    max_concurrent: number;
  }>;
  [key: string]: any;
}

export function useJarvisStatus() {
  return useQuery<JarvisStatus>({
    queryKey: ['jarvis-status'],
    queryFn: () => jarvisApi.getStatus(getCurrentTenantId()),
    refetchInterval: 5000,
  });
}
