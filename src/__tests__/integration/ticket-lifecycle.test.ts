/**
 * PARWA Integration Test: Ticket Lifecycle Flow
 *
 * Tests the complete ticket lifecycle from creation through
 * resolution, including status transitions, message handling,
 * variant assignment, and statistics computation.
 */

import { useTicketStore, Ticket, TicketStats, VARIANT_COST } from '@/lib/ticket-store';
import { useVariantStore } from '@/lib/variant-store';

describe('Integration: Ticket Lifecycle Flow', () => {
  beforeEach(() => {
    useTicketStore.setState({ tickets: [], initialized: false });
    useVariantStore.getState().reset();
  });

  describe('Create → AI Response → Resolve', () => {
    it('complete lifecycle for a billing ticket', () => {
      // 1. Create ticket
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Double charge on my credit card',
        description: 'I was charged twice for my monthly subscription.',
        category: 'billing_payments',
        priority: 'high',
        channel: 'email',
        customer_name: 'Sarah Mitchell',
        customer_email: 'sarah@example.com',
      });

      // Verify initial state
      expect(ticket.status).toBe('open');
      expect(ticket.assigned_variant).toBe('medium'); // high priority → medium variant
      expect(ticket.messages).toHaveLength(0);
      expect(ticket.ai_confidence).toBe(89.7); // medium variant confidence
      expect(ticket.cost_per_ticket).toBe(VARIANT_COST.medium);

      // 2. AI responds (auto-transitions to in_progress)
      const aiMsg = useTicketStore.getState().addMessage(ticket.id, {
        sender: 'ai_agent',
        sender_name: 'PARWA AI',
        content: "I've located the duplicate charge. Initiating a refund now.",
      });

      const afterAiResponse = useTicketStore.getState().getTicket(ticket.id)!;
      expect(afterAiResponse.status).toBe('in_progress');
      expect(afterAiResponse.messages).toHaveLength(1);
      expect(afterAiResponse.first_response_at).toBeDefined();
      expect(afterAiResponse.messages[0].sender).toBe('ai_agent');

      // 3. Customer replies
      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'customer',
        sender_name: 'Sarah Mitchell',
        content: 'Thank you! When will I see the refund?',
      });

      const afterCustomerReply = useTicketStore.getState().getTicket(ticket.id)!;
      expect(afterCustomerReply.messages).toHaveLength(2);
      expect(afterCustomerReply.status).toBe('in_progress'); // Still in progress

      // 4. AI provides final answer and resolves
      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'ai_agent',
        sender_name: 'PARWA AI',
        content: 'The refund will appear within 3-5 business days.',
      });

      useTicketStore.getState().resolveTicket(ticket.id, 'Refund processed for duplicate charge');

      const resolved = useTicketStore.getState().getTicket(ticket.id)!;
      expect(resolved.status).toBe('resolved');
      expect(resolved.resolved_at).toBeDefined();
      expect(resolved.resolution_time_hours).toBeGreaterThanOrEqual(0);
      expect(resolved.messages).toHaveLength(4); // AI + customer + AI + resolution
      expect(resolved.messages[3].content).toContain('Refund processed');
    });
  });

  describe('Create → Escalate → Human takes over', () => {
    it('escalation flow for GDPR request', () => {
      // 1. Create ticket
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Delete my account and all data',
        description: 'GDPR Article 17 right to erasure request.',
        category: 'account_management',
        priority: 'high',
        channel: 'email',
        customer_name: 'Ana Garcia',
        customer_email: 'ana@example.com',
      });

      expect(ticket.status).toBe('open');
      expect(ticket.assigned_variant).toBe('medium'); // high priority

      // 2. AI responds and recognizes need for escalation
      useTicketStore.getState().addMessage(ticket.id, {
        sender: 'ai_agent',
        sender_name: 'PARWA AI',
        content: "I've received your request. Escalating to our Data Protection Officer.",
      });

      expect(useTicketStore.getState().getTicket(ticket.id)!.status).toBe('in_progress');

      // 3. Escalate to human
      useTicketStore.getState().escalateToHuman(ticket.id);

      const escalated = useTicketStore.getState().getTicket(ticket.id)!;
      expect(escalated.status).toBe('awaiting_human');
      expect(escalated.assigned_agent).toBe('Human Agent');
      expect(escalated.messages).toHaveLength(2); // AI response + escalation message
      expect(escalated.messages[1].sender).toBe('system');
      expect(escalated.messages[1].content).toContain('escalated to a human agent');
    });
  });

  describe('Multiple tickets with statistics', () => {
    it('computes accurate stats across multiple tickets', () => {
      // Create tickets of different types
      const t1 = useTicketStore.getState().addTicket({
        subject: 'FAQ Question', description: 'D1', category: 'product_information',
        priority: 'low', channel: 'chat', customer_name: 'A', customer_email: 'a@b.com',
      });

      const t2 = useTicketStore.getState().addTicket({
        subject: 'Critical outage', description: 'D2', category: 'technical_support',
        priority: 'critical', channel: 'email', customer_name: 'B', customer_email: 'b@b.com',
      });

      const t3 = useTicketStore.getState().addTicket({
        subject: 'Billing issue', description: 'D3', category: 'billing_payments',
        priority: 'high', channel: 'email', customer_name: 'C', customer_email: 'c@b.com',
      });

      const t4 = useTicketStore.getState().addTicket({
        subject: 'Return request', description: 'D4', category: 'returns_exchanges',
        priority: 'medium', channel: 'chat', customer_name: 'D', customer_email: 'd@b.com',
      });

      const t5 = useTicketStore.getState().addTicket({
        subject: 'Shipping delay', description: 'D5', category: 'shipping_delivery',
        priority: 'low', channel: 'sms', customer_name: 'E', customer_email: 'e@b.com',
      });

      // Resolve 3 of 5 tickets
      useTicketStore.getState().addMessage(t1.id, { sender: 'ai_agent', sender_name: 'AI', content: 'Answer' });
      useTicketStore.getState().resolveTicket(t1.id, 'FAQ answered');

      useTicketStore.getState().addMessage(t3.id, { sender: 'ai_agent', sender_name: 'AI', content: 'Processing' });
      useTicketStore.getState().resolveTicket(t3.id, 'Refund issued');

      useTicketStore.getState().addMessage(t4.id, { sender: 'ai_agent', sender_name: 'AI', content: 'Return label' });
      useTicketStore.getState().resolveTicket(t4.id, 'Return processed');

      // Get stats
      const stats = useTicketStore.getState().ticketStats();

      expect(stats.total).toBe(5);
      expect(stats.resolved).toBe(3);
      expect(stats.resolutionRate).toBeCloseTo(60.0, 0);

      // Check category breakdown
      expect(stats.byCategory.product_information).toBe(1);
      expect(stats.byCategory.technical_support).toBe(1);
      expect(stats.byCategory.billing_payments).toBe(1);
      expect(stats.byCategory.returns_exchanges).toBe(1);
      expect(stats.byCategory.shipping_delivery).toBe(1);

      // Check priority breakdown
      expect(stats.byPriority.low).toBe(2);
      expect(stats.byPriority.medium).toBe(1);
      expect(stats.byPriority.high).toBe(1);
      expect(stats.byPriority.critical).toBe(1);

      // Check variant breakdown
      expect(stats.byVariant.light).toBe(3);  // low priority + medium priority standard categories
      expect(stats.byVariant.medium).toBe(1);  // high priority (billing)
      expect(stats.byVariant.heavy).toBe(1);   // critical priority

      // Check channel breakdown
      expect(stats.byChannel.chat).toBe(2);
      expect(stats.byChannel.email).toBe(2);
      expect(stats.byChannel.sms).toBe(1);

      // Total cost and savings
      const expectedCost = VARIANT_COST.light * 3 + VARIANT_COST.medium + VARIANT_COST.heavy;
      expect(stats.totalCost).toBeCloseTo(expectedCost, 2);
    });
  });

  describe('Priority change updates variant and cost', () => {
    it('escalating priority re-assigns heavier variant', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Low priority issue',
        description: 'Not urgent',
        category: 'product_information',
        priority: 'low',
        channel: 'chat',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      // Low priority → light variant
      expect(ticket.assigned_variant).toBe('light');
      expect(ticket.cost_per_ticket).toBe(VARIANT_COST.light);

      // Escalate to critical
      useTicketStore.getState().updatePriority(ticket.id, 'critical');

      const updated = useTicketStore.getState().getTicket(ticket.id)!;
      expect(updated.priority).toBe('critical');
      expect(updated.assigned_variant).toBe('heavy');
      expect(updated.cost_per_ticket).toBe(VARIANT_COST.heavy);
      expect(updated.savings_per_ticket).toBeCloseTo(12.5 - VARIANT_COST.heavy);
    });

    it('downgrading priority re-assigns lighter variant', () => {
      const ticket = useTicketStore.getState().addTicket({
        subject: 'Critical issue',
        description: 'Urgent',
        category: 'technical_support',
        priority: 'critical',
        channel: 'email',
        customer_name: 'Test',
        customer_email: 'test@example.com',
      });

      expect(ticket.assigned_variant).toBe('heavy');

      // Downgrade to low
      useTicketStore.getState().updatePriority(ticket.id, 'low');

      const updated = useTicketStore.getState().getTicket(ticket.id)!;
      expect(updated.assigned_variant).toBe('light');
      expect(updated.cost_per_ticket).toBe(VARIANT_COST.light);
    });
  });

  describe('Query integration', () => {
    it('filtering by status returns correct results after lifecycle changes', () => {
      const t1 = useTicketStore.getState().addTicket({
        subject: 'T1', description: 'D1', category: 'billing_payments',
        priority: 'low', channel: 'email', customer_name: 'A', customer_email: 'a@b.com',
      });
      const t2 = useTicketStore.getState().addTicket({
        subject: 'T2', description: 'D2', category: 'technical_support',
        priority: 'low', channel: 'chat', customer_name: 'B', customer_email: 'b@b.com',
      });
      const t3 = useTicketStore.getState().addTicket({
        subject: 'T3', description: 'D3', category: 'order_management',
        priority: 'low', channel: 'email', customer_name: 'C', customer_email: 'c@b.com',
      });

      // All open
      expect(useTicketStore.getState().getTicketsByStatus('open')).toHaveLength(3);

      // Progress t1 to in_progress
      useTicketStore.getState().addMessage(t1.id, { sender: 'ai_agent', sender_name: 'AI', content: 'Help' });

      // Progress t2 to resolved
      useTicketStore.getState().resolveTicket(t2.id);

      // Progress t3 to awaiting_human
      useTicketStore.getState().escalateToHuman(t3.id);

      expect(useTicketStore.getState().getTicketsByStatus('open')).toHaveLength(0);
      expect(useTicketStore.getState().getTicketsByStatus('in_progress')).toHaveLength(1);
      expect(useTicketStore.getState().getTicketsByStatus('resolved')).toHaveLength(1);
      expect(useTicketStore.getState().getTicketsByStatus('awaiting_human')).toHaveLength(1);
    });
  });
});
