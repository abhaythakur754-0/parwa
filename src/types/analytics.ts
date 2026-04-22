/**
 * PARWA Analytics Types
 *
 * TypeScript types for the ticket analytics API.
 * Based on backend/app/api/ticket_analytics.py and ticket_analytics_service.py
 */

// ── Date Range ────────────────────────────────────────────────────────

export interface DateRange {
  start_date: string;
  end_date: string;
}

export type IntervalType = 'hour' | 'day' | 'week' | 'month';

// ── Ticket Summary ────────────────────────────────────────────────────

export interface TicketSummary {
  total_tickets: number;
  open: number;
  in_progress: number;
  resolved: number;
  closed: number;
  awaiting_customer: number;
  awaiting_human: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  resolution_rate: number;
  avg_resolution_time_hours: number;
  avg_first_response_time_hours: number;
}

export interface TicketSummaryResponse {
  summary: TicketSummary;
  date_range: {
    start_date: string;
    end_date: string;
  };
}

// ── Trend Data ────────────────────────────────────────────────────────

export interface TrendPoint {
  timestamp: string;
  count: number;
  label: string;
}

export interface TrendPointResponse {
  trend: TrendPoint[];
  interval: IntervalType;
  date_range: {
    start_date: string;
    end_date: string;
  };
}

// ── Category Distribution ─────────────────────────────────────────────

export interface CategoryDistribution {
  category: string;
  count: number;
  percentage: number;
}

export interface CategoryDistributionResponse {
  categories: CategoryDistribution[];
  date_range: {
    start_date: string;
    end_date: string;
  };
}

// ── SLA Metrics ───────────────────────────────────────────────────────

export interface SLAMetrics {
  total_tickets_with_sla: number;
  breached_count: number;
  approaching_count: number;
  compliant_count: number;
  compliance_rate: number;
  avg_first_response_minutes: number;
  avg_resolution_minutes: number;
}

export interface SLAMetricsResponse {
  sla: SLAMetrics;
  date_range: {
    start_date: string;
    end_date: string;
  };
}

// ── Agent Metrics ─────────────────────────────────────────────────────

export interface AgentMetrics {
  agent_id: string;
  agent_name: string;
  tickets_assigned: number;
  tickets_resolved: number;
  tickets_open: number;
  avg_resolution_time_hours: number;
  csat_avg: number;
  csat_count: number;
  resolution_rate: number;
}

export interface AgentMetricsResponse {
  agents: AgentMetrics[];
  date_range: {
    start_date: string;
    end_date: string;
  };
}

// ── Response Time Distribution ─────────────────────────────────────────

export interface ResponseTimeBucket {
  bucket: string;
  count: number;
  label: string;
}

export interface ResponseTimeDistribution {
  buckets: ResponseTimeBucket[];
  avg_response_minutes: number;
  median_response_minutes: number;
  p95_response_minutes: number;
}

// ── Activity Feed (F-037) ─────────────────────────────────────────────

export type ActivityEventType =
  | 'ticket_created'
  | 'status_changed'
  | 'assigned'
  | 'resolved'
  | 'message_added'
  | 'note_added'
  | 'tag_added'
  | 'sla_warning'
  | 'attachment_added'
  | 'merged';

export interface ActivityEvent {
  event_id: string;
  event_type: ActivityEventType;
  actor_id?: string;
  actor_type?: 'human' | 'ai' | 'system' | 'customer';
  actor_name?: string;
  description: string;
  ticket_id?: string;
  ticket_subject?: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ActivityFeedResponse {
  events: ActivityEvent[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// ── Dashboard Alerts / Anomalies (F-036) ──────────────────────────────

export type AnomalySeverity = 'high' | 'medium' | 'low';
export type AnomalyType = 'volume_spike' | 'sla_breach_cluster' | 'resolution_drop' | 'csat_decline';

export interface AnomalyAlert {
  type: AnomalyType;
  severity: AnomalySeverity;
  message: string;
  detected_at: string;
}

// ── Widget Config (F-036 Layout) ───────────────────────────────────────

export interface WidgetPosition {
  row: number;
  col: number;
}

export interface WidgetSize {
  width: number;
  height: number;
}

export interface WidgetConfig {
  widget_id: string;
  widget_type: 'kpi' | 'chart' | 'feed' | 'counter' | 'table';
  title: string;
  position: WidgetPosition;
  size: WidgetSize;
  enabled?: boolean;
  refresh_interval_seconds?: number;
}

// ── Savings Summary (F-040) ───────────────────────────────────────────

export interface SavingsSummary {
  total_savings: number;
  tickets_ai: number;
  tickets_human: number;
  ai_accuracy?: number;
}

// ── Workforce Summary (F-041) ─────────────────────────────────────────

export interface WorkforceSummary {
  ai_tickets: number;
  human_tickets: number;
  ai_pct: number;
  human_pct: number;
  total: number;
}

// ── CSAT Summary (F-044) ──────────────────────────────────────────────

export interface CSATSummary {
  avg_rating: number;
  total_ratings: number;
}

// ── Dashboard Layout Response (F-036) ─────────────────────────────────

export interface DashboardLayoutResponse {
  layout_id: string;
  widgets: WidgetConfig[];
  is_default: boolean;
}

// ── Combined Dashboard (F-036: Unified Home) ───────────────────────────

export interface DashboardHomeData {
  summary: TicketSummary;
  kpis: Record<string, unknown>;
  sla: SLAMetrics;
  trend: TrendPoint[];
  by_category: CategoryDistribution[];
  activity_feed: ActivityEvent[];
  savings: SavingsSummary;
  workforce: WorkforceSummary;
  csat: CSATSummary;
  anomalies: AnomalyAlert[];
  layout?: DashboardLayoutResponse;
  generated_at?: string;
  error?: string;
}

// Keep backward-compatible alias
export interface DashboardData {
  summary: TicketSummary;
  sla: SLAMetrics;
  by_category: CategoryDistribution[];
  trend: TrendPoint[];
  date_range?: {
    start_date: string;
    end_date: string;
  };
}

export interface DashboardResponse {
  data: DashboardData;
}

// ── Channel Types ─────────────────────────────────────────────────────

export type ChannelType =
  | 'email'
  | 'chat'
  | 'sms'
  | 'voice'
  | 'whatsapp'
  | 'messenger'
  | 'twitter'
  | 'instagram'
  | 'telegram'
  | 'slack'
  | 'webchat';

export interface ChannelInfo {
  type: ChannelType;
  name: string;
  description: string;
  icon: string;
  is_enabled: boolean;
  config: Record<string, unknown>;
  auto_create_ticket: boolean;
  char_limit: number;
  allowed_file_types: string[];
  max_file_size: number;
}

export interface ChannelConfig {
  is_enabled: boolean;
  config: Record<string, unknown>;
  auto_create_ticket: boolean;
  char_limit: number;
  allowed_file_types: string[];
  max_file_size: number;
}
