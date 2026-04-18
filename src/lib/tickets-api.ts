/**
 * PARWA Tickets API — Real API Client
 *
 * API functions for ticket management.
 * Uses real HTTP calls via the centralized API client.
 */

import { get, post, patch, put, del } from '@/lib/api';
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

// ── Get Ticket List ─────────────────────────────────────────────────────

export async function fetchTickets(
  page: number = 1,
  pageSize: number = 25,
  filters?: Partial<TicketFilters>,
  sort?: TicketSort
): Promise<TicketListResponse> {
  const sp = new URLSearchParams();
  sp.set('page', String(page));
  sp.set('page_size', String(pageSize));
  if (sort) {
    sp.set('sort_by', sort.field);
    sp.set('sort_order', sort.direction);
  }
  if (filters?.status) sp.set('status', filters.status);
  if (filters?.priority) sp.set('priority', filters.priority);
  if (filters?.channel) sp.set('channel', filters.channel);
  if (filters?.search) sp.set('search', filters.search);
  if (filters?.assigned_to) sp.set('assigned_to', filters.assigned_to);
  if (filters?.date_from) sp.set('date_from', filters.date_from);
  if (filters?.date_to) sp.set('date_to', filters.date_to);
  if (filters?.category) sp.set('category', filters.category);

  const qs = sp.toString();
  return get<TicketListResponse>(`/api/tickets${qs ? `?${qs}` : ''}`);
}

// ── Get Ticket Detail ───────────────────────────────────────────────────

export async function fetchTicketDetail(ticketId: string): Promise<TicketDetailResponse | null> {
  return get<TicketDetailResponse>(`/api/tickets/${ticketId}`);
}

// ── Update Ticket Status ────────────────────────────────────────────────

export async function updateTicketStatus(
  ticketId: string,
  status: string
): Promise<Ticket> {
  return patch<Ticket>(`/api/tickets/${ticketId}/status`, { status });
}

// ── Assign Ticket ───────────────────────────────────────────────────────

export async function assignTicket(
  ticketId: string,
  agentId: string
): Promise<Ticket> {
  return post<Ticket>(`/api/tickets/${ticketId}/assign`, { assignee_id: agentId, assignee_type: 'human' });
}

// ── Change Ticket Priority ──────────────────────────────────────────────

export async function changePriority(
  ticketId: string,
  priority: string
): Promise<Ticket> {
  return patch<Ticket>(`/api/tickets/${ticketId}`, { priority });
}

// ── Add Internal Note ───────────────────────────────────────────────────

export async function addInternalNote(
  ticketId: string,
  content: string,
  isPinned: boolean = false
): Promise<InternalNote> {
  return post<InternalNote>(`/api/tickets/${ticketId}/notes`, { content, is_pinned: isPinned });
}

// ── Send Reply ──────────────────────────────────────────────────────────

export async function sendReply(
  ticketId: string,
  content: string
): Promise<TicketMessage> {
  return post<TicketMessage>(`/api/tickets/${ticketId}/messages`, { role: 'human_agent', content });
}

// ── Escalate Ticket ─────────────────────────────────────────────────────

export async function escalateTicket(
  ticketId: string,
  reason?: string
): Promise<Ticket> {
  return patch<Ticket>(`/api/tickets/${ticketId}/status`, {
    status: 'awaiting_human',
    reason: reason || 'Escalated by agent',
  });
}

// ── Bulk Actions ────────────────────────────────────────────────────────

export async function executeBulkAction(payload: BulkActionPayload): Promise<{ success: boolean; count: number }> {
  return post('/api/tickets/bulk-action', payload);
}

// ── Export Tickets ──────────────────────────────────────────────────────

export async function exportTickets(ticketIds: string[]): Promise<{ download_url: string }> {
  return post('/api/tickets/export', { ticket_ids: ticketIds });
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
