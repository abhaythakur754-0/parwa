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
  activeField?: string;
}

interface CollisionState {
  // ticket_id -> users on that ticket
  collisions: Map<string, CollisionUser[]>;

  // Actions
  userEntered: (ticketId: string, userId: string, userName: string, action?: CollisionAction) => void;
  userLeft: (ticketId: string, userId: string) => void;
  fieldUpdate: (ticketId: string, userId: string, field: string) => void;
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
          u.userId === userId ? { ...u, action, enteredAt: new Date().toISOString() } : u
        ));
      } else {
        newMap.set(ticketId, [...existing, {
          userId,
          userName,
          action,
          enteredAt: new Date().toISOString(),
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

  clearTicket: (ticketId) => {
    set((state) => {
      const newMap = new Map(state.collisions);
      newMap.delete(ticketId);
      return { collisions: newMap };
    });
  },

  getCollisions: (ticketId) => get().collisions.get(ticketId) || [],

  hasCollision: (ticketId) => (get().collisions.get(ticketId)?.length || 0) > 0,

  hasEditor: (ticketId) => (get().collisions.get(ticketId) || []).some(u => u.action === 'editing'),

  getEditors: (ticketId) => (get().collisions.get(ticketId) || []).filter(u => u.action === 'editing'),

  isUserEditing: (ticketId, userId) => {
    const user = (get().collisions.get(ticketId) || []).find(u => u.userId === userId);
    return user?.action === 'editing';
  },

  clearAll: () => set({ collisions: new Map() }),
}));
