/**
 * PARWA Day 6 Unit Tests — Presence Store
 *
 * Tests agent online/offline tracking, status updates,
 * bulk loading, and helper methods.
 */

import { usePresenceStore } from '@/lib/presence-store';

const mockFetch = jest.fn();
global.fetch = mockFetch;

function resetStore() {
  usePresenceStore.getState().clearAll();
}

describe('Presence Store', () => {
  beforeEach(() => {
    resetStore();
    mockFetch.mockReset();
  });

  // ── Initial State ──────────────────────────────────────────────────

  describe('initial state', () => {
    it('starts with empty agents map', () => {
      expect(usePresenceStore.getState().agents.size).toBe(0);
    });

    it('starts with onlineCount of 0', () => {
      expect(usePresenceStore.getState().onlineCount).toBe(0);
    });
  });

  // ── setOnline ──────────────────────────────────────────────────────

  describe('setOnline', () => {
    it('adds an online agent', () => {
      usePresenceStore.getState().setOnline({
        agent_id: 'agent-1',
        name: 'Alice',
        status: 'available',
      });

      const agent = usePresenceStore.getState().getAgent('agent-1');
      expect(agent).toBeDefined();
      expect(agent?.name).toBe('Alice');
      expect(agent?.status).toBe('available');
    });

    it('defaults to available status', () => {
      usePresenceStore.getState().setOnline({
        agent_id: 'agent-2',
        name: 'Bob',
      });

      expect(usePresenceStore.getState().getAgent('agent-2')?.status).toBe('available');
    });

    it('increments onlineCount', () => {
      usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'A' });
      usePresenceStore.getState().setOnline({ agent_id: 'a2', name: 'B' });

      expect(usePresenceStore.getState().onlineCount).toBe(2);
    });

    it('updates existing agent', () => {
      usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'Alice', status: 'available' });
      usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'Alice B', status: 'busy' });

      const agent = usePresenceStore.getState().getAgent('a1');
      expect(agent?.name).toBe('Alice B');
      expect(agent?.status).toBe('busy');
      expect(usePresenceStore.getState().onlineCount).toBe(1);
    });

    it('stores avatar and currentTicketId', () => {
      usePresenceStore.getState().setOnline({
        agent_id: 'a1',
        name: 'Carol',
        avatar: 'https://img.test/carol.jpg',
        current_ticket_id: 'TKT-001',
      });

      const agent = usePresenceStore.getState().getAgent('a1');
      expect(agent?.avatar).toBe('https://img.test/carol.jpg');
      expect(agent?.currentTicketId).toBe('TKT-001');
    });
  });

  // ── setOffline ─────────────────────────────────────────────────────

  describe('setOffline', () => {
    it('marks an agent as offline', () => {
      usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'Alice' });
      usePresenceStore.getState().setOffline('a1');

      expect(usePresenceStore.getState().getAgent('a1')?.status).toBe('offline');
      expect(usePresenceStore.getState().onlineCount).toBe(0);
    });

    it('handles offline for unknown agent gracefully', () => {
      usePresenceStore.getState().setOffline('unknown');
      expect(usePresenceStore.getState().agents.size).toBe(0);
    });

    it('decrements onlineCount', () => {
      usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'A' });
      usePresenceStore.getState().setOnline({ agent_id: 'a2', name: 'B' });
      usePresenceStore.getState().setOffline('a1');

      expect(usePresenceStore.getState().onlineCount).toBe(1);
    });
  });

  // ── updateStatus ───────────────────────────────────────────────────

  describe('updateStatus', () => {
    it('updates agent status', () => {
      usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'Alice', status: 'available' });
      usePresenceStore.getState().updateStatus('a1', 'busy');

      expect(usePresenceStore.getState().getAgent('a1')?.status).toBe('busy');
    });

    it('handles unknown agent gracefully', () => {
      usePresenceStore.getState().updateStatus('unknown', 'available');
      expect(usePresenceStore.getState().agents.size).toBe(0);
    });

    it('updates onlineCount when status changes to/from offline', () => {
      usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'A' });
      expect(usePresenceStore.getState().onlineCount).toBe(1);

      usePresenceStore.getState().updateStatus('a1', 'away');
      expect(usePresenceStore.getState().onlineCount).toBe(1);

      usePresenceStore.getState().updateStatus('a1', 'offline');
      expect(usePresenceStore.getState().onlineCount).toBe(0);
    });
  });

  // ── setBulk ────────────────────────────────────────────────────────

  describe('setBulk', () => {
    it('loads multiple agents at once', () => {
      usePresenceStore.getState().setBulk([
        { agent_id: 'a1', name: 'Alice', status: 'available' },
        { agent_id: 'a2', name: 'Bob', status: 'busy' },
        { agent_id: 'a3', name: 'Carol', status: 'offline' },
      ]);

      expect(usePresenceStore.getState().agents.size).toBe(3);
      expect(usePresenceStore.getState().onlineCount).toBe(2);
    });

    it('replaces existing data', () => {
      usePresenceStore.getState().setOnline({ agent_id: 'old', name: 'Old' });
      usePresenceStore.getState().setBulk([
        { agent_id: 'new1', name: 'New1', status: 'available' },
      ]);

      expect(usePresenceStore.getState().agents.size).toBe(1);
      expect(usePresenceStore.getState().getAgent('old')).toBeUndefined();
    });
  });

  // ── fetchPresence ──────────────────────────────────────────────────

  describe('fetchPresence', () => {
    it('loads presence from API', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ([
          { agent_id: 'a1', name: 'Alice', status: 'available' },
          { agent_id: 'a2', name: 'Bob', status: 'busy' },
        ]),
      });

      await usePresenceStore.getState().fetchPresence();

      expect(usePresenceStore.getState().agents.size).toBe(2);
      expect(usePresenceStore.getState().onlineCount).toBe(2);
    });

    it('handles agents in nested response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ agents: [
          { agent_id: 'a1', name: 'Alice', status: 'available' },
        ]}),
      });

      await usePresenceStore.getState().fetchPresence();
      expect(usePresenceStore.getState().agents.size).toBe(1);
    });

    it('ignores 404 errors gracefully', async () => {
      mockFetch.mockResolvedValueOnce({ ok: false, status: 404 });
      await usePresenceStore.getState().fetchPresence();
      // No crash, no data change
    });

    it('handles network errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
      await usePresenceStore.getState().fetchPresence();
      // No crash
    });
  });

  // ── Helper Methods ────────────────────────────────────────────────

  describe('helper methods', () => {
    it('isOnline returns true for available/busy/away agents', () => {
      usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'A', status: 'available' });
      usePresenceStore.getState().setOnline({ agent_id: 'a2', name: 'B', status: 'busy' });
      usePresenceStore.getState().setOnline({ agent_id: 'a3', name: 'C', status: 'away' });

      expect(usePresenceStore.getState().isOnline('a1')).toBe(true);
      expect(usePresenceStore.getState().isOnline('a2')).toBe(true);
      expect(usePresenceStore.getState().isOnline('a3')).toBe(true);
    });

    it('isOnline returns false for offline/unknown agents', () => {
      usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'A' });
      usePresenceStore.getState().setOffline('a1');

      expect(usePresenceStore.getState().isOnline('a1')).toBe(false);
      expect(usePresenceStore.getState().isOnline('unknown')).toBe(false);
    });

    it('getOnlineAgents returns only non-offline agents', () => {
      usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'A', status: 'available' });
      usePresenceStore.getState().setOnline({ agent_id: 'a2', name: 'B', status: 'busy' });
      usePresenceStore.getState().setOnline({ agent_id: 'a3', name: 'C', status: 'offline' });

      const online = usePresenceStore.getState().getOnlineAgents();
      expect(online).toHaveLength(2);
    });

    it('clearAll resets everything', () => {
      usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'A' });
      usePresenceStore.getState().clearAll();

      expect(usePresenceStore.getState().agents.size).toBe(0);
      expect(usePresenceStore.getState().onlineCount).toBe(0);
    });
  });
});
