/**
 * PARWA Approvals Query Hook
 *
 * Enhanced hook for approval queue management using React Query.
 * Features optimistic updates, filtering, and real-time synchronization.
 *
 * @module hooks/queries/useApprovalsQuery
 */

"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import { z } from "zod";
import { queryKeys } from "../../lib/react-query/query-client";

// ============================================================================
// Types & Schemas
// ============================================================================

/**
 * Approval type enumeration.
 */
export const ApprovalTypeSchema = z.enum([
  "refund",
  "refund-recommendation",
  "escalation",
  "account-change",
  "high-value-action",
]);
export type ApprovalType = z.infer<typeof ApprovalTypeSchema>;

/**
 * Approval status enumeration.
 */
export const ApprovalStatusSchema = z.enum(["pending", "approved", "denied", "expired"]);
export type ApprovalStatus = z.infer<typeof ApprovalStatusSchema>;

/**
 * Approval recommendation type.
 */
export const ApprovalRecommendationSchema = z.enum(["APPROVE", "REVIEW", "DENY"]);
export type ApprovalRecommendation = z.infer<typeof ApprovalRecommendationSchema>;

/**
 * Approval recommendation schema.
 */
export const ApprovalRecommendationDataSchema = z.object({
  decision: ApprovalRecommendationSchema,
  confidence: z.number().min(0).max(1),
  reasoning: z.string(),
});

export type ApprovalRecommendationData = z.infer<typeof ApprovalRecommendationDataSchema>;

/**
 * Requester schema.
 */
export const RequesterSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string().email(),
});

/**
 * Approval schema.
 */
export const ApprovalSchema = z.object({
  id: z.string(),
  type: ApprovalTypeSchema,
  status: ApprovalStatusSchema,
  amount: z.number().optional(),
  currency: z.string().optional(),
  reason: z.string(),
  requester: RequesterSchema,
  recommendation: ApprovalRecommendationDataSchema.optional(),
  ticketId: z.string().optional(),
  customerId: z.string().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
  expiresAt: z.string().optional(),
  metadata: z.record(z.unknown()).optional(),
});

export type Approval = z.infer<typeof ApprovalSchema>;

/**
 * Approvals list response schema.
 */
export const ApprovalsListResponseSchema = z.object({
  approvals: z.array(ApprovalSchema),
  total: z.number(),
  page: z.number(),
  pageSize: z.number(),
  hasMore: z.boolean().optional(),
});

export type ApprovalsListResponse = z.infer<typeof ApprovalsListResponseSchema>;

/**
 * Approvals filter options schema.
 */
export const ApprovalsFiltersSchema = z.object({
  type: ApprovalTypeSchema.optional(),
  status: ApprovalStatusSchema.optional(),
  minAmount: z.number().optional(),
  maxAmount: z.number().optional(),
  startDate: z.string().optional(),
  endDate: z.string().optional(),
  search: z.string().optional(),
  requesterId: z.string().optional(),
});

export type ApprovalsFilters = z.infer<typeof ApprovalsFiltersSchema>;

/**
 * Approve action request schema.
 */
export const ApproveRequestSchema = z.object({
  notes: z.string().optional(),
});

export type ApproveRequest = z.infer<typeof ApproveRequestSchema>;

/**
 * Deny action request schema.
 */
export const DenyRequestSchema = z.object({
  reason: z.string().min(1, "Denial reason is required"),
  notes: z.string().optional(),
});

export type DenyRequest = z.infer<typeof DenyRequestSchema>;

/**
 * Approval stats schema.
 */
export const ApprovalStatsSchema = z.object({
  total: z.number(),
  pending: z.number(),
  approved: z.number(),
  denied: z.number(),
  byType: z.record(z.number()),
  averageProcessingTime: z.number().optional(),
});

export type ApprovalStats = z.infer<typeof ApprovalStatsSchema>;

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = "/api";

/**
 * Fetch approvals list with filters and pagination.
 */
async function fetchApprovals(params: {
  page: number;
  pageSize: number;
  filters?: ApprovalsFilters;
}): Promise<ApprovalsListResponse> {
  const searchParams = new URLSearchParams({
    page: String(params.page),
    pageSize: String(params.pageSize),
  });

  if (params.filters) {
    const { filters } = params;
    if (filters.type) searchParams.set("type", filters.type);
    if (filters.status) searchParams.set("status", filters.status);
    if (filters.minAmount) searchParams.set("minAmount", String(filters.minAmount));
    if (filters.maxAmount) searchParams.set("maxAmount", String(filters.maxAmount));
    if (filters.startDate) searchParams.set("startDate", filters.startDate);
    if (filters.endDate) searchParams.set("endDate", filters.endDate);
    if (filters.search) searchParams.set("search", filters.search);
    if (filters.requesterId) searchParams.set("requesterId", filters.requesterId);
  }

  const response = await fetch(`${API_BASE}/approvals?${searchParams}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch approvals: ${response.statusText}`);
  }

  const data = await response.json();
  return ApprovalsListResponseSchema.parse(data);
}

/**
 * Fetch a single approval by ID.
 */
async function fetchApproval(id: string): Promise<Approval> {
  const response = await fetch(`${API_BASE}/approvals/${id}`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Approval not found");
    }
    throw new Error(`Failed to fetch approval: ${response.statusText}`);
  }

  const data = await response.json();
  return ApprovalSchema.parse(data);
}

/**
 * Approve an approval request.
 */
async function approveApproval(id: string, notes?: string): Promise<Approval> {
  const response = await fetch(`${API_BASE}/approvals/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });

  if (!response.ok) {
    throw new Error(`Failed to approve: ${response.statusText}`);
  }

  const data = await response.json();
  return ApprovalSchema.parse(data);
}

/**
 * Deny an approval request.
 */
async function denyApproval(id: string, reason: string, notes?: string): Promise<Approval> {
  const response = await fetch(`${API_BASE}/approvals/${id}/deny`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, notes }),
  });

  if (!response.ok) {
    throw new Error(`Failed to deny: ${response.statusText}`);
  }

  const data = await response.json();
  return ApprovalSchema.parse(data);
}

/**
 * Fetch approval statistics.
 */
async function fetchApprovalStats(): Promise<ApprovalStats> {
  const response = await fetch(`${API_BASE}/approvals/stats`);
  if (!response.ok) {
    throw new Error(`Failed to fetch approval stats: ${response.statusText}`);
  }

  const data = await response.json();
  return ApprovalStatsSchema.parse(data);
}

// ============================================================================
// Query Hooks
// ============================================================================

/**
 * Options for useApprovals hook.
 */
export interface UseApprovalsOptions
  extends Omit<UseQueryOptions<ApprovalsListResponse, Error>, "queryKey" | "queryFn"> {
  /** Initial filters */
  filters?: ApprovalsFilters;
  /** Page number */
  page?: number;
  /** Items per page */
  pageSize?: number;
  /** Enable real-time updates */
  realtime?: boolean;
  /** Auto-refetch interval in milliseconds */
  refetchInterval?: number;
}

/**
 * Hook to fetch approvals list with pagination and filtering.
 *
 * @param options - Query options
 * @returns Query result with approvals data
 *
 * @example
 * ```tsx
 * function ApprovalsQueue() {
 *   const { data, isLoading, refetch } = useApprovals({
 *     filters: { status: 'pending' },
 *     realtime: true,
 *   });
 *
 *   return (
 *     <div>
 *       {data?.approvals.map(approval => (
 *         <ApprovalCard key={approval.id} approval={approval} />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useApprovals(options: UseApprovalsOptions = {}) {
  const {
    filters = {},
    page = 1,
    pageSize = 20,
    realtime = false,
    refetchInterval = 30000, // 30 seconds default for approvals
    ...queryOptions
  } = options;

  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);

  const query = useQuery({
    queryKey: queryKeys.approvals.list({ ...filters, page, pageSize }),
    queryFn: () => fetchApprovals({ page, pageSize, filters }),
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval,
    ...queryOptions,
  });

  // Setup real-time updates
  useEffect(() => {
    if (!realtime) return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:3001";
    wsRef.current = new WebSocket(`${wsUrl}/approvals`);

    wsRef.current.onmessage = (event) => {
      const update = JSON.parse(event.data);

      if (update.type === "approval_created") {
        queryClient.setQueryData<ApprovalsListResponse>(
          queryKeys.approvals.lists(),
          (old) => {
            if (!old) return old;
            return {
              ...old,
              approvals: [update.data, ...old.approvals],
              total: old.total + 1,
            };
          }
        );
      } else if (update.type === "approval_updated") {
        queryClient.setQueryData(queryKeys.approvals.detail(update.data.id), update.data);

        queryClient.setQueryData<ApprovalsListResponse>(
          queryKeys.approvals.lists(),
          (old) => {
            if (!old) return old;
            return {
              ...old,
              approvals: old.approvals.map((a) =>
                a.id === update.data.id ? update.data : a
              ),
            };
          }
        );
      }
    };

    return () => {
      wsRef.current?.close();
    };
  }, [realtime, queryClient]);

  return query;
}

/**
 * Options for useApproval hook.
 */
export interface UseApprovalOptions
  extends Omit<UseQueryOptions<Approval, Error>, "queryKey" | "queryFn"> {
  /** Approval ID */
  id: string;
}

/**
 * Hook to fetch a single approval by ID.
 *
 * @param options - Query options including approval ID
 * @returns Query result with approval data
 */
export function useApproval(options: UseApprovalOptions) {
  const { id, ...queryOptions } = options;

  return useQuery({
    queryKey: queryKeys.approvals.detail(id),
    queryFn: () => fetchApproval(id),
    enabled: !!id,
    staleTime: 30 * 1000, // 30 seconds
    ...queryOptions,
  });
}

/**
 * Hook to fetch approval statistics.
 *
 * @param options - Query options
 * @returns Query result with approval stats
 */
export function useApprovalStats(
  options: Omit<UseQueryOptions<ApprovalStats, Error>, "queryKey" | "queryFn"> = {}
) {
  return useQuery({
    queryKey: queryKeys.approvals.stats(),
    queryFn: fetchApprovalStats,
    staleTime: 60 * 1000, // 1 minute
    ...options,
  });
}

// ============================================================================
// Mutation Hooks
// ============================================================================

/**
 * Hook to approve an approval request with optimistic update.
 *
 * @param options - Mutation options
 * @returns Mutation result
 */
export function useApproveApproval(
  options: Omit<UseMutationOptions<Approval, Error, { id: string; notes?: string }>, "mutationFn"> = {}
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, notes }) => approveApproval(id, notes),
    onMutate: async ({ id }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.approvals.lists() });
      await queryClient.cancelQueries({ queryKey: queryKeys.approvals.detail(id) });

      const previousLists = queryClient.getQueriesData({ queryKey: queryKeys.approvals.lists() });
      const previousDetail = queryClient.getQueryData<Approval>(queryKeys.approvals.detail(id));

      // Optimistically remove from pending lists
      queryClient.setQueriesData<ApprovalsListResponse>(
        { queryKey: queryKeys.approvals.lists() },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            approvals: old.approvals.filter((a) => a.id !== id),
            total: old.total - 1,
          };
        }
      );

      // Optimistically update detail
      if (previousDetail) {
        queryClient.setQueryData<Approval>(queryKeys.approvals.detail(id), {
          ...previousDetail,
          status: "approved",
          updatedAt: new Date().toISOString(),
        });
      }

      return { previousLists, previousDetail };
    },
    onError: (error, variables, context) => {
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data);
        });
      }
      if (context?.previousDetail) {
        queryClient.setQueryData(queryKeys.approvals.detail(variables.id), context.previousDetail);
      }
      options.onError?.(error, variables, context);
    },
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.approvals.lists() });
      queryClient.invalidateQueries({ queryKey: queryKeys.approvals.stats() });
      options.onSuccess?.(data, variables, context);
    },
  });
}

/**
 * Hook to deny an approval request with optimistic update.
 *
 * @param options - Mutation options
 * @returns Mutation result
 */
export function useDenyApproval(
  options: Omit<UseMutationOptions<Approval, Error, { id: string; reason: string; notes?: string }>, "mutationFn"> = {}
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, reason, notes }) => denyApproval(id, reason, notes),
    onMutate: async ({ id }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.approvals.lists() });
      await queryClient.cancelQueries({ queryKey: queryKeys.approvals.detail(id) });

      const previousLists = queryClient.getQueriesData({ queryKey: queryKeys.approvals.lists() });
      const previousDetail = queryClient.getQueryData<Approval>(queryKeys.approvals.detail(id));

      // Optimistically remove from pending lists
      queryClient.setQueriesData<ApprovalsListResponse>(
        { queryKey: queryKeys.approvals.lists() },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            approvals: old.approvals.filter((a) => a.id !== id),
            total: old.total - 1,
          };
        }
      );

      // Optimistically update detail
      if (previousDetail) {
        queryClient.setQueryData<Approval>(queryKeys.approvals.detail(id), {
          ...previousDetail,
          status: "denied",
          updatedAt: new Date().toISOString(),
        });
      }

      return { previousLists, previousDetail };
    },
    onError: (error, variables, context) => {
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data);
        });
      }
      if (context?.previousDetail) {
        queryClient.setQueryData(queryKeys.approvals.detail(variables.id), context.previousDetail);
      }
      options.onError?.(error, variables, context);
    },
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.approvals.lists() });
      queryClient.invalidateQueries({ queryKey: queryKeys.approvals.stats() });
      options.onSuccess?.(data, variables, context);
    },
  });
}

/**
 * Hook combining approve and deny actions for convenience.
 *
 * @param options - Options for both mutations
 * @returns Object with approve and deny mutations
 */
export function useApprovalActions(options: {
  onApproveSuccess?: (data: Approval) => void;
  onDenySuccess?: (data: Approval) => void;
  onError?: (error: Error) => void;
} = {}) {
  const approveMutation = useApproveApproval({
    onSuccess: options.onApproveSuccess,
    onError: options.onError,
  });

  const denyMutation = useDenyApproval({
    onSuccess: options.onDenySuccess,
    onError: options.onError,
  });

  const approve = useCallback(
    async (id: string, notes?: string) => {
      return approveMutation.mutateAsync({ id, notes });
    },
    [approveMutation]
  );

  const deny = useCallback(
    async (id: string, reason: string, notes?: string) => {
      return denyMutation.mutateAsync({ id, reason, notes });
    },
    [denyMutation]
  );

  return {
    approve,
    deny,
    isApproving: approveMutation.isPending,
    isDenying: denyMutation.isPending,
    isPending: approveMutation.isPending || denyMutation.isPending,
    approveError: approveMutation.error,
    denyError: denyMutation.error,
  };
}

/**
 * Prefetch approvals for faster navigation.
 *
 * @param filters - Filter options
 * @param page - Page number
 */
export function usePrefetchApprovals() {
  const queryClient = useQueryClient();

  return useCallback((filters?: ApprovalsFilters, page = 1, pageSize = 20) => {
    queryClient.prefetchQuery({
      queryKey: queryKeys.approvals.list({ ...filters, page, pageSize }),
      queryFn: () => fetchApprovals({ page, pageSize, filters }),
    });
  }, [queryClient]);
}

export default useApprovals;
