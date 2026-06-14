/**
 * PARWA Agents Store
 *
 * Zustand store for AI agent instances. Manages agent list,
 * status tracking, performance metrics, and tier limit enforcement.
 */

import { create } from 'zustand';

// ── Types ────────────────────────────────────────────────────────────

export type AgentType =
  | 'faq'
  | 'refund'
  | 'technical'
  | 'billing'
  | 'complaint'
  | 'fraud'
  | 'quality_coach'
  | 'churn_predictor'
  | 'shipping'
  | 'general';

export type AgentStatus = 'active' | 'idle' | 'error' | 'initializing';

export interface AgentMetrics {
  ticketsHandled: number;
  avgResponseTime: number; // seconds
  satisfactionScore: number; // 0-100
  resolutionRate: number; // 0-100
  totalCost: number;
  totalSavings: number;
}

export interface Agent {
  id: string;
  name: string;
  type: AgentType;
  status: AgentStatus;
  variant: 'light' | 'medium' | 'heavy';
  model: string;
  domain: string;
  createdAt: string;
  lastActiveAt: string | null;
  metrics: AgentMetrics;
  isAvailable: boolean;
}

export interface AgentsState {
  agents: Agent[];
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchAgents: () => Promise<void>;
  getAgentsByType: (type: AgentType) => Agent[];
  getAgentsByStatus: (status: AgentStatus) => Agent[];
  getAgent: (id: string) => Agent | undefined;
  getActiveAgentCount: () => number;
  getTotalMetrics: () => AgentMetrics;
}

// ── Agent Display Helpers ──────────────────────────────────────────

export const AGENT_TYPE_LABELS: Record<AgentType, string> = {
  faq: 'FAQ Agent',
  refund: 'Refund Agent',
  technical: 'Technical Support',
  billing: 'Billing Agent',
  complaint: 'Complaint Handler',
  fraud: 'Fraud Detection',
  quality_coach: 'Quality Coach',
  churn_predictor: 'Churn Predictor',
  shipping: 'Shipping Agent',
  general: 'General Agent',
};

export const AGENT_TYPE_COLORS: Record<AgentType, string> = {
  faq: 'from-blue-500 to-blue-400',
  refund: 'from-green-500 to-green-400',
  technical: 'from-purple-500 to-purple-400',
  billing: 'from-emerald-500 to-emerald-400',
  complaint: 'from-red-500 to-red-400',
  fraud: 'from-rose-500 to-rose-400',
  quality_coach: 'from-amber-500 to-amber-400',
  churn_predictor: 'from-pink-500 to-pink-400',
  shipping: 'from-cyan-500 to-cyan-400',
  general: 'from-zinc-500 to-zinc-400',
};

export const AGENT_STATUS_COLORS: Record<AgentStatus, string> = {
  active: 'bg-emerald-400',
  idle: 'bg-zinc-400',
  error: 'bg-red-400',
  initializing: 'bg-amber-400',
};

export const AGENT_STATUS_LABELS: Record<AgentStatus, string> = {
  active: 'Active',
  idle: 'Idle',
  error: 'Error',
  initializing: 'Initializing',
};

// ── Store ───────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const useAgentsStore = create<AgentsState>((set, get) => ({
  agents: [],
  isLoading: false,
  error: null,

  fetchAgents: async () => {
    set({ isLoading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/api/v1/ai/instances`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        // If backend is not available, use empty list
        if (res.status === 404 || res.status === 502 || res.status === 503) {
          set({ agents: [], isLoading: false });
          return;
        }
        throw new Error(`Failed to fetch agents: ${res.status}`);
      }

      const data = await res.json();

      // Handle different response formats
      const agentList = Array.isArray(data) ? data : (data.agents || data.instances || []);

      const agents: Agent[] = agentList.map((a: Record<string, unknown>) => ({
        id: String(a.id || a.instance_id || ''),
        name: String(a.name || a.agent_name || 'Unnamed Agent'),
        type: (a.type || a.agent_type || 'general') as AgentType,
        status: (a.status || 'idle') as AgentStatus,
        variant: (a.variant || 'light') as 'light' | 'medium' | 'heavy',
        model: String(a.model || a.llm_model || 'Unknown'),
        domain: String(a.domain || 'general'),
        createdAt: String(a.created_at || a.createdAt || new Date().toISOString()),
        lastActiveAt: a.last_active_at ? String(a.last_active_at) : null,
        metrics: {
          ticketsHandled: Number(a.tickets_handled ?? a.metrics?.ticketsHandled ?? 0),
          avgResponseTime: Number(a.avg_response_time ?? a.metrics?.avgResponseTime ?? 0),
          satisfactionScore: Number(a.satisfaction_score ?? a.metrics?.satisfactionScore ?? 0),
          resolutionRate: Number(a.resolution_rate ?? a.metrics?.resolutionRate ?? 0),
          totalCost: Number(a.total_cost ?? a.metrics?.totalCost ?? 0),
          totalSavings: Number(a.total_savings ?? a.metrics?.totalSavings ?? 0),
        },
        isAvailable: Boolean(a.is_available ?? a.isAvailable ?? true),
      }));

      set({ agents, isLoading: false });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch agents',
        agents: [], // Empty on error so UI doesn't show stale data
      });
    }
  },

  getAgentsByType: (type: AgentType) => get().agents.filter((a) => a.type === type),
  getAgentsByStatus: (status: AgentStatus) => get().agents.filter((a) => a.status === status),
  getAgent: (id: string) => get().agents.find((a) => a.id === id),

  getActiveAgentCount: () => get().agents.filter((a) => a.status === 'active' || a.status === 'idle').length,

  getTotalMetrics: () => {
    const agents = get().agents;
    return agents.reduce(
      (acc, a) => ({
        ticketsHandled: acc.ticketsHandled + a.metrics.ticketsHandled,
        avgResponseTime: acc.avgResponseTime + a.metrics.avgResponseTime,
        satisfactionScore: acc.satisfactionScore + a.metrics.satisfactionScore,
        resolutionRate: acc.resolutionRate + a.metrics.resolutionRate,
        totalCost: acc.totalCost + a.metrics.totalCost,
        totalSavings: acc.totalSavings + a.metrics.totalSavings,
      }),
      {
        ticketsHandled: 0,
        avgResponseTime: 0,
        satisfactionScore: 0,
        resolutionRate: 0,
        totalCost: 0,
        totalSavings: 0,
      }
    );
  },
}));
