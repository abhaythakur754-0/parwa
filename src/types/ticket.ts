/**
 * PARWA Ticket Types — Day 3
 *
 * Complete type definitions for the ticket management system.
 */

// ── Enums / Unions ──────────────────────────────────────────────────────

export type TicketStatus =
  | 'open'
  | 'in_progress'
  | 'awaiting_customer'
  | 'awaiting_agent'
  | 'escalated'
  | 'resolved'
  | 'closed'
  | 'spam';

export type TicketPriority = 'critical' | 'high' | 'medium' | 'low';

export type TicketChannel =
  | 'email'
  | 'chat'
  | 'sms'
  | 'voice'
  | 'slack'
  | 'webchat';

export type TicketSentiment = 'positive' | 'neutral' | 'negative' | 'mixed';

export type GSDState =
  | 'greeting'
  | 'understanding'
  | 'resolution'
  | 'confirmation'
  | 'closing';

export type AITechnique =
  | 'knowledge_base'
  | 'sentiment_match'
  | 'intent_classification'
  | 'entity_extraction'
  | 'conversation_flow'
  | 'escalation_trigger'
  | 'template_response'
  | 'fallback';

export type SenderRole = 'customer' | 'ai_agent' | 'human_agent' | 'system';

// ── Message ─────────────────────────────────────────────────────────────

export interface TicketMessage {
  id: string;
  ticket_id: string;
  sender_role: SenderRole;
  sender_name: string;
  content: string;
  content_type: 'text' | 'html' | 'markdown';
  ai_confidence: number | null;
  sentiment: TicketSentiment | null;
  ai_technique: AITechnique | null;
  attachments: TicketAttachment[];
  created_at: string;
  metadata?: Record<string, unknown>;
}

// ── Attachment ──────────────────────────────────────────────────────────

export interface TicketAttachment {
  id: string;
  filename: string;
  file_url: string;
  file_type: 'image' | 'document' | 'video' | 'audio' | 'other';
  file_size_bytes: number;
  uploaded_at: string;
}

// ── Internal Note ───────────────────────────────────────────────────────

export interface InternalNote {
  id: string;
  ticket_id: string;
  author_id: string;
  author_name: string;
  content: string;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

// ── Timeline Entry ──────────────────────────────────────────────────────

export interface TimelineEntry {
  id: string;
  ticket_id: string;
  event_type: string;
  description: string;
  actor_name: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

// ── Customer Info ───────────────────────────────────────────────────────

export interface CustomerInfo {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  avatar_url: string | null;
  company: string | null;
  total_tickets: number;
  resolved_tickets: number;
  avg_csat: number | null;
  first_seen: string;
  last_active: string;
  tags: string[];
}

// ── Ticket ──────────────────────────────────────────────────────────────

export interface Ticket {
  id: string;
  ticket_number: string;
  subject: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  channel: TicketChannel;
  customer: CustomerInfo;
  assigned_agent: AgentInfo | null;
  ai_confidence: number;
  sentiment: TicketSentiment;
  gsd_state: GSDState;
  ai_technique: AITechnique;
  resolution_time_minutes: number | null;
  first_response_time_minutes: number | null;
  sla_deadline: string | null;
  sla_breached: boolean;
  sla_approaching: boolean;
  is_ai_resolved: boolean;
  tags: string[];
  message_count: number;
  unread_count: number;
  has_attachments: boolean;
  variant_id: string | null;
  variant_name: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

// ── Agent Info ──────────────────────────────────────────────────────────

export interface AgentInfo {
  id: string;
  name: string;
  email: string;
  avatar_url: string | null;
  is_online: boolean;
  active_ticket_count: number;
}

// ── Filter / Sort Types ─────────────────────────────────────────────────

export interface TicketFilters {
  status?: TicketStatus[];
  channel?: TicketChannel[];
  agent_id?: string[];
  priority?: TicketPriority[];
  ai_confidence_min?: number;
  ai_confidence_max?: number;
  date_from?: string;
  date_to?: string;
  search?: string;
}

export type TicketSortField =
  | 'ticket_number'
  | 'status'
  | 'priority'
  | 'channel'
  | 'assigned_agent'
  | 'ai_confidence'
  | 'created_at'
  | 'updated_at';

export type TicketSortDirection = 'asc' | 'desc';

export interface TicketSort {
  field: TicketSortField;
  direction: TicketSortDirection;
}

// ── Pagination ──────────────────────────────────────────────────────────

export interface TicketPagination {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

// ── API Response ────────────────────────────────────────────────────────

export interface TicketListResponse {
  tickets: Ticket[];
  pagination: TicketPagination;
}

export interface TicketDetailResponse {
  ticket: Ticket;
  messages: TicketMessage[];
  notes: InternalNote[];
  timeline: TimelineEntry[];
}

// ── Bulk Action ─────────────────────────────────────────────────────────

export type BulkActionType =
  | 'mark_resolved'
  | 'assign_agent'
  | 'change_priority'
  | 'export'
  | 'close';

export interface BulkActionPayload {
  action: BulkActionType;
  ticket_ids: string[];
  data?: {
    agent_id?: string;
    priority?: TicketPriority;
    status?: TicketStatus;
  };
}

// ── Status/Channel/Priority Config ──────────────────────────────────────

export interface StatusConfig {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

export interface PriorityConfig {
  label: string;
  color: string;
  bgColor: string;
  icon: string;
}

export interface ChannelConfig {
  label: string;
  icon: string;
  color: string;
}
