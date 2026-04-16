/**
 * PARWA Socket.io Context
 *
 * Real-time WebSocket client for dashboard live updates.
 * Connects to backend Socket.io server at /ws/socket.io.
 * Tenant-scoped rooms, JWT auth, auto-reconnect with exponential backoff,
 * event buffer recovery for missed events during disconnection.
 *
 * Events consumed:
 *   ticket:new, ticket:status_changed, ticket:resolved, ticket:escalated
 *   agent:status_changed, ai:confidence_low
 *   notification:new
 *   system:error, system:recovered
 *   approval:pending, approval:approved, approval:rejected
 */

'use client';

import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
} from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuth } from '@/contexts/AuthContext';

// ── Types ──────────────────────────────────────────────────────────────

export interface BadgeCounts {
  tickets: number;
  approvals: number;
  notifications: number;
}

export interface SystemStatus {
  status: 'healthy' | 'degraded' | 'down';
  message: string;
  lastChecked: string;
}

export interface SocketContextValue {
  /** Whether the socket is connected */
  isConnected: boolean;
  /** Whether we're in the process of reconnecting */
  isReconnecting: boolean;
  /** Current system status (from Socket.io events) */
  systemStatus: SystemStatus;
  /** Live badge counts for sidebar */
  badgeCounts: BadgeCounts;
  /** Latest ticket event for dashboard refresh triggers */
  latestTicketEvent: string | null;
  /** Latest notification for bell badge */
  latestNotification: any | null;
  /** Unread notification count */
  unreadNotificationCount: number;
  /** Emergency pause state */
  isPaused: boolean;
  /** Current AI mode */
  aiMode: 'shadow' | 'supervised' | 'graduated';
  /** Raw socket instance (for advanced usage) */
  socket: Socket | null;
}

const defaultSystemStatus: SystemStatus = {
  status: 'healthy',
  message: 'All systems operational',
  lastChecked: new Date().toISOString(),
};

const defaultBadgeCounts: BadgeCounts = {
  tickets: 0,
  approvals: 0,
  notifications: 0,
};

// ── Context ────────────────────────────────────────────────────────────

const SocketContext = createContext<SocketContextValue>({
  isConnected: false,
  isReconnecting: false,
  systemStatus: defaultSystemStatus,
  badgeCounts: defaultBadgeCounts,
  latestTicketEvent: null,
  latestNotification: null,
  unreadNotificationCount: 0,
  isPaused: false,
  aiMode: 'shadow',
  socket: null,
});

// ── Provider ───────────────────────────────────────────────────────────

interface SocketProviderProps {
  children: React.ReactNode;
}

export function SocketProvider({ children }: SocketProviderProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const socketRef = useRef<Socket | null>(null);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const lastEventIdRef = useRef<string | null>(null);

  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>(defaultSystemStatus);
  const [badgeCounts, setBadgeCounts] = useState<BadgeCounts>(defaultBadgeCounts);
  const [latestTicketEvent, setLatestTicketEvent] = useState<string | null>(null);
  const [latestNotification, setLatestNotification] = useState<any>(null);
  const [unreadNotificationCount, setUnreadNotificationCount] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [aiMode, setAiMode] = useState<'shadow' | 'supervised' | 'graduated'>('shadow');

  // ── Connect / Disconnect ─────────────────────────────────────────────

  const connect = useCallback(() => {
    if (socketRef.current?.connected) return;

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const socket = io(`${API_BASE}/ws`, {
      path: '/ws/socket.io',
      transports: ['websocket', 'polling'],
      reconnection: false, // We handle reconnection ourselves
      timeout: 10000,
      auth: {
        token: 'anonymous', // Auth handled by httpOnly cookie
      },
    });

    socketRef.current = socket;
    reconnectAttemptsRef.current = 0;

    // ── Connection Events ──────────────────────────────────────────────

    socket.on('connect', () => {
      setIsConnected(true);
      setIsReconnecting(false);
      reconnectAttemptsRef.current = 0;

      // Join tenant room (server handles room assignment via session)
      socket.emit('event:subscribe', { events: ['*'] });

      // Recovery: fetch missed events
      if (lastEventIdRef.current) {
        socket.emit('events:recover', { last_event_id: lastEventIdRef.current });
      }
    });

    socket.on('disconnect', (reason) => {
      setIsConnected(false);
      if (reason === 'io server disconnect') {
        // Server forced disconnect — reconnect immediately
        scheduleReconnect();
      }
      // Client-side disconnect — don't reconnect (user logged out etc.)
    });

    socket.on('connect_error', (err) => {
      console.warn('[Socket.io] Connection error:', err.message);
      setIsConnected(false);
      scheduleReconnect();
    });

    // ── Ticket Events ──────────────────────────────────────────────────

    socket.on('ticket:new', (data: any) => {
      setLatestTicketEvent('ticket:new');
      setBadgeCounts(prev => ({
        ...prev,
        tickets: prev.tickets + 1,
      }));
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    socket.on('ticket:status_changed', (data: any) => {
      setLatestTicketEvent('ticket:status_changed');
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    socket.on('ticket:resolved', (data: any) => {
      setLatestTicketEvent('ticket:resolved');
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    socket.on('ticket:escalated', (data: any) => {
      setLatestTicketEvent('ticket:escalated');
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    // ── Agent Events ───────────────────────────────────────────────────

    socket.on('agent:status_changed', (data: any) => {
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    socket.on('ai:confidence_low', (data: any) => {
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    // ── Notification Events ────────────────────────────────────────────

    socket.on('notification:new', (data: any) => {
      setLatestNotification(data);
      setUnreadNotificationCount(prev => prev + 1);
      setBadgeCounts(prev => ({
        ...prev,
        notifications: prev.notifications + 1,
      }));
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    // ── System Events ──────────────────────────────────────────────────

    socket.on('system:error', (data: any) => {
      setSystemStatus({
        status: 'down',
        message: data.message || 'System error detected',
        lastChecked: new Date().toISOString(),
      });
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    socket.on('system:recovered', (data: any) => {
      setSystemStatus({
        status: 'healthy',
        message: 'All systems operational',
        lastChecked: new Date().toISOString(),
      });
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    socket.on('system:degraded', (data: any) => {
      setSystemStatus({
        status: 'degraded',
        message: data.message || 'Some services degraded',
        lastChecked: new Date().toISOString(),
      });
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    // ── Approval Events ────────────────────────────────────────────────

    socket.on('approval:pending', (data: any) => {
      setBadgeCounts(prev => ({
        ...prev,
        approvals: prev.approvals + 1,
      }));
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    socket.on('approval:approved', (data: any) => {
      setBadgeCounts(prev => ({
        ...prev,
        approvals: Math.max(0, prev.approvals - 1),
      }));
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    socket.on('approval:rejected', (data: any) => {
      setBadgeCounts(prev => ({
        ...prev,
        approvals: Math.max(0, prev.approvals - 1),
      }));
      lastEventIdRef.current = data.event_id || data.id || null;
    });

    // ── System Mode / Pause Events ─────────────────────────────────────

    socket.on('system:mode_changed', (data: any) => {
      if (data.mode) setAiMode(data.mode);
    });

    socket.on('system:paused', () => {
      setIsPaused(true);
    });

    socket.on('system:resumed', () => {
      setIsPaused(false);
    });

    socket.connect();
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (socketRef.current) {
      socketRef.current.removeAllListeners();
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    setIsConnected(false);
    setIsReconnecting(false);
  }, []);

  // ── Exponential Backoff Reconnect ────────────────────────────────────

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) return;
    setIsReconnecting(true);

    const attempt = reconnectAttemptsRef.current;
    // Max 30s between retries
    const delay = Math.min(1000 * Math.pow(2, attempt), 30000);
    reconnectAttemptsRef.current = attempt + 1;

    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      connect();
    }, delay);
  }, [connect]);

  // ── Lifecycle: Connect when authenticated, disconnect when not ───────

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      connect();
    } else if (!isLoading && !isAuthenticated) {
      disconnect();
    }
    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, isLoading]);

  // ── Context Value ────────────────────────────────────────────────────

  const value = useMemo<SocketContextValue>(() => ({
    isConnected,
    isReconnecting,
    systemStatus,
    badgeCounts,
    latestTicketEvent,
    latestNotification,
    unreadNotificationCount,
    isPaused,
    aiMode,
    socket: socketRef.current,
  }), [
    isConnected,
    isReconnecting,
    systemStatus,
    badgeCounts,
    latestTicketEvent,
    latestNotification,
    unreadNotificationCount,
    isPaused,
    aiMode,
  ]);

  return (
    <SocketContext.Provider value={value}>
      {children}
    </SocketContext.Provider>
  );
}

// ── Hook ───────────────────────────────────────────────────────────────

export function useSocket(): SocketContextValue {
  const ctx = useContext(SocketContext);
  return ctx;
}

export default SocketContext;
