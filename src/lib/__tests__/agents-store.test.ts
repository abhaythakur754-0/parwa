/**
 * PARWA Agents Store — Unit Tests
 *
 * Tests fetchAgents, filtering, metrics aggregation, and error handling.
 */

import { useAgentsStore, AGENT_TYPE_LABELS, AGENT_STATUS_LABELS } from '@/lib/agents-store';

describe('useAgentsStore', () => {
  beforeEach(() => {
    useAgentsStore.setState({
      agents: [],
      isLoading: false,
      error: null,
    });
  });

  describe('initial state', () => {
    it('starts with empty agents list', () => {
      expect(useAgentsStore.getState().agents).toEqual([]);
    });

    it('is not loading initially', () => {
      expect(useAgentsStore.getState().isLoading).toBe(false);
    });

    it('has no error initially', () => {
      expect(useAgentsStore.getState().error).toBeNull();
    });
  });

  describe('fetchAgents', () => {
    it('fetches agents from array response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            id: 'agent-1',
            name: 'FAQ Bot',
            type: 'faq',
            status: 'active',
            variant: 'light',
            model: 'gemini-flash',
            domain: 'general',
            created_at: '2026-01-01T00:00:00Z',
            last_active_at: '2026-05-14T00:00:00Z',
            tickets_handled: 100,
            avg_response_time: 2.5,
            satisfaction_score: 95,
            resolution_rate: 88,
            total_cost: 0.2,
            total_savings: 1249.8,
            is_available: true,
          },
        ],
      });

      await useAgentsStore.getState().fetchAgents();

      const agents = useAgentsStore.getState().agents;
      expect(agents).toHaveLength(1);
      expect(agents[0].name).toBe('FAQ Bot');
      expect(agents[0].type).toBe('faq');
      expect(agents[0].status).toBe('active');
      expect(agents[0].metrics.ticketsHandled).toBe(100);
      expect(agents[0].metrics.avgResponseTime).toBe(2.5);
    });

    it('handles agents wrapped in object response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          agents: [
            { id: '1', agent_name: 'Refund Agent', agent_type: 'refund', status: 'idle', variant: 'medium', llm_model: 'gemini-pro' },
          ],
        }),
      });

      await useAgentsStore.getState().fetchAgents();

      const agents = useAgentsStore.getState().agents;
      expect(agents).toHaveLength(1);
      expect(agents[0].name).toBe('Refund Agent');
      expect(agents[0].type).toBe('refund');
      expect(agents[0].model).toBe('gemini-pro');
    });

    it('handles instances key response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          instances: [
            { instance_id: 'inst-1', name: 'Tech Agent', type: 'technical', status: 'active' },
          ],
        }),
      });

      await useAgentsStore.getState().fetchAgents();

      const agents = useAgentsStore.getState().agents;
      expect(agents).toHaveLength(1);
      expect(agents[0].id).toBe('inst-1');
    });

    it('returns empty list on 404/502/503', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 502,
      });

      await useAgentsStore.getState().fetchAgents();

      expect(useAgentsStore.getState().agents).toEqual([]);
      expect(useAgentsStore.getState().error).toBeNull();
    });

    it('sets error on other HTTP errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await useAgentsStore.getState().fetchAgents();

      expect(useAgentsStore.getState().error).toContain('500');
      expect(useAgentsStore.getState().agents).toEqual([]);
    });

    it('sets error on network failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      await useAgentsStore.getState().fetchAgents();

      expect(useAgentsStore.getState().error).toBe('Network error');
      expect(useAgentsStore.getState().agents).toEqual([]);
    });

    it('sets isLoading during fetch', async () => {
      let resolvePromise: (value: unknown) => void;
      const fetchPromise = new Promise((resolve) => { resolvePromise = resolve; });
      (global.fetch as jest.Mock).mockReturnValueOnce(fetchPromise);

      const agentsPromise = useAgentsStore.getState().fetchAgents();
      expect(useAgentsStore.getState().isLoading).toBe(true);

      resolvePromise!({ ok: true, json: async () => [] });
      await agentsPromise;
      expect(useAgentsStore.getState().isLoading).toBe(false);
    });

    it('provides sensible defaults for missing fields', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => [{}],
      });

      await useAgentsStore.getState().fetchAgents();

      const agent = useAgentsStore.getState().agents[0];
      expect(agent.name).toBe('Unnamed Agent');
      expect(agent.type).toBe('general');
      expect(agent.status).toBe('idle');
      expect(agent.model).toBe('Unknown');
      expect(agent.isAvailable).toBe(true);
    });
  });

  describe('filter methods', () => {
    beforeEach(() => {
      useAgentsStore.setState({
        agents: [
          { id: '1', name: 'FAQ Bot', type: 'faq', status: 'active', variant: 'light', model: 'gemini-flash', domain: 'general', createdAt: '2026-01-01', lastActiveAt: '2026-05-14', metrics: { ticketsHandled: 100, avgResponseTime: 2.5, satisfactionScore: 95, resolutionRate: 88, totalCost: 0.2, totalSavings: 1249.8 }, isAvailable: true },
          { id: '2', name: 'Refund Agent', type: 'refund', status: 'idle', variant: 'medium', model: 'gemini-pro', domain: 'billing', createdAt: '2026-01-01', lastActiveAt: '2026-05-13', metrics: { ticketsHandled: 50, avgResponseTime: 5, satisfactionScore: 90, resolutionRate: 85, totalCost: 0.75, totalSavings: 624.25 }, isAvailable: true },
          { id: '3', name: 'Tech Agent', type: 'technical', status: 'active', variant: 'heavy', model: 'claude-3.5', domain: 'tech', createdAt: '2026-01-01', lastActiveAt: '2026-05-14', metrics: { ticketsHandled: 30, avgResponseTime: 8, satisfactionScore: 92, resolutionRate: 80, totalCost: 1.5, totalSavings: 373.5 }, isAvailable: true },
          { id: '4', name: 'Broken Agent', type: 'faq', status: 'error', variant: 'light', model: 'gemini-flash', domain: 'general', createdAt: '2026-01-01', lastActiveAt: null, metrics: { ticketsHandled: 0, avgResponseTime: 0, satisfactionScore: 0, resolutionRate: 0, totalCost: 0, totalSavings: 0 }, isAvailable: false },
        ],
      });
    });

    it('getAgentsByType returns correct agents', () => {
      expect(useAgentsStore.getState().getAgentsByType('faq')).toHaveLength(2);
      expect(useAgentsStore.getState().getAgentsByType('refund')).toHaveLength(1);
      expect(useAgentsStore.getState().getAgentsByType('technical')).toHaveLength(1);
      expect(useAgentsStore.getState().getAgentsByType('fraud')).toHaveLength(0);
    });

    it('getAgentsByStatus returns correct agents', () => {
      expect(useAgentsStore.getState().getAgentsByStatus('active')).toHaveLength(2);
      expect(useAgentsStore.getState().getAgentsByStatus('idle')).toHaveLength(1);
      expect(useAgentsStore.getState().getAgentsByStatus('error')).toHaveLength(1);
    });

    it('getAgent returns specific agent by id', () => {
      const agent = useAgentsStore.getState().getAgent('2');
      expect(agent).toBeDefined();
      expect(agent!.name).toBe('Refund Agent');
    });

    it('getAgent returns undefined for non-existent id', () => {
      expect(useAgentsStore.getState().getAgent('nonexistent')).toBeUndefined();
    });
  });

  describe('getActiveAgentCount', () => {
    it('counts active and idle agents', () => {
      useAgentsStore.setState({
        agents: [
          { id: '1', name: 'Active', type: 'faq', status: 'active', variant: 'light', model: 'm', domain: 'g', createdAt: '', lastActiveAt: null, metrics: { ticketsHandled: 0, avgResponseTime: 0, satisfactionScore: 0, resolutionRate: 0, totalCost: 0, totalSavings: 0 }, isAvailable: true },
          { id: '2', name: 'Idle', type: 'faq', status: 'idle', variant: 'light', model: 'm', domain: 'g', createdAt: '', lastActiveAt: null, metrics: { ticketsHandled: 0, avgResponseTime: 0, satisfactionScore: 0, resolutionRate: 0, totalCost: 0, totalSavings: 0 }, isAvailable: true },
          { id: '3', name: 'Error', type: 'faq', status: 'error', variant: 'light', model: 'm', domain: 'g', createdAt: '', lastActiveAt: null, metrics: { ticketsHandled: 0, avgResponseTime: 0, satisfactionScore: 0, resolutionRate: 0, totalCost: 0, totalSavings: 0 }, isAvailable: false },
          { id: '4', name: 'Init', type: 'faq', status: 'initializing', variant: 'light', model: 'm', domain: 'g', createdAt: '', lastActiveAt: null, metrics: { ticketsHandled: 0, avgResponseTime: 0, satisfactionScore: 0, resolutionRate: 0, totalCost: 0, totalSavings: 0 }, isAvailable: false },
        ],
      });

      expect(useAgentsStore.getState().getActiveAgentCount()).toBe(2); // active + idle
    });

    it('returns 0 for empty agents list', () => {
      expect(useAgentsStore.getState().getActiveAgentCount()).toBe(0);
    });
  });

  describe('getTotalMetrics', () => {
    it('aggregates metrics across all agents', () => {
      useAgentsStore.setState({
        agents: [
          { id: '1', name: 'A1', type: 'faq', status: 'active', variant: 'light', model: 'm', domain: 'g', createdAt: '', lastActiveAt: null, metrics: { ticketsHandled: 100, avgResponseTime: 2, satisfactionScore: 95, resolutionRate: 88, totalCost: 0.2, totalSavings: 1249.8 }, isAvailable: true },
          { id: '2', name: 'A2', type: 'refund', status: 'active', variant: 'medium', model: 'm', domain: 'g', createdAt: '', lastActiveAt: null, metrics: { ticketsHandled: 50, avgResponseTime: 5, satisfactionScore: 90, resolutionRate: 85, totalCost: 0.75, totalSavings: 624.25 }, isAvailable: true },
        ],
      });

      const total = useAgentsStore.getState().getTotalMetrics();
      expect(total.ticketsHandled).toBe(150);
      expect(total.avgResponseTime).toBe(7);  // sum (not average)
      expect(total.satisfactionScore).toBe(185); // sum
      expect(total.totalCost).toBeCloseTo(0.95, 2);
      expect(total.totalSavings).toBeCloseTo(1874.05, 2);
    });

    it('returns zeros for empty agents list', () => {
      const total = useAgentsStore.getState().getTotalMetrics();
      expect(total.ticketsHandled).toBe(0);
      expect(total.totalCost).toBe(0);
    });
  });

  describe('Agent display helpers', () => {
    it('has labels for all 10 agent types', () => {
      expect(Object.keys(AGENT_TYPE_LABELS)).toHaveLength(10);
    });

    it('has labels for all 4 statuses', () => {
      expect(Object.keys(AGENT_STATUS_LABELS)).toHaveLength(4);
    });

    it('has human-readable labels', () => {
      expect(AGENT_TYPE_LABELS.faq).toBe('FAQ Agent');
      expect(AGENT_TYPE_LABELS.fraud).toBe('Fraud Detection');
      expect(AGENT_STATUS_LABELS.active).toBe('Active');
    });
  });
});
