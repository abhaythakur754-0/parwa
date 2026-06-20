'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';
import { getCurrentTenantId } from '@/lib/auth-context';

export interface Notification {
  key: string;
  title: string;
  description: string;
  priority: string;
  category: string;
  timestamp: string;
  resolved?: boolean;
  batch_key?: string;
  [key: string]: any;
}

export function useNotifications(includeResolved = false) {
  return useQuery<{ notifications: Notification[] }>({
    queryKey: ['notifications', includeResolved],
    queryFn: () => jarvisApi.getNotifications(getCurrentTenantId(), includeResolved),
    refetchInterval: 10000,
  });
}

export function useResolveNotification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => jarvisApi.resolveNotification(key),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

export function useApproveBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ batchKey }: { batchKey: string }) =>
      jarvisApi.approveBatch(getCurrentTenantId(), batchKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
  });
}

export function useRejectBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ batchKey }: { batchKey: string }) =>
      jarvisApi.rejectBatch(getCurrentTenantId(), batchKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
    },
  });
}
