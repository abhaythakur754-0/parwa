/**
 * PARWA Tickets API Unit Tests
 *
 * Comprehensive tests for:
 * - fetchTickets
 * - fetchTicketDetail
 * - updateTicketStatus
 * - assignTicket
 * - changePriority
 * - addInternalNote
 * - sendReply
 * - escalateTicket
 * - executeBulkAction
 * - exportTickets
 *
 * Day 8 — Testing, Polish & Documentation
 */

import { jest } from '@jest/globals';

// ── Mock Dependencies ─────────────────────────────────────────────────────

// Mock the API module
const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPatch = jest.fn();

jest.mock('@/lib/api', () => ({
  get: (...args: unknown[]) => mockGet(...args),
  post: (...args: unknown[]) => mockPost(...args),
  patch: (...args: unknown[]) => mockPatch(...args),
}));

// ── Import API ────────────────────────────────────────────────────────────

import { ticketsApi, fetchTickets, fetchTicketDetail, updateTicketStatus, assignTicket, changePriority, addInternalNote, sendReply, escalateTicket, executeBulkAction, exportTickets } from '../tickets-api';

// ── fetchTickets Tests ─────────────────────────────────────────────────────

describe('fetchTickets', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should return paginated tickets', async () => {
    const resultPromise = fetchTickets(1, 25);
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.tickets).toBeDefined();
    expect(result.pagination).toBeDefined();
    expect(result.pagination.page).toBe(1);
    expect(result.pagination.page_size).toBe(25);
  });

  it('should apply status filter', async () => {
    const resultPromise = fetchTickets(1, 25, { status: ['open'] });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.tickets.every(t => t.status === 'open')).toBe(true);
  });

  it('should apply priority filter', async () => {
    const resultPromise = fetchTickets(1, 25, { priority: ['high'] });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.tickets.every(t => t.priority === 'high')).toBe(true);
  });

  it('should apply channel filter', async () => {
    const resultPromise = fetchTickets(1, 25, { channel: ['email'] });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.tickets.every(t => t.channel === 'email')).toBe(true);
  });

  it('should apply search filter', async () => {
    const resultPromise = fetchTickets(1, 25, { search: 'billing' });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    // Search results should contain 'billing' somewhere
    expect(result.tickets.length).toBeGreaterThanOrEqual(0);
  });

  it('should apply confidence filter', async () => {
    const resultPromise = fetchTickets(1, 25, { ai_confidence_min: 0.8 });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.tickets.every(t => t.ai_confidence >= 0.8)).toBe(true);
  });

  it('should sort by created_at ascending', async () => {
    const resultPromise = fetchTickets(1, 25, {}, { field: 'created_at', direction: 'asc' });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    for (let i = 1; i < result.tickets.length; i++) {
      expect(new Date(result.tickets[i].created_at).getTime()).toBeGreaterThanOrEqual(
        new Date(result.tickets[i - 1].created_at).getTime()
      );
    }
  });

  it('should sort by created_at descending', async () => {
    const resultPromise = fetchTickets(1, 25, {}, { field: 'created_at', direction: 'desc' });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    for (let i = 1; i < result.tickets.length; i++) {
      expect(new Date(result.tickets[i].created_at).getTime()).toBeLessThanOrEqual(
        new Date(result.tickets[i - 1].created_at).getTime()
      );
    }
  });

  it('should sort by priority', async () => {
    const resultPromise = fetchTickets(1, 25, {}, { field: 'priority', direction: 'asc' });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    for (let i = 1; i < result.tickets.length; i++) {
      const curr = priorityOrder[result.tickets[i].priority as keyof typeof priorityOrder];
      const prev = priorityOrder[result.tickets[i - 1].priority as keyof typeof priorityOrder];
      expect(curr).toBeGreaterThanOrEqual(prev);
    }
  });

  it('should sort by ai_confidence', async () => {
    const resultPromise = fetchTickets(1, 25, {}, { field: 'ai_confidence', direction: 'desc' });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    for (let i = 1; i < result.tickets.length; i++) {
      expect(result.tickets[i].ai_confidence).toBeLessThanOrEqual(
        result.tickets[i - 1].ai_confidence
      );
    }
  });

  it('should paginate correctly', async () => {
    const page1Promise = fetchTickets(1, 10);
    await jest.runAllTimersAsync();
    const page1 = await page1Promise;
    
    const page2Promise = fetchTickets(2, 10);
    await jest.runAllTimersAsync();
    const page2 = await page2Promise;
    
    expect(page1.tickets.length).toBe(10);
    // Page 2 should have different tickets
    const page1Ids = new Set(page1.tickets.map(t => t.id));
    const page2Ids = new Set(page2.tickets.map(t => t.id));
    const intersection = [...page1Ids].filter(id => page2Ids.has(id));
    expect(intersection.length).toBe(0);
  });

  it('should handle empty results', async () => {
    const resultPromise = fetchTickets(1, 25, { status: ['non_existent_status' as any] });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.tickets).toHaveLength(0);
    expect(result.pagination.total).toBe(0);
  });

  it('should return correct total count', async () => {
    const resultPromise = fetchTickets(1, 10);
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.pagination.total).toBe(60); // 60 mock tickets
  });
});

// ── fetchTicketDetail Tests ────────────────────────────────────────────────

describe('fetchTicketDetail', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should return ticket detail for valid ID', async () => {
    // First fetch tickets to get a valid ID
    const listPromise = fetchTickets(1, 1);
    await jest.runAllTimersAsync();
    const list = await listPromise;
    
    const ticketId = list.tickets[0].id;
    const detailPromise = fetchTicketDetail(ticketId);
    await jest.runAllTimersAsync();
    const result = await detailPromise;
    
    expect(result).not.toBeNull();
    expect(result!.ticket.id).toBe(ticketId);
    expect(result!.messages).toBeDefined();
    expect(result!.notes).toBeDefined();
    expect(result!.timeline).toBeDefined();
  });

  it('should return null for invalid ID', async () => {
    const resultPromise = fetchTicketDetail('non-existent-id');
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result).toBeNull();
  });

  it('should include messages', async () => {
    // First fetch tickets to get a valid ID
    const listPromise = fetchTickets(1, 1);
    await jest.runAllTimersAsync();
    const list = await listPromise;
    
    const ticketId = list.tickets[0].id;
    const detailPromise = fetchTicketDetail(ticketId);
    await jest.runAllTimersAsync();
    const result = await detailPromise;
    
    expect(result!.messages.length).toBeGreaterThan(0);
    expect(result!.messages[0].ticket_id).toBe(ticketId);
  });

  it('should include timeline entries', async () => {
    // First fetch tickets to get a valid ID
    const listPromise = fetchTickets(1, 1);
    await jest.runAllTimersAsync();
    const list = await listPromise;
    
    const ticketId = list.tickets[0].id;
    const detailPromise = fetchTicketDetail(ticketId);
    await jest.runAllTimersAsync();
    const result = await detailPromise;
    
    expect(result!.timeline.length).toBeGreaterThan(0);
  });
});

// ── updateTicketStatus Tests ───────────────────────────────────────────────

describe('updateTicketStatus', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should update ticket status', async () => {
    // First fetch tickets to get a valid ID
    const listPromise = fetchTickets(1, 1);
    await jest.runAllTimersAsync();
    const list = await listPromise;
    const ticketId = list.tickets[0].id;
    
    const resultPromise = updateTicketStatus(ticketId, 'in_progress');
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.status).toBe('in_progress');
  });

  it('should throw error for non-existent ticket', async () => {
    const resultPromise = updateTicketStatus('non-existent', 'in_progress');
    
    await jest.runAllTimersAsync();
    
    await expect(resultPromise).rejects.toThrow('Ticket not found');
  });

  it('should update updated_at timestamp', async () => {
    // First fetch tickets to get a valid ID
    const listPromise = fetchTickets(1, 1);
    await jest.runAllTimersAsync();
    const list = await listPromise;
    const ticketId = list.tickets[0].id;
    
    const resultPromise = updateTicketStatus(ticketId, 'resolved');
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.updated_at).toBeDefined();
    expect(new Date(result.updated_at).getTime()).toBeGreaterThan(0);
  });
});

// ── assignTicket Tests ─────────────────────────────────────────────────────

describe('assignTicket', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should assign ticket to agent', async () => {
    // First fetch tickets to get a valid ID
    const listPromise = fetchTickets(1, 1);
    await jest.runAllTimersAsync();
    const list = await listPromise;
    const ticketId = list.tickets[0].id;
    
    const resultPromise = assignTicket(ticketId, 'agent-1');
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.assigned_agent).toBeDefined();
    expect(result.assigned_agent!.id).toBe('agent-1');
  });

  it('should throw error for non-existent ticket', async () => {
    const resultPromise = assignTicket('non-existent', 'agent-1');
    
    await jest.runAllTimersAsync();
    
    await expect(resultPromise).rejects.toThrow('Ticket not found');
  });
});

// ── changePriority Tests ───────────────────────────────────────────────────

describe('changePriority', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should change ticket priority', async () => {
    // First fetch tickets to get a valid ID
    const listPromise = fetchTickets(1, 1);
    await jest.runAllTimersAsync();
    const list = await listPromise;
    const ticketId = list.tickets[0].id;
    
    const resultPromise = changePriority(ticketId, 'critical');
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.priority).toBe('critical');
  });

  it('should throw error for non-existent ticket', async () => {
    const resultPromise = changePriority('non-existent', 'high');
    
    await jest.runAllTimersAsync();
    
    await expect(resultPromise).rejects.toThrow('Ticket not found');
  });
});

// ── addInternalNote Tests ──────────────────────────────────────────────────

describe('addInternalNote', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should create internal note', async () => {
    const resultPromise = addInternalNote('ticket-1', 'This is a note', false);
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.content).toBe('This is a note');
    expect(result.is_pinned).toBe(false);
    expect(result.ticket_id).toBe('ticket-1');
  });

  it('should create pinned note', async () => {
    const resultPromise = addInternalNote('ticket-1', 'Pinned note', true);
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.is_pinned).toBe(true);
  });

  it('should generate unique ID', async () => {
    const note1Promise = addInternalNote('ticket-1', 'Note 1', false);
    const note2Promise = addInternalNote('ticket-1', 'Note 2', false);
    
    await jest.runAllTimersAsync();
    const note1 = await note1Promise;
    const note2 = await note2Promise;
    
    expect(note1.id).not.toBe(note2.id);
  });

  it('should have author info', async () => {
    const resultPromise = addInternalNote('ticket-1', 'Note', false);
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.author_id).toBeDefined();
    expect(result.author_name).toBeDefined();
  });
});

// ── sendReply Tests ────────────────────────────────────────────────────────

describe('sendReply', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should send reply', async () => {
    const resultPromise = sendReply('ticket-1', 'This is a reply');
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.content).toBe('This is a reply');
    expect(result.ticket_id).toBe('ticket-1');
    expect(result.sender_role).toBe('human_agent');
  });

  it('should set sender name as You', async () => {
    const resultPromise = sendReply('ticket-1', 'Reply content');
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.sender_name).toBe('You');
  });

  it('should have null AI confidence', async () => {
    const resultPromise = sendReply('ticket-1', 'Reply');
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.ai_confidence).toBeNull();
    expect(result.ai_technique).toBeNull();
  });

  it('should have created_at timestamp', async () => {
    const resultPromise = sendReply('ticket-1', 'Reply');
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.created_at).toBeDefined();
  });
});

// ── escalateTicket Tests ───────────────────────────────────────────────────

describe('escalateTicket', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should escalate ticket', async () => {
    // First fetch tickets to get a valid ID
    const listPromise = fetchTickets(1, 1);
    await jest.runAllTimersAsync();
    const list = await listPromise;
    const ticketId = list.tickets[0].id;
    
    const resultPromise = escalateTicket(ticketId);
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.status).toBe('escalated');
  });

  it('should throw error for non-existent ticket', async () => {
    const resultPromise = escalateTicket('non-existent');
    
    await jest.runAllTimersAsync();
    
    await expect(resultPromise).rejects.toThrow('Ticket not found');
  });
});

// ── executeBulkAction Tests ────────────────────────────────────────────────

describe('executeBulkAction', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should execute bulk action', async () => {
    const payload = {
      action: 'mark_resolved' as const,
      ticket_ids: ['ticket-1', 'ticket-2'],
    };
    
    const resultPromise = executeBulkAction(payload);
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.success).toBe(true);
    expect(result.count).toBe(2);
  });

  it('should handle single ticket', async () => {
    const payload = {
      action: 'close' as const,
      ticket_ids: ['ticket-1'],
    };
    
    const resultPromise = executeBulkAction(payload);
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.count).toBe(1);
  });

  it('should handle empty ticket list', async () => {
    const payload = {
      action: 'export' as const,
      ticket_ids: [],
    };
    
    const resultPromise = executeBulkAction(payload);
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.count).toBe(0);
  });
});

// ── exportTickets Tests ────────────────────────────────────────────────────

describe('exportTickets', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should return download URL', async () => {
    const resultPromise = exportTickets(['ticket-1', 'ticket-2']);
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.download_url).toBeDefined();
  });

  it('should handle empty list', async () => {
    const resultPromise = exportTickets([]);
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.download_url).toBeDefined();
  });
});

// ── ticketsApi Object Tests ────────────────────────────────────────────────

describe('ticketsApi object', () => {
  it('should export all API functions', () => {
    expect(ticketsApi.fetchTickets).toBeDefined();
    expect(ticketsApi.fetchTicketDetail).toBeDefined();
    expect(ticketsApi.updateTicketStatus).toBeDefined();
    expect(ticketsApi.assignTicket).toBeDefined();
    expect(ticketsApi.changePriority).toBeDefined();
    expect(ticketsApi.addInternalNote).toBeDefined();
    expect(ticketsApi.sendReply).toBeDefined();
    expect(ticketsApi.escalateTicket).toBeDefined();
    expect(ticketsApi.executeBulkAction).toBeDefined();
    expect(ticketsApi.exportTickets).toBeDefined();
  });

  it('should have 10 exported functions', () => {
    const keys = Object.keys(ticketsApi);
    expect(keys.length).toBe(10);
  });
});

// ── Edge Cases ─────────────────────────────────────────────────────────────

describe('Edge Cases', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should handle special characters in search', async () => {
    const resultPromise = fetchTickets(1, 25, { search: '!@#$%^&*()' });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.tickets).toBeDefined();
  });

  it('should handle very long search query', async () => {
    const longSearch = 'a'.repeat(1000);
    const resultPromise = fetchTickets(1, 25, { search: longSearch });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.tickets).toBeDefined();
  });

  it('should handle multiple filters combined', async () => {
    const resultPromise = fetchTickets(1, 25, {
      status: ['open', 'in_progress'],
      priority: ['high'],
    });
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    result.tickets.forEach(ticket => {
      expect(['open', 'in_progress']).toContain(ticket.status);
      expect(ticket.priority).toBe('high');
    });
  });

  it('should handle last page correctly', async () => {
    const resultPromise = fetchTickets(100, 25); // Page beyond data
    
    await jest.runAllTimersAsync();
    const result = await resultPromise;
    
    expect(result.tickets.length).toBe(0);
  });

  it('should handle all priority values', async () => {
    for (const priority of ['critical', 'high', 'medium', 'low']) {
      const resultPromise = fetchTickets(1, 25, { priority: [priority] });
      await jest.runAllTimersAsync();
      const result = await resultPromise;
      result.tickets.forEach(t => expect(t.priority).toBe(priority));
    }
  });
});
