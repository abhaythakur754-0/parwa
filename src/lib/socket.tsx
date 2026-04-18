/**
 * PARWA Socket.io Provider — Day 1
 *
 * Provides real-time WebSocket connection to the PARWA backend.
 * Wraps the entire dashboard layout to receive live events:
 * - ticket.created / ticket.updated / ticket.assigned
 * - notification.created
 * - system.status
 * - conversation.new_message
 *
 * Uses JWT auth token from localStorage for socket authentication.
 */

'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuth } from '@/hooks/useAuth';

// ── Types ──────────────────────────────────────────────────────────────

export interface TicketEvent {
  event_type: 'ticket.created' | 'ticket.updated' | 'ticket.assigned' | 'ticket.resolved';
  ticket_id: string;
  ticket_subject?: string;
  priority?: string;
  status?: string;
  assignee_id?: string;
  assignee_name?: string;
  timestamp: string;
}

export interface NotificationEvent {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'warning' | 'success' | 'error';
  read: boolean;
  created_at: string;
}

export interface SystemStatusEvent {
  status: 'healthy' | 'degraded' | 'down';
  message?: string;
  services?: Record<string, { status: string; latency_ms?: number }>;
}

export interface ConversationEvent {
  conversation_id: string;
  message_count: number;
  last_message?: string;
  customer_name?: string;
  channel?: string;
}

export interface BadgeCounts {
  tickets: number;
  approvals: number;
  notifications: number;
}

export interface SocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  badgeCounts: BadgeCounts;
  notifications: NotificationEvent[];
  latestTicketEvent: TicketEvent | null;
  systemStatus: SystemStatusEvent | null;
  markNotificationRead: (id: string) => void;
  clearNotifications: () => void;
}

// ── Context ────────────────────────────────────────────────────────────

export const SocketContext = createContext<SocketContextType>({
  socket: null,
  isConnected: false,
  badgeCounts: { tickets: 0, approvals: 0, notifications: 0 },
  notifications: [],
  latestTicketEvent: null,
  systemStatus: null,
  markNotificationRead: () => {},
  clearNotifications: () => {},
});

export function useSocket() {
  const ctx = useContext(SocketContext);
  if (!ctx) {
    throw new Error('useSocket must be used within a SocketProvider');
  }
  return ctx;
}

// ── Provider ───────────────────────────────────────────────────────────

interface SocketProviderProps {
  children: React.ReactNode;
}

export function SocketProvider({ children }: SocketProviderProps) {
  const { user } = useAuth();
  const socketRef = useRef<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [badgeCounts, setBadgeCounts] = useState<BadgeCounts>({
    tickets: 0,
    approvals: 0,
    notifications: 0,
  });
  const [notifications, setNotifications] = useState<NotificationEvent[]>([]);
  const [latestTicketEvent, setLatestTicketEvent] = useState<TicketEvent | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatusEvent | null>(null);

  const markNotificationRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
    setBadgeCounts((prev) => ({
      ...prev,
      notifications: Math.max(0, prev.notifications - 1),
    }));
  }, []);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
    setBadgeCounts((prev) => ({ ...prev, notifications: 0 }));
  }, []);

  useEffect(() => {
    if (!user?.id) return;

    const token = typeof window !== 'undefined'
      ? localStorage.getItem('parwa_access_token')
      : null;

    if (!token) return;

    const SOCKET_URL = process.env.NEXT_PUBLIC_SOCKET_URL || process.env.NEXT_PUBLIC_API_URL || '';
    const socket = io(SOCKET_URL, {
      auth: { token },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 2000,
      timeout: 15000,
    });

    socketRef.current = socket;

    // ── Connection Events ───────────────────────────────────────────
    socket.on('connect', () => {
      setIsConnected(true);
      // Join tenant room
      socket.emit('join', { tenant_id: user.company_id || user.id });
    });

    socket.on('disconnect', (reason) => {
      setIsConnected(false);
    });

    socket.on('connect_error', (err) => {
      setIsConnected(false);
      // Don't spam console — connect will auto-retry
    });

    // ── Ticket Events ───────────────────────────────────────────────
    socket.on('ticket.created', (data: TicketEvent) => {
      setLatestTicketEvent(data);
      setBadgeCounts((prev) => ({ ...prev, tickets: prev.tickets + 1 }));
    });

    socket.on('ticket.updated', (data: TicketEvent) => {
      setLatestTicketEvent(data);
    });

    socket.on('ticket.assigned', (data: TicketEvent) => {
      setLatestTicketEvent(data);
    });

    socket.on('ticket.resolved', (data: TicketEvent) => {
      setLatestTicketEvent(data);
      setBadgeCounts((prev) => ({
        ...prev,
        tickets: Math.max(0, prev.tickets - 1),
      }));
    });

    // ── Notification Events ─────────────────────────────────────────
    socket.on('notification.created', (data: NotificationEvent) => {
      setNotifications((prev) => [data, ...prev].slice(0, 50));
      setBadgeCounts((prev) => ({
        ...prev,
        notifications: prev.notifications + 1,
      }));
    });

    // ── System Status ───────────────────────────────────────────────
    socket.on('system.status', (data: SystemStatusEvent) => {
      setSystemStatus(data);
    });

    // ── Badge Count Sync ────────────────────────────────────────────
    socket.on('badge_counts', (data: BadgeCounts) => {
      setBadgeCounts(data);
    });

    // ── Cleanup ─────────────────────────────────────────────────────
    return () => {
      socket.off('connect');
      socket.off('disconnect');
      socket.off('connect_error');
      socket.off('ticket.created');
      socket.off('ticket.updated');
      socket.off('ticket.assigned');
      socket.off('ticket.resolved');
      socket.off('notification.created');
      socket.off('system.status');
      socket.off('badge_counts');
      socket.disconnect();
      socketRef.current = null;
    };
  }, [user?.id, user?.company_id]);

  const value: SocketContextType = {
    socket: socketRef.current,
    isConnected,
    badgeCounts,
    notifications,
    latestTicketEvent,
    systemStatus,
    markNotificationRead,
    clearNotifications,
  };

  return (
    <SocketContext.Provider value={value}>
      {children}
    </SocketContext.Provider>
  );
}

export default SocketProvider;
