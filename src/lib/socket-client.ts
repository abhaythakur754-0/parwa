/**
 * PARWA Socket.io Client Manager
 *
 * Singleton Socket.io client for the entire PARWA application.
 * Manages connection lifecycle, authentication, tenant room subscriptions,
 * reconnection with exponential backoff, and event listener cleanup.
 *
 * Connection URL: NEXT_PUBLIC_API_URL || 'http://localhost:8000', path: '/ws'
 * Auth: httpOnly `parwa_at` cookie sent automatically (withCredentials: true)
 * and verified by the backend handshake; an optional auth.token payload is
 * kept as a fallback for non-cookie clients.
 * Tenant room: emitted as 'event:subscribe' with { room: `tenant_{companyId}` }
 */

import { io, Socket } from 'socket.io-client';

// ── Types ────────────────────────────────────────────────────────────

export type ConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'error';

export interface SocketClientConfig {
  /** Backend URL (defaults to NEXT_PUBLIC_API_URL or http://localhost:8000) */
  url?: string;
  /** Socket.io path (defaults to '/ws') */
  path?: string;
  /** Maximum reconnection delay in ms (defaults to 30000) */
  maxReconnectDelay?: number;
  /** Initial reconnection delay in ms (defaults to 1000) */
  initialReconnectDelay?: number;
}

export interface MissedEvent {
  id: string;
  event: string;
  data: unknown;
  timestamp: string;
}

// ── Constants ────────────────────────────────────────────────────────

// Socket.io must connect directly to the backend (can't proxy WebSockets through Next.js API routes)
// In production, use the backend URL; in development, fall back to localhost
const DEFAULT_URL = process.env.NEXT_PUBLIC_SOCKET_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DEFAULT_PATH = '/ws';
const MAX_RECONNECT_DELAY = 30_000;
const INITIAL_RECONNECT_DELAY = 1_000;
const BACKOFF_MULTIPLIER = 2;

const isDev = process.env.NODE_ENV === 'development';

// ── Dev Logger ───────────────────────────────────────────────────────

function devLog(...args: unknown[]) {
  if (isDev) {
    console.log('[PARWA Socket]', ...args);
  }
}

function devWarn(...args: unknown[]) {
  if (isDev) {
    console.warn('[PARWA Socket]', ...args);
  }
}

function devError(...args: unknown[]) {
  if (isDev) {
    console.error('[PARWA Socket]', ...args);
  }
}

// ── Singleton Class ──────────────────────────────────────────────────

class SocketClient {
  private socket: Socket | null = null;
  private connectionState: ConnectionState = 'disconnected';
  private companyId: string | null = null;
  private currentToken: string | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private lastEventTimestamp: string | null = null;
  private config: Required<SocketClientConfig>;

  /** Track listeners for cleanup on disconnect */
  private listeners: Map<string, Set<(...args: unknown[]) => void>> = new Map();

  constructor(config?: SocketClientConfig) {
    this.config = {
      url: config?.url || DEFAULT_URL,
      path: config?.path || DEFAULT_PATH,
      maxReconnectDelay: config?.maxReconnectDelay || MAX_RECONNECT_DELAY,
      initialReconnectDelay: config?.initialReconnectDelay || INITIAL_RECONNECT_DELAY,
    };
  }

  // ── Public Methods ───────────────────────────────────────────────

  /**
   * Connect to the Socket.io server.
   * Authentication uses the httpOnly `parwa_at` cookie, which the browser
   * sends on the handshake (withCredentials: true) and the backend verifies.
   * @param companyId - Tenant/company ID for room subscription
   * @param token - Optional JWT access token (auth.token fallback for
   *                non-cookie clients; the cookie path is preferred)
   */
  connect(companyId: string, token?: string | null): void {
    if (typeof window === 'undefined') {
      devWarn('connect() called on server — ignoring');
      return;
    }

    // Avoid duplicate connections
    if (this.socket?.connected && this.companyId === companyId) {
      devLog('Already connected — skipping');
      return;
    }

    // Disconnect existing socket if any
    this.disconnect();

    this.companyId = companyId;
    this.currentToken = token || null;
    this.setConnectionState('connecting');

    devLog('Connecting to', this.config.url, 'path:', this.config.path);

    this.socket = io(this.config.url, {
      path: this.config.path,
      // Only attach an auth payload when a token was handed in — cookie
      // auth is the primary path and needs no client-side token.
      auth: this.currentToken ? { token: this.currentToken } : undefined,
      transports: ['websocket', 'polling'],
      reconnection: false, // We handle reconnection ourselves with exponential backoff
      timeout: 10_000,
      forceNew: true,
      // SECURITY: Send httpOnly cookies (parwa_at) on the WebSocket handshake.
      // This is the SECURE auth path — httpOnly cookies can't be stolen by XSS.
      // The auth.token payload (above) is a fallback for non-cookie clients;
      // if it's missing, the backend authenticates via the cookie instead.
      // This de-risks the C-03 security finding (tokens in localStorage).
      withCredentials: true,
    });

    this.setupEventHandlers();
  }

  /**
   * Disconnect from the Socket.io server and clean up.
   */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.reconnectAttempts = 0;

    if (this.socket) {
      devLog('Disconnecting');
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }

    this.listeners.clear();
    this.setConnectionState('disconnected');
  }

  /**
   * Attempt to reconnect to the Socket.io server.
   */
  reconnect(): void {
    if (!this.companyId) {
      devWarn('Cannot reconnect — no companyId set');
      return;
    }

    this.connect(this.companyId);
  }

  /**
   * Subscribe to a Socket.io event with automatic cleanup tracking.
   * @param event - Event name (e.g., 'ticket:new', 'notification:new')
   * @param callback - Event handler function
   */
  on(event: string, callback: (...args: unknown[]) => void): void {
    if (!this.socket) {
      devWarn(`Cannot subscribe to "${event}" — socket not initialized`);
      return;
    }

    this.socket.on(event, callback);

    // Track for cleanup
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  /**
   * Unsubscribe from a Socket.io event.
   * @param event - Event name
   * @param callback - The exact handler function to remove
   */
  off(event: string, callback: (...args: unknown[]) => void): void {
    if (!this.socket) return;

    this.socket.off(event, callback);

    // Clean up tracking
    const listeners = this.listeners.get(event);
    if (listeners) {
      listeners.delete(callback);
      if (listeners.size === 0) {
        this.listeners.delete(event);
      }
    }
  }

  /**
   * Emit an event to the Socket.io server.
   * @param event - Event name
   * @param data - Payload to send
   */
  emit(event: string, data?: unknown): void {
    if (!this.socket?.connected) {
      devWarn(`Cannot emit "${event}" — socket not connected`);
      return;
    }

    this.socket.emit(event, data);
    devLog(`Emitted "${event}"`, data);
  }

  /**
   * Get the current connection state.
   */
  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  /**
   * Get the underlying Socket.io instance (for advanced usage).
   * Returns null if not initialized.
   */
  getSocket(): Socket | null {
    return this.socket;
  }

  /**
   * Check if currently connected.
   */
  isConnected(): boolean {
    return this.connectionState === 'connected';
  }

  /**
   * Get the company ID currently subscribed to.
   */
  getCompanyId(): string | null {
    return this.companyId;
  }

  /**
   * Get the last event timestamp (used for reconnection recovery).
   */
  getLastEventTimestamp(): string | null {
    return this.lastEventTimestamp;
  }

  // ── Private Methods ──────────────────────────────────────────────

  /**
   * Set up all Socket.io event handlers.
   */
  private setupEventHandlers(): void {
    if (!this.socket) return;

    this.socket.on('connect', this.handleConnect.bind(this));
    this.socket.on('disconnect', this.handleDisconnect.bind(this));
    this.socket.on('connect_error', this.handleConnectError.bind(this));
  }

  /**
   * Handle successful connection.
   */
  private handleConnect(): void {
    devLog('Connected successfully');
    this.reconnectAttempts = 0;
    this.setConnectionState('connected');

    // Subscribe to tenant room
    if (this.companyId) {
      const room = `tenant_${this.companyId}`;
      this.emit('event:subscribe', { room });
      devLog('Subscribed to room:', room);
    }

    // Re-register all tracked listeners on the new socket
    this.reregisterListeners();

    // Fetch missed events if we have a lastEventTimestamp
    if (this.lastEventTimestamp) {
      this.fetchMissedEvents(this.lastEventTimestamp);
    }
  }

  /**
   * Handle disconnection from the server.
   */
  private handleDisconnect(reason: string): void {
    devLog('Disconnected:', reason);
    this.setConnectionState('disconnected');

    // Auto-reconnect unless explicitly disconnected
    if (reason !== 'io client disconnect') {
      this.scheduleReconnect();
    }
  }

  /**
   * Handle connection error.
   */
  private handleConnectError(error: Error): void {
    devError('Connection error:', error.message);
    this.setConnectionState('error');
    this.scheduleReconnect();
  }

  /**
   * Schedule a reconnection attempt with exponential backoff.
   * Backoff: 1s → 2s → 4s → 8s → 16s → 30s (max)
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer) return; // Already scheduled

    const delay = Math.min(
      this.config.initialReconnectDelay *
        Math.pow(BACKOFF_MULTIPLIER, this.reconnectAttempts),
      this.config.maxReconnectDelay
    );

    this.reconnectAttempts++;
    devLog(
      `Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`
    );

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;

      // Create new socket connection
      if (this.socket) {
        this.socket.removeAllListeners();
        this.socket.disconnect();
      }

      this.setConnectionState('connecting');

      this.socket = io(this.config.url, {
        path: this.config.path,
        auth: this.currentToken ? { token: this.currentToken } : undefined,
        transports: ['websocket', 'polling'],
        reconnection: false,
        timeout: 10_000,
        forceNew: true,
        // Cookies must flow on reconnect too — the backend handshake
        // authenticates the httpOnly parwa_at cookie (C-03 secure path).
        withCredentials: true,
      });

      this.setupEventHandlers();
    }, delay);
  }

  /**
   * Re-register all tracked event listeners on a new socket instance.
   */
  private reregisterListeners(): void {
    if (!this.socket) return;

    for (const [event, callbacks] of this.listeners) {
      for (const callback of callbacks) {
        this.socket.on(event, callback);
      }
    }

    devLog(
      `Re-registered ${this.listeners.size} event(s) on new socket`
    );
  }

  /**
   * Fetch missed events since the last seen timestamp.
   * Calls GET /api/events/since?last_seen={timestamp}
   */
  private async fetchMissedEvents(sinceTimestamp: string): Promise<void> {
    try {
      devLog('Fetching missed events since:', sinceTimestamp);

      const url = `${this.config.url}/api/events/since?last_seen=${encodeURIComponent(sinceTimestamp)}`;
      const response = await fetch(url, {
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(this.currentToken
            ? { Authorization: `Bearer ${this.currentToken}` }
            : {}),
        },
      });

      if (!response.ok) {
        devWarn('Failed to fetch missed events:', response.status);
        return;
      }

      const data = await response.json();
      const events: MissedEvent[] = Array.isArray(data)
        ? data
        : data.events ?? [];

      devLog(`Recovered ${events.length} missed event(s)`);

      // Replay missed events through the socket's event system
      for (const event of events) {
        if (this.socket && event.event) {
          this.socket.emit(event.event, event.data);
        }
        // Update lastEventTimestamp to the most recent one
        if (event.timestamp) {
          this.lastEventTimestamp = event.timestamp;
        }
      }
    } catch (error) {
      devError('Error fetching missed events:', error);
    }
  }

  /**
   * Update connection state and log.
   */
  private setConnectionState(state: ConnectionState): void {
    const prevState = this.connectionState;
    this.connectionState = state;

    if (prevState !== state) {
      devLog(`State: ${prevState} → ${state}`);
    }
  }

  /**
   * Update the last event timestamp (called by event dispatcher).
   */
  updateLastEventTimestamp(timestamp: string): void {
    this.lastEventTimestamp = timestamp;
  }
}

// ── Singleton Export ─────────────────────────────────────────────────

/**
 * Global singleton Socket.io client instance.
 *
 * Usage:
 *   import { socketClient } from '@/lib/socket-client';
 *   socketClient.connect(companyId);
 *   socketClient.on('ticket:new', (data) => { ... });
 *   socketClient.disconnect();
 */
export const socketClient = new SocketClient();

export default socketClient;
