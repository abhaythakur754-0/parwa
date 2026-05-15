/**
 * PARWA Typing Indicator Store
 *
 * Tracks who is currently typing on a ticket or conversation.
 * Auto-expires after a timeout (5s) if no further typing events.
 * Emits Socket.io events so other users see the typing indicator.
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

  // Socket.io emit helpers (call these from UI components)
  emitTypingStart: (ticketId: string, userId: string, userName: string) => void;
  emitTypingStop: (ticketId: string, userId: string) => void;
}

// ── Auto-expire timeout ──────────────────────────────────────────────

const TYPING_TIMEOUT = 5000; // 5 seconds
const expiryTimers = new Map<string, Map<string, ReturnType<typeof setTimeout>>>();

// ── Lazy Socket.io import ────────────────────────────────────────────

function getSocketClient() {
  try {
    // Dynamic require to avoid circular deps at module level
    const { socketClient } = require('@/lib/socket-client');
    return socketClient;
  } catch {
    return null;
  }
}

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
      // Also emit stop to other users
      get().emitTypingStop(ticketId, userId);
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

  // ── Socket.io Emit Helpers ──────────────────────────────────────

  emitTypingStart: (ticketId, userId, userName) => {
    // Update local store
    get().startTyping(ticketId, userId, userName);

    // Emit to other users via Socket.io
    const socket = getSocketClient();
    if (socket?.isConnected()) {
      socket.emit('typing:start', { ticket_id: ticketId, user_id: userId, user_name: userName });
    }
  },

  emitTypingStop: (ticketId, userId) => {
    // Update local store
    get().stopTyping(ticketId, userId);

    // Emit to other users via Socket.io
    const socket = getSocketClient();
    if (socket?.isConnected()) {
      socket.emit('typing:stop', { ticket_id: ticketId, user_id: userId });
    }
  },
}));
