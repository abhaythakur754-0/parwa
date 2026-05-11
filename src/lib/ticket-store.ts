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

// ── Seed Data ───────────────────────────────────────────────────────

function daysAgo(d: number): string {
  return new Date(Date.now() - d * 86400000).toISOString();
}

function hoursAgo(h: number): string {
  return new Date(Date.now() - h * 3600000).toISOString();
}

export function seedTickets(): Ticket[] {
  const HUMAN_COST = 12.5;
  const tickets: Ticket[] = [];

  function makeTicket(opts: {
    ticket_number: string;
    subject: string;
    description: string;
    category: TicketCategory;
    priority: TicketPriority;
    channel: TicketChannel;
    customer_name: string;
    customer_email: string;
    status?: TicketStatus;
    createdOffset: number; // hours ago
    resolvedOffset?: number; // hours ago
    customerMessages: string[];
    aiResponse?: string;
    aiResponseOffset?: number; // minutes after first message
    tags?: string[];
  }): Ticket {
    const variant = autoAssignVariant(opts.priority, opts.category);
    const created = hoursAgo(opts.createdOffset);
    const resolved =
      opts.status === 'resolved' || opts.status === 'closed'
        ? opts.resolvedOffset
          ? hoursAgo(opts.resolvedOffset)
          : hoursAgo(opts.createdOffset * 0.4)
        : null;
    const resolutionTime =
      resolved && opts.status !== 'open' && opts.status !== 'in_progress'
        ? Math.round(
            ((new Date(resolved).getTime() - new Date(created).getTime()) /
              3600000) *
              10
          ) / 10
        : null;
    const aiConfidence =
      variant === 'light' ? 95.2 : variant === 'medium' ? 89.7 : 93.1;

    const messages: TicketMessage[] = [];
    opts.customerMessages.forEach((content, i) => {
      messages.push({
        id: uuid(),
        ticket_id: '',
        sender: 'customer',
        sender_name: opts.customer_name,
        content,
        created_at: hoursAgo(
          opts.createdOffset - (opts.customerMessages.length - 1 - i) * 0.5
        ),
      });
    });

    if (opts.aiResponse && opts.status !== 'open') {
      messages.push({
        id: uuid(),
        ticket_id: '',
        sender: 'ai_agent',
        sender_name: 'PARWA AI',
        content: opts.aiResponse,
        created_at: hoursAgo(
          opts.createdOffset - (opts.aiResponseOffset ?? 1) / 60
        ),
        variant,
      });
    }

    return {
      id: uuid(),
      ticket_number: opts.ticket_number,
      subject: opts.subject,
      description: opts.description,
      category: opts.category,
      priority: opts.priority,
      status: opts.status ?? 'open',
      channel: opts.channel,
      customer_name: opts.customer_name,
      customer_email: opts.customer_email,
      assigned_variant: variant,
      assigned_agent: null,
      created_at: created,
      updated_at: resolved ?? created,
      resolved_at: resolved,
      first_response_at: messages.length > 1 ? messages[messages.length - 1].created_at : null,
      resolution_time_hours: resolutionTime,
      ai_confidence: aiConfidence,
      cost_per_ticket: VARIANT_COST[variant],
      savings_per_ticket: Math.round((HUMAN_COST - VARIANT_COST[variant]) * 100) / 100,
      messages,
      tags: opts.tags ?? [],
    };
  }

  // ── Billing & Payments ──
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0001',
      subject: 'Refund request for duplicate charge of $149.99',
      description: 'I was charged twice for my monthly subscription on January 15th. I can see two identical charges of $149.99 on my credit card statement. Please refund the duplicate charge immediately.',
      category: 'billing_payments',
      priority: 'high',
      channel: 'email',
      customer_name: 'Sarah Mitchell',
      customer_email: 'sarah.mitchell@email.com',
      status: 'in_progress',
      createdOffset: 4,
      customerMessages: [
        'Hi, I noticed I was charged twice for my monthly subscription on January 15th. Two identical charges of $149.99 appeared on my credit card statement. Can you please look into this and refund the duplicate charge? I have the transaction IDs if needed.',
      ],
      aiResponse:
        "Hello Sarah, thank you for reaching out. I've located the duplicate charge on your account. I can confirm there were two charges of $149.99 on January 15th. I'm initiating a refund for the duplicate charge of $149.99 right away. You should see the refund on your statement within 3-5 business days. Is there anything else I can help you with?",
      aiResponseOffset: 2,
      tags: ['refund', 'duplicate-charge', 'urgent'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0002',
      subject: 'Upgrade from Basic to Premium plan',
      description: 'I would like to upgrade my subscription from the Basic plan to the Premium plan. I want to take advantage of the additional features and higher usage limits.',
      category: 'billing_payments',
      priority: 'medium',
      channel: 'chat',
      customer_name: 'James Rodriguez',
      customer_email: 'james.rodriguez@email.com',
      status: 'resolved',
      createdOffset: 24,
      resolvedOffset: 2,
      customerMessages: [
        "Hey! I'm currently on the Basic plan but I'd like to upgrade to Premium. How do I do that, and will it be prorated for the remainder of my billing cycle?",
      ],
      aiResponse:
        "Great choice, James! I've upgraded your account from Basic to Premium effective immediately. The cost will be prorated for the remainder of your current billing cycle — you'll only pay the difference for the remaining days. Your new plan includes 10x the API calls, priority support, and advanced analytics. The change is already reflected in your account settings. Welcome to Premium! 🎉",
      aiResponseOffset: 1,
      tags: ['upgrade', 'subscription'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0003',
      subject: 'Cancel annual subscription - moving to competitor',
      description: 'I want to cancel my annual subscription immediately. I am moving to a competitor that offers better pricing and features for my needs.',
      category: 'billing_payments',
      priority: 'critical',
      channel: 'voice',
      customer_name: 'Priya Sharma',
      customer_email: 'priya.sharma@email.com',
      status: 'awaiting_human',
      createdOffset: 1,
      customerMessages: [
        "I've been a customer for 2 years but I need to cancel. The competitor offers better pricing and I've already migrated my data. Please process the cancellation and refund for the remaining months.",
        "Also, I want to make sure all my data is completely deleted from your systems per GDPR requirements.",
      ],
      aiResponse:
        "Priya, I understand you'd like to cancel your subscription. Before I process this, I'd like to mention that we have a loyalty discount program that could save you 25% on your annual plan. Would you be open to hearing about it? If you still wish to proceed with cancellation, I'll need to connect you with a human agent to handle the data deletion request and process any applicable refund. One moment please.",
      aiResponseOffset: 1,
      tags: ['cancel', 'churn-risk', 'gdpr', 'retention'],
    })
  );

  // ── Order Management ──
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0004',
      subject: 'Where is my order #ORD-78432?',
      description: 'I placed an order 5 days ago and have not received any shipping confirmation. Order number is #ORD-78432.',
      category: 'order_management',
      priority: 'medium',
      channel: 'sms',
      customer_name: 'Mike Chen',
      customer_email: 'mike.chen@email.com',
      status: 'in_progress',
      createdOffset: 6,
      customerMessages: [
        "Hi, I ordered 5 days ago and haven't received any shipping confirmation. My order number is #ORD-78432. Can you tell me the status?",
      ],
      aiResponse:
        "Hi Mike, I've checked your order #ORD-78432 and it's currently being processed at our warehouse. It was delayed slightly due to a high volume of orders. It's scheduled to ship today and you should receive a tracking number within the next few hours. Expected delivery is within 2-3 business days. I apologize for the delay!",
      aiResponseOffset: 3,
      tags: ['order-status', 'delayed-shipping'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0005',
      subject: 'Need to modify shipping address for order #ORD-91234',
      description: 'I just realized I entered the wrong shipping address for order #ORD-91234. The order hasn\'t shipped yet. Need to change to my new address.',
      category: 'order_management',
      priority: 'high',
      channel: 'email',
      customer_name: 'Emma Watson',
      customer_email: 'emma.watson@email.com',
      status: 'resolved',
      createdOffset: 12,
      resolvedOffset: 1,
      customerMessages: [
        'Hello, I just placed order #ORD-91234 but I entered the wrong shipping address. I recently moved and my old address was pre-filled. The correct address is 456 Oak Avenue, Apt 3B, Portland, OR 97201. The order has not shipped yet. Can you update it?',
      ],
      aiResponse:
        "Hi Emma, I've successfully updated the shipping address for order #ORD-91234 to your new address at 456 Oak Avenue, Apt 3B, Portland, OR 97201. The change has been confirmed in our system. You'll receive a shipping confirmation with tracking information once the order ships. Is there anything else I can help with?",
      aiResponseOffset: 2,
      tags: ['address-change', 'order-modification'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0006',
      subject: 'Order #ORD-67890 arrived damaged - requesting replacement',
      description: 'My order arrived today but the product is damaged. The box was crushed and the item inside is broken. I need a replacement sent ASAP.',
      category: 'order_management',
      priority: 'high',
      channel: 'chat',
      customer_name: 'David Park',
      customer_email: 'david.park@email.com',
      status: 'in_progress',
      createdOffset: 3,
      customerMessages: [
        "My order #ORD-67890 just arrived and it's completely damaged. The box was crushed in transit and the product inside is broken. This is really frustrating. I need a replacement sent as soon as possible.",
      ],
      aiResponse:
        "I'm really sorry about that, David. That's definitely not the experience we want you to have. I've flagged this for an immediate replacement. Here's what I'm doing: 1) Creating a replacement order that will ship via express delivery (2-day), 2) Generating a prepaid return label for the damaged item, and 3) Adding a 15% credit to your account for the inconvenience. You'll receive the tracking info for the replacement within 24 hours. Could you upload a photo of the damage so we can file a carrier claim?",
      aiResponseOffset: 1,
      tags: ['damaged', 'replacement', 'compensation'],
    })
  );

  // ── Account Management ──
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0007',
      subject: "Can't reset password - not receiving reset email",
      description: "I've tried to reset my password multiple times but I never receive the reset email. I've checked my spam folder and it's not there either.",
      category: 'account_management',
      priority: 'medium',
      channel: 'email',
      customer_name: 'Lisa Thompson',
      customer_email: 'lisa.thompson@email.com',
      status: 'resolved',
      createdOffset: 18,
      resolvedOffset: 3,
      customerMessages: [
        "I've been trying to reset my password for the past hour. I've requested the reset email 5 times but nothing comes through. I've checked my spam/junk folder and even added your domain to my safe senders list. Please help me regain access to my account.",
      ],
      aiResponse:
        "Hi Lisa, I found the issue! Your email provider has a strict DMARC policy that was filtering out our password reset emails. I've added a manual reset token that's valid for 24 hours. Please go to [reset link] and enter this code: LISA-2024-RESET. Alternatively, I've also sent the reset email through our backup email service — check your inbox now. If you still don't see it within 5 minutes, please let me know and I can reset it directly.",
      aiResponseOffset: 2,
      tags: ['password-reset', 'email-issues'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0008',
      subject: 'Update company name from TechCorp to TechCorp Solutions',
      description: 'Our company recently rebranded from TechCorp to TechCorp Solutions. We need to update our company name across all our invoices, communications, and account settings.',
      category: 'account_management',
      priority: 'low',
      channel: 'chat',
      customer_name: 'Robert Kim',
      customer_email: 'robert.kim@techcorp.com',
      status: 'resolved',
      createdOffset: 48,
      resolvedOffset: 6,
      customerMessages: [
        "We rebranded recently and need our company name updated from 'TechCorp' to 'TechCorp Solutions' everywhere — invoices, emails, dashboard, etc. Is this something you can help with?",
      ],
      aiResponse:
        "Hi Robert, congratulations on the rebrand! I've updated your company name across all our systems: account settings, billing profile, email templates, and invoice generation. The changes are effective immediately. Future invoices will show 'TechCorp Solutions' and all email communications will reflect the new name. You may need to log out and log back in to see the updated name in your dashboard. Is there anything else you need updated?",
      aiResponseOffset: 5,
      tags: ['rebrand', 'company-update'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0009',
      subject: 'Request to delete my account and all associated data',
      description: 'Under GDPR and CCPA, I am requesting complete deletion of my account and all associated data from your systems.',
      category: 'account_management',
      priority: 'high',
      channel: 'email',
      customer_name: 'Ana Garcia',
      customer_email: 'ana.garcia@email.com',
      status: 'awaiting_human',
      createdOffset: 2,
      customerMessages: [
        'I am formally requesting deletion of my account and all associated personal data under my rights under GDPR Article 17 (Right to Erasure) and CCPA. Please confirm receipt and provide a timeline for complete data deletion. I expect all data to be removed from your production systems, backups, and any third-party services within 30 days.',
      ],
      aiResponse:
        "Hello Ana, I've received your data deletion request. Under GDPR/CCPA regulations, I'm escalating this to our Data Protection Officer and legal team for processing. A human agent will contact you within 24 hours with: 1) Confirmation of all data categories associated with your account, 2) A detailed deletion timeline, and 3) Any required verification steps. Please note that some data may be retained for legal compliance purposes even after deletion. Your request reference number is GDPR-2024-00847.",
      aiResponseOffset: 2,
      tags: ['gdpr', 'account-deletion', 'data-privacy', 'legal'],
    })
  );

  // ── Technical Support ──
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0010',
      subject: 'API integration returning 500 errors since update',
      description: 'After the latest API update, all our integration endpoints are returning 500 errors. This is blocking our entire production workflow.',
      category: 'technical_support',
      priority: 'critical',
      channel: 'email',
      customer_name: 'Alex Turner',
      customer_email: 'alex.turner@techstartup.io',
      status: 'awaiting_human',
      createdOffset: 0.5,
      customerMessages: [
        'URGENT: Since the API update deployed 30 minutes ago, all our integration endpoints return 500 Internal Server Error. This is completely blocking our production workflow. We have 50k users affected. Error logs show: {"error": "internal_server_error", "message": "Unexpected null reference in response serializer", "endpoint": "/v2/tickets/batch"}. We need an immediate rollback or hotfix.',
      ],
      aiResponse:
        "Alex, I've identified the issue — it's a null reference bug in the response serializer for the /v2/tickets/batch endpoint introduced in the latest deployment. This is affecting all batch operations. I'm immediately escalating this to our engineering team as a P0 incident. Estimated time to hotfix: 30-60 minutes. A human engineer will reach out to you directly with updates. In the meantime, you can use the /v1/tickets endpoints as a temporary workaround (they use a different serializer). Incident ID: INC-2024-0192.",
      aiResponseOffset: 1,
      tags: ['api', 'outage', 'p0-incident', 'production'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0011',
      subject: 'Mobile app crashes on iOS 17 when uploading files',
      description: 'The mobile app crashes consistently when trying to upload any file on iOS 17 devices. Works fine on iOS 16.',
      category: 'technical_support',
      priority: 'high',
      channel: 'chat',
      customer_name: 'Rachel Green',
      customer_email: 'rachel.green@email.com',
      status: 'in_progress',
      createdOffset: 8,
      customerMessages: [
        "Every time I try to upload a photo or document in the app, it crashes. I'm on iPhone 15 Pro with iOS 17.2.1. The crash happens right after I select the file. I've tried restarting the app and my phone but it keeps happening.",
      ],
      aiResponse:
        "Hi Rachel, I've identified this as a known issue with iOS 17's new file picker API and our current upload handler. We're working on a fix that will be included in version 3.2.1. As a temporary workaround: 1) Try using the camera directly instead of selecting from gallery, 2) Or use the web app at app.parwa.com for file uploads until the fix is released. The update should be available within 48 hours. Would you like me to notify you when the fix is live?",
      aiResponseOffset: 3,
      tags: ['bug', 'ios', 'crash', 'mobile-app'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0012',
      subject: 'Request webhook support for real-time notifications',
      description: 'We need webhook support to get real-time notifications when tickets are created or updated. Currently we have to poll the API.',
      category: 'technical_support',
      priority: 'medium',
      channel: 'chat',
      customer_name: 'Omar Hassan',
      customer_email: 'omar.hassan@devco.com',
      status: 'open',
      createdOffset: 36,
      customerMessages: [
        "Our team needs webhook notifications for ticket events (created, updated, resolved). Right now we're polling the API every 30 seconds which is inefficient. Is webhook support available or planned?",
      ],
      tags: ['feature-request', 'webhook', 'api'],
    })
  );

  // ── Returns & Exchanges ──
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0013',
      subject: 'Return request for defective headphones - order #ORD-45678',
      description: 'The wireless headphones I received are defective. The left earbud produces static noise. I want to return them for a full refund.',
      category: 'returns_exchanges',
      priority: 'medium',
      channel: 'email',
      customer_name: 'Jennifer Lee',
      customer_email: 'jennifer.lee@email.com',
      status: 'resolved',
      createdOffset: 72,
      resolvedOffset: 4,
      customerMessages: [
        "I received the wireless headphones from order #ORD-45678 but they're defective. The left earbud constantly produces static noise, even after fully charging them. I've tried resetting them multiple times but the issue persists. I'd like to return them for a full refund please.",
      ],
      aiResponse:
        "I'm sorry about the defective headphones, Jennifer. I've processed a full refund of $89.99 to your original payment method. The refund should appear within 5-7 business days. I've also generated a prepaid return shipping label that you can use to send the defective headphones back at no cost. You'll find the label in your email and in your order history. As an apology for the inconvenience, I've added a $15 store credit to your account. Would you like me to suggest an alternative headphone model?",
      aiResponseOffset: 2,
      tags: ['return', 'defective', 'refund'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0014',
      subject: 'Exchange size M for size L in order #ORD-34567',
      description: 'The shirt I ordered is too small. Need to exchange size M for size L.',
      category: 'returns_exchanges',
      priority: 'low',
      channel: 'chat',
      customer_name: 'Chris Martinez',
      customer_email: 'chris.martinez@email.com',
      status: 'resolved',
      createdOffset: 96,
      resolvedOffset: 8,
      customerMessages: [
        "Hey, I ordered a shirt in size M from order #ORD-34567 but it runs small and doesn't fit. Can I exchange it for a size L?",
      ],
      aiResponse:
        "Of course, Chris! I've created an exchange for order #ORD-34567 — swapping the size M for size L. The new shirt will ship within 1-2 business days. I've included a prepaid return label in your email for sending back the size M. You have 14 days to send back the original item. No additional charges for the exchange. Your exchange reference is EXC-2024-0341.",
      aiResponseOffset: 4,
      tags: ['exchange', 'size-change'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0015',
      subject: 'Return status for RMA #RMA-89012 - been 2 weeks',
      description: 'I sent back my return 2 weeks ago with RMA #RMA-89012 but still haven\'t received my refund.',
      category: 'returns_exchanges',
      priority: 'high',
      channel: 'sms',
      customer_name: 'Natasha Petrov',
      customer_email: 'natasha.petrov@email.com',
      status: 'in_progress',
      createdOffset: 10,
      customerMessages: [
        "I returned my item 2 weeks ago with RMA #RMA-89012. The tracking shows it was delivered on January 10th but I still haven't received my refund of $199.99. What's the status?",
      ],
      aiResponse:
        "Hi Natasha, I've checked on RMA #RMA-89012. Your return was received at our warehouse on January 10th, but it appears to be stuck in our processing queue. I'm flagging this for priority processing right now. Your refund of $199.99 should be issued within 24-48 hours. I apologize for the delay. Would you like me to send you a confirmation email once the refund has been processed?",
      aiResponseOffset: 5,
      tags: ['return', 'refund-delay', 'rma'],
    })
  );

  // ── Shipping & Delivery ──
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0016',
      subject: 'Package showing delivered but not received',
      description: 'Tracking says my package was delivered yesterday but I never got it. I was home all day.',
      category: 'shipping_delivery',
      priority: 'high',
      channel: 'email',
      customer_name: 'Tom Wilson',
      customer_email: 'tom.wilson@email.com',
      status: 'in_progress',
      createdOffset: 5,
      customerMessages: [
        "My order tracking shows it was delivered yesterday at 2:34 PM but I was home all day and no package was left. I checked my porch, mailbox, and around my building. I even asked my neighbors. The tracking number is 1Z999AA10123456784. This has never happened before.",
      ],
      aiResponse:
        "Tom, I'm sorry your package is missing. I've initiated an investigation with the carrier. Here's what's happening: 1) I've filed a trace request with the carrier (reference: TRACE-2024-4521), 2) They'll contact the delivery driver to verify the delivery location, 3) If not located within 48 hours, I'll ship a replacement at no cost. In the meantime, could you confirm: Did you receive a delivery notice? Is there a leasing office or package room at your building? I'll keep you updated.",
      aiResponseOffset: 2,
      tags: ['missing-package', 'carrier-investigation'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0017',
      subject: 'Need to change delivery address for shipment #SHP-23456',
      description: 'My shipment is on its way but I need to change the delivery address. I just moved.',
      category: 'shipping_delivery',
      priority: 'medium',
      channel: 'sms',
      customer_name: 'Maria Santos',
      customer_email: 'maria.santos@email.com',
      status: 'resolved',
      createdOffset: 20,
      resolvedOffset: 3,
      customerMessages: [
        "I just realized shipment #SHP-23456 is going to my old address. I moved last week! Can I change the delivery address before it arrives?",
      ],
      aiResponse:
        "Hi Maria, I've submitted an address redirect request for shipment #SHP-23456. Since the package is still in transit, we can intercept it. The new address has been updated in our system. There may be a slight delay (1-2 extra days) due to the redirect, but you'll still receive your package. You'll get a new tracking link once the redirect is processed. Redirect fee has been waived as a courtesy.",
      aiResponseOffset: 1,
      tags: ['address-redirect', 'in-transit'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0018',
      subject: 'Express shipping took 7 days instead of 2',
      description: 'I paid for 2-day express shipping but my package arrived after 7 days. I want a refund for the shipping cost.',
      category: 'shipping_delivery',
      priority: 'high',
      channel: 'chat',
      customer_name: 'Kevin Brown',
      customer_email: 'kevin.brown@email.com',
      status: 'open',
      createdOffset: 14,
      customerMessages: [
        "I paid $24.99 for 2-day express shipping but my package took 7 days to arrive. I was promised delivery by Thursday but it didn't come until the following Wednesday. I want the express shipping fee refunded since I didn't get the service I paid for.",
        "I have the tracking history showing it sat in a sorting facility for 4 days.",
      ],
      tags: ['shipping-delay', 'refund-request', 'express-shipping'],
    })
  );

  // ── Product Information ──
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0019',
      subject: 'What are the exact dimensions of Product X-200?',
      description: 'Need exact dimensions of Product X-200 to make sure it fits in my space.',
      category: 'product_information',
      priority: 'low',
      channel: 'chat',
      customer_name: 'Sophie Laurent',
      customer_email: 'sophie.laurent@email.com',
      status: 'resolved',
      createdOffset: 120,
      resolvedOffset: 10,
      customerMessages: [
        "Can you tell me the exact dimensions of the Product X-200? I need width, height, and depth in both inches and centimeters. I want to make sure it fits in my designated space.",
      ],
      aiResponse:
        "Hi Sophie! Here are the exact dimensions for Product X-200:\n\n• Width: 18.5 inches (47.0 cm)\n• Height: 12.3 inches (31.2 cm)\n• Depth: 8.7 inches (22.1 cm)\n• Weight: 4.2 lbs (1.9 kg)\n\nFor clearance, we recommend adding at least 2 inches on each side for proper ventilation and cable management. You can also download the full specification sheet from our product page under 'Documents & Downloads'. Let me know if you need anything else!",
      aiResponseOffset: 2,
      tags: ['product-specs', 'dimensions'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0020',
      subject: 'Is the software compatible with macOS Sonoma?',
      description: 'Before purchasing, I need to confirm compatibility with macOS Sonoma (14.x).',
      category: 'product_information',
      priority: 'medium',
      channel: 'email',
      customer_name: 'Yusuf Ahmed',
      customer_email: 'yusuf.ahmed@email.com',
      status: 'resolved',
      createdOffset: 60,
      resolvedOffset: 5,
      customerMessages: [
        "I'm running macOS Sonoma 14.2.1 on my MacBook Pro M3. Is your software fully compatible? I saw some compatibility notes mentioning issues with macOS 14. Can you confirm before I purchase?",
      ],
      aiResponse:
        "Hi Yusuf, great question! Our software v4.1 and later is fully compatible with macOS Sonoma 14.x, including on M1/M2/M3 chips. The compatibility issues you may have seen were with version 3.x, which has been resolved. We've tested extensively on macOS Sonoma 14.0 through 14.2.1 with both Intel and Apple Silicon Macs. You can download a free 14-day trial from our website to verify compatibility before purchasing. Here's the download link: [link]. Let me know if you have any other questions!",
      aiResponseOffset: 3,
      tags: ['compatibility', 'macos', 'pre-purchase'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0021',
      subject: 'When will the new model be available for pre-order?',
      description: 'I saw a teaser for the new model on social media. When can I pre-order it?',
      category: 'product_information',
      priority: 'low',
      channel: 'chat',
      customer_name: 'Hannah Miller',
      customer_email: 'hannah.miller@email.com',
      status: 'resolved',
      createdOffset: 168,
      resolvedOffset: 12,
      customerMessages: [
        "I saw a post about the new X-300 model on your Instagram. It looks amazing! When will it be available for pre-order? Do you have pricing info?",
      ],
      aiResponse:
        "Hi Hannah! Thanks for your interest in the X-300! 🎉 We're excited to share that pre-orders will open on February 15th. Here's what we can share so far:\n\n• Expected launch: March 1st\n• Price range: $299-$399 (depending on configuration)\n• Pre-order bonus: Free carrying case + 1-year extended warranty\n\nIf you sign up for our newsletter at parwa.com/x300, you'll get early access to pre-orders 24 hours before the general public, plus an exclusive 10% discount code. Would you like me to add you to the notification list?",
      aiResponseOffset: 8,
      tags: ['pre-order', 'new-product', 'upcoming'],
    })
  );

  // ── Complaints ──
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0022',
      subject: 'Terrible customer service experience - was on hold for 45 minutes',
      description: 'I called support and was on hold for 45 minutes, only to be disconnected. This is unacceptable.',
      category: 'complaints',
      priority: 'critical',
      channel: 'voice',
      customer_name: 'Brad Johnson',
      customer_email: 'brad.johnson@email.com',
      status: 'awaiting_human',
      createdOffset: 3,
      customerMessages: [
        "I've been a customer for 5 years and this is the worst experience I've ever had. I called your support line and waited on hold for 45 minutes, only to be disconnected when an agent finally picked up. I called back and waited another 20 minutes. This is completely unacceptable. I'm seriously considering switching to a competitor unless this is resolved immediately.",
      ],
      aiResponse:
        "Brad, I sincerely apologize for this unacceptable experience. Your loyalty as a 5-year customer deserves much better treatment. I'm escalating this immediately to our Customer Experience Manager who will personally handle your concern. They will contact you within 2 hours via your preferred method. As a gesture of goodwill, I've applied a 3-month free upgrade to the Premium plan to your account. We're also reviewing our phone system to prevent this from happening again.",
      aiResponseOffset: 1,
      tags: ['complaint', 'wait-time', 'escalation', 'loyalty'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0023',
      subject: 'Charged for premium features that don\'t work',
      description: 'I upgraded to Premium for the analytics features but they haven\'t worked for 2 weeks. Support hasn\'t helped.',
      category: 'complaints',
      priority: 'high',
      channel: 'email',
      customer_name: 'Diana Ross',
      customer_email: 'diana.ross@email.com',
      status: 'in_progress',
      createdOffset: 48,
      customerMessages: [
        "I upgraded to Premium specifically for the advanced analytics dashboard two weeks ago. Since then, the analytics page has been showing a 'Service Temporarily Unavailable' error. I've contacted support twice and been told 'engineering is looking into it' both times with no resolution. I'm paying $49.99/month for features I can't use. Either fix this immediately or refund me for the time the features haven't worked.",
      ],
      aiResponse:
        "Diana, I completely understand your frustration — paying for features that don't work is unacceptable. I've checked the analytics service status and found that there's a database connection pool issue affecting approximately 2% of Premium accounts, including yours. Our engineering team has identified the root cause and a fix is being deployed right now. It should be resolved within 2-4 hours. I'm crediting your account for the full Premium subscription cost for the affected period ($24.99). I'll personally follow up with you tomorrow to confirm everything is working. Is there anything else I can do?",
      aiResponseOffset: 5,
      tags: ['complaint', 'billing', 'technical', 'compensation'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0024',
      subject: 'Third time reporting this issue - still not fixed',
      description: 'This is my third time contacting support about the same issue. It has not been resolved despite previous promises.',
      category: 'complaints',
      priority: 'critical',
      channel: 'email',
      customer_name: 'Frank Stevens',
      customer_email: 'frank.stevens@email.com',
      status: 'awaiting_human',
      createdOffset: 1,
      customerMessages: [
        "This is the THIRD time I'm reporting that my invoices show incorrect tax calculations. I was told it was fixed on Dec 15th and again on Jan 3rd. It is STILL not fixed. The tax rate applied is 8.5% when it should be 6.5% for my location in Ohio. Each month I'm being overcharged. At this point I want: 1) Immediate fix, 2) Refund of all overcharges, 3) A written guarantee this won't happen again. This is a serious compliance issue that could affect my business.",
      ],
      aiResponse:
        "Frank, you're absolutely right to be frustrated. Three times is unacceptable, and I can see from your ticket history that this was incorrectly marked as resolved twice. This is clearly a systemic issue that our standard support process has failed to address. I'm immediately escalating this to: 1) Our billing engineering team lead for a permanent fix, 2) Our finance team to calculate and refund all overcharges for the affected months, 3) Our compliance officer to ensure proper documentation. A senior human agent will contact you within 1 hour with a concrete resolution plan.",
      aiResponseOffset: 1,
      tags: ['complaint', 'recurring-issue', 'billing', 'compliance', 'escalation'],
    })
  );

  // ── VIP / Enterprise ──
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0025',
      subject: 'Enterprise SLA breach - need immediate escalation',
      description: 'Our enterprise SLA guarantees 99.9% uptime and 15-minute response time. We\'ve had 3 outages this month.',
      category: 'vip_enterprise',
      priority: 'critical',
      channel: 'voice',
      customer_name: 'Victoria Chen',
      customer_email: 'victoria.chen@megacorp.com',
      status: 'awaiting_human',
      createdOffset: 0.2,
      customerMessages: [
        "This is Victoria Chen, VP of Engineering at MegaCorp. Our enterprise agreement guarantees 99.9% uptime and 15-minute critical response time. This month alone we've experienced three outages totaling 4.5 hours of downtime, and our last critical ticket took 2 hours to get an initial response. This is a material breach of our SLA. We process $2M in daily transactions through your platform. I need an immediate escalation to your executive team with a root cause analysis and remediation plan within 24 hours.",
      ],
      aiResponse:
        "Victoria, thank you for reaching out. I can see your enterprise account and confirm the SLA parameters. Given the severity and the repeated nature of these incidents, I'm immediately escalating this beyond standard support channels. I'm notifying: 1) Our VP of Engineering, 2) Your dedicated Enterprise Account Manager, and 3) Our Customer Success Director. A member of our executive response team will be in contact with you within 30 minutes. Incident summary has been forwarded to all parties. Your reference: VIP-ESCALATION-2024-0091.",
      aiResponseOffset: 0.5,
      tags: ['vip', 'sla-breach', 'enterprise', 'executive-escalation', 'p0'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0026',
      subject: 'Custom API rate limit increase request for enterprise tier',
      description: 'Our application needs a higher API rate limit than the default enterprise tier provides.',
      category: 'vip_enterprise',
      priority: 'high',
      channel: 'email',
      customer_name: 'Marcus Williams',
      customer_email: 'marcus.williams@globaltech.com',
      status: 'resolved',
      createdOffset: 72,
      resolvedOffset: 6,
      customerMessages: [
        "As part of our enterprise agreement, we're requesting an increase to our API rate limits. Our current allocation of 10,000 requests/minute is insufficient for our growing traffic. We need at least 25,000 requests/minute. Our application traffic has grown 40% in Q4 and we expect another 50% growth in Q1. Can we discuss a custom rate limit increase?",
      ],
      aiResponse:
        "Marcus, thank you for the context about your growth. I've reviewed your current usage patterns and I'm happy to report we can accommodate this. I've increased your API rate limit to 30,000 requests/minute (exceeding your requested 25,000). This change is effective immediately. Here are the details:\n\n• New limit: 30,000 req/min (was 10,000)\n• Burst capacity: 45,000 req/min\n• No additional cost (included in your enterprise tier)\n\nIf your growth continues as projected, we can revisit this in Q2. I've also added monitoring alerts that will notify us if you approach 80% of your new limit, so we can proactively plan any further adjustments.",
      aiResponseOffset: 4,
      tags: ['vip', 'enterprise', 'api', 'rate-limit'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0027',
      subject: 'Dedicated account manager request',
      description: 'As an enterprise customer, we\'d like to have a dedicated account manager for more personalized support.',
      category: 'vip_enterprise',
      priority: 'medium',
      channel: 'chat',
      customer_name: 'Elizabeth Taylor',
      customer_email: 'elizabeth.taylor@conglomerate.com',
      status: 'resolved',
      createdOffset: 96,
      resolvedOffset: 12,
      customerMessages: [
        "We've been on the enterprise plan for 6 months and our team has grown significantly. We'd like to request a dedicated account manager who can help us with strategic planning, quarterly business reviews, and priority escalation. Is this available as part of our current plan or do we need to upgrade?",
      ],
      aiResponse:
        "Elizabeth, a dedicated account manager is absolutely available as part of your enterprise plan! I've assigned Sarah Mitchell as your dedicated Account Manager. She has 8 years of experience with enterprise clients and has been briefed on your account. Here's what she'll provide:\n\n• Monthly check-in calls\n• Quarterly Business Reviews (QBRs)\n• Priority escalation channel (direct Slack/Teams)\n• Strategic planning and optimization recommendations\n• Early access to new features and betas\n\nSarah will reach out to schedule your first meeting within the next 48 hours. Her direct contact info: sarah.mitchell@parwa.com. Is there anything specific you'd like her to focus on in the first meeting?",
      aiResponseOffset: 8,
      tags: ['vip', 'enterprise', 'account-management'],
    })
  );

  // ── Fraud & Security ──
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0028',
      subject: 'Unauthorized transactions on my account',
      description: 'I see several transactions I did not make on my account. My account may have been compromised.',
      category: 'fraud_security',
      priority: 'critical',
      channel: 'voice',
      customer_name: 'John Smith',
      customer_email: 'john.smith@email.com',
      status: 'awaiting_human',
      createdOffset: 0.3,
      customerMessages: [
        "I just noticed 4 transactions on my account that I didn't make — totaling $847. The transactions were made between January 14-16. I haven't logged in from a new device. I'm concerned my account has been compromised. I've already changed my password but I need you to investigate immediately, reverse the fraudulent charges, and secure my account.",
      ],
      aiResponse:
        "John, this is a serious security concern and I'm treating it with the highest priority. I've taken immediate protective actions:\n\n1) Your account has been temporarily locked to prevent further unauthorized access\n2) All active sessions have been terminated\n3) An investigation ticket (FRAUD-2024-0156) has been created\n4) Our security team has been notified for forensic analysis\n\nA fraud specialist from our security team will contact you within 30 minutes. They'll help with: verifying your identity, reviewing the fraudulent transactions, initiating chargebacks, and performing a full security audit. Please do NOT change your password again until the security team contacts you, as they may need to review the current state.",
      aiResponseOffset: 0.5,
      tags: ['fraud', 'security', 'unauthorized', 'account-compromised', 'critical'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0029',
      subject: 'Account locked after multiple login attempts',
      description: 'My account got locked because I forgot my password and tried too many times. Need help unlocking it.',
      category: 'fraud_security',
      priority: 'high',
      channel: 'email',
      customer_name: 'Amy Chen',
      customer_email: 'amy.chen@email.com',
      status: 'resolved',
      createdOffset: 8,
      resolvedOffset: 2,
      customerMessages: [
        "My account got locked because I tried logging in too many times. I recently changed my password and couldn't remember it. I've been locked out for 2 hours now. I need access urgently for work. Can you help me unlock it?",
      ],
      aiResponse:
        "Hi Amy, I can help you get back into your account. I've unlocked it and sent a secure password reset link to amy.chen@email.com. The link will expire in 1 hour for security. Once you reset your password, I recommend: 1) Using a password manager to store it securely, 2) Enabling two-factor authentication for extra protection (Settings → Security → 2FA). For future reference, the account auto-unlocks after 24 hours, but you can always contact us for faster assistance. Is there anything else you need?",
      aiResponseOffset: 1,
      tags: ['account-locked', 'password', 'security'],
    })
  );
  tickets.push(
    makeTicket({
      ticket_number: 'TKT-0030',
      subject: 'Suspicious login from unknown device in another country',
      description: 'I received a login alert for a device I don\'t recognize in a country I\'ve never been to.',
      category: 'fraud_security',
      priority: 'critical',
      channel: 'email',
      customer_name: 'Carlos Rivera',
      customer_email: 'carlos.rivera@email.com',
      status: 'in_progress',
      createdOffset: 1,
      customerMessages: [
        "I just received a security alert that my account was logged in from a device in Moscow, Russia. I've never been to Russia and I don't recognize the device (Windows PC, Chrome browser). I'm currently at home in Miami, Florida. I'm concerned someone has my credentials. I've already changed my password but need help securing my account fully.",
      ],
      aiResponse:
        "Carlos, this is indeed suspicious and I'm glad you reported it immediately. Here's what I've done to secure your account:\n\n1) ✅ Terminated the suspicious session from Moscow\n2) ✅ All other sessions remain active (you can review them in Settings → Security)\n3) ✅ Enabled login notifications for all new devices\n4) ✅ Flagged your account for enhanced monitoring for the next 30 days\n\nThe suspicious login occurred at 3:42 AM EST from IP 185.x.x.x. Our security team will investigate this IP address. I strongly recommend enabling two-factor authentication (2FA) immediately — this would prevent unauthorized access even if someone has your password. Would you like me to walk you through setting up 2FA?",
      aiResponseOffset: 1,
      tags: ['security', 'suspicious-login', 'unauthorized-access', '2fa'],
    })
  );

  // ── Update ticket IDs in messages ──
  for (const t of tickets) {
    for (const m of t.messages) {
      m.ticket_id = t.id;
    }
  }

  return tickets;
}

export function seedIfEmpty(): boolean {
  if (typeof window === 'undefined') return false;
  const alreadySeeded = localStorage.getItem(INIT_KEY);
  if (alreadySeeded) return false;

  const existing = localStorage.getItem(STORAGE_KEY);
  if (existing) {
    try {
      const parsed = JSON.parse(existing);
      if (Array.isArray(parsed) && parsed.length > 0) {
        localStorage.setItem(INIT_KEY, 'true');
        return false;
      }
    } catch {
      // ignore
    }
  }

  const tickets = seedTickets();
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets));
  localStorage.setItem(INIT_KEY, 'true');

  // Update ticket counter
  const maxNum = Math.max(
    ...tickets.map((t) => parseInt(t.ticket_number.replace('TKT-', ''), 10))
  );
  ticketCounter = maxNum + 1;

  return true;
}
