/**
 * PARWA Collision Detection Store
 *
 * Detects when multiple users are viewing/editing the same ticket
 * simultaneously. Shows a warning banner and prevents conflicting saves.
 *
 * Socket.io events:
 *   collision:enter   — { ticket_id, user_id, user_name, action: 'viewing'|'editing' }
 *   collision:leave   — { ticket_id, user_id }
 *   collision:update  — { ticket_id, user_id, field, old_value, new_value }
 */

import { create } from 'zustand';

// ── Types ────────────────────────────────────────────────────────────

export type CollisionAction = 'viewing' | 'editing';

export interface CollisionUser {
  userId: string;
  userName: string;
  action: CollisionAction;
  enteredAt: string;
  lastHeartbeat: number; // timestamp ms
  activeField?: string;
}

interface CollisionState {
  // ticket_id -> users on that ticket
  collisions: Map<string, CollisionUser[]>;

  // Actions
  userEntered: (ticketId: string, userId: string, userName: string, action?: CollisionAction) => void;
  userLeft: (ticketId: string, userId: string) => void;
  heartbeat: (ticketId: string, userId: string) => void;
  fieldUpdate: (ticketId: string, userId: string, field: string) => void;
  updateField: (ticketId: string, userId: string, field: string, value: unknown) => void;
  clearTicket: (ticketId: string) => void;
  getCollisions: (ticketId: string) => CollisionUser[];
  hasCollision: (ticketId: string) => boolean;
  hasEditor: (ticketId: string) => boolean;
  getEditors: (ticketId: string) => CollisionUser[];
  isUserEditing: (ticketId: string, userId: string) => boolean;
  clearAll: () => void;
}

// ── Store ────────────────────────────────────────────────────────────

export const useCollisionStore = create<CollisionState>((set, get) => ({
  collisions: new Map(),

  userEntered: (ticketId, userId, userName, action = 'viewing') => {
    set((state) => {
      const newMap = new Map(state.collisions);
      const existing = newMap.get(ticketId) || [];

      // Don't duplicate
      if (existing.some(u => u.userId === userId)) {
        newMap.set(ticketId, existing.map(u =>
          u.userId === userId ? { ...u, action, enteredAt: new Date().toISOString(), lastHeartbeat: Date.now() } : u
        ));
      } else {
        newMap.set(ticketId, [...existing, {
          userId,
          userName,
          action,
          enteredAt: new Date().toISOString(),
          lastHeartbeat: Date.now(),
        }]);
      }

      return { collisions: newMap };
    });
  },

  userLeft: (ticketId, userId) => {
    set((state) => {
      const newMap = new Map(state.collisions);
      const existing = newMap.get(ticketId) || [];
      const filtered = existing.filter(u => u.userId !== userId);
      if (filtered.length === 0) {
        newMap.delete(ticketId);
      } else {
        newMap.set(ticketId, filtered);
      }
      return { collisions: newMap };
    });
  },

  /** Update heartbeat for a user on a ticket — prevents auto-expiry. */
  heartbeat: (ticketId, userId) => {
    set((state) => {
      const newMap = new Map(state.collisions);
      const existing = newMap.get(ticketId);
      if (!existing) return state;

      const hasUser = existing.some(u => u.userId === userId);
      if (!hasUser) return state;

      newMap.set(ticketId, existing.map(u =>
        u.userId === userId ? { ...u, lastHeartbeat: Date.now() } : u
      ));
      return { collisions: newMap };
    });
  },

  fieldUpdate: (ticketId, userId, field) => {
    set((state) => {
      const newMap = new Map(state.collisions);
      const existing = newMap.get(ticketId) || [];
      newMap.set(ticketId, existing.map(u =>
        u.userId === userId ? { ...u, activeField: field, action: 'editing' as CollisionAction } : u
      ));
      return { collisions: newMap };
    });
  },

  updateField: (ticketId, userId, field, _value) => {
    // Alias used by useRealtimeEvents — delegates to fieldUpdate.
    // The `value` param is reserved for future optimistic field sync.
    get().fieldUpdate(ticketId, userId, field);
  },

  clearTicket: (ticketId) => {
    set((state) => {
      const newMap = new Map(state.collisions);
      newMap.delete(ticketId);
      return { collisions: newMap };
    });
  },

  getCollisions: (ticketId) => {
    const now = Date.now();
    const STALE_THRESHOLD_MS = 45_000; // 45 seconds
    const users = get().collisions.get(ticketId) || [];
    // Filter out stale users (no heartbeat for >45s)
    const active = users.filter(u => (now - u.lastHeartbeat) < STALE_THRESHOLD_MS);
    return active;
  },

  hasCollision: (ticketId) => {
    const users = get().getCollisions(ticketId);
    return users.length > 1; // collision = 2+ users on same ticket
  },

  hasEditor: (ticketId) => get().getCollisions(ticketId).some(u => u.action === 'editing'),

  getEditors: (ticketId) => get().getCollisions(ticketId).filter(u => u.action === 'editing'),

  isUserEditing: (ticketId, userId) => {
    const user = get().getCollisions(ticketId).find(u => u.userId === userId);
    return user?.action === 'editing';
  },

  clearAll: () => set({ collisions: new Map() }),
}));
