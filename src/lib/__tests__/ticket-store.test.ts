/**
 * PARWA Ticket Store — Unit Tests
 *
 * Tests CRUD operations, status transitions, auto-variant assignment,
 * message handling, statistics, and edge cases.
 */

import { useTicketStore, autoAssignVariant, computeStats, ALL_STATUSES, ALL_PRIORITIES, ALL_CHANNELS, ALL_CATEGORIES, VARIANT_COST, TicketCategory, TicketPriority, TicketChannel } from '@/lib/ticket-store';

// ── Constants Validation ────────────────────────────────────────────

describe('Ticket Store Constants', () => {
  it('has 6 statuses', () => {
    expect(ALL_STATUSES).toHaveLength(6);
    expect(ALL_STATUSES).toContain('open');
    expect(ALL_STATUSES).toContain('in_progress');
    expect(ALL_STATUSES).toContain('resolved');
    expect(ALL_STATUSES).toContain('closed');
    expect(ALL_STATUSES).toContain('awaiting_client');
    expect(ALL_STATUSES).toContain('awaiting_human');
  });

  it('has 4 priorities', () => {
    expect(ALL_PRIORITIES).toHaveLength(4);
    expect(ALL_PRIORITIES).toEqual(['low', 'medium', 'high', 'critical']);
  });

  it('has 4 channels', () => {
    expect(ALL_CHANNELS).toHaveLength(4);
    expect(ALL_CHANNELS).toEqual(['email', 'chat', 'sms', 'voice']);
  });

  it('has 10 categories', () => {
    expect(ALL_CATEGORIES).toHaveLength(10);
  });

  it('has variant costs: light < medium < heavy', () => {
    expect(VARIANT_COST.light).toBeLessThan(VARIANT_COST.medium);
    expect(VARIANT_COST.medium).toBeLessThan(VARIANT_COST.heavy);
  });
});

// ── Auto Variant Assignment ─────────────────────────────────────────

describe('autoAssignVariant', () => {
  // Import the function from the module — it's internal but we can test via addTicket

  it('assigns heavy variant for critical priority', () => {
    const store = useTicketStore.getState();
    const ticket = store.addTicket({
      subject: 'Critical issue',
      description: 'Urgent problem',
      category: 'billing_payments',
      priority: 'critical',
      channel: 'email',
      customer_name: 'Test User',
      customer_email: 'test@example.com',
    });
    expect(ticket.assigned_variant).toBe('heavy');
  });

  it('assigns medium variant for high priority', () => {
    const store = useTicketStore.getState();
    const ticket = store.addTicket({
      subject: 'High priority issue',
      description: 'Important problem',
      category: 'billing_payments',
      priority: 'high',
      channel: 'email',
      customer_name: 'Test User',
      customer_email: 'test@example.com',
    });
    expect(ticket.assigned_variant).toBe('medium');
  });

  it('assigns medium variant for fraud_security category even with low priority', () => {
    const store = useTicketStore.getState();
    const ticket = store.addTicket({
      subject: 'Suspicious activity',
      description: 'Fraud alert',
      category: 'fraud_security',
      priority: 'low',
      channel: 'email',
      customer_name: 'Test User',
      customer_email: 'test@example.com',
    });
    expect(ticket.assigned_variant).toBe('medium');
  });

  it('assigns medium variant for vip_enterprise category', () => {
    const store = useTicketStore.getState();
    const ticket = store.addTicket({
      subject: 'VIP request',
      description: 'Enterprise client issue',
      category: 'vip_enterprise',
      priority: 'low',
      channel: 'email',
      customer_name: 'Test User',
      customer_email: 'test@example.com',
    });
    expect(ticket.assigned_variant).toBe('medium');
  });

  it('assigns medium variant for complaints category', () => {
    const store = useTicketStore.getState();
    const ticket = store.addTicket({
      subject: 'Complaint',
      description: 'Unhappy customer',
      category: 'complaints',
      priority: 'low',
      channel: 'email',
      customer_name: 'Test User',
      customer_email: 'test@example.com',
    });
    expect(ticket.assigned_variant).toBe('medium');
  });

  it('assigns light variant for standard cases', () => {
    const store = useTicketStore.getState();
    const ticket = store.addTicket({
      subject: 'General question',
      description: 'Simple inquiry',
      category: 'product_information',
      priority: 'low',
      channel: 'chat',
      customer_name: 'Test User',
      customer_email: 'test@example.com',
    });
    expect(ticket.assigned_variant).toBe('light');
  });

  it('assigns light variant for medium priority with standard category', () => {
    const store = useTicketStore.getState();
    const ticket = store.addTicket({
      subject: 'Medium issue',
      description: 'Standard category',
      category: 'order_management',
      priority: 'medium',
      channel: 'chat',
      customer_name: 'Test User',
      customer_email: 'test@example.com',
    });
    expect(ticket.assigned_variant).toBe('light');
  });
});

// ── Store Actions ────────────────────────────────────────────────────

describe('useTicketStore', () => {
  beforeEach(() => {
    // Reset store
    useTicketStore.setState({ tickets: [], initialized: false });
  });

  describe('addTicket', () => {
    it('creates a ticket with correct defaults', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Test ticket',
        description: 'Test description',
        category: 'billing_payments',
        priority: 'medium',
        channel: 'email',
        customer_name: 'John Doe',
        customer_email: 'john@example.com',
      });

      expect(ticket.id).toBeDefined();
      expect(ticket.ticket_number).toMatch(/^TKT-\d{4}$/);
      expect(ticket.status).toBe('open');
      expect(ticket.subject).toBe('Test ticket');
      expect(ticket.category).toBe('billing_payments');
      expect(ticket.priority).toBe('medium');
      expect(ticket.channel).toBe('email');
      expect(ticket.customer_name).toBe('John Doe');
      expect(ticket.assigned_variant).toBeDefined();
      expect(ticket.assigned_agent).toBeNull();
      expect(ticket.messages).toEqual([]);
      expect(ticket.tags).toEqual([]);
      expect(ticket.resolved_at).toBeNull();
      expect(ticket.first_response_at).toBeNull();
      expect(ticket.resolution_time_hours).toBeNull();
    });

    it('adds ticket to the beginning of the list', () => {
      useTicketStore.getState().addTicket({
        subject: 'First ticket',
        description: 'First',
        category: 'billing_payments',
        priority: 'low',
        channel: 'email',
        customer_name: 'User 1',
        customer_email: 'user1@example.com',
      });

      useTicketStore.getState().addTicket({
        subject: 'Second ticket',
        description: 'Second',
        category: 'technical_support',
        priority: 'high',
        channel: 'chat',
        customer_name: 'User 2',
        customer_email: 'user2@example.com',
      });

      const tickets = useTicketStore.getState().tickets;
      expect(tickets).toHaveLength(2);
      expect(tickets[0].subject).toBe('Second ticket');
      expect(tickets[1].subject).toBe('First ticket');
    });

    it('sets AI confidence based on variant', () => {
      const lightTicket = useTicketStore.getState().addTicket({
        subject: 'Light ticket',
        description: 'Low priority',
        category: 'product_information',
        priority: 'low',
        channel: 'chat',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });
      expect(lightTicket.ai_confidence).toBe(95.2);

      const heavyTicket = useTicketStore.getState().addTicket({
        subject: 'Heavy ticket',
        description: 'Critical priority',
        category: 'billing_payments',
        priority: 'critical',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });
      expect(heavyTicket.ai_confidence).toBe(93.1);
    });

    it('calculates cost and savings per ticket', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Cost test',
        description: 'Testing cost',
        category: 'product_information',
        priority: 'low',
        channel: 'chat',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      expect(ticket.cost_per_ticket).toBe(VARIANT_COST[ticket.assigned_variant!]);
      expect(ticket.savings_per_ticket).toBeCloseTo(12.5 - VARIANT_COST[ticket.assigned_variant!]);
    });

    it('increments ticket numbers', () => {
      const t1 = useTicketStore.getState().addTicket({
        subject: 'T1',
        description: 'T1',
        category: 'billing_payments',
        priority: 'low',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });
      const t2 = useTicketStore.getState().addTicket({
        subject: 'T2',
        description: 'T2',
        category: 'billing_payments',
        priority: 'low',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });
      const num1 = parseInt(t1.ticket_number.replace('TKT-', ''), 10);
      const num2 = parseInt(t2.ticket_number.replace('TKT-', ''), 10);
      expect(num2).toBeGreaterThan(num1);
    });
  });

  describe('updateTicketStatus', () => {
    it('updates status and updated_at timestamp', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Status test',
        description: 'Testing status',
        category: 'billing_payments',
        priority: 'medium',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      const beforeUpdate = ticket.updated_at;
      useTicketStore.getState().updateTicketStatus(ticket.id, 'in_progress');

      const updated = useTicketStore.getState().getTicket(ticket.id)!;
      expect(updated.status).toBe('in_progress');
      expect(new Date(updated.updated_at).getTime()).toBeGreaterThanOrEqual(
        new Date(beforeUpdate).getTime()
      );
    });

    it('does not modify other tickets', () => {
      const t1 = useTicketStore.getState().addTicket({
        subject: 'Ticket 1',
        description: 'T1',
        category: 'billing_payments',
        priority: 'low',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });
      const t2 = useTicketStore.getState().addTicket({
        subject: 'Ticket 2',
        description: 'T2',
        category: 'billing_payments',
        priority: 'low',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      useTicketStore.getState().updateTicketStatus(t1.id, 'in_progress');

      expect(useTicketStore.getState().getTicket(t1.id)!.status).toBe('in_progress');
      expect(useTicketStore.getState().getTicket(t2.id)!.status).toBe('open');
    });
  });

  describe('assignVariant', () => {
    it('updates variant and recalculates cost', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Variant test',
        description: 'Testing variant',
        category: 'product_information',
        priority: 'low',
        channel: 'chat',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      useTicketStore.getState().assignVariant(ticket.id, 'heavy');

      const updated = useTicketStore.getState().getTicket(ticket.id)!;
      expect(updated.assigned_variant).toBe('heavy');
      expect(updated.cost_per_ticket).toBe(VARIANT_COST.heavy);
      expect(updated.savings_per_ticket).toBeCloseTo(12.5 - VARIANT_COST.heavy);
      expect(updated.ai_confidence).toBe(93.1);
    });
  });

  describe('resolveTicket', () => {
    it('sets status to resolved with resolution time', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Resolve test',
        description: 'Testing resolve',
        category: 'billing_payments',
        priority: 'medium',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      useTicketStore.getState().resolveTicket(ticket.id, 'Fixed the billing issue');

      const resolved = useTicketStore.getState().getTicket(ticket.id)!;
      expect(resolved.status).toBe('resolved');
      expect(resolved.resolved_at).toBeDefined();
      expect(resolved.resolution_time_hours).toBeGreaterThanOrEqual(0);
      expect(resolved.messages).toHaveLength(1);
      expect(resolved.messages[0].content).toContain('Fixed the billing issue');
      expect(resolved.messages[0].sender).toBe('ai_agent');
    });

    it('uses default message when no resolution provided', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Resolve test',
        description: 'Testing resolve',
        category: 'billing_payments',
        priority: 'medium',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      useTicketStore.getState().resolveTicket(ticket.id);

      const resolved = useTicketStore.getState().getTicket(ticket.id)!;
      expect(resolved.messages[0].content).toContain('marked as resolved');
    });

    it('preserves existing messages when resolving', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Messages test',
        description: 'Testing messages on resolve',
        category: 'billing_payments',
        priority: 'medium',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'customer',
        sender_name: 'Test',
        content: 'Original message',
      });

      useTicketStore.getState().resolveTicket(ticket.id);

      const resolved = useTicketStore.getState().getTicket(ticket.id)!;
      expect(resolved.messages).toHaveLength(2); // customer message + resolution message
    });
  });

  describe('escalateToHuman', () => {
    it('sets status to awaiting_human and assigns Human Agent', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Escalation test',
        description: 'Testing escalation',
        category: 'technical_support',
        priority: 'high',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      useTicketStore.getState().escalateToHuman(ticket.id);

      const escalated = useTicketStore.getState().getTicket(ticket.id)!;
      expect(escalated.status).toBe('awaiting_human');
      expect(escalated.assigned_agent).toBe('Human Agent');
      expect(escalated.messages).toHaveLength(1);
      expect(escalated.messages[0].content).toContain('escalated to a human agent');
      expect(escalated.messages[0].sender).toBe('system');
    });
  });

  describe('updatePriority', () => {
    it('updates priority and re-assigns variant based on new priority', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Priority test',
        description: 'Testing priority update',
        category: 'product_information',
        priority: 'low',
        channel: 'chat',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      expect(ticket.assigned_variant).toBe('light');

      useTicketStore.getState().updatePriority(ticket.id, 'critical');

      const updated = useTicketStore.getState().getTicket(ticket.id)!;
      expect(updated.priority).toBe('critical');
      expect(updated.assigned_variant).toBe('heavy');
      expect(updated.cost_per_ticket).toBe(VARIANT_COST.heavy);
    });
  });

  describe('addMessage', () => {
    it('adds a message to the ticket', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Message test',
        description: 'Testing messages',
        category: 'billing_payments',
        priority: 'medium',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      const msg = useTicketStore.getState().addMessage(ticket.id, {
        sender: 'customer',
        sender_name: 'Test User',
        content: 'Hello, I need help',
      });

      expect(msg.id).toBeDefined();
      expect(msg.ticket_id).toBe(ticket.id);
      expect(msg.content).toBe('Hello, I need help');
      expect(msg.sender).toBe('customer');

      const updated = useTicketStore.getState().getTicket(ticket.id)!;
      expect(updated.messages).toHaveLength(1);
    });

    it('auto-transitions open ticket to in_progress on first message', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Auto transition test',
        description: 'Testing auto status transition',
        category: 'billing_payments',
        priority: 'medium',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      expect(ticket.status).toBe('open');

      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'ai_agent',
        sender_name: 'PARWA AI',
        content: 'How can I help?',
      });

      const updated = useTicketStore.getState().getTicket(ticket.id)!;
      expect(updated.status).toBe('in_progress');
    });

    it('sets first_response_at on first message', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'First response test',
        description: 'Testing first response timestamp',
        category: 'billing_payments',
        priority: 'medium',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      expect(ticket.first_response_at).toBeNull();

      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'ai_agent',
        sender_name: 'PARWA AI',
        content: 'Response',
      });

      const updated = useTicketStore.getState().getTicket(ticket.id)!;
      expect(updated.first_response_at).toBeDefined();
    });

    it('does not override first_response_at on subsequent messages', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'FR test 2',
        description: 'Testing first_response_at immutability',
        category: 'billing_payments',
        priority: 'medium',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'ai_agent',
        sender_name: 'PARWA AI',
        content: 'First response',
      });

      const firstResponse = useTicketStore.getState().getTicket(ticket.id)!.first_response_at;

      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'customer',
        sender_name: 'Test User',
        content: 'Follow up',
      });

      const secondResponse = useTicketStore.getState().getTicket(ticket.id)!.first_response_at;
      expect(secondResponse).toBe(firstResponse);
    });

    it('does not change status from in_progress or other non-open statuses', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Status preservation',
        description: 'Testing status is preserved',
        category: 'billing_payments',
        priority: 'medium',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      useTicketStore.getState().updateTicketStatus(ticket.id, 'awaiting_client');

      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'customer',
        sender_name: 'Test',
        content: 'Follow up',
      });

      expect(useTicketStore.getState().getTicket(ticket.id)!.status).toBe('awaiting_client');
    });
  });

  describe('Query methods', () => {
    beforeEach(() => {
      // Add diverse tickets for querying
      useTicketStore.getState().addTicket({ subject: 'Billing 1', description: 'B1', category: 'billing_payments', priority: 'high', channel: 'email', customer_name: 'A', customer_email: 'a@b.com' });
      useTicketStore.getState().addTicket({ subject: 'Tech 1', description: 'T1', category: 'technical_support', priority: 'critical', channel: 'chat', customer_name: 'B', customer_email: 'b@b.com' });
      useTicketStore.getState().addTicket({ subject: 'Billing 2', description: 'B2', category: 'billing_payments', priority: 'low', channel: 'sms', customer_name: 'C', customer_email: 'c@b.com' });
    });

    it('getTicketsByStatus returns correct tickets', () => {
      const openTickets = useTicketStore.getState().getTicketsByStatus('open');
      expect(openTickets).toHaveLength(3);
    });

    it('getTicketsByCategory returns correct tickets', () => {
      const billingTickets = useTicketStore.getState().getTicketsByCategory('billing_payments');
      expect(billingTickets).toHaveLength(2);
      expect(billingTickets.every((t) => t.category === 'billing_payments')).toBe(true);
    });

    it('getTicketsByVariant returns correct tickets', () => {
      // Critical gets heavy, high gets medium, low gets light
      const heavyTickets = useTicketStore.getState().getTicketsByVariant('heavy');
      const mediumTickets = useTicketStore.getState().getTicketsByVariant('medium');
      const lightTickets = useTicketStore.getState().getTicketsByVariant('light');
      expect(heavyTickets).toHaveLength(1);
      expect(mediumTickets).toHaveLength(1);
      expect(lightTickets).toHaveLength(1);
    });

    it('getTicket returns ticket by id', () => {
      const ticket = useTicketStore.getState().tickets[0];
      const found = useTicketStore.getState().getTicket(ticket.id);
      expect(found).toBeDefined();
      expect(found!.id).toBe(ticket.id);
    });

    it('getTicket returns undefined for non-existent id', () => {
      const found = useTicketStore.getState().getTicket('non-existent-id');
      expect(found).toBeUndefined();
    });

    it('getTicketByNumber returns ticket by ticket_number', () => {
      const ticket = useTicketStore.getState().tickets[0];
      const found = useTicketStore.getState().getTicketByNumber(ticket.ticket_number);
      expect(found).toBeDefined();
      expect(found!.ticket_number).toBe(ticket.ticket_number);
    });
  });

  describe('ticketStats', () => {
    it('returns zeroed stats for empty store', () => {
      const stats = useTicketStore.getState().ticketStats();
      expect(stats.total).toBe(0);
      expect(stats.resolved).toBe(0);
      expect(stats.resolutionRate).toBe(0);
    });

    it('computes correct stats across multiple tickets', () => {
      // Add tickets with different statuses
      const t1 = useTicketStore.getState().addTicket({
        subject: 'Open ticket', description: 'O1', category: 'billing_payments',
        priority: 'low', channel: 'email', customer_name: 'A', customer_email: 'a@b.com',
      });
      const t2 = useTicketStore.getState().addTicket({
        subject: 'To resolve', description: 'R1', category: 'technical_support',
        priority: 'low', channel: 'chat', customer_name: 'B', customer_email: 'b@b.com',
      });
      const t3 = useTicketStore.getState().addTicket({
        subject: 'Also to resolve', description: 'R2', category: 'order_management',
        priority: 'low', channel: 'email', customer_name: 'C', customer_email: 'c@b.com',
      });

      useTicketStore.getState().resolveTicket(t2.id);
      useTicketStore.getState().resolveTicket(t3.id);

      const stats = useTicketStore.getState().ticketStats();
      expect(stats.total).toBe(3);
      expect(stats.resolved).toBe(2);
      expect(stats.resolutionRate).toBeCloseTo(66.7, 0);
      expect(stats.byStatus.open).toBe(1);
      expect(stats.byStatus.resolved).toBe(2);
    });

    it('computes total cost and savings', () => {
      useTicketStore.getState().addTicket({
        subject: 'Low cost', description: 'LC', category: 'product_information',
        priority: 'low', channel: 'chat', customer_name: 'A', customer_email: 'a@b.com',
      });
      useTicketStore.getState().addTicket({
        subject: 'High cost', description: 'HC', category: 'billing_payments',
        priority: 'critical', channel: 'email', customer_name: 'B', customer_email: 'b@b.com',
      });

      const stats = useTicketStore.getState().ticketStats();
      // light cost + heavy cost
      expect(stats.totalCost).toBeCloseTo(VARIANT_COST.light + VARIANT_COST.heavy, 4);
      expect(stats.totalSavings).toBeCloseTo(
        (12.5 - VARIANT_COST.light) + (12.5 - VARIANT_COST.heavy), 2
      );
    });
  });

  describe('Full ticket lifecycle', () => {
    it('open → in_progress → resolved flow', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Lifecycle test',
        description: 'Testing full lifecycle',
        category: 'billing_payments',
        priority: 'medium',
        channel: 'email',
        customer_name: 'Test User',
        customer_email: 'test@example.com',
      });

      // Starts as open
      expect(useTicketStore.getState().getTicket(ticket.id)!.status).toBe('open');

      // Add AI response → auto transitions to in_progress
      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'ai_agent',
        sender_name: 'PARWA AI',
        content: 'I can help with that',
      });
      expect(useTicketStore.getState().getTicket(ticket.id)!.status).toBe('in_progress');

      // Customer replies
      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'customer',
        sender_name: 'Test User',
        content: 'Thanks, that fixed it!',
      });

      // Resolve
      useTicketStore.getState().resolveTicket(ticket.id, 'Issue resolved');
      const resolved = useTicketStore.getState().getTicket(ticket.id)!;
      expect(resolved.status).toBe('resolved');
      expect(resolved.messages).toHaveLength(3); // AI + customer + resolution
    });

    it('open → in_progress → escalated flow', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Escalation flow',
        description: 'Testing escalation',
        category: 'account_management',
        priority: 'high',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'ai_agent',
        sender_name: 'PARWA AI',
        content: 'Let me help you',
      });

      useTicketStore.getState().escalateToHuman(ticket.id);

      const escalated = useTicketStore.getState().getTicket(ticket.id)!;
      expect(escalated.status).toBe('awaiting_human');
      expect(escalated.assigned_agent).toBe('Human Agent');
      expect(escalated.messages).toHaveLength(2);
    });
  });
});
