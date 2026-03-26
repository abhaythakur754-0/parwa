/**
 * PARWA useAgents Hook
 *
 * Custom hook for agent management.
 * Handles fetching agent list, status, and control actions.
 *
 * Features:
 * - Fetch agents list with status
 * - Pause/resume agents
 * - View agent logs
 * - Real-time status updates
 */

import { useState, useCallback, useEffect } from "react";
import { apiClient } from "../services/api/client";
import { useUIStore } from "../stores/uiStore";

/**
 * Agent variant type.
 */
export type AgentVariant = "mini" | "parwa" | "parwa_high";

/**
 * Agent status type.
 */
export type AgentStatus = "active" | "idle" | "offline" | "paused" | "error";

/**
 * Agent task interface.
 */
export interface AgentTask {
  id: string;
  type: string;
  status: "running" | "completed" | "failed";
  startedAt: string;
  completedAt?: string;
  metadata?: Record<string, unknown>;
}

/**
 * Agent metrics interface.
 */
export interface AgentMetrics {
  accuracy: number;
  avgResponseTime: number;
  ticketsResolved: number;
  escalationsHandled: number;
  csatScore: number;
  uptime: number;
}

/**
 * Agent interface.
 */
export interface Agent {
  id: string;
  name: string;
  variant: AgentVariant;
  status: AgentStatus;
  currentTask?: AgentTask;
  metrics: AgentMetrics;
  lastActivity: string;
  createdAt: string;
  config: {
    maxConcurrentCalls: number;
    refundLimit: number;
    escalationThreshold: number;
  };
}

/**
 * Agent log entry interface.
 */
export interface AgentLogEntry {
  id: string;
  agentId: string;
  level: "info" | "warning" | "error" | "debug";
  message: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

/**
 * Agents list response.
 */
export interface AgentsListResponse {
  agents: Agent[];
  total: number;
}

/**
 * useAgents hook return type.
 */
export interface UseAgentsReturn {
  /** List of agents */
  agents: Agent[];
  /** Agent status map */
  agentStatus: Record<string, AgentStatus>;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: string | null;

  // Actions
  /** Fetch agents list */
  fetchAgents: () => Promise<void>;
  /** Pause an agent */
  pauseAgent: (id: string) => Promise<void>;
  /** Resume an agent */
  resumeAgent: (id: string) => Promise<void>;
  /** Fetch agent logs */
  fetchAgentLogs: (id: string, limit?: number) => Promise<AgentLogEntry[]>;
  /** Get single agent by ID */
  getAgentById: (id: string) => Agent | undefined;
  /** Refresh agents list */
  refresh: () => Promise<void>;
  /** Clear error */
  clearError: () => void;
}

/**
 * Custom hook for agent management.
 *
 * @returns Agents state and actions
 *
 * @example
 * ```tsx
 * function AgentsStatusPage() {
 *   const {
 *     agents,
 *     isLoading,
 *     pauseAgent,
 *     resumeAgent,
 *     fetchAgentLogs
 *   } = useAgents();
 *
 *   return (
 *     <div>
 *       {agents.map(agent => (
 *         <AgentCard
 *           key={agent.id}
 *           agent={agent}
 *           onPause={() => pauseAgent(agent.id)}
 *           onResume={() => resumeAgent(agent.id)}
 *         />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useAgents(): UseAgentsReturn {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentStatus, setAgentStatus] = useState<Record<string, AgentStatus>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { addToast } = useUIStore();

  /**
   * Fetch agents list from API.
   */
  const fetchAgents = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.get<AgentsListResponse>("/agents");

      setAgents(response.data.agents);

      // Build status map
      const statusMap: Record<string, AgentStatus> = {};
      response.data.agents.forEach((agent) => {
        statusMap[agent.id] = agent.status;
      });
      setAgentStatus(statusMap);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch agents";
      setError(message);
      addToast({
        title: "Error",
        description: message,
        variant: "error",
      });
    } finally {
      setIsLoading(false);
    }
  }, [addToast]);

  /**
   * Pause an agent.
   */
  const pauseAgent = useCallback(
    async (id: string): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        await apiClient.post<Agent>(`/agents/${id}/pause`);

        // Update local state
        setAgents((prev) =>
          prev.map((agent) =>
            agent.id === id ? { ...agent, status: "paused" as AgentStatus } : agent
          )
        );
        setAgentStatus((prev) => ({ ...prev, [id]: "paused" }));

        addToast({
          title: "Agent paused",
          description: "The agent has been paused successfully.",
          variant: "success",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to pause agent";
        setError(message);
        addToast({
          title: "Error",
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
   * Resume an agent.
   */
  const resumeAgent = useCallback(
    async (id: string): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        await apiClient.post<Agent>(`/agents/${id}/resume`);

        // Update local state
        setAgents((prev) =>
          prev.map((agent) =>
            agent.id === id ? { ...agent, status: "idle" as AgentStatus } : agent
          )
        );
        setAgentStatus((prev) => ({ ...prev, [id]: "idle" }));

        addToast({
          title: "Agent resumed",
          description: "The agent has been resumed successfully.",
          variant: "success",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to resume agent";
        setError(message);
        addToast({
          title: "Error",
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
   * Fetch agent logs.
   */
  const fetchAgentLogs = useCallback(
    async (id: string, limit = 50): Promise<AgentLogEntry[]> => {
      setIsLoading(true);

      try {
        const response = await apiClient.get<AgentLogEntry[]>(`/agents/${id}/logs`, {
          limit: String(limit),
        });

        return response.data;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to fetch agent logs";
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });
        return [];
      } finally {
        setIsLoading(false);
      }
    },
    [addToast]
  );

  /**
   * Get single agent by ID.
   */
  const getAgentById = useCallback(
    (id: string): Agent | undefined => {
      return agents.find((agent) => agent.id === id);
    },
    [agents]
  );

  /**
   * Refresh agents list.
   */
  const refresh = useCallback(async (): Promise<void> => {
    await fetchAgents();
  }, [fetchAgents]);

  /**
   * Clear error.
   */
  const clearError = useCallback((): void => {
    setError(null);
  }, []);

  /**
   * Auto-fetch on mount.
   */
  useEffect(() => {
    fetchAgents();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    agents,
    agentStatus,
    isLoading,
    error,
    fetchAgents,
    pauseAgent,
    resumeAgent,
    fetchAgentLogs,
    getAgentById,
    refresh,
    clearError,
  };
}

export default useAgents;
