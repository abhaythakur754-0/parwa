/**
 * PARWA Ticket Mock Data — Day 3
 *
 * Realistic mock data for the ticket management page.
 * 60 tickets across various statuses, priorities, and channels.
 */

import type {
  Ticket,
  TicketMessage,
  InternalNote,
  TimelineEntry,
  CustomerInfo,
  AgentInfo,
  TicketStatus,
  TicketPriority,
  TicketChannel,
  TicketSentiment,
  GSDState,
  AITechnique,
  SenderRole,
  TicketAttachment,
} from '@/types/ticket';

// ── Helpers ─────────────────────────────────────────────────────────────

const rand = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1)) + min;
const pick = <T,>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];
const uuid = () => crypto.randomUUID();

const timeAgo = (minutes: number): string => {
  const d = new Date(Date.now() - minutes * 60_000);
  return d.toISOString();
};

// ── Agent Pool ──────────────────────────────────────────────────────────

export const mockAgents: AgentInfo[] = [
  { id: 'a1', name: 'Sarah Chen', email: 'sarah@parwa.ai', avatar_url: null, is_online: true, active_ticket_count: 5 },
  { id: 'a2', name: 'Marcus Johnson', email: 'marcus@parwa.ai', avatar_url: null, is_online: true, active_ticket_count: 3 },
  { id: 'a3', name: 'Priya Patel', email: 'priya@parwa.ai', avatar_url: null, is_online: false, active_ticket_count: 0 },
  { id: 'a4', name: 'James Wilson', email: 'james@parwa.ai', avatar_url: null, is_online: true, active_ticket_count: 7 },
  { id: 'a5', name: 'Emma Rodriguez', email: 'emma@parwa.ai', avatar_url: null, is_online: false, active_ticket_count: 2 },
];

// ── Customer Pool ───────────────────────────────────────────────────────

const customers: Omit<CustomerInfo, 'total_tickets' | 'resolved_tickets' | 'avg_csat'>[] = [
  { id: 'c1', name: 'Alex Thompson', email: 'alex@techcorp.com', phone: '+1-555-0101', avatar_url: null, company: 'TechCorp', first_seen: '2024-01-15T08:00:00Z', last_active: timeAgo(5), tags: ['enterprise', 'priority'] },
  { id: 'c2', name: 'Maria Garcia', email: 'maria@designhub.io', phone: '+1-555-0102', avatar_url: null, company: 'DesignHub', first_seen: '2024-02-10T10:30:00Z', last_active: timeAgo(120), tags: ['pro'] },
  { id: 'c3', name: 'David Kim', email: 'david@startupx.co', phone: null, avatar_url: null, company: 'StartupX', first_seen: '2024-03-01T14:00:00Z', last_active: timeAgo(60), tags: ['startup'] },
  { id: 'c4', name: 'Rachel Foster', email: 'rachel@mediapro.com', phone: '+1-555-0104', avatar_url: null, company: 'MediaPro', first_seen: '2024-01-20T09:00:00Z', last_active: timeAgo(1440), tags: ['enterprise'] },
  { id: 'c5', name: 'Omar Hassan', email: 'omar@globalretail.net', phone: '+44-555-0105', avatar_url: null, company: 'GlobalRetail', first_seen: '2024-04-05T11:00:00Z', last_active: timeAgo(30), tags: ['retail', 'international'] },
  { id: 'c6', name: 'Lisa Wang', email: 'lisa@cloudnine.dev', phone: '+1-555-0106', avatar_url: null, company: 'CloudNine', first_seen: '2024-02-28T16:00:00Z', last_active: timeAgo(240), tags: ['tech'] },
  { id: 'c7', name: 'John Mitchell', email: 'john@buildright.co', phone: '+1-555-0107', avatar_url: null, company: 'BuildRight', first_seen: '2024-05-10T13:00:00Z', last_active: timeAgo(15), tags: ['construction'] },
  { id: 'c8', name: 'Sofia Martinez', email: 'sofia@healthplus.org', phone: '+1-555-0108', avatar_url: null, company: 'HealthPlus', first_seen: '2024-03-15T08:30:00Z', last_active: timeAgo(45), tags: ['healthcare'] },
  { id: 'c9', name: 'Ryan Cooper', email: 'ryan@fintech.io', phone: null, avatar_url: null, company: 'FinTech Solutions', first_seen: '2024-01-08T10:00:00Z', last_active: timeAgo(720), tags: ['finance'] },
  { id: 'c10', name: 'Aisha Patel', email: 'aisha@educonnect.com', phone: '+1-555-0110', avatar_url: null, company: 'EduConnect', first_seen: '2024-04-20T15:00:00Z', last_active: timeAgo(90), tags: ['education'] },
  { id: 'c11', name: 'Tom Baker', email: 'tom@logistco.com', phone: '+1-555-0111', avatar_url: null, company: 'LogistCo', first_seen: '2024-06-01T09:00:00Z', last_active: timeAgo(10), tags: ['logistics'] },
  { id: 'c12', name: 'Nina Ivanova', email: 'nina@shopline.eu', phone: '+49-555-0112', avatar_url: null, company: 'ShopLine', first_seen: '2024-02-14T12:00:00Z', last_active: timeAgo(300), tags: ['ecommerce', 'international'] },
];

// ── Subjects & Descriptions ─────────────────────────────────────────────

const subjects: Record<TicketPriority, string[]> = {
  critical: [
    'System outage — entire platform unreachable',
    'Payment processing failure — customers cannot checkout',
    'Data breach alert — unauthorized access detected',
    'Critical API downtime affecting all clients',
    'Security vulnerability found in production',
  ],
  high: [
    'Billing discrepancy on enterprise invoice',
    'Feature not working after latest update',
    'Integration with Salesforce failing intermittently',
    'Cannot export reports — timeout errors',
    'SSO login broken for team accounts',
  ],
  medium: [
    'How to customize email templates?',
    'Request for bulk user import feature',
    'Dashboard loading slowly for large datasets',
    'Need help setting up webhook notifications',
    'Custom field not showing in reports',
  ],
  low: [
    'Feature request: dark mode support',
    'Minor typo in onboarding email',
    'Can I change my notification preferences?',
    'Suggestion: improve search filters',
    'Documentation link is broken on help page',
  ],
};

const descriptions: Record<TicketPriority, string> = {
  critical: 'This is a critical issue that requires immediate attention. Multiple customers are affected and business operations are impacted.',
  high: 'This issue is significantly impacting our workflow and needs to be addressed as soon as possible. Several team members are blocked.',
  medium: 'We need assistance with this matter. It is not urgent but affects our daily operations.',
  low: 'This is a minor issue or feature request. Low priority but would be nice to have resolved.',
};

// ── Ticket Generation ───────────────────────────────────────────────────

const statuses: TicketStatus[] = ['open', 'in_progress', 'awaiting_customer', 'awaiting_agent', 'escalated', 'resolved', 'closed', 'spam'];
const channels: TicketChannel[] = ['email', 'chat', 'sms', 'whatsapp', 'messenger', 'twitter', 'instagram'];
const sentiments: TicketSentiment[] = ['positive', 'neutral', 'negative', 'mixed'];
const gsdStates: GSDState[] = ['greeting', 'understanding', 'resolution', 'confirmation', 'closing'];
const techniques: AITechnique[] = ['knowledge_base', 'sentiment_match', 'intent_classification', 'entity_extraction', 'conversation_flow', 'escalation_trigger', 'template_response', 'fallback'];
const tags = ['billing', 'technical', 'feature-request', 'bug', 'onboarding', 'integration', 'security', 'performance', 'ui-ux', 'api', 'enterprise', 'urgent'];
const variantNames = ['Billing FAQ v2.3', 'Password Reset Flow v1.8', 'Feature Tour v3.1', 'Onboarding Guide v4.0', 'API Docs v2.7', 'Pricing Query v1.5', 'Troubleshooting v2.1', 'Account Settings v1.9'];

function generateTicket(index: number): Ticket {
  const priority = pick([
    ...Array(3).fill('low' as TicketPriority),
    ...Array(6).fill('medium' as TicketPriority),
    ...Array(4).fill('high' as TicketPriority),
    ...Array(2).fill('critical' as TicketPriority),
  ]);

  const status = index < 8
    ? pick(['open', 'in_progress', 'awaiting_customer', 'escalated'] as TicketStatus[])
    : index < 14
      ? pick(['resolved', 'closed'] as TicketStatus[])
      : pick(statuses);

  const agent = status === 'open' || status === 'spam' ? null : pick(mockAgents);
  const customer = pick(customers);
  const channel = pick(channels);
  const createdMinutesAgo = rand(5, 43_800);
  const isResolved = status === 'resolved' || status === 'closed';

  return {
    id: uuid(),
    ticket_number: `TKT-${String(3000 + index).padStart(4, '0')}`,
    subject: pick(subjects[priority]),
    description: descriptions[priority],
    status,
    priority,
    channel,
    customer: {
      ...customer,
      total_tickets: rand(1, 25),
      resolved_tickets: rand(0, 20),
      avg_csat: pick([null, 3.2, 3.5, 3.8, 4.0, 4.2, 4.5, 4.8, 5.0]),
    },
    assigned_agent: agent,
    ai_confidence: status === 'spam' ? rand(0, 30) / 100 : rand(45, 99) / 100,
    sentiment: pick(sentiments),
    gsd_state: isResolved ? 'closing' : pick(gsdStates),
    ai_technique: pick(techniques),
    resolution_time_minutes: isResolved ? rand(5, 1440) : null,
    first_response_time_minutes: status !== 'open' ? rand(1, 30) : null,
    sla_deadline: createdMinutesAgo < 500 ? new Date(Date.now() + rand(60, 480) * 60_000).toISOString() : null,
    sla_breached: createdMinutesAgo > 500 && Math.random() > 0.5,
    sla_approaching: createdMinutesAgo > 400 && createdMinutesAgo <= 500 && Math.random() > 0.3,
    is_ai_resolved: isResolved && Math.random() > 0.4,
    tags: Array.from({ length: rand(0, 3) }, () => pick(tags)).filter((v, i, a) => a.indexOf(v) === i),
    message_count: rand(2, 24),
    unread_count: status === 'open' ? rand(0, 3) : 0,
    has_attachments: Math.random() > 0.7,
    variant_id: Math.random() > 0.5 ? `v-${rand(1, 99)}` : null,
    variant_name: Math.random() > 0.5 ? pick(variantNames) : null,
    created_at: timeAgo(createdMinutesAgo),
    updated_at: timeAgo(rand(1, createdMinutesAgo)),
    resolved_at: isResolved ? timeAgo(rand(1, createdMinutesAgo - 5)) : null,
  };
}

// ── Generate Ticket List ────────────────────────────────────────────────

export const mockTickets: Ticket[] = Array.from({ length: 60 }, (_, i) => generateTicket(i));

// ── Generate Messages for a Ticket ──────────────────────────────────────

const customerMessages = [
  'Hi, I need help with something.',
  "I've been trying to access my account but keep getting an error.",
  'The billing page shows the wrong amount. Can you check?',
  'Is there a way to export all my data?',
  "We're seeing a significant delay in response times from your API.",
  'Can you help me set up the webhook integration?',
  'I need to upgrade our plan. How do I do that?',
  'Our team is locked out of the dashboard. Urgent!',
  "Thanks for the quick fix! That's working now.",
  "I'm still seeing the issue. Here's a screenshot.",
  'When will this feature be available?',
  'Can we schedule a call to discuss the enterprise plan?',
];

const aiResponses = [
  "I understand your concern. Let me help you with that right away.",
  "I can see the issue in your account. Here's what I recommend...",
  "I've found the relevant article in our knowledge base that addresses this.",
  "Let me walk you through the steps to resolve this.",
  "I've escalated this to our technical team. You'll receive an update within 2 hours.",
  "That's a great question! Here's how you can do that...",
  "I've checked your account and everything looks correct on our end.",
  "I apologize for the inconvenience. Let me investigate this further.",
  "Based on your account type, you have access to this feature. Here's how to enable it...",
  "I can help with that! Let me pull up the relevant information.",
];

const humanAgentMessages = [
  "I've reviewed your case and pushed a fix to production. Can you verify?",
  "I'm assigning this to our integration specialist. You'll hear back shortly.",
  "This requires a database migration. I've scheduled it for tonight's maintenance window.",
  "I've added a credit to your account for the inconvenience.",
  "Let me check with our billing team and get back to you.",
  "I can see the root cause now. It's related to the recent infrastructure change.",
];

function generateMessages(ticketId: string, count: number): TicketMessage[] {
  const messages: TicketMessage[] = [];
  const roles: SenderRole[] = ['customer', 'ai_agent', 'human_agent'];

  for (let i = 0; i < count; i++) {
    const role = i === 0 ? 'customer' : i === count - 1 ? 'customer' : pick(roles);
    const attachments: TicketAttachment[] = Math.random() > 0.85
      ? [{
          id: uuid(),
          filename: pick(['screenshot.png', 'error-log.txt', 'invoice.pdf', 'config.json', 'report.csv']),
          file_url: '#',
          file_type: pick(['image', 'document', 'document', 'other', 'document']),
          file_size_bytes: rand(1024, 5_242_880),
          uploaded_at: timeAgo(rand(1, 500)),
        }]
      : [];

    messages.push({
      id: uuid(),
      ticket_id: ticketId,
      sender_role: role,
      sender_name: role === 'customer'
        ? pick(customers).name
        : role === 'ai_agent'
          ? 'PARWA AI'
          : pick(mockAgents).name,
      content: role === 'customer'
        ? pick(customerMessages)
        : role === 'ai_agent'
          ? pick(aiResponses)
          : pick(humanAgentMessages),
      content_type: 'text',
      ai_confidence: role === 'ai_agent' ? rand(60, 99) / 100 : null,
      sentiment: role === 'customer' ? pick(sentiments) : null,
      ai_technique: role === 'ai_agent' ? pick(techniques) : null,
      attachments,
      created_at: timeAgo(rand(count - i, (count - i) * 60)),
    });
  }

  return messages.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
}

// ── Generate Notes ──────────────────────────────────────────────────────

function generateNotes(ticketId: string): InternalNote[] {
  const noteCount = rand(0, 3);
  return Array.from({ length: noteCount }, () => ({
    id: uuid(),
    ticket_id: ticketId,
    author_id: pick(mockAgents).id,
    author_name: pick(mockAgents).name,
    content: pick([
      'Customer is on the enterprise plan — prioritize this.',
      'This is a known issue with the latest release. Patch incoming.',
      'Customer confirmed the fix works. Ready to close.',
      'Escalated to engineering. Waiting for root cause analysis.',
      'Follow up next week to ensure satisfaction.',
      'Customer mentioned this happens intermittently — may be hard to reproduce.',
    ]),
    is_pinned: Math.random() > 0.8,
    created_at: timeAgo(rand(30, 1440)),
    updated_at: timeAgo(rand(10, 1440)),
  }));
}

// ── Generate Timeline ───────────────────────────────────────────────────

function generateTimeline(ticketId: string): TimelineEntry[] {
  const events = [
    { event_type: 'ticket.created', description: 'Ticket created', actor_name: null },
    { event_type: 'ticket.auto_assigned', description: 'Auto-assigned to AI agent', actor_name: 'PARWA AI' },
    { event_type: 'ticket.ai_responded', description: 'AI sent initial response', actor_name: 'PARWA AI' },
    { event_type: 'ticket.agent_assigned', description: 'Assigned to human agent', actor_name: pick(mockAgents).name },
    { event_type: 'ticket.escalated', description: 'Escalated to support team', actor_name: pick(mockAgents).name },
    { event_type: 'ticket.note_added', description: 'Internal note added', actor_name: pick(mockAgents).name },
    { event_type: 'ticket.status_changed', description: 'Status changed to in_progress', actor_name: pick(mockAgents).name },
    { event_type: 'ticket.priority_changed', description: 'Priority updated to high', actor_name: pick(mockAgents).name },
    { event_type: 'ticket.resolved', description: 'Ticket resolved', actor_name: pick(mockAgents).name },
    { event_type: 'ticket.closed', description: 'Ticket closed', actor_name: pick(mockAgents).name },
  ];

  const count = rand(3, 7);
  return Array.from({ length: count }, (_, i) => ({
    id: uuid(),
    ticket_id: ticketId,
    ...events[i],
    metadata: {},
    created_at: timeAgo(rand(count * 30, (count - i) * 120)),
  })).sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
}

// ── Mock Detail Data ────────────────────────────────────────────────────

export function getMockTicketDetail(ticket: Ticket) {
  return {
    ticket,
    messages: generateMessages(ticket.id, ticket.message_count),
    notes: generateNotes(ticket.id),
    timeline: generateTimeline(ticket.id),
  };
}

// ── Filter Helpers ──────────────────────────────────────────────────────

export function filterTickets(
  tickets: Ticket[],
  filters: {
    status?: string[];
    channel?: string[];
    agent_id?: string[];
    priority?: string[];
    ai_confidence_min?: number;
    ai_confidence_max?: number;
    date_from?: string;
    date_to?: string;
    search?: string;
  }
): Ticket[] {
  return tickets.filter((t) => {
    if (filters.status?.length && !filters.status.includes(t.status)) return false;
    if (filters.channel?.length && !filters.channel.includes(t.channel)) return false;
    if (filters.agent_id?.length) {
      if (!t.assigned_agent || !filters.agent_id.includes(t.assigned_agent.id)) return false;
    }
    if (filters.priority?.length && !filters.priority.includes(t.priority)) return false;
    if (filters.ai_confidence_min !== undefined && t.ai_confidence < filters.ai_confidence_min) return false;
    if (filters.ai_confidence_max !== undefined && t.ai_confidence > filters.ai_confidence_max) return false;
    if (filters.date_from && new Date(t.created_at) < new Date(filters.date_from)) return false;
    if (filters.date_to && new Date(t.created_at) > new Date(filters.date_to)) return false;
    if (filters.search) {
      const q = filters.search.toLowerCase();
      const searchable = `${t.ticket_number} ${t.subject} ${t.customer.name} ${t.customer.email} ${t.description}`.toLowerCase();
      if (!searchable.includes(q)) return false;
    }
    return true;
  });
}

export function sortTickets(
  tickets: Ticket[],
  field: string,
  direction: 'asc' | 'desc'
): Ticket[] {
  const sorted = [...tickets].sort((a, b) => {
    let cmp = 0;
    switch (field) {
      case 'ticket_number':
        cmp = a.ticket_number.localeCompare(b.ticket_number);
        break;
      case 'status':
        cmp = a.status.localeCompare(b.status);
        break;
      case 'priority': {
        const order: Record<TicketPriority, number> = { critical: 0, high: 1, medium: 2, low: 3 };
        cmp = order[a.priority] - order[b.priority];
        break;
      }
      case 'channel':
        cmp = a.channel.localeCompare(b.channel);
        break;
      case 'assigned_agent':
        cmp = (a.assigned_agent?.name || '').localeCompare(b.assigned_agent?.name || '');
        break;
      case 'ai_confidence':
        cmp = a.ai_confidence - b.ai_confidence;
        break;
      case 'created_at':
        cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        break;
      case 'updated_at':
        cmp = new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime();
        break;
      default:
        cmp = 0;
    }
    return direction === 'asc' ? cmp : -cmp;
  });
  return sorted;
}

export function paginateTickets(
  tickets: Ticket[],
  page: number,
  pageSize: number
): { items: Ticket[]; total: number; totalPages: number } {
  const total = tickets.length;
  const totalPages = Math.ceil(total / pageSize);
  const start = (page - 1) * pageSize;
  const items = tickets.slice(start, start + pageSize);
  return { items, total, totalPages };
}
