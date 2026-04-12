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
  awaiting_client: number;
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

// ── Combined Dashboard ────────────────────────────────────────────────

export interface DashboardData {
  summary: TicketSummary;
  sla: SLAMetrics;
  by_category: CategoryDistribution[];
  trend: TrendPoint[];
  date_range: {
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

// ── Response Time Distribution ───────────────────────────────────────

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

// ── Channel Configuration ────────────────────────────────────────────

export interface ChannelConfig {
  is_enabled: boolean;
  config: Record<string, unknown>;
  auto_create_ticket: boolean;
  char_limit: number;
  allowed_file_types: string[];
  max_file_size: number;
}
