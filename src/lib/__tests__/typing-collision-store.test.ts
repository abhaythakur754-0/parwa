/**
 * PARWA Day 6 Unit Tests — Typing Store & Collision Store
 *
 * Tests typing indicators with auto-expiry, and collision
 * detection with viewing/editing states.
 */

import { useTypingStore } from '@/lib/typing-store';
import { useCollisionStore } from '@/lib/collision-store';

// ── Typing Store Tests ───────────────────────────────────────────────

describe('Typing Store', () => {
  beforeEach(() => {
    useTypingStore.getState().typingUsers.forEach((_, key) => {
      useTypingStore.getState().clearTyping(key);
    });
  });

  describe('initial state', () => {
    it('starts with empty typing users', () => {
      expect(useTypingStore.getState().typingUsers.size).toBe(0);
    });

    it('returns empty array for unknown ticket', () => {
      expect(useTypingStore.getState().getTypingUsers('TKT-999')).toEqual([]);
    });

    it('isSomeoneTyping returns false for unknown ticket', () => {
      expect(useTypingStore.getState().isSomeoneTyping('TKT-999')).toBe(false);
    });
  });

  describe('startTyping', () => {
    it('adds a typing user', () => {
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      const users = useTypingStore.getState().getTypingUsers('TKT-001');
      expect(users).toHaveLength(1);
      expect(users[0].userName).toBe('Alice');
    });

    it('tracks multiple users on same ticket', () => {
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      useTypingStore.getState().startTyping('TKT-001', 'user-2', 'Bob');
      expect(useTypingStore.getState().getTypingUsers('TKT-001')).toHaveLength(2);
    });

    it('tracks typing across different tickets', () => {
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      useTypingStore.getState().startTyping('TKT-002', 'user-2', 'Bob');
      expect(useTypingStore.getState().isSomeoneTyping('TKT-001')).toBe(true);
      expect(useTypingStore.getState().isSomeoneTyping('TKT-002')).toBe(true);
    });

    it('does not duplicate same user on same ticket', () => {
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      expect(useTypingStore.getState().getTypingUsers('TKT-001')).toHaveLength(1);
    });

    it('isSomeoneTyping returns true when someone is typing', () => {
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      expect(useTypingStore.getState().isSomeoneTyping('TKT-001')).toBe(true);
    });
  });

  describe('stopTyping', () => {
    it('removes a typing user', () => {
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      useTypingStore.getState().stopTyping('TKT-001', 'user-1');
      expect(useTypingStore.getState().getTypingUsers('TKT-001')).toHaveLength(0);
    });

    it('only removes specified user', () => {
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      useTypingStore.getState().startTyping('TKT-001', 'user-2', 'Bob');
      useTypingStore.getState().stopTyping('TKT-001', 'user-1');
      const users = useTypingStore.getState().getTypingUsers('TKT-001');
      expect(users).toHaveLength(1);
      expect(users[0].userName).toBe('Bob');
    });

    it('cleans up ticket entry when all users stop', () => {
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      useTypingStore.getState().stopTyping('TKT-001', 'user-1');
      expect(useTypingStore.getState().typingUsers.has('TKT-001')).toBe(false);
    });
  });

  describe('clearTyping', () => {
    it('removes all typing users for a ticket', () => {
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      useTypingStore.getState().startTyping('TKT-001', 'user-2', 'Bob');
      useTypingStore.getState().clearTyping('TKT-001');
      expect(useTypingStore.getState().getTypingUsers('TKT-001')).toHaveLength(0);
    });

    it('does not affect other tickets', () => {
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      useTypingStore.getState().startTyping('TKT-002', 'user-2', 'Bob');
      useTypingStore.getState().clearTyping('TKT-001');
      expect(useTypingStore.getState().isSomeoneTyping('TKT-002')).toBe(true);
    });
  });

  describe('auto-expiry', () => {
    it('auto-expires typing after timeout', async () => {
      jest.useFakeTimers();
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
      expect(useTypingStore.getState().isSomeoneTyping('TKT-001')).toBe(true);

      jest.advanceTimersByTime(5500); // 5.5s — past the 5s timeout

      expect(useTypingStore.getState().isSomeoneTyping('TKT-001')).toBe(false);
      jest.useRealTimers();
    });

    it('resets timeout when user continues typing', async () => {
      jest.useFakeTimers();
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');

      jest.advanceTimersByTime(3000); // 3s
      useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice'); // reset

      jest.advanceTimersByTime(3000); // 3s more = 6s total but reset at 3s
      expect(useTypingStore.getState().isSomeoneTyping('TKT-001')).toBe(true);

      jest.advanceTimersByTime(3000); // 9s total — past the reset timeout
      expect(useTypingStore.getState().isSomeoneTyping('TKT-001')).toBe(false);
      jest.useRealTimers();
    });
  });
});

// ── Collision Store Tests ────────────────────────────────────────────

describe('Collision Store', () => {
  beforeEach(() => {
    useCollisionStore.getState().clearAll();
  });

  describe('initial state', () => {
    it('starts with empty collisions', () => {
      expect(useCollisionStore.getState().collisions.size).toBe(0);
    });

    it('returns empty array for unknown ticket', () => {
      expect(useCollisionStore.getState().getCollisions('TKT-999')).toEqual([]);
    });

    it('hasCollision returns false for unknown ticket', () => {
      expect(useCollisionStore.getState().hasCollision('TKT-999')).toBe(false);
    });
  });

  describe('userEntered', () => {
    it('adds a viewing user', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice');
      const collisions = useCollisionStore.getState().getCollisions('TKT-001');
      expect(collisions).toHaveLength(1);
      expect(collisions[0].action).toBe('viewing');
    });

    it('adds an editing user', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice', 'editing');
      const collisions = useCollisionStore.getState().getCollisions('TKT-001');
      expect(collisions[0].action).toBe('editing');
    });

    it('tracks multiple users', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice');
      useCollisionStore.getState().userEntered('TKT-001', 'user-2', 'Bob', 'editing');
      expect(useCollisionStore.getState().getCollisions('TKT-001')).toHaveLength(2);
    });

    it('updates existing user action', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice', 'viewing');
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice', 'editing');
      const collisions = useCollisionStore.getState().getCollisions('TKT-001');
      expect(collisions).toHaveLength(1);
      expect(collisions[0].action).toBe('editing');
    });

    it('hasCollision returns true', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice');
      expect(useCollisionStore.getState().hasCollision('TKT-001')).toBe(true);
    });
  });

  describe('userLeft', () => {
    it('removes a user', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice');
      useCollisionStore.getState().userLeft('TKT-001', 'user-1');
      expect(useCollisionStore.getState().getCollisions('TKT-001')).toHaveLength(0);
    });

    it('only removes the specified user', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice');
      useCollisionStore.getState().userEntered('TKT-001', 'user-2', 'Bob');
      useCollisionStore.getState().userLeft('TKT-001', 'user-1');
      expect(useCollisionStore.getState().getCollisions('TKT-001')).toHaveLength(1);
    });

    it('cleans up ticket entry when all users leave', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice');
      useCollisionStore.getState().userLeft('TKT-001', 'user-1');
      expect(useCollisionStore.getState().collisions.has('TKT-001')).toBe(false);
    });
  });

  describe('fieldUpdate', () => {
    it('updates field and sets action to editing', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice', 'viewing');
      useCollisionStore.getState().fieldUpdate('TKT-001', 'user-1', 'priority');

      const collisions = useCollisionStore.getState().getCollisions('TKT-001');
      expect(collisions[0].action).toBe('editing');
      expect(collisions[0].activeField).toBe('priority');
    });

    it('does not affect other users', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice');
      useCollisionStore.getState().userEntered('TKT-001', 'user-2', 'Bob');
      useCollisionStore.getState().fieldUpdate('TKT-001', 'user-1', 'status');

      const collisions = useCollisionStore.getState().getCollisions('TKT-001');
      expect(collisions[0].activeField).toBe('status');
      expect(collisions[1].activeField).toBeUndefined();
    });
  });

  describe('hasEditor / getEditors', () => {
    it('hasEditor returns false when only viewers', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice', 'viewing');
      expect(useCollisionStore.getState().hasEditor('TKT-001')).toBe(false);
    });

    it('hasEditor returns true when someone is editing', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice', 'editing');
      expect(useCollisionStore.getState().hasEditor('TKT-001')).toBe(true);
    });

    it('getEditors returns only editors', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice', 'viewing');
      useCollisionStore.getState().userEntered('TKT-001', 'user-2', 'Bob', 'editing');
      useCollisionStore.getState().userEntered('TKT-001', 'user-3', 'Carol', 'editing');

      const editors = useCollisionStore.getState().getEditors('TKT-001');
      expect(editors).toHaveLength(2);
    });
  });

  describe('isUserEditing', () => {
    it('returns true when user is editing', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice', 'editing');
      expect(useCollisionStore.getState().isUserEditing('TKT-001', 'user-1')).toBe(true);
    });

    it('returns false when user is viewing', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice', 'viewing');
      expect(useCollisionStore.getState().isUserEditing('TKT-001', 'user-1')).toBe(false);
    });

    it('returns false for unknown user', () => {
      expect(useCollisionStore.getState().isUserEditing('TKT-001', 'unknown')).toBe(false);
    });
  });

  describe('clearAll', () => {
    it('resets everything', () => {
      useCollisionStore.getState().userEntered('TKT-001', 'user-1', 'Alice', 'editing');
      useCollisionStore.getState().userEntered('TKT-002', 'user-2', 'Bob');
      useCollisionStore.getState().clearAll();
      expect(useCollisionStore.getState().collisions.size).toBe(0);
    });
  });
});
