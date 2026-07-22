/**
 * PARWA Socket Provider
 *
 * React Context provider that manages the Socket.io connection lifecycle.
 * - Connects after auth is verified
 * - Disconnects on unmount
 * - Subscribes to tenant room on connect
 * - Fetches missed events on reconnection
 * - Shows reconnection toast notifications
 * - Provides connection state context to children
 * - Triggers useRealtimeEvents() to start the central event dispatcher
 */

'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import toast from 'react-hot-toast';
import { socketClient, ConnectionState } from '@/lib/socket-client';
import { useAuth } from '@/hooks/useAuth';
import { useRealtimeEvents } from '@/hooks/useRealtimeEvents';
import { usePresenceStore } from '@/lib/presence-store';

// ── Types ────────────────────────────────────────────────────────────

export interface SocketContextValue {
  /** Whether the socket is currently connected */
  isConnected: boolean;
  /** Whether the socket is attempting to reconnect after a drop */
  isReconnecting: boolean;
  /** ISO timestamp of the last successful connection */
  lastConnected: string | null;
  /** Current raw connection state */
  connectionState: ConnectionState;
}

// ── Context ──────────────────────────────────────────────────────────

const SocketContext = createContext<SocketContextValue | undefined>(undefined);

// ── Provider ─────────────────────────────────────────────────────────

interface SocketProviderProps {
  children: React.ReactNode;
}

export function SocketProvider({ children }: SocketProviderProps) {
  const { isAuthenticated, user, isInitialized } = useAuth();

  // ── State ────────────────────────────────────────────────────────

  const [connectionState, setConnectionState] = useState<ConnectionState>(
    'disconnected'
  );
  const [lastConnected, setLastConnected] = useState<string | null>(null);
  const reconnectToastIdRef = useRef<string | null>(null);
  const prevConnectedRef = useRef(false);

  // ── Derived State ────────────────────────────────────────────────

  const isConnected = connectionState === 'connected';
  const isReconnecting =
    connectionState === 'connecting' && prevConnectedRef.current;

  // ── Connection Management ────────────────────────────────────────

  /**
   * Connect to the Socket.io server when authenticated.
   * Disconnect when authentication is lost.
   */
  useEffect(() => {
    if (!isInitialized) return;

    if (isAuthenticated && user?.company_id) {
      // Get token from cookie (httpOnly cookies are sent automatically,
      // but socket.io needs the token in the query string)
      // Try localStorage first (legacy), then extract from cookie
      let token: string | null = null;
      if (typeof window !== 'undefined') {
        token = localStorage.getItem('parwa_access_token');
        if (!token) {
          // Try to extract from cookie
          const match = document.cookie.match(/parwa_at=([^;]+)/);
          if (match) token = decodeURIComponent(match[1]);
        }
      }

      // Only connect if we have a token — otherwise socket will fail auth
      if (token) {
        devLog('Auth verified — connecting socket', {
          companyId: user.company_id,
          hasToken: true,
        });
        socketClient.connect(token, user.company_id);
      } else {
        devLog('No token found — skipping socket connection');
      }
    } else {
      // Not authenticated — ensure socket is disconnected
      if (socketClient.isConnected()) {
        devLog('Auth lost — disconnecting socket');
        socketClient.disconnect();
        setConnectionState('disconnected');
        prevConnectedRef.current = false;
      }
    }

    // Cleanup on unmount or when auth changes
    return () => {
      // Only disconnect if the component is truly unmounting
      // (not on re-renders)
    };
  }, [isAuthenticated, user?.company_id, isInitialized]);

  /**
   * Disconnect socket on provider unmount.
   */
  useEffect(() => {
    return () => {
      socketClient.disconnect();
    };
  }, []);

  // ── Socket Event Monitoring ──────────────────────────────────────

  const connectionStateRef = useRef(connectionState);
  connectionStateRef.current = connectionState;

  useEffect(() => {
    const interval = setInterval(() => {
      const state = socketClient.getConnectionState();
      const prevState = connectionStateRef.current;

      if (state !== prevState) {
        const wasConnected = prevConnectedRef.current;
        setConnectionState(state);

        if (state === 'connected') {
          setLastConnected(new Date().toISOString());
          if (reconnectToastIdRef.current) {
            toast.dismiss(reconnectToastIdRef.current);
            reconnectToastIdRef.current = null;
          }
          if (wasConnected) {
            toast.success('Reconnected to server', { duration: 3000, id: 'socket-reconnected' });
          }
          prevConnectedRef.current = true;
        } else if (state === 'disconnected' && wasConnected) {
          reconnectToastIdRef.current = toast.loading('Reconnecting...', { duration: Infinity, id: 'socket-reconnecting' });
        } else if (state === 'error' && wasConnected) {
          if (!reconnectToastIdRef.current) {
            reconnectToastIdRef.current = toast.loading('Connection lost — reconnecting...', { duration: Infinity, id: 'socket-error' });
          }
        }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  // ── Context Value ────────────────────────────────────────────────

  const value = useMemo<SocketContextValue>(
    () => ({
      isConnected,
      isReconnecting,
      lastConnected,
      connectionState,
    }),
    [isConnected, isReconnecting, lastConnected, connectionState]
  );

  return (
    <SocketContext.Provider value={value}>
      {children}
      {/* Start the central event dispatcher when connected */}
      {isAuthenticated && <RealtimeEventBridge />}
    </SocketContext.Provider>
  );
}

// ── Event Bridge Component ───────────────────────────────────────────

/**
 * Internal component that activates useRealtimeEvents when the user
 * is authenticated. Rendered as an invisible child of SocketProvider.
 */
function RealtimeEventBridge() {
  useRealtimeEvents();

  // Fetch initial presence data on mount
  React.useEffect(() => {
    usePresenceStore.getState().fetchPresence();
  }, []);

  return null;
}

// ── useSocketContext Hook ─────────────────────────────────────────────

/**
 * Access the socket connection context.
 * Must be used within a <SocketProvider>.
 */
export function useSocketContext(): SocketContextValue {
  const context = useContext(SocketContext);
  if (context === undefined) {
    throw new Error(
      'useSocketContext must be used within a <SocketProvider>'
    );
  }
  return context;
}

// ── Dev Logger ───────────────────────────────────────────────────────

function devLog(...args: unknown[]) {
  if (process.env.NODE_ENV === 'development') {
    console.log('[SocketProvider]', ...args);
  }
}

// ── Default Export ───────────────────────────────────────────────────

export default SocketProvider;
