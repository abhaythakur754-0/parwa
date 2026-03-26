/**
 * PARWA Approval Service
 * Handles approval queue API operations with backend integration.
 */

import { apiClient } from "./api/client";

export interface Approval {
  id: string;
  type: "refund" | "refund-recommendation" | "escalation" | "account-change";
  status: "pending" | "approved" | "denied" | "expired";
  amount?: number;
  currency?: string;
  reason: string;
  requester: { id: string; name: string; email: string };
  recommendation?: { decision: string; confidence: number; reasoning: string };
  ticketId?: string;
  customerId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ApprovalFilters {
  type?: string;
  status?: string;
  minAmount?: number;
  maxAmount?: number;
  startDate?: string;
  endDate?: string;
  search?: string;
}

export const approvalService = {
  async getApprovals(filters?: ApprovalFilters, page = 1, pageSize = 20) {
    const params: Record<string, string> = { page: String(page), pageSize: String(pageSize) };
    if (filters) Object.entries(filters).forEach(([k, v]) => { if (v !== undefined) params[k] = String(v); });
    const res = await apiClient.get<{ approvals: Approval[]; total: number }>("/approvals", params);
    return res.data;
  },

  async getApproval(id: string) {
    const res = await apiClient.get<Approval>(`/approvals/${id}`);
    return res.data;
  },

  /** CRITICAL: Calls Paddle exactly once after approval */
  async approve(id: string, notes?: string) {
    const res = await apiClient.post<Approval>(`/approvals/${id}/approve`, { notes });
    return res.data;
  },

  async deny(id: string, reason: string, notes?: string) {
    const res = await apiClient.post<Approval>(`/approvals/${id}/deny`, { reason, notes });
    return res.data;
  },

  async bulkApprove(ids: string[], notes?: string) {
    const res = await apiClient.post<{ approved: string[] }>("/approvals/bulk-approve", { ids, notes });
    return res.data;
  },
};

export default approvalService;
