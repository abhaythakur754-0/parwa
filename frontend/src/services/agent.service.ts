/**
 * PARWA Agent Service
 * Handles agent management API operations.
 */

import { apiClient } from "./api/client";

export interface Agent {
  id: string;
  name: string;
  variant: "mini" | "parwa" | "parwa_high";
  status: "active" | "idle" | "offline" | "paused" | "error";
  currentTask?: { id: string; type: string; status: string };
  metrics: { accuracy: number; avgResponseTime: number; ticketsResolved: number };
  lastActivity: string;
  config: { maxConcurrentCalls: number; refundLimit: number };
}

export interface AgentLog {
  id: string;
  agentId: string;
  level: "info" | "warning" | "error" | "debug";
  message: string;
  timestamp: string;
}

export const agentService = {
  async getAgents() {
    const res = await apiClient.get<{ agents: Agent[]; total: number }>("/agents");
    return res.data;
  },

  async getAgent(id: string) {
    const res = await apiClient.get<Agent>(`/agents/${id}`);
    return res.data;
  },

  async pauseAgent(id: string) {
    const res = await apiClient.post<Agent>(`/agents/${id}/pause`);
    return res.data;
  },

  async resumeAgent(id: string) {
    const res = await apiClient.post<Agent>(`/agents/${id}/resume`);
    return res.data;
  },

  async getAgentLogs(id: string, limit = 50) {
    const res = await apiClient.get<AgentLog[]>(`/agents/${id}/logs`, { limit: String(limit) });
    return res.data;
  },

  async updateAgentConfig(id: string, config: Partial<Agent["config"]>) {
    const res = await apiClient.patch<Agent>(`/agents/${id}/config`, config);
    return res.data;
  },
};

export default agentService;
