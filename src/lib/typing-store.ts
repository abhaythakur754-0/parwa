/**
 * PARWA Typing Indicator Store + Component
 *
 * Tracks who is currently typing on a ticket or conversation.
 * Auto-expires after a timeout (5s) if no further typing events.
 *
 * Socket.io events:
 *   typing:start  — { ticket_id, user_id, user_name }
 *   typing:stop   — { ticket_id, user_id }
 */

import { create } from 'zustand';

// ── Types ────────────────────────────────────────────────────────────

interface TypingUser {
  userId: string;
  userName: string;
  startedAt: number; // timestamp
}

interface TypingState {
  // ticket_id -> list of typing users
  typingUsers: Map<string, TypingUser[]>;

  // Actions
  startTyping: (ticketId: string, userId: string, userName: string) => void;
  stopTyping: (ticketId: string, userId: string) => void;
  clearTyping: (ticketId: string) => void;
  getTypingUsers: (ticketId: string) => TypingUser[];
  isSomeoneTyping: (ticketId: string) => boolean;
}

// ── Auto-expire timeout ──────────────────────────────────────────────

const TYPING_TIMEOUT = 5000; // 5 seconds
const expiryTimers = new Map<string, Map<string, ReturnType<typeof setTimeout>>>();

// ── Store ────────────────────────────────────────────────────────────

export const useTypingStore = create<TypingState>((set, get) => ({
  typingUsers: new Map(),

  startTyping: (ticketId, userId, userName) => {
    set((state) => {
      const newMap = new Map(state.typingUsers);
      const existing = newMap.get(ticketId) || [];

      // Don't duplicate
      if (existing.some(u => u.userId === userId)) {
        // Reset timeout for this user
        newMap.set(ticketId, existing.map(u =>
          u.userId === userId ? { ...u, startedAt: Date.now() } : u
        ));
      } else {
        newMap.set(ticketId, [...existing, { userId, userName, startedAt: Date.now() }]);
      }

      return { typingUsers: newMap };
    });

    // Auto-expire after timeout
    if (!expiryTimers.has(ticketId)) expiryTimers.set(ticketId, new Map());
    const ticketTimers = expiryTimers.get(ticketId)!;
    if (ticketTimers.has(userId)) clearTimeout(ticketTimers.get(userId)!);
    ticketTimers.set(userId, setTimeout(() => {
      get().stopTyping(ticketId, userId);
      ticketTimers.delete(userId);
    }, TYPING_TIMEOUT));
  },

  stopTyping: (ticketId, userId) => {
    set((state) => {
      const newMap = new Map(state.typingUsers);
      const existing = newMap.get(ticketId) || [];
      const filtered = existing.filter(u => u.userId !== userId);
      if (filtered.length === 0) {
        newMap.delete(ticketId);
      } else {
        newMap.set(ticketId, filtered);
      }
      return { typingUsers: newMap };
    });

    // Clear timer
    const ticketTimers = expiryTimers.get(ticketId);
    if (ticketTimers?.has(userId)) {
      clearTimeout(ticketTimers.get(userId)!);
      ticketTimers.delete(userId);
    }
  },

  clearTyping: (ticketId) => {
    set((state) => {
      const newMap = new Map(state.typingUsers);
      newMap.delete(ticketId);
      return { typingUsers: newMap };
    });

    // Clear all timers for this ticket
    const ticketTimers = expiryTimers.get(ticketId);
    if (ticketTimers) {
      for (const timer of ticketTimers.values()) clearTimeout(timer);
      ticketTimers.clear();
    }
  },

  getTypingUsers: (ticketId) => get().typingUsers.get(ticketId) || [],

  isSomeoneTyping: (ticketId) => (get().typingUsers.get(ticketId)?.length || 0) > 0,
}));
