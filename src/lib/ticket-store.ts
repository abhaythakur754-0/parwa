'use client';

import { create } from 'zustand';
import { v4 as uuid } from 'uuid';
import toast from 'react-hot-toast';

// ── Types ────────────────────────────────────────────────────────────

export type TicketCategory =
  | 'billing_payments'
  | 'order_management'
  | 'account_management'
  | 'technical_support'
  | 'returns_exchanges'
  | 'shipping_delivery'
  | 'product_information'
  | 'complaints'
  | 'vip_enterprise'
  | 'fraud_security';

export type TicketPriority = 'low' | 'medium' | 'high' | 'critical';
export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'closed' | 'awaiting_client' | 'awaiting_human';
export type TicketChannel = 'email' | 'chat' | 'sms' | 'voice';
export type TicketVariant = 'light' | 'medium' | 'heavy';
export type MessageSender = 'customer' | 'ai_agent' | 'human_agent' | 'system';

export interface TicketMessage {
  id: string;
  ticket_id: string;
  sender: MessageSender;
  sender_name: string;
  content: string;
  created_at: string;
  variant?: TicketVariant;
}

export interface Ticket {
  id: string;
  ticket_number: string;
  subject: string;
  description: string;
  category: TicketCategory;
  priority: TicketPriority;
  status: TicketStatus;
  channel: TicketChannel;
  customer_name: string;
  customer_email: string;
  company_id?: string | null;  // Company context for filtering
  assigned_variant: TicketVariant | null;
  assigned_agent: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  first_response_at: string | null;
  resolution_time_hours: number | null;
  ai_confidence: number | null;
  cost_per_ticket: number | null;
  savings_per_ticket: number | null;
  messages: TicketMessage[];
  tags: string[];
  // New fields for agent control
  skipped: boolean;           // User marked as "do not auto-solve"
  agent_stopped: boolean;     // Agent processing halted
  kb_matched: boolean;        // KB article found for this ticket
  kb_article_id?: string | null;  // Matched KB article ID
}

export interface TicketStats {
  total: number;
  byStatus: Record<TicketStatus, number>;
  byCategory: Record<TicketCategory, number>;
  byPriority: Record<TicketPriority, number>;
  byVariant: Record<TicketVariant, number>;
  byChannel: Record<TicketChannel, number>;
  resolved: number;
  resolutionRate: number;
  avgResolutionTime: number | null;
  totalCost: number;
  totalSavings: number;
}

// ── Display Helpers ─────────────────────────────────────────────────

export const CATEGORY_LABELS: Record<TicketCategory, string> = {
  billing_payments: 'Billing & Payments',
  order_management: 'Order Management',
  account_management: 'Account Management',
  technical_support: 'Technical Support',
  returns_exchanges: 'Returns & Exchanges',
  shipping_delivery: 'Shipping & Delivery',
  product_information: 'Product Information',
  complaints: 'Complaints',
  vip_enterprise: 'VIP / Enterprise',
  fraud_security: 'Fraud & Security',
};

export const PRIORITY_LABELS: Record<TicketPriority, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
};

export const STATUS_LABELS: Record<TicketStatus, string> = {
  open: 'Open',
  in_progress: 'In Progress',
  resolved: 'Resolved',
  closed: 'Closed',
  awaiting_client: 'Awaiting Client',
  awaiting_human: 'Escalated',
};

export const CHANNEL_LABELS: Record<TicketChannel, string> = {
  email: 'Email',
  chat: 'Chat',
  sms: 'SMS',
  voice: 'Voice',
};

export const VARIANT_LABELS: Record<TicketVariant, string> = {
  light: 'Light (Gemini Flash)',
  medium: 'Medium (Gemini Pro)',
  heavy: 'Heavy (Claude 3.5)',
};

export const VARIANT_COST: Record<TicketVariant, number> = {
  light: 0.002,
  medium: 0.015,
  heavy: 0.05,
};

export const ALL_CATEGORIES: TicketCategory[] = [
  'billing_payments', 'order_management', 'account_management', 'technical_support',
  'returns_exchanges', 'shipping_delivery', 'product_information', 'complaints',
  'vip_enterprise', 'fraud_security',
];

export const ALL_STATUSES: TicketStatus[] = [
  'open', 'in_progress', 'resolved', 'closed', 'awaiting_client', 'awaiting_human',
];

export const ALL_PRIORITIES: TicketPriority[] = ['low', 'medium', 'high', 'critical'];
export const ALL_CHANNELS: TicketChannel[] = ['email', 'chat', 'sms', 'voice'];
export const ALL_VARIANTS: TicketVariant[] = ['light', 'medium', 'heavy'];

// ── Helpers ─────────────────────────────────────────────────────────

let ticketCounter = 1;
function generateTicketNumber(): string {
  const num = String(ticketCounter++).padStart(4, '0');
  return `TKT-${num}`;
}

/**
 * @deprecated Variant assignment now happens server-side in Node 2 of the
 * 8-node PARWA pipeline. This function is kept only for backwards
 * compatibility with existing tests; new code should NOT call it.
 */
export function autoAssignVariant(
  priority: TicketPriority,
  category: TicketCategory
): TicketVariant {
  if (priority === 'critical') return 'heavy';
  if (priority === 'high') return 'medium';
  if (
    category === 'fraud_security' ||
    category === 'vip_enterprise' ||
    category === 'complaints'
  ) {
    return 'medium';
  }
  return 'light';
}

export function computeStats(tickets: Ticket[]): TicketStats {
  const byStatus = {} as Record<TicketStatus, number>;
  const byCategory = {} as Record<TicketCategory, number>;
  const byPriority = {} as Record<TicketPriority, number>;
  const byVariant = {} as Record<TicketVariant, number>;
  const byChannel = {} as Record<TicketChannel, number>;

  ALL_STATUSES.forEach((s) => (byStatus[s] = 0));
  ALL_CATEGORIES.forEach((c) => (byCategory[c] = 0));
  ALL_PRIORITIES.forEach((p) => (byPriority[p] = 0));
  ALL_VARIANTS.forEach((v) => (byVariant[v] = 0));
  ALL_CHANNELS.forEach((ch) => (byChannel[ch] = 0));

  let resolved = 0;
  let totalResolutionTime = 0;
  let resolutionCount = 0;
  let totalCost = 0;
  let totalSavings = 0;

  for (const t of tickets) {
    byStatus[t.status]++;
    byCategory[t.category]++;
    byPriority[t.priority]++;
    byChannel[t.channel]++;
    if (t.assigned_variant) byVariant[t.assigned_variant]++;
    if (t.status === 'resolved' || t.status === 'closed') {
      resolved++;
      if (t.resolution_time_hours !== null) {
        totalResolutionTime += t.resolution_time_hours;
        resolutionCount++;
      }
    }
    if (t.cost_per_ticket !== null) totalCost += t.cost_per_ticket;
    if (t.savings_per_ticket !== null) totalSavings += t.savings_per_ticket;
  }

  const nonTerminal = tickets.filter(
    (t) => t.status !== 'resolved' && t.status !== 'closed'
  );
  const resolutionRate =
    tickets.length > 0
      ? Math.round((resolved / tickets.length) * 1000) / 10
      : 0;

  return {
    total: tickets.length,
    byStatus,
    byCategory,
    byPriority,
    byVariant,
    byChannel,
    resolved,
    resolutionRate,
    avgResolutionTime:
      resolutionCount > 0 ? Math.round(totalResolutionTime / resolutionCount * 10) / 10 : null,
    totalCost: Math.round(totalCost * 1000) / 1000,
    totalSavings: Math.round(totalSavings * 100) / 100,
  };
}

// ── Store ───────────────────────────────────────────────────────────

interface TicketState {
  tickets: Ticket[];
  initialized: boolean;
  agentStopped: boolean;  // Global agent stop flag

  // Actions
  init: () => void;
  addTicket: (data: Omit<Ticket, 'id' | 'ticket_number' | 'status' | 'assigned_variant' | 'assigned_agent' | 'created_at' | 'updated_at' | 'resolved_at' | 'first_response_at' | 'resolution_time_hours' | 'ai_confidence' | 'cost_per_ticket' | 'savings_per_ticket' | 'messages' | 'tags' | 'skipped' | 'agent_stopped' | 'kb_matched' | 'kb_article_id' | 'company_id'> & {
    // CRM-universal optional fields (forwarded to backend TicketCreate schema)
    customer_id?: string;        // existing customer ID — skips auto-create
    customer_phone?: string;     // used when auto-creating a Customer
    tags?: string[];             // free-form tags (refund, vip, etc.)
    metadata_json?: Record<string, unknown>;  // structured context (order_id, url, etc.)
    company_id?: string;         // company for filtering
  }) => Ticket;
  updateTicketStatus: (id: string, status: TicketStatus) => void;
  assignVariant: (id: string, variant: TicketVariant) => void;
  resolveTicket: (id: string, resolution?: string) => void;
  escalateToHuman: (id: string) => void;
  resumeWithGuidance: (id: string, guidance: string) => Promise<boolean>;
  updatePriority: (id: string, priority: TicketPriority) => void;
  addMessage: (ticketId: string, message: Omit<TicketMessage, 'id' | 'ticket_id' | 'created_at'>) => TicketMessage;
  
  // NEW: Agent control actions
  skipTicket: (id: string) => void;              // Mark ticket as "do not auto-solve"
  unskipTicket: (id: string) => void;            // Remove skip mark
  stopAllAgents: () => void;                     // Stop all agent processing
  resumeAllAgents: () => void;                   // Resume agent processing
  setKbMatched: (id: string, articleId: string) => void;  // Mark as KB-matched
  
  // Getters
  getTicketsByStatus: (status: TicketStatus) => Ticket[];
  getTicketsByCategory: (category: TicketCategory) => Ticket[];
  getTicketsByVariant: (variant: TicketVariant) => Ticket[];
  getTicket: (id: string) => Ticket | undefined;
  getTicketByNumber: (number: string) => Ticket | undefined;
  getAutoSolvableTickets: () => Ticket[];         // Tickets that can be auto-solved by KB
  getQueueTickets: (companyId?: string) => Ticket[];  // Tickets in process (company-filtered)
  getSkippedTickets: () => Ticket[];              // Tickets marked as skip

  // Computed
  ticketStats: () => TicketStats;
}

const STORAGE_KEY = 'parwa_tickets';
const INIT_KEY = 'parwa_tickets_initialized';

export const useTicketStore = create<TicketState>((set, get) => ({
  tickets: [],
  initialized: false,
  agentStopped: false,  // Global agent stop flag

  init: () => {
    if (get().initialized) return;
    if (typeof window === 'undefined') return;

    // ── KI-2 FIX (Week 3): Fetch from backend first, fall back to localStorage ──
    // Previously this ONLY read from localStorage, meaning tickets were always
    // local fake data. Now we kick off an async backend fetch; meanwhile we
    // synchronously hydrate from localStorage (if any) so the UI doesn't flash
    // empty. The async fetch will replace the data once it returns.
    try {
      const existing = localStorage.getItem(STORAGE_KEY);
      if (existing) {
        const parsed = JSON.parse(existing) as Ticket[];
        // Restore ticket counter to avoid collisions
        if (parsed.length > 0) {
          const maxNum = Math.max(
            ...parsed.map((t) =>
              parseInt(t.ticket_number.replace('TKT-', ''), 10)
            )
          );
          ticketCounter = maxNum + 1;
        }
        set({ tickets: parsed, initialized: true });
      } else {
        // No local data — mark initialized so loading state resolves
        set({ initialized: true });
      }
    } catch {
      set({ initialized: true });
    }

    // Fire-and-forget backend sync (non-blocking)
    void syncFromBackend();
  },

  addTicket: (data) => {
    // Backend is the source of truth — we NO LONGER do client-side variant
    // assignment, hardcoded ai_confidence, hardcoded cost_per_ticket, or
    // hardcoded savings_per_ticket. The 8-node pipeline runs on the
    // backend (Node 2 smart-routes the variant, Node 4 generates the
    // response, Node 6 quality-checks, Node 7 persists cost/savings) and
    // the next syncFromBackend() will populate all these fields from
    // real data.
    //
    // Until that sync completes, we show optimistic placeholders (null /
    // 'open' / no variant) so the user sees the ticket they just created.
    const now = new Date().toISOString();
    const optimisticId = uuid();
    const ticket: Ticket = {
      id: optimisticId,
      ticket_number: `TKT-PENDING`,
      subject: data.subject,
      description: data.description,
      category: data.category,
      priority: data.priority,
      status: 'open',
      channel: data.channel,
      customer_name: data.customer_name,
      customer_email: data.customer_email,
      company_id: data.company_id ?? null,
      assigned_variant: null,
      assigned_agent: null,
      created_at: now,
      updated_at: now,
      resolved_at: null,
      first_response_at: null,
      resolution_time_hours: null,
      ai_confidence: null,
      cost_per_ticket: null,
      savings_per_ticket: null,
      messages: [],
      tags: [],
      // New fields for agent control
      skipped: false,
      agent_stopped: false,
      kb_matched: false,
      kb_article_id: null,
    };
    set((s) => ({ tickets: [ticket, ...s.tickets] }));

    // Push to backend. The backend will:
    //   1. Auto-create a Customer (if customer_email is new) or match existing
    //   2. Store description as first TicketMessage (role=customer)
    //   3. Trigger the 8-node pipeline (sync for critical, async for others)
    //   4. Store AI response as TicketMessage (role=ai)
    //   5. Update ticket with status / variant / ai_confidence / cost
    // On success, we patch the optimistic ticket with the REAL backend ID
    // (so subsequent escalate/resolve calls use the correct ID) and re-sync
    // from backend to fetch the full real ticket (including AI response).
    void pushToBackendWithBody<{ id?: string }>('POST', '/api/v1/tickets', {
      subject: ticket.subject,
      description: ticket.description,
      category: ticket.category,
      priority: ticket.priority,
      channel: ticket.channel,
      customer_name: ticket.customer_name,
      customer_email: ticket.customer_email,
      // CRM-universal optional fields — only send when provided so the
      // backend's validators don't reject empty strings.
      ...(data.customer_id ? { customer_id: data.customer_id } : {}),
      ...(data.customer_phone ? { customer_phone: data.customer_phone } : {}),
      ...(data.tags && data.tags.length > 0 ? { tags: data.tags } : {}),
      ...(data.metadata_json && Object.keys(data.metadata_json).length > 0
        ? { metadata_json: data.metadata_json }
        : {}),
    }).then((responseBody) => {
      if (!responseBody) {
        // Ticket creation failed on the backend (likely trial expired or
        // trial ticket limit hit). Remove the optimistic ghost ticket so
        // the user doesn't see a ticket that doesn't actually exist.
        set((s) => ({ tickets: s.tickets.filter((t) => t.id !== optimisticId) }));
        return;
      }
      // Patch the optimistic ticket in-place with the real backend ID
      // so subsequent calls (escalate, resolve, update) use the persisted ID.
      const realId = responseBody.id;
      if (realId && realId !== optimisticId) {
        set((s) => ({
          tickets: s.tickets.map((t) =>
            t.id === optimisticId
              ? { ...t, id: realId, ticket_number: t.ticket_number === 'TKT-PENDING' ? 'TKT-…' : t.ticket_number }
              : t
          ),
        }));
      }
      void syncFromBackend();
    });
    return ticket;
  },

  updateTicketStatus: (id, status) => {
    set((s) => ({
      tickets: s.tickets.map((t) =>
        t.id === id ? { ...t, status, updated_at: new Date().toISOString() } : t
      ),
    }));
    void pushToBackend('PATCH', `/api/v1/tickets/${id}/status`, { status });
  },

  assignVariant: (id, variant) => {
    // Send the variant update to the backend. The backend's pipeline
    // will re-run with the new variant and update ai_confidence /
    // cost / savings. We do NOT compute these client-side anymore.
    set((s) => ({
      tickets: s.tickets.map((t) =>
        t.id === id
          ? {
              ...t,
              assigned_variant: variant,
              updated_at: new Date().toISOString(),
            }
          : t
      ),
    }));
    void pushToBackend('PUT', `/api/v1/tickets/${id}`, { assigned_variant: variant })
      .then((ok) => { if (ok) void syncFromBackend(); });
  },

  resolveTicket: (id, resolution) => {
    const now = new Date().toISOString();
    set((s) => ({
      tickets: s.tickets.map((t) => {
        if (t.id !== id) return t;
        const created = new Date(t.created_at).getTime();
        const resolved = new Date(now).getTime();
        const hours = Math.round(((resolved - created) / 3600000) * 10) / 10;
        const msgs: TicketMessage[] = [
          ...t.messages,
          {
            id: uuid(),
            ticket_id: id,
            sender: 'ai_agent',
            sender_name: 'PARWA AI',
            content: resolution
              ? `Issue resolved: ${resolution}`
              : 'This ticket has been marked as resolved. Please let us know if you need further assistance.',
            created_at: now,
            variant: t.assigned_variant || undefined,
          },
        ];
        return {
          ...t,
          status: 'resolved' as TicketStatus,
          resolved_at: now,
          updated_at: now,
          resolution_time_hours: hours,
          messages: msgs,
        };
      }),
    }));
    void pushToBackend('PATCH', `/api/v1/tickets/${id}/status`, { status: 'resolved', resolution });
  },

  escalateToHuman: (id) => {
    const now = new Date().toISOString();
    set((s) => ({
      tickets: s.tickets.map((t) => {
        if (t.id !== id) return t;
        const msgs: TicketMessage[] = [
          ...t.messages,
          {
            id: uuid(),
            ticket_id: id,
            sender: 'system',
            sender_name: 'System',
            content:
              'Ticket has been escalated to a human agent. A team member will be with you shortly.',
            created_at: now,
          },
        ];
        return {
          ...t,
          status: 'awaiting_human' as TicketStatus,
          assigned_agent: 'Human Agent',
          updated_at: now,
          messages: msgs,
        };
      }),
    }));
    void pushToBackend('POST', `/api/v1/tickets/${id}/escalate`, {});
  },

  resumeWithGuidance: async (id, guidance) => {
    // Approach A: Resume a paused pipeline with human/variant guidance.
    // Calls POST /api/v1/tickets/{id}/resume which loads the LangGraph
    // checkpoint and resumes from the exact node that paused.
    try {
      const res = await fetch(`/api/v1/tickets/${id}/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ guidance }),
      });
      if (res.ok) {
        const data = await res.json();
        // Update ticket status based on resume result
        set((s) => ({
          tickets: s.tickets.map((t) =>
            t.id === id
              ? {
                  ...t,
                  status: (data.status === 'resolved' ? 'resolved' : 'awaiting_human') as TicketStatus,
                  updated_at: new Date().toISOString(),
                }
              : t
          ),
        }));
        // Sync from backend to get the latest AI response
        void syncFromBackend();
        return true;
      }
    } catch {
      // Network error
    }
    return false;
  },

  updatePriority: (id, priority) => {
    // Update priority on backend. Variant assignment happens server-side
    // via Node 2 smart-routing — we don't auto-assign a variant client-side.
    set((s) => ({
      tickets: s.tickets.map((t) =>
        t.id === id
          ? {
              ...t,
              priority,
              updated_at: new Date().toISOString(),
            }
          : t
      ),
    }));
    void pushToBackend('PUT', `/api/v1/tickets/${id}`, { priority })
      .then((ok) => { if (ok) void syncFromBackend(); });
  },

  addMessage: (ticketId, message) => {
    const msg: TicketMessage = {
      ...message,
      id: uuid(),
      ticket_id: ticketId,
      created_at: new Date().toISOString(),
    };
    set((s) => ({
      tickets: s.tickets.map((t) =>
        t.id === ticketId
          ? {
              ...t,
              messages: [...t.messages, msg],
              first_response_at:
                t.first_response_at ?? msg.created_at,
              updated_at: new Date().toISOString(),
              status:
                t.status === 'open' ? ('in_progress' as TicketStatus) : t.status,
            }
          : t
      ),
    }));
    void pushToBackend('POST', `/api/v1/tickets/${ticketId}/messages`, {
      // Backend MessageCreate schema expects: role, content, channel
      // Map frontend sender → backend role (human_agent → agent, ai_agent → ai)
      role: msg.sender === 'human_agent' ? 'agent' : msg.sender === 'ai_agent' ? 'ai' : msg.sender,
      content: msg.content,
      channel: 'email',
      metadata_json: { sender_name: msg.sender_name },
    });
    return msg;
  },

  getTicketsByStatus: (status) => get().tickets.filter((t) => t.status === status),
  getTicketsByCategory: (category) =>
    get().tickets.filter((t) => t.category === category),
  getTicketsByVariant: (variant) =>
    get().tickets.filter((t) => t.assigned_variant === variant),
  getTicket: (id) => get().tickets.find((t) => t.id === id),
  getTicketByNumber: (number) =>
    get().tickets.find((t) => t.ticket_number === number),

  // ── NEW: Agent Control Actions ──────────────────────────────────────
  
  /**
   * Mark a ticket as "skipped" — PARWA will NOT auto-solve this ticket.
   * User can still manually resolve or escalate it.
   */
  skipTicket: (id) => {
    set((s) => ({
      tickets: s.tickets.map((t) =>
        t.id === id ? { ...t, skipped: true, updated_at: new Date().toISOString() } : t
      ),
    }));
    toast.success('Ticket marked as skipped — AI will not auto-solve');
    void pushToBackend('PATCH', `/api/v1/tickets/${id}/status`, { status: 'skipped' });
  },

  /**
   * Remove skip mark — PARWA can now auto-solve this ticket again.
   */
  unskipTicket: (id) => {
    set((s) => ({
      tickets: s.tickets.map((t) =>
        t.id === id ? { ...t, skipped: false, updated_at: new Date().toISOString() } : t
      ),
    }));
    toast.success('Ticket unskipped — AI can now process');
  },

  /**
   * Stop ALL agent processing globally. New tickets won't be auto-processed
   * until resumeAllAgents() is called.
   */
  stopAllAgents: () => {
    set({ agentStopped: true });
    // Also mark all in-progress tickets as stopped
    set((s) => ({
      tickets: s.tickets.map((t) =>
        t.status === 'open' || t.status === 'in_progress'
          ? { ...t, agent_stopped: true, updated_at: new Date().toISOString() }
          : t
      ),
    }));
    toast.success('All agents stopped — processing halted');
  },

  /**
   * Resume all agent processing. Tickets can be processed again.
   */
  resumeAllAgents: () => {
    set({ agentStopped: false });
    // Clear stop flags on tickets
    set((s) => ({
      tickets: s.tickets.map((t) =>
        t.agent_stopped ? { ...t, agent_stopped: false, updated_at: new Date().toISOString() } : t
      ),
    }));
    toast.success('Agents resumed — processing active');
  },

  /**
   * Mark a ticket as matched to a KB article (auto-solvable).
   * Called when Node 2/Node 3 finds a KB match.
   */
  setKbMatched: (id, articleId) => {
    set((s) => ({
      tickets: s.tickets.map((t) =>
        t.id === id
          ? { ...t, kb_matched: true, kb_article_id: articleId, updated_at: new Date().toISOString() }
          : t
      ),
    }));
  },

  // ── NEW: Computed Getters for UI Sections ───────────────────────────

  /**
   * Get tickets that PARWA can auto-solve via KB matching.
   * These are: open/in_progress + not skipped + not stopped + KB matched OR simple categories.
   */
  getAutoSolvableTickets: () => {
    const { tickets } = get();
    return tickets.filter((t) => {
      if (t.skipped || t.agent_stopped) return false;
      if (t.status === 'resolved' || t.status === 'closed') return false;
      // Auto-solvable if KB-matched OR if it's a "simple" category with high confidence
      const simpleCategories: TicketCategory[] = [
        'billing_payments', 'order_management', 'account_management',
        'shipping_delivery', 'product_information'
      ];
      return t.kb_matched || (simpleCategories.includes(t.category) && t.priority !== 'critical');
    });
  },

  /**
   * Get tickets currently in queue (being processed or waiting).
   * Filtered by company_id if provided.
   */
  getQueueTickets: (companyId?: string) => {
    const { tickets } = get();
    return tickets.filter((t) => {
      // Only non-terminal statuses
      if (t.status === 'resolved' || t.status === 'closed') return false;
      // Filter by company if specified
      if (companyId && t.company_id !== companyId) return false;
      return true;
    });
  },

  /**
   * Get all tickets marked as skipped.
   */
  getSkippedTickets: () => {
    return get().tickets.filter((t) => t.skipped);
  },

  ticketStats: () => computeStats(get().tickets),
}));

// ── Seed Data ───────────────────────────────────────────────────────

// ── KI-2 FIX (Week 3): Backend sync ──────────────────────────────────────────
// Fetches real tickets from the backend via the BFF proxy at /api/tickets.
// Maps the backend TicketResponse shape → frontend Ticket shape.
// On success, replaces the store + persists to localStorage (so the next page
// load is instant from cache, then re-synced). On failure, leaves existing
// data intact (graceful degradation).
//
// Backend response shape (see backend/app/schemas/ticket.py):
//   { items: TicketResponse[], total: number, page: number, page_size: number }
//
// TicketResponse has snake_case fields (ticket_number, customer_name, etc.);
// the frontend Ticket interface also uses snake_case, so most fields pass
// through directly. We only need to normalize a few fields that the backend
// may omit (messages, tags) or name differently.

interface BackendTicketResponse {
  id: string;
  ticket_number: string;
  subject: string;
  description?: string;
  category: string;
  priority: string;
  status: string;
  channel: string;
  customer_name: string;
  customer_email?: string;
  company_id?: string | null;
  assigned_variant?: string | null;
  assigned_agent?: string | null;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
  first_response_at?: string | null;
  resolution_time_hours?: number | null;
  ai_confidence?: number | null;
  cost_per_ticket?: number | null;
  savings_per_ticket?: number | null;
  tags?: string[];
  // New fields from backend
  skipped?: boolean;
  agent_stopped?: boolean;
  kb_matched?: boolean;
  kb_article_id?: string | null;
}

function normalizeBackendTicket(raw: BackendTicketResponse): Ticket {
  // Validate enum fields; fall back to safe defaults if backend sends unknown values
  const validCategories: TicketCategory[] = ALL_CATEGORIES;
  const validPriorities: TicketPriority[] = ALL_PRIORITIES;
  const validStatuses: TicketStatus[] = ALL_STATUSES;
  const validChannels: TicketChannel[] = ALL_CHANNELS;
  const validVariants: TicketVariant[] = ALL_VARIANTS;

  const category = (validCategories as string[]).includes(raw.category)
    ? (raw.category as TicketCategory)
    : 'technical_support';
  const priority = (validPriorities as string[]).includes(raw.priority)
    ? (raw.priority as TicketPriority)
    : 'medium';
  const status = (validStatuses as string[]).includes(raw.status)
    ? (raw.status as TicketStatus)
    : 'open';
  const channel = (validChannels as string[]).includes(raw.channel)
    ? (raw.channel as TicketChannel)
    : 'email';

  // Map backend variant names → frontend variant names
  // Backend uses 'mini' / 'parwa' / 'high'; frontend uses 'light' / 'medium' / 'heavy'
  let assigned_variant: TicketVariant | null = null;
  if (raw.assigned_variant) {
    const v = raw.assigned_variant.toLowerCase();
    if (v === 'mini' || v === 'light') assigned_variant = 'light';
    else if (v === 'parwa' || v === 'medium') assigned_variant = 'medium';
    else if (v === 'high' || v === 'heavy') assigned_variant = 'heavy';
    else if ((validVariants as string[]).includes(raw.assigned_variant)) {
      assigned_variant = raw.assigned_variant as TicketVariant;
    }
  }

  return {
    id: raw.id,
    ticket_number: raw.ticket_number,
    subject: raw.subject,
    description: raw.description ?? '',
    category,
    priority,
    status,
    channel,
    customer_name: raw.customer_name,
    customer_email: raw.customer_email ?? '',
    company_id: raw.company_id ?? null,
    assigned_variant,
    assigned_agent: raw.assigned_agent ?? null,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    resolved_at: raw.resolved_at ?? null,
    first_response_at: raw.first_response_at ?? null,
    resolution_time_hours: raw.resolution_time_hours ?? null,
    ai_confidence: raw.ai_confidence ?? null,
    cost_per_ticket: raw.cost_per_ticket ?? null,
    savings_per_ticket: raw.savings_per_ticket ?? null,
    messages: [],  // Backend doesn't return messages in list view; fetch on detail view
    tags: raw.tags ?? [],
    // New fields for agent control
    skipped: raw.skipped ?? false,
    agent_stopped: raw.agent_stopped ?? false,
    kb_matched: raw.kb_matched ?? false,
    kb_article_id: raw.kb_article_id ?? null,
  };
}

export async function syncFromBackend(): Promise<void> {
  if (typeof window === 'undefined') return;
  try {
    const res = await fetch('/api/tickets?page=1&page_size=100', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });

    if (!res.ok) {
      // 401 = not authenticated; 5xx = backend down. Either way, leave existing data.
      return;
    }

    const data = await res.json();
    const items: BackendTicketResponse[] = Array.isArray(data?.items) ? data.items : [];

    const normalized: Ticket[] = items.map(normalizeBackendTicket);

    // Update store
    useTicketStore.setState({ tickets: normalized, initialized: true });

    // Persist to localStorage so next page load is instant from cache
    localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    localStorage.setItem(INIT_KEY, 'true');

    // Restore ticket counter
    if (normalized.length > 0) {
      const maxNum = Math.max(
        ...normalized.map((t) =>
          parseInt(t.ticket_number.replace('TKT-', ''), 10) || 0
        )
      );
      if (!Number.isNaN(maxNum)) ticketCounter = maxNum + 1;
    }
  } catch (err) {
    // Network error / JSON parse error — leave existing data intact
    console.warn('[ticket-store] syncFromBackend failed:', err);
  }
}

/**
 * Fetch messages for a single ticket from /api/v1/tickets/{id}/messages
 * and merge them into the store. Used by the ticket detail panel so the
 * user sees the AI/customer conversation thread instead of "No messages yet".
 *
 * The list endpoint does not return messages, so we fetch them on demand
 * when the user opens a ticket.
 */
export async function fetchTicketMessages(ticketId: string): Promise<void> {
  if (typeof window === 'undefined') return;
  try {
    const res = await fetch(`/api/v1/tickets/${ticketId}/messages`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
    if (!res.ok) return;
    const data = await res.json();
    const rawMsgs: Array<Record<string, unknown>> =
      Array.isArray(data?.messages) ? data.messages : (Array.isArray(data) ? data : []);
    const msgs: TicketMessage[] = rawMsgs.map((m) => {
      const role = String(m.role ?? m.sender ?? 'system');
      // Backend uses role=ai|customer|human_agent|system; map to MessageSender
      const sender = (
        role === 'ai' ? 'ai_agent' :
        role === 'customer' ? 'customer' :
        role === 'human_agent' ? 'human_agent' :
        'system'
      ) as MessageSender;
      return {
        id: String(m.id ?? ''),
        ticket_id: String(m.ticket_id ?? ticketId),
        sender,
        sender_name: String(m.sender_name ?? (sender === 'ai_agent' ? 'AI' : sender === 'customer' ? 'Customer' : 'Agent')),
        content: String(m.content ?? ''),
        created_at: String(m.created_at ?? new Date().toISOString()),
        variant: (m.variant_version as TicketVariant | undefined) ?? undefined,
      };
    });
    // Merge into the selected ticket in the store
    const { tickets } = useTicketStore.getState();
    const updated = tickets.map((t) =>
      t.id === ticketId ? { ...t, messages: msgs } : t,
    );
    useTicketStore.setState({ tickets: updated });
  } catch (err) {
    console.warn(`[ticket-store] fetchTicketMessages ${ticketId} failed:`, err);
  }
}

/**
 * Push a mutation to the backend (fire-and-forget).
 * Used by addTicket / updateTicketStatus / assignVariant / resolveTicket /
 * escalateToHuman / updatePriority / addMessage so the backend is the source
 * of truth (CLAUDE.md #2 fix). Returns true on success, false on failure;
 * failures are logged but do not roll back the optimistic local update —
 * the next syncFromBackend() call will reconcile.
 */
async function pushToBackend(method: string, path: string, body?: unknown): Promise<boolean> {
  if (typeof window === 'undefined') return false;
  try {
    const res = await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      console.warn(`[ticket-store] pushToBackend ${method} ${path} failed:`, res.status);
      return false;
    }
    return true;
  } catch (err) {
    console.warn(`[ticket-store] pushToBackend ${method} ${path} network error:`, err);
    return false;
  }
}

/**
 * Push a mutation to the backend and return the parsed JSON response body.
 * Used by addTicket to capture the real ticket ID returned by the backend
 * (avoids the optimistic-UUID leak where escalate/resolve calls hit the
 * backend with a local UUID instead of the real persisted ticket ID).
 *
 * Returns the parsed response body on success, or null on failure.
 */
async function pushToBackendWithBody<T = unknown>(method: string, path: string, body?: unknown): Promise<T | null> {
  if (typeof window === 'undefined') return null;
  try {
    const res = await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      console.warn(`[ticket-store] pushToBackendWithBody ${method} ${path} failed:`, res.status);
      return null;
    }
    return (await res.json()) as T;
  } catch (err) {
    console.warn(`[ticket-store] pushToBackendWithBody ${method} ${path} network error:`, err);
    return null;
  }
}
