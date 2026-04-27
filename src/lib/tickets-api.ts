/**
 * PARWA Tickets API Client
 *
 * Dedicated API client for all ticket-related endpoints.
 * Full TypeScript types matching the backend schema.
 */

import { get, post, patch, put, del } from '@/lib/api';

// ── Ticket Types ─────────────────────────────────────────────────────────

export type TicketStatus =
  | 'open'
  | 'assigned'
  | 'in_progress'
  | 'awaiting_customer'
  | 'awaiting_human'
  | 'resolved'
  | 'reopened'
  | 'closed'
  | 'frozen'
  | 'queued'
  | 'stale';

export type TicketPriority = 'critical' | 'high' | 'medium' | 'low';

export type TicketChannel = 'email' | 'chat' | 'sms' | 'voice' | 'slack' | 'webchat';

export type TicketCategory =
  | 'tech_support'
  | 'billing'
  | 'feature_request'
  | 'bug_report'
  | 'general'
  | 'complaint';

export type MessageRole = 'customer' | 'agent' | 'ai' | 'system';

export interface TicketResponse {
  id: string;
  company_id: string;
  customer_id: string | null;
  channel: string;
  status: string;
  subject: string | null;
  priority: string;
  category: string | null;
  tags: string[];
  agent_id: string | null;
  assigned_to: string | null;
  classification_intent: string | null;
  classification_type: string | null;
  metadata_json: Record<string, unknown>;
  reopen_count: number;
  frozen: boolean;
  is_spam: boolean;
  awaiting_human: boolean;
  awaiting_customer: boolean;
  escalation_level: number;
  sla_breached: boolean;
  first_response_at: string | null;
  resolution_target_at: string | null;
  variant_version: string | null;
  plan_snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  // Computed
  is_open: boolean;
  is_resolved: boolean;
  is_closed: boolean;
  time_since_created: string | null;
  time_since_updated: string | null;
}

export interface MessageResponse {
  id: string;
  ticket_id: string;
  role: string;
  content: string;
  channel: string;
  is_internal: boolean;
  is_redacted: boolean;
  ai_confidence: number | null;
  variant_version: string | null;
  created_at: string;
}

export interface NoteResponse {
  id: string;
  ticket_id: string;
  author_id: string;
  content: string;
  is_pinned: boolean;
  created_at: string;
}

export interface TimelineEvent {
  id: string;
  type: string;
  timestamp: string;
  actor_id: string | null;
  actor_type: string;
  old_value: string | null;
  new_value: string | null;
  reason: string | null;
  metadata: Record<string, unknown> | null;
}

export interface AttachmentResponse {
  id: string;
  ticket_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  url: string;
  uploaded_by: string | null;
  created_at: string;
}

export interface TicketListResponse {
  items: TicketResponse[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface MessageListResponse {
  messages: MessageResponse[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface NoteListResponse {
  notes: NoteResponse[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TimelineResponse {
  events: TimelineEvent[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TimelineSummary {
  total_events: number;
  messages_count: number;
  notes_count: number;
  status_changes: number;
  assignments: number;
  escalations: number;
  sla_events: number;
}

export interface AttachmentListResponse {
  attachments: AttachmentResponse[];
  total: number;
}

// ── Query Parameter Types ───────────────────────────────────────────────

export interface TicketListParams {
  status?: TicketStatus[];
  priority?: TicketPriority[];
  category?: TicketCategory[];
  channel?: TicketChannel;
  assigned_to?: string;
  customer_id?: string;
  search?: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface MessageListParams {
  include_internal?: boolean;
  role?: MessageRole;
  page?: number;
  page_size?: number;
  order?: 'asc' | 'desc';
}

export interface NoteListParams {
  pinned_only?: boolean;
  page?: number;
  page_size?: number;
  order?: 'asc' | 'desc';
}

export interface TimelineParams {
  include_messages?: boolean;
  include_notes?: boolean;
  activity_types?: string[];
  page?: number;
  page_size?: number;
}

// ── Request Body Types ──────────────────────────────────────────────────

export interface CreateMessageRequest {
  role: MessageRole;
  content: string;
  channel?: string;
  is_internal?: boolean;
  metadata_json?: Record<string, unknown>;
  ai_confidence?: number;
}

export interface UpdateTicketRequest {
  subject?: string;
  priority?: TicketPriority;
  category?: TicketCategory;
  tags?: string[];
  metadata_json?: Record<string, unknown>;
}

export interface UpdateStatusRequest {
  status: TicketStatus;
  reason?: string;
}

export interface AssignTicketRequest {
  assignee_id: string;
  assignee_type: 'human' | 'ai';
  reason?: string;
}

export interface CreateNoteRequest {
  content: string;
  is_pinned?: boolean;
}

export interface BulkStatusRequest {
  ticket_ids: string[];
  status: TicketStatus;
  reason?: string;
}

export interface BulkAssignRequest {
  ticket_ids: string[];
  assignee_id: string;
  assignee_type: 'human' | 'ai';
  reason?: string;
}

// ── Tickets API ─────────────────────────────────────────────────────────

export const ticketsApi = {
  // ── Ticket CRUD ───────────────────────────────────────────────────
  list: (params?: TicketListParams) => {
    const sp = new URLSearchParams();
    if (params) {
      if (params.status?.length) params.status.forEach(s => sp.append('status[]', s));
      if (params.priority?.length) params.priority.forEach(p => sp.append('priority[]', p));
      if (params.category?.length) params.category.forEach(c => sp.append('category[]', c));
      if (params.channel) sp.set('channel', params.channel);
      if (params.assigned_to) sp.set('assigned_to', params.assigned_to);
      if (params.customer_id) sp.set('customer_id', params.customer_id);
      if (params.search) sp.set('search', params.search);
      if (params.page) sp.set('page', String(params.page));
      if (params.page_size) sp.set('page_size', String(params.page_size));
      if (params.sort_by) sp.set('sort_by', params.sort_by);
      if (params.sort_order) sp.set('sort_order', params.sort_order);
    }
    const qs = sp.toString();
    return get<TicketListResponse>(`/api/tickets${qs ? `?${qs}` : ''}`);
  },

  get: (id: string) =>
    get<TicketResponse>(`/api/tickets/${id}`),

  update: (id: string, data: UpdateTicketRequest) =>
    put<TicketResponse>(`/api/tickets/${id}`, data),

  updateStatus: (id: string, data: UpdateStatusRequest) =>
    patch<TicketResponse>(`/api/tickets/${id}/status`, data),

  assign: (id: string, data: AssignTicketRequest) =>
    post<TicketResponse>(`/api/tickets/${id}/assign`, data),

  // ── Bulk Operations ──────────────────────────────────────────────
  bulkUpdateStatus: (data: BulkStatusRequest) =>
    post<{ updated: number }>('/api/tickets/bulk/status', data),

  bulkAssign: (data: BulkAssignRequest) =>
    post<{ updated: number }>('/api/tickets/bulk/assign', data),

  // ── Messages ─────────────────────────────────────────────────────
  getMessages: (ticketId: string, params?: MessageListParams) => {
    const sp = new URLSearchParams();
    if (params) {
      if (params.include_internal !== undefined) sp.set('include_internal', String(params.include_internal));
      if (params.role) sp.set('role', params.role);
      if (params.page) sp.set('page', String(params.page));
      if (params.page_size) sp.set('page_size', String(params.page_size));
      if (params.order) sp.set('order', params.order);
    }
    const qs = sp.toString();
    return get<MessageListResponse>(`/api/tickets/${ticketId}/messages${qs ? `?${qs}` : ''}`);
  },

  createMessage: (ticketId: string, data: CreateMessageRequest) =>
    post<MessageResponse>(`/api/tickets/${ticketId}/messages`, data),

  updateMessage: (ticketId: string, messageId: string, data: Partial<CreateMessageRequest>) =>
    put<MessageResponse>(`/api/tickets/${ticketId}/messages/${messageId}`, data),

  deleteMessage: (ticketId: string, messageId: string) =>
    del<void>(`/api/tickets/${ticketId}/messages/${messageId}`),

  redactMessage: (ticketId: string, messageId: string) =>
    post<MessageResponse>(`/api/tickets/${ticketId}/messages/${messageId}/redact`),

  // ── Notes ────────────────────────────────────────────────────────
  getNotes: (ticketId: string, params?: NoteListParams) => {
    const sp = new URLSearchParams();
    if (params) {
      if (params.pinned_only) sp.set('pinned_only', 'true');
      if (params.page) sp.set('page', String(params.page));
      if (params.page_size) sp.set('page_size', String(params.page_size));
      if (params.order) sp.set('order', params.order);
    }
    const qs = sp.toString();
    return get<NoteListResponse>(`/api/tickets/${ticketId}/notes${qs ? `?${qs}` : ''}`);
  },

  createNote: (ticketId: string, data: CreateNoteRequest) =>
    post<NoteResponse>(`/api/tickets/${ticketId}/notes`, data),

  updateNote: (ticketId: string, noteId: string, data: { content: string }) =>
    put<NoteResponse>(`/api/tickets/${ticketId}/notes/${noteId}`, data),

  deleteNote: (ticketId: string, noteId: string) =>
    del<void>(`/api/tickets/${ticketId}/notes/${noteId}`),

  togglePinNote: (ticketId: string, noteId: string) =>
    patch<NoteResponse>(`/api/tickets/${ticketId}/notes/${noteId}/pin`),

  // ── Timeline ─────────────────────────────────────────────────────
  getTimeline: (ticketId: string, params?: TimelineParams) => {
    const sp = new URLSearchParams();
    if (params) {
      if (params.include_messages !== undefined) sp.set('include_messages', String(params.include_messages));
      if (params.include_notes !== undefined) sp.set('include_notes', String(params.include_notes));
      if (params.activity_types?.length) params.activity_types.forEach(t => sp.append('activity_types', t));
      if (params.page) sp.set('page', String(params.page));
      if (params.page_size) sp.set('page_size', String(params.page_size));
    }
    const qs = sp.toString();
    return get<TimelineResponse>(`/api/tickets/${ticketId}/timeline${qs ? `?${qs}` : ''}`);
  },

  getTimelineSummary: (ticketId: string) =>
    get<TimelineSummary>(`/api/tickets/${ticketId}/timeline/summary`),

  // ── Attachments ──────────────────────────────────────────────────
  getAttachments: (ticketId: string) =>
    get<AttachmentListResponse>(`/api/tickets/${ticketId}/attachments`),

  uploadAttachment: async (ticketId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`/api/tickets/${ticketId}/attachments`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });
    if (!response.ok) throw new Error('Failed to upload attachment');
    return response.json() as Promise<AttachmentResponse>;
  },
};

export default ticketsApi;
