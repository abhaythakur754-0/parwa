/**
 * PARWA Tickets API — Day 3
 *
 * API functions for ticket management.
 * Currently uses mock data — will be replaced with real API calls.
 */

import { get, post, patch } from '@/lib/api';
import type {
  Ticket,
  TicketListResponse,
  TicketDetailResponse,
  TicketFilters,
  TicketSort,
  InternalNote,
  TicketMessage,
  BulkActionPayload,
} from '@/types/ticket';
import {
  mockTickets,
  getMockTicketDetail,
  filterTickets,
  sortTickets,
  paginateTickets,
} from '@/lib/mock/ticket-mock-data';

// ── Helper: simulate network delay ──────────────────────────────────────

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ── Get Ticket List ─────────────────────────────────────────────────────

export async function fetchTickets(
  page: number = 1,
  pageSize: number = 25,
  filters?: Partial<TicketFilters>,
  sort?: TicketSort
): Promise<TicketListResponse> {
  // TODO: Replace with real API call
  // return get<TicketListResponse>(`/api/tickets?page=${page}&page_size=${pageSize}`);
  await delay(300);

  let filtered = filterTickets(mockTickets, filters || {});

  if (sort) {
    filtered = sortTickets(filtered, sort.field, sort.direction);
  }

  const { items, total, totalPages } = paginateTickets(filtered, page, pageSize);

  return {
    tickets: items,
    pagination: {
      page,
      page_size: pageSize,
      total,
      total_pages: totalPages,
    },
  };
}

// ── Get Ticket Detail ───────────────────────────────────────────────────

export async function fetchTicketDetail(ticketId: string): Promise<TicketDetailResponse | null> {
  // TODO: Replace with real API call
  // return get<TicketDetailResponse>(`/api/tickets/${ticketId}`);
  await delay(200);

  const ticket = mockTickets.find((t) => t.id === ticketId);
  if (!ticket) return null;

  const detail = getMockTicketDetail(ticket);
  return {
    ticket: detail.ticket,
    messages: detail.messages,
    notes: detail.notes,
    timeline: detail.timeline,
  };
}

// ── Update Ticket Status ────────────────────────────────────────────────

export async function updateTicketStatus(
  ticketId: string,
  status: string
): Promise<Ticket> {
  // TODO: Replace with real API call
  // return patch<Ticket>(`/api/tickets/${ticketId}`, { status });
  await delay(200);

  const ticket = mockTickets.find((t) => t.id === ticketId);
  if (!ticket) throw new Error('Ticket not found');

  return { ...ticket, status: status as Ticket['status'], updated_at: new Date().toISOString() };
}

// ── Assign Ticket ───────────────────────────────────────────────────────

export async function assignTicket(
  ticketId: string,
  agentId: string
): Promise<Ticket> {
  // TODO: Replace with real API call
  // return patch<Ticket>(`/api/tickets/${ticketId}/assign`, { agent_id: agentId });
  await delay(200);

  const ticket = mockTickets.find((t) => t.id === ticketId);
  if (!ticket) throw new Error('Ticket not found');

  return { ...ticket, assigned_agent: { id: agentId, name: 'Agent', email: '', avatar_url: null, is_online: true, active_ticket_count: 0 }, updated_at: new Date().toISOString() };
}

// ── Change Ticket Priority ──────────────────────────────────────────────

export async function changePriority(
  ticketId: string,
  priority: string
): Promise<Ticket> {
  // TODO: Replace with real API call
  await delay(200);

  const ticket = mockTickets.find((t) => t.id === ticketId);
  if (!ticket) throw new Error('Ticket not found');

  return { ...ticket, priority: priority as Ticket['priority'], updated_at: new Date().toISOString() };
}

// ── Add Internal Note ───────────────────────────────────────────────────

export async function addInternalNote(
  ticketId: string,
  content: string,
  isPinned: boolean = false
): Promise<InternalNote> {
  // TODO: Replace with real API call
  // return post<InternalNote>(`/api/tickets/${ticketId}/notes`, { content, is_pinned: isPinned });
  await delay(200);

  return {
    id: crypto.randomUUID(),
    ticket_id: ticketId,
    author_id: 'current-user',
    author_name: 'You',
    content,
    is_pinned: isPinned,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

// ── Send Reply ──────────────────────────────────────────────────────────

export async function sendReply(
  ticketId: string,
  content: string
): Promise<TicketMessage> {
  // TODO: Replace with real API call
  // return post<TicketMessage>(`/api/tickets/${ticketId}/reply`, { content });
  await delay(300);

  return {
    id: crypto.randomUUID(),
    ticket_id: ticketId,
    sender_role: 'human_agent',
    sender_name: 'You',
    content,
    content_type: 'text',
    ai_confidence: null,
    sentiment: null,
    ai_technique: null,
    attachments: [],
    created_at: new Date().toISOString(),
  };
}

// ── Escalate Ticket ─────────────────────────────────────────────────────

export async function escalateTicket(
  ticketId: string,
  reason?: string
): Promise<Ticket> {
  // TODO: Replace with real API call
  await delay(200);

  const ticket = mockTickets.find((t) => t.id === ticketId);
  if (!ticket) throw new Error('Ticket not found');

  return { ...ticket, status: 'escalated', updated_at: new Date().toISOString() };
}

// ── Bulk Actions ────────────────────────────────────────────────────────

export async function executeBulkAction(payload: BulkActionPayload): Promise<{ success: boolean; count: number }> {
  // TODO: Replace with real API call
  // return post('/api/tickets/bulk-action', payload);
  await delay(500);

  return { success: true, count: payload.ticket_ids.length };
}

// ── Export Tickets ──────────────────────────────────────────────────────

export async function exportTickets(ticketIds: string[]): Promise<{ download_url: string }> {
  // TODO: Replace with real API call
  // return post('/api/tickets/export', { ticket_ids: ticketIds });
  await delay(1000);

  return { download_url: '#export-csv' };
}

export const ticketsApi = {
  fetchTickets,
  fetchTicketDetail,
  updateTicketStatus,
  assignTicket,
  changePriority,
  addInternalNote,
  sendReply,
  escalateTicket,
  executeBulkAction,
  exportTickets,
};

export default ticketsApi;
