/**
 * PARWA Approval Store
 *
 * Zustand store for human-in-the-loop approval management.
 * Tracks AI agent approval requests (refunds, cancellations, escalations, etc.)
 * with real-time Socket.io updates and server-backed persistence.
 */

import { create } from 'zustand';
import { v4 as uuid } from 'uuid';

// ── Types ────────────────────────────────────────────────────────────

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'timeout' | 'expired';
export type ApprovalType =
  | 'refund'
  | 'cancellation'
  | 'escalation'
  | 'discount'
  | 'account_change'
  | 'data_deletion';

export interface Approval {
  id: string;
  type: ApprovalType;
  status: ApprovalStatus;
  title: string;
  description: string;
  requestedBy: string;
  ticketId?: string;
  ticketNumber?: string;
  customerName?: string;
  amount?: number;
  currency?: string;
  reason: string;
  riskLevel: 'low' | 'medium' | 'high';
  aiConfidence: number;
  createdAt: string;
  expiresAt: string;
  respondedAt?: string;
  respondedBy?: string;
  responseReason?: string;
  metadata?: Record<string, unknown>;
}

export interface ApprovalState {
  approvals: Approval[];
  pendingCount: number;
  isLoading: boolean;
  activeApprovalId: string | null;

  // Actions
  addApproval: (approval: Omit<Approval, 'id' | 'status' | 'createdAt'>) => void;
  approve: (id: string, reason?: string) => Promise<void>;
  reject: (id: string, reason?: string) => Promise<void>;
  setActiveApproval: (id: string | null) => void;

  // Socket.io event handlers
  handleApprovalPending: (data: any) => void;
  handleApprovalApproved: (data: { id: string; respondedBy?: string; reason?: string }) => void;
  handleApprovalRejected: (data: { id: string; respondedBy?: string; reason?: string }) => void;
  handleApprovalTimeout: (data: { id: string }) => void;
  handleApprovalBatch: (data: { approvals: any[] }) => void;

  // API
  fetchApprovals: () => Promise<void>;
  fetchPendingApprovals: () => Promise<void>;

  // Computed
  getPendingApprovals: () => Approval[];
  getApprovalById: (id: string) => Approval | undefined;
  getApprovalsByType: (type: ApprovalType) => Approval[];
  getApprovalsByStatus: (status: ApprovalStatus) => Approval[];
  isExpired: (id: string) => boolean;
}

// ── Display Helpers ──────────────────────────────────────────────────

export const APPROVAL_TYPE_LABELS: Record<ApprovalType, string> = {
  refund: 'Refund Request',
  cancellation: 'Cancellation',
  escalation: 'Escalation',
  discount: 'Discount',
  account_change: 'Account Change',
  data_deletion: 'Data Deletion',
};

export const APPROVAL_STATUS_LABELS: Record<ApprovalStatus, string> = {
  pending: 'Pending',
  approved: 'Approved',
  rejected: 'Rejected',
  timeout: 'Timed Out',
  expired: 'Expired',
};

export const APPROVAL_TYPE_COLORS: Record<ApprovalType, string> = {
  refund: 'from-emerald-500 to-emerald-400',
  cancellation: 'from-red-500 to-red-400',
  escalation: 'from-amber-500 to-amber-400',
  discount: 'from-sky-500 to-sky-400',
  account_change: 'from-violet-500 to-violet-400',
  data_deletion: 'from-rose-500 to-rose-400',
};

export const RISK_LEVEL_COLORS: Record<Approval['riskLevel'], string> = {
  low: 'bg-emerald-400',
  medium: 'bg-amber-400',
  high: 'bg-red-400',
};

export const APPROVAL_STATUS_COLORS: Record<ApprovalStatus, string> = {
  pending: 'bg-amber-400',
  approved: 'bg-emerald-400',
  rejected: 'bg-red-400',
  timeout: 'bg-zinc-400',
  expired: 'bg-zinc-400',
};

// ── Constants ────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Helpers ──────────────────────────────────────────────────────────

function computePendingCount(approvals: Approval[]): number {
  return approvals.filter((a) => a.status === 'pending').length;
}

function markExpiredApprovals(approvals: Approval[]): Approval[] {
  const now = new Date();
  return approvals.map((a) => {
    if (a.status === 'pending' && new Date(a.expiresAt) < now) {
      return { ...a, status: 'timeout' as ApprovalStatus };
    }
    return a;
  });
}

function normalizeApproval(a: Record<string, unknown>): Approval {
  return {
    id: String(a.id || uuid()),
    type: (a.type || a.approval_type || 'refund') as ApprovalType,
    status: (a.status || 'pending') as ApprovalStatus,
    title: String(a.title || ''),
    description: String(a.description || a.reason || ''),
    requestedBy: String(a.requested_by || a.requestedBy || 'AI Agent'),
    ticketId: a.ticket_id ? String(a.ticket_id) : a.ticketId ? String(a.ticketId) : undefined,
    ticketNumber: a.ticket_number ? String(a.ticket_number) : a.ticketNumber ? String(a.ticketNumber) : undefined,
    customerName: a.customer_name ? String(a.customer_name) : a.customerName ? String(a.customerName) : undefined,
    amount: a.amount != null ? Number(a.amount) : undefined,
    currency: a.currency ? String(a.currency) : undefined,
    reason: String(a.reason || ''),
    riskLevel: (a.risk_level || a.riskLevel || 'medium') as Approval['riskLevel'],
    aiConfidence: Number(a.ai_confidence ?? a.aiConfidence ?? 0),
    createdAt: String(a.created_at || a.createdAt || new Date().toISOString()),
    expiresAt: String(a.expires_at || a.expiresAt || new Date(Date.now() + 3600000).toISOString()),
    respondedAt: a.responded_at ? String(a.responded_at) : a.respondedAt ? String(a.respondedAt) : undefined,
    respondedBy: a.responded_by ? String(a.responded_by) : a.respondedBy ? String(a.respondedBy) : undefined,
    responseReason: a.response_reason ? String(a.response_reason) : a.responseReason ? String(a.responseReason) : undefined,
    metadata: (a.metadata || undefined) as Record<string, unknown> | undefined,
  };
}

// ── Store ────────────────────────────────────────────────────────────

export const useApprovalStore = create<ApprovalState>((set, get) => ({
  approvals: [],
  pendingCount: 0,
  isLoading: false,
  activeApprovalId: null,

  addApproval: (approval) => {
    const newApproval: Approval = {
      ...approval,
      id: uuid(),
      status: 'pending',
      createdAt: new Date().toISOString(),
    };

    set((state) => {
      const approvals = [newApproval, ...state.approvals];
      const pendingCount = computePendingCount(approvals);
      return { approvals, pendingCount };
    });
  },

  approve: async (id, reason?: string) => {
    const now = new Date().toISOString();

    // Optimistic update
    set((state) => {
      const approvals = state.approvals.map((a) =>
        a.id === id
          ? { ...a, status: 'approved' as ApprovalStatus, respondedAt: now, respondedBy: 'You', responseReason: reason }
          : a
      );
      const pendingCount = computePendingCount(approvals);
      return { approvals, pendingCount };
    });

    try {
      const res = await fetch(`${API_BASE}/api/v1/approvals/${id}`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'approved', reason }),
      });

      if (!res.ok) {
        // Revert on failure
        set((state) => {
          const approvals = state.approvals.map((a) =>
            a.id === id
              ? { ...a, status: 'pending' as ApprovalStatus, respondedAt: undefined, respondedBy: undefined, responseReason: undefined }
              : a
          );
          const pendingCount = computePendingCount(approvals);
          return { approvals, pendingCount };
        });
        throw new Error(`Failed to approve: ${res.status}`);
      }
    } catch (error) {
      // Already reverted above; re-throw so caller can handle
      throw error;
    }
  },

  reject: async (id, reason?: string) => {
    const now = new Date().toISOString();

    // Optimistic update
    set((state) => {
      const approvals = state.approvals.map((a) =>
        a.id === id
          ? { ...a, status: 'rejected' as ApprovalStatus, respondedAt: now, respondedBy: 'You', responseReason: reason }
          : a
      );
      const pendingCount = computePendingCount(approvals);
      return { approvals, pendingCount };
    });

    try {
      const res = await fetch(`${API_BASE}/api/v1/approvals/${id}`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'rejected', reason }),
      });

      if (!res.ok) {
        // Revert on failure
        set((state) => {
          const approvals = state.approvals.map((a) =>
            a.id === id
              ? { ...a, status: 'pending' as ApprovalStatus, respondedAt: undefined, respondedBy: undefined, responseReason: undefined }
              : a
          );
          const pendingCount = computePendingCount(approvals);
          return { approvals, pendingCount };
        });
        throw new Error(`Failed to reject: ${res.status}`);
      }
    } catch (error) {
      throw error;
    }
  },

  setActiveApproval: (id) => {
    set({ activeApprovalId: id });
  },

  // ── Socket.io Event Handlers ─────────────────────────────────────

  handleApprovalPending: (data: any) => {
    const approval = normalizeApproval(data);
    approval.status = 'pending';
    approval.id = data.id || uuid();

    set((state) => {
      // Avoid duplicates
      if (state.approvals.some((a) => a.id === approval.id)) {
        return state;
      }
      const approvals = [approval, ...state.approvals];
      const pendingCount = computePendingCount(approvals);
      return { approvals, pendingCount };
    });
  },

  handleApprovalApproved: (data: { id: string; respondedBy?: string; reason?: string }) => {
    const now = new Date().toISOString();
    set((state) => {
      const approvals = state.approvals.map((a) =>
        a.id === data.id
          ? {
              ...a,
              status: 'approved' as ApprovalStatus,
              respondedAt: now,
              respondedBy: data.respondedBy || 'System',
              responseReason: data.reason,
            }
          : a
      );
      const pendingCount = computePendingCount(approvals);
      return { approvals, pendingCount };
    });
  },

  handleApprovalRejected: (data: { id: string; respondedBy?: string; reason?: string }) => {
    const now = new Date().toISOString();
    set((state) => {
      const approvals = state.approvals.map((a) =>
        a.id === data.id
          ? {
              ...a,
              status: 'rejected' as ApprovalStatus,
              respondedAt: now,
              respondedBy: data.respondedBy || 'System',
              responseReason: data.reason,
            }
          : a
      );
      const pendingCount = computePendingCount(approvals);
      return { approvals, pendingCount };
    });
  },

  handleApprovalTimeout: (data: { id: string }) => {
    set((state) => {
      const approvals = state.approvals.map((a) =>
        a.id === data.id
          ? { ...a, status: 'timeout' as ApprovalStatus, respondedAt: new Date().toISOString() }
          : a
      );
      const pendingCount = computePendingCount(approvals);
      return { approvals, pendingCount };
    });
  },

  handleApprovalBatch: (data: { approvals: any[] }) => {
    if (!Array.isArray(data.approvals)) return;

    const incoming: Approval[] = data.approvals.map((a: Record<string, unknown>) => normalizeApproval(a));

    set((state) => {
      // Merge: incoming replaces existing by id
      const existingMap = new Map(state.approvals.map((a) => [a.id, a]));
      for (const a of incoming) {
        existingMap.set(a.id, a);
      }
      const approvals = markExpiredApprovals(
        Array.from(existingMap.values()).sort(
          (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        )
      );
      const pendingCount = computePendingCount(approvals);
      return { approvals, pendingCount };
    });
  },

  // ── API ──────────────────────────────────────────────────────────

  fetchApprovals: async () => {
    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE}/api/v1/approvals`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        if (res.status === 404 || res.status === 502 || res.status === 503) {
          set({ isLoading: false });
          return;
        }
        throw new Error(`Failed to fetch approvals: ${res.status}`);
      }

      const data = await res.json();
      const list = Array.isArray(data) ? data : (data.approvals || []);

      const approvals = markExpiredApprovals(
        list.map((a: Record<string, unknown>) => normalizeApproval(a))
      );
      const pendingCount = computePendingCount(approvals);
      set({ approvals, pendingCount, isLoading: false });
    } catch {
      // On error, keep existing approvals
      set({ isLoading: false });
    }
  },

  fetchPendingApprovals: async () => {
    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE}/api/v1/approvals?status=pending`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        if (res.status === 404 || res.status === 502 || res.status === 503) {
          set({ isLoading: false });
          return;
        }
        throw new Error(`Failed to fetch pending approvals: ${res.status}`);
      }

      const data = await res.json();
      const list = Array.isArray(data) ? data : (data.approvals || []);

      const pendingApprovals = list.map((a: Record<string, unknown>) => normalizeApproval(a));

      set((state) => {
        // Merge pending approvals into existing, replacing by id
        const existingMap = new Map(state.approvals.map((a) => [a.id, a]));
        for (const a of pendingApprovals) {
          existingMap.set(a.id, a);
        }
        const approvals = markExpiredApprovals(
          Array.from(existingMap.values()).sort(
            (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          )
        );
        const pendingCount = computePendingCount(approvals);
        return { approvals, pendingCount, isLoading: false };
      });
    } catch {
      set({ isLoading: false });
    }
  },

  // ── Computed ─────────────────────────────────────────────────────

  getPendingApprovals: () => {
    return get().approvals.filter((a) => a.status === 'pending');
  },

  getApprovalById: (id: string) => {
    return get().approvals.find((a) => a.id === id);
  },

  getApprovalsByType: (type: ApprovalType) => {
    return get().approvals.filter((a) => a.type === type);
  },

  getApprovalsByStatus: (status: ApprovalStatus) => {
    return get().approvals.filter((a) => a.status === status);
  },

  isExpired: (id: string) => {
    const approval = get().approvals.find((a) => a.id === id);
    if (!approval) return false;
    return new Date(approval.expiresAt) < new Date();
  },
}));
