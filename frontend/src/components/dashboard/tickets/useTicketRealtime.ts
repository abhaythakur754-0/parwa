/**
 * PARWA Ticket Real-time Hook
 *
 * Custom hook for subscribing to real-time ticket updates via WebSocket.
 * Provides live ticket events, status changes, and new ticket notifications.
 *
 * Day 7 — Real-time Updates & Dashboard Integration
 */

'use client';

import { useEffect, useCallback, useRef, useState } from 'react';
import { useSocket } from '@/contexts/SocketContext';

// ── Types ─────────────────────────────────────────────────────────────────

export interface TicketEvent {
  event_id: string;
  event_type:
    | 'ticket:new'
    | 'ticket:status_changed'
    | 'ticket:assigned'
    | 'ticket:resolved'
    | 'ticket:escalated'
    | 'ticket:updated'
    | 'ticket:merged'
    | 'ticket:reopened'
    | 'message:new'
    | 'note:added';
  ticket_id: string;
  ticket_subject?: string;
  actor_id?: string;
  actor_name?: string;
  actor_type?: 'human' | 'ai' | 'system';
  old_value?: string;
  new_value?: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface TicketRealtimeState {
  /** Latest events received (last 50) */
  recentEvents: TicketEvent[];
  /** Count of new tickets since last acknowledgment */
  newTicketCount: number;
  /** Count of status changes since last acknowledgment */
  statusChangeCount: number;
  /** Count of new messages since last acknowledgment */
  newMessageCount: number;
  /** Count of escalations since last acknowledgment */
  escalationCount: number;
  /** Whether connected to WebSocket */
  isConnected: boolean;
  /** Last event received timestamp */
  lastEventAt: string | null;
}

export interface TicketRealtimeActions {
  /** Acknowledge and reset counts */
  acknowledge: (type?: 'all' | 'tickets' | 'messages' | 'escalations') => void;
  /** Clear all events */
  clearEvents: () => void;
  /** Subscribe to specific ticket events */
  subscribeToTicket: (ticketId: string) => void;
  /** Unsubscribe from specific ticket events */
  unsubscribeFromTicket: (ticketId: string) => void;
}

export type TicketRealtimeReturn = TicketRealtimeState & TicketRealtimeActions;

// ── Constants ────────────────────────────────────────────────────────────

const MAX_EVENTS = 50;

// ── Hook Implementation ──────────────────────────────────────────────────

export function useTicketRealtime(): TicketRealtimeReturn {
  const { socket, isConnected } = useSocket();
  const eventsRef = useRef<TicketEvent[]>([]);
  const subscribedTicketsRef = useRef<Set<string>>(new Set());

  const [recentEvents, setRecentEvents] = useState<TicketEvent[]>([]);
  const [newTicketCount, setNewTicketCount] = useState(0);
  const [statusChangeCount, setStatusChangeCount] = useState(0);
  const [newMessageCount, setNewMessageCount] = useState(0);
  const [escalationCount, setEscalationCount] = useState(0);
  const [lastEventAt, setLastEventAt] = useState<string | null>(null);

  // ── Event Handlers ────────────────────────────────────────────────────

  const handleTicketEvent = useCallback((event: TicketEvent) => {
    // Add to recent events (keep last MAX_EVENTS)
    eventsRef.current = [
      event,
      ...eventsRef.current.slice(0, MAX_EVENTS - 1),
    ];
    setRecentEvents([...eventsRef.current]);
    setLastEventAt(event.timestamp);

    // Update counts based on event type
    switch (event.event_type) {
      case 'ticket:new':
        setNewTicketCount((c) => c + 1);
        break;
      case 'ticket:status_changed':
        setStatusChangeCount((c) => c + 1);
        break;
      case 'message:new':
        setNewMessageCount((c) => c + 1);
        break;
      case 'ticket:escalated':
        setEscalationCount((c) => c + 1);
        break;
    }
  }, []);

  // ── Socket Event Subscriptions ────────────────────────────────────────

  useEffect(() => {
    if (!socket || !isConnected) return;

    // Subscribe to ticket events
    socket.on('ticket:new', handleTicketEvent);
    socket.on('ticket:status_changed', handleTicketEvent);
    socket.on('ticket:assigned', handleTicketEvent);
    socket.on('ticket:resolved', handleTicketEvent);
    socket.on('ticket:escalated', handleTicketEvent);
    socket.on('ticket:updated', handleTicketEvent);
    socket.on('ticket:merged', handleTicketEvent);
    socket.on('ticket:reopened', handleTicketEvent);
    socket.on('message:new', handleTicketEvent);
    socket.on('note:added', handleTicketEvent);

    return () => {
      socket.off('ticket:new', handleTicketEvent);
      socket.off('ticket:status_changed', handleTicketEvent);
      socket.off('ticket:assigned', handleTicketEvent);
      socket.off('ticket:resolved', handleTicketEvent);
      socket.off('ticket:escalated', handleTicketEvent);
      socket.off('ticket:updated', handleTicketEvent);
      socket.off('ticket:merged', handleTicketEvent);
      socket.off('ticket:reopened', handleTicketEvent);
      socket.off('message:new', handleTicketEvent);
      socket.off('note:added', handleTicketEvent);
    };
  }, [socket, isConnected, handleTicketEvent]);

  // ── Actions ───────────────────────────────────────────────────────────

  const acknowledge = useCallback(
    (type: 'all' | 'tickets' | 'messages' | 'escalations' = 'all') => {
      switch (type) {
        case 'all':
          setNewTicketCount(0);
          setStatusChangeCount(0);
          setNewMessageCount(0);
          setEscalationCount(0);
          break;
        case 'tickets':
          setNewTicketCount(0);
          setStatusChangeCount(0);
          break;
        case 'messages':
          setNewMessageCount(0);
          break;
        case 'escalations':
          setEscalationCount(0);
          break;
      }
    },
    []
  );

  const clearEvents = useCallback(() => {
    eventsRef.current = [];
    setRecentEvents([]);
    acknowledge('all');
  }, [acknowledge]);

  const subscribeToTicket = useCallback(
    (ticketId: string) => {
      if (!socket || !isConnected) return;
      if (subscribedTicketsRef.current.has(ticketId)) return;

      socket.emit('ticket:subscribe', { ticket_id: ticketId });
      subscribedTicketsRef.current.add(ticketId);
    },
    [socket, isConnected]
  );

  const unsubscribeFromTicket = useCallback(
    (ticketId: string) => {
      if (!socket || !isConnected) return;
      if (!subscribedTicketsRef.current.has(ticketId)) return;

      socket.emit('ticket:unsubscribe', { ticket_id: ticketId });
      subscribedTicketsRef.current.delete(ticketId);
    },
    [socket, isConnected]
  );

  return {
    recentEvents,
    newTicketCount,
    statusChangeCount,
    newMessageCount,
    escalationCount,
    isConnected,
    lastEventAt,
    acknowledge,
    clearEvents,
    subscribeToTicket,
    unsubscribeFromTicket,
  };
}

export default useTicketRealtime;
