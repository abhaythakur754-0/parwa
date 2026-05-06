/**
 * PARWA useApprovals Hook
 *
 * Custom hook for approval queue management.
 * Handles fetching, approving, and denying approval requests.
 *
 * Features:
 * - Fetch pending approvals list
 * - Approve/deny actions
 * - Refresh functionality
 * - Loading and error states
 */

import { useState, useCallback, useEffect } from "react";
import { apiClient } from "../services/api/client";
import { useUIStore } from "../stores/uiStore";

/**
 * Approval type enumeration.
 */
export type ApprovalType =
  | "refund"
  | "refund-recommendation"
  | "escalation"
  | "account-change"
  | "high-value-action";

/**
 * Approval status enumeration.
 */
export type ApprovalStatus = "pending" | "approved" | "denied" | "expired";

/**
 * Approval recommendation type.
 */
export type ApprovalRecommendation = "APPROVE" | "REVIEW" | "DENY";

/**
 * Approval item interface.
 */
export interface Approval {
  /** Unique approval ID */
  id: string;
  /** Type of approval */
  type: ApprovalType;
  /** Current status */
  status: ApprovalStatus;
  /** Amount involved (for refunds) */
  amount?: number;
  /** Currency code */
  currency?: string;
  /** Reason for the request */
  reason: string;
  /** User who requested */
  requester: {
    id: string;
    name: string;
    email: string;
  };
  /** AI recommendation */
  recommendation?: {
    decision: ApprovalRecommendation;
    confidence: number;
    reasoning: string;
  };
  /** Related ticket ID */
  ticketId?: string;
  /** Related customer ID */
  customerId?: string;
  /** Creation timestamp */
  createdAt: string;
  /** Last update timestamp */
  updatedAt: string;
  /** Expiration timestamp */
  expiresAt?: string;
}

/**
 * Approvals list response.
 */
export interface ApprovalsListResponse {
  approvals: Approval[];
  total: number;
  page: number;
  pageSize: number;
}

/**
 * Approvals filter options.
 */
export interface ApprovalsFilters {
  type?: ApprovalType;
  status?: ApprovalStatus;
  minAmount?: number;
  maxAmount?: number;
  startDate?: string;
  endDate?: string;
  search?: string;
}

/**
 * Approve action request.
 */
export interface ApproveRequest {
  notes?: string;
}

/**
 * Deny action request.
 */
export interface DenyRequest {
  reason: string;
  notes?: string;
}

/**
 * useApprovals hook return type.
 */
export interface UseApprovalsReturn {
  /** List of approvals */
  approvals: Approval[];
  /** Total count for pagination */
  total: number;
  /** Current page */
  page: number;
  /** Page size */
  pageSize: number;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: string | null;
  /** Current filters */
  filters: ApprovalsFilters;

  // Actions
  /** Fetch approvals list */
  fetchApprovals: (filters?: ApprovalsFilters, page?: number) => Promise<void>;
  /** Approve an approval */
  approve: (id: string, notes?: string) => Promise<void>;
  /** Deny an approval */
  deny: (id: string, reason: string, notes?: string) => Promise<void>;
  /** Refresh current list */
  refresh: () => Promise<void>;
  /** Set filters */
  setFilters: (filters: ApprovalsFilters) => void;
  /** Clear any errors */
  clearError: () => void;
}

/**
 * Custom hook for approval queue management.
 *
 * @returns Approvals state and actions
 *
 * @example
 * ```tsx
 * function ApprovalsQueue() {
 *   const {
 *     approvals,
 *     isLoading,
 *     approve,
 *     deny,
 *     refresh
 *   } = useApprovals();
 *
 *   const handleApprove = async (id: string) => {
 *     await approve(id, "Looks good");
 *     refresh();
 *   };
 *
 *   return (
 *     <div>
 *       {approvals.map(approval => (
 *         <ApprovalCard
 *           key={approval.id}
 *           approval={approval}
 *           onApprove={handleApprove}
 *         />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useApprovals(): UseApprovalsReturn {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFiltersState] = useState<ApprovalsFilters>({});

  const { addToast } = useUIStore();

  /**
   * Fetch approvals list from API.
   */
  const fetchApprovals = useCallback(
    async (newFilters?: ApprovalsFilters, newPage?: number): Promise<void> => {
      setIsLoading(true);
      setError(null);

      const currentPage = newPage ?? page;
      const currentFilters = newFilters ?? filters;

      try {
        const params: Record<string, string> = {
          page: String(currentPage),
          pageSize: String(pageSize),
        };

        // Add filters to params
        if (currentFilters.type) params.type = currentFilters.type;
        if (currentFilters.status) params.status = currentFilters.status;
        if (currentFilters.minAmount) params.minAmount = String(currentFilters.minAmount);
        if (currentFilters.maxAmount) params.maxAmount = String(currentFilters.maxAmount);
        if (currentFilters.startDate) params.startDate = currentFilters.startDate;
        if (currentFilters.endDate) params.endDate = currentFilters.endDate;
        if (currentFilters.search) params.search = currentFilters.search;

        const response = await apiClient.get<ApprovalsListResponse>(
          "/approvals",
          params
        );

        setApprovals(response.data.approvals);
        setTotal(response.data.total);
        setPage(response.data.page);
        setPageSize(response.data.pageSize);

        if (newFilters) {
          setFiltersState(newFilters);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to fetch approvals";
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
    [page, pageSize, filters, addToast]
  );

  /**
   * Approve an approval request.
   */
  const approve = useCallback(
    async (id: string, notes?: string): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        await apiClient.post<void>(`/approvals/${id}/approve`, { notes } as ApproveRequest);

        // Remove from local list
        setApprovals((prev) => prev.filter((a) => a.id !== id));
        setTotal((prev) => prev - 1);

        addToast({
          title: "Approved",
          description: "The approval request has been approved.",
          variant: "success",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to approve";
        setError(message);
        addToast({
          title: "Approval failed",
          description: message,
          variant: "error",
        });
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [addToast]
  );

  /**
   * Deny an approval request.
   */
  const deny = useCallback(
    async (id: string, reason: string, notes?: string): Promise<void> => {
      if (!reason.trim()) {
        throw new Error("Denial reason is required");
      }

      setIsLoading(true);
      setError(null);

      try {
        await apiClient.post<void>(`/approvals/${id}/deny`, {
          reason,
          notes,
        } as DenyRequest);

        // Remove from local list
        setApprovals((prev) => prev.filter((a) => a.id !== id));
        setTotal((prev) => prev - 1);

        addToast({
          title: "Denied",
          description: "The approval request has been denied.",
          variant: "warning",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to deny";
        setError(message);
        addToast({
          title: "Denial failed",
          description: message,
          variant: "error",
        });
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [addToast]
  );

  /**
   * Refresh the current list.
   */
  const refresh = useCallback(async (): Promise<void> => {
    await fetchApprovals(filters, page);
  }, [fetchApprovals, filters, page]);

  /**
   * Set filters and refetch.
   */
  const setFilters = useCallback(
    (newFilters: ApprovalsFilters): void => {
      setFiltersState(newFilters);
      setPage(1); // Reset to first page
    },
    []
  );

  /**
   * Clear error state.
   */
  const clearError = useCallback((): void => {
    setError(null);
  }, []);

  /**
   * Auto-fetch on mount.
   */
  useEffect(() => {
    fetchApprovals();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    approvals,
    total,
    page,
    pageSize,
    isLoading,
    error,
    filters,
    fetchApprovals,
    approve,
    deny,
    refresh,
    setFilters,
    clearError,
  };
}

export default useApprovals;
