/**
 * PARWA Agents API Client
 *
 * Dedicated API client for all AI agent-related endpoints.
 * Full TypeScript types matching the backend schema.
 */

import { get, post, put } from '@/lib/api';

// ── Agent Types ─────────────────────────────────────────────────────────

export interface Agent {
  id: string;
  company_id: string;
  name: string;
  specialty: string;
  description: string | null;
  status: string;
  channels: Record<string, any>;
  permissions: Record<string, any>;
  base_model: string | null;
  model_checkpoint_id: string | null;
  created_by: string | null;
  created_at: string | null;
  activated_at: string | null;
  updated_at: string | null;
}

export interface AgentCardData {
  agent: Agent;
  tickets_assigned: number;
  tickets_resolved: number;
  tickets_open: number;
  resolution_rate: number;
  csat_avg: number;
  avg_confidence: number;
}

export interface AgentCreateRequest {
  name: string;
  specialty: string;
  description?: string;
  channels?: string[];
  permission_level?: string;
  base_model?: string;
  requires_approval?: boolean;
}

export interface AgentStatusCounts {
  active: number;
  paused: number;
  error: number;
  initializing: number;
  total: number;
}

export interface AgentMetrics {
  tickets_handled_7d: number;
  resolution_rate_7d: number;
  csat_avg_7d: number;
  avg_response_time_7d: number;
  confidence_avg_7d: number;
  mistakes_7d: number;
}

export interface AgentMistake {
  id: string;
  timestamp: string;
  ticket_id: string;
  error_type: string;
  description: string;
}

export interface AgentComparisonResult {
  agents: Array<{
    agent_id: string;
    name: string;
    specialty: string;
    metrics: Record<string, any>;
  }>;
  comparison: Record<string, any>;
}

// ── Agents API ─────────────────────────────────────────────────────────

export const agentsApi = {
  // ── Dashboard Cards ──────────────────────────────────────────────
  getAgentCards: () =>
    get<{ agents: AgentCardData[]; total: number }>('/api/agents/dashboard'),

  getAgentCardDetail: (id: string) =>
    get<AgentCardData>(`/api/agents/dashboard/${id}`),

  getStatusCounts: () =>
    get<AgentStatusCounts>('/api/agents/dashboard/status-counts'),

  // ── Actions ──────────────────────────────────────────────────────
  pauseAgent: (id: string) =>
    post(`/api/agents/dashboard/${id}/pause`),

  resumeAgent: (id: string) =>
    post(`/api/agents/dashboard/${id}/resume`),

  // ── Metrics ──────────────────────────────────────────────────────
  getRealtimeMetrics: (id: string) =>
    get<Record<string, any>>(`/api/agents/dashboard/${id}/metrics`),

  getAgentMetrics: (id: string) =>
    get<AgentMetrics>(`/api/agents/${id}/metrics`),

  getThresholds: (id: string) =>
    get<Record<string, any>>(`/api/agents/${id}/metrics/thresholds`),

  updateThresholds: (id: string, data: any) =>
    put(`/api/agents/${id}/metrics/thresholds`, data),

  compareAgents: (agentIds: string[]) =>
    get<AgentComparisonResult>(`/api/agents/metrics/compare?agent_ids=${agentIds.join(',')}`),

  // ── CRUD ─────────────────────────────────────────────────────────
  listAgents: (params?: { limit?: number; offset?: number; status?: string }) => {
    const sp = new URLSearchParams();
    if (params?.limit) sp.set('limit', String(params.limit));
    if (params?.offset) sp.set('offset', String(params.offset));
    if (params?.status) sp.set('status', params.status);
    const qs = sp.toString();
    return get<{ agents: Agent[]; total: number; limit: number; offset: number }>(
      `/api/agents${qs ? `?${qs}` : ''}`
    );
  },

  getAgent: (id: string) =>
    get<Agent>(`/api/agents/${id}`),

  createAgent: (data: AgentCreateRequest) =>
    post<{ agent: Agent; message: string }>('/api/agents/create', data),
};

export default agentsApi;
