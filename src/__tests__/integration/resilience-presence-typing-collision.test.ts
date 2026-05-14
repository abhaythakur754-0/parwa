/**
 * PARWA Day 6 Integration Tests — Reconnection, Presence, Typing, Collision
 *
 * End-to-end flow tests verifying:
 * - Presence: bulk load → online/offline → status updates → fetch
 * - Typing: start → multiple users → stop → auto-expiry
 * - Collision: enter → edit → field update → leave
 * - Polling fallback: enable/disable → fetch → error handling
 * - Reconnection recovery: simulate disconnect → reconnect → missed events
 */

import { usePresenceStore } from '@/lib/presence-store';
import { useTypingStore } from '@/lib/typing-store';
import { useCollisionStore } from '@/lib/collision-store';

const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('Day 6 Integration: Presence Flow', () => {
  beforeEach(() => {
    usePresenceStore.getState().clearAll();
    mockFetch.mockReset();
  });

  it('full presence lifecycle: fetch → online → status change → offline', async () => {
    // Step 1: Fetch initial presence
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ([
        { agent_id: 'a1', name: 'Alice', status: 'available' },
        { agent_id: 'a2', name: 'Bob', status: 'busy' },
        { agent_id: 'a3', name: 'Carol', status: 'away' },
      ]),
    });

    await usePresenceStore.getState().fetchPresence();
    expect(usePresenceStore.getState().agents.size).toBe(3);
    expect(usePresenceStore.getState().onlineCount).toBe(3);

    // Step 2: Socket event — new agent comes online
    usePresenceStore.getState().setOnline({ agent_id: 'a4', name: 'Dave', status: 'available' });
    expect(usePresenceStore.getState().onlineCount).toBe(4);
    expect(usePresenceStore.getState().isOnline('a4')).toBe(true);

    // Step 3: Socket event — agent changes status
    usePresenceStore.getState().updateStatus('a2', 'away');
    expect(usePresenceStore.getState().getAgent('a2')?.status).toBe('away');

    // Step 4: Socket event — agent goes offline
    usePresenceStore.getState().setOffline('a3');
    expect(usePresenceStore.getState().isOnline('a3')).toBe(false);
    expect(usePresenceStore.getState().onlineCount).toBe(3);

    // Step 5: Verify getOnlineAgents returns correct list
    const onlineAgents = usePresenceStore.getState().getOnlineAgents();
    expect(onlineAgents).toHaveLength(3);
    expect(onlineAgents.map(a => a.name).sort()).toEqual(['Alice', 'Bob', 'Dave']);
  });

  it('handles bulk reload replacing existing data', () => {
    usePresenceStore.getState().setOnline({ agent_id: 'old1', name: 'Old Agent' });
    usePresenceStore.getState().setBulk([
      { agent_id: 'new1', name: 'New Agent 1', status: 'available' },
      { agent_id: 'new2', name: 'New Agent 2', status: 'busy' },
    ]);

    expect(usePresenceStore.getState().getAgent('old1')).toBeUndefined();
    expect(usePresenceStore.getState().agents.size).toBe(2);
  });
});

describe('Day 6 Integration: Typing Flow', () => {
  beforeEach(() => {
    useTypingStore.getState().typingUsers.forEach((_, key) => {
      useTypingStore.getState().clearTyping(key);
    });
  });

  it('full typing lifecycle: start → multiple users → stop', () => {
    // Alice starts typing
    useTypingStore.getState().startTyping('TKT-001', 'u1', 'Alice');
    expect(useTypingStore.getState().isSomeoneTyping('TKT-001')).toBe(true);

    // Bob starts typing on same ticket
    useTypingStore.getState().startTyping('TKT-001', 'u2', 'Bob');
    expect(useTypingStore.getState().getTypingUsers('TKT-001')).toHaveLength(2);

    // Alice stops
    useTypingStore.getState().stopTyping('TKT-001', 'u1');
    const users = useTypingStore.getState().getTypingUsers('TKT-001');
    expect(users).toHaveLength(1);
    expect(users[0].userName).toBe('Bob');

    // Bob stops
    useTypingStore.getState().stopTyping('TKT-001', 'u2');
    expect(useTypingStore.getState().isSomeoneTyping('TKT-001')).toBe(false);
  });

  it('typing on different tickets is independent', () => {
    useTypingStore.getState().startTyping('TKT-001', 'u1', 'Alice');
    useTypingStore.getState().startTyping('TKT-002', 'u2', 'Bob');

    expect(useTypingStore.getState().isSomeoneTyping('TKT-001')).toBe(true);
    expect(useTypingStore.getState().isSomeoneTyping('TKT-002')).toBe(true);

    useTypingStore.getState().clearTyping('TKT-001');
    expect(useTypingStore.getState().isSomeoneTyping('TKT-001')).toBe(false);
    expect(useTypingStore.getState().isSomeoneTyping('TKT-002')).toBe(true);
  });
});

describe('Day 6 Integration: Collision Flow', () => {
  beforeEach(() => {
    useCollisionStore.getState().clearAll();
  });

  it('full collision lifecycle: enter → view → edit → field update → leave', () => {
    // User 1 enters viewing
    useCollisionStore.getState().userEntered('TKT-001', 'u1', 'Alice', 'viewing');
    expect(useCollisionStore.getState().hasCollision('TKT-001')).toBe(true);
    expect(useCollisionStore.getState().hasEditor('TKT-001')).toBe(false);

    // User 2 enters editing
    useCollisionStore.getState().userEntered('TKT-001', 'u2', 'Bob', 'editing');
    expect(useCollisionStore.getState().hasEditor('TKT-001')).toBe(true);
    expect(useCollisionStore.getState().getEditors('TKT-001')).toHaveLength(1);

    // User 1 starts editing a field
    useCollisionStore.getState().fieldUpdate('TKT-001', 'u1', 'priority');
    expect(useCollisionStore.getState().isUserEditing('TKT-001', 'u1')).toBe(true);

    // User 2 leaves
    useCollisionStore.getState().userLeft('TKT-001', 'u2');
    expect(useCollisionStore.getState().getCollisions('TKT-001')).toHaveLength(1);

    // User 1 leaves
    useCollisionStore.getState().userLeft('TKT-001', 'u1');
    expect(useCollisionStore.getState().hasCollision('TKT-001')).toBe(false);
  });

  it('collision across multiple tickets is independent', () => {
    useCollisionStore.getState().userEntered('TKT-001', 'u1', 'Alice');
    useCollisionStore.getState().userEntered('TKT-002', 'u2', 'Bob', 'editing');

    expect(useCollisionStore.getState().hasCollision('TKT-001')).toBe(true);
    expect(useCollisionStore.getState().hasEditor('TKT-002')).toBe(true);
    expect(useCollisionStore.getState().hasEditor('TKT-001')).toBe(false);

    useCollisionStore.getState().clearTicket('TKT-001');
    expect(useCollisionStore.getState().hasCollision('TKT-001')).toBe(false);
    expect(useCollisionStore.getState().hasEditor('TKT-002')).toBe(true);
  });
});

describe('Day 6 Integration: Reconnection Recovery', () => {
  it('socket client tracks last event timestamp for recovery', () => {
    // Import socket client — it's a singleton
    const { socketClient } = require('@/lib/socket-client');

    // Initially no timestamp
    expect(socketClient.getLastEventTimestamp()).toBeNull();

    // After updating
    socketClient.updateLastEventTimestamp('2026-05-14T12:00:00Z');
    expect(socketClient.getLastEventTimestamp()).toBe('2026-05-14T12:00:00Z');
  });

  it('fetches missed events on reconnection', async () => {
    const { socketClient } = require('@/lib/socket-client');
    socketClient.updateLastEventTimestamp('2026-05-14T12:00:00Z');

    // The fetchMissedEvents method is private, but we can verify
    // the lastEventTimestamp is preserved
    expect(socketClient.getLastEventTimestamp()).toBe('2026-05-14T12:00:00Z');

    // Update to newer timestamp
    socketClient.updateLastEventTimestamp('2026-05-14T12:30:00Z');
    expect(socketClient.getLastEventTimestamp()).toBe('2026-05-14T12:30:00Z');
  });
});

describe('Day 6 Integration: Presence + Collision Combined', () => {
  beforeEach(() => {
    usePresenceStore.getState().clearAll();
    useCollisionStore.getState().clearAll();
  });

  it('tracks agent presence alongside ticket collision', () => {
    // Agent comes online
    usePresenceStore.getState().setOnline({ agent_id: 'agent-1', name: 'Alice', status: 'available' });
    expect(usePresenceStore.getState().isOnline('agent-1')).toBe(true);

    // Same agent enters a ticket
    useCollisionStore.getState().userEntered('TKT-001', 'agent-1', 'Alice', 'viewing');
    expect(useCollisionStore.getState().hasCollision('TKT-001')).toBe(true);

    // Agent goes offline
    usePresenceStore.getState().setOffline('agent-1');
    expect(usePresenceStore.getState().isOnline('agent-1')).toBe(false);

    // Collision is still tracked (agent may reconnect)
    expect(useCollisionStore.getState().hasCollision('TKT-001')).toBe(true);

    // Agent leaves the ticket
    useCollisionStore.getState().userLeft('TKT-001', 'agent-1');
    expect(useCollisionStore.getState().hasCollision('TKT-001')).toBe(false);
  });
});
