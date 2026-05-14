/**
 * PARWA useRealtimeEvents Hook
 *
 * Central event dispatcher that subscribes to all backend Socket.io events
 * and routes them to the appropriate Zustand stores.
 *
 * Called from SocketProvider — starts the event pipeline when authenticated.
 *
 * Event routing:
 *   ticket:*       → useTicketStore
 *   notification:* → useNotificationStore (placeholder — will be created)
 *   approval:*     → useApprovalStore (placeholder — will be created)
 *   system:*       → system health store (placeholder — will be created)
 *   billing:*      → useBillingStore / useVariantStore
 *   ai:*           → AI streaming state (placeholder — will be created)
 *   chat:*         → chat hooks (delegated for future phases)
 *
 * For stores that don't exist yet, placeholder references are created that
 * can be wired up when those stores are implemented in future phases.
 */

'use client';

import { useCallback, useEffect, useRef } from 'react';
import toast from 'react-hot-toast';
import { socketClient } from '@/lib/socket-client';

// ── Store Imports ───────────────────────────────────────────────────

import { useTicketStore, Ticket, TicketMessage, TicketPriority, TicketStatus } from '@/lib/ticket-store';
import { useBillingStore } from '@/lib/billing-store';
import { useVariantStore, VariantTier } from '@/lib/variant-store';
import { useNotificationStore } from '@/lib/notification-store';
import { useApprovalStore } from '@/lib/approval-store';
import { useSystemHealthStore } from '@/lib/system-health-store';

// ── AI State Store Placeholder (Phase 5 — Real-Time Chat) ──────────
// AI streaming state will be implemented in Phase 5 when we build
// real-time chat with token-level streaming.

interface AIStateStoreActions {
  appendChunk: (chunk: string) => void;
  setThinking: (isThinking: boolean) => void;
  setDraftReady: (draft: { content: string; ticketId?: string }) => void;
  showConfidenceWarning: (info: { confidence: number; ticketId?: string }) => void;
}

const aiStateStorePlaceholder: AIStateStoreActions = {
  appendChunk: (chunk) => {
    if (process.env.NODE_ENV === 'development') {
      console.log('[useRealtimeEvents] ai:appendChunk', chunk);
    }
  },
  setThinking: (isThinking) => {
    if (process.env.NODE_ENV === 'development') {
      console.log('[useRealtimeEvents] ai:setThinking', isThinking);
    }
  },
  setDraftReady: (draft) => {
    if (process.env.NODE_ENV === 'development') {
      console.log('[useRealtimeEvents] ai:setDraftReady', draft);
    }
  },
  showConfidenceWarning: (info) => {
    if (process.env.NODE_ENV === 'development') {
      console.log('[useRealtimeEvents] ai:showConfidenceWarning', info);
    }
  },
};

// ── Chat State Placeholder (Phase 5 — Real-Time Chat) ──────────────
// Chat events will be routed to chat hooks in Phase 5.

interface ChatStateActions {
  addMessage: (message: { id: string; content: string; sender: string; timestamp: string }) => void;
  setTyping: (info: { userId: string; isTyping: boolean }) => void;
  markRead: (info: { messageIds: string[]; readBy: string }) => void;
}

const chatStatePlaceholder: ChatStateActions = {
  addMessage: (message) => {
    if (process.env.NODE_ENV === 'development') {
      console.log('[useRealtimeEvents] chat:addMessage', message);
    }
  },
  setTyping: (info) => {
    if (process.env.NODE_ENV === 'development') {
      console.log('[useRealtimeEvents] chat:setTyping', info);
    }
  },
  markRead: (info) => {
    if (process.env.NODE_ENV === 'development') {
      console.log('[useRealtimeEvents] chat:markRead', info);
    }
  },
};

// ── Event Data Types ─────────────────────────────────────────────────
// Type definitions for incoming Socket.io event payloads.

// Ticket events
interface TicketNewData {
  ticket: Ticket;
}

interface TicketAssignedData {
  ticketId: string;
  agentName: string;
  agentId?: string;
}

interface TicketMessageNewData {
  ticketId: string;
  message: TicketMessage;
}

interface TicketResolvedData {
  ticketId: string;
  resolution?: string;
  resolvedAt?: string;
}

interface TicketEscalatedData {
  ticketId: string;
  reason?: string;
  escalatedTo?: string;
}

interface TicketSlaWarningData {
  ticketId: string;
  ticketNumber?: string;
  minutesRemaining: number;
  slaTarget: string;
}

interface TicketSlaBreachedData {
  ticketId: string;
  ticketNumber?: string;
  breachedAt: string;
  slaTarget: string;
}

interface TicketCollisionData {
  ticketId: string;
  activeAgents: string[];
  currentAgent: string;
}

// Notification events
interface NotificationNewData {
  id: string;
  type: string;
  title: string;
  message: string;
  data?: Record<string, unknown>;
}

interface NotificationReadData {
  id: string;
}

interface NotificationBulkData {
  notifications: NotificationNewData[];
}

// Approval events
interface ApprovalPendingData {
  approval: ApprovalItem;
}

interface ApprovalStatusData {
  id: string;
  status: 'approved' | 'rejected';
  approvedBy?: string;
  reason?: string;
}

interface ApprovalTimeoutData {
  id: string;
  escalatedTo?: string;
}

interface ApprovalBulkData {
  approvals: ApprovalItem[];
}

// System events
interface SystemHealthData {
  status: SystemHealthStatus;
}

interface SystemQueueDepthData {
  depth: number;
  queueName: string;
}

interface SystemErrorData {
  message: string;
  severity: string;
  timestamp: string;
}

interface SystemMaintenanceData {
  active: boolean;
  message?: string;
  scheduledEnd?: string;
}

// Billing events
interface BillingPlanChangedData {
  tier: VariantTier;
  changedAt?: string;
}

interface BillingUsageAlertData {
  resource: string;
  used: number;
  limit: number;
  percentage: number;
}

// AI events
interface AiChunkData {
  chunk: string;
  ticketId?: string;
  requestId?: string;
}

interface AiThinkingData {
  isThinking: boolean;
  ticketId?: string;
  requestId?: string;
}

interface AiDraftReadyData {
  content: string;
  ticketId?: string;
  confidence?: number;
}

interface AiConfidenceLowData {
  confidence: number;
  ticketId?: string;
  reason?: string;
}

// Chat events
interface ChatMessageData {
  id: string;
  content: string;
  sender: string;
  timestamp: string;
}

interface ChatTypingData {
  userId: string;
  isTyping: boolean;
}

interface ChatReadData {
  messageIds: string[];
  readBy: string;
}

// ── Hook ─────────────────────────────────────────────────────────────

/**
 * Central event dispatcher.
 * Subscribes to all backend Socket.io events and routes them to Zustand stores.
 * Called internally by SocketProvider.
 */
export function useRealtimeEvents(): void {
  // Track whether we've registered listeners to avoid duplicates
  const registeredRef = useRef(false);

  // ── Ticket Event Handlers ──────────────────────────────────────

  const handleTicketNew = useCallback((...args: unknown[]) => {
    const data = args[0] as TicketNewData;
    if (!data?.ticket) return;

    const store = useTicketStore.getState();

    // Check if ticket already exists (avoid duplicates)
    const existing = store.getTicket(data.ticket.id);
    if (existing) return;

    // Prepend ticket to the list
    store.addTicket({
      subject: data.ticket.subject,
      description: data.ticket.description,
      category: data.ticket.category,
      priority: data.ticket.priority,
      channel: data.ticket.channel,
      customer_name: data.ticket.customer_name,
      customer_email: data.ticket.customer_email,
    });

    toast.success(`New ticket: ${data.ticket.subject}`, {
      duration: 4000,
      id: `ticket-new-${data.ticket.id}`,
    });

    updateLastEventTimestamp();
  }, []);

  const handleTicketAssigned = useCallback((...args: unknown[]) => {
    const data = args[0] as TicketAssignedData;
    if (!data?.ticketId) return;

    const store = useTicketStore.getState();
    const ticket = store.getTicket(data.ticketId);

    if (ticket) {
      // Update ticket with new agent assignment
      const updatedTickets = store.tickets.map((t) =>
        t.id === data.ticketId
          ? { ...t, assigned_agent: data.agentName, updated_at: new Date().toISOString() }
          : t
      );
      useTicketStore.setState({ tickets: updatedTickets });
    }

    toast.success(`Ticket assigned to ${data.agentName}`, {
      duration: 3000,
      id: `ticket-assigned-${data.ticketId}`,
    });

    updateLastEventTimestamp();
  }, []);

  const handleTicketMessageNew = useCallback((...args: unknown[]) => {
    const data = args[0] as TicketMessageNewData;
    if (!data?.ticketId || !data?.message) return;

    const store = useTicketStore.getState();

    // Add message to the ticket
    store.addMessage(data.ticketId, {
      sender: data.message.sender,
      sender_name: data.message.sender_name,
      content: data.message.content,
      variant: data.message.variant,
    });

    // Increment unread counter (could be added to ticket store in future)
    toast(`New message on ticket`, {
      icon: '💬',
      duration: 3000,
      id: `ticket-msg-${data.ticketId}-${data.message.id}`,
    });

    updateLastEventTimestamp();
  }, []);

  const handleTicketResolved = useCallback((...args: unknown[]) => {
    const data = args[0] as TicketResolvedData;
    if (!data?.ticketId) return;

    const store = useTicketStore.getState();
    store.resolveTicket(data.ticketId, data.resolution);

    toast.success('Ticket resolved!', {
      duration: 4000,
      id: `ticket-resolved-${data.ticketId}`,
    });

    updateLastEventTimestamp();
  }, []);

  const handleTicketEscalated = useCallback((...args: unknown[]) => {
    const data = args[0] as TicketEscalatedData;
    if (!data?.ticketId) return;

    const store = useTicketStore.getState();
    store.escalateToHuman(data.ticketId);

    toast.error('Ticket escalated — requires human attention', {
      duration: 5000,
      id: `ticket-escalated-${data.ticketId}`,
    });

    updateLastEventTimestamp();
  }, []);

  const handleTicketSlaWarning = useCallback((...args: unknown[]) => {
    const data = args[0] as TicketSlaWarningData;
    if (!data?.ticketId) return;

    toast(
      `⚠️ SLA Warning: ${data.minutesRemaining} min remaining${data.ticketNumber ? ` for ${data.ticketNumber}` : ''}`,
      {
        icon: '⏰',
        duration: 6000,
        id: `sla-warning-${data.ticketId}`,
      }
    );

    updateLastEventTimestamp();
  }, []);

  const handleTicketSlaBreached = useCallback((...args: unknown[]) => {
    const data = args[0] as TicketSlaBreachedData;
    if (!data?.ticketId) return;

    toast.error(
      `🚨 SLA Breached${data.ticketNumber ? ` on ${data.ticketNumber}` : ''}! Target: ${data.slaTarget}`,
      {
        duration: 8000,
        id: `sla-breached-${data.ticketId}`,
      }
    );

    updateLastEventTimestamp();
  }, []);

  const handleTicketCollision = useCallback((...args: unknown[]) => {
    const data = args[0] as TicketCollisionData;
    if (!data?.ticketId) return;

    toast(
      `⚠️ Collision detected: ${data.activeAgents?.length || 0} agent(s) viewing this ticket`,
      {
        icon: '👥',
        duration: 4000,
        id: `ticket-collision-${data.ticketId}`,
      }
    );

    updateLastEventTimestamp();
  }, []);

  // ── Notification Event Handlers ────────────────────────────────

  const handleNotificationNew = useCallback((...args: unknown[]) => {
    const data = args[0];
    if (!data) return;

    // Route directly to the real notification store
    useNotificationStore.getState().handleNotificationNew(data);

    updateLastEventTimestamp();
  }, []);

  const handleNotificationRead = useCallback((...args: unknown[]) => {
    const data = args[0] as NotificationReadData;
    if (!data?.id) return;

    useNotificationStore.getState().handleNotificationRead(data);
    updateLastEventTimestamp();
  }, []);

  const handleNotificationBulk = useCallback((...args: unknown[]) => {
    const data = args[0] as NotificationBulkData;
    if (!data?.notifications) return;

    useNotificationStore.getState().handleNotificationBulk(data);
    updateLastEventTimestamp();
  }, []);

  // ── Approval Event Handlers ────────────────────────────────────

  const handleApprovalPending = useCallback((...args: unknown[]) => {
    const data = args[0];
    if (!data) return;

    // Route directly to the real approval store
    useApprovalStore.getState().handleApprovalPending(data);

    // Also push a notification about the approval
    useNotificationStore.getState().addToast({
      type: 'approval',
      category: 'approval',
      title: 'New Approval Request',
      message: String((data as Record<string, unknown>).title || 'An AI agent needs your approval'),
      priority: 'high',
      actionUrl: '/dashboard/monitoring',
      actionLabel: 'Review',
    });

    updateLastEventTimestamp();
  }, []);

  const handleApprovalApproved = useCallback((...args: unknown[]) => {
    const data = args[0] as { id: string; respondedBy?: string; reason?: string };
    if (!data?.id) return;

    useApprovalStore.getState().handleApprovalApproved(data);

    toast.success('Approval granted', {
      duration: 3000,
      id: `approval-approved-${data.id}`,
    });

    updateLastEventTimestamp();
  }, []);

  const handleApprovalRejected = useCallback((...args: unknown[]) => {
    const data = args[0] as { id: string; respondedBy?: string; reason?: string };
    if (!data?.id) return;

    useApprovalStore.getState().handleApprovalRejected(data);

    toast.error('Approval rejected', {
      duration: 4000,
      id: `approval-rejected-${data.id}`,
    });

    updateLastEventTimestamp();
  }, []);

  const handleApprovalTimeout = useCallback((...args: unknown[]) => {
    const data = args[0] as { id: string };
    if (!data?.id) return;

    useApprovalStore.getState().handleApprovalTimeout(data);

    toast.error('Approval timed out — escalated', {
      duration: 5000,
      id: `approval-timeout-${data.id}`,
    });

    updateLastEventTimestamp();
  }, []);

  const handleApprovalBulk = useCallback((...args: unknown[]) => {
    const data = args[0] as { approvals: unknown[] };
    if (!data?.approvals) return;

    useApprovalStore.getState().handleApprovalBatch(data);
    updateLastEventTimestamp();
  }, []);

  // ── System Event Handlers ──────────────────────────────────────

  const handleSystemHealth = useCallback((...args: unknown[]) => {
    const data = args[0];
    if (!data) return;

    // Route directly to the real system health store
    useSystemHealthStore.getState().handleSystemHealth(data);

    updateLastEventTimestamp();
  }, []);

  const handleSystemQueueDepth = useCallback((...args: unknown[]) => {
    const data = args[0];
    if (!data) return;

    useSystemHealthStore.getState().handleSystemQueueDepth(data);

    updateLastEventTimestamp();
  }, []);

  const handleSystemError = useCallback((...args: unknown[]) => {
    const data = args[0];
    if (!data) return;

    useSystemHealthStore.getState().handleSystemError(data);

    // Only show toast for high-severity errors
    const severity = (data as Record<string, unknown>).severity;
    const message = String((data as Record<string, unknown>).message || 'System error');
    if (severity === 'critical' || severity === 'high') {
      toast.error(`System Error: ${message}`, {
        duration: 6000,
        id: `system-error-${Date.now()}`,
      });
    }

    updateLastEventTimestamp();
  }, []);

  const handleSystemMaintenance = useCallback((...args: unknown[]) => {
    const data = args[0];
    if (!data) return;

    useSystemHealthStore.getState().handleSystemMaintenance(data);

    const isActive = Boolean((data as Record<string, unknown>).active ?? (data as Record<string, unknown>).is_maintenance ?? false);
    const message = String((data as Record<string, unknown>).message || '');

    if (isActive) {
      toast(
        `Scheduled Maintenance${message ? `: ${message}` : ''}`,
        {
          icon: '🔧',
          duration: 10000,
          id: 'system-maintenance',
        }
      );
    }

    updateLastEventTimestamp();
  }, []);

  // ── Billing Event Handlers ─────────────────────────────────────

  const handleBillingPlanChanged = useCallback((...args: unknown[]) => {
    const data = args[0] as BillingPlanChangedData;
    if (!data?.tier) return;

    // Validate tier
    const validTiers: VariantTier[] = ['mini', 'pro', 'high'];
    if (!validTiers.includes(data.tier)) return;

    // Update variant store
    useVariantStore.getState().setTier(data.tier);

    // Update billing store
    useBillingStore.getState().fetchBilling();

    toast.success(`Plan updated to ${data.tier.charAt(0).toUpperCase() + data.tier.slice(1)}`, {
      duration: 4000,
      id: 'billing-plan-changed',
    });

    updateLastEventTimestamp();
  }, []);

  const handleBillingUsageAlert = useCallback((...args: unknown[]) => {
    const data = args[0] as BillingUsageAlertData;
    if (!data) return;

    const pct = Math.round(data.percentage * 100);

    toast(
      `📊 Usage Alert: ${data.resource} at ${pct}% (${data.used}/${data.limit})`,
      {
        icon: pct >= 90 ? '🔴' : '🟡',
        duration: pct >= 90 ? 8000 : 5000,
        id: `billing-usage-${data.resource}`,
      }
    );

    // Refresh usage data
    useBillingStore.getState().fetchUsage();

    updateLastEventTimestamp();
  }, []);

  // ── AI Event Handlers ──────────────────────────────────────────

  const handleAiChunk = useCallback((...args: unknown[]) => {
    const data = args[0] as AiChunkData;
    if (!data?.chunk) return;

    aiStateStorePlaceholder.appendChunk(data.chunk);
    updateLastEventTimestamp();
  }, []);

  const handleAiThinking = useCallback((...args: unknown[]) => {
    const data = args[0] as AiThinkingData;
    if (data === undefined) return;

    aiStateStorePlaceholder.setThinking(data.isThinking);

    if (data.isThinking) {
      toast('AI is thinking...', {
        icon: '🤔',
        duration: 2000,
        id: `ai-thinking-${data.ticketId || 'general'}`,
      });
    }

    updateLastEventTimestamp();
  }, []);

  const handleAiDraftReady = useCallback((...args: unknown[]) => {
    const data = args[0] as AiDraftReadyData;
    if (!data?.content) return;

    aiStateStorePlaceholder.setDraftReady({
      content: data.content,
      ticketId: data.ticketId,
    });

    toast('AI draft ready for review', {
      icon: '✍️',
      duration: 4000,
      id: `ai-draft-${data.ticketId || 'general'}`,
    });

    updateLastEventTimestamp();
  }, []);

  const handleAiConfidenceLow = useCallback((...args: unknown[]) => {
    const data = args[0] as AiConfidenceLowData;
    if (!data) return;

    aiStateStorePlaceholder.showConfidenceWarning({
      confidence: data.confidence,
      ticketId: data.ticketId,
    });

    toast.error(
      `⚠️ Low AI Confidence (${Math.round(data.confidence * 100)}%)${data.reason ? `: ${data.reason}` : ''}`,
      {
        duration: 6000,
        id: `ai-confidence-${data.ticketId || 'general'}`,
      }
    );

    updateLastEventTimestamp();
  }, []);

  // ── Chat Event Handlers (Delegated for Future Phases) ──────────

  const handleChatMessage = useCallback((...args: unknown[]) => {
    const data = args[0] as ChatMessageData;
    if (!data) return;

    chatStatePlaceholder.addMessage({
      id: data.id,
      content: data.content,
      sender: data.sender,
      timestamp: data.timestamp,
    });

    updateLastEventTimestamp();
  }, []);

  const handleChatTyping = useCallback((...args: unknown[]) => {
    const data = args[0] as ChatTypingData;
    if (!data) return;

    chatStatePlaceholder.setTyping({
      userId: data.userId,
      isTyping: data.isTyping,
    });

    updateLastEventTimestamp();
  }, []);

  const handleChatRead = useCallback((...args: unknown[]) => {
    const data = args[0] as ChatReadData;
    if (!data) return;

    chatStatePlaceholder.markRead({
      messageIds: data.messageIds,
      readBy: data.readBy,
    });

    updateLastEventTimestamp();
  }, []);

  // ── Register All Event Listeners ───────────────────────────────

  useEffect(() => {
    // Prevent duplicate registrations (React StrictMode double-mount)
    if (registeredRef.current) return;
    registeredRef.current = true;

    const events: Array<[string, (...args: unknown[]) => void]> = [
      // ── Ticket events ──
      ['ticket:new', handleTicketNew],
      ['ticket:assigned', handleTicketAssigned],
      ['ticket:message_new', handleTicketMessageNew],
      ['ticket:resolved', handleTicketResolved],
      ['ticket:escalated', handleTicketEscalated],
      ['ticket:sla_warning', handleTicketSlaWarning],
      ['ticket:sla_breached', handleTicketSlaBreached],
      ['ticket:collision', handleTicketCollision],

      // ── Notification events ──
      ['notification:new', handleNotificationNew],
      ['notification:read', handleNotificationRead],
      ['notification:bulk', handleNotificationBulk],

      // ── Approval events ──
      ['approval:pending', handleApprovalPending],
      ['approval:approved', handleApprovalApproved],
      ['approval:rejected', handleApprovalRejected],
      ['approval:timeout', handleApprovalTimeout],
      ['approval:batch', handleApprovalBulk],

      // ── System events ──
      ['system:health', handleSystemHealth],
      ['system:queue_depth', handleSystemQueueDepth],
      ['system:error', handleSystemError],
      ['system:maintenance', handleSystemMaintenance],

      // ── Billing events ──
      ['billing:plan_changed', handleBillingPlanChanged],
      ['billing:usage_alert', handleBillingUsageAlert],

      // ── AI events ──
      ['ai:chunk', handleAiChunk],
      ['ai:thinking', handleAiThinking],
      ['ai:draft_ready', handleAiDraftReady],
      ['ai:confidence_low', handleAiConfidenceLow],

      // ── Chat events ──
      ['chat:message', handleChatMessage],
      ['chat:typing', handleChatTyping],
      ['chat:read', handleChatRead],
    ];

    // Register each event with the socket client
    for (const [event, handler] of events) {
      socketClient.on(event, handler);
    }

    if (process.env.NODE_ENV === 'development') {
      console.log(
        `[useRealtimeEvents] Registered ${events.length} event listeners`
      );
    }

    // Cleanup on unmount
    return () => {
      for (const [event, handler] of events) {
        socketClient.off(event, handler);
      }
      registeredRef.current = false;

      if (process.env.NODE_ENV === 'development') {
        console.log('[useRealtimeEvents] Unregistered all event listeners');
      }
    };
    // We intentionally only run this effect once on mount.
    // The callbacks are stable (useCallback with []) so they won't change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

// ── Helpers ──────────────────────────────────────────────────────────

/**
 * Update the last event timestamp on the socket client for
 * reconnection recovery.
 */
function updateLastEventTimestamp(): void {
  socketClient.updateLastEventTimestamp(new Date().toISOString());
}

export default useRealtimeEvents;
