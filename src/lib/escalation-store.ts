'use client';

import { create } from 'zustand';
import { toast } from 'sonner';

// ── Types ────────────────────────────────────────────────────────────

export type TicketType =
  | 'billing'
  | 'technical'
  | 'account'
  | 'general'
  | 'refund'
  | 'feature_request'
  | 'complaint';

export type Complexity = 'simple' | 'moderate' | 'complex' | 'critical';
export type HumanStatus = 'pending' | 'guidance_provided' | 'resolved';
export type ReprocessStatus = 'pending' | 'processing' | 'done' | 'failed';
export type CrmProvider = 'zendesk' | 'hubspot' | 'generic' | '';
export type CrmStatus = 'pending' | 'updated' | 'failed' | '';

export interface Escalation {
  escalation_id: string;
  tenant_id: string;
  original_ticket_id: string;
  notification_key: string;
  original_query: string;
  ticket_type: TicketType;
  complexity: Complexity;
  required_action: string;
  knowledge_context: Array<{ title: string; snippet: string; score: number }>;
  customer_context: Record<string, unknown> | null;
  previous_attempts: string[];
  failure_analysis: string;
  quality_score: number;
  technique_log: Array<{ step: string; detail: string; duration_ms: number }>;
  human_guidance: string;
  human_status: HumanStatus;
  guidance_timestamp: string | null;
  guidance_source: string | null;
  reprocess_status: ReprocessStatus;
  reprocess_result: string;
  reprocess_quality_score: number | null;
  reprocess_technique_log: Array<{ step: string; detail: string; duration_ms: number }>;
  crm_ticket_id: string;
  crm_provider: CrmProvider;
  crm_status: CrmStatus;
  created_at: string;
  updated_at: string;
}

export interface EscalationStats {
  awaiting_human: number;
  guidance_provided: number;
  resolved: number;
  failed: number;
  total: number;
}

export interface EscalationFilters {
  humanStatus: HumanStatus | 'all';
  reprocessStatus: ReprocessStatus | 'all';
  search: string;
}

// ── Display Helpers ─────────────────────────────────────────────────

export const TICKET_TYPE_LABELS: Record<TicketType, string> = {
  billing: 'Billing',
  technical: 'Technical',
  account: 'Account',
  general: 'General',
  refund: 'Refund',
  feature_request: 'Feature Request',
  complaint: 'Complaint',
};

export const COMPLEXITY_LABELS: Record<Complexity, string> = {
  simple: 'Simple',
  moderate: 'Moderate',
  complex: 'Complex',
  critical: 'Critical',
};

export const HUMAN_STATUS_LABELS: Record<HumanStatus, string> = {
  pending: 'Awaiting Human',
  guidance_provided: 'Guidance Provided',
  resolved: 'Resolved',
};

export const REPROCESS_STATUS_LABELS: Record<ReprocessStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  done: 'Done',
  failed: 'Failed',
};

export const CRM_PROVIDER_LABELS: Record<string, string> = {
  zendesk: 'Zendesk',
  hubspot: 'HubSpot',
  generic: 'Generic',
};

export const ALL_HUMAN_STATUSES: HumanStatus[] = ['pending', 'guidance_provided', 'resolved'];
export const ALL_REPROCESS_STATUSES: ReprocessStatus[] = ['pending', 'processing', 'done', 'failed'];

// ── (Mock data removed for production) ────────────────────────────────


// ── Store Interface ──────────────────────────────────────────────────

interface EscalationStore {
  escalations: Escalation[];
  stats: EscalationStats;
  loading: boolean;
  providingGuidance: boolean;
  selectedEscalation: Escalation | null;
  isModalOpen: boolean;
  modalMode: 'guidance' | 'result';
  filters: EscalationFilters;
  autoResumeResult: { success: number; failed: number; message: string } | null;

  // Actions
  fetchEscalations: (tenantId: string, filters?: Partial<EscalationFilters>) => Promise<void>;
  fetchStats: (tenantId: string) => Promise<void>;
  setFilters: (filters: Partial<EscalationFilters>) => void;
  openModal: (escalation: Escalation, mode: 'guidance' | 'result') => void;
  closeModal: () => void;
  provideGuidance: (escalationId: string, guidance: string, source?: string) => Promise<boolean>;
  provideGuidanceByNotification: (notificationKey: string, guidance: string) => Promise<boolean>;
  resumeEscalation: (escalationId: string) => Promise<boolean>;
  autoResumeAll: (tenantId: string) => Promise<void>;
  createGuidanceTicket: (escalationId: string) => Promise<boolean>;
  batchGuidanceTickets: (tenantId: string) => Promise<void>;
}

// ── Store ────────────────────────────────────────────────────────────

export const useEscalationStore = create<EscalationStore>((set, get) => ({
  escalations: [],
  stats: { awaiting_human: 0, guidance_provided: 0, resolved: 0, failed: 0, total: 0 },
  loading: false,
  providingGuidance: false,
  selectedEscalation: null,
  isModalOpen: false,
  modalMode: 'guidance',
  filters: { humanStatus: 'all', reprocessStatus: 'all', search: '' },
  autoResumeResult: null,

  fetchEscalations: async (tenantId: string, filters?: Partial<EscalationFilters>) => {
    set({ loading: true, autoResumeResult: null });
    const mergedFilters = { ...get().filters, ...filters };

    try {
      const params = new URLSearchParams();
      params.set('tenant_id', tenantId);
      if (mergedFilters.humanStatus !== 'all') params.set('human_status', mergedFilters.humanStatus);
      if (mergedFilters.reprocessStatus !== 'all') params.set('reprocess_status', mergedFilters.reprocessStatus);
      if (mergedFilters.search) params.set('search', mergedFilters.search);

      const res = await fetch(`/api/escalations?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        set({ escalations: data.escalations || data, loading: false });
        return;
      }
    } catch {
      // Backend unavailable
    }
    set({ escalations: [], loading: false });
  },

  fetchStats: async (tenantId: string) => {
    try {
      const res = await fetch(`/api/escalations?action=stats&tenant_id=${tenantId}`);
      if (res.ok) {
        const data = await res.json();
        set({ stats: data });
        return;
      }
    } catch {
      // Backend unavailable
    }
    set({
      stats: { awaiting_human: 0, guidance_provided: 0, resolved: 0, failed: 0, total: 0 },
    });
  },

  setFilters: (filters: Partial<EscalationFilters>) => {
    set({ filters: { ...get().filters, ...filters } });
  },

  openModal: (escalation: Escalation, mode: 'guidance' | 'result') => {
    set({ selectedEscalation: escalation, isModalOpen: true, modalMode: mode });
  },

  closeModal: () => {
    set({ selectedEscalation: null, isModalOpen: false, modalMode: 'guidance' });
  },

  provideGuidance: async (escalationId: string, guidance: string, source: string = 'agent') => {
    set({ providingGuidance: true });
    try {
      const res = await fetch(`/api/escalations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'guidance', escalation_id: escalationId, guidance, source }),
      });
      if (res.ok) {
        const data = await res.json();
        // Update local state
        set((state) => ({
          escalations: state.escalations.map((e) =>
            e.escalation_id === escalationId
              ? {
                  ...e,
                  human_guidance: guidance,
                  human_status: 'guidance_provided' as HumanStatus,
                  guidance_timestamp: new Date().toISOString(),
                  guidance_source: source,
                }
              : e,
          ),
          providingGuidance: false,
        }));
        return true;
      }
    } catch {
      // Backend unavailable
    }
    set({ providingGuidance: false });
    toast.error('Could not save guidance. Backend unavailable.');
    return false;
  },

  provideGuidanceByNotification: async (notificationKey: string, guidance: string) => {
    set({ providingGuidance: true });
    try {
      const res = await fetch(`/api/escalations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'guidance-by-notification', notification_key: notificationKey, guidance }),
      });
      if (res.ok) {
        const data = await res.json();
        // Update local state
        set((state) => ({
          escalations: state.escalations.map((e) =>
            e.notification_key === notificationKey
              ? {
                  ...e,
                  human_guidance: guidance,
                  human_status: 'guidance_provided' as HumanStatus,
                  guidance_timestamp: new Date().toISOString(),
                  guidance_source: 'notification',
                }
              : e,
          ),
          providingGuidance: false,
        }));
        toast.success('Guidance saved. Ticket is now eligible for resume.');
        return true;
      }
    } catch {
      // Backend unavailable
    }
    set({ providingGuidance: false });
    toast.error('Could not save guidance. Backend unavailable.');
    return false;
  },

  resumeEscalation: async (escalationId: string) => {
    try {
      const res = await fetch(`/api/escalations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'resume', escalation_id: escalationId }),
      });
      if (res.ok) {
        set((state) => ({
          escalations: state.escalations.map((e) =>
            e.escalation_id === escalationId
              ? { ...e, reprocess_status: 'processing' as ReprocessStatus, updated_at: new Date().toISOString() }
              : e,
          ),
        }));
        toast.success('Escalation queued for reprocessing.');
        return true;
      }
    } catch {
      // Backend unavailable
    }
    toast.error('Could not resume escalation. Backend unavailable.');
    return false;
  },

  autoResumeAll: async (tenantId: string) => {
    set({ autoResumeResult: null, loading: true });
    try {
      const res = await fetch(`/api/escalations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'auto-resume', tenant_id: tenantId }),
      });
      if (res.ok) {
        const data = await res.json();
        set({
          autoResumeResult: data,
          loading: false,
        });
        toast.success(`Auto-resume complete: ${data.success} succeeded, ${data.failed} failed.`);
        // Refresh data
        get().fetchEscalations(tenantId);
        get().fetchStats(tenantId);
        return;
      }
    } catch {
      // Backend unavailable
    }
    set({ autoResumeResult: null, loading: false });
    toast.error('Could not auto-resume escalations. Backend unavailable.');
  },

  createGuidanceTicket: async (escalationId: string) => {
    try {
      const res = await fetch(`/api/escalations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'guidance-ticket', escalation_id: escalationId }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          set((state) => ({
            escalations: state.escalations.map((e) =>
              e.escalation_id === escalationId
                ? {
                    ...e,
                    reprocess_status: 'done' as ReprocessStatus,
                    reprocess_result: data.guidance_result || '',
                    reprocess_quality_score: data.quality_score ?? null,
                    human_status: 'resolved' as HumanStatus,
                    updated_at: new Date().toISOString(),
                  }
                : e,
            ),
          }));
          toast.success('Guidance used as direct answer. Quality passed!');
          return true;
        } else {
          toast.error(`Guidance ticket quality too low (${data.quality_score}). Resume failed.`);
          return false;
        }
      }
    } catch {
      // Backend unavailable
    }
    toast.error('Could not process guidance ticket. Backend unavailable.');
    return false;
  },

  batchGuidanceTickets: async (tenantId: string) => {
    set({ autoResumeResult: null, loading: true });
    try {
      const res = await fetch(`/api/escalations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'batch-guidance-tickets', tenant_id: tenantId }),
      });
      if (res.ok) {
        const data = await res.json();
        set({
          autoResumeResult: {
            success: data.resolved ?? 0,
            failed: data.failed ?? 0,
            message: `${data.resolved ?? 0} guidance tickets resolved, ${data.failed ?? 0} failed.`,
          },
          loading: false,
        });
        toast.success(`Batch guidance tickets: ${data.resolved ?? 0} resolved, ${data.failed ?? 0} failed.`);
        get().fetchEscalations(tenantId);
        get().fetchStats(tenantId);
        return;
      }
    } catch {
      // Backend unavailable
    }
    set({ autoResumeResult: { success: 0, failed: 0, message: 'Batch guidance failed. Backend unavailable.' }, loading: false });
    toast.error('Batch guidance failed. Backend unavailable.');
  },
}));