/**
 * PARWA Presence Store — Agent Online/Offline Presence
 *
 * Tracks which agents are currently online, their status,
 * and updates via Socket.io events.
 *
 * Socket.io events:
 *   presence:online    — { agent_id, name, avatar, status }
 *   presence:offline   — { agent_id }
 *   presence:status    — { agent_id, status: 'available'|'busy'|'away' }
 *   presence:bulk      — { agents: [...] }
 */

import { create } from 'zustand';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Types ────────────────────────────────────────────────────────────

export type AgentStatus = 'available' | 'busy' | 'away' | 'offline';

export interface AgentPresence {
  agentId: string;
  name: string;
  avatar?: string;
  status: AgentStatus;
  lastSeen: string;
  currentTicketId?: string;
}

interface PresenceState {
  // State
  agents: Map<string, AgentPresence>;
  onlineCount: number;

  // Actions
  setOnline: (data: { agent_id: string; name: string; avatar?: string; status?: AgentStatus; current_ticket_id?: string }) => void;
  setOffline: (agentId: string) => void;
  updateStatus: (agentId: string, status: AgentStatus) => void;
  setBulk: (agents: Array<{ agent_id: string; name: string; avatar?: string; status: AgentStatus; last_seen?: string; current_ticket_id?: string }>) => void;
  fetchPresence: () => Promise<void>;
  getAgent: (agentId: string) => AgentPresence | undefined;
  isOnline: (agentId: string) => boolean;
  getOnlineAgents: () => AgentPresence[];
  clearAll: () => void;
}

// ── Store ────────────────────────────────────────────────────────────

export const usePresenceStore = create<PresenceState>((set, get) => ({
  agents: new Map(),
  onlineCount: 0,

  setOnline: (data) => {
    set((state) => {
      const newAgents = new Map(state.agents);
      newAgents.set(data.agent_id, {
        agentId: data.agent_id,
        name: data.name,
        avatar: data.avatar,
        status: data.status || 'available',
        lastSeen: new Date().toISOString(),
        currentTicketId: data.current_ticket_id,
      });
      const onlineCount = [...newAgents.values()].filter(a => a.status !== 'offline').length;
      return { agents: newAgents, onlineCount };
    });
  },

  setOffline: (agentId) => {
    set((state) => {
      const newAgents = new Map(state.agents);
      const existing = newAgents.get(agentId);
      if (existing) {
        newAgents.set(agentId, { ...existing, status: 'offline', lastSeen: new Date().toISOString() });
      }
      const onlineCount = [...newAgents.values()].filter(a => a.status !== 'offline').length;
      return { agents: newAgents, onlineCount };
    });
  },

  updateStatus: (agentId, status) => {
    set((state) => {
      const newAgents = new Map(state.agents);
      const existing = newAgents.get(agentId);
      if (existing) {
        newAgents.set(agentId, { ...existing, status, lastSeen: new Date().toISOString() });
      }
      const onlineCount = [...newAgents.values()].filter(a => a.status !== 'offline').length;
      return { agents: newAgents, onlineCount };
    });
  },

  setBulk: (agents) => {
    set(() => {
      const newAgents = new Map<string, AgentPresence>();
      for (const a of agents) {
        newAgents.set(a.agent_id, {
          agentId: a.agent_id,
          name: a.name,
          avatar: a.avatar,
          status: a.status,
          lastSeen: a.last_seen || new Date().toISOString(),
          currentTicketId: a.current_ticket_id,
        });
      }
      const onlineCount = [...newAgents.values()].filter(a => a.status !== 'offline').length;
      return { agents: newAgents, onlineCount };
    });
  },

  fetchPresence: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/presence`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        const agents = Array.isArray(data) ? data : data.agents ?? [];
        get().setBulk(agents);
      } else if (res.status !== 404 && res.status !== 502 && res.status !== 503) {
        console.error('Failed to fetch presence:', res.status);
      }
    } catch {
      // Network error — keep existing data
    }
  },

  getAgent: (agentId) => get().agents.get(agentId),

  isOnline: (agentId) => {
    const agent = get().agents.get(agentId);
    return agent ? agent.status !== 'offline' : false;
  },

  getOnlineAgents: () => [...get().agents.values()].filter(a => a.status !== 'offline'),

  clearAll: () => set({ agents: new Map(), onlineCount: 0 }),
}));
