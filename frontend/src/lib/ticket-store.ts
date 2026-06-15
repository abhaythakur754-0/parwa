'use client';

import { create } from 'zustand';
import { v4 as uuid } from 'uuid';

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

function autoAssignVariant(
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

function computeStats(tickets: Ticket[]): TicketStats {
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

  // Actions
  init: () => void;
  addTicket: (data: Omit<Ticket, 'id' | 'ticket_number' | 'status' | 'assigned_variant' | 'assigned_agent' | 'created_at' | 'updated_at' | 'resolved_at' | 'first_response_at' | 'resolution_time_hours' | 'ai_confidence' | 'cost_per_ticket' | 'savings_per_ticket' | 'messages' | 'tags'>) => Ticket;
  updateTicketStatus: (id: string, status: TicketStatus) => void;
  assignVariant: (id: string, variant: TicketVariant) => void;
  resolveTicket: (id: string, resolution?: string) => void;
  escalateToHuman: (id: string) => void;
  updatePriority: (id: string, priority: TicketPriority) => void;
  addMessage: (ticketId: string, message: Omit<TicketMessage, 'id' | 'ticket_id' | 'created_at'>) => TicketMessage;
  getTicketsByStatus: (status: TicketStatus) => Ticket[];
  getTicketsByCategory: (category: TicketCategory) => Ticket[];
  getTicketsByVariant: (variant: TicketVariant) => Ticket[];
  getTicket: (id: string) => Ticket | undefined;
  getTicketByNumber: (number: string) => Ticket | undefined;

  // Computed
  ticketStats: () => TicketStats;
}

const STORAGE_KEY = 'parwa_tickets';
const INIT_KEY = 'parwa_tickets_initialized';

export const useTicketStore = create<TicketState>((set, get) => ({
  tickets: [],
  initialized: false,

  init: () => {
    if (get().initialized) return;
    if (typeof window === 'undefined') return;

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
      }
    } catch {
      // ignore
    }
  },

  addTicket: (data) => {
    const variant = autoAssignVariant(data.priority, data.category);
    const now = new Date().toISOString();
    const ticket: Ticket = {
      id: uuid(),
      ticket_number: generateTicketNumber(),
      subject: data.subject,
      description: data.description,
      category: data.category,
      priority: data.priority,
      status: 'open',
      channel: data.channel,
      customer_name: data.customer_name,
      customer_email: data.customer_email,
      assigned_variant: variant,
      assigned_agent: null,
      created_at: now,
      updated_at: now,
      resolved_at: null,
      first_response_at: null,
      resolution_time_hours: null,
      ai_confidence: variant === 'light' ? 95.2 : variant === 'medium' ? 89.7 : 93.1,
      cost_per_ticket: VARIANT_COST[variant],
      savings_per_ticket: 12.5 - VARIANT_COST[variant],
      messages: [],
      tags: [],
    };
    set((s) => {
      const tickets = [ticket, ...s.tickets];
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets));
      }
      return { tickets };
    });
    return ticket;
  },

  updateTicketStatus: (id, status) => {
    set((s) => {
      const tickets = s.tickets.map((t) =>
        t.id === id
          ? { ...t, status, updated_at: new Date().toISOString() }
          : t
      );
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets));
      }
      return { tickets };
    });
  },

  assignVariant: (id, variant) => {
    set((s) => {
      const tickets = s.tickets.map((t) =>
        t.id === id
          ? {
              ...t,
              assigned_variant: variant,
              cost_per_ticket: VARIANT_COST[variant],
              savings_per_ticket: 12.5 - VARIANT_COST[variant],
              ai_confidence:
                variant === 'light' ? 95.2 : variant === 'medium' ? 89.7 : 93.1,
              updated_at: new Date().toISOString(),
            }
          : t
      );
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets));
      }
      return { tickets };
    });
  },

  resolveTicket: (id, resolution) => {
    const now = new Date().toISOString();
    set((s) => {
      const tickets = s.tickets.map((t) => {
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
      });
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets));
      }
      return { tickets };
    });
  },

  escalateToHuman: (id) => {
    const now = new Date().toISOString();
    set((s) => {
      const tickets = s.tickets.map((t) => {
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
      });
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets));
      }
      return { tickets };
    });
  },

  updatePriority: (id, priority) => {
    const newVariant = autoAssignVariant(priority, get().tickets.find((t) => t.id === id)?.category ?? 'product_information');
    set((s) => {
      const tickets = s.tickets.map((t) =>
        t.id === id
          ? {
              ...t,
              priority,
              assigned_variant: newVariant,
              cost_per_ticket: VARIANT_COST[newVariant],
              savings_per_ticket: 12.5 - VARIANT_COST[newVariant],
              updated_at: new Date().toISOString(),
            }
          : t
      );
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets));
      }
      return { tickets };
    });
  },

  addMessage: (ticketId, message) => {
    const msg: TicketMessage = {
      ...message,
      id: uuid(),
      ticket_id: ticketId,
      created_at: new Date().toISOString(),
    };
    set((s) => {
      const tickets = s.tickets.map((t) =>
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
      );
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets));
      }
      return { tickets };
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

  ticketStats: () => computeStats(get().tickets),
}));
