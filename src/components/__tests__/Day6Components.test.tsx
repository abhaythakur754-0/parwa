/**
 * PARWA Day 6 Unit Tests — UI Components (Typing, Collision, Presence)
 *
 * Tests TypingIndicator, CollisionBanner, AgentPresenceBadge
 * WITHOUT the polling hook (that's in its own test file).
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useTypingStore } from '@/lib/typing-store';
import { useCollisionStore } from '@/lib/collision-store';
import { usePresenceStore } from '@/lib/presence-store';

// ── Mocks ────────────────────────────────────────────────────────────

jest.mock('next/navigation', () => ({
  useRouter() {
    return { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn(), pathname: '/', query: {}, asPath: '/' };
  },
  useSearchParams() { return new URLSearchParams(); },
  usePathname() { return '/'; },
}));

jest.mock('lucide-react', () => {
  return new Proxy({}, {
    get: function(_target: Record<string, unknown>, prop: string) {
      return (props: Record<string, unknown>) =>
        React.createElement('svg', { 'data-testid': `icon-${prop.toLowerCase()}`, ...props });
    },
  });
});

// ── TypingIndicator Tests ────────────────────────────────────────────

describe('TypingIndicator', () => {
  beforeEach(() => {
    useTypingStore.getState().typingUsers.forEach((_, key) => {
      useTypingStore.getState().clearTyping(key);
    });
  });

  it('renders nothing when no one is typing', () => {
    const { TypingIndicator } = require('@/components/TypingIndicator');
    render(React.createElement(TypingIndicator, { ticketId: 'TKT-001' }));
    expect(screen.queryByTestId('typing-indicator')).not.toBeInTheDocument();
  });

  it('renders when someone is typing', () => {
    useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
    const { TypingIndicator } = require('@/components/TypingIndicator');
    render(React.createElement(TypingIndicator, { ticketId: 'TKT-001' }));
    expect(screen.getByTestId('typing-indicator')).toBeInTheDocument();
    expect(screen.getByText(/Alice is typing/)).toBeInTheDocument();
  });

  it('shows multiple users', () => {
    useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
    useTypingStore.getState().startTyping('TKT-001', 'user-2', 'Bob');
    const { TypingIndicator } = require('@/components/TypingIndicator');
    render(React.createElement(TypingIndicator, { ticketId: 'TKT-001' }));
    expect(screen.getByText(/Alice and Bob are typing/)).toBeInTheDocument();
  });

  it('shows "X and N others" for 3+ users', () => {
    useTypingStore.getState().startTyping('TKT-001', 'u1', 'A');
    useTypingStore.getState().startTyping('TKT-001', 'u2', 'B');
    useTypingStore.getState().startTyping('TKT-001', 'u3', 'C');
    const { TypingIndicator } = require('@/components/TypingIndicator');
    render(React.createElement(TypingIndicator, { ticketId: 'TKT-001' }));
    expect(screen.getByText(/A and 2 others are typing/)).toBeInTheDocument();
  });

  it('has aria-live for accessibility', () => {
    useTypingStore.getState().startTyping('TKT-001', 'user-1', 'Alice');
    const { TypingIndicator } = require('@/components/TypingIndicator');
    render(React.createElement(TypingIndicator, { ticketId: 'TKT-001' }));
    expect(screen.getByTestId('typing-indicator')).toHaveAttribute('aria-live', 'polite');
  });
});

// ── CollisionBanner Tests ────────────────────────────────────────────

describe('CollisionBanner', () => {
  beforeEach(() => {
    useCollisionStore.getState().clearAll();
  });

  it('renders nothing when no collisions', () => {
    const { CollisionBanner } = require('@/components/CollisionBanner');
    render(React.createElement(CollisionBanner, { ticketId: 'TKT-001' }));
    expect(screen.queryByTestId('collision-banner')).not.toBeInTheDocument();
  });

  it('renders when another user is viewing', () => {
    useCollisionStore.getState().userEntered('TKT-001', 'other-user', 'Bob', 'viewing');
    const { CollisionBanner } = require('@/components/CollisionBanner');
    render(React.createElement(CollisionBanner, { ticketId: 'TKT-001', currentUserId: 'me' }));
    expect(screen.getByTestId('collision-banner')).toBeInTheDocument();
    expect(screen.getByText(/Bob/)).toBeInTheDocument();
    expect(screen.getByTestId('collision-viewing-icon')).toBeInTheDocument();
  });

  it('renders warning when someone is editing', () => {
    useCollisionStore.getState().userEntered('TKT-001', 'other-user', 'Bob', 'editing');
    const { CollisionBanner } = require('@/components/CollisionBanner');
    render(React.createElement(CollisionBanner, { ticketId: 'TKT-001', currentUserId: 'me' }));
    expect(screen.getByTestId('collision-warning-icon')).toBeInTheDocument();
    expect(screen.getByText(/editing/)).toBeInTheDocument();
  });

  it('hides current user from collision list', () => {
    useCollisionStore.getState().userEntered('TKT-001', 'me', 'Me', 'viewing');
    const { CollisionBanner } = require('@/components/CollisionBanner');
    render(React.createElement(CollisionBanner, { ticketId: 'TKT-001', currentUserId: 'me' }));
    expect(screen.queryByTestId('collision-banner')).not.toBeInTheDocument();
  });

  it('shows "N others" for multiple users', () => {
    useCollisionStore.getState().userEntered('TKT-001', 'u1', 'Alice', 'viewing');
    useCollisionStore.getState().userEntered('TKT-001', 'u2', 'Bob', 'viewing');
    useCollisionStore.getState().userEntered('TKT-001', 'u3', 'Carol', 'viewing');
    const { CollisionBanner } = require('@/components/CollisionBanner');
    render(React.createElement(CollisionBanner, { ticketId: 'TKT-001', currentUserId: 'me' }));
    expect(screen.getByText(/Alice and 2 others/)).toBeInTheDocument();
  });
});

// ── AgentPresenceBadge Tests ─────────────────────────────────────────

describe('AgentPresenceBadge', () => {
  beforeEach(() => {
    usePresenceStore.getState().clearAll();
  });

  it('renders offline status for unknown agent', () => {
    const { AgentPresenceBadge } = require('@/components/AgentPresenceBadge');
    render(React.createElement(AgentPresenceBadge, { agentId: 'unknown' }));
    expect(screen.getByTestId('presence-unknown')).toBeInTheDocument();
  });

  it('renders agent name when showName is true', () => {
    usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'Alice', status: 'available' });
    const { AgentPresenceBadge } = require('@/components/AgentPresenceBadge');
    render(React.createElement(AgentPresenceBadge, { agentId: 'a1' }));
    expect(screen.getByText('Alice')).toBeInTheDocument();
  });

  it('hides name when showName is false', () => {
    usePresenceStore.getState().setOnline({ agent_id: 'a1', name: 'Alice', status: 'available' });
    const { AgentPresenceBadge } = require('@/components/AgentPresenceBadge');
    render(React.createElement(AgentPresenceBadge, { agentId: 'a1', showName: false }));
    expect(screen.queryByText('Alice')).not.toBeInTheDocument();
  });
});
